from dataclasses import dataclass
from threading import Lock
from sqlalchemy.orm import Session

from app.service.vocabulary.location import normalize_location_payload
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.models import VocabularyEntry, VocabularyLocation
from app.service.vocabulary.parser import parse_uploaded_vocabulary_file
from app.service.vocabulary.permissions import get_effective_permission_level
from app.service.vocabulary.database import raise_vocabulary_database_busy_if_locked

MAX_LOGGED_DELETED_ENTRIES = 500


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
class VocabularyUploadPreviewResult:
    success: bool
    location_name: str
    permission_level: str
    parsed_count: int
    would_delete_existing_count: int
    skipped_count: int
    errors: list[str]
    parser_mode: str


_import_locks_guard = Lock()
_import_locks: dict[tuple[int, str], Lock] = {}


def _get_import_lock(user_id: int, location_name: str) -> Lock:
    key = (user_id, location_name)
    with _import_locks_guard:
        lock = _import_locks.get(key)
        if lock is None:
            lock = Lock()
            _import_locks[key] = lock
        return lock


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
    if location is not None:
        location.coordinates = normalized_location.coordinates
        location.province = normalized_location.province
        location.city = normalized_location.city
        location.county = normalized_location.county
        location.town = normalized_location.town
        location.administrative_village = normalized_location.administrative_village
        location.natural_village = normalized_location.natural_village
        location.yindian_region = normalized_location.yindian_region
        location.atlas_region = normalized_location.atlas_region
    else:
        location = VocabularyLocation(
            user_id=user.id,
            location_name=normalized_location.location_name,
            coordinates=normalized_location.coordinates,
            province=normalized_location.province,
            city=normalized_location.city,
            county=normalized_location.county,
            town=normalized_location.town,
            administrative_village=normalized_location.administrative_village,
            natural_village=normalized_location.natural_village,
            yindian_region=normalized_location.yindian_region,
            atlas_region=normalized_location.atlas_region,
        )
        session.add(location)
    session.flush()
    return location


def _entry_mapping(*, user_id: int, location_name: str, filename: str, row) -> dict[str, object]:
    return {
        "user_id": user_id,
        "location_name": location_name,
        "standard_word": row.standard_word,
        "local_expression": row.local_expression,
        "ipa": row.ipa,
        "notes": row.notes,
        "informations": "",
        "source_filename": filename,
    }


def _entry_snapshot(entry: VocabularyEntry) -> dict[str, object]:
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "location_name": entry.location_name,
        "standard_word": entry.standard_word,
        "local_expression": entry.local_expression,
        "ipa": entry.ipa,
        "notes": entry.notes or "",
        "informations": entry.informations or "",
        "source_filename": entry.source_filename or "",
    }


def _location_snapshot(location: VocabularyLocation | None) -> dict[str, object] | None:
    if location is None:
        return None
    return {
        "id": location.id,
        "user_id": location.user_id,
        "location_name": location.location_name,
        "coordinates": location.coordinates,
        "province": location.province or "",
        "city": location.city or "",
        "county": location.county or "",
        "town": location.town or "",
        "administrative_village": location.administrative_village or "",
        "natural_village": location.natural_village or "",
        "yindian_region": location.yindian_region or "",
        "atlas_region": location.atlas_region or "",
    }


def preview_vocabulary_upload(
    *,
    session: Session,
    user: object,
    filename: str,
    content: bytes,
    location_payload,
    parser_mode: str = "auto",
) -> VocabularyUploadPreviewResult:
    permission_level = get_effective_permission_level(session, user)
    normalized_location = normalize_location_payload(location_payload)
    parse_result = parse_uploaded_vocabulary_file(
        filename=filename,
        content=content,
        parser_mode=parser_mode,
    )
    errors = list(parse_result.errors)
    parsed_count = len(parse_result.rows) if not errors else 0
    would_delete_existing_count = 0
    if parsed_count > 0:
        would_delete_existing_count = session.query(VocabularyEntry).filter(
            VocabularyEntry.user_id == user.id,
            VocabularyEntry.location_name == normalized_location.location_name,
        ).count()

    return VocabularyUploadPreviewResult(
        success=not errors and parsed_count > 0,
        location_name=normalized_location.location_name,
        permission_level=permission_level,
        parsed_count=parsed_count,
        would_delete_existing_count=would_delete_existing_count,
        skipped_count=parse_result.skipped_count,
        errors=errors or ([] if parsed_count > 0 else ["No valid vocabulary rows found"]),
        parser_mode=parse_result.parser_mode,
    )


def import_vocabulary_upload(
    *,
    session: Session,
    user: object,
    filename: str,
    content: bytes,
    location_payload,
    parser_mode: str = "auto",
    overwrite: bool = False,
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

    if not overwrite:
        existing_count = session.query(VocabularyEntry).filter(
            VocabularyEntry.location_name == normalized_location.location_name,
        ).count()
        if existing_count > 0:
            raise ValueError(
                "该地点已有数据，不能重复上传。如需更新，请联系管理员。"
            )

    import_lock = _get_import_lock(user.id, normalized_location.location_name)
    with import_lock:
        try:
            before_location = session.query(VocabularyLocation).filter(
                VocabularyLocation.user_id == user.id,
                VocabularyLocation.location_name == normalized_location.location_name,
            ).first()
            before_location_snapshot = _location_snapshot(before_location)
            location = _upsert_location(
                session=session,
                user=user,
                normalized_location=normalized_location,
            )
            deleted_entries = [
                _entry_snapshot(entry)
                for entry in session.query(VocabularyEntry).filter(
                    VocabularyEntry.user_id == user.id,
                    VocabularyEntry.location_name == normalized_location.location_name,
                ).all()
            ]
            can_log_deleted_entries = len(deleted_entries) <= MAX_LOGGED_DELETED_ENTRIES
            deleted_existing_count = session.query(VocabularyEntry).filter(
                VocabularyEntry.user_id == user.id,
                VocabularyEntry.location_name == normalized_location.location_name,
            ).delete(synchronize_session=False)

            session.bulk_insert_mappings(
                VocabularyEntry,
                [
                    _entry_mapping(
                        user_id=user.id,
                        location_name=normalized_location.location_name,
                        filename=filename,
                        row=row,
                    )
                    for row in parse_result.rows
                ],
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
                    "deleted_entries": deleted_entries if can_log_deleted_entries else [],
                    "deleted_entries_omitted": not can_log_deleted_entries,
                    "deleted_entries_log_limit": MAX_LOGGED_DELETED_ENTRIES,
                    "before_location": before_location_snapshot,
                    "after_location": _location_snapshot(location),
                    "rollback_supported": False,
                    "rollback_note": "import replaces a location set; logs preserve deleted entries only when under limit, but inserted entry ids are not tracked",
                },
            )
            session.commit()
            session.refresh(location)
        except Exception as exc:
            session.rollback()
            raise_vocabulary_database_busy_if_locked(exc)
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
