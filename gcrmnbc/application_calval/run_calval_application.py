from argparse import ArgumentParser
from logging import Logger
import os
import shlex
import subprocess

from bfgn.data_management import apply_model_to_data, data_core
from bfgn.experiments import experiments
from bfgn.utils import logging

from gcrmnbc.utils import encodings, shared_configs


_DIR_MODELS = '../models'
_DIR_CONFIGS = '../configs'
_DIR_CALVAL_SRC = '/scratch/nfabina/gcrmn-benthic-classification/evaluation_data'
DIR_APPLIED_DEST = '/scratch/nfabina/gcrmn-benthic-classification/applied_data'

FILENAME_COMPLETE = 'calval_application.complete'


def run_application(config_name: str, response_mapping: str) -> None:
    _assert_encoding_assumptions_hold()
    filepath_config = os.path.join(_DIR_CONFIGS, config_name + '.yaml')
    config = shared_configs.build_dynamic_config(filepath_config, response_mapping)

    # Get paths and logger
    log_out = os.path.join(_DIR_MODELS, config_name, response_mapping, 'run_calval_application.log')
    if not os.path.exists(os.path.dirname(log_out)):
        os.makedirs(os.path.dirname(log_out))
    logger = logging.get_root_logger(log_out)

    # Build dataset
    data_container = data_core.DataContainer(config)
    data_container.build_or_load_rawfile_data()
    data_container.build_or_load_scalers()
    data_container.load_sequences()

    # Build experiment
    experiment = experiments.Experiment(config)
    experiment.build_or_load_model(data_container)

    # Apply model
    reefs = sorted([reef for reef in os.listdir(_DIR_CALVAL_SRC)])
    dir_model_out = os.path.join(DIR_APPLIED_DEST, config_name, response_mapping)
    for idx_filepath, reef in enumerate(reefs):
        logger.debug('Applying model to reef {}'.format(reef))
        dir_reef_in = os.path.join(_DIR_CALVAL_SRC, reef)
        dir_reef_out = os.path.join(dir_model_out, reef)
        _apply_to_raster(experiment, data_container, dir_reef_in, dir_reef_out, logger)

    # Create application.complete if all files are done
    are_reefs_complete = list()
    for reef in reefs:
        filepath_reef_complete = os.path.join(dir_model_out, reef, FILENAME_COMPLETE)
        are_reefs_complete.append(os.path.exists(filepath_reef_complete))
    if all(are_reefs_complete):
        filepath_model_complete = os.path.join(dir_model_out, FILENAME_COMPLETE)
        open(filepath_model_complete, 'w')


def _apply_to_raster(
        experiment: experiments.Experiment,
        data_container: data_core.DataContainer,
        dir_reef_in: str,
        dir_reef_out: str,
        logger: Logger
) -> None:
    if not os.path.exists(dir_reef_out):
        try:
            os.makedirs(dir_reef_out)
        except FileExistsError:
            pass

    # Set filepaths
    filepath_probs = os.path.join(dir_reef_out, 'calval_probs.tif')
    filepath_mle = os.path.join(dir_reef_out, 'calval_mle.tif')
    filepath_reef_raster = os.path.join(dir_reef_out, 'calval_reefs.tif')
    filepath_reef_shapefile = os.path.join(dir_reef_out, 'calval_reefs.shp')
    filepaths_out = (filepath_probs, filepath_mle, filepath_reef_raster, filepath_reef_shapefile)
    filepath_lock = os.path.join(dir_reef_out, 'calval_apply.lock')
    filepath_complete = os.path.join(dir_reef_out, FILENAME_COMPLETE)
    filepath_features = os.path.join(dir_reef_in, 'features.vrt')

    # Return early if application is completed or in progress
    if all([os.path.exists(filepath) for filepath in filepaths_out]):
        logger.debug('Skipping application:  output files already exist')
        open(filepath_complete, 'w')
        return
    if os.path.exists(filepath_lock):
        logger.debug('Skipping application:  lock file already exists at {}'.format(filepath_lock))
        return

    # Acquire the file lock or return if we lose the race condition
    try:
        file_lock = open(filepath_lock, 'x')
    except OSError:
        logger.debug('Skipping application:  lock file acquired by another process at {}'.format(filepath_lock))
        return

    # Apply model to raster and clean up file lock
    try:
        basename_probs = os.path.splitext(filepath_probs)[0]
        basename_mle = os.path.splitext(filepath_mle)[0]
        apply_model_to_data.apply_model_to_site(
            experiment.model, data_container, [filepath_features], basename_probs, exclude_feature_nodata=True)
        apply_model_to_data.maximum_likelihood_classification(
            filepath_probs, data_container, basename_mle, creation_options=['TILED=YES', 'COMPRESS=DEFLATE'])
        _create_reef_only_raster(filepath_mle, filepath_reef_raster, logger)
        _create_reef_only_shapefile(filepath_reef_raster, filepath_reef_shapefile, logger)
        logger.debug('Application success, removing lock file and placing complete file')
        open(filepath_complete, 'w')
    except Exception as error_:
        raise error_
    finally:
        file_lock.close()
        os.remove(filepath_lock)
        logger.debug('Lock file removed')


def _create_reef_only_raster(filepath_mle: str, filepath_reef_raster: str, logger: Logger) -> None:
    min_reef_value = min(encodings.MAPPINGS[encodings.REEF_TOP], encodings.MAPPINGS[encodings.NOT_REEF_TOP])
    command = 'gdal_calc.py -A {filepath_mle} --outfile={filepath_reef} --type=Byte --NoDataValue=0 ' + \
              '--calc="1*(A>={min_value}) + 0*(A<{min_value})"'
    command = command.format(
        filepath_mle=filepath_mle, filepath_reef=filepath_reef_raster, min_value=min_reef_value)
    completed = subprocess.run(shlex.split(command), capture_output=True)
    if completed.stderr:
        logger.error('gdalinfo stdout:  {}'.format(completed.stdout.decode('utf-8')))
        logger.error('gdalinfo stderr:  {}'.format(completed.stderr.decode('utf-8')))
        raise AssertionError('Unknown error in reef raster generation, see above log lines')


def _create_reef_only_shapefile(filepath_reef_raster: str, filepath_reef_shapefile: str, logger: Logger) -> None:
    command = 'gdal_polygonize.py {} {}'.format(filepath_reef_raster, filepath_reef_shapefile)
    completed = subprocess.run(shlex.split(command), capture_output=True)
    if completed.stderr:
        logger.error('gdalinfo stdout:  {}'.format(completed.stdout.decode('utf-8')))
        logger.error('gdalinfo stderr:  {}'.format(completed.stderr.decode('utf-8')))
        raise AssertionError('Unknown error in reef outline generation, see above log lines')


def _assert_encoding_assumptions_hold():
    """
    We'd like to get land, water, reef top, and not reef top areas for sampling. Training data is generated by sampling
    images for areas where the features and responses have enough data, but we'd also like more feature context for the
    labelled reef areas.

    We want to buffer out reef areas to get more context, but we don't really need to buffer out land or water areas
    because we'll probably get plenty adjacent to the reefs themselves. We can add in additional water or land pretty
    easily but just manually selecting large swaths of land or reef in the images themselves; e.g., here's a giant
    patch of blue water or turbid water, use that as a water class (that's probably necessary due to the format of the
    new training data, which has very little land or water selected).

    Here, we just assert that reef top and not reef top are still the classes with the greatest numbered labels after
    removing cloud-shade and unknown. The gdal_calc commands depend on this assumption.
    """
    max_other = max(encodings.MAPPINGS[encodings.LAND], encodings.MAPPINGS[encodings.WATER])
    reef_top = encodings.MAPPINGS[encodings.REEF_TOP]
    not_reef_top = encodings.MAPPINGS[encodings.NOT_REEF_TOP]
    assert reef_top > max_other and not_reef_top > max_other, 'Please see _assert_encoding_assumptions_hold for details'


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config_name', required=True)
    parser.add_argument('--response_mapping', required=True)
    args = parser.parse_args()
    run_application(args.config_name, args.response_mapping)
