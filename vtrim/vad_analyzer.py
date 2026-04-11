import sys
import os
import json
import tempfile
import subprocess
import numpy as np
from typing import List, Dict

try:
    import torch
    from silero_vad import load_silero_vad, get_speech_timestamps
except ImportError:
    raise ImportError(
        "Silero VAD is not installed. Please install it with: pip install silero-vad torch torchaudio onnxruntime"
    )

from .config import Config


# Global cache for VAD model instance
_vad_model_cache = None


def get_vad_model():
    """Get or load the Silero VAD model (singleton pattern)."""
    global _vad_model_cache
    if _vad_model_cache is None:
        _vad_model_cache = load_silero_vad()
    return _vad_model_cache


def extract_audio_from_video(video_path: str, sample_rate: int = 16000) -> np.ndarray:
    """
    Extract audio from video file using FFmpeg and convert to numpy array.
    
    Args:
        video_path: Path to input video file
        sample_rate: Target sample rate (8000 or 16000)
    
    Returns:
        Numpy array of audio samples (float32, normalized to [-1, 1])
    """
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', str(sample_rate),
            '-ac', '1',
            tmp_path
        ]
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")
        
        import wave
        with wave.open(tmp_path, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            framerate = wf.getframerate()
            
            raw_data = wf.readframes(n_frames)
            audio_data = np.frombuffer(raw_data, dtype=np.int16)
            
            if n_channels == 2:
                audio_data = audio_data.reshape(-1, 2).mean(axis=1)
            
            audio_float = audio_data.astype(np.float32) / 32768.0
        
        return audio_float
    
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def detect_speech(video_path: str, 
                  vad_threshold: float = Config.VAD_THRESHOLD,
                  min_speech_duration: float = Config.VAD_MIN_SPEECH_DURATION,
                  min_silence_duration: float = Config.VAD_MIN_SILENCE_DURATION,
                  sampling_rate: int = Config.VAD_SAMPLING_RATE) -> List[Dict[str, float]]:
    """
    Detect speech segments in video using Silero VAD.
    
    Args:
        video_path: Path to input video file
        vad_threshold: Confidence threshold for speech detection (0.0-1.0)
        min_speech_duration: Minimum speech duration in seconds
        min_silence_duration: Minimum silence duration to split segments
        sampling_rate: Audio sampling rate (8000 or 16000)
    
    Returns:
        List of segments with "start" and "end" time (in seconds)
    """
    model = get_vad_model()
    
    use_json_progress = os.getenv("ANALYZER_PROGRESS_JSON", "0") == "1"
    
    if not use_json_progress:
        sys.stderr.write("[VAD] Extracting audio from video...\n")
        sys.stderr.flush()
    
    audio_data = extract_audio_from_video(video_path, sample_rate=sampling_rate)
    
    if not use_json_progress:
        sys.stderr.write(f"[VAD] Running speech detection on {len(audio_data)} samples...\n")
        sys.stderr.flush()
    
    speech_timestamps = get_speech_timestamps(
        audio_data,
        model,
        threshold=vad_threshold,
        min_speech_duration_ms=int(min_speech_duration * 1000),
        min_silence_duration_ms=int(min_silence_duration * 1000),
        sampling_rate=sampling_rate,
        return_seconds=True
    )
    
    segments = []
    for ts in speech_timestamps:
        segments.append({
            "start": float(ts['start']),
            "end": float(ts['end'])
        })
    
    if not use_json_progress:
        sys.stderr.write(f"[VAD] Detected {len(segments)} speech segment(s)\n")
        sys.stderr.flush()
    
    return segments
