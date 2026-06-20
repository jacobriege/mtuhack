# ~/ppe-pi/pi_ppe_face_web_fast.py
#
# Local WLAN stream:
# http://RASPBERRY_PI_IP:8000
#
# Required local NCNN model folders:
# ~/ppe-pi/models/ppe_yolo26n_ncnn_model/
# ~/ppe-pi/models/face_yolo11n_ncnn_model/
#
# No model downloading. No Hugging Face needed on the Pi.

import threading
import time
from pathlib import Path

import cv2
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
FACE_MODEL_PATH = MODEL_DIR / "face_yolo11n_ncnn_model"

CAMERA_INDEX = 1  # second webcam

# Lower resolution = less delay / faster inference
CAMERA_WIDTH = 480
CAMERA_HEIGHT = 360

# Keep these equal to the NCNN export sizes
PPE_IMGSZ = 256
FACE_IMGSZ = 128

PPE_CONF = 0.35
FACE_CONF = 0.35

ENABLE_FACE = True

# Lower quality reduces WLAN bandwidth and JPEG encoding time
JPEG_QUALITY = 60

# PPE model class IDs:
# 0 = Hardhat, 5 = Person, 7 = Safety Vest
PPE_CLASSES = [0, 5, 7]

PPE_LABELS = {
    0: "helmet",
    5: "person",
    7: "vest",
}

COLORS = {
    "person": (0, 220, 0),
    "helmet": (0, 165, 255),
    "vest": (255, 180, 0),
    "face": (255, 0, 255),
}


# -------------------------------------------------
# Shared stream state
# -------------------------------------------------

app = Flask(__name__)

state_lock = threading.Lock()

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

    if ENABLE_FACE and not FACE_MODEL_PATH.is_dir():
        missing.append(str(FACE_MODEL_PATH))

    if missing:
        raise FileNotFoundError(
            "Missing NCNN model folder(s):\n- "
            + "\n- ".join(missing)
        )


def safe_box(box, frame_width, frame_height):
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

    x1 = max(0, min(x1, frame_width - 1))
    y1 = max(0, min(y1, frame_height - 1))
    x2 = max(0, min(x2, frame_width - 1))
    y2 = max(0, min(y2, frame_height - 1))

    return x1, y1, x2, y2


def draw_box(image, x1, y1, x2, y2, label, confidence):
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

        face_model = None

        if ENABLE_FACE:
            print("Loading local NCNN face model...")
            face_model = YOLO(str(FACE_MODEL_PATH))

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

            if ppe_result.boxes is not None:
                for box in ppe_result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())

                    x1, y1, x2, y2 = safe_box(
                        box,
                        frame_w,
                        frame_h,
                    )

                    if x2 <= x1 or y2 <= y1:
                        continue

                    label = PPE_LABELS.get(class_id, str(class_id))

                    draw_box(
                        output,
                        x1,
                        y1,
                        x2,
                        y2,
                        label,
                        confidence,
                    )

                    detections.append({
                        "model": "ppe",
                        "label": label,
                        "confidence": round(confidence, 4),
                        "bbox": {
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                        },
                    })

                    if label == "person":
                        person_boxes.append((x1, y1, x2, y2))

            # ---------------- Face detection ----------------
            # Only runs inside person boxes.

            if ENABLE_FACE and face_model is not None:
                for px1, py1, px2, py2 in person_boxes:
                    crop = frame[py1:py2, px1:px2]

                    if crop.size == 0:
                        continue

                    crop_h, crop_w = crop.shape[:2]

                    # Skip very small/distant people.
                    if crop_w < 50 or crop_h < 80:
                        continue

                    face_result = face_model(
                        crop,
                        imgsz=FACE_IMGSZ,
                        conf=FACE_CONF,
                        max_det=3,
                        verbose=False,
                    )[0]

                    if face_result.boxes is None:
                        continue

                    for face_box in face_result.boxes:
                        fx1, fy1, fx2, fy2 = map(
                            int,
                            face_box.xyxy[0].tolist(),
                        )

                        confidence = float(face_box.conf[0].item())

                        x1 = max(0, min(px1 + fx1, frame_w - 1))
                        y1 = max(0, min(py1 + fy1, frame_h - 1))
                        x2 = max(0, min(px1 + fx2, frame_w - 1))
                        y2 = max(0, min(py1 + fy2, frame_h - 1))

                        if x2 <= x1 or y2 <= y1:
                            continue

                        draw_box(
                            output,
                            x1,
                            y1,
                            x2,
                            y2,
                            "face",
                            confidence,
                        )

                        detections.append({
                            "model": "face",
                            "label": "face",
                            "confidence": round(confidence, 4),
                            "bbox": {
                                "x1": x1,
                                "y1": y1,
                                "x2": x2,
                                "y2": y2,
                            },
                        })

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

    print("Web server running on port 8000.")

    app.run(
        host="0.0.0.0",
        port=8000,
        threaded=True,
        debug=False,
        use_reloader=False,
    )