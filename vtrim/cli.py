import argparse
import sys
import os
import json
import cv2
import numpy as np
import subprocess
import tempfile
import bisect
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

# YOLOv8 input size
INPUT_WIDTH = 640
INPUT_HEIGHT = 640
PERSON_CLASS_ID = 0  # Class ID for 'person' in YOLOv8

def get_video_total_frames(video_path, fps):
    """获取视频总帧数（fallback 到估算）"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'json', video_path
        ], capture_output=True, text=True, check=True)
        duration_sec = float(json.loads(result.stdout)['format']['duration'])
        return int(round(duration_sec * fps))
    except Exception:
        # fallback: assume 60s if ffprobe fails
        return int(round(60.0 * fps))


def export_fcp7_xml(input_video_path, segments, output_xml_path, fps=24.0):
    """
    导出兼容 DaVinci Resolve 的 FCP7 XML。
    
    参数:
        input_video_path (str): 原始视频路径（如 "3.mp4"）
        segments (list): [{"start": 1.2, "end": 4.5}, ...] 单位：秒
        output_xml_path (str): 输出 XML 路径（如 "edit.xml"）
        fps (float): 项目帧率，默认 24.0
    """
    input_video_path = os.path.abspath(input_video_path)
    video_name = os.path.basename(input_video_path)
    file_id = f"{video_name} file"

    # 获取原始视频总帧数（用于 <file><duration>）
    media_total_frames = get_video_total_frames(input_video_path, fps)

    # 构建时间线：计算每个 clip 的 in/out/start/end（单位：帧）
    clip_items = []
    current_timeline_frame = 0

    for seg in segments:
        in_frame = int(round(seg["start"] * fps))
        out_frame = int(round(seg["end"] * fps))
        clip_duration_frames = out_frame - in_frame

        start_frame = current_timeline_frame
        end_frame = start_frame + clip_duration_frames

        clip_items.append({
            "in": in_frame,
            "out": out_frame,
            "start": start_frame,
            "end": end_frame,
            "duration": clip_duration_frames,
        })
        current_timeline_frame = end_frame

    sequence_duration = current_timeline_frame  # ✅ 关键修复：等于最后一个 clip 的 end

    # --- 开始构建 XML ---
    xmeml = ET.Element("xmeml", version="5")
    seq = ET.SubElement(xmeml, "sequence")
    ET.SubElement(seq, "name").text = "VTrim Auto-Edit"
    ET.SubElement(seq, "duration").text = str(sequence_duration)  # ✅ 正确值！

    rate = ET.SubElement(seq, "rate")
    ET.SubElement(rate, "timebase").text = str(int(round(fps)))
    ET.SubElement(rate, "ntsc").text = "FALSE"

    ET.SubElement(seq, "in").text = "-1"
    ET.SubElement(seq, "out").text = "-1"

    # Timecode
    tc = ET.SubElement(seq, "timecode")
    ET.SubElement(tc, "string").text = "01:00:00:00"
    ET.SubElement(tc, "frame").text = "86400"
    ET.SubElement(tc, "displayformat").text = "NDF"
    tc_rate = ET.SubElement(tc, "rate")
    ET.SubElement(tc_rate, "timebase").text = str(int(round(fps)))
    ET.SubElement(tc_rate, "ntsc").text = "FALSE"

    # Media
    media = ET.SubElement(seq, "media")

    # === Video Track ===
    video = ET.SubElement(media, "video")
    track = ET.SubElement(video, "track")

    for i, clip in enumerate(clip_items):
        clip_id = f"{video_name} {i}"
        ci = ET.SubElement(track, "clipitem", id=clip_id)
        ET.SubElement(ci, "name").text = video_name
        ET.SubElement(ci, "duration").text = str(clip["duration"])

        cr = ET.SubElement(ci, "rate")
        ET.SubElement(cr, "timebase").text = str(int(round(fps)))
        ET.SubElement(cr, "ntsc").text = "FALSE"

        ET.SubElement(ci, "start").text = str(clip["start"])
        ET.SubElement(ci, "end").text = str(clip["end"])
        ET.SubElement(ci, "in").text = str(clip["in"])
        ET.SubElement(ci, "out").text = str(clip["out"])
        ET.SubElement(ci, "enabled").text = "TRUE"

        if i == 0:
            # 定义完整 file（仅第一个 clip）
            file_elem = ET.SubElement(ci, "file", id=file_id)
            ET.SubElement(file_elem, "name").text = video_name
            ET.SubElement(file_elem, "pathurl").text = f"file://{input_video_path.replace(os.sep, '/')}"
            ET.SubElement(file_elem, "duration").text = str(media_total_frames)

            fr = ET.SubElement(file_elem, "rate")
            ET.SubElement(fr, "timebase").text = str(int(round(fps)))
            ET.SubElement(fr, "ntsc").text = "FALSE"

            ft = ET.SubElement(file_elem, "timecode")
            ET.SubElement(ft, "string").text = "00:00:00:00"
            ET.SubElement(ft, "displayformat").text = "NDF"
            ftr = ET.SubElement(ft, "rate")
            ET.SubElement(ftr, "timebase").text = str(int(round(fps)))
            ET.SubElement(ftr, "ntsc").text = "FALSE"

            # Media characteristics (关键!)
            media_info = ET.SubElement(file_elem, "media")
            vid_info = ET.SubElement(media_info, "video")
            ET.SubElement(vid_info, "duration").text = str(media_total_frames)
            sc = ET.SubElement(vid_info, "samplecharacteristics")
            ET.SubElement(sc, "width").text = "1920"
            ET.SubElement(sc, "height").text = "1080"

            aud_info = ET.SubElement(media_info, "audio")
            ET.SubElement(aud_info, "channelcount").text = "2"
        else:
            # 复用 file
            ET.SubElement(ci, "file", id=file_id)

        # Link
        link = ET.SubElement(ci, "link")
        ET.SubElement(link, "linkclipref").text = clip_id

    # Format (Resolve 必需!)
    fmt = ET.SubElement(video, "format")
    sc_fmt = ET.SubElement(fmt, "samplecharacteristics")
    ET.SubElement(sc_fmt, "width").text = "1920"
    ET.SubElement(sc_fmt, "height").text = "1080"
    ET.SubElement(sc_fmt, "pixelaspectratio").text = "square"
    fmt_rate = ET.SubElement(sc_fmt, "rate")
    ET.SubElement(fmt_rate, "timebase").text = str(int(round(fps)))
    ET.SubElement(fmt_rate, "ntsc").text = "FALSE"

    # === Audio Track (提升兼容性) ===
    audio = ET.SubElement(media, "audio")
    audio_track = ET.SubElement(audio, "track")

    if clip_items:
        audio_clip = ET.SubElement(audio_track, "clipitem", id=f"{video_name} audio")
        ET.SubElement(audio_clip, "name").text = video_name
        ET.SubElement(audio_clip, "duration").text = str(sequence_duration)

        ar = ET.SubElement(audio_clip, "rate")
        ET.SubElement(ar, "timebase").text = str(int(round(fps)))
        ET.SubElement(ar, "ntsc").text = "FALSE"

        ET.SubElement(audio_clip, "start").text = "0"
        ET.SubElement(audio_clip, "end").text = str(sequence_duration)
        ET.SubElement(audio_clip, "in").text = "0"
        ET.SubElement(audio_clip, "out").text = str(sequence_duration)
        ET.SubElement(audio_clip, "enabled").text = "TRUE"

        ET.SubElement(audio_clip, "file", id=file_id)

        st = ET.SubElement(audio_clip, "sourcetrack")
        ET.SubElement(st, "mediatype").text = "audio"
        ET.SubElement(st, "trackindex").text = "1"

        # Link to first video clip
        ET.SubElement(audio_clip, "link").text = f"{video_name} 0"
        ET.SubElement(audio_clip, "link").text = f"{video_name} audio"

    # --- 写入文件 ---
    rough_string = ET.tostring(xmeml, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # 清理空行
    lines = [line for line in pretty_xml.splitlines() if line.strip()]
    with open(output_xml_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ Exported FCP7 XML to: {output_xml_path}")
    print(f"   Sequence duration: {sequence_duration} frames @ {fps} fps")

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

def get_keyframe_times(video_path):
    """获取视频中所有关键帧（I-frame）的时间戳（秒）"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=print_section=0",
        video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    keyframes = []
    for line in result.stdout.strip().splitlines():
        pts, flags = line.split(",")
        if "K" in flags:  # Keyframe flag
            keyframes.append(float(pts))
    return sorted(keyframes)

def align_to_next_keyframe(t, keyframes):
    """返回 >= t 的最小关键帧时间"""
    for kf in keyframes:
        if kf >= t:
            return kf
    return t  # fallback

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

def resource_path(relative_path):
    """Get absolute path to resource, works for PyInstaller bundles."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent
    return os.path.join(base_path, relative_path)

def load_onnx_model(model_path):
    net = cv2.dnn.readNetFromONNX(model_path)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    return net

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

def detect_human(video_path, model_path="yolov8s.onnx", conf_threshold=0.5):
    net = load_onnx_model(model_path)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if fps <= 0:
        fps = 30.0
    if total_frames <= 0:
        total_frames = None

    # 2 FPS
    frame_interval = max(1, int(round(fps / 2)))
    segments = []
    frame_idx = 0
    last_reported_percent = -1

    use_json_progress = os.getenv("ANALYZER_PROGRESS_JSON", "0") == "1"

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            input_blob = preprocess(frame)
            net.setInput(input_blob)
            outputs = net.forward()
            if postprocess(outputs, conf_threshold=conf_threshold):
                t = frame_idx / fps
                segments.append({"start": t, "end": t})

        if total_frames is not None and total_frames > 0:
            current_percent = int((frame_idx / total_frames) * 100)
            if current_percent != last_reported_percent and current_percent % 5 == 0:
                if use_json_progress:
                    msg = json.dumps({
                        "type": "progress",
                        "percent": current_percent,
                        "frames": frame_idx,
                        "total": total_frames
                    })
                    sys.stderr.write(msg + "\n")
                else:
                    sys.stderr.write(f"\r[Progress] {current_percent}% ({frame_idx}/{total_frames} frames)")
                sys.stderr.flush()
                last_reported_percent = current_percent
        else:
            if frame_idx % 1000 == 0:
                if use_json_progress:
                    msg = json.dumps({
                        "type": "progress",
                        "frames_processed": frame_idx
                    })
                    sys.stderr.write(msg + "\n")
                else:
                    sys.stderr.write(f"\r[Processed] {frame_idx} frames")
                sys.stderr.flush()

        frame_idx += 1

    cap.release()
    if not use_json_progress:
        sys.stderr.write("\n")
    sys.stderr.flush()
    return segments

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

def main():
    parser = argparse.ArgumentParser(
        description="Analyze a video file to detect segments containing human presence using YOLOv8, optionally output a trimmed video."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input video file (e.g., /path/to/video.mp4)."
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Path to save the trimmed output video (lossless cut using FFmpeg). If not provided, only JSON is printed."
    )
    parser.add_argument(
        "--detectHuman",
        action="store_true",
        help="Enable human detection. If omitted, no analysis is performed and an empty segment list is returned."
    )
    parser.add_argument(
        "--confThreshold",
        type=float,
        default=0.25,
        help="Confidence threshold for person detection (range: 0.0–1.0). Lower values increase sensitivity but may raise false positives. Default: 0.5."
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=1.5,
        help="Padding in seconds added to the start and end of each detected segment to ensure context is preserved. Default: 0.5 seconds."
    )
    parser.add_argument(
        "--gapTolerance",
        type=float,
        default=2.0,
        help="Maximum gap (in seconds) between adjacent detections to be merged into a single continuous segment. Default: 1.0 second."
    )
    parser.add_argument(
        "--export-xml",
        type=str,
        metavar="FILE",
        help="Export an Adobe Premiere Pro XML file for professional editing (no video processing)."
    )
    args = parser.parse_args()

    video_path = args.input
    output_path = args.output
    segments = []

    if args.detectHuman:
        model_path = "yolov8s.onnx"
        if not os.path.isabs(model_path) and not os.path.exists(model_path):
            model_path = resource_path(model_path)
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at: {model_path}")

        conf_threshold = args.confThreshold
        padding = args.padding
        gap_tolerance = args.gapTolerance

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = frame_count / fps if fps > 0 else float('inf')
        cap.release()

        raw_segments = detect_human(video_path, model_path=model_path, conf_threshold=conf_threshold)
        merged = merge_segments(raw_segments, gap_tolerance=gap_tolerance)
        segments = apply_padding(merged, padding=padding, video_duration=video_duration)

        if args.export_xml:
            print(f"Exporting Premiere Pro XML to {args.export_xml}")
            export_fcp7_xml(
                input_video_path=args.input,
                segments=segments,
                output_xml_path=args.export_xml,
                fps=24.0
            )
            print("✅ XML exported successfully. Import into Premiere Pro or DaVinci Resolve.")

    # Always output JSON to stdout (for compatibility)
    print(json.dumps({"segments": segments}, indent=None))

    # If --output is specified, generate trimmed video
    if output_path:
        if not segments:
            error_msg = "No human segments detected. Output video will not be created."
            print(json.dumps({"error": error_msg}), file=sys.stderr)
            sys.exit(1)
        try:
            cut_video_with_ffmpeg(video_path, segments, output_path)
            # Optional: log success to stderr (non-JSON, safe)
            sys.stderr.write(f"[Info] Trimmed video saved to: {output_path}\n")
            sys.stderr.flush()
        except Exception as e:
            error_out = {
                "error": str(e),
                "type": "ffmpeg_error"
            }
            print(json.dumps(error_out), file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_out = {
            "error": str(e),
            "type": "runtime_error"
        }
        print(json.dumps(error_out), file=sys.stderr)
        sys.exit(1)