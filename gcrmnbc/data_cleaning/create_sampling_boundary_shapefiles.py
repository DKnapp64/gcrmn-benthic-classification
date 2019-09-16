import logging
import os
import re
import shlex
import subprocess

from gcrmnbc.utils import encodings


_logger = logging.getLogger(__name__)
_logger.setLevel('DEBUG')
_formatter = logging.Formatter(fmt='%(asctime)s - %(processName)s - %(name)s - %(levelname)s - %(message)s')
_handler = logging.FileHandler('rasterize_response_quads.log')
_handler.setFormatter(_formatter)
_logger.addHandler(_handler)


DIR_DATA = '/scratch/nfabina/gcrmn-benthic-classification/training_data'
DIR_DATA_TMP = os.path.join(DIR_DATA, 'tmp')
DIR_DATA_CLEAN = os.path.join(DIR_DATA, 'clean')


def create_sampling_boundary_shapefiles() -> None:
    _assert_encoding_assumptions_hold()
    # Get list of completed responses rasters
    filepath_reef_raster = os.path.join(DIR_DATA_TMP, 'tmp_reef_only.tif')
    filepath_reef_outline = os.path.join(DIR_DATA_TMP, 'tmp_reef_outline.shp')
    basename_reef_outline = os.path.splitext(os.path.basename(filepath_reef_outline))[0]
    filepaths_responses = sorted([os.path.join(DIR_DATA_CLEAN, filename) for filename in os.listdir(DIR_DATA_CLEAN)
                                  if filename.endswith('_responses.tif')])
    for idx_responses, filepath_responses in enumerate(filepaths_responses):
        _logger.debug('Creating boundaries for response file {} of {}'.format(idx_responses, len(filepaths_responses)))
        filepath_boundary = re.sub('responses.tif', 'boundaries.shp', filepath_responses)
        # Get raster of only reef areas
        command = 'gdal_calc.py - A {filepath_responses} -outfile={filepath_reef} -NoDataValue=-9999 ' + \
                  '-calc="1*(A>2) + -9999*(A<=2)" -quit'
        command = command.format(filepath_responses=filepath_responses, filepath_reef=filepath_reef_raster)
        subprocess.run(shlex.split(command))
        # Get shapefile of reef outline
        command = 'gdal_polygonize.py -q {} {}'.format(filepath_reef_raster, filepath_reef_outline)
        subprocess.run(shlex.split(command))
        # Get shapefile of sampling boundaries by buffering reef outline
        command = 'ogr2ogr -f "ESRI Shapefile" {filepath_boundary} {filepath_outline} -dialect sqlite ' + \
                  '-sql "select ST_buffer(geometry, 200) as geometry from test_outline"'
        command = command.format(filepath_boundary=filepath_boundary, filepath_outline=filepath_reef_outline)
        subprocess.run(shlex.split(command))
        # Clean up
        os.remove(filepath_reef_raster)
        for filename_outline in os.listdir(DIR_DATA_TMP):
            if not re.search(basename_reef_outline, filename_outline):
                continue
            os.remove(os.path.join(DIR_DATA_TMP, filename_outline))


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
    max_other = max(encodings.LAND, encodings.WATER)
    assert encodings.REEF_TOP > max_other and encodings.NOT_REEF_TOP > max_other, \
        'Please see _assert_encoding_assumptions_hold for details'