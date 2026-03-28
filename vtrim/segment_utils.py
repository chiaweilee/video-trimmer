import bisect

def merge_segments(segments, gap_tolerance=1.0):
    """
    Merge overlapping or nearby segments into continuous blocks.
    
    Args:
        segments: List of {"start": float, "end": float} dicts
        gap_tolerance: Maximum gap in seconds between segments to merge
    
    Returns:
        List of merged segments
    """
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
    """
    Apply temporal padding to segments while respecting video boundaries.
    
    Args:
        segments: List of {"start": float, "end": float} dicts
        padding: Seconds to add before and after each segment
        video_duration: Total video duration (optional boundary)
    
    Returns:
        List of padded segments
    """
    if not segments:
        return []
    
    padded = []
    for seg in segments:
        start = max(0.0, seg["start"] - padding)
        end = seg["end"] + padding
        if video_duration is not None:
            end = min(end, video_duration)
        
        # Ensure segment is valid (start < end)
        if start < end:
            padded.append({"start": start, "end": end})
    return padded

def align_to_next_keyframe(t, keyframes):
    """
    Find the smallest keyframe timestamp >= t.
    
    Args:
        t: Target timestamp in seconds
        keyframes: Sorted list of keyframe timestamps
    
    Returns:
        Aligned keyframe timestamp or original t if no match
    """
    if not keyframes:
        return t
    
    idx = bisect.bisect_left(keyframes, t)
    if idx < len(keyframes):
        return keyframes[idx]
    return t
