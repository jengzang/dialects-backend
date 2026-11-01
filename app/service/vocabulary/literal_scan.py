"""Bounded, request-local selection of a literal prefilter for SQLite LIKE.

The original LIKE remains authoritative (including NUL/blob handling). Literal
instr is a necessary condition only when SQLite's ASCII folding and wildcard
syntax cannot add matches. No index, cache, background task or retry is added.
"""


def supports_literal_prefilter(terms):
    # Single characters did not repay the planning overhead on current data.
    return bool(terms) and all(
        len(term) >= 2 and not any(c in '%_\x00' or 'a' <= c <= 'z' or 'A' <= c <= 'Z' for c in term)
        for term in terms
    )


def guarded_literal_like(columns, terms):
    parts, values = [], []
    for term in terms:
        for column in columns:
            parts.append(f"(instr({column}, ?) > 0 AND COALESCE({column}, '') LIKE ?)")
            values.extend((term, '%' + term + '%'))
    return '(' + ' OR '.join(parts) + ')', values


def sparse_literal_sample(cursor, *, columns, where, values):
    """Read <=128 content rows spread across the ID range, not an OFFSET scan.

    Heuristic only: unusual clustering/gaps may misestimate density, affecting
    performance but never results. Small ID spans avoid the planning overhead.
    None marks a small/empty ID span; False marks a non-sparse sample.
    Separate MIN/MAX scalar seeks prevent SQLite scanning for a combined pair.
    """
    low, high = cursor.execute(
        'SELECT /* vocabulary_literal_probe */ '
        '(SELECT MIN(id) FROM vocabulary_entries), '
        '(SELECT MAX(id) FROM vocabulary_entries)'
    ).fetchone()
    if low is None or high - low < 1024:
        return None
    matched = sampled = 0
    names = ', '.join(dict.fromkeys(column.removeprefix('e.') for column in columns))
    for block in range(8):
        target = low + (high - low) * block // 8
        rows = cursor.execute(
            f'SELECT /* vocabulary_literal_probe */ ({where}) FROM '
            f'(SELECT {names} FROM vocabulary_entries WHERE id >= ? '
            'ORDER BY id LIMIT 16) e', list(values) + [target],
        ).fetchall()
        sampled += len(rows)
        matched += sum(bool(row[0]) for row in rows)
        # More than eight matches cannot pass even a full 128-row sample.
        if matched > 8:
            return False
    return bool(sampled) and matched * 16 <= sampled
