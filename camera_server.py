"""
camera_server.py — Multi-Camera YOLO Detection Server with Usage Tracking

Accepts TCP connections from multiple camera_client instances.
Each client identifies the gym machine it is filming.
Receives video frames, runs YOLO inference (machine-used only),
tracks usage time with debounce to handle detection errors,
and updates average_time in gym.db.

Usage:
    python camera_server.py

Press Q or ESC to quit.
"""

import socket
import struct
import json
import threading
import time
import sqlite3
import os
import cv2
import numpy as np
from ultralytics import YOLO

# ── Configuration ─────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 6060
MODEL_PATH = "/Users/davidcervantes/Documents/Sistemas Multiagentes/Proyecto Gym/Model/best.torchscript"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gym.db")
CONFIDENCE_THRESHOLD = 0.25
WINDOW_NAME = "Camera Server — YOLO Detection (press Q to quit)"

# Debounce: how many seconds of non-detection before considering the
# machine truly "not in use". This absorbs brief YOLO misses.
DEBOUNCE_SECONDS = 3.0

# Minimum session length (seconds) to count as a real usage session.
# Anything shorter is considered a detection flicker and is discarded.
MIN_SESSION_SECONDS = 10.0

# How to blend observed times into the DB average_time.
# new_avg = old_avg * (1 - ALPHA) + observed * ALPHA
# Higher ALPHA = observations change the average faster.
SMOOTHING_ALPHA = 0.3

# ── Shared state ──────────────────────────────────────────────────────
lock = threading.Lock()

# Per-client camera feed data
# {client_id: {"frame": ndarray, "machine": str, "last_update": float}}
camera_feeds = {}

# Per-machine usage tracking state
# {machine_name: {"in_use": bool, "session_start": float|None,
#                  "last_detected": float, "sessions": [float, ...]}}
usage_trackers = {}

next_client_id = 0

# ── Load YOLO model ──────────────────────────────────────────────────
print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
print(f"Model loaded. Class names: {model.names}")

# Violet accent for bounding boxes (BGR)
BOX_COLOR_USED = (246, 92, 138)      # violet
BOX_COLOR_IDLE = (80, 80, 80)         # dim gray (not drawn, but just in case)


# ── Database helpers ──────────────────────────────────────────────────
def update_average_time(machine_name, observed_minutes):
    """
    Update the average_time for a machine in gym.db using exponential
    moving average so it smoothly adapts to real observed usage.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT average_time FROM machines WHERE name = ?", (machine_name,)
        ).fetchone()
        if row is None:
            print(f"  [DB] Machine '{machine_name}' not found in database, skipping.")
            return

        old_avg = row[0]
        new_avg = round(old_avg * (1 - SMOOTHING_ALPHA) + observed_minutes * SMOOTHING_ALPHA)
        new_avg = max(1, new_avg)  # floor at 1 minute

        conn.execute(
            "UPDATE machines SET average_time = ? WHERE name = ?",
            (new_avg, machine_name),
        )
        conn.commit()
        print(f"  [DB] {machine_name}: observed {observed_minutes:.1f} min → "
              f"avg updated {old_avg} → {new_avg} min")
    finally:
        conn.close()


# ── Usage tracking logic ─────────────────────────────────────────────
def get_or_create_tracker(machine_name):
    """Get or initialize the usage tracker for a machine."""
    if machine_name not in usage_trackers:
        usage_trackers[machine_name] = {
            "in_use": False,
            "session_start": None,
            "last_detected": 0.0,
            "sessions": [],
        }
    return usage_trackers[machine_name]


def process_detection(machine_name, detected_in_use):
    """
    Update usage state for a machine based on a single frame's detection.
    Uses debounce to absorb brief YOLO misses/flickers.

    Args:
        machine_name: Which machine this is
        detected_in_use: True if YOLO detected 'machine-used' in this frame
    """
    now = time.time()
    tracker = get_or_create_tracker(machine_name)

    if detected_in_use:
        tracker["last_detected"] = now

        # Transition: idle → in use
        if not tracker["in_use"]:
            tracker["in_use"] = True
            tracker["session_start"] = now
            print(f"  [{machine_name}] Session STARTED")

    else:
        # Check debounce: has it been long enough since last detection?
        if tracker["in_use"]:
            time_since_last = now - tracker["last_detected"]

            if time_since_last >= DEBOUNCE_SECONDS:
                # Transition: in use → idle  (debounce expired)
                tracker["in_use"] = False
                session_start = tracker["session_start"]
                # Use last_detected as session end (not now, since the
                # machine actually stopped being detected earlier)
                session_end = tracker["last_detected"]
                duration_sec = session_end - session_start

                if duration_sec >= MIN_SESSION_SECONDS:
                    duration_min = duration_sec / 60.0
                    tracker["sessions"].append(duration_min)
                    print(f"  [{machine_name}] Session ENDED: {duration_min:.1f} min")

                    # Update DB average
                    update_average_time(machine_name, duration_min)
                else:
                    print(f"  [{machine_name}] Session discarded (too short: {duration_sec:.1f}s)")

                tracker["session_start"] = None


# ── YOLO annotation ──────────────────────────────────────────────────
def annotate_frame(frame, machine_name):
    """
    Run YOLO inference, draw 'machine-used' detections,
    and update the usage tracker for this machine.
    Returns (annotated_frame, detection_count).
    """
    results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

    det_count = 0
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names.get(cls_id, str(cls_id))

            if cls_name != "machine-used":
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR_USED, 3)

            # Large label
            label = f"In Use {conf:.0%}"
            font_scale = 1.0
            font_thick = 2
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thick
            )
            cv2.rectangle(frame, (x1, y1 - th - 16), (x1 + tw + 12, y1), BOX_COLOR_USED, -1)
            cv2.putText(
                frame, label, (x1 + 6, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), font_thick, cv2.LINE_AA,
            )
            det_count += 1

    # Update usage tracker
    process_detection(machine_name, detected_in_use=(det_count > 0))

    return frame, det_count


# ── Network helpers ───────────────────────────────────────────────────
def recv_exact(sock, n):
    """Receive exactly n bytes from the socket."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def handle_camera_client(conn, addr, client_id):
    """Receive the machine header then stream frames from a camera client."""
    machine_name = f"Camera {client_id + 1}"

    try:
        # ── Read machine name header ──
        header_len_data = recv_exact(conn, 4)
        if header_len_data is None:
            print(f"[-] Client {addr} disconnected before sending header.")
            conn.close()
            return

        header_len = struct.unpack(">I", header_len_data)[0]
        header_data = recv_exact(conn, header_len)
        if header_data:
            header = json.loads(header_data.decode("utf-8"))
            machine_name = header.get("machine", machine_name)

        print(f"[+] {machine_name} connected from {addr}")

        with lock:
            camera_feeds[client_id] = {
                "frame": None,
                "machine": machine_name,
                "last_update": time.time(),
            }
            # Initialize usage tracker
            get_or_create_tracker(machine_name)

        # ── Stream frames ──
        while True:
            size_data = recv_exact(conn, 4)
            if size_data is None:
                break

            frame_size = struct.unpack(">I", size_data)[0]
            if frame_size == 0 or frame_size > 10_000_000:
                break

            jpeg_data = recv_exact(conn, frame_size)
            if jpeg_data is None:
                break

            np_arr = np.frombuffer(jpeg_data, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            with lock:
                camera_feeds[client_id]["frame"] = frame
                camera_feeds[client_id]["last_update"] = time.time()

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        # Finalize any open session for this machine
        tracker = get_or_create_tracker(machine_name)
        if tracker["in_use"] and tracker["session_start"]:
            duration_sec = time.time() - tracker["session_start"]
            if duration_sec >= MIN_SESSION_SECONDS:
                duration_min = duration_sec / 60.0
                tracker["sessions"].append(duration_min)
                print(f"  [{machine_name}] Session ENDED on disconnect: {duration_min:.1f} min")
                update_average_time(machine_name, duration_min)
            tracker["in_use"] = False
            tracker["session_start"] = None

        print(f"[-] {machine_name} disconnected ({addr})")
        with lock:
            camera_feeds.pop(client_id, None)
        conn.close()


# ── Grid composition ─────────────────────────────────────────────────
def compose_grid(feeds, target_w=1280, target_h=720):
    """Arrange all camera frames into a grid with YOLO annotations."""
    n = len(feeds)
    if n == 0:
        blank = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        msg = "Waiting for camera clients on port 6060..."
        cv2.putText(blank, msg, (40, target_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (100, 100, 100), 2, cv2.LINE_AA)
        return blank

    # Grid layout
    if n == 1:
        cols, rows = 1, 1
    elif n == 2:
        cols, rows = 2, 1
    elif n <= 4:
        cols, rows = 2, 2
    elif n <= 6:
        cols, rows = 3, 2
    else:
        cols = 3
        rows = (n + cols - 1) // cols

    cell_w = target_w // cols
    cell_h = target_h // rows
    grid = np.zeros((target_h, target_w, 3), dtype=np.uint8)

    for i, (cid, feed) in enumerate(sorted(feeds.items())):
        r = i // cols
        c = i % cols
        x_off = c * cell_w
        y_off = r * cell_h

        frame = feed["frame"]
        machine_name = feed["machine"]

        if frame is None:
            cv2.putText(grid, f"{machine_name}: No Frame",
                        (x_off + 20, y_off + cell_h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2, cv2.LINE_AA)
            continue

        # Run YOLO + update usage tracking
        annotated, det_count = annotate_frame(frame.copy(), machine_name)

        # Resize to fit cell
        resized = cv2.resize(annotated, (cell_w - 4, cell_h - 4))

        # Machine name overlay
        cv2.rectangle(resized, (0, 0), (len(machine_name) * 16 + 20, 38), (0, 0, 0), -1)
        cv2.putText(resized, machine_name, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

        # Usage status badge
        tracker = get_or_create_tracker(machine_name)
        if tracker["in_use"]:
            elapsed = time.time() - (tracker["session_start"] or time.time())
            status = f"IN USE {elapsed:.0f}s"
            badge_color = (0, 180, 255)  # orange
        else:
            status = "IDLE"
            badge_color = (100, 100, 100)

        (sw, sh), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        sx = resized.shape[1] - sw - 16
        cv2.rectangle(resized, (sx - 6, 4), (sx + sw + 6, 34), badge_color, -1)
        cv2.putText(resized, status, (sx, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # Place in grid
        grid[y_off + 2: y_off + 2 + resized.shape[0],
             x_off + 2: x_off + 2 + resized.shape[1]] = resized

    # Grid lines
    for c in range(1, cols):
        cv2.line(grid, (c * cell_w, 0), (c * cell_w, target_h), (60, 60, 60), 1)
    for r in range(1, rows):
        cv2.line(grid, (0, r * cell_h), (target_w, r * cell_h), (60, 60, 60), 1)

    return grid


# ── Server main loop ─────────────────────────────────────────────────
def start_server():
    global next_client_id

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)
    server.settimeout(0.5)
    print(f"Camera server listening on {HOST}:{PORT}")
    print(f"YOLO model: {MODEL_PATH}")
    print(f"Database: {DB_PATH}")
    print(f"Debounce: {DEBOUNCE_SECONDS}s | Min session: {MIN_SESSION_SECONDS}s")
    print("Waiting for camera clients...\n")

    try:
        while True:
            try:
                conn, addr = server.accept()
                cid = next_client_id
                next_client_id += 1
                t = threading.Thread(
                    target=handle_camera_client, args=(conn, addr, cid), daemon=True
                )
                t.start()
            except socket.timeout:
                pass
            except OSError:
                break

            # Build and display the grid
            with lock:
                current_feeds = dict(camera_feeds)

            grid = compose_grid(current_feeds)
            cv2.imshow(WINDOW_NAME, grid)

            key = cv2.waitKey(30) & 0xFF
            if key == ord("q") or key == 27:
                break

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Print session summaries
        print("\n=== Usage Session Summary ===")
        for machine, tracker in usage_trackers.items():
            sessions = tracker["sessions"]
            if sessions:
                avg = sum(sessions) / len(sessions)
                print(f"  {machine}: {len(sessions)} sessions, avg {avg:.1f} min")
            else:
                print(f"  {machine}: no completed sessions")
        print("=============================\n")

        server.close()
        cv2.destroyAllWindows()
        print("Camera server stopped.")


if __name__ == "__main__":
    start_server()
