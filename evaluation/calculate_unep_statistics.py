import argparse
import functools
import json
import logging
import os
import re
import sys

import fiona
import matplotlib.pyplot as plt
import pyproj
import shapely.geometry
import shapely.ops


_logger = logging.getLogger(__name__)
_logger.setLevel('DEBUG')
_formatter = logging.Formatter(fmt='%(asctime)s - %(processName)s - %(name)s - %(levelname)s - %(message)s')
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_formatter)
_logger.addHandler(_handler)


_DIR_BASE = '/scratch/nfabina/gcrmn-benthic-classification/'
_FILEPATH_UNEP = os.path.join(_DIR_BASE, 'unep/14_001_WCMC008_CoralReefs2018_v4/01_Data/WCMC008_CoralReef2018_Py_v4.shp')
_DIR_REEFS = os.path.join(_DIR_BASE, 'training_data')
_FILEPATH_UQ = os.path.join(_DIR_REEFS, '{}/clean/reef_outline.shp')
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
    reefs = os.listdir(_DIR_REEFS)

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
    _generate_pdf_summary(statistics)


def _calculate_unep_statistics_for_reef(reef: str) -> dict:
    _logger.debug('Load UNEP and UQ reef features')
    unep = fiona.open(_FILEPATH_UNEP)
    uq = fiona.open(_FILEPATH_UQ.format(reef))

    _logger.debug('Generate UQ reef multipolygon')
    uq_reef = _parse_multipolygon_from_features(uq)

    _logger.debug('Generate UQ reef bounds')
    x, y, w, z = uq_reef.bounds
    uq_bounds = shapely.geometry.Polygon([[x, y], [x, z], [w, z], [w, y]])

    _logger.debug('Generate UNEP reef multipolygon nearby UQ reef bounds')
    unep_reef = _parse_multipolygon_from_features(unep, uq_bounds)

    _logger.debug('Calculate reef area statistics')
    # Note that the obvious calculation for the area of true negatives, i.e., the overlap between UQ and UNEP
    # not-reef area, did not work during tests of certain reefs because there are self-intersection and invalid
    # polygon issues that cannot be resolved using buffer(0). Note that the "obvious calculation" is
    # total_footprint.difference(unep_reef).
    total_footprint = uq_reef.convex_hull
    uq_nonreef = total_footprint.difference(uq_reef)
    stats = dict()
    stats['total_area'] = _calculate_area_in_square_kilometers(total_footprint)
    stats['uq_reef_area'] = _calculate_area_in_square_kilometers(uq_reef)
    stats['uq_nonreef_area'] = _calculate_area_in_square_kilometers(uq_nonreef)
    stats['unep_reef_area'] = _calculate_area_in_square_kilometers(unep_reef.intersection(total_footprint))
    stats['unep_nonreef_area'] = stats['total_area'] - stats['unep_reef_area']
    stats['uq_reef_pct'] = stats['uq_reef_area'] / stats['total_area']
    stats['uq_nonreef_pct'] = stats['uq_nonreef_area'] / stats['total_area']
    stats['unep_reef_pct'] = stats['unep_reef_area'] / stats['total_area']
    stats['unep_nonreef_pct'] = stats['unep_nonreef_area'] / stats['total_area']

    _logger.debug('Calculate T/F P/N statistics')
    stats['area_tp'] = _calculate_area_in_square_kilometers(uq_reef.intersection(unep_reef))  # UQ R x UNEP NR
    stats['area_fn'] = stats['uq_reef_area'] - stats['area_tp']  # UQ R x UNEP NR
    stats['area_fp'] = _calculate_area_in_square_kilometers(uq_nonreef.intersection(unep_reef))  # UQ NR x UNEP R
    stats['area_tn'] = stats['total_area'] - stats['area_tp'] - stats['area_fp'] - stats['area_fn']  # UQ NR x UNEP NR
    stats['pct_tp'] = stats['area_tp'] / stats['total_area']
    stats['pct_fn'] = stats['area_fn'] / stats['total_area']
    stats['pct_fp'] = stats['area_fp'] / stats['total_area']
    stats['pct_tn'] = stats['area_tn'] / stats['total_area']

    _logger.debug('Calculate model recall/precision statistics')
    stats['accuracy'] = stats['pct_tp'] + stats['pct_tn']
    stats['precision'] = stats['pct_tp'] / (stats['pct_tp'] + stats['pct_fn'])
    stats['recall'] = stats['pct_tp'] / (stats['pct_tp'] + stats['pct_fp'])

    return stats


def _parse_multipolygon_from_features(features: fiona.Collection, bounds: shapely.geometry.Polygon = None) \
        -> shapely.geometry.MultiPolygon:
    polygons = list()
    for feature in features:
        geom_type = feature['geometry']['type']
        assert geom_type in ('MultiPolygon', 'Polygon'), 'Type is {}'.format(geom_type)
        shape = shapely.geometry.shape(feature['geometry'])
        if bounds:
            if not bounds.intersects(shape):
                continue
        if geom_type == 'Polygon':
            polygons = [shape]
        elif geom_type == 'MultiPolygon':
            polygons = [polygon for polygon in shape]
        polygons.extend(polygons)
    return shapely.geometry.MultiPolygon(polygons).buffer(0)


def _calculate_area_in_square_kilometers(geometry: shapely.geometry.base.BaseGeometry) -> float:
    """
    Shamelessly borrowed from:
        https://gis.stackexchange.com/questions/127607/area-in-km-from-polygon-of-coordinates
    Trusted because the answer is from sgillies
    """
    transformed = shapely.ops.transform(
        functools.partial(
            pyproj.transform,
            pyproj.Proj(init='EPSG:4326'),
            pyproj.Proj(proj='aea', lat1=geometry.bounds[1], lat2=geometry.bounds[3])
        ),
        geometry
    )
    return transformed.area / 10 ** 6


def _generate_pdf_summary(statistics: dict) -> None:
    lines = ['UNEP Reef Performance Summary', '', '']

    for reef, stats in sorted(statistics.items()):
        reef_name = re.sub('_', ' ', reef).title()

        lines.append('------------------------------------------------------------------------------------------------')
        lines.append('')
        lines.append(reef_name)
        lines.append('')
        lines.append('  Recall:             {:8.1f} %  of reef area is detected correctly'.format(100*stats['recall']))
        lines.append('  Precision:          {:8.1f} %  of reef detections are correct'.format(100*stats['precision']))
        lines.append('')
        lines.append('  Total area:         {:8.1f} km2  in convex hull around ACA reef'.format(stats['total_area']))
        lines.append('')
        lines.append('  ACA reef:           {:8.1f} km2 | {:4.1f} %  of total area'.format(
            stats['uq_reef_area'], 100*stats['uq_reef_pct']))
        lines.append('  UNEP reef:          {:8.1f} km2 | {:4.1f} %  of total area'.format(
            stats['unep_reef_area'], 100*stats['unep_reef_pct']))
        lines.append('')
        lines.append('  Reef detections')
        lines.append('  True positives:     {:8.1f} km2 | {:4.1f} %  of reef area'.format(
            stats['area_tp'], 100*stats['area_tp']/stats['uq_reef_area']))
        lines.append('  False positives:    {:8.1f} km2 | {:4.1f} %  of reef area'.format(
            stats['area_fp'], 100*stats['area_fp']/stats['uq_reef_area']))
        lines.append('')
        lines.append('  ACA non-reef:       {:8.1f} km2 | {:4.1f} %  of total area'.format(
            stats['uq_nonreef_area'], 100*stats['uq_nonreef_pct']))
        lines.append('  UNEP non-reef:      {:8.1f} km2 | {:4.1f} %  of total area'.format(
            stats['unep_nonreef_area'], 100*stats['unep_nonreef_pct']))
        lines.append('')
        lines.append('  Non-reef detections')
        lines.append('  True negatives:     {:8.1f} km2 | {:4.1f} % of non-reef area'.format(
            stats['area_tn'], 100*stats['area_tn']/stats['uq_nonreef_area']))
        lines.append('  False negatives:    {:8.1f} km2 | {:4.1f} % of non-reef area'.format(
            stats['area_fn'], 100*stats['area_fn']/stats['uq_nonreef_area']))
        lines.append('')
        lines.append('')

    fig, ax = plt.subplots(figsize=(8.5, 2 + 3.25 * len(statistics)))
    ax.text(0, 0, '\n'.join(lines), **{'fontsize': 8, 'fontfamily': 'monospace'})
    ax.axis('off')
    plt.savefig(_FILEPATH_FIG_OUT)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='recalculate', action='store_true')
    args = parser.parse_args()
    calculate_unep_statistics(args.recalculate)