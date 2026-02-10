"""
Praat service configuration.
"""

# Cleanup settings
CLEANUP_ENABLED = True  # Enable automatic cleanup
CLEANUP_AGE_HOURS = 1  # Delete tasks older than this many hours
CLEANUP_SCHEDULE_MINUTES = 30  # Run cleanup every N minutes

# Upload limits
MAX_UPLOAD_MB = 50  # Maximum upload size in MB
MAX_DURATION_S = 20  # Maximum audio duration in seconds

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
