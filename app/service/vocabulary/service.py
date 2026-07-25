from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.service.vocabulary.location import normalize_location_payload
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.models import VocabularyEntry, VocabularyLocation
from app.service.vocabulary.parser import parse_uploaded_vocabulary_file
from app.service.vocabulary.permissions import get_effective_permission_level


@dataclass(frozen=True)
class VocabularyImportResult:
    success: bool
    location_id: int
    location_name: str
    permission_level: str
    imported_count: int
    deleted_existing_count: int
    skipped_count: int
    errors: list[str]
    parser_mode: str


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


def _upsert_location(
    *,
    session: Session,
    user: object,
    normalized_location,
) -> VocabularyLocation:
    location = session.query(VocabularyLocation).filter(
        VocabularyLocation.user_id == user.id,
        VocabularyLocation.location_name == normalized_location.location_name,
    ).first()
    if location is None:
        location = VocabularyLocation(
            user_id=user.id,
            location_name=normalized_location.location_name,
        )
        session.add(location)

    location.coordinates = normalized_location.coordinates
    location.province = normalized_location.province
    location.city = normalized_location.city
    location.county = normalized_location.county
    location.town = normalized_location.town
    location.administrative_village = normalized_location.administrative_village
    location.natural_village = normalized_location.natural_village
    location.yindian_region = normalized_location.yindian_region
    location.atlas_region = normalized_location.atlas_region
    location.raw_location_json = normalized_location.raw_location_json
    return location


def import_vocabulary_upload(
    *,
    session: Session,
    user: object,
    filename: str,
    content: bytes,
    location_payload,
    parser_mode: str = "auto",
) -> VocabularyImportResult:
    permission_level = get_effective_permission_level(session, user)
    normalized_location = normalize_location_payload(location_payload)
    parse_result = parse_uploaded_vocabulary_file(
        filename=filename,
        content=content,
        parser_mode=parser_mode,
    )
    if parse_result.errors:
        raise ValueError("; ".join(parse_result.errors))
    if not parse_result.rows:
        raise ValueError("No valid vocabulary rows found")

    try:
        location = _upsert_location(
            session=session,
            user=user,
            normalized_location=normalized_location,
        )
        deleted_existing_count = session.query(VocabularyEntry).filter(
            VocabularyEntry.user_id == user.id,
            VocabularyEntry.location_name == normalized_location.location_name,
        ).delete(synchronize_session=False)

        for row in parse_result.rows:
            session.add(
                VocabularyEntry(
                    user_id=user.id,
                    location_name=normalized_location.location_name,
                    standard_word=row.standard_word,
                    local_expression=row.local_expression,
                    ipa=row.ipa,
                    notes=row.notes,
                    informations="",
                    source_filename=filename,
                )
            )

        record_vocabulary_log(
            session=session,
            user_id=user.id,
            permission_level=permission_level,
            source="upload",
            action="import",
            table_name="vocabulary_entries",
            target_scope=f"user_id = {user.id}; location_name = {normalized_location.location_name}",
            affected_rows=len(parse_result.rows),
            payload={
                "filename": filename,
                "location_name": normalized_location.location_name,
                "deleted_existing_count": deleted_existing_count,
                "imported_count": len(parse_result.rows),
                "parser_mode": parse_result.parser_mode,
            },
        )
        session.commit()
        session.refresh(location)
    except Exception:
        session.rollback()
        raise

    return VocabularyImportResult(
        success=True,
        location_id=location.id,
        location_name=normalized_location.location_name,
        permission_level=permission_level,
        imported_count=len(parse_result.rows),
        deleted_existing_count=deleted_existing_count,
        skipped_count=parse_result.skipped_count,
        errors=[],
        parser_mode=parse_result.parser_mode,
    )
