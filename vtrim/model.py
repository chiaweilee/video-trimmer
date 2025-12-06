from ultralytics import YOLO

def load_yolo_model(model_name="yolov8n.pt"):
    """
    Load YOLO model using Ultralytics' built-in auto-download.
    Supports: 'yolov8n.pt', 'yolov8s.onnx', etc.
    """
    return YOLO(model_name)