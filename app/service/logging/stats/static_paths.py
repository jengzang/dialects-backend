"""Shared path-based classification for static resources."""

STATIC_EXTENSIONS = frozenset({
    ".js", ".mjs", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".gif", ".webp", ".avif", ".woff", ".woff2", ".ttf", ".otf",
    ".map", ".json", ".xml", ".txt", ".xlsx", ".kmz", ".wasm",
    ".webmanifest",
})


def is_static_path(path: str) -> bool:
    return path.lower().endswith(tuple(STATIC_EXTENSIONS))


def non_static_sql(column: str = "path") -> str:
    # The column name is internal, and extensions are fixed constants.
    return " AND ".join(
        f"lower({column}) NOT LIKE '%{ext}'" for ext in sorted(STATIC_EXTENSIONS)
    )
