import cv2
import imutils
import csv
import os
import time
import threading
import smtplib
import winsound
import requests
import numpy as np
from collections import deque
from datetime import datetime
from sort import Sort
from deepface import DeepFace
try:
    from db_manager import init_db, log_detection, log_alert, log_signal, log_anomaly, log_queue
    init_db()
    DB_ENABLED = True
except Exception:
    DB_ENABLED = False

# ── SaaS Tenant Config ────────────────────────────────────────────────────────
ACTIVE_TENANT_ID = os.environ.get("TENANT_ID", "city_pune")
try:
    from saas_config import get_tenant, get_plan
    _tenant = get_tenant(ACTIVE_TENANT_ID)
    _plan   = get_plan(ACTIVE_TENANT_ID)
    print(f"Tenant: {_tenant.get('name', ACTIVE_TENANT_ID)} | Plan: {_tenant.get('plan','basic')}")
except Exception:
    _tenant = {}
    _plan   = {}

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG — fill your details
# ═══════════════════════════════════════════════════════════════════════════════
CROWD_LIMIT        = _tenant.get("crowd_limit", 5)
SAFE_DISTANCE_PX   = 100
LOITER_SECONDS     = 5
FOCAL_LENGTH       = 615
REAL_HEIGHT        = 1.7

# Email
EMAIL_ENABLED      = False
EMAIL_SENDER       = "your_email@gmail.com"
EMAIL_PASSWORD     = "your_app_password"
EMAIL_RECEIVER     = "receiver@gmail.com"

# Telegram — get token from @BotFather, get chat_id from @userinfobot
TELEGRAM_ENABLED   = False
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# Restricted Zone — loaded from tenant config
RESTRICTED_ZONE    = _tenant.get("restricted_zone", (300, 50, 580, 300))

# Paths
LOG_FILE           = "logs/detection_log.csv"
VIDEO_OUT_FILE     = "logs/output_recording.avi"
SNAPSHOT_DIR       = "logs/snapshots"
KNOWN_FACES_DIR    = "known_faces"
SAVE_VIDEO         = True

# Cloud (Step 8) — set CLOUD_ENABLED=True and fill endpoint to push summaries
CLOUD_ENABLED      = False
CLOUD_ENDPOINT     = "https://your-cloud-endpoint/api/summary"
CLOUD_INTERVAL     = 30   # seconds between cloud pushes

# Incident Recording (Step 9)
INCIDENT_DIR       = "logs/incidents"
INCIDENT_DURATION  = 5    # seconds of video to save per incident

# Smart Traffic Signal (Step 12)
SIGNAL_PED_THRESH  = _tenant.get("signal_ped_thresh", 3)
SIGNAL_RED_HOLD    = 10   # seconds to hold RED after trigger
SIGNAL_LOG_FILE    = "logs/signal_log.csv"

# Twilio WhatsApp (Step 5)
TWILIO_ENABLED     = False
TWILIO_SID         = "your_account_sid"
TWILIO_TOKEN       = "your_auth_token"
TWILIO_FROM        = "whatsapp:+14155238886"
TWILIO_TO          = "whatsapp:+91XXXXXXXXXX"

# Multi-Camera (Step 4)
# Phone 1: http://10.211.20.90:8080  Phone 2: http://10.211.20.34:8080
CAMERA_SOURCES     = [0, "http://10.211.20.90:8080/video", "http://10.211.20.34:8080/video"]

# License Plate (Step 6)
PLATE_ENABLED      = False

# Anomaly Detection (Step 2)
ANOMALY_WINDOW     = 30
ANOMALY_THRESH     = 2.5

# Queue Detection (Step 3)
QUEUE_ZONE         = (0, 0, 320, 480)
QUEUE_DENSITY_THRESH = 4

# Object Left Behind (Step 10)
STATIC_FRAMES_THRESH = 150
# ═══════════════════════════════════════════════════════════════════════════════

os.makedirs("logs", exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(["Timestamp", "People Count", "Violations", "Alert"])

# ── Load Known Faces ──────────────────────────────────────────────────────────
known_faces = {}
for fname in os.listdir(KNOWN_FACES_DIR):
    if fname.lower().endswith((".jpg", ".png")):
        img  = cv2.imread(os.path.join(KNOWN_FACES_DIR, fname))
        name = os.path.splitext(fname)[0]
        known_faces[name] = img
print(f"Loaded {len(known_faces)} known face(s): {list(known_faces.keys())}")

# ── YOLOv8 Person Detector (replaces HOG for 10x better accuracy) ────────────
try:
    from ultralytics import YOLO as _PersonYOLO
    person_model     = _PersonYOLO("yolov8n.pt")
    PERSON_YOLO_READY = True
    print("YOLOv8 person detector loaded.")
except Exception as _e:
    person_model      = None
    PERSON_YOLO_READY = False
    print(f"YOLOv8 person detector unavailable ({_e}), falling back to HOG.")
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# ── Face Detector ─────────────────────────────────────────────────────────────
face_cascade  = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
face_recognizer = cv2.face.LBPHFaceRecognizer_create()
face_rec_trained = False

# Train face recognizer if known faces exist
if known_faces:
    train_imgs, train_labels, label_map = [], [], {}
    for idx, (name, img) in enumerate(known_faces.items()):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (100, 100))
        train_imgs.append(gray)
        train_labels.append(idx)
        label_map[idx] = name
    face_recognizer.train(train_imgs, np.array(train_labels))
    face_rec_trained = True
    print("Face recognizer trained.")

# ── SORT Tracker ──────────────────────────────────────────────────────────────
tracker = Sort(max_age=10, min_hits=2, iou_threshold=0.3)

# ── Camera ────────────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    print("Error: Camera not found.")
    exit()

frame_width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

video_writer = None
if SAVE_VIDEO:
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    video_writer = cv2.VideoWriter(VIDEO_OUT_FILE, fourcc, 20.0, (640, frame_height))

# ── State ─────────────────────────────────────────────────────────────────────
in_count         = 0
out_count        = 0
track_history    = {}
track_first_seen = {}
track_positions  = {}
heatmap          = np.zeros((frame_height, 640), dtype=np.float32)
emotion_cache    = {}
identity_cache   = {}
behavior_history = {}          # tid -> deque of (cx, cy, timestamp)
velocity_cache   = {}          # tid -> (vx, vy) px/sec
vehicle_boxes    = []          # list of (x1,y1,x2,y2,label) from YOLO
risk_indices     = set()
log_timer        = time.time()
email_sent_time  = 0
alarm_sent_time  = 0
alert_log_file   = "logs/alert_log.csv"
heatmap_log_timer = time.time()
crowd_density_map = {}         # grid cell -> count for density zones
face_blur_enabled = True       # Step 7: face blur toggle
cloud_last_push   = 0
incident_writer   = None
incident_end_time = 0
signal_state      = "GREEN"    # current signal: GREEN / YELLOW / RED
signal_red_until  = 0          # timestamp when RED expires
anomaly_baseline  = []
static_objects    = {}
plate_cache       = {}
queue_alert_time  = 0
anomaly_alert_time= 0
whatsapp_sent_time= 0

os.makedirs("logs/heatmaps", exist_ok=True)
os.makedirs(INCIDENT_DIR, exist_ok=True)
if not os.path.exists(SIGNAL_LOG_FILE):
    with open(SIGNAL_LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(["Timestamp", "Signal", "People", "Vehicles", "Risk"])
if not os.path.exists(alert_log_file):
    with open(alert_log_file, "w", newline="") as f:
        csv.writer(f).writerow(["Timestamp", "Type", "People", "Vehicles", "Risk"])
night_mode       = False
auto_night       = True
night_brightness_thresh = 60
show_heatmap     = False
show_zone        = True
show_trajectory  = True
frame_count      = 0
fps_time         = time.time()
fps              = 0

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN  = (0, 255, 0)
RED    = (0, 0, 255)
YELLOW = (0, 255, 255)
WHITE  = (255, 255, 255)
BLACK  = (0, 0, 0)
BLUE   = (255, 100, 0)
ORANGE = (0, 165, 255)
PURPLE = (255, 0, 200)


# ── Alert Functions ───────────────────────────────────────────────────────────
def send_email(count):
    if not EMAIL_ENABLED:
        return
    try:
        msg = f"Subject: CROWD ALERT\n\nCrowd limit exceeded! {count} people at {datetime.now().strftime('%H:%M:%S')}"
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg)
        print("Email sent!")
    except Exception as e:
        print(f"Email error: {e}")


def send_telegram(message, image_path=None):
    if not TELEGRAM_ENABLED:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img:
                requests.post(f"{url}/sendPhoto",
                              data={"chat_id": TELEGRAM_CHAT_ID, "caption": message},
                              files={"photo": img}, timeout=5)
        else:
            requests.post(f"{url}/sendMessage",
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
        print("Telegram sent!")
    except Exception as e:
        print(f"Telegram error: {e}")


def play_alarm():
    for _ in range(3):
        winsound.Beep(1000, 300)
        time.sleep(0.1)


# Step 5: WhatsApp via Twilio
def send_whatsapp(message):
    if not TWILIO_ENABLED:
        return
    try:
        from twilio.rest import Client
        Client(TWILIO_SID, TWILIO_TOKEN).messages.create(
            body=message, from_=TWILIO_FROM, to=TWILIO_TO)
        print("WhatsApp sent!")
    except Exception as e:
        print(f"WhatsApp error: {e}")


# Step 2: Anomaly Detection
def check_anomaly(people_count):
    anomaly_baseline.append(people_count)
    if len(anomaly_baseline) > 200:
        anomaly_baseline.pop(0)
    if len(anomaly_baseline) < ANOMALY_WINDOW:
        return False, 0.0
    import statistics
    mean = statistics.mean(anomaly_baseline)
    std  = statistics.stdev(anomaly_baseline) if len(anomaly_baseline) > 1 else 0
    if std == 0:
        return False, 0.0
    z = (people_count - mean) / std
    return z > ANOMALY_THRESH, round(z, 2)


# Step 3: Queue Detection
def check_queue(centers_list, frame_w, frame_h):
    qx1, qy1, qx2, qy2 = QUEUE_ZONE
    count = sum(1 for (cx, cy) in centers_list if qx1 < cx < qx2 and qy1 < cy < qy2)
    return count >= QUEUE_DENSITY_THRESH, count


# Step 6: License Plate Recognition
def read_plate(frame, x1, y1, x2, y2, tid):
    if not PLATE_ENABLED:
        return
    try:
        import easyocr
        if not hasattr(read_plate, "_reader"):
            read_plate._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        crop = frame[max(0,y1):y2, max(0,x1):x2]
        if crop.size == 0:
            return
        results = read_plate._reader.readtext(crop, detail=0)
        if results:
            plate_cache[tid] = results[0].upper().replace(" ", "")
    except Exception:
        pass


# Step 10: Object Left Behind Detection
def check_left_behind(vehicle_boxes_list):
    alerts = []
    current_keys = set()
    for (vx1, vy1, vx2, vy2, vlabel) in vehicle_boxes_list:
        key = f"{vx1//20}_{vy1//20}_{vx2//20}_{vy2//20}"
        current_keys.add(key)
        static_objects[key] = static_objects.get(key, 0) + 1
        if static_objects[key] >= STATIC_FRAMES_THRESH:
            alerts.append((vx1, vy1, vx2, vy2, vlabel))
    for key in list(static_objects.keys()):
        if key not in current_keys:
            del static_objects[key]
    return alerts


# ── Cloud Push (Step 8) ─────────────────────────────────────────────────────────
def push_to_cloud(payload):
    if not CLOUD_ENABLED:
        return
    try:
        requests.post(CLOUD_ENDPOINT, json=payload, timeout=5)
        print(f"Cloud push OK: {payload['timestamp']}")
    except Exception as e:
        print(f"Cloud push failed: {e}")


# ── Smart Traffic Signal (Step 12) ───────────────────────────────────────────────
def update_signal(people, vehicles, risk, ts):
    """Decide signal state based on pedestrian density + risk.
    Returns new signal state: GREEN / YELLOW / RED"""
    global signal_state, signal_red_until

    # Force RED: crowd threshold OR active collision risk
    if people >= SIGNAL_PED_THRESH or risk > 0:
        signal_state     = "RED"
        signal_red_until = ts + SIGNAL_RED_HOLD
        return signal_state

    # Hold RED until timer expires
    if ts < signal_red_until:
        signal_state = "RED"
        return signal_state

    # YELLOW: vehicles present but no crowd
    if vehicles > 0:
        signal_state = "YELLOW"
        return signal_state

    signal_state = "GREEN"
    return signal_state


def draw_signal(frame, state, x=None, y=20):
    """Draw a traffic light widget on the frame."""
    h, w = frame.shape[:2]
    x = x or w - 60
    colors = {"RED": (RED, BLACK, BLACK),
              "YELLOW": (BLACK, YELLOW, BLACK),
              "GREEN": (BLACK, BLACK, GREEN)}
    r_col, y_col, g_col = colors[state]
    cv2.rectangle(frame, (x, y), (x+40, y+110), (50, 50, 50), -1)
    cv2.rectangle(frame, (x, y), (x+40, y+110), WHITE, 1)
    cv2.circle(frame, (x+20, y+20),  14, r_col, -1)   # RED
    cv2.circle(frame, (x+20, y+55),  14, y_col, -1)   # YELLOW
    cv2.circle(frame, (x+20, y+90),  14, g_col, -1)   # GREEN
    cv2.putText(frame, state, (x-10, y+125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1)


# ── Crowd Density config ─────────────────────────────────────────────────────────────
DENSITY_GRID_COLS = 4          # divide frame into 4x3 grid
DENSITY_GRID_ROWS = 3
DENSITY_HOT_THRESH = 3         # people per cell to mark as hotspot


def compute_density_grid(centers_list, frame_w, frame_h):
    """Return dict of (col,row)->count and list of hotspot rects."""
    grid = {}
    cw = frame_w // DENSITY_GRID_COLS
    ch = frame_h // DENSITY_GRID_ROWS
    for (cx, cy) in centers_list:
        col = min(cx // cw, DENSITY_GRID_COLS - 1)
        row = min(cy // ch, DENSITY_GRID_ROWS - 1)
        grid[(col, row)] = grid.get((col, row), 0) + 1
    hotspots = []
    for (col, row), cnt in grid.items():
        if cnt >= DENSITY_HOT_THRESH:
            hotspots.append((col * cw, row * ch, (col+1)*cw, (row+1)*ch, cnt))
    return grid, hotspots


# Step 13: Predictive Trajectory
TRAJ_STEPS = 20
TRAJ_DT    = 0.1

def draw_trajectory(frame, tracked_list, frame_w, frame_h):
    for trk in tracked_list:
        tid = int(trk[4])
        vx, vy = velocity_cache.get(tid, (0, 0))
        if abs(vx) < 2 and abs(vy) < 2:
            continue
        cx = int((trk[0] + trk[2]) / 2)
        cy = int((trk[1] + trk[3]) / 2)
        pts = [(cx, cy)]
        for step in range(1, TRAJ_STEPS + 1):
            nx = max(0, min(frame_w - 1, int(cx + vx * TRAJ_DT * step)))
            ny = max(0, min(frame_h - 1, int(cy + vy * TRAJ_DT * step)))
            pts.append((nx, ny))
        for i in range(1, len(pts)):
            alpha = 1.0 - i / len(pts)
            color = (0, int(255 * alpha), int(255 * alpha))
            cv2.line(frame, pts[i-1], pts[i], color, 1)
        if len(pts) >= 4:
            cv2.arrowedLine(frame, pts[-4], pts[-1], (0, 255, 255), 2, tipLength=0.4)


# ── Accident Risk + Vehicle Detection config ─────────────────────────────────
RISK_CLOSE_PX        = 120
RISK_APPROACH_SPEED  = 40
VEHICLE_CLASSES      = {2: "Car", 3: "Motorbike", 5: "Bus", 7: "Truck"}
VEHICLE_PED_RISK_PX  = 150

try:
    from ultralytics import YOLO as _YOLO
    yolo_model   = _YOLO("yolov8n.pt")
    YOLO_ENABLED = True
    print("YOLOv8 loaded.")
except Exception:
    yolo_model   = None
    YOLO_ENABLED = False
    print("YOLOv8 not available - vehicle detection disabled.")


def compute_velocity(tid, cx, cy):
    if tid not in behavior_history or len(behavior_history[tid]) < 2:
        return 0, 0
    hist = behavior_history[tid]
    p1, p2 = hist[-2], hist[-1]
    dt = p2[2] - p1[2]
    if dt <= 0:
        return 0, 0
    velocity_cache[tid] = ((p2[0]-p1[0])/dt, (p2[1]-p1[1])/dt)
    return velocity_cache[tid]


def predict_accident_risk(tracked_list):
    risky = set()
    n = len(tracked_list)
    for i in range(n):
        for j in range(i+1, n):
            ti, tj = int(tracked_list[i][4]), int(tracked_list[j][4])
            cxi = int((tracked_list[i][0]+tracked_list[i][2])/2)
            cyi = int((tracked_list[i][1]+tracked_list[i][3])/2)
            cxj = int((tracked_list[j][0]+tracked_list[j][2])/2)
            cyj = int((tracked_list[j][1]+tracked_list[j][3])/2)
            dist = np.hypot(cxi-cxj, cyi-cyj)
            if dist > RISK_CLOSE_PX*2:
                continue
            vxi, vyi = velocity_cache.get(ti, (0, 0))
            vxj, vyj = velocity_cache.get(tj, (0, 0))
            dx, dy   = cxj-cxi, cyj-cyi
            norm     = max(np.hypot(dx, dy), 1)
            closing  = ((vxi-vxj)*dx + (vyi-vyj)*dy) / norm
            if dist < RISK_CLOSE_PX and closing > RISK_APPROACH_SPEED:
                risky.add(i); risky.add(j)
    for i in range(n):
        pcx = int((tracked_list[i][0]+tracked_list[i][2])/2)
        pcy = int((tracked_list[i][1]+tracked_list[i][3])/2)
        for (vx1, vy1, vx2, vy2, _) in vehicle_boxes:
            if np.hypot(pcx-(vx1+vx2)//2, pcy-(vy1+vy2)//2) < VEHICLE_PED_RISK_PX:
                risky.add(i)
    return risky


# ═══════════════════════════════════════════════════════════════════════════════
#  FEATURE 1 — Predictive AI (Future Position Forecasting)
# ═══════════════════════════════════════════════════════════════════════════════
PREDICT_SECONDS   = 4      # how many seconds ahead to predict
PREDICT_MIN_HIST  = 5      # minimum history points needed

def predict_future_position(tid):
    """Linear extrapolation on position history → predicted (px, py) in PREDICT_SECONDS.
    Returns None if not enough history."""
    if tid not in behavior_history or len(behavior_history[tid]) < PREDICT_MIN_HIST:
        return None
    hist = list(behavior_history[tid])
    xs = np.array([p[0] for p in hist], dtype=float)
    ys = np.array([p[1] for p in hist], dtype=float)
    ts = np.array([p[2] for p in hist], dtype=float)
    ts -= ts[0]  # normalise
    # Fit linear trend (least squares)
    if ts[-1] == 0:
        return None
    vx = np.polyfit(ts, xs, 1)[0]
    vy = np.polyfit(ts, ys, 1)[0]
    px = int(xs[-1] + vx * PREDICT_SECONDS)
    py = int(ys[-1] + vy * PREDICT_SECONDS)
    return px, py


def draw_predictions(frame, tracked_list, frame_w, frame_h):
    """Draw predicted future positions and warn if two predicted paths collide."""
    predictions = {}
    for trk in tracked_list:
        tid = int(trk[4])
        pred = predict_future_position(tid)
        if pred:
            predictions[tid] = pred
            cx = int((trk[0] + trk[2]) / 2)
            cy = int((trk[1] + trk[3]) / 2)
            # Dashed trajectory line
            cv2.arrowedLine(frame, (cx, cy), pred, (0, 200, 255), 2, tipLength=0.2)
            cv2.circle(frame, pred, 6, (0, 200, 255), -1)
            cv2.putText(frame, f"~{PREDICT_SECONDS}s", (pred[0]+4, pred[1]-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 255), 1)
    # Predict collision between any two future positions
    pids = list(predictions.keys())
    for i in range(len(pids)):
        for j in range(i+1, len(pids)):
            d = np.hypot(predictions[pids[i]][0] - predictions[pids[j]][0],
                         predictions[pids[i]][1] - predictions[pids[j]][1])
            if d < SAFE_DISTANCE_PX:
                mid = ((predictions[pids[i]][0]+predictions[pids[j]][0])//2,
                       (predictions[pids[i]][1]+predictions[pids[j]][1])//2)
                cv2.putText(frame, "PREDICTED COLLISION!", (mid[0]-60, mid[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
    return len(predictions)


# ═══════════════════════════════════════════════════════════════════════════════
#  FEATURE 2 — Multi-Camera Re-ID (Color Histogram Appearance Matching)
# ═══════════════════════════════════════════════════════════════════════════════
REID_HIST_BINS    = 32
REID_MATCH_THRESH = 0.55   # cosine similarity threshold
REID_LOG_FILE     = "logs/reid_log.csv"

if not os.path.exists(REID_LOG_FILE):
    with open(REID_LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(["Timestamp", "Camera", "TrackID", "MatchedID", "Similarity"])

reid_gallery = {}   # global_id -> color histogram (np.array)
reid_id_map  = {}   # local tid -> global_id
reid_counter = [0]  # mutable counter


def extract_color_hist(frame, x1, y1, x2, y2):
    """Extract normalised HSV color histogram for a bounding box crop."""
    crop = frame[max(0,y1):max(0,y2), max(0,x1):max(0,x2)]
    if crop.size == 0:
        return None
    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [REID_HIST_BINS, REID_HIST_BINS], [0,180,0,256])
    cv2.normalize(hist, hist)
    return hist.flatten()


def reid_assign(tid, hist, camera_id="CAM_A"):
    """Assign or match a global Re-ID to a local track."""
    if hist is None:
        return tid, 0.0
    best_gid, best_sim = None, 0.0
    for gid, ghist in reid_gallery.items():
        sim = float(np.dot(hist, ghist) / (np.linalg.norm(hist)*np.linalg.norm(ghist)+1e-6))
        if sim > best_sim:
            best_sim, best_gid = sim, gid
    if best_sim >= REID_MATCH_THRESH and best_gid is not None:
        reid_id_map[tid] = best_gid
        reid_gallery[best_gid] = hist  # update gallery
        return best_gid, best_sim
    else:
        reid_counter[0] += 1
        new_gid = reid_counter[0]
        reid_gallery[new_gid] = hist
        reid_id_map[tid] = new_gid
        return new_gid, 0.0


# ── Behavior Analysis ─────────────────────────────────────────────────────────
# Thresholds (pixels/sec)
SPEED_RUNNING  = 80
SPEED_WALKING  = 15
JAYWALK_LINE_BAND  = 40   # px around LINE_Y considered jaywalking zone

def classify_behavior(tid, cx, cy, line_y):
    """Returns (behavior_label, pixel_speed)"""
    if tid not in behavior_history:
        behavior_history[tid] = deque(maxlen=10)
    behavior_history[tid].append((cx, cy, time.time()))

    hist = behavior_history[tid]
    if len(hist) < 3:
        return "...", 0

    # Speed = distance over time using oldest & newest sample
    oldest = hist[0]
    newest = hist[-1]
    dt = newest[2] - oldest[2]
    if dt <= 0:
        return "Standing", 0

    dist = np.hypot(newest[0] - oldest[0], newest[1] - oldest[1])
    speed = dist / dt  # px/sec

    # Sudden movement: large jump between last two frames
    prev = hist[-2]
    sudden_dist = np.hypot(newest[0] - prev[0], newest[1] - prev[1])
    if sudden_dist > 40:
        return "Sudden Move!", speed

    # Jaywalking: moving horizontally (x changes more than y) near count line
    dx = abs(newest[0] - oldest[0])
    dy = abs(newest[1] - oldest[1])
    near_line = abs(cy - line_y) < JAYWALK_LINE_BAND
    if near_line and dx > dy * 1.5 and speed > SPEED_WALKING:
        return "Jaywalking!", speed

    if speed > SPEED_RUNNING:
        return "Running", speed
    elif speed > SPEED_WALKING:
        return "Walking", speed
    else:
        return "Standing", speed


def analyze_emotion(face_img, tid):
    try:
        result = DeepFace.analyze(face_img, actions=["emotion", "age", "gender"],
                                  enforce_detection=False, silent=True)
        emotion_cache[tid] = {
            "emotion": result[0]["dominant_emotion"],
            "age":     result[0]["age"],
            "gender":  result[0]["dominant_gender"]
        }
    except:
        pass


def recognize_face(face_gray, tid):
    if not face_rec_trained:
        identity_cache[tid] = "Unknown"
        return
    try:
        resized = cv2.resize(face_gray, (100, 100))
        label, confidence = face_recognizer.predict(resized)
        identity_cache[tid] = label_map[label] if confidence < 80 else "Unknown"
    except:
        identity_cache[tid] = "Unknown"


print("Camera opened.")
print("Keys: Q=quit | N=night | H=heatmap | S=snapshot | Z=zone | F=fullscreen | B=face blur")

fullscreen = False

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame       = imutils.resize(frame, width=640)
    h, w        = frame.shape[:2]
    LINE_Y      = h // 2
    frame_count += 1

    # ── FPS Calculation ───────────────────────────────────────────────────────
    if frame_count % 10 == 0:
        fps = 10 / (time.time() - fps_time)
        fps_time = time.time()

    # ── Night Vision ──────────────────────────────────────────────────────────
    # Step 14: Night Vision Auto Enhancement
    gray_lum   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray_lum))
    if auto_night:
        if brightness < night_brightness_thresh:
            night_mode = True
        elif brightness >= night_brightness_thresh + 10:
            night_mode = False
    if night_mode:
        clahe  = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enh    = clahe.apply(gray_lum)
        frame  = cv2.cvtColor(enh, cv2.COLOR_GRAY2BGR)
        frame[:, :, 1] = cv2.add(frame[:, :, 1], 20)

    display = frame.copy()

    # ── Restricted Zone ───────────────────────────────────────────────────────
    zx1, zy1, zx2, zy2 = RESTRICTED_ZONE
    if show_zone:
        overlay_zone = display.copy()
        cv2.rectangle(overlay_zone, (zx1, zy1), (zx2, zy2), (0, 0, 180), -1)
        cv2.addWeighted(overlay_zone, 0.25, display, 0.75, 0, display)
        cv2.rectangle(display, (zx1, zy1), (zx2, zy2), RED, 2)
        cv2.putText(display, "RESTRICTED", (zx1+4, zy1+18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, RED, 2)

    # ── Person Detection (YOLOv8 primary, HOG fallback) ─────────────────────
    detections = []
    if PERSON_YOLO_READY:
        try:
            yolo_persons = person_model(frame, classes=[0], verbose=False)[0]
            for box in yolo_persons.boxes:
                conf = float(box.conf[0])
                if conf > 0.4:
                    px1, py1, px2, py2 = map(int, box.xyxy[0])
                    detections.append([px1, py1, px2, py2, conf])
        except Exception:
            pass
    else:
        (regions, weights) = hog.detectMultiScale(frame, winStride=(8, 8),
                                                  padding=(16, 16), scale=1.05)
        for (x, y, bw, bh), weight in zip(regions, weights):
            if weight > 0.4:
                detections.append([x, y, x+bw, y+bh, float(weight)])

    detections = np.array(detections) if detections else np.empty((0, 5))

    # ── SORT Tracking ─────────────────────────────────────────────────────────
    tracked      = tracker.update(detections)
    centers      = []
    people_count = len(tracked)
    now          = time.time()
    zone_intruders = 0

    for trk in tracked:
        x1, y1, x2, y2, tid = int(trk[0]), int(trk[1]), int(trk[2]), int(trk[3]), int(trk[4])
        cx, cy = (x1+x2)//2, (y1+y2)//2
        centers.append((cx, cy))

        # ── In/Out Counting ───────────────────────────────────────────────────
        if tid in track_history:
            prev_y = track_history[tid]
            if prev_y < LINE_Y and cy >= LINE_Y:
                in_count += 1
            elif prev_y > LINE_Y and cy <= LINE_Y:
                out_count += 1
        track_history[tid] = cy

        if tid not in track_first_seen:
            track_first_seen[tid] = now
        track_positions[tid] = (cx, cy)

        # ── Dwell Time ────────────────────────────────────────────────────────
        dwell    = now - track_first_seen[tid]
        loitering = dwell > LOITER_SECONDS
        dwell_text = f"{int(dwell)}s"

        # ── Speed ─────────────────────────────────────────────────────────────
        speed_text = ""
        if tid in track_history:
            dy = abs(cy - track_history.get(tid, cy))
            if dy > 0:
                speed_text = f"{dy*30/100:.1f}km/h"

        # ── Distance ──────────────────────────────────────────────────────────
        ph = y2 - y1
        dist_text = f"{(REAL_HEIGHT*FOCAL_LENGTH/ph):.1f}m" if ph > 0 else ""

        # ── Restricted Zone Check ─────────────────────────────────────────────
        in_zone = zx1 < cx < zx2 and zy1 < cy < zy2
        if in_zone:
            zone_intruders += 1

        # ── Heatmap ───────────────────────────────────────────────────────────
        if 0 <= cy < h and 0 <= cx < w:
            cv2.circle(heatmap, (cx, cy), 20, 1, -1)

        # ── Face Analysis (every 30 frames) ───────────────────────────────────
        if frame_count % 30 == 0:
            pad  = 10
            fx1, fy1 = max(0, x1-pad), max(0, y1-pad)
            fx2, fy2 = min(w, x2+pad), min(h, y2+pad)
            crop = frame[fy1:fy2, fx1:fx2]
            if crop.size > 0:
                threading.Thread(target=analyze_emotion, args=(crop.copy(), tid), daemon=True).start()
                gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                threading.Thread(target=recognize_face, args=(gray_crop.copy(), tid), daemon=True).start()
                threading.Thread(target=read_plate, args=(frame.copy(), x1, y1, x2, y2, tid), daemon=True).start()

        # ── Re-ID (Feature 2) ─────────────────────────────────────────────────
        if frame_count % 15 == 0:
            hist_reid = extract_color_hist(frame, x1, y1, x2, y2)
            gid, sim  = reid_assign(tid, hist_reid)
            if sim >= REID_MATCH_THRESH:
                with open(REID_LOG_FILE, "a", newline="") as rf:
                    csv.writer(rf).writerow([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "CAM_A", tid, gid, f"{sim:.2f}"
                    ])
        gid = reid_id_map.get(tid, tid)

        # ── Behavior + Velocity ───────────────────────────────────────────────
        behavior, px_speed = classify_behavior(tid, cx, cy, LINE_Y)
        compute_velocity(tid, cx, cy)

        # ── Box Color Logic ───────────────────────────────────────────────────
        identity = identity_cache.get(tid, "?")
        if in_zone:
            box_color = PURPLE
        elif loitering:
            box_color = ORANGE
        elif identity not in ("?", "Unknown"):
            box_color = GREEN
        else:
            box_color = YELLOW

        cv2.rectangle(display, (x1, y1), (x2, y2), box_color, 2)

        # ── Labels ────────────────────────────────────────────────────────────
        top_label = f"ID:{tid} {dist_text} {dwell_text}"
        if in_zone:
            top_label += " INTRUDER!"
        elif loitering:
            top_label += " LOITER!"

        # Behavior label (shown above box)
        b_color = RED if behavior in ("Running", "Jaywalking!", "Sudden Move!") else GREEN
        cv2.putText(display, behavior, (x1, y1-22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, b_color, 1)
        cv2.putText(display, top_label, (x1, y1-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1)

        # Identity label + Global Re-ID
        id_color = GREEN if identity not in ("?", "Unknown") else RED
        cv2.putText(display, identity, (x1, y2+14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, id_color, 1)
        cv2.putText(display, f"GID:{gid}", (x1, y2+28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 255, 180), 1)

        # Emotion label
        if tid in emotion_cache:
            ec = emotion_cache[tid]
            cv2.putText(display, f"{ec['emotion']} {ec['age']}y {ec['gender']}",
                        (x1, y2+28), cv2.FONT_HERSHEY_SIMPLEX, 0.38, YELLOW, 1)

        cv2.circle(display, (cx, cy), 4, YELLOW, -1)
        if tid in plate_cache:
            cv2.putText(display, f"Plate:{plate_cache[tid]}", (x1, y2+42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)

    # ── Vehicle Detection (YOLOv8) ──────────────────────────────────────────
    # Step 13: Predictive trajectories
    if show_trajectory:
        draw_trajectory(display, tracked, w, h)

    vehicle_boxes.clear()
    if YOLO_ENABLED and frame_count % 5 == 0:
        try:
            results = yolo_model(frame, verbose=False)[0]
            for box in results.boxes:
                cls = int(box.cls[0])
                if cls in VEHICLE_CLASSES:
                    bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                    vehicle_boxes.append((bx1, by1, bx2, by2, VEHICLE_CLASSES[cls]))
        except Exception:
            pass
    for (vx1, vy1, vx2, vy2, vlabel) in vehicle_boxes:
        cv2.rectangle(display, (vx1, vy1), (vx2, vy2), ORANGE, 2)
        cv2.putText(display, vlabel, (vx1, vy1-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, ORANGE, 1)

    # Step 10: Object Left Behind
    left_behind = check_left_behind(vehicle_boxes)
    for (lx1, ly1, lx2, ly2, _) in left_behind:
        cv2.rectangle(display, (lx1, ly1), (lx2, ly2), (0, 0, 255), 3)
        cv2.putText(display, "LEFT BEHIND!", (lx1, ly1-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Step 2: Anomaly Detection
    is_anomaly, z_score = check_anomaly(people_count)
    if is_anomaly:
        cv2.putText(display, f"!! ANOMALY z={z_score} !!",
                    (w//2-160, h//2+150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    # Step 3: Queue Detection
    is_queue, queue_count = check_queue(centers, w, h)
    if is_queue:
        qx1, qy1, qx2, qy2 = QUEUE_ZONE
        ov_q = display.copy()
        cv2.rectangle(ov_q, (qx1, qy1), (qx2, qy2), (255, 165, 0), -1)
        cv2.addWeighted(ov_q, 0.2, display, 0.8, 0, display)
        cv2.rectangle(display, (qx1, qy1), (qx2, qy2), (255, 165, 0), 2)
        cv2.putText(display, f"QUEUE: {queue_count} people",
                    (qx1+4, qy1+22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)

    # ── Predictive AI — draw future trajectories (Feature 1) ──────────────
    pred_count = draw_predictions(display, tracked, w, h)

    # ── Accident Risk Prediction ──────────────────────────────────────────────
    risk_indices = predict_accident_risk(tracked)
    for ri in risk_indices:
        trk = tracked[ri]
        rx1, ry1, rx2, ry2 = int(trk[0]), int(trk[1]), int(trk[2]), int(trk[3])
        cv2.rectangle(display, (rx1-3, ry1-3), (rx2+3, ry2+3), (0, 100, 255), 3)
        cv2.putText(display, "HIGH RISK", (rx1, ry1-36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 100, 255), 2)
    if risk_indices:
        cv2.putText(display, f"!! COLLISION RISK: {len(risk_indices)} !!",
                    (w//2-170, h//2+100), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 100, 255), 2)

    # ── Social Distancing ─────────────────────────────────────────────────────
    violations = set()
    for i in range(len(centers)):
        for j in range(i+1, len(centers)):
            d = np.linalg.norm(np.array(centers[i]) - np.array(centers[j]))
            if d < SAFE_DISTANCE_PX:
                violations.add(i)
                violations.add(j)
                cv2.line(display, centers[i], centers[j], RED, 2)

    for idx, trk in enumerate(tracked):
        if idx in violations:
            cv2.rectangle(display, (int(trk[0]), int(trk[1])),
                          (int(trk[2]), int(trk[3])), RED, 2)

    # ── Face Blur (Step 7) ───────────────────────────────────────────────────
    if face_blur_enabled:
        gray_fb = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces   = face_cascade.detectMultiScale(gray_fb, 1.1, 5, minSize=(30, 30))
        for (fx, fy, fw, fh) in faces:
            roi = display[fy:fy+fh, fx:fx+fw]
            if roi.size > 0:
                display[fy:fy+fh, fx:fx+fw] = cv2.GaussianBlur(roi, (51, 51), 30)
        # Show blur status
        cv2.putText(display, f"FaceBlur: ON ({len(faces)})",
                    (w-160, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, GREEN, 1)
    else:
        cv2.putText(display, "FaceBlur: OFF",
                    (w-130, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, RED, 1)

    # ── Crowd Density Grid (Step 6) ──────────────────────────────────────────
    _, hotspots = compute_density_grid(centers, w, h)
    for (hx1, hy1, hx2, hy2, hcnt) in hotspots:
        ov = display.copy()
        cv2.rectangle(ov, (hx1, hy1), (hx2, hy2), (0, 0, 255), -1)
        cv2.addWeighted(ov, 0.25, display, 0.75, 0, display)
        cv2.rectangle(display, (hx1, hy1), (hx2, hy2), (0, 0, 255), 2)
        cv2.putText(display, f"HOT:{hcnt}", (hx1+4, hy1+18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1)

    # ── Counting Line ─────────────────────────────────────────────────────────
    cv2.line(display, (0, LINE_Y), (w, LINE_Y), BLUE, 2)
    cv2.putText(display, "COUNT LINE", (5, LINE_Y-6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, BLUE, 1)

    # ── Crowd + Zone Alert ────────────────────────────────────────────────────
    alert = people_count >= CROWD_LIMIT or zone_intruders > 0 or bool(risk_indices)
    if people_count >= CROWD_LIMIT:
        cv2.rectangle(display, (0, 0), (w, h), RED, 6)
        cv2.putText(display, "!! CROWD ALERT !!", (w//2-150, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, RED, 3)

    if zone_intruders > 0:
        cv2.putText(display, f"!! ZONE BREACH: {zone_intruders} !!", (w//2-160, h//2+50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, PURPLE, 3)

    # ── Smart Alert System ─────────────────────────────────────────────────────
    alert_type = None
    if people_count >= CROWD_LIMIT:  alert_type = "CROWD"
    elif zone_intruders > 0:         alert_type = "ZONE_BREACH"
    elif risk_indices:               alert_type = "COLLISION_RISK"

    if alert and now - alarm_sent_time > 10:
        threading.Thread(target=play_alarm, daemon=True).start()
        alarm_sent_time = now

    if alert and now - email_sent_time > 60:
        snap_path = f"{SNAPSHOT_DIR}/alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(snap_path, display)
        msg = (f"ALERT [{alert_type}] People:{people_count} "
               f"Vehicles:{len(vehicle_boxes)} Risk:{len(risk_indices)} "
               f"Zone:{zone_intruders} Time:{datetime.now().strftime('%H:%M:%S')}")
        threading.Thread(target=send_email, args=(people_count,), daemon=True).start()
        threading.Thread(target=send_telegram, args=(msg, snap_path), daemon=True).start()
        threading.Thread(target=send_whatsapp, args=(msg,), daemon=True).start()
        # Log alert to CSV + DB
        with open(alert_log_file, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                alert_type, people_count, len(vehicle_boxes), len(risk_indices)
            ])
        if DB_ENABLED:
            log_alert(alert_type, people_count, len(vehicle_boxes), len(risk_indices))
        email_sent_time = now

    if is_anomaly and DB_ENABLED:
        log_anomaly(z_score, people_count)
    if is_anomaly and now - anomaly_alert_time > 60:
        threading.Thread(target=send_whatsapp,
            args=(f"ANOMALY! Z={z_score} People:{people_count} {datetime.now().strftime('%H:%M:%S')}",),
            daemon=True).start()
        anomaly_alert_time = now

    if is_queue and DB_ENABLED:
        log_queue(queue_count)
    if is_queue and now - queue_alert_time > 60:
        threading.Thread(target=send_whatsapp,
            args=(f"QUEUE ALERT! {queue_count} people in queue zone {datetime.now().strftime('%H:%M:%S')}",),
            daemon=True).start()
        queue_alert_time = now

    # ── Dashboard Overlay ─────────────────────────────────────────────────────
    overlay = display.copy()
    cv2.rectangle(overlay, (0, 0), (275, 220), BLACK, -1)
    cv2.addWeighted(overlay, 0.5, display, 0.5, 0, display)

    cv2.putText(display, f"FPS        : {fps:.1f}",              (10, 22),  cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE,  1)
    cv2.putText(display, f"People     : {people_count}",         (10, 44),  cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE,  2)
    cv2.putText(display, f"IN         : {in_count}",             (10, 66),  cv2.FONT_HERSHEY_SIMPLEX, 0.55, GREEN,  2)
    cv2.putText(display, f"OUT        : {out_count}",            (10, 88),  cv2.FONT_HERSHEY_SIMPLEX, 0.55, RED,    2)
    cv2.putText(display, f"Violations : {len(violations)}",      (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, YELLOW, 2)
    cv2.putText(display, f"Zone Breach: {zone_intruders}",       (10, 132), cv2.FONT_HERSHEY_SIMPLEX, 0.55, PURPLE, 2)
    cv2.putText(display, f"Alert      : {'YES' if alert else 'NO'}", (10, 154), cv2.FONT_HERSHEY_SIMPLEX, 0.55, RED if alert else GREEN, 2)
    cv2.putText(display, f"Night      : {'ON' if night_mode else 'OFF'}", (10, 176), cv2.FONT_HERSHEY_SIMPLEX, 0.45, YELLOW, 1)
    cv2.putText(display, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (10, 198), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1)

    # Behavior summary counts
    behaviors_this_frame = [classify_behavior(int(t[4]), int((t[0]+t[2])//2), int((t[1]+t[3])//2), LINE_Y)[0] for t in tracked]
    running_count  = behaviors_this_frame.count("Running")
    jaywalk_count  = behaviors_this_frame.count("Jaywalking!")
    sudden_count   = behaviors_this_frame.count("Sudden Move!")
    overlay = display.copy()
    cv2.rectangle(overlay, (0, 220), (275, 430), BLACK, -1)
    cv2.addWeighted(overlay, 0.5, display, 0.5, 0, display)
    cv2.putText(display, f"Running    : {running_count}",  (10, 232), cv2.FONT_HERSHEY_SIMPLEX, 0.50, RED,    1)
    cv2.putText(display, f"Jaywalking : {jaywalk_count}",  (10, 252), cv2.FONT_HERSHEY_SIMPLEX, 0.50, ORANGE, 1)
    cv2.putText(display, f"Sudden Mv  : {sudden_count}",   (10, 272), cv2.FONT_HERSHEY_SIMPLEX, 0.50, YELLOW, 1)
    cv2.putText(display, f"Vehicles   : {len(vehicle_boxes)}", (10, 292), cv2.FONT_HERSHEY_SIMPLEX, 0.50, ORANGE, 1)
    cv2.putText(display, f"Risk       : {len(risk_indices)}",  (10, 312), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 100, 255), 1)
    cv2.putText(display, f"Hotspots   : {len(hotspots)}",       (10, 332), cv2.FONT_HERSHEY_SIMPLEX, 0.50, RED,           1)
    sig_color = GREEN if signal_state == "GREEN" else (YELLOW if signal_state == "YELLOW" else RED)
    cv2.putText(display, f"Signal     : {signal_state}",         (10, 352), cv2.FONT_HERSHEY_SIMPLEX, 0.50, sig_color,     2)
    cv2.putText(display, f"Predicted  : {pred_count}",          (10, 372), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 200, 255), 1)
    cv2.putText(display, f"Re-IDs     : {len(reid_gallery)}",   (10, 392), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 255, 180), 1)
    an_color = (0, 255, 255) if is_anomaly else GREEN
    cv2.putText(display, f"Anomaly    : {'YES z='+str(z_score) if is_anomaly else 'NO'}", (10, 412), cv2.FONT_HERSHEY_SIMPLEX, 0.45, an_color, 1)
    qu_color = (255, 165, 0) if is_queue else GREEN
    cv2.putText(display, f"Queue      : {queue_count} {'ALERT' if is_queue else 'OK'}", (10, 432), cv2.FONT_HERSHEY_SIMPLEX, 0.45, qu_color, 1)
    cv2.putText(display, f"LeftBehind : {len(left_behind)}", (10, 452), cv2.FONT_HERSHEY_SIMPLEX, 0.45, RED if left_behind else GREEN, 1)

    # ── Heatmap Overlay ─────────────────────────────────────────────────────────
    if show_heatmap:
        hmap  = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        hmap  = cv2.applyColorMap(hmap, cv2.COLORMAP_JET)
        hmap  = cv2.resize(hmap, (w, h))
        display = cv2.addWeighted(display, 0.6, hmap, 0.4, 0)

    # ── Heatmap Analytics: auto-save hourly snapshot ────────────────────────
    if time.time() - heatmap_log_timer >= 3600:
        ts   = datetime.now().strftime("%Y%m%d_%H%M")
        hsnap = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        cv2.imwrite(f"logs/heatmaps/heatmap_{ts}.jpg",
                    cv2.applyColorMap(hsnap, cv2.COLORMAP_JET))
        heatmap_log_timer = time.time()
        print(f"Heatmap snapshot saved: logs/heatmaps/heatmap_{ts}.jpg")

    # ── Smart Traffic Signal (Step 12) ───────────────────────────────────────────
    prev_signal = signal_state
    update_signal(people_count, len(vehicle_boxes), len(risk_indices), now)
    draw_signal(display, signal_state)
    # Log signal change
    if signal_state != prev_signal:
        with open(SIGNAL_LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                signal_state, people_count, len(vehicle_boxes), len(risk_indices)
            ])
        if DB_ENABLED:
            log_signal(signal_state, people_count, len(vehicle_boxes), len(risk_indices))
        print(f"Signal changed: {prev_signal} -> {signal_state}")

    # ── Incident Recording (Step 9) ─────────────────────────────────────────────
    if alert and incident_writer is None:
        inc_path = f"{INCIDENT_DIR}/incident_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
        fourcc_i = cv2.VideoWriter_fourcc(*"XVID")
        incident_writer  = cv2.VideoWriter(inc_path, fourcc_i, 20.0, (w, h))
        incident_end_time = now + INCIDENT_DURATION
        print(f"Incident recording started: {inc_path}")
    if incident_writer is not None:
        incident_writer.write(display)
        if now >= incident_end_time:
            incident_writer.release()
            incident_writer  = None
            incident_end_time = 0
            print("Incident clip saved.")

    # ── Cloud Push (Step 8) ─────────────────────────────────────────────────
    if now - cloud_last_push >= CLOUD_INTERVAL:
        payload = {
            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "people":     people_count,
            "vehicles":   len(vehicle_boxes),
            "violations": len(violations),
            "risk":       len(risk_indices),
            "zone_breach":zone_intruders,
            "alert":      alert,
            "alert_type": alert_type if alert else None,
            "hotspots":   len(hotspots)
        }
        threading.Thread(target=push_to_cloud, args=(payload,), daemon=True).start()
        cloud_last_push = now

    # ── CSV Log ───────────────────────────────────────────────────────────────
    if time.time() - log_timer >= 5:
        with open(LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                people_count, len(violations), "YES" if alert else "NO",
                len(vehicle_boxes), len(risk_indices)
            ])
        if DB_ENABLED:
            log_detection(people_count, len(violations), len(vehicle_boxes), len(risk_indices), "YES" if alert else "NO")
        log_timer = time.time()

    # ── Save Video ────────────────────────────────────────────────────────────
    if SAVE_VIDEO and video_writer:
        video_writer.write(display)

    # ── Show ──────────────────────────────────────────────────────────────────
    if fullscreen:
        cv2.setWindowProperty("Smart Pedestrian Detection", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("Smart Pedestrian Detection", display)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('n'):
        auto_night = not auto_night
        if not auto_night:
            night_mode = not night_mode
        print(f"Auto night: {'ON' if auto_night else 'OFF'}")
    elif key == ord('h'):
        show_heatmap = not show_heatmap
    elif key == ord('z'):
        show_zone = not show_zone
    elif key == ord('f'):
        fullscreen = not fullscreen
        if not fullscreen:
            cv2.setWindowProperty("Smart Pedestrian Detection", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
    elif key == ord('b'):
        face_blur_enabled = not face_blur_enabled
        print(f"Face blur: {'ON' if face_blur_enabled else 'OFF'}")
    elif key == ord('t'):
        show_trajectory = not show_trajectory
        print(f"Trajectory: {'ON' if show_trajectory else 'OFF'}")
    elif key == ord('s'):
        snap = f"{SNAPSHOT_DIR}/manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(snap, display)
        print(f"Snapshot saved: {snap}")

# ── Cleanup ───────────────────────────────────────────────────────────────────
cap.release()
if video_writer:
    video_writer.release()
if incident_writer:
    incident_writer.release()
cv2.destroyAllWindows()

hmap = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
cv2.imwrite("logs/final_heatmap.jpg", cv2.applyColorMap(hmap, cv2.COLORMAP_JET))

# Save final heatmap with timestamp
ts_end = datetime.now().strftime("%Y%m%d_%H%M")
cv2.imwrite(f"logs/heatmaps/heatmap_final_{ts_end}.jpg",
            cv2.applyColorMap(hmap, cv2.COLORMAP_JET))
print("Session ended. All outputs saved in logs/ folder.")



# python Pedestrian_Detection.py for main detection 
# streamlit run dashboard.py for web dashboard 
# python register_face.py  for your face register 

''' 1. Live Pedestrian Detection

"System uses HOG algorithm to detect people from live camera. Boxes appear around each person automatically."

2. Person Tracking with ID

"Each person gets a unique ID like ID:1, ID:2 using SORT algorithm. ID stays same even if person moves."

3. People IN/OUT Counter

"There is a blue line on screen. When person crosses it, IN or OUT count increases. Press nothing — fully automatic."

4. Social Distancing

"If two people come too close, a red line appears between them and box turns red. Violation count shown on screen."

5. Face Recognition

"First run python register_face.py to save your face. Then system shows your name in green. Unknown person shows red Unknown."

6. Restricted Zone Alert

"Red shaded area on screen is restricted zone. If anyone enters it, purple box appears with INTRUDER alert and alarm beeps."

7. Emotion + Age + Gender

"DeepFace AI detects your emotion like happy/sad, age like 22y and gender automatically below each person box."

8. Night Vision Mode

"Press N key to turn on night vision. Screen becomes enhanced for low light. Press N again to turn off."

9. Heatmap

"Press H key to see heatmap. It shows colored overlay where people spent most time. Red = most crowded area."

10. Web Dashboard

"Run streamlit run dashboard.py and open http://localhost:8501 in browser. Shows live count, charts, snapshots and alert history."

Bonus Keys to Show:

Key	What happens
N	Night vision on/off
H	Heatmap on/off
S	Save snapshot photo
Z	Show/hide restricted zone
F	Fullscreen on/off
Q	Quit '''

''' # Main detection (single camera)
python Pedestrian_Detection.py

# Multi-camera (3 cameras)
python multi_camera.py

# Web dashboard
streamlit run dashboard.py

# Flutter API server
python api_server.py

# Generate PDF report
python pdf_report.py

# Initialize database
python db_manager.py
 '''