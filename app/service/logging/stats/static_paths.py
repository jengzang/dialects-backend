"""Shared path-based classification for static resources."""

STATIC_EXTENSIONS = frozenset({
    ".js", ".mjs", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".gif", ".webp", ".avif", ".woff", ".woff2", ".ttf", ".otf",
    ".map", ".json", ".xml", ".txt", ".xlsx", ".kmz", ".wasm",
    ".webmanifest",
})


# File and probe patterns observed in the request log; these do not change
# the content-hash normalization extension set used at write time.
EXCLUDED_FILE_EXTENSIONS = STATIC_EXTENSIONS | frozenset({
    ".html", ".htm", ".yaml", ".yml", ".env", ".bak", ".old", ".zip",
    ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".tar", ".sql",
    ".php", ".jsp", ".aspx", ".cgi", ".conf", ".ini", ".log",
})
PROBE_SEGMENTS = (".git", ".svn", ".hg", "wp-admin", "wp-content", "wp-includes", "phpmyadmin", "actuator", "cgi-bin")

# HTML entry points. /auth and /admin also have API descendants, so only
# their entry URLs are classified as pages.
PAGE_PATHS = frozenset({"/", "/auth", "/admin", "/detail"})
PAGE_PREFIXES = ("/intro", "/menu", "/explore", "/villagesml")


def is_static_path(path: str) -> bool:
    path = path.lower()
    return (
        path.endswith(tuple(EXCLUDED_FILE_EXTENSIONS))
        or any(segment.startswith(".env") or segment in PROBE_SEGMENTS for segment in path.split("/"))
        or path.rstrip("/") in PAGE_PATHS
        or path == "/"
        or any(path == prefix or path.startswith(prefix + "/") for prefix in PAGE_PREFIXES)
    )


def non_static_sql(column: str = "path") -> str:
    # The column name is internal; all path rules are fixed constants.
    clauses = [f"lower({column}) NOT LIKE '%{ext}'" for ext in sorted(EXCLUDED_FILE_EXTENSIONS)]
    clauses += [f"rtrim(lower({column}), '/') != '{path}'" for path in sorted(PAGE_PATHS) if path != "/"]
    clauses.append(f"{column} != '/' AND {column} != ''")
    for segment in PROBE_SEGMENTS:
        clauses.append(f"instr('/' || trim(lower({column}), '/') || '/', '/{segment}/') = 0")
    clauses.append(f"instr('/' || lower({column}), '/.env') = 0")
    for prefix in PAGE_PREFIXES:
        clauses.append(f"lower({column}) != '{prefix}' AND lower({column}) NOT LIKE '{prefix}/%'")
    return " AND ".join(clauses)
