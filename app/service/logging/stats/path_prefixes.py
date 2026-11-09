"""Literal, segment-boundary path exclusion shared by statistics endpoints."""


def normalize_prefixes(prefixes):
    result = []
    for prefix in prefixes or ():
        if not prefix.startswith('/') or prefix.strip() != prefix or len(prefix) > 255:
            raise ValueError('exclude_prefix must be an absolute path of at most 255 characters')
        normalized = prefix.rstrip('/') or '/'
        if normalized not in result:
            result.append(normalized)
    if len(result) > 20:
        raise ValueError('at most 20 exclude_prefix values are allowed')
    return result


def is_excluded_path(path, prefixes):
    return any(prefix == '/' or path == prefix or path.startswith(prefix + '/') for prefix in prefixes)


def prefix_filter_sql(prefixes, column='path'):
    clauses, params = [], []
    for prefix in normalize_prefixes(prefixes):
        if prefix == '/':
            clauses.append('0')
        else:
            clauses.append(f'({column} != ? AND substr({column}, 1, ?) != ?)')
            params.extend((prefix, len(prefix) + 1, prefix + '/'))
    return clauses, tuple(params)
