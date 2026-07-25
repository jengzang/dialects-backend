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
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    location_name = Column(String(200), nullable=False, index=True)
    standard_word = Column(String(500), nullable=False, index=True)
    local_expression = Column(Text, nullable=False)
    ipa = Column(Text, nullable=False)
    notes = Column(Text, default="")
    informations = Column(Text, default="")
    source_filename = Column(String(255), default="")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_vocabulary_entries_user_location", "user_id", "location_name"),
    )


class VocabularyLocation(Base):
    __tablename__ = "vocabulary_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=False)
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
    raw_location_json = Column(Text, default="")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "location_name", name="uq_vocabulary_location_user_name"),
        Index("idx_vocabulary_locations_user_location", "user_id", "location_name"),
    )


class VocabularyPermission(Base):
    __tablename__ = "vocabulary_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=False)
    permission_level = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
