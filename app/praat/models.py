"""
SQLAlchemy models for Praat analysis service.
"""
from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Upload(Base):
    """Audio upload resource."""
    __tablename__ = "uploads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100))
    size_bytes = Column(Integer)
    duration_s = Column(Float)
    sample_rate = Column(Integer)
    channels = Column(Integer)
    normalized_path = Column(String(500))
    original_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    warnings = Column(JSON, default=list)

    # Relationship
    jobs = relationship("Job", back_populates="upload", cascade="all, delete-orphan")


class Job(Base):
    """Analysis job resource."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = Column(String(36), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    mode = Column(String(20), nullable=False)  # single | continuous
    modules = Column(JSON, nullable=False)  # List of module names
    options = Column(JSON, default=dict)  # Module options
    output_options = Column(JSON, default=dict)  # Output configuration

    # Status tracking
    status = Column(String(20), default="queued")  # queued | running | done | error | canceled
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    stage = Column(String(50))  # Current processing stage
    error = Column(JSON)  # Error details if status=error

    # Result
    result_path = Column(String(500))  # Path to result JSON file

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    upload = relationship("Upload", back_populates="jobs")
