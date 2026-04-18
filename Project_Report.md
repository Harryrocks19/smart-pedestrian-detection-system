# Smart Pedestrian Detection System
### Project Report

---

## 1. Project Overview

The **Smart Pedestrian Detection System** is a real-time computer vision application that detects, tracks, and monitors pedestrians using a live camera feed. It combines HOG-based human detection, SORT multi-object tracking, social distancing analysis, crowd alerting, face privacy blurring, and automated logging into a single unified system.

---

## 2. Objectives

- Detect pedestrians in real-time using a webcam
- Track each individual across frames with a unique ID
- Count people entering and exiting a monitored zone
- Detect social distancing violations between individuals
- Estimate the approximate distance of each person from the camera
- Blur faces to protect individual privacy
- Alert when crowd density exceeds a defined threshold
- Log detection data to CSV and save output video

---

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python 3.x | Core programming language |
| OpenCV (cv2) | Image processing, HOG detection, display |
| imutils | Frame resizing utility |
| NumPy | Numerical operations, distance calculations |
| SciPy | Hungarian algorithm for tracker assignment |
| SORT (Custom) | Multi-object tracking |
| CSV Module | Detection data logging |
| datetime / time | Timestamping and log intervals |

---

## 4. System Architecture

```
Camera Input (Webcam)
        |
        v
  Frame Preprocessing (Resize to 640px width)
        |
        v
  HOG People Detection (winStride=8x8, scale=1.05)
        |
        v
  SORT Tracker (max_age=10, min_hits=2, iou_threshold=0.3)
        |
        +---> In/Out Counting (Horizontal Line Crossing)
        |
        +---> Distance Estimation (Focal Length Method)
        |
        +---> Social Distancing Check (Euclidean Distance < 100px)
        |
        +---> Face Detection + Gaussian Blur (Privacy)
        |
        +---> Crowd Alert (People >= 5)
        |
        v
  Dashboard Overlay (People, IN, OUT, Violations, Alert, Time)
        |
        +---> CSV Log (every 5 seconds)
        +---> Video Recording (XVID .avi)
        +---> Live Display Window
```

---

## 5. Key Features

### 5.1 Pedestrian Detection
- Uses OpenCV's built-in **HOG (Histogram of Oriented Gradients)** descriptor with a pre-trained SVM people detector
- Detection confidence threshold set to `0.4` to reduce false positives
- Parameters: `winStride=(8,8)`, `padding=(16,16)`, `scale=1.05`, `finalThreshold=2`

### 5.2 Multi-Object Tracking (SORT)
- Custom implementation of the **SORT (Simple Online and Realtime Tracking)** algorithm
- Uses **IoU (Intersection over Union)** matching with the **Hungarian algorithm** (via `scipy.optimize.linear_sum_assignment`)
- Each tracked person is assigned a unique persistent ID
- Parameters: `max_age=10`, `min_hits=2`, `iou_threshold=0.3`

### 5.3 In/Out People Counting
- A horizontal counting line is drawn at the vertical center of the frame
- Tracks each person's Y-position across frames
- Crossing the line downward → **IN count** increments
- Crossing the line upward → **OUT count** increments

### 5.4 Distance Estimation
- Uses the **focal length method**:
  ```
  Distance = (Real Height × Focal Length) / Detected Height in Pixels
  ```
- Focal Length: `615 px`, Average Human Height: `1.7 m`
- Distance is displayed above each bounding box in meters

### 5.5 Social Distancing Violation Detection
- Calculates **Euclidean distance** between centers of all detected persons
- If distance < `100 pixels`, a red line is drawn between them
- Violating bounding boxes are recolored **red**
- Total violation count is shown on the dashboard

### 5.6 Face Blurring (Privacy Protection)
- Uses Haar Cascade classifier (`haarcascade_frontalface_default.xml`) to detect faces
- Applies **Gaussian Blur** (`kernel=51x51`, `sigma=30`) to each detected face region
- Ensures individual privacy in recorded footage

### 5.7 Crowd Alert
- If the number of tracked people reaches or exceeds `CROWD_LIMIT = 5`:
  - A red border is drawn around the entire frame
  - A large `!! CROWD ALERT !!` text is displayed at the center

### 5.8 Dashboard Overlay
- Semi-transparent black panel in the top-left corner displays:
  - Total people count
  - IN / OUT counts
  - Number of distancing violations
  - Alert status (YES / NO)
  - Current timestamp

### 5.9 CSV Logging
- Logs are saved every **5 seconds** to `logs/detection_log.csv`
- Each row contains: `Timestamp`, `People Count`, `Alert`

### 5.10 Video Recording
- Output video saved to `logs/output_recording.avi`
- Format: XVID codec, 20 FPS, 640px width

---

## 6. Configuration Parameters

| Parameter | Value | Description |
|---|---|---|
| CROWD_LIMIT | 5 | Minimum people count to trigger alert |
| SAFE_DISTANCE_PX | 100 | Minimum safe pixel distance between persons |
| LOG_FILE | logs/detection_log.csv | CSV log file path |
| SAVE_VIDEO | True | Enable/disable video saving |
| VIDEO_OUT_FILE | logs/output_recording.avi | Output video path |
| FOCAL_LENGTH | 615 px | Camera focal length for distance estimation |
| REAL_HEIGHT | 1.7 m | Assumed average human height |

---

## 7. Project File Structure

```
AI Insem/
├── Pedestrian_Detection.py     # Main application script
├── sort.py                     # SORT tracking algorithm
├── logs/
│   ├── detection_log.csv       # Auto-generated detection log
│   └── output_recording.avi    # Saved video output
└── img.png                     # Reference image
```

---

## 8. SORT Algorithm (sort.py)

The custom SORT implementation consists of two classes:

- **KalmanBoxTracker**: Represents a single tracked object. Stores bounding box, hit count, and loss count. Provides `update()`, `predict()`, and `get_state()` methods.
- **Sort**: Manages all active trackers. On each frame:
  1. Predicts positions of existing trackers
  2. Computes IoU matrix between predictions and new detections
  3. Uses Hungarian algorithm to find optimal assignment
  4. Updates matched trackers, creates new ones for unmatched detections
  5. Removes trackers that have been lost for more than `max_age` frames

---

## 9. How to Run

### Prerequisites
```bash
pip install opencv-python imutils numpy scipy
```

### Run the Application
```bash
python Pedestrian_Detection.py
```

### Controls
- Press `q` to quit the application
- Output logs and video are automatically saved in the `logs/` folder

---

## 10. Limitations

- HOG detector may miss people in crowded or occluded scenes
- Distance estimation assumes a fixed camera angle and average human height
- Social distancing is measured in pixels, not real-world meters
- Face blur depends on frontal face visibility
- Performance may vary based on system hardware and camera quality

---

## 11. Future Enhancements

- Replace HOG with a deep learning model (e.g., YOLOv8) for better accuracy
- Use real-world coordinate mapping for accurate distance measurement
- Add email/SMS alerts for crowd events
- Build a web dashboard for remote monitoring
- Support multiple camera feeds simultaneously
- Add re-identification to handle occlusion and re-entry

---

## 12. Conclusion

The Smart Pedestrian Detection System successfully demonstrates a real-time, multi-feature surveillance solution using classical computer vision techniques. It integrates detection, tracking, counting, distancing, privacy protection, and alerting into a single pipeline — making it suitable for public safety monitoring, retail footfall analysis, and smart city applications.

---

*Report generated for: Smart Pedestrian Detection System*  
*Language: Python | Libraries: OpenCV, SORT, NumPy, SciPy*
