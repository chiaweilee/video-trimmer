from ultralytics import YOLO, settings
from pathlib import Path

def load_yolo_model(model_name="yolov8n.pt"):
    """
    Load YOLO model using Ultralytics' built-in auto-download.
    Supports: 'yolov8n.pt', 'yolov8s.onnx', etc.
    """
    cache_dir = Path.home() / ".cache" / "vtrim"
    cache_dir.mkdir(parents=True, exist_ok=True)
    settings.update({"weights_dir": str(cache_dir)})
    return YOLO(model_name)