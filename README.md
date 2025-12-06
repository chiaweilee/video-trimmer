# VTrim

**VTrim** is a lightweight, efficient video analysis and trimming tool. It automatically finds segments containing people and can **output a trimmed video instantly—without re-encoding**, preserving original quality at blazing speed.

• ⚡ Lossless • 🎥 Professional edit-ready XML

## Installation

Install via pip:

```bash
pip install vtrim
```

## Quick Start

### Trim Video Directly

```bash
vtrim --input your_video.mp4 --detect-human --output output.mp4
```

- Uses FFmpeg stream copy (-c copy) → no re-encoding, no quality loss.
- Automatically merges nearby detections and adds padding for smooth transitions.

### Export Edit Timeline to DaVinci Resolve / Premiere Pro

Preserve the full timeline (including gaps) as an **FCP7 XML** for professional editing:

```bash
vtrim --input your_video.mp4 --detect-human --export-xml timeline.xml
```

*Audio and video are perfectly synchronized and split per segment.*

You can **combine both outputs**:

```bash
vtrim --input your_video.mp4 \
      --detect-human \
      --output output.mp4 \
      --export-xml timeline.xml
```

### Get Raw Detection Results (JSON)

Print detected time segments to `stdout` for scripting or integration:

```bash
vtrim --input meeting.mp4 --detect-human
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

Segments are in **seconds**, ready for automation (e.g., with Python, Node.js, or shell scripts).

#### Full Option Reference

| Parameter          | Required | Description                                                                                                                              |
| ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `--input`          | Yes      | Path to the input video file (e.g., `video.mp4`).                                                                                        |
| `--detect-human`   | No\*     | Enable human detection. If omitted, the tool returns an empty segment list and does nothing. (Required if you want analysis or trimming) |
| `--output`         | No       | Path to save the trimmed video (e.g., `trimmed.mp4`). If not provided, only JSON results are printed to stdout.                          |
| `--export-xml`     | No       | Path to save the FCP7 XML.                                                                                                               |
| `--conf-threshold` | No       | Confidence threshold for person detection (0.0–1.0). Lower = more sensitive. Default: `0.5`.                                             |
| `--padding`        | No       | Seconds of padding added before/after each detected segment. Default: `0.5`.                                                             |
| `--gap-tolerance`  | No       | Maximum gap (in seconds) between detections to merge into one segment. Default: `1.0`.                                                   |

> 📌 **Important**: `--detect-human` must be specified to perform any analysis. Without it, the output will always be `{"segments": []}`.

### Notes

- The underlying model is **YOLOv8n** (ONNX format), optimized for CPU inference.
- Video trimming uses **FFmpeg stream copy** (`-c copy`), so it’s fast and lossless—no quality degradation.
- Progress updates are printed to `stderr` during analysis (every 5% for known-length videos).
- For automation, set the environment variable `ANALYZER_PROGRESS_JSON=1` to receive machine-readable progress messages on `stderr`.
