# Praat Acoustic Analysis Backend Service

A comprehensive experimental phonetics analysis backend using FastAPI and praat-parselmouth, specifically designed for Chinese and dialectal tone analysis.

## Overview

This service provides asynchronous acoustic analysis capabilities with support for:
- **Two analysis modes**: Single syllable and continuous speech
- **Modular analysis**: Basic features, pitch, intensity, formants, voice quality, segmentation
- **Tone feature extraction**: Specialized for Chinese/dialect tone contour analysis
- **Audio normalization**: Automatic format conversion via FFmpeg
- **Job-based processing**: Non-blocking async task execution

## Architecture

### Resource Model
1. **Upload**: Audio file management (original + normalized)
2. **Job**: Async analysis task with progress tracking
3. **Result**: JSON output with acoustic features

### Components
- `app/praat/routes.py`: API endpoints
- `app/praat/models.py`: SQLAlchemy models (Upload, Job)
- `app/praat/database.py`: Database session management
- `app/praat/core/audio_processor.py`: FFmpeg audio normalization
- `app/praat/core/job_executor.py`: Background job orchestration
- `app/praat/core/modules/`: Analysis modules (basic, pitch, intensity, formant, voice_quality, segments)
- `app/praat/utils/tone_features.py`: Chinese tone feature extraction
- `app/praat/schemas/`: Pydantic request/response models

## API Endpoints

### Capabilities
```
GET /api/praat/capabilities
```
Returns supported formats, modules, modes, and limits.

### Upload Management
```
POST /api/praat/uploads
  - file: Audio file (multipart/form-data)
  - normalize: bool (default: true)
  - retain_original: bool (default: false)

GET /api/praat/uploads/{upload_id}
GET /api/praat/uploads/{upload_id}/audio
DELETE /api/praat/uploads/{upload_id}
```

### Job Management
```
POST /api/praat/jobs
  Body: {
    "upload_id": "uuid",
    "mode": "single | continuous",
    "modules": ["basic", "pitch", "intensity", "formant", "voice_quality", "segments"],
    "options": {...},
    "output": {...}
  }

GET /api/praat/jobs/{job_id}
GET /api/praat/jobs/{job_id}/result?view=full|summary|timeseries
DELETE /api/praat/jobs/{job_id}
```

## Analysis Modes

### Single Mode
For single syllables or isolated sounds:
- Segments: silence → voiced → rime_core
- Extracts stable tone features from rime_core
- Optimized for accurate F0 contour extraction

### Continuous Mode
For phrases, sentences, or connected speech:
- Segments: silence → speech → voiced → syllable_like
- Detects syllable-like units via energy peaks
- Handles coarticulation and tone sandhi

## Analysis Modules

### Basic
- Duration, RMS, peak amplitude
- Silence ratio

### Pitch (Two-Phase Auto-Tuning)
1. **Phase 1**: Wide range extraction (75-600 Hz)
2. **Phase 2**: Auto-tune based on P5/P95, re-extract
- No interpolation across unvoiced segments
- Speaker reference (P5, P50, P95)

### Intensity
- Intensity contour extraction
- Summary statistics

### Formant
- F1-F5 extraction with median filtering
- Computed only in stable regions
- Robust tracking with smoothing

### Voice Quality
- HNR (Harmonics-to-Noise Ratio)
- Jitter (local, absolute)
- Shimmer (local, dB)

### Segments
- Mode-specific segmentation strategies
- Silence detection
- Voiced region identification
- Syllable-like unit detection (continuous mode)

## Tone Features (Chinese/Dialect Specific)

For each rime_core (single) or syllable_like (continuous) segment:
- `f0_start`, `f0_end`: Boundary F0 values
- `f0_min`, `f0_max`, `f0_mean`: Statistics
- `f0_slope`: Linear regression slope (Hz/s)
- `f0_range`: F0 range (max - min)
- `contour_5pt`: 5-point normalized contour [0%, 25%, 50%, 75%, 100%]
- `voiced_ratio`: Proportion of voiced frames

## Result JSON Structure

```json
{
  "schema": "praat-analysis",
  "meta": {
    "job_id": "...",
    "mode": "single|continuous",
    "duration_s": 3.42
  },
  "summary": {
    "basic": {...},
    "pitch": {
      "mean_f0": 180.5,
      "speaker_ref": {"p5": 120, "p50": 180, "p95": 250}
    },
    "intensity": {...},
    "formant": {...},
    "voice_quality": {...}
  },
  "timeseries": {
    "time": [0.0, 0.01, 0.02, ...],
    "pitch_hz": [null, 180.2, 181.5, ...],
    "intensity_db": [45.2, 46.1, ...],
    "formants": {"f1": [...], "f2": [...]}
  },
  "segments": [
    {
      "type": "rime_core",
      "start_s": 0.25,
      "end_s": 0.75,
      "tone_features": {...}
    }
  ],
  "units": [
    {
      "unit_id": 0,
      "start_s": 0.15,
      "end_s": 0.85,
      "segments": [0, 1, 2],
      "tone_features": {...}
    }
  ]
}
```

## Installation

### Dependencies
```bash
pip install praat-parselmouth>=0.4.3 scipy>=1.10.0
```

### FFmpeg
Required for audio normalization. Install via:
- Windows: Download from https://ffmpeg.org/
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

### Database
SQLite database is automatically created at `data/praat.db` on first run.


Tests verify:
- Module imports
- Database creation
- Parselmouth functionality
- FFmpeg availability

## Configuration

Rate limiting and logging configured in `common/config.py`:
```python
API_ROUTE_CONFIG["/api/praat/uploads"] = {
    "rate_limit": True,
    "require_login": False,
    "log_params": True,
    "log_body": False,  # Don't log binary audio
}
```

### Automatic Cleanup

The service automatically cleans up old uploads to prevent disk space exhaustion:

**Storage Location**:
- Files stored in system temp directory: `{temp}/fastapi_tools/praat/`
- Same location as other tools (consistent with project pattern)

**Default Settings** (`app/praat/config.py`):
- `CLEANUP_AGE_HOURS = 1`: Delete uploads older than 1 hour
- `CLEANUP_SCHEDULE_MINUTES = 30`: Run cleanup every 30 minutes
- `ORPHANED_CLEANUP_HOURS = 2`: Clean up orphaned files every 2 hours

**Cleanup Policy**:
- Uploads older than 1 hour are automatically deleted
- Only deletes uploads with no active jobs (queued/running)
- Orphaned files (no database record) cleaned every 2 hours
- Both files and database records are removed

**Manual Cleanup**:
```bash
# Clean up uploads older than 1 hour (default)
python -m app.praat.manual_cleanup

# Clean up uploads older than 6 hours
python -m app.praat.manual_cleanup --hours 6

# Dry run (show what would be deleted)
python -m app.praat.manual_cleanup --dry-run

# Clean up orphaned files only
python -m app.praat.manual_cleanup --orphaned-only
```

**Disable Automatic Cleanup**:
Set `CLEANUP_ENABLED = False` in `app/praat/config.py`

## Usage Example

### 1. Upload Audio
```bash
curl -X POST http://localhost:8000/api/praat/uploads \
  -F "file=@audio.mp3" \
  -F "normalize=true"
```

Response:
```json
{
  "upload_id": "uuid",
  "source_filename": "audio.mp3",
  "normalized_meta": {
    "format": "wav",
    "sample_rate": 16000,
    "channels": 1,
    "duration_s": 3.42
  }
}
```

### 2. Create Analysis Job
```bash
curl -X POST http://localhost:8000/api/praat/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "upload_id": "uuid",
    "mode": "single",
    "modules": ["basic", "pitch", "intensity", "segments"],
    "options": {
      "pitch": {"f0_min": 75, "f0_max": 600}
    }
  }'
```

Response:
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### 3. Poll Job Status
```bash
curl http://localhost:8000/api/praat/jobs/{job_id}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "running",
  "progress": 0.6,
  "stage": "pitch"
}
```

### 4. Get Result
```bash
curl http://localhost:8000/api/praat/jobs/{job_id}/result?view=full
```

## Performance

- Single mode: 2-5x real-time
- Continuous mode: 5-10x real-time
- Background processing prevents HTTP blocking
- Results cached on disk

## Limits

- Max upload size: 50 MB
- Max duration: 60 seconds
- Supported formats: WAV, MP3, M4A, WebM, OGG, FLAC, AAC

## Error Handling

Standardized error format:
```json
{
  "error": {
    "code": "PRAAT_ANALYSIS_FAILED",
    "message": "Formant extraction failed",
    "detail": {...}
  }
}
```

Error codes:
- `UPLOAD_TOO_LARGE`: File exceeds 50MB
- `AUDIO_DECODE_FAILED`: FFmpeg cannot decode
- `AUDIO_TOO_LONG`: Duration exceeds 60s
- `UNSUPPORTED_OPTION`: Invalid module or option
- `PRAAT_ANALYSIS_FAILED`: Parselmouth error
- `JOB_NOT_FOUND`: Job ID doesn't exist
- `UPLOAD_NOT_FOUND`: Upload ID doesn't exist

## Future Extensions

- WebSocket/SSE for real-time progress
- Batch processing (multiple files)
- Tone classification (map contour to categories)
- IPA transcription integration
- Export to Praat TextGrid format
- Comparison with reference recordings

## References

- Praat: https://www.fon.hum.uva.nl/praat/
- Parselmouth: https://parselmouth.readthedocs.io/
- FastAPI: https://fastapi.tiangolo.com/

## License

Part of the dialect comparison and geolinguistic analysis toolkit.
