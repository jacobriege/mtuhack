# ppe_face_pi.py
import time

import cv2
import torch
from huggingface_hub import hf_hub_download
from ultralytics import YOLO
import json
import websocket

# ---------- Raspberry Pi settings ----------
BACKEND_WS_URL = "ws://192.168.178.50:8000/ws/pi/pi-cam-1"
STREAM_TOKEN = "replace-this-with-a-long-random-secret"

SEND_FPS = 5                 # Network stream rate
JPEG_QUALITY = 75
SHOW_LOCAL_WINDOW = False    # True only when a Pi display is connected
CAMERA_INDEX = 1          # second webcam
CAMERA_WIDTH = 480
CAMERA_HEIGHT = 360
CAMERA_FPS = 30

PPE_IMGSZ = 320           # lower = faster
FACE_IMGSZ = 160         # lower = faster
PPE_CONF = 0.35
FACE_CONF = 0.35

# PPE model class IDs:
# 0 Hardhat, 5 Person, 7 Safety Vest
PPE_CLASSES = [0, 5, 7]

PPE_LABELS = {
    0: "helmet",
    5: "person",
    7: "vest",
}


def clipped_box(box, frame_width, frame_height):
    """Convert YOLO box to safe integer image coordinates."""
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

    x1 = max(0, min(x1, frame_width - 1))
    y1 = max(0, min(y1, frame_height - 1))
    x2 = max(0, min(x2, frame_width - 1))
    y2 = max(0, min(y2, frame_height - 1))

    return x1, y1, x2, y2


def draw_detection(image, x1, y1, x2, y2, label, confidence, color):
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

    text = f"{label} {confidence:.2f}"
    cv2.putText(
        image,
        text,
        (x1, max(20, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
    )


def main():
    # Pi 5 has limited CPU resources: avoid excessive OpenCV/PyTorch threading.
    cv2.setUseOptimized(True)
    cv2.setNumThreads(2)
    torch.set_num_threads(4)

    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    print("Downloading/loading PPE model...")
    ppe_path = hf_hub_download(
        repo_id="yihong1120/Construction-Hazard-Detection",
        filename="models/yolo26/pt/yolo26n.pt",
    )

    print("Downloading/loading face model...")
    face_path = hf_hub_download(
        repo_id="AdamCodd/YOLOv11n-face-detection",
        filename="model.pt",
    )

    ppe_model = YOLO(ppe_path)
    face_model = YOLO(face_path)

    # V4L2 is the normal Linux webcam backend.
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

    # Fallback if the V4L2-specific open fails.
    if not cap.isOpened():
        cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        raise RuntimeError(
            "Camera source=1 could not be opened. "
            "Check /dev/video* or try CAMERA_INDEX = 0 or 2."
        )

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # lower camera lag where supported

    print("Running. Press Q in the camera window to quit.")

    with torch.inference_mode():
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Could not read a frame from the webcam.")
                break

            start_time = time.perf_counter()
            output = frame.copy()
            frame_h, frame_w = frame.shape[:2]

            # PPE: only helmet, person and vest.
            ppe_result = ppe_model(
                frame,
                imgsz=PPE_IMGSZ,
                conf=PPE_CONF,
                classes=PPE_CLASSES,
                device="cpu",
                verbose=False,
            )[0]

            person_boxes = []

            if ppe_result.boxes is not None:
                for box in ppe_result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())

                    x1, y1, x2, y2 = clipped_box(box, frame_w, frame_h)

                    if x2 <= x1 or y2 <= y1:
                        continue

                    label = PPE_LABELS.get(class_id, str(class_id))

                    if class_id == 5:
                        color = (0, 220, 0)
                        person_boxes.append((x1, y1, x2, y2))
                    elif class_id == 0:
                        color = (0, 165, 255)
                    else:
                        color = (255, 180, 0)

                    draw_detection(
                        output, x1, y1, x2, y2,
                        label, confidence, color
                    )

            # Run face detector only inside each detected person.
            for px1, py1, px2, py2 in person_boxes:
                person_crop = frame[py1:py2, px1:px2]

                crop_h, crop_w = person_crop.shape[:2]

                # Ignore tiny person boxes: face detection would be unreliable.
                if crop_w < 50 or crop_h < 80:
                    continue

                face_result = face_model(
                    person_crop,
                    imgsz=FACE_IMGSZ,
                    conf=FACE_CONF,
                    max_det=5,
                    device="cpu",
                    verbose=False,
                )[0]

                if face_result.boxes is None:
                    continue

                for face_box in face_result.boxes:
                    fx1, fy1, fx2, fy2 = map(
                        int, face_box.xyxy[0].tolist()
                    )
                    face_conf = float(face_box.conf[0].item())

                    # Convert crop coordinates back to full image coordinates.
                    x1 = px1 + fx1
                    y1 = py1 + fy1
                    x2 = px1 + fx2
                    y2 = py1 + fy2

                    x1 = max(0, min(x1, frame_w - 1))
                    y1 = max(0, min(y1, frame_h - 1))
                    x2 = max(0, min(x2, frame_w - 1))
                    y2 = max(0, min(y2, frame_h - 1))

                    if x2 > x1 and y2 > y1:
                        draw_detection(
                            output, x1, y1, x2, y2,
                            "face", face_conf, (255, 0, 255)
                        )

            fps = 1.0 / max(time.perf_counter() - start_time, 0.001)
            cv2.putText(
                output,
                f"FPS: {fps:.1f}",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            cv2.imshow("PPE + Face | Raspberry Pi", output)

            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()