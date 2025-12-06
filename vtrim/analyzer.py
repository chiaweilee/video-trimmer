import cv2
import sys
import os
import json
from .model import load_yolo_model

def detect_human(video_path, conf_threshold=0.5):
    """
    Detect human presence in video using a pre-loaded YOLO model.
    
    Args:
        video_path (str): Path to input video
        model: Ultralytics YOLO model instance (e.g., YOLO("yolov8n.pt"))
        conf_threshold (float): Confidence threshold for detection
    
    Returns:
        List[dict]: List of segments with "start" and "end" time (in seconds)
    """
    model = load_yolo_model()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 30.0
    if total_frames <= 0:
        total_frames = None

    # Sample at 2 FPS
    frame_interval = max(1, int(round(fps / 2)))
    segments = []
    frame_idx = 0
    last_reported_percent = -1

    use_json_progress = os.getenv("ANALYZER_PROGRESS_JSON", "0") == "1"

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            # ✅ Use Ultralytics YOLO for inference
            # Set verbose=False to suppress per-frame logs
            results = model(frame, conf=conf_threshold, classes=[0], verbose=False)
            
            # Check if any person (class 0) is detected
            if len(results[0].boxes) > 0:
                t = frame_idx / fps
                segments.append({"start": t, "end": t})

        # Progress reporting (unchanged)
        if total_frames is not None and total_frames > 0:
            current_percent = min(100, int(round((frame_idx / total_frames) * 100)))
            if current_percent > last_reported_percent:
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