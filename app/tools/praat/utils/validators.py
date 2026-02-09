"""
Input validation and error handling.
"""
from fastapi import HTTPException
from typing import Dict, Any, Optional


# Error codes
class ErrorCode:
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
    AUDIO_DECODE_FAILED = "AUDIO_DECODE_FAILED"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_NOT_FOUND = "AUDIO_NOT_FOUND"
    UNSUPPORTED_OPTION = "UNSUPPORTED_OPTION"
    PRAAT_ANALYSIS_FAILED = "PRAAT_ANALYSIS_FAILED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_NOT_DONE = "JOB_NOT_DONE"
    JOB_RUNNING = "JOB_RUNNING"
    JOB_CANCELED = "JOB_CANCELED"
    UPLOAD_NOT_FOUND = "UPLOAD_NOT_FOUND"
    RESULT_NOT_FOUND = "RESULT_NOT_FOUND"
    INVALID_MODULE = "INVALID_MODULE"
    FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"


# Limits
MAX_UPLOAD_MB = 50
MAX_DURATION_S = 60

# Supported modules
SUPPORTED_MODULES = {"basic", "pitch", "intensity", "formant", "voice_quality", "segments", "spectrogram"}

# Supported modes
SUPPORTED_MODES = {"single", "continuous"}


def raise_error(code: str, message: str, detail: Optional[Dict[str, Any]] = None, status_code: int = 400):
    """Raise HTTP exception with standardized error format."""
    raise HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "detail": detail or {}
            }
        }
    )


def validate_job_request(request) -> None:
    """Validate job creation request."""
    # Check mode
    if request.mode not in SUPPORTED_MODES:
        raise_error(
            ErrorCode.UNSUPPORTED_OPTION,
            f"Unsupported mode: {request.mode}",
            {"supported_modes": list(SUPPORTED_MODES)}
        )

    # Check modules
    invalid_modules = set(request.modules) - SUPPORTED_MODULES
    if invalid_modules:
        raise_error(
            ErrorCode.INVALID_MODULE,
            f"Invalid modules: {invalid_modules}",
            {"supported_modules": list(SUPPORTED_MODULES)}
        )

    # At least one module required
    if not request.modules:
        raise_error(
            ErrorCode.UNSUPPORTED_OPTION,
            "At least one module must be specified"
        )


def validate_upload_file(file_size: int) -> None:
    """Validate upload file size."""
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if file_size > max_bytes:
        raise_error(
            ErrorCode.UPLOAD_TOO_LARGE,
            f"File size exceeds maximum of {MAX_UPLOAD_MB}MB",
            {"size_bytes": file_size, "max_bytes": max_bytes}
        )


def validate_audio_limits(duration_s: Optional[float], size_bytes: int) -> None:
    """Validate audio duration and size limits."""
    if duration_s and duration_s > MAX_DURATION_S:
        raise_error(
            ErrorCode.AUDIO_TOO_LONG,
            f"Audio duration exceeds maximum of {MAX_DURATION_S}s",
            {"duration_s": duration_s, "max_duration_s": MAX_DURATION_S}
        )

    validate_upload_file(size_bytes)
