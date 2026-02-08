"""
Audio processing with FFmpeg.
"""
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from ..utils.validators import raise_error, ErrorCode


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def detect_audio_format(file_path: str) -> Dict[str, Any]:
    """
    Detect audio format using ffprobe.

    Args:
        file_path: Path to audio file

    Returns:
        Dictionary with format metadata

    Raises:
        HTTPException if detection fails
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise_error(
                ErrorCode.AUDIO_DECODE_FAILED,
                "Failed to detect audio format",
                {"stderr": result.stderr}
            )

        data = json.loads(result.stdout)

        # Extract audio stream info
        audio_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                audio_stream = stream
                break

        if not audio_stream:
            raise_error(
                ErrorCode.AUDIO_DECODE_FAILED,
                "No audio stream found in file"
            )

        format_info = data.get("format", {})

        return {
            "mime_type": format_info.get("format_name"),
            "duration_s": float(format_info.get("duration", 0)),
            "size_bytes": int(format_info.get("size", 0)),
            "sample_rate": int(audio_stream.get("sample_rate", 0)),
            "channels": int(audio_stream.get("channels", 0)),
            "codec": audio_stream.get("codec_name"),
            "bit_rate": int(audio_stream.get("bit_rate", 0))
        }

    except subprocess.TimeoutExpired:
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            "Audio format detection timed out"
        )
    except json.JSONDecodeError as e:
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            "Failed to parse ffprobe output",
            {"error": str(e)}
        )
    except Exception as e:
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            f"Audio format detection failed: {str(e)}"
        )


def normalize_audio(
    input_path: str,
    output_path: str,
    target_sr: int = 16000,
    channels: int = 1
) -> Dict[str, Any]:
    """
    Normalize audio to WAV format using ffmpeg.

    Args:
        input_path: Input audio file path
        output_path: Output WAV file path
        target_sr: Target sample rate (Hz)
        channels: Target number of channels

    Returns:
        Dictionary with normalized audio metadata

    Raises:
        HTTPException if normalization fails
    """
    try:
        # Run ffmpeg
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", input_path,
                "-ar", str(target_sr),
                "-ac", str(channels),
                "-y",  # Overwrite output
                output_path
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise_error(
                ErrorCode.AUDIO_DECODE_FAILED,
                "Audio normalization failed",
                {"stderr": result.stderr}
            )

        # Get metadata of normalized file
        metadata = detect_audio_format(output_path)

        return {
            "format": "wav",
            "sample_rate": metadata["sample_rate"],
            "channels": metadata["channels"],
            "duration_s": metadata["duration_s"],
            "size_bytes": metadata["size_bytes"]
        }

    except subprocess.TimeoutExpired:
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            "Audio normalization timed out"
        )
    except Exception as e:
        raise_error(
            ErrorCode.AUDIO_DECODE_FAILED,
            f"Audio normalization failed: {str(e)}"
        )


def get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds."""
    metadata = detect_audio_format(file_path)
    return metadata["duration_s"]


def validate_audio_file(
    file_path: str,
    max_duration_s: float = 60,
    max_size_mb: float = 50
) -> Tuple[bool, Optional[str]]:
    """
    Validate audio file.

    Args:
        file_path: Path to audio file
        max_duration_s: Maximum duration in seconds
        max_size_mb: Maximum file size in MB

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        metadata = detect_audio_format(file_path)

        # Check duration
        if metadata["duration_s"] > max_duration_s:
            return False, f"Duration {metadata['duration_s']:.1f}s exceeds maximum {max_duration_s}s"

        # Check size
        size_mb = metadata["size_bytes"] / (1024 * 1024)
        if size_mb > max_size_mb:
            return False, f"File size {size_mb:.1f}MB exceeds maximum {max_size_mb}MB"

        return True, None

    except Exception as e:
        return False, f"Validation failed: {str(e)}"
