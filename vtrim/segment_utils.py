def merge_segments(segments, gap_tolerance=1.0):
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
    padded = []
    for seg in segments:
        start = max(0.0, seg["start"] - padding)
        end = seg["end"] + padding
        if video_duration is not None:
            end = min(end, video_duration)
        padded.append({"start": start, "end": end})
    return padded

def align_to_next_keyframe(t, keyframes):
    """返回 >= t 的最小关键帧时间"""
    for kf in keyframes:
        if kf >= t:
            return kf
    return t  # fallback
