from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class VocabularyItem:
    standard_word: str
    local_expression: str
    ipa: str
    notes: str
    informations: str
    location_name: str
    location_label: str


@dataclass(frozen=True)
class VocabularyItemsResult:
    items: list[VocabularyItem]
    total: int
    page: int
    page_size: int


SEARCH_FIELD_COLUMNS = {
    "definition": ("e.standard_word",),
    "headword": ("e.local_expression",),
    "pronunciation": ("e.ipa",),
    "detail": ("e.notes", "e.informations"),
    "location": (
        "e.location_name",
        "l.location_name",
        "l.province",
        "l.city",
        "l.county",
        "l.town",
        "l.administrative_village",
        "l.natural_village",
        "l.yindian_region",
        "l.atlas_region",
    ),
}
DEFAULT_SEARCH_FIELDS = ("definition", "headword", "pronunciation", "detail")


def _normalize_multi_value(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    raw_values = [value] if isinstance(value, str) else list(value)
    normalized = []
    for raw_value in raw_values:
        normalized.extend(part.strip() for part in str(raw_value).split(","))
    return [part for part in normalized if part]


def _normalize_search_fields(search_fields: str | Iterable[str] | None) -> list[str]:
    fields = _normalize_multi_value(search_fields)
    if not fields or "all" in fields:
        return list(DEFAULT_SEARCH_FIELDS)

    invalid = sorted(set(fields).difference(SEARCH_FIELD_COLUMNS))
    if invalid:
        raise ValueError(f"Unsupported search_fields: {', '.join(invalid)}")
    return fields


def _append_like_group(
    *,
    clauses: list[str],
    values: list[str],
    columns: Iterable[str],
    terms: Iterable[str],
) -> None:
    parts = []
    for term in terms:
        pattern = f"%{term}%"
        for column in columns:
            parts.append(f"COALESCE({column}, '') LIKE ?")
            values.append(pattern)
    if parts:
        clauses.append(f"({' OR '.join(parts)})")


def _format_location(row: dict) -> str:
    parts = [
        row["province"],
        row["city"],
        row["county"],
        row["town"],
        row["administrative_village"],
        row["natural_village"],
    ]
    clean_parts = [part for part in parts if part]
    if clean_parts:
        return " / ".join(clean_parts)
    return row["location_name"] or ""


def _row_to_vocabulary_item(row: dict) -> VocabularyItem:
    return VocabularyItem(
        standard_word=row["standard_word"] or "",
        local_expression=row["local_expression"] or "",
        ipa=row["ipa"] or "",
        notes=row["notes"] or "",
        informations=row["informations"] or "",
        location_name=row["location_name"] or "",
        location_label=_format_location(row),
    )


def query_vocabulary_items(
    *,
    session: Session,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> VocabularyItemsResult:
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    if page_size > 200:
        raise ValueError("page_size cannot exceed 200")

    fields = _normalize_search_fields(search_fields)
    location_terms = _normalize_multi_value(locations)
    clauses: list[str] = []
    values: list[str] = []

    if q and q.strip():
        search_columns = [
            column
            for field in fields
            for column in SEARCH_FIELD_COLUMNS[field]
        ]
        _append_like_group(
            clauses=clauses,
            values=values,
            columns=search_columns,
            terms=[q.strip()],
        )

    if location_terms:
        _append_like_group(
            clauses=clauses,
            values=values,
            columns=SEARCH_FIELD_COLUMNS["location"],
            terms=location_terms,
        )

    where_clause = " AND ".join(clauses) if clauses else "1=1"
    offset = (page - 1) * page_size
    conn = session.connection().connection
    cursor = conn.cursor()
    select_sql = (
        "SELECT "
        "e.standard_word, e.local_expression, e.ipa, e.notes, e.informations, "
        "e.location_name, l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {where_clause} "
        "ORDER BY e.id ASC LIMIT ? OFFSET ?"
    )
    count_sql = (
        "SELECT COUNT(*) "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {where_clause}"
    )

    cursor.execute(select_sql, values + [page_size, offset])
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]
    cursor.execute(count_sql, values)
    total = cursor.fetchone()[0]

    return VocabularyItemsResult(
        items=[_row_to_vocabulary_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
