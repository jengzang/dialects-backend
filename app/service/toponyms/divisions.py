"""Load only requested administrative paths, in bounded batches."""
from .resources import QueryTooBroad, check_deadline

BATCH_SIZE = 256
MAX_PATH_NODES = 40_000
MAX_DEPTH = 16


def load_paths(conn, codes):
    divisions = {}
    missing = set(codes)
    seen = set()
    for _ in range(MAX_DEPTH):
        missing -= seen
        if not missing:
            return divisions
        if len(seen) + len(missing) > MAX_PATH_NODES:
            raise QueryTooBroad("Too many administrative paths; narrow the query")
        current = sorted(missing)
        seen.update(current)
        missing = set()
        for start in range(0, len(current), BATCH_SIZE):
            check_deadline()
            batch = current[start:start + BATCH_SIZE]
            rows = conn.execute(
                "SELECT code,name,parent_code,level FROM divisions WHERE code IN ("
                + ",".join("?" for _ in batch) + ")", batch,
            )
            for row in rows:
                item = dict(row)
                divisions[item["code"]] = item
                if item["parent_code"]:
                    missing.add(item["parent_code"])
    raise QueryTooBroad("Administrative hierarchy exceeds maximum depth")


def division_path(code, divisions):
    path = []
    seen = set()
    current = divisions.get(code)
    while current is not None and current["level"] > 0:
        if current["code"] in seen or len(path) >= MAX_DEPTH:
            raise QueryTooBroad("Invalid administrative hierarchy")
        seen.add(current["code"])
        path.append(current)
        current = divisions.get(current["parent_code"])
    return list(reversed(path))


def resolve_parent_codes(conn, names):
    if not names:
        return []
    rows = conn.execute(
        "SELECT code FROM divisions WHERE level=1 AND name=? ORDER BY code", (names[0],)
    ).fetchmany(257)
    codes = [row["code"] for row in rows]
    for name in names[1:]:
        if len(codes) > 256:
            raise QueryTooBroad("Ambiguous administrative path")
        if not codes:
            return []
        check_deadline()
        rows = conn.execute(
            "SELECT code FROM divisions WHERE parent_code IN ("
            + ",".join("?" for _ in codes) + ") AND name=? ORDER BY code",
            [*codes, name],
        ).fetchmany(257)
        codes = [row["code"] for row in rows]
    if len(codes) > 256:
        raise QueryTooBroad("Ambiguous administrative path")
    return codes
