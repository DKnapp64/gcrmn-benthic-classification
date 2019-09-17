import os
import shutil

import gdal

from gcrmnbc.utils import logs


_logger = logs.get_logger(__name__)


DIR_BASE = '/scratch/nfabina/gcrmn-benthic-classification/training_data'
DIR_CLEAN = os.path.join(DIR_BASE, 'clean')
DIR_TMP = os.path.join(DIR_BASE, 'tmp')


def compress_feature_response_rasters() -> None:
    _logger.info('Compress feature rasters')
    filepaths_features = [os.path.join(DIR_CLEAN, fn) for fn in os.listdir(DIR_CLEAN) if fn.endswith('.tif')]
    filepath_tmp = os.path.join(DIR_TMP, 'tmp_compress.tif')
    for idx_filepath, filepath_clean in enumerate(filepaths_features):
        _logger.debug('Compressing raster {} of {}:  {}'.format(
            1+idx_filepath, len(filepaths_features), filepath_clean))
        options_translate = gdal.TranslateOptions(creationOptions=['COMPRESS=DEFLATE', 'TILED=YES'])
        gdal.Translate(filepath_tmp, filepath_clean, options=options_translate)
        shutil.copy(filepath_tmp, filepath_clean)
        os.remove(filepath_tmp)


if __name__ == '__main__':
    compress_feature_response_rasters()