"""
Praat acoustic analysis API routes (task_manager version).
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Optional, Literal
import shutil
from datetime import datetime

from app.tools.task_manager import task_manager, TaskStatus
from app.tools.file_manager import file_manager
from .schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from .core.audio_processor import (
    detect_audio_format,
    normalize_audio,
    check_ffmpeg,
)
from .utils.validators import (
    validate_job_request,
    validate_upload_file,
    raise_error,
    ErrorCode,
    SUPPORTED_MODULES,
    SUPPORTED_MODES,
    MAX_UPLOAD_MB,
    MAX_DURATION_S
)
from .utils.job_utils import extract_task_id_from_job_id, find_job_by_id
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

router = APIRouter(prefix="/api/tools/praat", tags=["Praat Acoustic Analysis"])


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
            "segments": {},
            "spectrogram": {
                "window_length": [0.001, 0.01],
                "time_step": [0.001, 0.01],
                "frequency_step": [10, 100],
                "max_frequency": [4000, 16000]
            }
        },
        "limits": {
            "max_duration_s": MAX_DURATION_S,
            "max_upload_mb": MAX_UPLOAD_MB
        },
        "ffmpeg_available": check_ffmpeg(),
        "storage": "file_based"
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
        Task metadata with task_id
    """
    # Check ffmpeg (required for normalization)
    if not check_ffmpeg():
        raise_error(
            ErrorCode.FFMPEG_NOT_FOUND,
            "FFmpeg is required for audio normalization but not found"
        )

    # Create task
    task_id = task_manager.create_task("praat", {
        "upload": {
            "source_filename": file.filename,
            "detected_mime": file.content_type
        },
        "jobs": [],
        "current_job_id": None
    })

    # Get task directory
    task_dir = file_manager.get_task_dir(task_id, "praat")

    # Save original file
    original_filename = file.filename
    original_ext = Path(original_filename).suffix.lower()
    original_path = task_dir / f"original{original_ext}"

    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Get file size and validate
    original_size = original_path.stat().st_size
    validate_upload_file(original_size)

    # Detect format
    detected_mime = detect_audio_format(original_path)

    # Normalize audio (mandatory)
    normalized_path = task_dir / "normalized.wav"
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
            file_manager.delete_task_files(task_id, "praat")
            raise_error(
                ErrorCode.AUDIO_TOO_LONG,
                f"Audio duration ({audio_meta['duration_s']:.1f}s) exceeds maximum ({MAX_DURATION_S}s)"
            )

    except HTTPException:
        # Re-raise our own errors
        raise
    except Exception as e:
        # Normalization failed - clean up and error
        file_manager.delete_task_files(task_id, "praat")
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            f"Failed to normalize audio: {str(e)}"
        )

    # Delete original if not retained
    if not retain_original:
        original_path.unlink()
        original_path_str = None
    else:
        original_path_str = str(original_path.relative_to(task_dir))

    # Update task with upload info
    task_manager.update_task(
        task_id,
        status=TaskStatus.COMPLETED,
        data={
            "upload": {
                "source_filename": original_filename,
                "detected_mime": detected_mime,
                "original_path": original_path_str,
                "normalized_path": "normalized.wav",
                "audio_metadata": {
                    "duration_s": audio_meta["duration_s"],
                    "sample_rate": audio_meta["sample_rate"],
                    "channels": audio_meta["channels"],
                    "format": "wav"
                }
            },
            "jobs": [],
            "current_job_id": None
        }
    )

    return {
        "task_id": task_id,
        "source_filename": original_filename,
        "detected_mime": detected_mime,
        "original_meta": {
            "size_bytes": original_size
        },
        "normalized_meta": normalized_meta
    }


@router.get("/uploads/progress/{task_id}")
async def get_upload(
        task_id: str,
        user: Optional[User] = Depends(ApiLimiter)
):
    """Get upload information."""
    task = task_manager.get_task(task_id)

    if not task:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Task {task_id} not found"
        )

    upload_data = task.get('data', {}).get('upload', {})

    return {
        "task_id": task_id,
        "source_filename": upload_data.get('source_filename'),
        "detected_mime": upload_data.get('detected_mime'),
        "has_original": upload_data.get('original_path') is not None,
        "has_normalized": upload_data.get('normalized_path') is not None,
        "audio_metadata": upload_data.get('audio_metadata'),
        "created_at": task.get('created_at')
    }


@router.get("/uploads/progress/{task_id}/audio")
async def get_upload_audio(
        task_id: str,
        user: Optional[User] = Depends(ApiLimiter)
):
    """Download normalized audio file."""
    task = task_manager.get_task(task_id)

    if not task:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Task {task_id} not found"
        )

    task_dir = file_manager.get_task_dir(task_id, "praat")
    normalized_path = task_dir / "normalized.wav"

    if not normalized_path.exists():
        raise_error(
            ErrorCode.AUDIO_NOT_FOUND,
            f"Audio file not found for task {task_id}"
        )

    return FileResponse(
        path=normalized_path,
        media_type="audio/wav",
        filename=f"{task_id}.wav"
    )


@router.delete("/uploads/progress/{task_id}")
async def delete_upload(
        task_id: str,
        user: Optional[User] = Depends(ApiLimiter)
):
    """Delete task and associated files."""
    task = task_manager.get_task(task_id)

    if not task:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Task {task_id} not found"
        )

    # Delete task (includes all files)
    task_manager.delete_task(task_id)

    return {"message": "Task deleted successfully"}


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

    # Check task exists (using upload_id as task_id)
    task_id = request.upload_id
    task = task_manager.get_task(task_id)
    if not task:
        raise_error(
            ErrorCode.UPLOAD_NOT_FOUND,
            f"Task {task_id} not found"
        )

    # Check if there's a running job
    current_job_id = task.get('data', {}).get('current_job_id')
    if current_job_id:
        current_job = find_job_by_id(task, current_job_id)
        if current_job and current_job.get('status') == 'running':
            raise_error(
                ErrorCode.JOB_RUNNING,
                "Another job is currently running for this task",
                status_code=400
            )

    # Generate job_id
    job_counter = len(task.get('data', {}).get('jobs', [])) + 1
    job_id = f"{task_id}_job_{job_counter}"

    # Add job record
    job_record = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "mode": request.mode,
        "modules": request.modules,
        "options": request.options.model_dump(exclude_none=True) if request.options else {},
        "output_options": request.output.model_dump(exclude_none=True) if request.output else {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Update task data
    task_data = task.get('data', {})
    if 'jobs' not in task_data:
        task_data['jobs'] = []
    task_data['jobs'].append(job_record)
    task_data['current_job_id'] = job_id

    task_manager.update_task(task_id, data=task_data)

    # Start background analysis
    from .core.job_executor import execute_job_async
    background_tasks.add_task(execute_job_async, task_id, job_id)

    return {
        "job_id": job_id,
        "status": "queued"
    }


@router.get("/jobs/progress/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
        job_id: str,
        user: Optional[User] = Depends(ApiLimiter)
):
    """Get job status."""
    # Extract task_id from job_id
    task_id = extract_task_id_from_job_id(job_id)

    # Read task
    task = task_manager.get_task(task_id)
    if not task:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404
        )

    # Find job
    job = find_job_by_id(task, job_id)
    if not job:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    return {
        "job_id": job_id,
        "status": job.get('status'),
        "progress": job.get('progress', 0.0),
        "stage": job.get('stage'),
        "error": job.get('error'),
        "created_at": job.get('created_at'),
        "updated_at": job.get('updated_at')
    }


@router.get("/jobs/progress/{job_id}/result")
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
    # Extract task_id
    task_id = extract_task_id_from_job_id(job_id)

    # Verify job exists and is completed
    task = task_manager.get_task(task_id)
    if not task:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404
        )

    job = find_job_by_id(task, job_id)
    if not job:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    if job.get('status') != 'done':
        raise_error(
            ErrorCode.JOB_NOT_DONE,
            f"Job {job_id} is not done yet (status: {job.get('status')})",
            status_code=400
        )

    # Read result.json
    task_dir = file_manager.get_task_dir(task_id, "praat")
    result_path = task_dir / "result.json"

    if not result_path.exists():
        raise_error(
            ErrorCode.RESULT_NOT_FOUND,
            f"Result file not found for job {job_id}",
            status_code=404
        )

    import json
    with open(result_path, encoding='utf-8') as f:
        result = json.load(f)

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


@router.delete("/jobs/progress/{job_id}")
async def cancel_job(
        job_id: str,
        user: Optional[User] = Depends(ApiLimiter)
):
    """
    Cancel job (best-effort).

    Note: Already running jobs may not be immediately canceled.
    """
    from .utils.job_utils import update_job_status

    # Extract task_id
    task_id = extract_task_id_from_job_id(job_id)

    task = task_manager.get_task(task_id)
    if not task:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404
        )

    job = find_job_by_id(task, job_id)
    if not job:
        raise_error(
            ErrorCode.JOB_NOT_FOUND,
            f"Job {job_id} not found",
            status_code=404
        )

    # Update status to canceled
    if job.get('status') in ["queued", "running"]:
        update_job_status(task_manager, task_id, job_id, status="canceled")

        # Clear current_job_id if this is the current job
        task_data = task.get('data', {})
        if task_data.get('current_job_id') == job_id:
            task_data['current_job_id'] = None
            task_manager.update_task(task_id, data=task_data)

    return {"message": "Job canceled successfully"}
