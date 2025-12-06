from pathlib import Path
from ultralytics import YOLO

def load_yolo_model(model_name="yolov8n.pt"):
    """
    Load YOLO model ONLY from the same directory as this file.
    Raises error if not found or invalid.
    """
    current_dir = Path(__file__).parent.resolve()
    model_path = current_dir / model_name

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    return YOLO(str(model_path))