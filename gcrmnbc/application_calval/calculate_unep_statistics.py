import argparse
import json
import os

import fiona
import shapely.geometry
import shapely.ops

from gcrmnbc.application_calval import shared_report, shared_statistics
from gcrmnbc.utils import logs, paths


_logger = logs.get_logger(__file__)

_FILEPATH_UNEP = os.path.join(
    paths.DIR_DATA, 'unep/14_001_WCMC008_CoralReefs2018_v4/01_Data/WCMC008_CoralReef2018_Py_v4.shp')

_FILEPATH_UQ = os.path.join(paths.DIR_DATA_TRAIN, '{}/originals/reef_outline.shp')
_FILEPATH_DATA_OUT = 'unep_statistics.json'
_FILEPATH_FIG_OUT = 'unep_statistics.pdf'


def calculate_unep_statistics(recalculate: bool = False) -> None:
    _logger.info('Calculating UNEP statistics')
    if os.path.exists(_FILEPATH_DATA_OUT) and not recalculate:
        _logger.debug('Loading existing statistics')
        with open(_FILEPATH_DATA_OUT) as file_:
            statistics = json.load(file_)
    else:
        _logger.debug('Calculating statistics from scratch')
        statistics = dict()
    reefs = os.listdir(paths.DIR_DATA_TRAIN)

    for reef in reefs:
        if reef in statistics and not recalculate:
            _logger.debug('Skipping {}:  already calculated'.format(reef))
            continue
        _logger.info('Calculating statistics for {}'.format(reef))
        statistics[reef] = _calculate_unep_statistics_for_reef(reef)
        _logger.debug('Saving statistics'.format(reef))
        with open(_FILEPATH_DATA_OUT, 'w') as file_:
            json.dump(statistics, file_)
    _logger.info('Calculations complete')
    shared_report.generate_pdf_summary_report(statistics, 'UNEP', _FILEPATH_FIG_OUT)


def _calculate_unep_statistics_for_reef(reef: str) -> dict:
    _logger.debug('Load UNEP and UQ reef features')
    unep = fiona.open(_FILEPATH_UNEP)
    uq = fiona.open(_FILEPATH_UQ.format(reef))

    _logger.debug('Generate UQ reef multipolygon')
    uq_reef = shapely.ops.unary_union([shapely.geometry.shape(feature['geometry']) for feature in uq])

    _logger.debug('Generate UQ reef bounds')
    x, y, w, z = uq_reef.bounds
    uq_bounds = shapely.geometry.Polygon([[x, y], [x, z], [w, z], [w, y]])

    _logger.debug('Generate UNEP reef multipolygon nearby UQ reef bounds')
    unep_reef = list()
    for feature in unep:
        shape = shapely.geometry.shape(feature['geometry'])
        if shape.intersects(uq_bounds):
            unep_reef.append(shape)
    unep_reef = shapely.ops.unary_union(unep_reef)

    return shared_statistics.calculate_model_performance_statistics(unep_reef, uq_reef)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='recalculate', action='store_true')
    args = parser.parse_args()
    calculate_unep_statistics(args.recalculate)
