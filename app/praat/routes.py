"""
Praat acoustic analysis API routes.
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, Literal
import shutil
import uuid

from .database import get_praat_db
from .models import Upload, Job
from .schemas.upload import UploadResponse, UploadMetadata, UploadInfo
from .schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from .schemas.result import AnalysisResult
from .core.audio_processor import (
    detect_audio_format,
    normalize_audio,
    check_ffmpeg,
    validate_audio_file
)
from .core.job_executor import execute_job
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

# Storage base directory (use system temp directory, same as tools)
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
        "ffmpeg_available": check_ffmpeg()
    }


@router.post("/uploads", response_model=UploadResponse)
async def create_upload(
    file: UploadFile = File(...),
    normalize: bool = Form(True),
    retain_original: bool = Form(False),
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Upload and normalize audio file.

    Args:
        file: Audio file (any format)
        normalize: Whether to normalize to WAV (default: True)
        retain_original: Whether to keep original file (default: False)
        db: Database session

    Returns:
        Upload metadata and ID
    """
    # Check ffmpeg
    if normalize and not check_ffmpeg():
        raise_error(
            ErrorCode.FFMPEG_NOT_FOUND,
            "FFmpeg is required for audio normalization but not found"
        )

    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset
    validate_upload_file(file_size)

    # Create upload directory
    upload_id = str(uuid.uuid4())
    upload_dir = STORAGE_BASE / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save original file
    original_ext = Path(file.filename).suffix or ".bin"
    original_path = upload_dir / f"original{original_ext}"

    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Detect format
    try:
        original_meta_dict = detect_audio_format(str(original_path))
    except HTTPException as e:
        # Cleanup and re-raise
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise e

    # Validate limits
    try:
        validate_audio_limits(
            original_meta_dict.get("duration_s"),
            original_meta_dict.get("size_bytes", file_size)
        )
    except HTTPException as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise e

    # Normalize if requested
    normalized_meta_dict = None
    normalized_path = None
    warnings = []

    if normalize:
        try:
            normalized_path = upload_dir / "normalized.wav"
            normalized_meta_dict = normalize_audio(
                str(original_path),
                str(normalized_path)
            )
        except Exception as e:
            warnings.append(f"Normalization failed: {str(e)}")
            normalized_path = None

    # Delete original if not retained and normalization succeeded
    if not retain_original and normalized_path:
        original_path.unlink()
        original_path = None

    # Create database record
    upload = Upload(
        id=upload_id,
        filename=file.filename,
        mime_type=original_meta_dict.get("mime_type"),
        size_bytes=original_meta_dict.get("size_bytes", file_size),
        duration_s=original_meta_dict.get("duration_s"),
        sample_rate=normalized_meta_dict.get("sample_rate") if normalized_meta_dict else original_meta_dict.get("sample_rate"),
        channels=normalized_meta_dict.get("channels") if normalized_meta_dict else original_meta_dict.get("channels"),
        normalized_path=str(normalized_path) if normalized_path else None,
        original_path=str(original_path) if original_path else None,
        warnings=warnings
    )

    db.add(upload)
    db.commit()
    db.refresh(upload)

    # Build response
    original_meta = UploadMetadata(
        size_bytes=original_meta_dict.get("size_bytes", file_size),
        duration_s=original_meta_dict.get("duration_s"),
        sample_rate=original_meta_dict.get("sample_rate"),
        channels=original_meta_dict.get("channels"),
        format=original_meta_dict.get("mime_type")
    )

    normalized_meta = None
    if normalized_meta_dict:
        normalized_meta = UploadMetadata(
            size_bytes=normalized_meta_dict.get("size_bytes"),
            duration_s=normalized_meta_dict.get("duration_s"),
            sample_rate=normalized_meta_dict.get("sample_rate"),
            channels=normalized_meta_dict.get("channels"),
            format=normalized_meta_dict.get("format")
        )

    return UploadResponse(
        upload_id=upload_id,
        source_filename=file.filename,
        detected_mime=original_meta_dict.get("mime_type"),
        original_meta=original_meta,
        normalized_meta=normalized_meta,
        warnings=warnings
    )


@router.get("/uploads/{upload_id}", response_model=UploadInfo)
async def get_upload(
    upload_id: str,
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """Get upload information."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()

    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {upload_id} not found",
            status_code=404
        )

    return UploadInfo(
        upload_id=upload.id,
        filename=upload.filename,
        mime_type=upload.mime_type,
        size_bytes=upload.size_bytes,
        duration_s=upload.duration_s,
        sample_rate=upload.sample_rate,
        channels=upload.channels,
        created_at=upload.created_at,
        warnings=upload.warnings or []
    )


@router.get("/uploads/{upload_id}/audio")
async def get_upload_audio(
    upload_id: str,
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """Download normalized audio file."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()

    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {upload_id} not found",
            status_code=404
        )

    # Prefer normalized, fallback to original
    audio_path = upload.normalized_path or upload.original_path

    if not audio_path or not Path(audio_path).exists():
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            "Audio file not found on disk",
            status_code=404
        )

    return FileResponse(
        audio_path,
        media_type="audio/wav" if audio_path.endswith(".wav") else "audio/mpeg",
        filename=f"{upload_id}.wav" if audio_path.endswith(".wav") else upload.filename
    )


@router.delete("/uploads/{upload_id}")
async def delete_upload(
    upload_id: str,
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """Delete upload and associated files."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()

    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {upload_id} not found",
            status_code=404
        )

    # Delete files
    upload_dir = STORAGE_BASE / upload_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    # Delete from database (cascade will delete jobs)
    db.delete(upload)
    db.commit()

    return {"message": "Upload deleted successfully"}


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Create analysis job.

    Args:
        request: Job creation request
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Job ID and initial status
    """
    # Validate request
    validate_job_request(request)

    # Check upload exists
    upload = db.query(Upload).filter(Upload.id == request.upload_id).first()
    if not upload:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Upload {request.upload_id} not found",
            status_code=404
        )

    # Create job
    job = Job(
        id=str(uuid.uuid4()),
        upload_id=request.upload_id,
        mode=request.mode,
        modules=request.modules,
        options=request.options.dict() if request.options else {},
        output_options=request.output.dict() if request.output else {},
        status="queued",
        progress=0.0
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Add background task
    background_tasks.add_task(execute_job, job.id, db)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """Get job status."""
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    error_detail = None
    if job.error:
        error_detail = {
            "code": job.error.get("code"),
            "message": job.error.get("message"),
            "detail": job.error.get("detail")
        }

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        error=error_detail,
        created_at=job.created_at,
        updated_at=job.updated_at
    )


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    view: Literal["full", "summary", "timeseries"] = Query("full"),
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Get job result.

    Args:
        job_id: Job ID
        view: Result view (full, summary, timeseries)
        db: Database session

    Returns:
        Analysis result JSON
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    if job.status != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not complete (status: {job.status})"
        )

    if not job.result_path or not Path(job.result_path).exists():
        raise_error(
            ErrorCode.PRAAT_ANALYSIS_FAILED,
            "Result file not found",
            status_code=404
        )

    # Load result
    import json
    with open(job.result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    # Filter by view
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
    db: Session = Depends(get_praat_db),
    user: Optional[User] = Depends(ApiLimiter)
):
    """
    Cancel job (best-effort).

    Note: Already running jobs may not be immediately canceled.
    """
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    if job.status in ["done", "error", "canceled"]:
        return {"message": f"Job already in terminal state: {job.status}"}

    job.status = "canceled"
    db.commit()

    return {"message": "Job canceled"}
