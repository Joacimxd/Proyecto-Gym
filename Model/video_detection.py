"""
YOLO v11 — Live Video Detection (machine-used only)

Only shows annotations for machines that are being USED.
Labels are large and clearly visible.

Usage:
    python video_detection.py

Keys:
    Q / ESC  — Quit the live window
"""

import os
import glob
import time
import cv2
import numpy as np
from ultralytics import YOLO

# ── Configuration ─────────────────────────────────────────────────────
MODEL_PATH = "/Users/davidcervantes/Documents/Sistemas Multiagentes/Proyecto Gym/Model/best2.torchscript"

# Source: 0 for webcam, or a video file path
SOURCE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "/Users/davidcervantes/Documents/Sistemas Multiagentes/Proyecto Gym/Dataset/Pend.MOV",
)

CONFIDENCE_THRESHOLD = 0.25
WINDOW_NAME = "YOLO v11 — Live Detection (press Q to quit)"

# ── Auto-detect video if SOURCE is "auto" ─────────────────────────────
if isinstance(SOURCE, str) and SOURCE == "auto":
    VIDEO_EXTENSIONS = ("*.mp4", "*.avi", "*.mov", "*.mkv", "*.webm")
    video_files = []
    for ext in VIDEO_EXTENSIONS:
        video_files.extend(glob.glob(ext))
    if not video_files:
        raise FileNotFoundError(
            "No video file found. Place a video in the Model/ folder "
            "or set SOURCE = 0 to use your webcam."
        )
    SOURCE = video_files[0]
    print(f"Auto-detected video: {SOURCE}")

if isinstance(SOURCE, int):
    print(f"Source: Webcam (device {SOURCE})")
else:
    print(f"Source: Video file — {SOURCE}")

# ── Load YOLO model ───────────────────────────────────────────────────
model = YOLO(MODEL_PATH)
print("Model loaded successfully!")
print(f"   Class names: {model.names}")

# ── Live detection window ─────────────────────────────────────────────

# Fixed color for "in use" bounding boxes (violet accent)
BOX_COLOR = (246, 92, 138)       # BGR for violet (#8B5CF6)
BOX_COLOR_BG = (180, 60, 100)    # Slightly darker for label bg

cap = cv2.VideoCapture(SOURCE)
if not cap.isOpened():
    raise RuntimeError(f"Could not open source: {SOURCE}")

# Get video properties
src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Stream: {width}x{height} @ {src_fps:.0f} FPS")

frame_count = 0
fps_display = 0.0
prev_time = time.time()

print("\nLive window opened — press 'Q' or 'ESC' to close.\n")

while True:
    ret, frame = cap.read()
    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

    # If video file ended, loop back to start
    if not ret:
        if isinstance(SOURCE, str):
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        else:
            break

    frame_count += 1

    # ── Run YOLO inference ──
    results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

    # ── Draw detections (ONLY "machine-used") ──
    det_count = 0
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names.get(cls_id, str(cls_id))

            # Skip anything that is NOT "machine-used"
            if cls_name != "machine_used":
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])

            # Thick bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 3)

            # Large label with background
            label = f"In Use {conf:.0%}"
            font_scale = 1.2
            font_thick = 3
            (tw, th), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thick
            )
            # Label background
            cv2.rectangle(
                frame,
                (x1, y1 - th - 18),
                (x1 + tw + 14, y1),
                BOX_COLOR,
                -1,
            )
            # Label text
            cv2.putText(
                frame,
                label,
                (x1 + 7, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                font_thick,
                cv2.LINE_AA,
            )
            det_count += 1

    # ── FPS counter ──
    curr_time = time.time()
    fps_display = 1.0 / max(curr_time - prev_time, 1e-6)
    prev_time = curr_time

    # ── HUD overlay ──
    hud = f"FPS: {fps_display:.1f}  |  Machines in use: {det_count}"
    cv2.rectangle(frame, (0, 0), (len(hud) * 15 + 20, 44), (0, 0, 0), -1)
    cv2.putText(
        frame,
        hud,
        (10, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    # ── Show frame ──
    cv2.imshow(WINDOW_NAME, frame)

    # ── Check for quit ──
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q") or key == 27:  # Q or ESC
        break

cap.release()
cv2.destroyAllWindows()
print(f"\nStopped. Processed {frame_count} frames.")
