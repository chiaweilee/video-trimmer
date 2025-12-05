import argparse
import sys
import os
import json
import cv2
import numpy as np
import subprocess
import tempfile
from pathlib import Path

# YOLOv8 input size
INPUT_WIDTH = 640
INPUT_HEIGHT = 640
PERSON_CLASS_ID = 0  # Class ID for 'person' in YOLOv8

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    shape = img.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img

def resource_path(relative_path):
    """Get absolute path to resource, works for PyInstaller bundles."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent
    return os.path.join(base_path, relative_path)

def load_onnx_model(model_path):
    net = cv2.dnn.readNetFromONNX(model_path)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    return net

def preprocess(frame):
    input_img = letterbox(frame, (INPUT_WIDTH, INPUT_HEIGHT))
    input_img = input_img.astype(np.float32) / 255.0
    input_img = input_img.transpose(2, 0, 1)
    input_img = np.expand_dims(input_img, axis=0)
    return input_img

def postprocess(outputs, conf_threshold=0.5):
    outputs = np.squeeze(outputs).T
    for row in outputs:
        class_scores = row[4:]
        max_score = np.max(class_scores)
        if max_score >= conf_threshold:
            class_id = np.argmax(class_scores)
            if class_id == PERSON_CLASS_ID:
                return True
    return False

def detect_human(video_path, model_path="yolov8n.onnx", conf_threshold=0.5):
    net = load_onnx_model(model_path)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 30.0
    if total_frames <= 0:
        total_frames = None

    frame_interval = max(1, int(round(fps)))
    segments = []
    frame_idx = 0
    last_reported_percent = -1

    use_json_progress = os.getenv("ANALYZER_PROGRESS_JSON", "0") == "1"

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            input_blob = preprocess(frame)
            net.setInput(input_blob)
            outputs = net.forward()
            if postprocess(outputs, conf_threshold=conf_threshold):
                t_start = frame_idx / fps
                t_end = (frame_idx + frame_interval) / fps
                segments.append({"start": t_start, "end": t_end})

        if total_frames is not None and total_frames > 0:
            current_percent = int((frame_idx / total_frames) * 100)
            if current_percent != last_reported_percent and current_percent % 5 == 0:
                if use_json_progress:
                    msg = json.dumps({
                        "type": "progress",
                        "percent": current_percent,
                        "frames": frame_idx,
                        "total": total_frames
                    })
                    sys.stderr.write(msg + "\n")
                else:
                    sys.stderr.write(f"\r[Progress] {current_percent}% ({frame_idx}/{total_frames} frames)")
                sys.stderr.flush()
                last_reported_percent = current_percent
        else:
            if frame_idx % 1000 == 0:
                if use_json_progress:
                    msg = json.dumps({
                        "type": "progress",
                        "frames_processed": frame_idx
                    })
                    sys.stderr.write(msg + "\n")
                else:
                    sys.stderr.write(f"\r[Processed] {frame_idx} frames")
                sys.stderr.flush()

        frame_idx += 1

    cap.release()
    if not use_json_progress:
        sys.stderr.write("\n")
    sys.stderr.flush()
    return segments

def merge_segments(segments, gap_tolerance=1.0):
    if not segments:
        return []
    segments = sorted(segments, key=lambda x: x["start"])
    merged = [segments[0].copy()]
    for seg in segments[1:]:
        last = merged[-1]
        if seg["start"] <= last["end"] + gap_tolerance:
            last["end"] = max(last["end"], seg["end"])
        else:
            merged.append(seg.copy())
    return merged

def apply_padding(segments, padding=0.5, video_duration=None):
    padded = []
    for seg in segments:
        start = max(0.0, seg["start"] - padding)
        end = seg["end"] + padding
        if video_duration is not None:
            end = min(end, video_duration)
        padded.append({"start": start, "end": end})
    return padded

def cut_video_with_ffmpeg(input_path, segments, output_path):
    """
    Use FFmpeg to losslessly cut and concatenate segments.
    Uses stream copy (-c copy) for speed and quality.
    """
    if not segments:
        # If no segments, create empty output or skip?
        # Here we create a 0-byte file? Better: warn and exit?
        raise ValueError("No human segments detected. Nothing to output.")

    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("FFmpeg is not installed or not found in PATH. Please install FFmpeg.")

    with tempfile.TemporaryDirectory() as tmpdir:
        segment_files = []
        for i, seg in enumerate(segments):
            seg_file = os.path.join(tmpdir, f"seg_{i:04d}.mp4")
            start = seg["start"]
            duration = seg["end"] - seg["start"]
            if duration <= 0:
                continue
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(start),
                "-i", input_path,
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                seg_file
            ]
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed on segment {i}: {result.stderr}")
            if os.path.exists(seg_file) and os.path.getsize(seg_file) > 0:
                segment_files.append(seg_file)

        if not segment_files:
            raise RuntimeError("All segments resulted in empty files. Cannot produce output.")

        # Create concat list
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for seg_file in segment_files:
                # Escape backslashes and single quotes for FFmpeg
                abs_path = os.path.abspath(seg_file).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        # Concatenate
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")

def main():
    parser = argparse.ArgumentParser(
        description="Analyze a video file to detect segments containing human presence using YOLOv8, optionally output a trimmed video."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input video file (e.g., /path/to/video.mp4)."
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Path to save the trimmed output video (lossless cut using FFmpeg). If not provided, only JSON is printed."
    )
    parser.add_argument(
        "--detectHuman",
        action="store_true",
        help="Enable human detection. If omitted, no analysis is performed and an empty segment list is returned."
    )
    parser.add_argument(
        "--confThreshold",
        type=float,
        default=0.5,
        help="Confidence threshold for person detection (range: 0.0–1.0). Lower values increase sensitivity but may raise false positives. Default: 0.5."
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.5,
        help="Padding in seconds added to the start and end of each detected segment to ensure context is preserved. Default: 0.5 seconds."
    )
    parser.add_argument(
        "--gapTolerance",
        type=float,
        default=1.0,
        help="Maximum gap (in seconds) between adjacent detections to be merged into a single continuous segment. Default: 1.0 second."
    )
    args = parser.parse_args()

    video_path = args.input
    output_path = args.output
    segments = []

    if args.detectHuman:
        model_path = "yolov8n.onnx"
        if not os.path.isabs(model_path) and not os.path.exists(model_path):
            model_path = resource_path(model_path)
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at: {model_path}")

        conf_threshold = args.confThreshold
        padding = args.padding
        gap_tolerance = args.gapTolerance

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = frame_count / fps if fps > 0 else float('inf')
        cap.release()

        raw_segments = detect_human(video_path, model_path=model_path, conf_threshold=conf_threshold)
        merged = merge_segments(raw_segments, gap_tolerance=gap_tolerance)
        segments = apply_padding(merged, padding=padding, video_duration=video_duration)

    # Always output JSON to stdout (for compatibility)
    print(json.dumps({"segments": segments}, indent=None))

    # If --output is specified, generate trimmed video
    if output_path:
        if not segments:
            error_msg = "No human segments detected. Output video will not be created."
            print(json.dumps({"error": error_msg}), file=sys.stderr)
            sys.exit(1)
        try:
            cut_video_with_ffmpeg(video_path, segments, output_path)
            # Optional: log success to stderr (non-JSON, safe)
            sys.stderr.write(f"[Info] Trimmed video saved to: {output_path}\n")
            sys.stderr.flush()
        except Exception as e:
            error_out = {
                "error": str(e),
                "type": "ffmpeg_error"
            }
            print(json.dumps(error_out), file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_out = {
            "error": str(e),
            "type": "runtime_error"
        }
        print(json.dumps(error_out), file=sys.stderr)
        sys.exit(1)