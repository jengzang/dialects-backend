"""Vocabulary-owned partition paths; no public-database location expansion."""
import hashlib
import json
from collections.abc import Iterable
from itertools import islice

from sqlalchemy.orm import Session

from app.common.partition_policy import ROOT_ORDER, valid_partition_path

PARTITION_COLUMNS = {'yindian': 'yindian_region', 'map': 'atlas_region'}
MAX_REGIONS = 50
MAX_PATH_LENGTH = 200


def normalize_regions(regions: str | Iterable[str] | None, region_mode: str = 'yindian') -> list[str]:
    if region_mode not in PARTITION_COLUMNS:
        raise ValueError('region_mode must be map or yindian')
    if regions is None:
        return []
    paths = [regions] if isinstance(regions, str) else list(islice(regions, MAX_REGIONS + 1))
    if len(paths) > MAX_REGIONS:
        raise ValueError(f'regions cannot exceed {MAX_REGIONS} paths')
    for path in paths:
        if not isinstance(path, str) or len(path) > MAX_PATH_LENGTH or '\x00' in path or not valid_partition_path(path):
            raise ValueError('Invalid partition path (maximum 200 characters)')
    selected = set(paths)
    result = []
    for path in sorted(selected):
        parts = path.split('-')
        if not any('-'.join(parts[:depth]) in selected for depth in range(1, len(parts))):
            result.append(path)
    return result


def partition_filter(regions, region_mode='yindian', *, alias='l'):
    paths = normalize_regions(regions, region_mode)
    if not paths:
        return '', []
    column = f'{alias}.{PARTITION_COLUMNS[region_mode]}'
    conditions, values = [], []
    for path in paths:
        conditions.append(f'({column} = ? OR substr({column}, 1, ?) = ?)')
        values.extend([path, len(path) + 1, path + '-'])
    return '(' + ' OR '.join(conditions) + ')', values


def query_vocabulary_partition_options(*, session: Session, region_mode='yindian', parent=None):
    normalize_regions([parent] if parent is not None else None, region_mode)
    column = PARTITION_COLUMNS[region_mode]
    cursor = session.connection().connection.cursor()
    cursor.execute(f'SELECT DISTINCT {column} FROM vocabulary_locations')
    paths = sorted(value for (value,) in cursor.fetchall()
                   if isinstance(value, str) and len(value) <= MAX_PATH_LENGTH
                   and '\x00' not in value and valid_partition_path(value))
    roots, nodes = [], {}
    max_depth = 0
    for path in paths:
        parts = path.split('-')
        max_depth = max(max_depth, len(parts))
        children = roots
        for depth, label in enumerate(parts, 1):
            prefix = '-'.join(parts[:depth])
            if prefix not in nodes:
                node = {'label': label, 'path': prefix, 'depth': depth, 'children': []}
                nodes[prefix] = node
                children.append(node)
            children = nodes[prefix]['children']
    for node in nodes.values():
        node['children'].sort(key=lambda child: child['label'])
    preference = {name: index for index, name in enumerate(ROOT_ORDER[region_mode])}
    roots.sort(key=lambda node: (preference.get(node['label'], len(preference)), node['label']))
    if parent is not None and parent not in nodes:
        raise KeyError(parent)
    revision = json.dumps([region_mode, paths, ROOT_ORDER[region_mode]], ensure_ascii=False, separators=(',', ':'))
    return {'schema_version': 2, 'region_mode': region_mode,
            'revision': hashlib.sha256(revision.encode()).hexdigest(), 'max_depth': max_depth,
            'parent': parent, 'nodes': roots if parent is None else nodes[parent]['children']}
