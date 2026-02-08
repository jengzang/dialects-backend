"""
Result JSON schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ToneFeatures(BaseModel):
    """Tone features for Chinese/dialect analysis."""
    f0_start: Optional[float] = Field(None, description="Starting F0 in Hz")
    f0_end: Optional[float] = Field(None, description="Ending F0 in Hz")
    f0_min: Optional[float] = Field(None, description="Minimum F0 in Hz")
    f0_max: Optional[float] = Field(None, description="Maximum F0 in Hz")
    f0_mean: Optional[float] = Field(None, description="Mean F0 in Hz")
    f0_slope: Optional[float] = Field(None, description="F0 slope in Hz/s")
    f0_range: Optional[float] = Field(None, description="F0 range (max-min) in Hz")
    contour_5pt: Optional[List[Optional[float]]] = Field(
        None,
        description="5-point normalized contour [0%, 25%, 50%, 75%, 100%]"
    )
    voiced_ratio: Optional[float] = Field(None, description="Proportion of voiced frames")


class SegmentInfo(BaseModel):
    """Segment information."""
    type: str = Field(description="Segment type: silence, voiced, rime_core, speech, syllable_like")
    start_s: float = Field(description="Start time in seconds")
    end_s: float = Field(description="End time in seconds")
    duration_s: Optional[float] = Field(None, description="Duration in seconds")
    tone_features: Optional[ToneFeatures] = None


class UnitInfo(BaseModel):
    """Analysis unit (syllable-like unit)."""
    unit_id: int
    start_s: float
    end_s: float
    segments: List[int] = Field(description="Indices of segments in this unit")
    tone_features: Optional[ToneFeatures] = None


class AnalysisResult(BaseModel):
    """Complete analysis result."""
    schema_name: str = Field(default="praat-analysis", alias="schema", description="Schema identifier")
    meta: Dict[str, Any] = Field(description="Job metadata")
    summary: Dict[str, Any] = Field(description="Summary statistics by module")
    timeseries: Optional[Dict[str, Any]] = Field(None, description="Time-series data")
    segments: List[SegmentInfo] = Field(description="Detected segments")
    units: List[UnitInfo] = Field(description="Analysis units")
    debug: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True  # Allow both 'schema' and 'schema_name'
