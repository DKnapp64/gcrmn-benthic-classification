import os
import re

from gcrmnbc.utils import data_bucket, logs, paths


_logger = logs.get_logger(__file__)


def download_training_feature_quads() -> None:
    _logger.debug('Download training feature quads')
    # Get list of response files from UQ training data
    filenames = [filename for filename in os.listdir(paths.DIR_DATA_TRAIN_RAW) if filename.endswith('.shp')]
    # Get list of response files from UQ training data and supplemental training data
    filenames.extend([filename for filename in os.listdir(paths.DIR_DATA_TRAIN_CLEAN) if filename.endswith('.shp')])
    # Get list of of response files from Millennium Project training data
    filenames.extend([fn for fn in os.listdir(paths.DIR_DATA_TRAIN_RAW_MP) if fn.endswith('responses.shp')])
    quads = set()
    for filename in filenames:
        quad_name = re.search(r'L15-\d{4}E-\d{4}N', filename).group()
        if quad_name:
            quads.add(quad_name)
    quad_blobs = [quad_blob for quad_blob in data_bucket.get_imagery_quad_blobs() if quad_blob.quad_focal in quads]
    for idx_blob, quad_blob in enumerate(quad_blobs):
        _logger.debug('Downloading blob {} of {}'.format(1+idx_blob, len(quad_blobs)))
        data_bucket.download_model_training_input_data_for_quad_blob(paths.DIR_DATA_TRAIN_RAW, quad_blob)


if __name__ == '__main__':
    download_training_feature_quads()
