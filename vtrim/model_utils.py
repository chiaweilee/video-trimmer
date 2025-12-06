import cv2
import numpy as np
from pathlib import Path
import sys
import os

INPUT_WIDTH = 640
INPUT_HEIGHT = 640
PERSON_CLASS_ID = 0

def resource_path(relative_path):
    """Get absolute path to resource, works for PyInstaller bundles."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent
    return os.path.join(base_path, relative_path)

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

def load_onnx_model(model_path):
    net = cv2.dnn.readNetFromONNX(model_path)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    return net
