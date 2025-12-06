import subprocess
import tempfile
import os
import bisect

def get_keyframe_timestamps(video_path):
    """
    使用 ffprobe 获取视频所有关键帧（I-frame）的时间戳（秒），返回排序列表。
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=print_section=0",
        video_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")

    keyframes = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        pts_str, flags = parts[0], parts[1]
        try:
            pts = float(pts_str)
            if "K" in flags:  # 关键帧标志
                keyframes.append(pts)
        except ValueError:
            continue
    return sorted(set(keyframes))  # 去重并排序

def cut_video_with_ffmpeg(input_path, segments, output_path):
    """
    Use FFmpeg to losslessly cut and concatenate segments.
    Uses stream copy (-c copy) for speed and quality.
    """
    if not segments:
        # If no segments, create empty output or skip?
        # Here we create a 0-byte file? Better: warn and exit?
        raise ValueError("No human segments detected. Nothing to output.")

    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("FFmpeg is not installed or not found in PATH. Please install FFmpeg.")
    
    keyframes = get_keyframe_timestamps(input_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        segment_files = []
        for i, seg in enumerate(segments):
            seg_file = os.path.join(tmpdir, f"seg_{i:04d}.mp4")
            start = seg["start"]
            end = seg["end"]
            duration = end - start
            if duration <= 0:
                continue

            idx = bisect.bisect_left(keyframes, start)
            if idx < len(keyframes):
                aligned_start = keyframes[idx]
                # 如果对齐后起始时间 >= end，跳过该 segment
                if aligned_start >= end:
                    continue
                actual_duration = end - aligned_start
            else:
                # 没有后续关键帧？用原始 start（fallback）
                aligned_start = start
                actual_duration = duration

            if actual_duration <= 0:
                continue

            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(aligned_start),
                "-i", input_path,
                "-t", str(actual_duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                seg_file
            ]
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed on segment {i}: {result.stderr}")
            if os.path.exists(seg_file) and os.path.getsize(seg_file) > 0:
                segment_files.append(seg_file)

        if not segment_files:
            raise RuntimeError("All segments resulted in empty files. Cannot produce output.")

        # Create concat list
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for seg_file in segment_files:
                # Escape backslashes and single quotes for FFmpeg
                abs_path = os.path.abspath(seg_file).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        # Concatenate
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")
