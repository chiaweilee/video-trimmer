import argparse
import sys
import json
import cv2

from .analyzer import detect_human
from .segment_utils import merge_segments, apply_padding
from .ffmpeg_utils import cut_video_with_ffmpeg
from .xml_export import export_fcp7_xml

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
        "--detect-human",
        action="store_true",
        help="Enable human detection. If omitted, no analysis is performed and an empty segment list is returned."
    )
    parser.add_argument(
        "--conf-threshold",
        type=float,
        default=0.25,
        help="Confidence threshold for person detection (range: 0.0–1.0). Lower values increase sensitivity but may raise false positives. "
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=1,
        help="Padding in seconds added to the start and end of each detected segment to ensure context is preserved. "
    )
    parser.add_argument(
        "--gap-tolerance",
        type=float,
        default=4.0,
        help="Maximum gap (in seconds) between adjacent detections to be merged into a single continuous segment. "
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

    if args.detect_human:
        conf_threshold = args.conf_threshold
        padding = args.padding
        gap_tolerance = args.gap_tolerance

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = frame_count / fps if fps > 0 else float('inf')
        cap.release()

        raw_segments = detect_human(video_path, conf_threshold=conf_threshold)
        merged = merge_segments(raw_segments, gap_tolerance=gap_tolerance)
        segments = apply_padding(merged, padding=padding, video_duration=video_duration)

        if args.export_xml:
            export_fcp7_xml(
                input_video_path=args.input,
                segments=segments,
                output_xml_path=args.export_xml,
                video_duration=video_duration,
                fps=fps
            )

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