"""Partition trees from the caller's accessible default database."""
import hashlib
import json
import logging

from app.common.partition_policy import EXCLUDED_ROOTS, PARTITION_COLUMNS, ROOT_ORDER, valid_partition_path
from app.sql.db_pool import get_db_pool

logger = logging.getLogger(__name__)


def read_partition_paths(db_path, region_mode):
    column = PARTITION_COLUMNS[region_mode]
    with get_db_pool(db_path).get_connection() as connection:
        values = connection.execute(f'SELECT DISTINCT "{column}" FROM dialects').fetchall()
    paths = set()
    malformed = 0
    for (value,) in values:
        if value is None or value == "":
            continue
        if valid_partition_path(value):
            paths.add(value)
        else:
            malformed += 1
    if malformed:
        logger.warning("Skipped %s malformed %s partition paths", malformed, region_mode)
    return paths


def get_partition_tree(db_path, region_mode="yindian", parent=None):
    if region_mode not in PARTITION_COLUMNS:
        raise ValueError("Invalid region_mode")
    if parent is not None and not valid_partition_path(parent):
        raise ValueError("Invalid partition path")
    paths = sorted(path for path in read_partition_paths(db_path, region_mode)
                   if path.split("-")[0] not in EXCLUDED_ROOTS)
    nodes = {}
    roots = []
    max_depth = 0
    for path in paths:
        parts = path.split("-")
        max_depth = max(max_depth, len(parts))
        children = roots
        for depth, label in enumerate(parts, 1):
            full_path = "-".join(parts[:depth])
            if full_path not in nodes:
                node = {"label": label, "path": full_path, "depth": depth, "children": []}
                nodes[full_path] = node
                children.append(node)
            children = nodes[full_path]["children"]
    for node in nodes.values():
        node["children"].sort(key=lambda child: child["label"])
    preference = {name: index for index, name in enumerate(ROOT_ORDER[region_mode])}
    roots.sort(key=lambda node: (preference.get(node["label"], len(preference)), node["label"]))
    if parent is not None and parent not in nodes:
        raise KeyError(parent)
    revision_content = json.dumps([region_mode, paths, sorted(EXCLUDED_ROOTS), ROOT_ORDER[region_mode]],
                                  ensure_ascii=False, separators=(",", ":"))
    return {
        "schema_version": 2,
        "region_mode": region_mode,
        "revision": hashlib.sha256(revision_content.encode("utf-8")).hexdigest(),
        "max_depth": max_depth,
        "parent": parent,
        "nodes": roots if parent is None else nodes[parent]["children"],
    }


def resolve_partition_items(db_path, region_mode, items, scope="default", db=None, user=None):
    from opencc import OpenCC
    from app.service.user.core.models import Information

    sources = {}

    def add_paths(paths, source):
        for path in paths:
            if not valid_partition_path(path):
                continue
            parts = path.split("-")
            for depth in range(1, len(parts) + 1):
                prefix = "-".join(parts[:depth])
                sources.setdefault(prefix, set()).add(source)

    # Visibility is a selector policy, not a restriction on explicitly typed accessible paths.
    add_paths(read_partition_paths(db_path, region_mode), "default")
    if scope == "default_and_user" and region_mode == "yindian" and db is not None and user:
        rows = db.query(Information.音典分區).filter(Information.user_id == user.id).distinct().all()
        add_paths((path for (path,) in rows), "user")
    converter = OpenCC("t2s")
    output = []
    for item in items:
        text, kind = item.text, item.kind
        if kind == "path":
            matches = [text] if text in sources else []
        else:
            matches = [path for path in sources if path.split("-")[-1] == text]
            if not matches:
                simplified = converter.convert(text)
                matches = [path for path in sources if converter.convert(path.split("-")[-1]) == simplified]
        candidates = [{"path": path, "label": path.split("-")[-1], "sources": sorted(sources[path])}
                      for path in sorted(matches)]
        output.append({"text": text, "kind": kind,
                       "status": "resolved" if len(candidates) == 1 else "ambiguous" if candidates else "not_found",
                       "candidates": candidates})
    return {"schema_version": 2, "region_mode": region_mode, "items": output}
