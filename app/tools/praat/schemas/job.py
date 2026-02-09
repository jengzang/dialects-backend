"""
Job-related Pydantic schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class NormalizeOptions(BaseModel):
    """Audio normalization options."""
    sample_rate: int = 16000
    channels: int = 1


class PitchOptions(BaseModel):
    """Pitch extraction options."""
    f0_min: float = 75.0
    f0_max: float = 600.0
    time_step: float = 0.0  # 0 = auto


class FormantOptions(BaseModel):
    """Formant extraction options.

    Recommended max_freq_hz values by speaker type:
    - Adult males: 5000 Hz
    - Adult females: 5500 Hz (default)
    - Children: 8000 Hz

    Using incorrect max_freq_hz can cause tracking errors and
    systematically biased formant values.
    """
    max_formants: int = 5
    max_freq_hz: float = Field(
        default=5500.0,
        description="Maximum formant frequency in Hz. Use 5000 for males, 5500 for females, 8000 for children."
    )
    window_length: float = 0.025
    time_step: float = 0.002  # 2ms for better resolution
    pre_emphasis_from: float = Field(
        default=50.0,
        description="Pre-emphasis frequency in Hz. Standard value is 50 Hz for high-pass filtering."
    )


class SpectrogramOptions(BaseModel):
    """Spectrogram extraction options."""
    window_length: float = 0.005  # 5ms
    time_step: float = 0.002  # 2ms
    frequency_step: float = 20.0  # 20 Hz
    max_frequency: float = 8000.0  # 8000 Hz


class VoiceQualityOptions(BaseModel):
    """Voice quality analysis options."""
    f0_min: float = 75.0
    f0_max: float = 600.0
    min_voiced_frames: int = 10


class JobOptions(BaseModel):
    """Analysis options."""
    normalize: Optional[NormalizeOptions] = None
    pitch: Optional[PitchOptions] = None
    formant: Optional[FormantOptions] = None
    spectrogram: Optional[SpectrogramOptions] = None
    voice_quality: Optional[VoiceQualityOptions] = None


class OutputOptions(BaseModel):
    """Output configuration."""
    downsample_hz: Optional[int] = 100
    include_timeseries: bool = True
    include_summary: bool = True
    include_debug: bool = False


class JobCreateRequest(BaseModel):
    """Request to create analysis job."""
    upload_id: str
    mode: Literal["single", "continuous"]
    modules: List[str] = Field(
        default=["basic", "pitch", "intensity", "segments"],
        description="Modules to run: basic, pitch, intensity, formant, voice_quality, segments, spectrogram"
    )
    options: JobOptions = Field(default_factory=JobOptions)
    output: OutputOptions = Field(default_factory=OutputOptions)


class JobCreateResponse(BaseModel):
    """Response for job creation."""
    job_id: str
    status: str


class ErrorDetail(BaseModel):
    """Error details."""
    code: str
    message: str
    detail: Optional[Dict[str, Any]] = None


class JobStatusResponse(BaseModel):
    """Job status response."""
    job_id: str
    status: Literal["queued", "running", "done", "error", "canceled"]
    progress: float = Field(ge=0.0, le=1.0)
    stage: Optional[str] = None
    error: Optional[ErrorDetail] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
