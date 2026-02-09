"""
Job execution engine for Praat analysis (task_manager version).
"""
import json
import traceback
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from app.tools.task_manager import task_manager
from app.tools.file_manager import file_manager
from ..utils.validators import ErrorCode
from ..utils.tone_features import extract_tone_features, sanitize_json
from ..utils.job_utils import update_job_status, find_job_by_id
from .modules import MODULES

# Import all modules to register them
from .modules import basic, pitch, intensity, formant, voice_quality, segments, spectrogram


async def execute_job_async(task_id: str, job_id: str):
    """
    Execute analysis job in background (async).

    Args:
        task_id: Task ID (e.g., "praat_abc123")
        job_id: Job ID (e.g., "praat_abc123_job_1")
    """
    try:
        # 1. Update job status to running
        update_job_status(
            task_manager, task_id, job_id,
            status="running",
            progress=0.0,
            stage="loading"
        )

        # 2. Load task and job info
        task = task_manager.get_task(task_id)
        job = find_job_by_id(task, job_id)

        if not job:
            raise Exception(f"Job {job_id} not found")

        # 3. Load audio (all jobs share the same file)
        task_dir = file_manager.get_task_dir(task_id, "praat")
        audio_path = task_dir / "normalized.wav"

        if not audio_path.exists():
            raise Exception(f"Audio file not found: {audio_path}")

        import parselmouth
        sound = parselmouth.Sound(str(audio_path))

        # 4. Execute analysis modules
        module_results = {}
        modules = job['modules']
        total_modules = len(modules)

        for idx, module_name in enumerate(modules):
            # Update current stage
            update_job_status(task_manager, task_id, job_id, stage=module_name)

            if module_name not in MODULES:
                raise Exception(f"Unknown module: {module_name}")

            # Get module options
            module_options = job.get('options', {}).get(module_name, {})

            # For voice_quality, also include pitch options if not specified
            if module_name == 'voice_quality' and not module_options.get('f0_min'):
                pitch_options = job.get('options', {}).get('pitch', {})
                if pitch_options:
                    module_options = {
                        'f0_min': pitch_options.get('f0_min', 75.0),
                        'f0_max': pitch_options.get('f0_max', 600.0),
                        **module_options
                    }

            # Run module
            module_class = MODULES[module_name]
            module_instance = module_class()
            result = module_instance.analyze(sound, module_options, job['mode'])

            module_results[module_name] = result

            # Update progress (0-0.9)
            progress = (idx + 1) / total_modules * 0.9
            update_job_status(task_manager, task_id, job_id, progress=progress)

        # 5. Build result JSON
        update_job_status(task_manager, task_id, job_id, stage="finalize", progress=0.95)

        upload_data = task.get('data', {}).get('upload', {})
        audio_metadata = upload_data.get('audio_metadata', {})

        result_json = build_result_json(
            job_id=job_id,
            task_id=task_id,
            job_data=job,
            module_results=module_results,
            audio_metadata=audio_metadata,
            sound=sound
        )

        # 6. Save result (overwrite result.json)
        result_path = task_dir / "result.json"

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)

        # 7. Mark job as done
        update_job_status(
            task_manager, task_id, job_id,
            status="done",
            progress=1.0,
            completed_at=datetime.now().isoformat()
        )

        # 8. Update last_result and clear current_job_id
        task = task_manager.get_task(task_id)
        task_data = task.get('data', {})
        task_data['last_result'] = {
            "job_id": job_id,
            "completed_at": datetime.now().isoformat()
        }
        task_data['current_job_id'] = None  # Clear current job
        task_manager.update_task(task_id, data=task_data)

    except Exception as e:
        # Error handling
        error_msg = str(e)
        error_trace = traceback.format_exc()

        try:
            update_job_status(
                task_manager, task_id, job_id,
                status="error",
                error={
                    "code": ErrorCode.PRAAT_ANALYSIS_FAILED,
                    "message": error_msg,
                    "detail": {"traceback": error_trace}
                }
            )

            # Clear current_job_id on error
            task = task_manager.get_task(task_id)
            if task:
                task_data = task.get('data', {})
                if task_data.get('current_job_id') == job_id:
                    task_data['current_job_id'] = None
                    task_manager.update_task(task_id, data=task_data)
        except:
            # If we can't even update the error status, log it
            print(f"[Praat] Failed to update error status for job {job_id}: {e}")


def build_result_json(
    job_id: str,
    task_id: str,
    job_data: Dict[str, Any],
    module_results: Dict[str, Any],
    audio_metadata: Dict[str, Any],
    sound
) -> Dict[str, Any]:
    """
    Build final result JSON.

    Args:
        job_id: Job ID
        task_id: Task ID
        job_data: Job data dict
        module_results: Results from all modules
        audio_metadata: Audio metadata from upload
        sound: Parselmouth Sound object

    Returns:
        Complete result dictionary
    """
    # Meta
    meta = {
        "job_id": job_id,
        "task_id": task_id,
        "mode": job_data.get('mode'),
        "modules": job_data.get('modules'),
        "created_at": job_data.get('created_at'),
        "duration_s": audio_metadata.get('duration_s'),
        "sample_rate": audio_metadata.get('sample_rate'),
        "channels": audio_metadata.get('channels')
    }

    # Summary
    summary = {}
    for module_name, result in module_results.items():
        # Skip modules that returned errors
        if "error" in result:
            continue
        # Extract summary if available
        if "summary" in result:
            summary[module_name] = result["summary"]
        else:
            summary[module_name] = result

    # Timeseries (if requested)
    output_opts = job_data.get('output_options', {})
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
    units = build_units(segments_list, job_data.get('mode'))

    # Debug info (if requested)
    debug = None
    if output_opts.get("include_debug", False):
        debug = {
            "module_results": module_results
        }

    # Spectrogram (if requested)
    spectrogram_data = None
    if "spectrogram" in module_results and "error" not in module_results["spectrogram"]:
        spectrogram_data = {
            "time": module_results["spectrogram"]["time"],
            "frequency": module_results["spectrogram"]["frequency"],
            "energy_db": module_results["spectrogram"]["energy_db"]
        }

    # Assemble result
    result = {
        "schema": "praat-analysis",
        "meta": meta,
        "summary": summary,
        "timeseries": timeseries,
        "spectrogram": spectrogram_data,
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
