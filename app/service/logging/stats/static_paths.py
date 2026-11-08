"""Shared path-based classification for static resources."""

STATIC_EXTENSIONS = frozenset({
    ".js", ".mjs", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".gif", ".webp", ".avif", ".woff", ".woff2", ".ttf", ".otf",
    ".map", ".json", ".xml", ".txt", ".xlsx", ".kmz", ".wasm",
    ".webmanifest",
})


# HTML entry points. /auth and /admin also have API descendants, so only
# their entry URLs are classified as pages.
PAGE_PATHS = frozenset({"/", "/auth", "/admin", "/detail"})
PAGE_PREFIXES = ("/intro", "/menu", "/explore", "/villagesml")


def is_static_path(path: str) -> bool:
    path = path.lower()
    return (
        path.endswith(tuple(STATIC_EXTENSIONS))
        or path.rstrip("/") in PAGE_PATHS
        or path == "/"
        or any(path == prefix or path.startswith(prefix + "/") for prefix in PAGE_PREFIXES)
    )


def non_static_sql(column: str = "path") -> str:
    # The column name is internal; all path rules are fixed constants.
    clauses = [f"lower({column}) NOT LIKE '%{ext}'" for ext in sorted(STATIC_EXTENSIONS)]
    clauses += [f"rtrim(lower({column}), '/') != '{path}'" for path in sorted(PAGE_PATHS) if path != "/"]
    clauses.append(f"{column} != '/' AND {column} != ''")
    for prefix in PAGE_PREFIXES:
        clauses.append(f"lower({column}) != '{prefix}' AND lower({column}) NOT LIKE '{prefix}/%'")
    return " AND ".join(clauses)
