"""Standalone search service for character-note rows."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.service.geo.match_input_tip import match_locations_batch_all
from app.sql.db_pool import get_db_pool


SEARCH_FIELDS = frozenset({"pronunciation", "detail"})
_VALID_REGION_MODES = frozenset({"map", "yindian"})
_SCOPE_TABLE = "_notes_scope_abbreviations"
_VALID_NOTE_CLAUSE = "TRIM(COALESCE(notes.註釋, '')) NOT IN ('', '_', '-')"


def _normalize_values(values: str | Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    raw_values = [values] if isinstance(values, str) else values
    return [str(value).strip() for value in raw_values if str(value).strip()]


def parse_notes_search_fields(values: list[str] | None) -> set[str]:
    """Return valid fields, treating omitted, empty, and ``all`` as both fields."""
    fields = _normalize_values(values)
    if not fields or "all" in fields:
        return set(SEARCH_FIELDS)

    invalid = sorted(set(fields).difference(SEARCH_FIELDS))
    if invalid:
        raise ValueError(f"Unsupported search_fields: {', '.join(invalid)}")
    return set(fields)


def resolve_notes_scope(
    locations: str | Iterable[str] | None,
    regions: str | Iterable[str] | None,
    region_mode: str,
    query_db_path: str | Path,
) -> tuple[bool, list[str]]:
    """Resolve raw location and partition input without using the search-chars service."""
    if region_mode not in _VALID_REGION_MODES:
        raise ValueError("region_mode must be map or yindian")

    explicit_locations = _normalize_values(locations)
    selected_regions = _normalize_values(regions)
    has_scope = bool(explicit_locations or selected_regions)
    if not has_scope:
        return False, []

    matched_locations = match_locations_batch_all(
        explicit_locations,
        filter_valid_abbrs_only=True,
        exact_only=True,
        query_db=str(query_db_path),
        db=None,
        user=None,
    )
    abbreviations = query_dialect_abbreviations(
        region_input=selected_regions,
        location_sequence=matched_locations,
        db_path=str(query_db_path),
        region_mode=region_mode,
    )
    return True, list(dict.fromkeys(abbreviations))


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def _fts_query_for_notes(query: str) -> str | None:
    """Build a literal FTS query over the character-tokenized notes index.

    The index stores every character as its own token (``上面`` -> ``上 面``,
    ``tsiu24`` -> ``t s i u 2 4``).  A run of consecutive Han/alnum characters
    must therefore be quoted as a *phrase*; joining single characters with
    ``AND`` would also match notes that merely contain those characters apart,
    e.g. ``上面`` matching ``〚請而開上〛面大也``.
    """
    phrases: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if run:
            phrases.append('"' + " ".join(run) + '"')
            run.clear()

    for character in query:
        if _is_han(character) or character.isalnum():
            run.append(character)
        else:
            flush()
    flush()

    if not phrases:
        return None

    return " AND ".join(phrases)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _prepare_scope_table(conn: Any, abbreviations: list[str]) -> None:
    """Store the resolved scope without imposing SQLite's bound-parameter limit."""
    conn.execute(
        f"CREATE TEMP TABLE IF NOT EXISTS {_SCOPE_TABLE} (abbr TEXT PRIMARY KEY)"
    )
    conn.execute(f"DELETE FROM {_SCOPE_TABLE}")
    conn.executemany(
        f"INSERT INTO {_SCOPE_TABLE}(abbr) VALUES (?)",
        [(abbreviation,) for abbreviation in abbreviations],
    )


def _candidate_rowids_sql(
    *,
    query: str,
    search_fields: set[str],
) -> tuple[str, list[str]]:
    """Rowids matching ``query`` in the requested fields, before validity/scope.

    Both the validity rule and the location scope are per-row properties, so the
    caller applies them once to the unioned candidates instead of inside every
    branch.  Keeping them out of the branches matters for performance: a
    pronunciation ``LIKE '%…%'`` scan can only use the covering index on 音節
    when no other column is referenced, otherwise SQLite falls back to a full
    table scan.  The detail branch also reads ``notes_fts`` directly—its rowids
    are ``notes`` rowids—avoiding a needless join back to ``notes``.
    """
    branches: list[str] = []
    params: list[str] = []

    if "detail" in search_fields:
        fts_query = _fts_query_for_notes(query)
        if fts_query is not None:
            branches.append("SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?")
            params.append(fts_query)

    if "pronunciation" in search_fields:
        branches.append(
            "SELECT notes.rowid AS rowid FROM notes "
            "WHERE COALESCE(notes.音節, '') LIKE ? ESCAPE '\\'"
        )
        params.append(f"%{_escape_like(query)}%")

    if not branches:
        return "SELECT notes.rowid AS rowid FROM notes WHERE 0", []

    return " UNION ".join(branches), params


def query_notes(
    *,
    q: str,
    search_fields: list[str] | None,
    locations: str | Iterable[str] | None,
    regions: str | Iterable[str] | None,
    region_mode: str,
    page: int,
    page_size: int,
    notes_db_path: str | Path,
    query_db_path: str | Path,
) -> dict[str, Any]:
    """Return one page of note rows and the total count for the same matched set."""
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    if page_size > 200:
        raise ValueError("page_size cannot exceed 200")

    fields = parse_notes_search_fields(search_fields)
    scope_supplied, abbreviations = resolve_notes_scope(
        locations=locations,
        regions=regions,
        region_mode=region_mode,
        query_db_path=query_db_path,
    )
    if scope_supplied and not abbreviations:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    normalized_query = q.strip()
    scope_clause = (
        f" AND notes.簡稱 IN (SELECT abbr FROM {_SCOPE_TABLE})" if abbreviations else ""
    )
    if normalized_query:
        candidate_sql, params = _candidate_rowids_sql(
            query=normalized_query,
            search_fields=fields,
        )
        matched_sql = (
            f"SELECT candidates.rowid AS rowid FROM ({candidate_sql}) AS candidates "
            "JOIN notes ON notes.rowid = candidates.rowid "
            f"WHERE {_VALID_NOTE_CLAUSE}{scope_clause}"
        )
    page_columns = (
        "notes.rowid AS id, notes.簡稱 AS location_name, notes.漢字 AS character, "
        "notes.音節 AS ipa, notes.註釋 AS notes"
    )

    pool = get_db_pool(str(notes_db_path))
    with pool.get_connection() as conn:
        if abbreviations:
            _prepare_scope_table(conn, abbreviations)

        if normalized_query:
            # Materialize the matched rowids once.  Embedding the candidate UNION
            # in both the count and the page statement would re-evaluate the FTS
            # match and the pronunciation LIKE scan twice per request.
            conn.execute("DROP TABLE IF EXISTS temp.matched_rowids")
            conn.execute(f"CREATE TEMP TABLE matched_rowids AS {matched_sql}", params)
            total = conn.execute("SELECT COUNT(*) FROM matched_rowids").fetchone()[0]
            rows = conn.execute(
                f"SELECT {page_columns} FROM notes "
                "JOIN matched_rowids ON matched_rowids.rowid = notes.rowid "
                "ORDER BY notes.rowid ASC LIMIT ? OFFSET ?",
                [page_size, (page - 1) * page_size],
            ).fetchall()
        else:
            scope_where = (
                f" WHERE notes.簡稱 IN (SELECT abbr FROM {_SCOPE_TABLE})"
                if abbreviations else ""
            )
            total = conn.execute(
                f"SELECT COUNT(*) FROM notes{scope_where}"
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT {page_columns} FROM notes{scope_where} "
                "ORDER BY notes.rowid DESC LIMIT ? OFFSET ?",
                [page_size, (page - 1) * page_size],
            ).fetchall()

    return {
        "items": [
            {
                "id": int(row["id"]),
                "location_name": row["location_name"] or "",
                "character": row["character"] or "",
                "ipa": row["ipa"] or "",
                "notes": row["notes"] or "",
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
