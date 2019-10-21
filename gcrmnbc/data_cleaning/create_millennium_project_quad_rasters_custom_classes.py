from collections import OrderedDict
import os
import re

import fiona
import fiona.crs
from osgeo import gdal
from tqdm import tqdm

from gcrmnbc.utils import encodings_mp, gdal_command_line, logs, paths


_logger = logs.get_logger(__file__)


SHAPEFILE_DRIVER = 'ESRI Shapefile'
SHAPEFILE_EPSG = 3857
SHAPEFILE_SCHEMA = {'properties': OrderedDict([('custom_class', 'int')]), 'geometry': 'Polygon'}


def create_millennium_project_quad_rasters_custom_classes() -> None:
    _logger.info('Create Millennium Project response quad rasters')
    if not os.path.exists(paths.DIR_DATA_TRAIN_CLEAN_MP):
        os.makedirs(paths.DIR_DATA_TRAIN_CLEAN_MP)
    filenames_polys = [
        filename for filename in os.listdir(paths.DIR_DATA_TRAIN_RAW_MP)
        if filename.startswith('L15-') and filename.endswith('responses.shp')
    ]
    missing_features = list()
    for idx_filename, filename_poly in enumerate(tqdm(filenames_polys, desc='Create Millennium Project rasters')):
        _logger.debug('Create raster {} ({} total):  {}'.format(idx_filename, len(filenames_polys), filename_poly))
        # Set filepaths
        filepath_src = os.path.join(paths.DIR_DATA_TRAIN_RAW_MP, filename_poly)
        filename_custom = re.sub('responses.shp', 'responses_custom.shp', filename_poly)
        filepath_custom = os.path.join(paths.DIR_DATA_TRAIN_RAW_MP, filename_custom)
        filename_raster = re.sub('.shp', '_custom.tif', filename_poly)
        filepath_dest = os.path.join(paths.DIR_DATA_TRAIN_CLEAN_MP, filename_raster)
        if os.path.exists(filepath_dest):
            continue

        # Try to find existing features file, may be either raw or clean, but also may not be available from Vulcan
        filename_features = re.search(r'L15-\d{4}E-\d{4}N', filename_poly).group() + '_features.tif'
        filepath_features = os.path.join(paths.DIR_DATA_TRAIN_RAW, filename_features)
        if not os.path.exists(filepath_features):
            filepath_features = os.path.join(paths.DIR_DATA_TRAIN_CLEAN, filename_features)
        if not os.path.exists(filepath_features):
            _logger.warning('Features file not available in raw or clean dirs: {}'.format(filename_features))
            missing_features.append(filename_features)
            continue

        # Create shapefile with custom classes
        crs = fiona.crs.from_epsg(SHAPEFILE_EPSG)
        with fiona.open(filepath_custom, 'w', driver=SHAPEFILE_DRIVER, crs=crs, schema=SHAPEFILE_SCHEMA) as file_custom:
            for original_feature in fiona.open(filepath_src):
                original_code = original_feature['properties']['L4_CODE']
                custom_code = encodings_mp.MAPPINGS_CUSTOM[original_code]
                custom_feature = {'properties': {'custom_class': custom_code}, 'geometry': original_feature['geometry']}
                file_custom.write(custom_feature)

        # Get rasterize parameters
        raster_features = gdal.Open(filepath_features)
        cols = raster_features.RasterXSize
        rows = raster_features.RasterYSize
        llx, xres, _, y0, _, yres = raster_features.GetGeoTransform()
        urx = llx + cols * xres
        y1 = y0 + rows * yres
        lly = min([y0, y1])
        ury = max([y0, y1])

        # Rasterize several attributes separately
        command = 'gdal_rasterize -ot Int16 -co COMPRESS=DEFLATE -co TILED=YES -a_nodata -9999 -init -9999 ' \
                  '-a custom_class -te {llx} {lly} {urx} {ury} -tr {xres} {yres} {filepath_src} {filepath_dest}'
        command = command.format(
            llx=llx, lly=lly, urx=urx, ury=ury, xres=xres, yres=yres, filepath_custom=filepath_custom,
            filepath_dest=filepath_dest
        )
        gdal_command_line.run_gdal_command(command, _logger)

    assert not missing_features, 'Missing features files: {}'.format(', '.join(missing_features))


if __name__ == '__main__':
    create_millennium_project_quad_rasters_custom_classes()