# ~/ppe-pi/pi_ppe_face_web_fast.py
#
# Local WLAN stream:
# http://RASPBERRY_PI_IP:5000
#
# Required local NCNN model folders:
# ~/ppe-pi/models/ppe_yolo26n_ncnn_model/
# ~/ppe-pi/models/face_yolo11n_ncnn_model/
#
# No model downloading. No Hugging Face needed on the Pi.

import base64
import math
import threading
import time
from pathlib import Path

import cv2
import requests
from flask import Flask, Response, jsonify, render_template_string
from ultralytics import YOLO


# -------------------------------------------------
# Configuration
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
MAX_PROCESS_FPS = 30

# NCNN model FOLDERS, not .pt files
PPE_MODEL_PATH = MODEL_DIR / "ppe_yolo26n_ncnn_model"
YUNET_MODEL_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"

CAMERA_INDEX = 0  # default webcam

# Lower resolution = less delay / faster inference
CAMERA_WIDTH = 480
CAMERA_HEIGHT = 360

# Keep these equal to the NCNN export sizes
PPE_IMGSZ = 640
FACE_IMGSZ = 640

PPE_CONF = 0.35
FACE_CONF = 0.35

ENABLE_FACE = True

BACKEND_URL = "http://localhost:5000/violations"
VIOLATION_COOLDOWN = 10  # seconds between events of the same violation type

# Lower quality reduces WLAN bandwidth and JPEG encoding time
JPEG_QUALITY = 60

# PPE model class IDs:
# 0 = Hardhat, 5 = Person, 7 = Safety Vest
PPE_CLASSES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

PPE_LABELS = {
    0: "hardhat",
    1: "mask",
    2: "no-hardhat",
    3: "no-mask",
    4: "no-safety-vest",
    5: "person",
    6: "safety-cone",
    7: "safety-vest",
    8: "machinery",
    9: "utility-pole",
    10: "vehicle",
}

COLORS = {
    "hardhat": (0, 165, 255),
    "mask": (255, 255, 0),
    "no-hardhat": (0, 0, 255),
    "no-mask": (0, 0, 180),
    "no-safety-vest": (0, 0, 255),
    "person": (0, 220, 0),
    "safety-cone": (0, 140, 255),
    "safety-vest": (255, 180, 0),
    "face": (255, 0, 255),
}


# -------------------------------------------------
# Shared stream state
# -------------------------------------------------

app = Flask(__name__)

state_lock = threading.Lock()
violation_lock = threading.Lock()
violation_last_sent: dict = {}  # violation_type -> last sent timestamp

latest_jpeg = None
latest_data = {
    "status": "starting",
    "frame_id": 0,
    "detections": [],
}


# -------------------------------------------------
# Camera reader: always keep newest frame only
# -------------------------------------------------

class LatestFrameCamera:
    def __init__(self, index, width, height):
        self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)

        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(index)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open camera source={index}. "
                "Try CAMERA_INDEX = 0 or 2."
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.lock = threading.Lock()
        self.latest_frame = None
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
        )
        self.thread.start()

    def _reader_loop(self):
        while self.running:
            ok, frame = self.cap.read()

            if not ok:
                time.sleep(0.01)
                continue

            with self.lock:
                self.latest_frame = frame

    def get_latest(self):
        with self.lock:
            if self.latest_frame is None:
                return None

            return self.latest_frame.copy()

    def stop(self):
        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=2)

        self.cap.release()


# -------------------------------------------------
# Helper functions
# -------------------------------------------------

def require_models():
    missing = []

    if not PPE_MODEL_PATH.is_dir():
        missing.append(str(PPE_MODEL_PATH))

    if ENABLE_FACE and not YUNET_MODEL_PATH.is_file():
        missing.append(str(YUNET_MODEL_PATH))

    if missing:
        raise FileNotFoundError(
            "Missing NCNN model folder(s):\n- "
            + "\n- ".join(missing)
        )


def safe_box(box, frame_width, frame_height):
    coords = box.xyxy[0].tolist()
    if any(math.isnan(v) or math.isinf(v) for v in coords):
        return None
    x1, y1, x2, y2 = map(int, coords)

    x1 = max(0, min(x1, frame_width - 1))
    y1 = max(0, min(y1, frame_height - 1))
    x2 = max(0, min(x2, frame_width - 1))
    y2 = max(0, min(y2, frame_height - 1))

    return x1, y1, x2, y2


def draw_box(image, x1, y1, x2, y2, label, confidence, color=None):
    if color is None:
        color = COLORS.get(label, (255, 255, 255))

    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

    cv2.putText(
        image,
        f"{label} {confidence:.2f}",
        (x1, max(20, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        2,
    )


def boxes_overlap(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def send_violation(vtype, frame_jpeg_bytes, person_box, head_box=None):
    now = time.time()
    with violation_lock:
        if now - violation_last_sent.get(vtype, 0) < VIOLATION_COOLDOWN:
            return
        violation_last_sent[vtype] = now

    px1, py1, px2, py2 = person_box

    if head_box:
        fx1, fy1, fx2, fy2 = head_box
    else:
        # No face detected — estimate head as top 30% of the person box.
        ph = py2 - py1
        head_h = max(int(ph * 0.3), 20)
        cx = (px1 + px2) // 2
        half_w = (px2 - px1) // 3
        fx1, fy1 = cx - half_w, py1
        fx2, fy2 = cx + half_w, py1 + head_h

    payload = {
        "type": vtype,
        "timestamp": int(now),
        "image": base64.b64encode(frame_jpeg_bytes).decode(),
        "blackbox": [fx1, fy1, fx2 - fx1, fy2 - fy1],  # face region — gets emoji overlay
        "headbox": [px1, py1, px2 - px1, py2 - py1],    # full person box as metadata
    }
    try:
        requests.post(BACKEND_URL, json=payload, timeout=2)
    except Exception as exc:
        print(f"Backend post failed ({vtype}): {exc}")


# -------------------------------------------------
# Detection thread
# -------------------------------------------------

def detector_loop():
    global latest_jpeg, latest_data

    camera = None

    try:
        cv2.setUseOptimized(True)
        cv2.setNumThreads(2)

        require_models()

        print("Loading local NCNN PPE model...")
        ppe_model = YOLO(str(PPE_MODEL_PATH))

        face_detector = None

        if ENABLE_FACE:
            print("Loading YuNet face detector...")
            face_detector = cv2.FaceDetectorYN.create(
                str(YUNET_MODEL_PATH),
                "",
                (CAMERA_WIDTH, CAMERA_HEIGHT),
                score_threshold=FACE_CONF,
                nms_threshold=0.3,
                top_k=100,
            )

        print("Opening camera...")
        camera = LatestFrameCamera(
            CAMERA_INDEX,
            CAMERA_WIDTH,
            CAMERA_HEIGHT,
        )
        camera.start()

        frame_id = 0
        print("Detection ready.")

        while True:
            started = time.perf_counter()

            # Never process old camera frames.
            frame = camera.get_latest()

            if frame is None:
                time.sleep(0.01)
                continue

            output = frame.copy()
            frame_h, frame_w = frame.shape[:2]

            detections = []
            person_boxes = []

            # ---------------- PPE detection ----------------

            ppe_result = ppe_model(
                frame,
                imgsz=PPE_IMGSZ,
                conf=PPE_CONF,
                classes=PPE_CLASSES,
                verbose=False,
            )[0]

            person_entries = []   # (x1, y1, x2, y2, confidence)
            no_hardhat_boxes = []
            no_vest_boxes = []

            if ppe_result.boxes is not None:
                for box in ppe_result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())

                    coords = safe_box(box, frame_w, frame_h)
                    if coords is None:
                        continue
                    x1, y1, x2, y2 = coords

                    if x2 <= x1 or y2 <= y1:
                        continue

                    label = PPE_LABELS.get(class_id, str(class_id))

                    if label == "person":
                        person_entries.append((x1, y1, x2, y2, confidence))
                        continue

                    if label == "no-hardhat":
                        no_hardhat_boxes.append((x1, y1, x2, y2))
                    elif label == "no-safety-vest":
                        no_vest_boxes.append((x1, y1, x2, y2))

            # Draw persons with OK/NOK and collect per-person violation info.
            person_data = []  # {"box", "vtypes", "face"} — one entry per person
            for px1, py1, px2, py2, conf in person_entries:
                pbox = (px1, py1, px2, py2)
                has_no_hardhat = any(boxes_overlap(pbox, b) for b in no_hardhat_boxes)
                has_no_vest = any(boxes_overlap(pbox, b) for b in no_vest_boxes)
                nok = has_no_hardhat or has_no_vest
                status = "NO PPE" if nok else "OK"
                color = (0, 0, 255) if nok else (0, 220, 0)
                draw_box(output, px1, py1, px2, py2, f"person {status}", conf, color=color)
                detections.append({
                    "model": "ppe",
                    "label": "person",
                    "status": status,
                    "confidence": round(conf, 4),
                    "bbox": {"x1": px1, "y1": py1, "x2": px2, "y2": py2},
                })
                person_boxes.append(pbox)
                vtypes = []
                if has_no_hardhat:
                    vtypes.append("no_hardhat")
                if has_no_vest:
                    vtypes.append("no_safety_vest")
                person_data.append({"box": pbox, "vtypes": vtypes, "face": None})

            # ---------------- Face detection ----------------
            # Only runs inside person boxes.

            if ENABLE_FACE and face_detector is not None:
                for i, (px1, py1, px2, py2) in enumerate(person_boxes):
                    crop = frame[py1:py2, px1:px2]

                    if crop.size == 0:
                        continue

                    crop_h, crop_w = crop.shape[:2]

                    # Skip very small/distant people.
                    if crop_w < 50 or crop_h < 80:
                        continue

                    face_detector.setInputSize((crop_w, crop_h))
                    _, faces = face_detector.detect(crop)

                    if faces is None:
                        continue

                    for face in faces:
                        fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                        confidence = float(face[14])

                        x1 = max(0, min(px1 + fx, frame_w - 1))
                        y1 = max(0, min(py1 + fy, frame_h - 1))
                        x2 = max(0, min(px1 + fx + fw, frame_w - 1))
                        y2 = max(0, min(py1 + fy + fh, frame_h - 1))

                        if x2 <= x1 or y2 <= y1:
                            continue

                        # Record first face found for this person (used as headbox).
                        if i < len(person_data) and person_data[i]["face"] is None:
                            person_data[i]["face"] = (x1, y1, x2, y2)

            # Fire violation events (non-blocking, with per-type cooldown).
            nok_persons = [pd for pd in person_data if pd["vtypes"]]
            if nok_persons:
                enc_ok, enc = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if enc_ok:
                    frame_jpeg_bytes = enc.tobytes()
                    for pd in nok_persons:
                        for vtype in pd["vtypes"]:
                            threading.Thread(
                                target=send_violation,
                                args=(vtype, frame_jpeg_bytes, pd["box"], pd["face"]),
                                daemon=True,
                            ).start()

            elapsed = time.perf_counter() - started
            fps = 1.0 / max(elapsed, 0.001)
            remaining = (1.0 / MAX_PROCESS_FPS) - elapsed
            if remaining > 0:
                time.sleep(remaining)

            cv2.putText(
                output,
                f"FPS: {fps:.1f}",
                (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            ok, encoded = cv2.imencode(
                ".jpg",
                output,
                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
            )

            if not ok:
                continue

            frame_id += 1

            with state_lock:
                latest_jpeg = encoded.tobytes()
                latest_data = {
                    "status": "running",
                    "frame_id": frame_id,
                    "timestamp_ms": int(time.time() * 1000),
                    "fps": round(fps, 2),
                    "image": {
                        "width": int(frame_w),
                        "height": int(frame_h),
                    },
                    "detections": detections,
                }

    except Exception as error:
        print(f"Detector error: {error}")

        with state_lock:
            latest_data = {
                "status": "error",
                "error": str(error),
                "detections": [],
            }

    finally:
        if camera is not None:
            camera.stop()


# -------------------------------------------------
# Web routes
# -------------------------------------------------

@app.route("/")
def index():
    return render_template_string("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>PPE + Face Stream</title>
  <style>
    body {
      background: #111;
      color: #eee;
      font-family: Arial, sans-serif;
      margin: 20px;
    }

    img {
      width: min(100%, 900px);
      display: block;
      border: 1px solid #555;
    }

    pre {
      background: #1d1d1d;
      padding: 12px;
      width: min(100%, 900px);
      overflow: auto;
    }
  </style>
</head>
<body>
  <h2>PPE + Face Live Stream</h2>

  <img src="/stream.mjpg" alt="Live stream">

  <h3>Latest detections</h3>
  <pre id="data">Loading...</pre>

  <script>
    async function refreshData() {
      try {
        const response = await fetch("/api/latest", {
          cache: "no-store"
        });

        const data = await response.json();

        document.getElementById("data").textContent =
          JSON.stringify(data, null, 2);
      } catch (error) {
        document.getElementById("data").textContent =
          "Could not load detection data.";
      }
    }

    refreshData();
    setInterval(refreshData, 1000);
  </script>
</body>
</html>
""")


@app.route("/stream.mjpg")
def stream():
    def generate():
        last_frame_id = -1

        while True:
            with state_lock:
                jpeg = latest_jpeg
                frame_id = latest_data.get("frame_id", -1)

            if jpeg is not None and frame_id != last_frame_id:
                last_frame_id = frame_id

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                    + jpeg
                    + b"\r\n"
                )
            else:
                time.sleep(0.01)

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.route("/api/latest")
def api_latest():
    with state_lock:
        return jsonify(latest_data)


if __name__ == "__main__":
    worker = threading.Thread(
        target=detector_loop,
        daemon=True,
    )
    worker.start()

    print("Web server running on port 5000.")

    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=True,
        debug=False,
        use_reloader=False,
    )
