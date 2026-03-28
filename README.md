# VTrim

**VTrim** is a lightweight, efficient video analysis and trimming tool. It automatically finds segments containing people and can **output a trimmed video instantly—without re-encoding**, preserving original quality at blazing speed.

• ⚡ Lossless • 🎥 Professional edit-ready XML • 🔍 AI-powered detection

## Features

- 🚀 **Fast Analysis**: Model caching and batch inference for 50-80% faster processing
- ✂️ **Lossless Trimming**: FFmpeg stream copy (-c copy) - no quality degradation
- 🎬 **Professional XML**: Export FCP7 XML for DaVinci Resolve/Premiere Pro
- 🤖 **AI Detection**: YOLOv8 human detection with configurable sensitivity
- ⚙️ **Flexible Configuration**: Centralized config for easy customization
- 📊 **JSON Output**: Machine-readable results for automation

## Installation

Install via pip:

```bash
pip install vtrim
```

## Quick Start

### Basic Usage

#### Analyze Video (Detect Humans)
```bash
vtrim --input video.mp4
# or use the short form:
vtrim -i video.mp4
```

Output:
```json
{"segments": [{"start": 2.3, "end": 5.8}, {"start": 10.1, "end": 14.7}]}
```

#### Trim Video Directly

```bash
vtrim --input your_video.mp4 --output output.mp4
# or use short forms:
vtrim -i your_video.mp4 -o output.mp4
```

- Uses FFmpeg stream copy (-c copy) → no re-encoding, no quality loss.
- Automatically merges nearby detections and adds padding for smooth transitions.

### Export Edit Timeline to DaVinci Resolve / Premiere Pro

Preserve the full timeline (including gaps) as an **FCP7 XML** for professional editing:

```bash
vtrim --input your_video.mp4 --export-xml timeline.xml
# or:
vtrim -i your_video.mp4 --export-xml timeline.xml
```

*Audio and video are perfectly synchronized and split per segment.*

### Advanced Examples

#### High Sensitivity Detection
```bash
vtrim --input video.mp4 \
      --conf-threshold 0.15 \
      --output sensitive_trim.mp4
```

Lower threshold = more detections (including false positives)

#### Conservative Detection with Large Padding
```bash
vtrim --input video.mp4 \
      --conf-threshold 0.4 \
      --padding 3.0 \
      --output conservative_trim.mp4
```

Higher threshold + more padding = fewer, longer segments

#### Merge All Nearby Detections
```bash
vtrim --input video.mp4 \
      --gap-tolerance 10.0 \
      --output merged_trim.mp4
```

Large gap tolerance merges nearby segments into continuous blocks

### Combined Workflow

```bash
vtrim --input your_video.mp4 \
      --output output.mp4 \
      --export-xml timeline.xml
# or use short forms for faster typing:
vtrim -i your_video.mp4 -o output.mp4 --export-xml timeline.xml
```

### Get Raw Detection Results (JSON)

Print detected time segments to `stdout` for scripting or integration:

```bash
vtrim --input meeting.mp4
```

Output:

```json
{
  "segments": [
    { "start": 2.3, "end": 5.8 },
    { "start": 10.1, "end": 14.7 }
  ]
}
```

### Programmatic Usage (Python API)

```python
from vtrim.analyzer import detect_human
from vtrim.segment_utils import merge_segments, apply_padding
from vtrim.ffmpeg_utils import cut_video_with_ffmpeg
from vtrim.xml_export import export_fcp7_xml
from vtrim import Config

# Detect humans
raw_segments = detect_human("video.mp4", conf_threshold=0.25)

# Process segments
merged = merge_segments(raw_segments, gap_tolerance=4.0)
padded = apply_padding(merged, padding=1.0)

# Cut video
cut_video_with_ffmpeg("video.mp4", padded, "output.mp4")

# Export XML
export_fcp7_xml("video.mp4", padded, "timeline.xml", video_duration=120.5)

# Access configuration
print(f"Default threshold: {Config.CONF_THRESHOLD}")
print(f"Default padding: {Config.PADDING}")
```

---

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--input`, `-i` | Required | - | Path to input video file |
| `--output`, `-o` | Optional | - | Path to save trimmed video |
| `--export-xml` | String | - | Path to export FCP7 XML |
| `--conf-threshold` | Float | 0.25 | Detection confidence (0.0-1.0) |
| `--padding` | Float | 1.0 | Seconds added before/after segments |
| `--gap-tolerance` | Float | 4.0 | Max gap to merge segments |
| `--verbose` | Flag | Off | Show detailed progress |

> 📌 **Note**: Human detection is always enabled. Just provide the input video and VTrim will automatically detect human presence.

---

## Performance

### Optimizations (v0.1.4+)

- **Model Caching**: 50-80% faster on subsequent runs (singleton pattern)
- **Batch Inference**: 20-30% faster processing (batch size = 4)
- **Dynamic Resolution**: Automatic video metadata detection
- **Enhanced Error Handling**: Better validation and error messages

### Benchmark Example

For a 10-minute video at 30 FPS:
- **Before**: ~3-4 minutes total
- **After**: ~2-2.5 minutes (with cached model)

### Configuration

All defaults are defined in `vtrim/config.py`:

```python
from vtrim import Config

# Customize settings
Config.CONF_THRESHOLD = 0.15  # Higher sensitivity
Config.PADDING = 2.0          # More padding
Config.GAP_TOLERANCE = 10.0   # Merge nearby detections
Config.SAMPLE_FPS = 2.0       # Analysis sample rate (2 FPS)
Config.BATCH_SIZE = 4         # Inference batch size
```

---

## Output Formats

### JSON Output (stdout)
Machine-readable format for scripting:

```json
{
  "segments": [
    {"start": 2.3, "end": 5.8},
    {"start": 10.1, "end": 14.7}
  ]
}
```

### FCP7 XML (DaVinci Resolve / Premiere Pro)

Compatible with:
- DaVinci Resolve
- Adobe Premiere Pro
- Final Cut Pro 7

Features:
- Full timeline (valid + invalid segments)
- Color-coded clips (blue=keep, gray=skip)
- Synchronized audio/video
- Frame-accurate timing

### Trimmed Video

- Format: MP4 (same as input)
- Codec: Unchanged (stream copy)
- Quality: Lossless (no re-encoding)

---

## Troubleshooting

### Error: "FFmpeg not found"

**Solution:** Install FFmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Error: "Input video file not found"

**Solution:** Check that the file path is correct (absolute or relative to current directory).

### Error: "No human segments detected"

**Solutions:**
1. Lower `--conf-threshold` (e.g., 0.15 for higher sensitivity)
2. Verify the video actually contains people
3. Check that `vtrim/yolov8n.pt` model file exists

### Slow Analysis

**Tips:**
- First run downloads the model (one-time delay)
- Subsequent runs are 50-80% faster (model cached)
- Reduce `Config.SAMPLE_FPS` for faster but less accurate analysis

---

## Best Practices

1. **Test with short videos first**: Verify settings before processing long videos
2. **Keep original backups**: Always preserve source files until satisfied
3. **Use verbose mode for debugging**: `vtrim --input video.mp4 --verbose`
4. **Combine outputs for flexibility**: Generate both trimmed video AND XML timeline

---

## Requirements

- Python 3.7+
- FFmpeg (must be in PATH)
- Dependencies:
  - opencv-python
  - ultralytics
  - setuptools

---

## Environment Variables

| Variable | Values | Effect |
|----------|--------|--------|
| `ANALYZER_PROGRESS_JSON` | "0" (default), "1" | Output progress as JSON to stderr |

Example:
```bash
ANALYZER_PROGRESS_JSON=1 vtrim --input video.mp4
```

---

## Project Structure

```
vtrim/
├── __init__.py          # Package initialization, exports Config
├── analyzer.py          # Human detection logic
├── cli.py              # Command-line interface
├── config.py           # Configuration settings
├── ffmpeg_utils.py     # FFmpeg video processing
├── model.py            # YOLO model loading
├── segment_utils.py    # Segment merging/padding
├── xml_export.py       # FCP7 XML export
└── yolov8n.pt          # Pre-trained YOLO model
```

---

## Notes

- The underlying model is **YOLOv8n** (PyTorch format), optimized for CPU inference.
- Video trimming uses **FFmpeg stream copy** (`-c copy`), so it's fast and lossless—no quality degradation.
- Progress updates are printed to `stderr` during analysis (every 5% for known-length videos).
- For automation, set the environment variable `ANALYZER_PROGRESS_JSON=1` to receive machine-readable progress messages on `stderr`.

---

## Documentation

- **README.md**: This file - comprehensive overview and quick start guide
- **CHANGELOG.md**: Detailed version history, optimizations, and upgrade notes

For more detailed usage examples and advanced configurations, see the inline documentation in `vtrim/config.py` and individual module docstrings.

---

## Support

- **GitHub**: https://github.com/chiaweilee/vtrim
- **Issues**: https://github.com/chiaweilee/vtrim/issues
- **License**: Apache License v2

---

## Version

Current version: **0.2.0**

See [CHANGELOG.md](CHANGELOG.md) for the latest updates and migration notes.
