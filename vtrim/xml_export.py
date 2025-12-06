import os
import subprocess
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

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

    sequence_duration = current_timeline_frame

    # --- 开始构建 XML ---
    xmeml = ET.Element("xmeml", version="5")
    seq = ET.SubElement(xmeml, "sequence")
    ET.SubElement(seq, "name").text = "VTrim Auto-Edit"
    ET.SubElement(seq, "duration").text = str(sequence_duration)

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

    print(f"Exported FCP7 XML to: {output_xml_path}")
    print(f"Sequence duration: {sequence_duration} frames @ {fps} fps")
