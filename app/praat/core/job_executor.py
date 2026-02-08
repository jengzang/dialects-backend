"""
Job execution engine for Praat analysis.
"""
import json
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import Job, Upload
from ..utils.validators import ErrorCode, raise_error
from ..utils.tone_features import extract_tone_features, sanitize_json
from .modules import MODULES

# Import all modules to register them
from .modules import basic, pitch, intensity, formant, voice_quality, segments


def execute_job(job_id: str, db: Session) -> None:
    """
    Execute analysis job in background.

    Args:
        job_id: Job ID
        db: Database session
    """
    job = None
    try:
        # Load job
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        # Update status to running
        job.status = "running"
        job.progress = 0.0
        job.stage = "loading"
        db.commit()

        # Load upload
        upload = db.query(Upload).filter(Upload.id == job.upload_id).first()
        if not upload:
            raise Exception("Upload not found")

        # Load audio with parselmouth
        import parselmouth

        audio_path = upload.normalized_path or upload.original_path
        if not audio_path or not Path(audio_path).exists():
            raise Exception(f"Audio file not found: {audio_path}")

        sound = parselmouth.Sound(audio_path)

        # Execute modules
        module_results = {}
        total_modules = len(job.modules)

        for idx, module_name in enumerate(job.modules):
            job.stage = module_name
            db.commit()

            if module_name not in MODULES:
                raise Exception(f"Unknown module: {module_name}")

            # Get module options
            module_options = job.options.get(module_name, {}) if job.options else {}

            # Execute module
            module_class = MODULES[module_name]
            module_instance = module_class()
            result = module_instance.analyze(sound, module_options, job.mode)

            module_results[module_name] = result

            # Update progress
            job.progress = (idx + 1) / total_modules
            db.commit()

        # Build final result
        job.stage = "finalize"
        db.commit()

        result_json = build_result_json(
            job=job,
            upload=upload,
            module_results=module_results,
            sound=sound
        )

        # Save result to file
        result_dir = Path(audio_path).parent
        result_path = result_dir / f"result_{job_id}.json"

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)

        # Update job
        job.result_path = str(result_path)
        job.status = "done"
        job.progress = 1.0
        job.stage = "completed"
        db.commit()

    except Exception as e:
        # Handle error
        if job:
            job.status = "error"
            job.error = {
                "code": ErrorCode.PRAAT_ANALYSIS_FAILED,
                "message": str(e),
                "detail": {
                    "traceback": traceback.format_exc()
                }
            }
            db.commit()


def build_result_json(
    job: Job,
    upload: Upload,
    module_results: Dict[str, Any],
    sound
) -> Dict[str, Any]:
    """
    Build final result JSON.

    Args:
        job: Job model
        upload: Upload model
        module_results: Results from all modules
        sound: Parselmouth Sound object

    Returns:
        Complete result dictionary
    """
    # Meta
    meta = {
        "job_id": job.id,
        "upload_id": upload.id,
        "mode": job.mode,
        "modules": job.modules,
        "created_at": job.created_at.isoformat(),
        "duration_s": upload.duration_s,
        "sample_rate": upload.sample_rate,
        "channels": upload.channels
    }

    # Summary
    summary = {}
    for module_name, result in module_results.items():
        if "summary" in result:
            summary[module_name] = result["summary"]
        elif "error" not in result:
            summary[module_name] = result

    # Timeseries (if requested)
    output_opts = job.output_options or {}
    include_timeseries = output_opts.get("include_timeseries", True)

    timeseries = None
    if include_timeseries:
        timeseries = {}

        # Pitch
        if "pitch" in module_results and "contour" in module_results["pitch"]:
            pitch_contour = module_results["pitch"]["contour"]
            timeseries["time"] = pitch_contour.get("time", [])
            timeseries["pitch_hz"] = pitch_contour.get("f0_hz", [])

        # Intensity
        if "intensity" in module_results and "contour" in module_results["intensity"]:
            intensity_contour = module_results["intensity"]["contour"]
            if "time" not in timeseries:
                timeseries["time"] = intensity_contour.get("time", [])
            timeseries["intensity_db"] = intensity_contour.get("intensity_db", [])

        # Formants
        if "formant" in module_results and "contour" in module_results["formant"]:
            formant_contour = module_results["formant"]["contour"]
            timeseries["formants"] = {
                k: v for k, v in formant_contour.items() if k.startswith("f")
            }

        # Downsample if requested
        downsample_hz = output_opts.get("downsample_hz")
        if downsample_hz and timeseries.get("time"):
            timeseries = downsample_timeseries(timeseries, downsample_hz)

    # Segments
    segments_list = []
    if "segments" in module_results:
        segments_list = module_results["segments"].get("segments", [])

    # Extract tone features for relevant segments
    pitch_contour = None
    pitch_times = None
    speaker_ref = None

    if "pitch" in module_results and "contour" in module_results["pitch"]:
        pitch_data = module_results["pitch"]["contour"]
        pitch_times = pitch_data.get("time", [])
        pitch_contour = pitch_data.get("f0_hz", [])
        speaker_ref = module_results["pitch"].get("speaker_ref")

    # Add tone features to segments
    if pitch_contour and pitch_times:
        for segment in segments_list:
            if segment["type"] in ["rime_core", "syllable_like"]:
                tone_features = extract_tone_features(
                    pitch_contour=pitch_contour,
                    time_values=pitch_times,
                    segment_start=segment["start_s"],
                    segment_end=segment["end_s"],
                    speaker_ref=speaker_ref
                )
                segment["tone_features"] = tone_features

    # Build units
    units = build_units(segments_list, job.mode)

    # Debug info (if requested)
    debug = None
    if output_opts.get("include_debug", False):
        debug = {
            "module_results": module_results
        }

    # Assemble result
    result = {
        "schema": "praat-analysis",
        "meta": meta,
        "summary": summary,
        "timeseries": timeseries,
        "segments": segments_list,
        "units": units,
        "debug": debug
    }

    # Sanitize JSON (remove NaN/inf)
    result = sanitize_json(result)

    return result


def build_units(segments: list, mode: str) -> list:
    """
    Build analysis units from segments.

    Args:
        segments: List of segments
        mode: Analysis mode

    Returns:
        List of units
    """
    units = []

    if mode == "single":
        # Single mode: one unit containing all segments
        if segments:
            start_s = min(s["start_s"] for s in segments)
            end_s = max(s["end_s"] for s in segments)

            # Find rime_core tone features
            tone_features = None
            for seg in segments:
                if seg["type"] == "rime_core" and "tone_features" in seg:
                    tone_features = seg["tone_features"]
                    break

            units.append({
                "unit_id": 0,
                "start_s": start_s,
                "end_s": end_s,
                "segments": list(range(len(segments))),
                "tone_features": tone_features
            })

    else:  # continuous
        # Group syllable_like segments as units
        syllable_segments = [
            (i, s) for i, s in enumerate(segments)
            if s["type"] == "syllable_like"
        ]

        for unit_id, (seg_idx, seg) in enumerate(syllable_segments):
            units.append({
                "unit_id": unit_id,
                "start_s": seg["start_s"],
                "end_s": seg["end_s"],
                "segments": [seg_idx],
                "tone_features": seg.get("tone_features")
            })

    return units


def downsample_timeseries(timeseries: Dict[str, Any], target_hz: int) -> Dict[str, Any]:
    """
    Downsample timeseries to target sampling rate.

    Args:
        timeseries: Timeseries dictionary
        target_hz: Target sampling rate

    Returns:
        Downsampled timeseries
    """
    import numpy as np

    if "time" not in timeseries or not timeseries["time"]:
        return timeseries

    times = np.array(timeseries["time"])
    if len(times) < 2:
        return timeseries

    # Calculate current sampling rate
    dt = np.mean(np.diff(times))
    current_hz = 1.0 / dt

    if current_hz <= target_hz:
        return timeseries

    # Downsample factor
    factor = int(current_hz / target_hz)
    if factor < 2:
        return timeseries

    # Downsample all arrays
    downsampled = {}
    for key, values in timeseries.items():
        if isinstance(values, list) and len(values) == len(times):
            downsampled[key] = values[::factor]
        elif isinstance(values, dict):
            # Handle nested dicts (like formants)
            downsampled[key] = {
                k: v[::factor] if isinstance(v, list) and len(v) == len(times) else v
                for k, v in values.items()
            }
        else:
            downsampled[key] = values

    return downsampled
