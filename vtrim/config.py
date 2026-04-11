"""
Configuration settings for VTrim.
Centralizes default values and constants used throughout the application.
"""

from dataclasses import dataclass


@dataclass
class Config:
    """Default configuration for VTrim."""
    
    # Detection settings
    CONF_THRESHOLD: float = 0.25
    PADDING: float = 1.0
    GAP_TOLERANCE: float = 4.0
    
    # Video processing settings
    DEFAULT_FPS: float = 24.0
    DEFAULT_WIDTH: int = 1920
    DEFAULT_HEIGHT: int = 1080
    
    # Analysis settings
    SAMPLE_FPS: float = 2.0  # Sample video at 2 FPS for detection
    BATCH_SIZE: int = 4  # Batch size for inference
    
    # VAD (Voice Activity Detection) settings
    VAD_THRESHOLD: float = 0.5  # Confidence threshold for speech detection (0.0-1.0)
    VAD_MIN_SPEECH_DURATION: float = 0.25  # Minimum speech duration in seconds
    VAD_MIN_SILENCE_DURATION: float = 0.5  # Minimum silence duration to split segments
    VAD_SAMPLING_RATE: int = 16000  # Audio sampling rate for VAD (8000 or 16000)
    
    # File paths
    DEFAULT_MODEL_NAME: str = "yolov8n.pt"
