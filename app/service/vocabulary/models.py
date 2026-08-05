from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base


Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class VocabularyEntry(Base):
    __tablename__ = "vocabulary_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    location_name = Column(String(200), nullable=False, index=True)
    standard_word = Column(String(500), nullable=False, index=True)
    local_expression = Column(Text, nullable=False)
    ipa = Column(Text, nullable=False)
    notes = Column(Text, default="")
    informations = Column(Text, default="")
    source_filename = Column(String(255), default="")

    __table_args__ = (
        Index("idx_vocabulary_entries_user_location", "user_id", "location_name"),
    )


class VocabularyLocation(Base):
    __tablename__ = "vocabulary_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    location_name = Column(String(200), nullable=False, index=True)
    coordinates = Column(String(200), nullable=False)
    province = Column(String(100), default="")
    city = Column(String(100), default="")
    county = Column(String(100), default="")
    town = Column(String(100), default="")
    administrative_village = Column(String(200), default="")
    natural_village = Column(String(200), default="")
    yindian_region = Column(String(200), default="")
    atlas_region = Column(String(200), default="")
    __table_args__ = (
        UniqueConstraint("user_id", "location_name", name="uq_vocabulary_location_user_name"),
    )


class VocabularyPermission(Base):
    __tablename__ = "vocabulary_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    permission_level = Column(String(20), nullable=False)


class VocabularyLog(Base):
    __tablename__ = "vocabulary_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    permission_level = Column(String(20), nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    table_name = Column(String(100), nullable=False, index=True)
    target_scope = Column(Text, default="")
    affected_rows = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="success", index=True)
    payload_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)
