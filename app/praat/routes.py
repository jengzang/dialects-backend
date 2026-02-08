"""
Praat acoustic analysis API routes (no database version).
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Optional, Literal
import shutil
import uuid
import threading

from .memory_store import task_store, upload_store
from .schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from .core.audio_processor import (
    detect_audio_format,
    normalize_audio,
    check_ffmpeg,
    validate_audio_file
)
from .core.job_executor_memory import execute_task
from .utils.validators import (
    validate_job_request,
    validate_upload_file,
    validate_audio_limits,
    raise_error,
    ErrorCode,
    SUPPORTED_MODULES,
    SUPPORTED_MODES,
    MAX_UPLOAD_MB,
    MAX_DURATION_S
)
from .config import STORAGE_BASE_DIR
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

router = APIRouter(prefix="/api/praat", tags=["Praat Acoustic Analysis"])

# Storage base directory
STORAGE_BASE = STORAGE_BASE_DIR
STORAGE_BASE.mkdir(parents=True, exist_ok=True)


@router.get("/capabilities")
async def get_capabilities():
    """
    Get backend capabilities.

    Returns supported formats, modules, modes, and limits.
    """
    return {
        "supported_input_formats": ["wav", "mp3", "m4a", "webm", "ogg", "flac", "aac"],
        "modes": list(SUPPORTED_MODES),
        "modules": {
            "basic": {},
            "pitch": {
                "f0_min": [30, 200],
                "f0_max": [200, 2000]
            },
            "intensity": {},
            "formant": {
                "max_formants": [3, 6]
            },
            "voice_quality": ["hnr", "jitter", "shimmer"],
            "segments": {}
        },
        "limits": {
            "max_duration_s": MAX_DURATION_S,
            "max_upload_mb": MAX_UPLOAD_MB
        },
        "ffmpeg_available": check_ffmpeg(),
        "storage": "memory"  # Indicate no database
    }


@router.post("/uploads")
async def create_upload(
    file: UploadFile = File(...),
    retain_original: bool = Form(False),
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Upload and normalize audio file.

    Note: Normalization is mandatory for Praat analysis.
    All audio files are automatically normalized to 16kHz mono WAV.

    Args:
        file: Audio file (any format)
        retain_original: Whether to keep original file (default: False)
        user: Current user (from ApiLimiter)

    Returns:
        Upload metadata and ID
    """
    # Check ffmpeg (required for normalization)
    if not check_ffmpeg():
        raise_error(
            ErrorCode.FFMPEG_NOT_FOUND,
            "FFmpeg is required for audio normalization but not found"
        )

    # Create upload directory first
    upload_id = str(uuid.uuid4())
    upload_dir = STORAGE_BASE / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save original file
    original_filename = file.filename
    original_ext = Path(original_filename).suffix.lower()
    original_path = upload_dir / f"original{original_ext}"

    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Get file size and validate
    original_size = original_path.stat().st_size
    validate_upload_file(original_size)

    # Detect format
    detected_mime = detect_audio_format(original_path)

    # Normalize audio (mandatory)
    normalized_path = upload_dir / "normalized.wav"
    try:
        normalize_audio(
            input_path=original_path,
            output_path=normalized_path,
            target_sr=16000,
            channels=1
        )

        # Validate normalized audio
        audio_meta = detect_audio_format(normalized_path)
        normalized_meta = {
            "format": "wav",
            "sample_rate": audio_meta["sample_rate"],
            "channels": audio_meta["channels"],
            "duration_s": audio_meta["duration_s"]
        }

        # Check duration limit
        if audio_meta["duration_s"] > MAX_DURATION_S:
            # Clean up
            shutil.rmtree(upload_dir)
            raise_error(
                ErrorCode.AUDIO_TOO_LONG,
                f"Audio duration ({audio_meta['duration_s']:.1f}s) exceeds maximum ({MAX_DURATION_S}s)"
            )

    except HTTPException:
        # Re-raise our own errors
        raise
    except Exception as e:
        # Normalization failed - clean up and error
        shutil.rmtree(upload_dir)
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            f"Failed to normalize audio: {str(e)}"
        )

    # Delete original if not retained
    if not retain_original:
        original_path.unlink()
        original_path = None

    # Store upload info in memory
    upload_store.create_upload(
        upload_id=upload_id,
        filename=original_filename,
        original_path=str(original_path) if original_path else None,
        normalized_path=str(normalized_path),
        metadata={
            "detected_mime": detected_mime,
            "original_size": original_size,
            "duration_s": audio_meta["duration_s"],
            "sample_rate": audio_meta["sample_rate"],
            "channels": audio_meta["channels"]
        }
    )

    return {
        "upload_id": upload_id,
        "source_filename": original_filename,
        "detected_mime": detected_mime,
        "original_meta": {
            "size_bytes": original_size
        },
        "normalized_meta": normalized_meta
    }


@router.get("/uploads/{upload_id}")
async def get_upload(
    upload_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """Get upload information."""
    upload = upload_store.get_upload(upload_id)

    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {upload_id} not found"
        )

    return {
        "upload_id": upload["id"],
        "filename": upload["filename"],
        "has_original": upload["original_path"] is not None,
        "has_normalized": upload["normalized_path"] is not None,
        "metadata": upload["metadata"],
        "created_at": upload["created_at"]
    }


@router.get("/uploads/{upload_id}/audio")
async def get_upload_audio(
    upload_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """Download normalized audio file."""
    upload = upload_store.get_upload(upload_id)

    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {upload_id} not found"
        )

    audio_path = upload["normalized_path"] or upload["original_path"]
    if not audio_path or not Path(audio_path).exists():
        raise_error(
            ErrorCode.AUDIO_NOT_FOUND,
            f"Audio file not found for upload {upload_id}"
        )

    return FileResponse(
        path=audio_path,
        media_type="audio/wav" if audio_path.endswith(".wav") else "audio/mpeg",
        filename=f"{upload_id}.wav" if audio_path.endswith(".wav") else upload["filename"]
    )


@router.delete("/uploads/{upload_id}")
async def delete_upload(
    upload_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """Delete upload and associated files."""
    upload = upload_store.get_upload(upload_id)

    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {upload_id} not found"
        )

    # Delete files
    upload_dir = STORAGE_BASE / upload_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)

    # Remove from memory
    upload_store.delete_upload(upload_id)

    return {"message": "Upload deleted successfully"}


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Create analysis job.

    Args:
        request: Job creation request
        background_tasks: FastAPI background tasks
        user: Current user

    Returns:
        Job ID and status
    """
    # Validate request
    validate_job_request(request)

    # Check upload exists
    upload = upload_store.get_upload(request.upload_id)
    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {request.upload_id} not found"
        )

    # Create task
    task_id = task_store.create_task(
        upload_id=request.upload_id,
        mode=request.mode,
        modules=request.modules,
        options=request.options.model_dump(exclude_none=True) if request.options else {},
        output_options=request.output.model_dump(exclude_none=True) if request.output else {}
    )

    # Execute in background
    background_tasks.add_task(execute_task, task_id)

    return {
        "job_id": task_id,
        "status": "queued"
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """Get job status."""
    task = task_store.get_task(job_id)

    if not task:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    return {
        "job_id": task["id"],
        "status": task["status"],
        "progress": task["progress"],
        "stage": task["stage"],
        "error": task["error"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"]
    }


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    view: Literal["full", "summary", "timeseries"] = Query("full"),
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Get job result.

    Args:
        job_id: Job ID
        view: Result view (full, summary, timeseries)
        user: Current user

    Returns:
        Analysis result JSON
    """
    task = task_store.get_task(job_id)

    if not task:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    if task["status"] != "done":
        raise_error(
            ErrorCode.JOB_NOT_DONE,
            f"Job {job_id} is not done yet (status: {task['status']})",
            status_code=400
        )

    result = task["result"]
    if not result:
        raise_error(
            ErrorCode.RESULT_NOT_FOUND,
            f"Result not found for job {job_id}",
            status_code=404
        )

    # Filter result based on view
    if view == "summary":
        result = {
            "schema": result.get("schema"),
            "meta": result.get("meta"),
            "summary": result.get("summary")
        }
    elif view == "timeseries":
        result = {
            "schema": result.get("schema"),
            "meta": result.get("meta"),
            "timeseries": result.get("timeseries")
        }

    return JSONResponse(content=result)


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Cancel job (best-effort).

    Note: Already running jobs may not be immediately canceled.
    """
    task = task_store.get_task(job_id)

    if not task:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    # Update status to canceled
    if task["status"] in ["queued", "running"]:
        task_store.update_task(job_id, status="canceled")

    # Delete task
    task_store.delete_task(job_id)

    return {"message": "Job canceled successfully"}
