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


@dataclass(frozen=True)
class VocabularyMapPoint:
    location_name: str
    location_label: str
    longitude: float
    latitude: float
    entry_count: int


@dataclass(frozen=True)
class VocabularyMapPointsResult:
    points: list[VocabularyMapPoint]
    total_entries: int
    total_points: int
    omitted_without_coordinates: int


@dataclass(frozen=True)
class VocabularyLocationOption:
    location_name: str
    location_label: str


@dataclass(frozen=True)
class VocabularyLocationOptionsResult:
    locations: list[VocabularyLocationOption]
    total: int


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


def _parse_coordinates(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    parts = value.replace("，", ",").split(",")
    if len(parts) < 2:
        return None
    try:
        longitude = float(parts[0].strip())
        latitude = float(parts[1].strip())
    except ValueError:
        return None
    return longitude, latitude


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


def _build_filter_clause(
    *,
    q: str | None,
    search_fields: str | Iterable[str] | None,
    locations: str | Iterable[str] | None,
) -> tuple[str, list[str]]:
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

    return " AND ".join(clauses) if clauses else "1=1", values


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

    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=search_fields,
        locations=locations,
    )
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


def query_vocabulary_map_points(
    *,
    session: Session,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
) -> VocabularyMapPointsResult:
    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=search_fields,
        locations=locations,
    )
    conn = session.connection().connection
    cursor = conn.cursor()
    select_sql = (
        "SELECT "
        "e.location_name, l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village, COUNT(*) AS entry_count, "
        "MIN(e.id) AS first_entry_id "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {where_clause} "
        "GROUP BY "
        "e.location_name, l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village "
        "ORDER BY first_entry_id ASC"
    )

    cursor.execute(select_sql, values)
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]

    points: list[VocabularyMapPoint] = []
    omitted_without_coordinates = 0
    total_entries = 0
    for row in rows:
        entry_count = int(row["entry_count"] or 0)
        total_entries += entry_count
        parsed_coordinates = _parse_coordinates(row["coordinates"])
        if parsed_coordinates is None:
            omitted_without_coordinates += 1
            continue

        longitude, latitude = parsed_coordinates
        points.append(
            VocabularyMapPoint(
                location_name=row["location_name"] or "",
                location_label=_format_location(row),
                longitude=longitude,
                latitude=latitude,
                entry_count=entry_count,
            )
        )

    return VocabularyMapPointsResult(
        points=points,
        total_entries=total_entries,
        total_points=len(points),
        omitted_without_coordinates=omitted_without_coordinates,
    )


def query_vocabulary_location_options(*, session: Session) -> VocabularyLocationOptionsResult:
    conn = session.connection().connection
    cursor = conn.cursor()
    select_sql = (
        "SELECT "
        "location_name, province, city, county, town, "
        "administrative_village, natural_village, MIN(id) AS first_location_id "
        "FROM vocabulary_locations "
        "GROUP BY "
        "location_name, province, city, county, town, "
        "administrative_village, natural_village "
        "ORDER BY location_name ASC, first_location_id ASC"
    )

    cursor.execute(select_sql)
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]

    seen_location_names = set()
    locations: list[VocabularyLocationOption] = []
    for row in rows:
        location_name = row["location_name"] or ""
        if not location_name or location_name in seen_location_names:
            continue
        seen_location_names.add(location_name)
        locations.append(
            VocabularyLocationOption(
                location_name=location_name,
                location_label=_format_location(row),
            )
        )

    return VocabularyLocationOptionsResult(
        locations=locations,
        total=len(locations),
    )
