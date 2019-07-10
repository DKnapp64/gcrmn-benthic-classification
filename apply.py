from argparse import ArgumentParser
import os

from rsCNN.configuration import configs
from rsCNN.data_management import apply_model_to_data, data_core
from rsCNN.experiments import experiments


_DIR_MODELS = 'models'
_DIR_APPLIED = 'applied'
_DIR_DATA_BASE = '/scratch/nfabina/gcrmn-benthic-classification'
_DIR_DATA_BUILT = os.path.join(_DIR_DATA_BASE, 'built')
_DIR_DATA_APPLY = os.path.join(_DIR_DATA_BASE, 'for_application')


def apply(filepath_config: str) -> None:
    config = configs.create_config_from_file(filepath_config)
    config_name = os.path.splitext(os.path.basename(filepath_config))[0]

    # Update config with filesystem references or potentially dynamic values
    config.data_build.dir_out = _DIR_DATA_BUILT
    config.model_training.dir_out = os.path.join(_DIR_MODELS, config_name)

    # Build dataset
    data_container = data_core.DataContainer(config)
    data_container.build_or_load_rawfile_data()
    data_container.build_or_load_scalers()
    data_container.load_sequences()

    # Build experiment
    experiment = experiments.Experiment(config)
    experiment.build_or_load_model(data_container)

    # Apply model
    dir_applied = os.path.join(config.model_training.dir_out, _DIR_APPLIED)
    filenames_apply = os.listdir(_DIR_DATA_APPLY)
    for idx_apply, filename_apply in enumerate(filenames_apply):
        filepath_in = os.path.join(_DIR_DATA_APPLY, filename_apply)
        filepath_out = os.path.join(dir_applied, filename_apply)
        apply_model_to_data.apply_model_to_raster(experiment.model, data_container, filepath_in, filepath_out)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--filepath_config', dest='filepath_config', required=True)
    filepath_config = vars(parser.parse_args())['filepath_config']
    apply(filepath_config=filepath_config)
