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
    
    # File paths
    DEFAULT_MODEL_NAME: str = "yolov8n.pt"
