import os
import subprocess
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

def get_video_total_frames(video_path, fps):
    """Get total frame count via ffprobe; fallback to duration * fps if failed."""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'json', video_path
        ], capture_output=True, text=True, check=True)
        duration_sec = float(json.loads(result.stdout)['format']['duration'])
        return int(round(duration_sec * fps))
    except Exception:
        # Fallback: assume 60 seconds if ffprobe fails
        return int(round(60.0 * fps))

def build_full_timeline_segments(segments, video_duration):
    """
    Convert 'valid-only' segments into a full timeline covering [0, video_duration],
    with each segment labeled as 'valid' (keep) or 'invalid' (skip).
    """
    if not segments:
        return [{"start": 0, "end": video_duration, "type": "invalid"}]

    segments = sorted(segments, key=lambda x: x["start"])
    full = []
    current = 0.0

    for seg in segments:
        start = seg["start"]
        end = seg["end"]

        # Add preceding invalid segment
        if current < start:
            full.append({"start": current, "end": start, "type": "invalid"})
        
        # Add valid segment
        full.append({"start": start, "end": end, "type": "valid"})
        current = end

    # Add trailing invalid segment if needed
    if current < video_duration:
        full.append({"start": current, "end": video_duration, "type": "invalid"})

    return full

def export_fcp7_xml(input_video_path, segments, output_xml_path, video_duration, fps=24.0):
    """
    Export an FCP7 XML file compatible with DaVinci Resolve and Premiere Pro.
    
    This version exports the FULL timeline (both kept and skipped segments),
    with synchronized video and audio clips for each segment.
    Clips are labeled and color-coded for easy identification.

    Args:
        input_video_path (str): Path to source video file (e.g., "clip.mp4")
        segments (list): List of dicts [{"start": s, "end": e}, ...] in seconds (only VALID segments)
        output_xml_path (str): Output XML file path
        video_duration (float): Total duration of the source video in seconds
        fps (float): Frame rate (default: 24.0)
    """
    input_video_path = os.path.abspath(input_video_path)
    video_name = os.path.basename(input_video_path)
    file_id = f"{video_name} file"

    media_total_frames = get_video_total_frames(input_video_path, fps)

    # Build full timeline with 'valid'/'invalid' types
    full_segments = build_full_timeline_segments(segments, video_duration)
    clip_items = []
    current_timeline_frame = 0

    for seg in full_segments:
        in_frame = int(round(seg["start"] * fps))
        out_frame = int(round(seg["end"] * fps))
        clip_duration_frames = max(1, out_frame - in_frame)  # Avoid zero-duration clips

        start_frame = current_timeline_frame
        end_frame = start_frame + clip_duration_frames

        clip_items.append({
            "in": in_frame,
            "out": out_frame,
            "start": start_frame,
            "end": end_frame,
            "duration": clip_duration_frames,
            "type": seg["type"],
        })
        current_timeline_frame = end_frame

    sequence_duration = current_timeline_frame

    # --- Build XML ---
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

    # Media container
    media = ET.SubElement(seq, "media")

    # === Video Track ===
    video = ET.SubElement(media, "video")
    track = ET.SubElement(video, "track")

    for i, clip in enumerate(clip_items):
        clip_id = f"{video_name} {i}"
        ci = ET.SubElement(track, "clipitem", id=clip_id)

        # Clip name with prefix for clarity
        prefix = "[V] " if clip["type"] == "valid" else "[I] "
        ET.SubElement(ci, "name").text = prefix + video_name

        # Color label for DaVinci Resolve
        label_elem = ET.SubElement(ci, "label")
        label_elem.text = "Blue" if clip["type"] == "valid" else "Gray"

        ET.SubElement(ci, "duration").text = str(clip["duration"])

        cr = ET.SubElement(ci, "rate")
        ET.SubElement(cr, "timebase").text = str(int(round(fps)))
        ET.SubElement(cr, "ntsc").text = "FALSE"

        ET.SubElement(ci, "start").text = str(clip["start"])
        ET.SubElement(ci, "end").text = str(clip["end"])
        ET.SubElement(ci, "in").text = str(clip["in"])
        ET.SubElement(ci, "out").text = str(clip["out"])
        ET.SubElement(ci, "enabled").text = "TRUE"

        # Define media file only once (on first clip)
        if i == 0:
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

            media_info = ET.SubElement(file_elem, "media")
            vid_info = ET.SubElement(media_info, "video")
            ET.SubElement(vid_info, "duration").text = str(media_total_frames)
            sc = ET.SubElement(vid_info, "samplecharacteristics")
            ET.SubElement(sc, "width").text = "1920"
            ET.SubElement(sc, "height").text = "1080"

            aud_info = ET.SubElement(media_info, "audio")
            ET.SubElement(aud_info, "channelcount").text = "2"
        else:
            ET.SubElement(ci, "file", id=file_id)

        # Link video clip to itself (required by FCP7 spec)
        link = ET.SubElement(ci, "link")
        ET.SubElement(link, "linkclipref").text = clip_id

    # Video format info
    fmt = ET.SubElement(video, "format")
    sc_fmt = ET.SubElement(fmt, "samplecharacteristics")
    ET.SubElement(sc_fmt, "width").text = "1920"
    ET.SubElement(sc_fmt, "height").text = "1080"
    ET.SubElement(sc_fmt, "pixelaspectratio").text = "square"
    fmt_rate = ET.SubElement(sc_fmt, "rate")
    ET.SubElement(fmt_rate, "timebase").text = str(int(round(fps)))
    ET.SubElement(fmt_rate, "ntsc").text = "FALSE"

    # === Audio Track ===
    audio = ET.SubElement(media, "audio")
    audio_track = ET.SubElement(audio, "track")

    for i, clip in enumerate(clip_items):
        audio_clip_id = f"{video_name} audio {i}"
        ac = ET.SubElement(audio_track, "clipitem", id=audio_clip_id)

        ET.SubElement(ac, "name").text = video_name
        ET.SubElement(ac, "duration").text = str(clip["duration"])

        ar = ET.SubElement(ac, "rate")
        ET.SubElement(ar, "timebase").text = str(int(round(fps)))
        ET.SubElement(ar, "ntsc").text = "FALSE"

        ET.SubElement(ac, "start").text = str(clip["start"])
        ET.SubElement(ac, "end").text = str(clip["end"])
        ET.SubElement(ac, "in").text = str(clip["in"])
        ET.SubElement(ac, "out").text = str(clip["out"])
        ET.SubElement(ac, "enabled").text = "TRUE"

        # Reference the same media file
        ET.SubElement(ac, "file", id=file_id)

        # Source track info
        st = ET.SubElement(ac, "sourcetrack")
        ET.SubElement(st, "mediatype").text = "audio"
        ET.SubElement(st, "trackindex").text = "1"

        # Link audio to its corresponding video clip (standard FCP7 linking)
        link = ET.SubElement(ac, "link")
        ET.SubElement(link, "linkclipref").text = f"{video_name} {i}"      # video clip ID
        ET.SubElement(link, "linkclipref").text = audio_clip_id             # self

    # --- Write pretty-printed XML to file ---
    rough_string = ET.tostring(xmeml, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # Remove blank lines
    lines = [line for line in pretty_xml.splitlines() if line.strip()]
    with open(output_xml_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Exported FCP7 XML to: {output_xml_path}")
    print(f"Sequence duration: {sequence_duration} frames @ {fps} fps")