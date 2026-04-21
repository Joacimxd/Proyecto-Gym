import socket
import struct
import json
import time
import argparse
import sys
import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="Camera client for YOLO detection server")
    parser.add_argument(
        "--machine", required=True,
        help="Name of the gym machine this camera is filming (e.g. 'Bench', 'Leg Curl')",
    )
    parser.add_argument(
        "--source", default="0",
        help="Webcam device index (integer) or path to a video file. Default: 0",
    )
    parser.add_argument("--host", default="192.168.100.119", help="Server host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=6060, help="Server port. Default: 6060")
    parser.add_argument("--quality", type=int, default=70, help="JPEG quality 1-100. Default: 70")
    parser.add_argument("--fps", type=int, default=24, help="Max FPS to send. Default: 24")
    parser.add_argument("--rotate", type=int, default=90, choices=[0, 90, 180, 270], help="Rotation degrees. Default: 0")
    parser.add_argument("--send-width", type=int, default=640, help="Downscale frame width before encoding/sending. 0=no resize. Default: 640")
    parser.add_argument("--no-preview", action="store_true", help="Disable local preview window (saves CPU).")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        source = int(args.source)
        print(f"Source: Webcam (device {source})")
    except ValueError:
        source = args.source
        print(f"Source: Video file — {source}")

    print(f"Machine: {args.machine}")

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Could not open source: {source}")
        sys.exit(1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    print(f"Capture: {width}x{height} @ {src_fps:.0f} FPS")

    rotate_map = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    rotation = rotate_map.get(args.rotate)

    print(f"Connecting to camera server at {args.host}:{args.port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((args.host, args.port))
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to {args.host}:{args.port}")
        print("       Make sure camera_server.py is running.")
        sys.exit(1)

    header = json.dumps({"machine": args.machine}).encode("utf-8")
    sock.sendall(struct.pack(">I", len(header)) + header)
    print(f"Sent machine header: {args.machine}")
    print("Connected! Streaming...\n")

    frame_interval = 1.0 / args.fps
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, args.quality]
    frame_count = 0

    try:
        while True:
            t_start = time.time()

            ret, frame = cap.read()

            if not ret:
                if isinstance(source, str):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    print("Webcam stream ended.")
                    break

            if rotation is not None:
                frame = cv2.rotate(frame, rotation)

            if args.send_width and frame.shape[1] > args.send_width:
                ratio = args.send_width / frame.shape[1]
                send_frame = cv2.resize(
                    frame,
                    (args.send_width, int(frame.shape[0] * ratio)),
                    interpolation=cv2.INTER_AREA,
                )
            else:
                send_frame = frame

            success, jpeg = cv2.imencode(".jpg", send_frame, encode_params)
            if not success:
                continue

            jpeg_bytes = jpeg.tobytes()
            frame_size = len(jpeg_bytes)

            try:
                sock.sendall(struct.pack(">I", frame_size) + jpeg_bytes)
            except (BrokenPipeError, ConnectionResetError, OSError):
                print("Connection to server lost.")
                break

            frame_count += 1
            if frame_count % 100 == 0:
                print(f"  Sent {frame_count} frames ({frame_size // 1024} KB/frame)")

            if not args.no_preview:
                preview = cv2.resize(frame, (480, 360))
                cv2.putText(
                    preview, f"{args.machine} -> {args.host}:{args.port}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA,
                )
                cv2.putText(
                    preview, f"Frame {frame_count} | Q={args.quality} | {args.fps}fps | send {send_frame.shape[1]}x{send_frame.shape[0]}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA,
                )
                cv2.imshow(f"Camera Client — {args.machine} (Q to quit)", preview)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

            elapsed = time.time() - t_start
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        cap.release()
        sock.close()
        cv2.destroyAllWindows()
        print(f"Camera client stopped. Sent {frame_count} frames total.")


if __name__ == "__main__":
    main()
