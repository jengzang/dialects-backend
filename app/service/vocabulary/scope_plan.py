"""Request-local, bounded location planning using existing SQLite indexes.

Limits select a fallback plan, never restrict the result set. Callers must hold
one read snapshot from planning through their query. No cache, worker or retry.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LocationScope:
    names: tuple[str, ...]
    identities: tuple[tuple[int, str], ...]

    def cte(self):
        names = ','.join('(?)' for _ in self.names)
        identities = ','.join('(?,?)' for _ in self.identities)
        sql = (
            'WITH matched_names(name) AS ('
            + ('VALUES ' + names if names else 'SELECT NULL WHERE 0')
            + '), matched_meta(user_id, location_name) AS ('
            + ('VALUES ' + identities if identities else 'SELECT NULL, NULL WHERE 0') + ') '
        )
        values = list(self.names) + [value for identity in self.identities for value in identity]
        return sql, values

    def branches(self, content='1=1'):
        # Extra identities have already excluded every name handled by branch 1.
        return (
            'matched_names n CROSS JOIN vocabulary_entries e '
            'INDEXED BY ix_vocabulary_entries_location_name '
            f'WHERE e.location_name = n.name AND ({content})',
            'matched_meta p CROSS JOIN vocabulary_entries e '
            'INDEXED BY idx_vocabulary_entries_user_location '
            'WHERE e.user_id = p.user_id AND e.location_name = p.location_name '
            f'AND ({content})',
        )

    def rows(self, columns, content, values):
        cte, bindings = self.cte()
        first, second = self.branches(content)
        return cte, f'SELECT {columns} FROM {first} UNION ALL SELECT {columns} FROM {second}', bindings + list(values) * 2


def plan_location_scope(cursor, *, locations, metadata_columns):
    """Return a small exact scope, or None to retain the original full query.

    Collect <=257 names/extra identities; overflow falls back. Candidate-count
    probe reads <=32769 matching index rows. Location metadata filtering still
    scans its table, with a bounded returned buffer (not constant total I/O).
    """
    patterns = ['%' + term + '%' for term in locations]
    name_filter = ' OR '.join("COALESCE(name, '') LIKE ?" for _ in patterns)
    names = cursor.execute(
        'WITH RECURSIVE location_names(name) AS ('
        'SELECT MIN(location_name) FROM vocabulary_entries '
        'UNION ALL SELECT (SELECT MIN(location_name) FROM vocabulary_entries '
        'WHERE location_name > n.name) FROM location_names n '
        'WHERE n.name IS NOT NULL LIMIT 257) '
        f'SELECT /* vocabulary_scope_plan */ name, ({name_filter}) '
        'FROM location_names WHERE name IS NOT NULL', patterns,
    ).fetchall()
    if len(names) > 256:
        return None
    matched_names = tuple(name for name, matched in names if matched)
    metadata_filter = ' OR '.join(
        f"COALESCE({column}, '') LIKE ?" for _ in patterns for column in metadata_columns
    )
    excluded = (' AND p.location_name NOT IN (' + ','.join('?' for _ in matched_names) + ')') if matched_names else ''
    identities = cursor.execute(
        'SELECT /* vocabulary_scope_plan */ p.user_id, p.location_name '
        'FROM vocabulary_locations p WHERE (' + metadata_filter + ')' + excluded + ' LIMIT 257',
        [pattern for pattern in patterns for _ in metadata_columns] + list(matched_names),
    ).fetchall()
    if len(identities) > 256:
        return None
    scope = LocationScope(matched_names, tuple(identities))
    if not matched_names and not identities:
        return scope
    total = cursor.execute('SELECT /* vocabulary_scope_plan */ COUNT(*) FROM vocabulary_entries').fetchone()[0]
    budget = min(32768, max(1024, total // 10))
    cte, rows, values = scope.rows('1', '1=1', [])
    matched = cursor.execute(
        cte + 'SELECT /* vocabulary_scope_plan */ COUNT(*) FROM (' + rows + ' LIMIT ?)',
        values + [budget + 1],
    ).fetchone()[0]
    return scope if matched <= budget else None
