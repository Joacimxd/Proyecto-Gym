"""
extract_frames.py — Extract frames from a video at a fixed interval.

Saves frames as JPEG images into a folder named after the video file.

Usage:
    python Dataset/extract_frames.py --video video1.mov video2.mov video3.mov --interval 2

Options:
    --video      One or more video file paths (REQUIRED)
    --interval   Extract 1 frame every N seconds. Default: 1
    --output     Output directory. Default: same folder as the video
    --quality    JPEG quality 1-100. Default: 95
    --rotate     Rotate frames: 0, 90, 180, 270. Default: 0
"""

import os
import argparse
import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="Extract frames from a video at fixed intervals")
    parser.add_argument("--video", required=True, nargs="+", help="One or more video file paths")
    parser.add_argument("--interval", type=float, default=1.0, help="Extract 1 frame every N seconds. Default: 1")
    parser.add_argument("--output", default=None, help="Output base directory. Default: same folder as video")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality 1-100. Default: 95")
    parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270], help="Rotation degrees. Default: 0")
    return parser.parse_args()


def process_video(video_path, interval, output_base, quality, rotation):
    """Extract frames from a single video."""
    video_path = os.path.abspath(video_path)
    if not os.path.isfile(video_path):
        print(f"[ERROR] Video not found: {video_path}")
        return

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    base_dir = output_base or os.path.dirname(video_path)
    output_dir = os.path.join(base_dir, video_name)
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    frame_step = int(fps * interval)

    print(f"Video:     {video_path}")
    print(f"FPS:       {fps:.1f}")
    print(f"Duration:  {duration:.1f}s ({total_frames} frames)")
    print(f"Interval:  1 frame every {interval}s (every {frame_step} frames)")
    print(f"Expected:  ~{int(duration / interval)} frames")
    print(f"Output:    {output_dir}")

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    saved = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step == 0:
            if rotation is not None:
                frame = cv2.rotate(frame, rotation)

            filename = f"frame_{saved:05d}.jpg"
            filepath = os.path.join(output_dir, filename)
            cv2.imwrite(filepath, frame, encode_params)
            saved += 1

            if saved % 10 == 0:
                print(f"  Saved {saved} frames...")

        frame_idx += 1

    cap.release()
    print(f"Done! Extracted {saved} frames to {output_dir}\n")


def main():
    args = parse_args()

    rotate_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    rotation = rotate_map.get(args.rotate)

    print(f"Processing {len(args.video)} video(s) | interval={args.interval}s | quality={args.quality} | rotate={args.rotate}°\n")

    for video in args.video:
        process_video(video, args.interval, args.output, args.quality, rotation)


if __name__ == "__main__":
    main()
