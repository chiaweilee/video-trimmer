# VTrim

VTrim is a lightweight, efficient video analysis and trimming tool powered by YOLOv8 object detection. It automatically scans your video files for segments containing human presence and can optionally output a trimmed version that includes only those segments—**without re-encoding**, preserving original quality and enabling ultra-fast processing.

## Installation

Install via pip:

```bash
pip install vtrim
```

### Usage

```bash
vtrim --input <video_file_path> [--detect-human] [--output <trimmed_video_path>] [other options]
```

#### Basic Command

```bash
vtrim --input input.mp4 --detect-human --output output.mp4
```

This command analyzes `input.mp4`, detects all segments with people, merges nearby detections, adds padding, and saves a trimmed version as `output.mp4` using lossless stream copy.

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

### Output

#### Standard Output (stdout)

Always prints a JSON object with detected time segments:

```json
{
  "segments": [
    { "start": 2.3, "end": 5.8 },
    { "start": 10.1, "end": 14.7 }
  ]
}
```

Each segment is in seconds.

#### Error Reporting (stderr)

If an error occurs (e.g., missing model, FFmpeg failure), a JSON error object is written to `stderr`:

```json
{
  "error": "FFmpeg is not installed or not found in PATH. Please install FFmpeg.",
  "type": "ffmpeg_error"
}
```

This enables reliable integration with scripts or parent processes (e.g., Node.js, shell pipelines).

### Examples

#### Analyze Only (No Video Output)

Print human-presence segments without generating a new video:

```bash
vtrim --input meeting.mp4 --detect-human
```

#### Adjust Sensitivity and Padding

Use a lower confidence threshold and add 1-second padding around each segment:

```bash
vtrim --input event.mp4 --detect-human --output clean.mp4 --conf-threshold 0.3 --padding 1.0
```

#### Merge Close Detections

Treat detections within 2 seconds of each other as one continuous segment:

```bash
vtrim --input interview.mp4 --detect-human --output cut.mp4 --gap-tolerance 2.0
```

#### Export to Premiere Pro / DaVinci Resolve

```bash
vtrim --input your_video.mp4 --detect-human --export-xml timeline.xml
```

You can combine this with --output to also generate a preview video:

```bash
vtrim --input interview.mp4 --detect-human \
      --output preview.mp4 \
      --export-xml interview_edit.xml
```

### Notes

- The underlying model is **YOLOv8n** (ONNX format), optimized for CPU inference.
- Video trimming uses **FFmpeg stream copy** (`-c copy`), so it’s fast and lossless—no quality degradation.
- Progress updates are printed to `stderr` during analysis (every 5% for known-length videos).
- For automation, set the environment variable `ANALYZER_PROGRESS_JSON=1` to receive machine-readable progress messages on `stderr`.
