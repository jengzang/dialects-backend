from dataclasses import dataclass
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
