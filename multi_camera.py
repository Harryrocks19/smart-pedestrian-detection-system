"""
multi_camera.py — Multi-Camera Pedestrian Detection
Cameras:
  CAM_0: USB Webcam
  CAM_1: Phone 1 — http://10.211.20.90:8080
  CAM_2: Phone 2 — http://10.211.20.34:8080

Run: python multi_camera.py
Keys: Q = quit
"""

import cv2
import threading
import time
import numpy as np
import urllib.request
from datetime import datetime
from sort import Sort

try:
    from db_manager import log_detection, log_alert
    DB_OK = True
except Exception:
    DB_OK = False

# ── Camera Sources ────────────────────────────────────────────────────────────
CAMERA_SOURCES = {
    "CAM_0": 0,
    "CAM_1": "http://10.211.20.90:8080",
    "CAM_2": "http://10.211.20.34:8080",
}

# ── Config ────────────────────────────────────────────────────────────────────
CROWD_LIMIT      = 5
SAFE_DISTANCE_PX = 100
DISPLAY_W        = 640
DISPLAY_H        = 360

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN  = (0, 255, 0)
RED    = (0, 0, 255)
YELLOW = (0, 255, 255)
WHITE  = (255, 255, 255)
BLACK  = (0, 0, 0)
ORANGE = (0, 165, 255)

# ── Shared state ──────────────────────────────────────────────────────────────
cam_frames = {}
cam_counts = {}
cam_alerts = {}
cam_lock   = threading.Lock()
running    = True

# ── HOG ───────────────────────────────────────────────────────────────────────
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


# ── IP Camera Reader (urllib JPEG — works when OpenCV fails) ──────────────────
class IPCamReader:
    """Grabs JPEG snapshots from IP Webcam app via urllib."""
    def __init__(self, base_url):
        self.snap_url = base_url.rstrip('/') + '/shot.jpg'
        self.frame    = None
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            try:
                resp = urllib.request.urlopen(self.snap_url, timeout=3)
                arr  = np.asarray(bytearray(resp.read()), dtype=np.uint8)
                img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    self.frame = img
            except Exception:
                pass
            time.sleep(0.04)   # ~25 fps

    def read(self):
        return (True, self.frame) if self.frame is not None else (False, None)

    def isOpened(self):
        return self.frame is not None

    def release(self):
        self._running = False


def open_camera(source):
    """Returns (cap, label). Uses IPCamReader for phone URLs."""
    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        return cap
    # Try VideoCapture first
    cap = cv2.VideoCapture(source + '/video', cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    ret, _ = cap.read()
    if ret:
        print(f"VideoCapture OK for {source}")
        return cap
    cap.release()
    # Fallback to IPCamReader
    print(f"Using IPCamReader for {source}")
    return IPCamReader(source)


# ── Per-camera detection thread ───────────────────────────────────────────────
def process_camera(cam_id, source):
    cap = open_camera(source)

    # Wait up to 5 seconds for camera to open
    for _ in range(50):
        if cap.isOpened():
            break
        time.sleep(0.1)

    if not cap.isOpened():
        print(f"[{cam_id}] OFFLINE: {source}")
        blank = np.zeros((DISPLAY_H, DISPLAY_W, 3), dtype=np.uint8)
        cv2.putText(blank, f"{cam_id}: OFFLINE", (20, DISPLAY_H//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, RED, 2)
        cv2.putText(blank, str(source), (20, DISPLAY_H//2 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, YELLOW, 1)
        with cam_lock:
            cam_frames[cam_id] = blank
            cam_counts[cam_id] = 0
            cam_alerts[cam_id] = False
        return

    print(f"[{cam_id}] Connected: {source}")
    tracker       = Sort(max_age=10, min_hits=2, iou_threshold=0.3)
    track_history = {}
    frame_count   = 0
    fps_time      = time.time()
    fps           = 0
    log_timer     = time.time()

    while running:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        frame       = cv2.resize(frame, (DISPLAY_W, DISPLAY_H))
        h, w        = frame.shape[:2]
        frame_count += 1
        display     = frame.copy()

        if frame_count % 10 == 0:
            fps      = 10 / max(time.time() - fps_time, 0.001)
            fps_time = time.time()

        # HOG detection
        regions, weights = hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        detections = []
        if len(regions) > 0:
            for (x, y, bw, bh), wt in zip(regions, weights):
                if wt > 0.4:
                    detections.append([x, y, x+bw, y+bh, float(wt)])
        dets = np.array(detections) if detections else np.empty((0, 5))

        # Tracking
        tracked      = tracker.update(dets)
        people_count = len(tracked)
        centers      = []

        for trk in tracked:
            x1, y1, x2, y2, tid = (int(trk[0]), int(trk[1]),
                                    int(trk[2]), int(trk[3]), int(trk[4]))
            cx, cy = (x1+x2)//2, (y1+y2)//2
            centers.append((cx, cy))
            track_history[tid] = cy
            cv2.rectangle(display, (x1, y1), (x2, y2), YELLOW, 2)
            cv2.putText(display, f"ID:{tid}", (x1, y1-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1)
            cv2.circle(display, (cx, cy), 4, YELLOW, -1)

        # Social distancing lines
        for i in range(len(centers)):
            for j in range(i+1, len(centers)):
                if np.linalg.norm(np.array(centers[i])-np.array(centers[j])) < SAFE_DISTANCE_PX:
                    cv2.line(display, centers[i], centers[j], RED, 2)

        # Crowd alert
        alert = people_count >= CROWD_LIMIT
        if alert:
            cv2.rectangle(display, (0, 0), (w, h), RED, 4)
            cv2.putText(display, "CROWD ALERT!", (w//2-90, h//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, RED, 2)

        # Overlay
        ov = display.copy()
        cv2.rectangle(ov, (0, 0), (190, 75), BLACK, -1)
        cv2.addWeighted(ov, 0.5, display, 0.5, 0, display)
        cv2.putText(display, f"{cam_id}",             (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ORANGE, 1)
        cv2.putText(display, f"People: {people_count}",(5, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE,  1)
        cv2.putText(display, f"FPS: {fps:.1f}",        (5, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GREEN, 1)
        cv2.putText(display, f"Alert: {'YES' if alert else 'NO'}", (5, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, RED if alert else GREEN, 1)

        # DB log
        if time.time() - log_timer >= 5 and DB_OK:
            try:
                log_detection(people_count, 0, 0, 0, "YES" if alert else "NO")
                if alert:
                    log_alert("CROWD", people_count, 0, 0)
            except Exception:
                pass
            log_timer = time.time()

        with cam_lock:
            cam_frames[cam_id] = display.copy()
            cam_counts[cam_id] = people_count
            cam_alerts[cam_id] = alert

    cap.release()
    print(f"[{cam_id}] Stopped.")


# ── Grid builder ──────────────────────────────────────────────────────────────
def build_grid():
    with cam_lock:
        frames = {k: cam_frames.get(k) for k in CAMERA_SOURCES}

    tiles = []
    for cam_id in CAMERA_SOURCES:
        f = frames.get(cam_id)
        if f is None:
            f = np.zeros((DISPLAY_H, DISPLAY_W, 3), dtype=np.uint8)
            cv2.putText(f, f"{cam_id}: Connecting...", (20, DISPLAY_H//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, YELLOW, 2)
        tiles.append(cv2.resize(f, (DISPLAY_W, DISPLAY_H)))

    n = len(tiles)
    if n == 1:
        return tiles[0]
    if n == 2:
        return np.hstack(tiles)
    # 3 cameras: top row = cam0 + cam1, bottom row = cam2 + blank
    top  = np.hstack(tiles[:2])
    blank = np.zeros((DISPLAY_H, DISPLAY_W, 3), dtype=np.uint8)
    bot  = np.hstack([tiles[2], blank])
    return np.vstack([top, bot])


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global running

    threads = []
    for cam_id, source in CAMERA_SOURCES.items():
        t = threading.Thread(target=process_camera, args=(cam_id, source), daemon=True)
        t.start()
        threads.append(t)
        print(f"Started {cam_id}")

    print("\nMulti-Camera running. Press Q to quit.\n")
    cv2.namedWindow("Multi-Camera View", cv2.WINDOW_NORMAL)

    while True:
        grid = build_grid()

        with cam_lock:
            total   = sum(cam_counts.values())
            any_alr = any(cam_alerts.values())

        bar = np.zeros((40, grid.shape[1], 3), dtype=np.uint8)
        cv2.putText(bar,
                    f"TOTAL: {total} people  |  CAMERAS: {len(CAMERA_SOURCES)}  |  "
                    f"ALERT: {'YES' if any_alr else 'NO'}  |  "
                    f"{datetime.now().strftime('%H:%M:%S')}",
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    RED if any_alr else GREEN, 1)

        cv2.imshow("Multi-Camera View", np.vstack([grid, bar]))

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    running = False
    cv2.destroyAllWindows()
    print("Stopped.")


if __name__ == "__main__":
    main()
