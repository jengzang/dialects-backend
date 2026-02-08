"""
Praat service configuration.
"""
import os
import tempfile
from pathlib import Path

# Storage settings
# Use system temp directory (same as tools) instead of project directory
STORAGE_BASE_DIR = Path(os.getenv("FILE_STORAGE_PATH", tempfile.gettempdir())) / "fastapi_tools" / "praat"

# Cleanup settings
CLEANUP_ENABLED = True  # Enable automatic cleanup
CLEANUP_AGE_HOURS = 1  # Delete uploads older than this many hours (changed from days to hours)
CLEANUP_SCHEDULE_MINUTES = 30  # Run cleanup every N minutes (changed from daily to frequent)

# Orphaned file cleanup
ORPHANED_CLEANUP_ENABLED = True  # Enable orphaned file cleanup
ORPHANED_CLEANUP_HOURS = 2  # Run every 2 hours (changed from weekly)

# Upload limits
MAX_UPLOAD_MB = 50  # Maximum upload size in MB
MAX_DURATION_S = 20  # Maximum audio duration in seconds (reduced from 60s)

# Memory storage settings
TASK_RETENTION_SECONDS = 3600  # Keep tasks in memory for 1 hour
UPLOAD_RETENTION_SECONDS = 3600  # Keep uploads in memory for 1 hour

# Analysis settings
DEFAULT_SAMPLE_RATE = 16000  # Default sample rate for normalization
DEFAULT_CHANNELS = 1  # Default number of channels

# Supported audio formats
SUPPORTED_FORMATS = ["wav", "mp3", "m4a", "webm", "ogg", "flac", "aac"]

# Module settings
SUPPORTED_MODULES = {"basic", "pitch", "intensity", "formant", "voice_quality", "segments"}
SUPPORTED_MODES = {"single", "continuous"}

# Pitch extraction defaults
DEFAULT_F0_MIN = 75.0  # Hz
DEFAULT_F0_MAX = 600.0  # Hz

# Formant extraction defaults
DEFAULT_MAX_FORMANTS = 5
DEFAULT_MAX_FREQ_HZ = 5500.0
