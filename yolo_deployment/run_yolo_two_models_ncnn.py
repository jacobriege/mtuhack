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
# Both YOLO models stay on the NCNN backend.
# Backend events contain sad violation faces in blackbox and compliant faces in happybox.

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

# NCNN model folders, not .pt files.
PPE_MODEL_PATH = MODEL_DIR / "ppe_yolo26n_ncnn_model"
FACE_MODEL_PATH = MODEL_DIR / "face_yolo11n_ncnn_model"

CAMERA_INDEX = 1
CAMERA_WIDTH = 480
CAMERA_HEIGHT = 360

# Keep these equal to the NCNN export sizes.
PPE_IMGSZ = 256
FACE_IMGSZ = 128

PPE_CONF = 0.35
FACE_CONF = 0.35
ENABLE_FACE = True

# None = do not filter; all PPE model classes are retained.
# Example filter: [0, 1, 2, 3, 4, 5, 6, 7]
PPE_CLASSES = None

# Live stream / performance
MAX_PROCESS_FPS = 30
JPEG_QUALITY = 60

# Backend notification on safety violations.
# Keep the same endpoint used by the existing backend-enabled script.
BACKEND_URL = "http://192.168.0.164:5000/violations"
VIOLATION_COOLDOWN = 10  # seconds per violation type

# A violation must remain visible for this long before it is reported.
# This filters short, temporary false detections.
VIOLATION_MIN_DURATION = 3.0

# Short recognition gaps do not immediately reset the 3-second timer.
# Set to 0.0 for completely strict, frame-by-frame continuity.
VIOLATION_MAX_GAP_SECONDS = 0.50

# A current person detection is matched to the same earlier person when the
# boxes overlap by at least this IoU. This keeps each person's timer separate.
VIOLATION_PERSON_MATCH_IOU = 0.30

# Emergency boxes can change shape much more than standing-person boxes.
# Use a looser match so the 3-second emergency timer is not constantly reset.
EMERGENCY_PERSON_MATCH_IOU = 0.10

# When a backend request fails, keep the same active violation and retry it.
BACKEND_RETRY_SECONDS = 3.0
BACKEND_REQUEST_TIMEOUT = 2.0

# Console logs make it clear whether emergency persistence and HTTP delivery work.
PRINT_EMERGENCY_DEBUG = True

# Face inference remains limited to person crops for speed.
MIN_PERSON_CROP_WIDTH = 50
MIN_PERSON_CROP_HEIGHT = 80
MAX_FACE_DETECTIONS_PER_PERSON = 3

# Safety-association logic.
MIN_HELMET_FACE_OVERLAP = 0.01
MIN_VEST_PERSON_IOU = 0.05
HORIZONTAL_TOLERANCE_DEGREES = 30
MIN_LYING_WIDTH_HEIGHT_RATIO = 1.25

# If the PPE model explicitly predicts "no-hardhat" or "no-safety-vest"
# inside a person box, it overrides a simultaneous positive PPE detection.
EXPLICIT_NEGATIVE_PPE_OVERRIDES = True


# -------------------------------------------------
# Colors (OpenCV BGR)
# -------------------------------------------------

RAW_COLORS = {
    "hardhat": (0, 165, 255),
    "mask": (255, 255, 0),
    "no-hardhat": (0, 0, 255),
    "no-mask": (0, 0, 180),
    "no-safety-vest": (0, 0, 255),
    "person": (0, 220, 0),
    "safety-cone": (0, 140, 255),
    "safety-vest": (255, 180, 0),
    "machinery": (180, 100, 255),
    "utility-pole": (180, 180, 180),
    "vehicle": (255, 100, 100),
    "face": (255, 0, 255),
}

SAFETY_COLORS = {
    "ok": (0, 255, 0),
    "not_ok": (0, 255, 255),
    "emergency": (0, 0, 255),
}


# -------------------------------------------------
# Shared stream state
# -------------------------------------------------

app = Flask(__name__)

state_lock = threading.Lock()

# Protects the per-violation cooldown timestamps below.
violation_lock = threading.Lock()
violation_last_sent = {}  # violation type -> monotonic timestamp

# Updated only by the detector thread. Each entry is one ongoing violation
# for one visually matched person.
violation_tracks = []
violation_next_track_id = 1

latest_jpeg = None
latest_data = {
    "status": "starting",
    "frame_id": 0,
    "detections": [],
    "safety": {
        "summary": {},
        "persons": [],
    },
}


# -------------------------------------------------
# Camera reader: always keep only the newest frame
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
# Generic helper functions
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


def get_model_label(model, class_id):
    names = getattr(model, "names", {})

    if isinstance(names, dict):
        return str(names.get(class_id, class_id))

    try:
        return str(names[class_id])
    except (IndexError, KeyError, TypeError):
        return str(class_id)


def canonical_ppe_label(label):
    """Normalize common model naming variations to stable API labels."""
    normalized = str(label).strip().lower()
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace("-", " ")
    normalized = " ".join(normalized.split())

    aliases = {
        "hardhat": "hardhat",
        "hard hat": "hardhat",
        "helmet": "hardhat",
        "mask": "mask",
        "no hardhat": "no-hardhat",
        "no hard hat": "no-hardhat",
        "no helmet": "no-hardhat",
        "no mask": "no-mask",
        "no safety vest": "no-safety-vest",
        "no vest": "no-safety-vest",
        "person": "person",
        "worker": "person",
        "safety cone": "safety-cone",
        "cone": "safety-cone",
        "safety vest": "safety-vest",
        "vest": "safety-vest",
        "machinery": "machinery",
        "machine": "machinery",
        "utility pole": "utility-pole",
        "pole": "utility-pole",
        "vehicle": "vehicle",
        "car": "vehicle",
        "truck": "vehicle",
    }

    return aliases.get(normalized, normalized.replace(" ", "-"))


def box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def box_width(box):
    x1, _, x2, _ = box
    return max(0, x2 - x1)


def box_height(box):
    _, y1, _, y2 = box
    return max(0, y2 - y1)


def box_center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def intersection_area(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)

    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(box_a, box_b):
    union = box_area(box_a) + box_area(box_b) - intersection_area(box_a, box_b)

    if union <= 0:
        return 0.0

    return intersection_area(box_a, box_b) / union


def box_center_inside(inner_box, outer_box):
    cx, cy = box_center(inner_box)
    ox1, oy1, ox2, oy2 = outer_box

    return ox1 <= cx <= ox2 and oy1 <= cy <= oy2


def person_face_angle_degrees(person_box, face_box):
    """0° = horizontal, 90° = vertical."""
    px, py = box_center(person_box)
    fx, fy = box_center(face_box)

    angle = abs(math.degrees(math.atan2(fy - py, fx - px)))

    if angle > 90:
        angle = 180 - angle

    return angle


def person_is_lying_down(person_box, face_box=None):
    """
    Emergency logic:
    - person bounding box is clearly wider than tall, OR
    - line from person center to face center is approximately horizontal.
    """
    height = box_height(person_box)

    if height == 0:
        return False

    width_height_ratio = box_width(person_box) / height

    if width_height_ratio >= MIN_LYING_WIDTH_HEIGHT_RATIO:
        return True

    if face_box is not None:
        angle = person_face_angle_degrees(person_box, face_box)

        if angle <= HORIZONTAL_TOLERANCE_DEGREES:
            return True

    return False


def safe_box(box, frame_width, frame_height):
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

    x1 = max(0, min(x1, frame_width - 1))
    y1 = max(0, min(y1, frame_height - 1))
    x2 = max(0, min(x2, frame_width - 1))
    y2 = max(0, min(y2, frame_height - 1))

    return x1, y1, x2, y2


def bbox_to_api(box):
    x1, y1, x2, y2 = box

    return {
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
    }


def detection_to_api(detection):
    return {
        "model": detection["model"],
        "label": detection["label"],
        "model_label": detection["model_label"],
        "confidence": round(detection["confidence"], 4),
        "bbox": bbox_to_api(detection["bbox"]),
    }


def draw_box_only(image, box, color, thickness=2):
    x1, y1, x2, y2 = map(int, box)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        color=color,
        thickness=thickness,
    )


def draw_box_with_label(image, box, label, color, thickness=2):
    x1, y1, x2, y2 = map(int, box)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        color=color,
        thickness=thickness,
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    text_thickness = 1

    text_size, _ = cv2.getTextSize(
        label,
        font,
        font_scale,
        text_thickness,
    )
    text_width, text_height = text_size

    label_y1 = max(y1 - text_height - 8, 0)
    label_y2 = max(y1, text_height + 8)

    cv2.rectangle(
        image,
        (x1, label_y1),
        (x1 + text_width + 6, label_y2),
        color=color,
        thickness=-1,
    )

    text_color = (0, 0, 0) if color in {(0, 255, 0), (0, 255, 255)} else (255, 255, 255)

    cv2.putText(
        image,
        label,
        (x1 + 3, label_y2 - 5),
        font,
        font_scale,
        text_color,
        text_thickness,
        cv2.LINE_AA,
    )


def draw_raw_detection(image, detection):
    """Draw every detected PPE/face class. Person gets its safety overlay later."""
    if detection["label"] == "person":
        return

    label = f'{detection["label"]} {detection["confidence"]:.2f}'
    color = RAW_COLORS.get(detection["label"], (230, 230, 230))

    draw_box_with_label(
        image,
        detection["bbox"],
        label,
        color,
        thickness=1,
    )


def detection_is_within_person(detection, person_box, min_overlap=0.50):
    item_box = detection["bbox"]

    center_inside = box_center_inside(item_box, person_box)
    item_overlap = intersection_area(item_box, person_box) / max(box_area(item_box), 1)

    return center_inside or item_overlap >= min_overlap


def deduplicate_detections(detections, iou_threshold=0.70):
    """Remove duplicate face detections caused by overlapping person crops."""
    kept = []

    for candidate in sorted(
        detections,
        key=lambda item: item["confidence"],
        reverse=True,
    ):
        is_duplicate = any(
            candidate["label"] == existing["label"]
            and iou(candidate["bbox"], existing["bbox"]) >= iou_threshold
            for existing in kept
        )

        if not is_duplicate:
            kept.append(candidate)

    return kept


# -------------------------------------------------
# Safety analysis
# -------------------------------------------------

def choose_best_head(faces, person_box):
    candidates = [
        face
        for face in faces
        if detection_is_within_person(face, person_box)
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (box_area(item["bbox"]), item["confidence"]),
    )


def choose_best_vest(vests, person_box):
    candidates = []

    for vest in vests:
        vest_box = vest["bbox"]

        center_inside = box_center_inside(vest_box, person_box)
        vest_iou_person = iou(vest_box, person_box)
        vest_overlap_person = (
            intersection_area(vest_box, person_box)
            / max(box_area(vest_box), 1)
        )

        if (
            center_inside
            or vest_iou_person >= MIN_VEST_PERSON_IOU
            or vest_overlap_person >= 0.50
        ):
            score = max(vest_iou_person, vest_overlap_person)
            candidates.append((score, vest))

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (item[0], item[1]["confidence"]),
    )[1]


def choose_best_helmet(helmets, person_box, face_box):
    """
    A helmet belongs to a person when it is inside/overlaps the person.
    It counts as worn only if it overlaps the associated face/head box.
    """
    if face_box is None:
        return None, 0.0

    best_helmet = None
    best_overlap = 0.0
    face_area = max(box_area(face_box), 1)

    for helmet in helmets:
        helmet_box = helmet["bbox"]

        if not detection_is_within_person(helmet, person_box):
            continue

        overlap = intersection_area(helmet_box, face_box) / face_area

        if (
            overlap > best_overlap
            or (
                overlap == best_overlap
                and best_helmet is not None
                and helmet["confidence"] > best_helmet["confidence"]
            )
        ):
            best_helmet = helmet
            best_overlap = overlap

    return best_helmet, best_overlap


def choose_strongest_within_person(detections, person_box):
    candidates = [
        item
        for item in detections
        if detection_is_within_person(item, person_box)
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda item: item["confidence"])


def analyze_safety(detections):
    """
    Combine raw PPE + face boxes into one safety result per detected person.

    Compliance requires:
    - a face associated with the person,
    - a hardhat overlapping that face,
    - a safety vest associated with the person.

    Emergency overrides compliance if the person appears to be lying down.
    """
    persons = [d for d in detections if d["label"] == "person"]
    helmets = [d for d in detections if d["label"] == "hardhat"]
    vests = [d for d in detections if d["label"] == "safety-vest"]
    faces = [d for d in detections if d["label"] == "face"]
    no_hardhats = [d for d in detections if d["label"] == "no-hardhat"]
    no_vests = [d for d in detections if d["label"] == "no-safety-vest"]

    results = []

    for person_index, person in enumerate(persons):
        person_box = person["bbox"]

        best_face = choose_best_head(faces, person_box)
        best_vest = choose_best_vest(vests, person_box)

        face_box = best_face["bbox"] if best_face is not None else None
        best_helmet, helmet_face_overlap = choose_best_helmet(
            helmets,
            person_box,
            face_box,
        )

        explicit_no_hardhat = choose_strongest_within_person(
            no_hardhats,
            person_box,
        )
        explicit_no_vest = choose_strongest_within_person(
            no_vests,
            person_box,
        )

        helmet_is_worn = (
            best_helmet is not None
            and helmet_face_overlap >= MIN_HELMET_FACE_OVERLAP
        )
        vest_is_worn = best_vest is not None

        if EXPLICIT_NEGATIVE_PPE_OVERRIDES:
            if explicit_no_hardhat is not None:
                helmet_is_worn = False

            if explicit_no_vest is not None:
                vest_is_worn = False

        is_compliant = helmet_is_worn and vest_is_worn
        is_lying_down = person_is_lying_down(person_box, face_box)

        issues = []

        # Emergency is a backend-reportable event as well. It uses the same
        # persistence timer and per-person tracking as PPE violations.
        if is_lying_down:
            issues.append("emergency")

        if not helmet_is_worn:
            issues.append("helmet_missing")

        if not vest_is_worn:
            issues.append("vest_missing")

        if is_lying_down:
            status_code = "emergency"
            status_label = "Emergency"
        elif is_compliant:
            status_code = "ok"
            status_label = "Safety Equipment OK"
        else:
            status_code = "not_ok"
            status_label = "Safety Equipment NOT OK"

        person_head_angle = (
            person_face_angle_degrees(person_box, face_box)
            if face_box is not None
            else None
        )

        results.append({
            "person_index": person_index,
            "status_code": status_code,
            "status_label": status_label,
            "issues": issues,
            "has_face": best_face is not None,
            "helmet_is_worn": helmet_is_worn,
            "vest_is_worn": vest_is_worn,
            "is_compliant": is_compliant,
            "is_lying_down": is_lying_down,
            "person_box": person_box,
            "face_box": face_box,
            "helmet_box": (
                best_helmet["bbox"] if best_helmet is not None else None
            ),
            "vest_box": (
                best_vest["bbox"] if best_vest is not None else None
            ),
            "no_hardhat_box": (
                explicit_no_hardhat["bbox"]
                if explicit_no_hardhat is not None
                else None
            ),
            "no_safety_vest_box": (
                explicit_no_vest["bbox"]
                if explicit_no_vest is not None
                else None
            ),
            "helmet_face_overlap_ratio": round(helmet_face_overlap, 4),
            "person_head_angle_degrees": (
                round(person_head_angle, 2)
                if person_head_angle is not None
                else None
            ),
            "person_width_height_ratio": round(
                box_width(person_box) / max(box_height(person_box), 1),
                4,
            ),
        })

    summary = {
        "person_count": len(results),
        "compliant_count": sum(
            person["status_code"] == "ok"
            for person in results
        ),
        "not_ok_count": sum(
            person["status_code"] == "not_ok"
            for person in results
        ),
        "emergency_count": sum(
            person["status_code"] == "emergency"
            for person in results
        ),
    }

    return {
        "summary": summary,
        "persons": results,
    }


def safety_to_api(safety):
    persons = []

    for person in safety["persons"]:
        persons.append({
            "person_index": person["person_index"],
            "status_code": person["status_code"],
            "status_label": person["status_label"],
            "issues": person["issues"],
            "has_face": person["has_face"],
            "helmet_is_worn": person["helmet_is_worn"],
            "vest_is_worn": person["vest_is_worn"],
            "is_compliant": person["is_compliant"],
            "is_lying_down": person["is_lying_down"],
            "person_bbox": bbox_to_api(person["person_box"]),
            "face_bbox": (
                bbox_to_api(person["face_box"])
                if person["face_box"] is not None
                else None
            ),
            "helmet_bbox": (
                bbox_to_api(person["helmet_box"])
                if person["helmet_box"] is not None
                else None
            ),
            "vest_bbox": (
                bbox_to_api(person["vest_box"])
                if person["vest_box"] is not None
                else None
            ),
            "no_hardhat_bbox": (
                bbox_to_api(person["no_hardhat_box"])
                if person["no_hardhat_box"] is not None
                else None
            ),
            "no_safety_vest_bbox": (
                bbox_to_api(person["no_safety_vest_box"])
                if person["no_safety_vest_box"] is not None
                else None
            ),
            "helmet_face_overlap_ratio": person[
                "helmet_face_overlap_ratio"
            ],
            "person_head_angle_degrees": person[
                "person_head_angle_degrees"
            ],
            "person_width_height_ratio": person[
                "person_width_height_ratio"
            ],
        })

    return {
        "summary": safety["summary"],
        "persons": persons,
    }


def draw_safety_overlay(image, safety):
    for person in safety["persons"]:
        color = SAFETY_COLORS[person["status_code"]]

        draw_box_with_label(
            image,
            person["person_box"],
            person["status_label"],
            color,
            thickness=3,
        )

        for linked_box in (
            person["face_box"],
            person["helmet_box"],
            person["vest_box"],
        ):
            if linked_box is not None:
                draw_box_only(image, linked_box, color, thickness=2)


# -------------------------------------------------
# Backend violation notifications
# -------------------------------------------------

def estimated_head_box(person_box):
    """Fallback head box when no face was detected for a person."""
    px1, py1, px2, py2 = person_box

    person_height = py2 - py1
    person_width = px2 - px1

    head_height = max(int(person_height * 0.30), 20)
    center_x = (px1 + px2) // 2
    half_width = max(person_width // 3, 20)

    return (
        center_x - half_width,
        py1,
        center_x + half_width,
        py1 + head_height,
    )


def reserve_violation_cooldown(violation_type):
    """Reserve the global backend cooldown before starting an HTTP thread."""
    now = time.monotonic()

    with violation_lock:
        last_sent = violation_last_sent.get(violation_type, 0.0)

        if now - last_sent < VIOLATION_COOLDOWN:
            return False

        violation_last_sent[violation_type] = now
        return True


def mark_backend_send_failed(track_id, violation_type, reason):
    """Allow the still-active track to retry after a failed POST."""
    now = time.monotonic()

    with violation_lock:
        # Release the type-level cooldown: the backend did not accept the event.
        violation_last_sent.pop(violation_type, None)

        for track in violation_tracks:
            if track["track_id"] == track_id:
                track["sent"] = False
                track["retry_not_before"] = now + BACKEND_RETRY_SECONDS
                break

    print(
        f"[BACKEND] {violation_type} track={track_id} failed; "
        f"retry in {BACKEND_RETRY_SECONDS:.1f}s. Reason: {reason}"
    )


def boxes_to_backend(boxes):
    """Convert XYXY boxes to backend [x, y, width, height] boxes."""
    converted = []

    for x1, y1, x2, y2 in boxes:
        width = max(0, int(x2) - int(x1))
        height = max(0, int(y2) - int(y1))

        if width <= 0 or height <= 0:
            continue

        converted.append([
            int(x1),
            int(y1),
            width,
            height,
        ])

    return converted


def boxes_overlap_iou(box_a, box_b, threshold=0.70):
    """True when two XYXY boxes likely refer to the same face."""
    return iou(box_a, box_b) >= threshold


def unique_face_boxes(face_boxes):
    """Remove duplicate face boxes caused by overlapping person detections."""
    unique = []

    for candidate in face_boxes:
        if not any(boxes_overlap_iou(candidate, kept) for kept in unique):
            unique.append(candidate)

    return unique


def split_face_boxes_by_safety(safety):
    """
    Return (sad_face_boxes, happy_face_boxes) for the current frame.

    A face attached to a person with status 'not_ok' or 'emergency' is sad.
    A face attached to a person with status 'ok' is happy. If duplicate person
    detections associate the same face with both groups, sad wins.
    """
    sad_faces = []
    happy_faces = []

    for person in safety["persons"]:
        face_box = person["face_box"]

        if face_box is None:
            continue

        if person["status_code"] in {"not_ok", "emergency"}:
            sad_faces.append(face_box)
        elif person["status_code"] == "ok":
            happy_faces.append(face_box)

    sad_faces = unique_face_boxes(sad_faces)

    # Do not render a happy emoji on top of a sad emoji when a duplicated
    # person/face association exists.
    happy_faces = [
        face_box
        for face_box in unique_face_boxes(happy_faces)
        if not any(boxes_overlap_iou(face_box, sad_box) for sad_box in sad_faces)
    ]

    return sad_faces, happy_faces


def send_violation(
    violation_type,
    frame_jpeg_bytes,
    person_box,
    sad_face_boxes,
    happy_face_boxes,
    track_id,
    duration_seconds,
):
    """
    POST one persistent violation and log the exact HTTP result.

    Backend schema:
      blackbox: sad face boxes (list of [x, y, width, height])
      happybox: compliant face boxes (same format)
      headbox: violating person's box as a one-element list
    """
    now = time.time()
    px1, py1, px2, py2 = person_box

    payload = {
        "type": violation_type,
        "timestamp": int(now),
        "image": base64.b64encode(frame_jpeg_bytes).decode("ascii"),
        "blackbox": boxes_to_backend(sad_face_boxes),
        "happybox": boxes_to_backend(happy_face_boxes),
        "headbox": [[px1, py1, px2 - px1, py2 - py1]],
    }

    tag = "[EMERGENCY]" if violation_type == "emergency" else "[BACKEND]"
    print(
        f"{tag} POST -> {BACKEND_URL} "
        f"track={track_id} persistent={duration_seconds:.2f}s "
        f"sad_faces={len(payload['blackbox'])} "
        f"happy_faces={len(payload['happybox'])}"
    )

    try:
        response = requests.post(
            BACKEND_URL,
            json=payload,
            timeout=BACKEND_REQUEST_TIMEOUT,
        )

        # requests.post() does not raise automatically for HTTP 4xx/5xx.
        response.raise_for_status()

        response_text = response.text.strip().replace("\n", " ")[:300]
        print(
            f"{tag} delivered successfully: HTTP {response.status_code} "
            f"track={track_id} response={response_text or '<empty>'}"
        )

    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        details = str(exc)

        if response is not None:
            body = response.text.strip().replace("\n", " ")[:500]
            details = f"HTTP {response.status_code}: {body or details}"

        mark_backend_send_failed(track_id, violation_type, details)

def violation_observations_from_safety(safety):
    """Return one observation per active backend-relevant issue and person."""
    issue_to_backend_type = {
        "emergency": "emergency",
        "helmet_missing": "no_hardhat",
        "vest_missing": "no_safety_vest",
    }

    observations = []

    for person in safety["persons"]:
        for issue in person["issues"]:
            violation_type = issue_to_backend_type.get(issue)

            if violation_type is None:
                continue

            observations.append({
                "violation_type": violation_type,
                "person_box": person["person_box"],
                "face_box": person["face_box"],
            })

    return observations


def box_center_distance(box_a, box_b):
    ax, ay = box_center(box_a)
    bx, by = box_center(box_b)
    return math.hypot(ax - bx, ay - by)


def find_matching_violation_track(violation_type, person_box, now, used_track_ids):
    """
    Find the best recent track of the same violation/person.

    Emergency uses a looser match because a lying person's detector box often
    changes shape quickly. A nearby center is accepted as a fallback so its
    3-second timer can continue instead of resetting every few frames.
    """
    best_track = None
    best_score = -1.0

    required_iou = (
        EMERGENCY_PERSON_MATCH_IOU
        if violation_type == "emergency"
        else VIOLATION_PERSON_MATCH_IOU
    )

    for track in violation_tracks:
        if track["track_id"] in used_track_ids:
            continue

        if track["violation_type"] != violation_type:
            continue

        if now - track["last_seen"] > VIOLATION_MAX_GAP_SECONDS:
            continue

        overlap = iou(track["person_box"], person_box)
        matches = overlap >= required_iou
        score = overlap

        if violation_type == "emergency" and not matches:
            old_box = track["person_box"]
            old_size = max(box_width(old_box), box_height(old_box), 1)
            new_size = max(box_width(person_box), box_height(person_box), 1)
            max_center_distance = 0.75 * max(old_size, new_size)
            center_distance = box_center_distance(old_box, person_box)

            if center_distance <= max_center_distance:
                matches = True
                # Prefer an IoU match, but still rank nearby center matches.
                score = 0.01 - (center_distance / max_center_distance) * 0.001

        if matches and score > best_score:
            best_track = track
            best_score = score

    return best_track

def update_persistent_violations(safety):
    """
    Track violation duration separately for each person/type.

    Returns events that have been continuously detected for at least
    VIOLATION_MIN_DURATION seconds and are ready to be sent once.
    """
    global violation_next_track_id

    now = time.monotonic()
    observations = violation_observations_from_safety(safety)
    used_track_ids = set()
    ready_events = []

    for observation in observations:
        violation_type = observation["violation_type"]
        person_box = observation["person_box"]

        track = find_matching_violation_track(
            violation_type,
            person_box,
            now,
            used_track_ids,
        )

        if track is None:
            track = {
                "track_id": violation_next_track_id,
                "violation_type": violation_type,
                "first_seen": now,
                "last_seen": now,
                "person_box": person_box,
                "face_box": observation["face_box"],
                "sent": False,
                "retry_not_before": 0.0,
                "last_debug_second": -1,
            }
            violation_tracks.append(track)
            violation_next_track_id += 1

            if violation_type == "emergency" and PRINT_EMERGENCY_DEBUG:
                print(
                    f"[EMERGENCY] observed: track={track['track_id']} "
                    f"timer started; waiting {VIOLATION_MIN_DURATION:.1f}s"
                )
        else:
            track["last_seen"] = now
            track["person_box"] = person_box
            track["face_box"] = observation["face_box"]

        used_track_ids.add(track["track_id"])

        duration = now - track["first_seen"]

        if violation_type == "emergency" and PRINT_EMERGENCY_DEBUG:
            whole_seconds = int(duration)
            if whole_seconds != track.get("last_debug_second", -1):
                track["last_debug_second"] = whole_seconds
                print(
                    f"[EMERGENCY] active: track={track['track_id']} "
                    f"{duration:.2f}s / {VIOLATION_MIN_DURATION:.2f}s"
                )

        if (
            not track["sent"]
            and now >= track.get("retry_not_before", 0.0)
            and duration >= VIOLATION_MIN_DURATION
            and reserve_violation_cooldown(violation_type)
        ):
            track["sent"] = True
            ready_events.append({
                "track_id": track["track_id"],
                "violation_type": violation_type,
                "person_box": track["person_box"],
                "face_box": track["face_box"],
                "duration_seconds": duration,
            })

            tag = "[EMERGENCY]" if violation_type == "emergency" else "[BACKEND]"
            print(
                f"{tag} persistent event ready: track={track['track_id']} "
                f"type={violation_type} after {duration:.2f}s"
            )

    # A violation that is no longer observed for too long becomes a new episode
    # if it appears again later. Its three-second timer then starts from zero.
    violation_tracks[:] = [
        track
        for track in violation_tracks
        if now - track["last_seen"] <= VIOLATION_MAX_GAP_SECONDS
    ]

    return ready_events

def annotate_persistence_state(safety):
    """Optional API-only view of active persistence timers; no effect on inference."""
    now = time.monotonic()

    active = []
    for track in violation_tracks:
        active.append({
            "track_id": track["track_id"],
            "type": track["violation_type"],
            "duration_seconds": round(now - track["first_seen"], 2),
            "reported": track["sent"],
            "retry_not_before_seconds": round(
                max(0.0, track.get("retry_not_before", 0.0) - now),
                2,
            ),
            "person_bbox": bbox_to_api(track["person_box"]),
        })

    return active


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

            # Never process a backlog of old webcam frames.
            frame = camera.get_latest()

            if frame is None:
                time.sleep(0.01)
                continue

            output = frame.copy()
            frame_h, frame_w = frame.shape[:2]
            detections = []
            person_boxes = []

            # ---------------- PPE inference: all model classes ----------------

            ppe_kwargs = {
                "imgsz": PPE_IMGSZ,
                "conf": PPE_CONF,
                "verbose": False,
            }

            if PPE_CLASSES is not None:
                ppe_kwargs["classes"] = PPE_CLASSES

            ppe_result = ppe_model(frame, **ppe_kwargs)[0]

            if ppe_result.boxes is not None:
                for box in ppe_result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    box_xyxy = safe_box(box, frame_w, frame_h)

                    if box_xyxy[2] <= box_xyxy[0] or box_xyxy[3] <= box_xyxy[1]:
                        continue

                    model_label = get_model_label(ppe_model, class_id)
                    label = canonical_ppe_label(model_label)

                    detection = {
                        "model": "ppe",
                        "label": label,
                        "model_label": model_label,
                        "confidence": confidence,
                        "bbox": box_xyxy,
                    }

                    detections.append(detection)

                    if label == "person":
                        person_boxes.append(box_xyxy)

            # ---------------- Face inference: person crops only ----------------

            face_detections = []

            if ENABLE_FACE and face_model is not None:
                for px1, py1, px2, py2 in person_boxes:
                    crop = frame[py1:py2, px1:px2]

                    if crop.size == 0:
                        continue

                    crop_h, crop_w = crop.shape[:2]

                    if (
                        crop_w < MIN_PERSON_CROP_WIDTH
                        or crop_h < MIN_PERSON_CROP_HEIGHT
                    ):
                        continue

                    face_result = face_model(
                        crop,
                        imgsz=FACE_IMGSZ,
                        conf=FACE_CONF,
                        max_det=MAX_FACE_DETECTIONS_PER_PERSON,
                        verbose=False,
                    )[0]

                    if face_result.boxes is None:
                        continue

                    for face_box in face_result.boxes:
                        confidence = float(face_box.conf[0].item())
                        fx1, fy1, fx2, fy2 = map(
                            int,
                            face_box.xyxy[0].tolist(),
                        )

                        x1 = max(0, min(px1 + fx1, frame_w - 1))
                        y1 = max(0, min(py1 + fy1, frame_h - 1))
                        x2 = max(0, min(px1 + fx2, frame_w - 1))
                        y2 = max(0, min(py1 + fy2, frame_h - 1))

                        if x2 <= x1 or y2 <= y1:
                            continue

                        face_detections.append({
                            "model": "face",
                            "label": "face",
                            "model_label": "face",
                            "confidence": confidence,
                            "bbox": (x1, y1, x2, y2),
                        })

            detections.extend(deduplicate_detections(face_detections))

            # ---------------- Safety logic + rendering ----------------

            safety = analyze_safety(detections)

            # Split currently associated face boxes by each person's safety
            # state. Violating/emergency persons get sad emojis in the backend;
            # compliant persons get happy emojis.
            sad_face_boxes, happy_face_boxes = split_face_boxes_by_safety(safety)

            for detection in detections:
                draw_raw_detection(output, detection)

            draw_safety_overlay(output, safety)

            # A backend event is created only after the same violation has
            # persisted for at least VIOLATION_MIN_DURATION seconds.
            # HTTP POSTs still run in daemon threads and never block inference.
            ready_violation_events = update_persistent_violations(safety)

            if ready_violation_events:
                event_ok, event_jpeg = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
                )

                if event_ok:
                    event_jpeg_bytes = event_jpeg.tobytes()

                    for event in ready_violation_events:
                        threading.Thread(
                            target=send_violation,
                            args=(
                                event["violation_type"],
                                event_jpeg_bytes,
                                event["person_box"],
                                sad_face_boxes,
                                happy_face_boxes,
                                event["track_id"],
                                event["duration_seconds"],
                            ),
                            daemon=True,
                        ).start()

            inference_elapsed = time.perf_counter() - started
            remaining = (1.0 / MAX_PROCESS_FPS) - inference_elapsed

            if remaining > 0:
                time.sleep(remaining)

            loop_elapsed = time.perf_counter() - started
            loop_fps = 1.0 / max(loop_elapsed, 0.001)
            inference_fps = 1.0 / max(inference_elapsed, 0.001)

            cv2.putText(
                output,
                f"FPS: {loop_fps:.1f} | infer: {inference_fps:.1f}",
                (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
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
                    "fps": round(loop_fps, 2),
                    "inference_fps": round(inference_fps, 2),
                    "image": {
                        "width": int(frame_w),
                        "height": int(frame_h),
                    },
                    "detections": [
                        detection_to_api(item)
                        for item in detections
                    ],
                    "safety": safety_to_api(safety),
                    "violation_persistence": annotate_persistence_state(safety),
                }

    except Exception as error:
        print(f"Detector error: {error}")

        with state_lock:
            latest_data = {
                "status": "error",
                "error": str(error),
                "detections": [],
                "safety": {
                    "summary": {},
                    "persons": [],
                },
                "violation_persistence": [],
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
  <title>PPE Safety Stream</title>
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
  <h2>PPE + Face Safety Stream</h2>
  <img src="/stream.mjpg" alt="Live stream">
  <h3>Latest detections and safety status</h3>
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
