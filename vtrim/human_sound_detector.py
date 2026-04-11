import sys
import os
import tempfile
import subprocess
import numpy as np
from typing import List, Dict

try:
    import tensorflow as tf
    import tensorflow_hub as hub
except ImportError:
    raise ImportError(
        "TensorFlow and TensorFlow Hub are required for human sound detection. "
        "Please install: pip install tensorflow tensorflow-hub"
    )

from .config import Config


# Global cache for YAMNet model
_yamnet_model_cache = None

# Human sound categories from AudioSet ontology (indices)
# Source: https://research.google.com/audioset/ontology/index.html
HUMAN_SOUND_CATEGORIES = {
    # Speech (0-5)
    0: "Speech",
    1: "Child speech, kid speaking",
    2: "Conversation",
    3: "Narration, monologue",
    4: "Babbling",
    5: "Speech synthesizer",
    
    # Shouting and screaming (6-12)
    6: "Shout",
    7: "Bellow",
    8: "Whoop",
    9: "Yell",
    10: "Cheer",
    11: "Screaming",
    12: "Whispering",
    
    # Laughter (13-18)
    13: "Laughter",
    14: "Baby laughter",
    15: "Giggle",
    16: "Snicker",
    17: "Belly laugh",
    18: "Chuckle, chortle",
    
    # Crying and sobbing (19-23)
    19: "Crying, sobbing",
    20: "Baby cry, infant cry",
    21: "Whimper",
    22: "Wail, moan",
    23: "Sigh",
    
    # Singing (24-32)
    24: "Singing",
    25: "Choir",
    26: "Yodeling",
    27: "Chant",
    28: "Mantra",
    29: "Male singing",
    30: "Female singing",
    31: "Child singing",
    32: "Synthetic singing",
    
    # Body sounds (33-45)
    33: "Rapping",
    34: "Humming",
    35: "Groan",
    36: "Grunt",
    37: "Whistling",
    38: "Breathing",
    39: "Wheeze",
    40: "Snoring",
    41: "Gasp",
    42: "Pant",
    43: "Sniff",
    44: "Cough",
    45: "Throat clearing",
}


def get_yamnet_model():
    """Get or load the YAMNet model (singleton pattern)."""
    global _yamnet_model_cache
    if _yamnet_model_cache is None:
        print("Loading YAMNet model...", file=sys.stderr)
        _yamnet_model_cache = hub.load('https://tfhub.dev/google/yamnet/1')
        print("YAMNet model loaded successfully", file=sys.stderr)
    return _yamnet_model_cache


def extract_audio_from_video(video_path: str, sample_rate: int = 16000) -> np.ndarray:
    """
    Extract audio from video file using FFmpeg.
    
    Args:
        video_path: Path to input video file
        sample_rate: Target sample rate (16000 for YAMNet)
    
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
            
            raw_data = wf.readframes(n_frames)
            audio_data = np.frombuffer(raw_data, dtype=np.int16)
            
            if n_channels == 2:
                audio_data = audio_data.reshape(-1, 2).mean(axis=1)
            
            audio_float = audio_data.astype(np.float32) / 32768.0
        
        return audio_float
    
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def detect_human_sounds(video_path: str, 
                       confidence_threshold: float = 0.3,
                       min_segment_duration: float = 0.5,
                       sampling_rate: int = 16000) -> List[Dict[str, float]]:
    """
    Detect human sounds (speech, scream, cry, laugh, etc.) in video using YAMNet.
    
    Args:
        video_path: Path to input video file
        confidence_threshold: Minimum confidence score (0.0-1.0)
        min_segment_duration: Minimum segment duration in seconds
        sampling_rate: Audio sampling rate (16000 for YAMNet)
    
    Returns:
        List of segments with "start" and "end" time (in seconds)
    """
    model = get_yamnet_model()
    
    use_json_progress = os.getenv("ANALYZER_PROGRESS_JSON", "0") == "1"
    
    if not use_json_progress:
        sys.stderr.write("[HumanSound] Extracting audio from video...\n")
        sys.stderr.flush()
    
    audio_data = extract_audio_from_video(video_path, sample_rate=sampling_rate)
    
    if not use_json_progress:
        sys.stderr.write(f"[HumanSound] Running human sound detection on {len(audio_data)} samples...\n")
        sys.stderr.flush()
    
    # YAMNet expects 16kHz audio
    # Process audio in chunks (YAMNet works with ~0.975 second windows)
    window_size = int(sampling_rate * 0.975)  # ~975ms windows
    hop_size = int(sampling_rate * 0.48)  # ~480ms hop (50% overlap)
    
    human_sound_timestamps = []
    total_windows = max(1, (len(audio_data) - window_size) // hop_size + 1)
    
    for i in range(0, len(audio_data) - window_size + 1, hop_size):
        window = audio_data[i:i + window_size]
        
        if len(window) < window_size:
            break
        
        # Run YAMNet inference
        scores, embeddings, spectrogram = model(window)
        scores = scores.numpy()  # Shape: (num_classes,)
        
        # Check if any human sound category has high confidence
        max_human_score = 0.0
        detected_category = None
        
        for class_idx in HUMAN_SOUND_CATEGORIES.keys():
            if class_idx < len(scores):
                score = scores[class_idx]
                if score > max_human_score:
                    max_human_score = score
                    detected_category = HUMAN_SOUND_CATEGORIES[class_idx]
        
        # If confidence exceeds threshold, mark this window as human sound
        if max_human_score >= confidence_threshold:
            start_time = i / sampling_rate
            end_time = (i + window_size) / sampling_rate
            human_sound_timestamps.append({
                'start': start_time,
                'end': end_time,
                'category': detected_category,
                'confidence': float(max_human_score)
            })
        
        # Progress reporting
        current_window = i // hop_size
        if current_window % 100 == 0 and not use_json_progress:
            percent = min(100, int((current_window / total_windows) * 100))
            sys.stderr.write(f"\r[HumanSound] Processing: {percent}%")
            sys.stderr.flush()
    
    if not use_json_progress:
        sys.stderr.write("\n")
        sys.stderr.flush()
    
    # Merge nearby timestamps into segments
    segments = merge_human_sound_segments(human_sound_timestamps, min_segment_duration)
    
    if not use_json_progress:
        sys.stderr.write(f"[HumanSound] Detected {len(segments)} human sound segment(s)\n")
        sys.stderr.flush()
    
    return segments


def merge_human_sound_segments(timestamps: List[Dict], min_duration: float) -> List[Dict[str, float]]:
    """
    Merge nearby human sound detections into continuous segments.
    
    Args:
        timestamps: List of detection timestamps with start/end times
        min_duration: Minimum segment duration in seconds
    
    Returns:
        List of merged segments
    """
    if not timestamps:
        return []
    
    # Sort by start time
    timestamps.sort(key=lambda x: x['start'])
    
    merged = []
    current_start = timestamps[0]['start']
    current_end = timestamps[0]['end']
    
    for ts in timestamps[1:]:
        # If gap is small (< 0.5s), merge
        if ts['start'] - current_end < 0.5:
            current_end = max(current_end, ts['end'])
        else:
            # Save current segment if it meets minimum duration
            segment_duration = current_end - current_start
            if segment_duration >= min_duration:
                merged.append({
                    'start': current_start,
                    'end': current_end
                })
            current_start = ts['start']
            current_end = ts['end']
    
    # Don't forget the last segment
    segment_duration = current_end - current_start
    if segment_duration >= min_duration:
        merged.append({
            'start': current_start,
            'end': current_end
        })
    
    return merged
