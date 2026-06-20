from pathlib import Path
import cv2
from ultralytics import YOLO
import math


def box_center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def angle_between_person_and_face(person_box, face_box):
    """
    Berechnet den Winkel der Verbindungslinie zwischen Mittelpunkt der Person-Box
    und Mittelpunkt der Face-Box relativ zur horizontalen x-Achse.

    Rückgabe:
    - 0 Grad   = waagrecht
    - 90 Grad  = senkrecht
    """

    px, py = box_center(person_box)
    fx, fy = box_center(face_box)

    dx = fx - px
    dy = fy - py

    angle = abs(math.degrees(math.atan2(dy, dx)))

    # Winkel auf 0..90 Grad normalisieren
    if angle > 90:
        angle = 180 - angle

    return angle


def person_is_lying_down(person_box, face_box, horizontal_tolerance_degrees=20):
    """
    Eine Person gilt als liegend, wenn die Verbindungslinie zwischen
    Person-Mitte und Face-Mitte ungefähr waagrecht ist.

    horizontal_tolerance_degrees=20 bedeutet:
    0 bis 20 Grad wird als liegend interpretiert.
    """

    if face_box is None:
        return False

    angle = angle_between_person_and_face(person_box, face_box)

    return angle <= horizontal_tolerance_degrees


def load_yolo_models(path_to_ppe_model, path_to_face_model):
    ppe_model = YOLO(path_to_ppe_model)
    face_model = YOLO(path_to_face_model)
    return ppe_model, face_model

def process_ppe_images(
    model,
    input_dir="test_images",
    output_dir="result_images",
    conf=0.25,
    imgsz=640
):
    """
    Bearbeitet alle Bilder im input_dir mit einem YOLO-Modell.
    Speichert Ausgabebilder mit Bounding Boxes, Labels und Confidence Scores
    im output_dir.
    """

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    image_paths = [
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    ]

    if not image_paths:
        print(f"Keine Bilder in '{input_dir}' gefunden.")
        return []

    all_detections = []

    for image_path in image_paths:
        # YOLO-Inferenz
        results = model(
            source=str(image_path),
            conf=conf,
            imgsz=imgsz,
            verbose=False
        )

        result = results[0]

        # Bild mit Bounding Boxes + Labels rendern
        # Ultralytics plot() zeichnet standardmäßig Boxen, Klassenlabels und Scores ein.
        annotated_image = result.plot()

        output_path = output_dir / image_path.name

        # result.plot() liefert ein NumPy-Bild im BGR-Format, passend für cv2.imwrite
        cv2.imwrite(str(output_path), annotated_image)

        image_detections = []

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                confidence = float(box.conf[0])

                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detection = {
                    "image": image_path.name,
                    "label": label,
                    "confidence": confidence,
                    "bbox_xyxy": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    }
                }

                image_detections.append(detection)
                all_detections.append(detection)

        print(f"Gespeichert: {output_path} | Detektionen: {len(image_detections)}")

    return all_detections


def process_ppe_images_filtered(
    model,
    input_dir="test_images",
    output_dir="result_images",
    conf=0.25,
    imgsz=640,
    wanted_labels=None
):
    """
    Bearbeitet alle Bilder im input_dir mit einem YOLO-Modell.
    Zeichnet nur ausgewählte Labels ins Ausgabebild.
    Speichert die Ergebnisse im output_dir.
    """

    if wanted_labels is None:
        wanted_labels = {"helmet", "vest", "goggles", "Person"}

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    image_paths = [
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    ]

    if not image_paths:
        print(f"Keine Bilder in '{input_dir}' gefunden.")
        return []

    all_detections = []

    for image_path in image_paths:
        image = cv2.imread(str(image_path))

        if image is None:
            print(f"Konnte Bild nicht lesen: {image_path}")
            continue

        results = model(
            source=str(image_path),
            conf=conf,
            imgsz=imgsz,
            verbose=False
        )

        result = results[0]
        image_detections = []

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]

                # Unerwünschte Labels überspringen
                if label not in wanted_labels:
                    continue

                confidence = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

                # Bounding Box zeichnen
                cv2.rectangle(
                    image,
                    (x1, y1),
                    (x2, y2),
                    color=(0, 255, 0),
                    thickness=2
                )

                text = f"{label} {confidence:.2f}"

                # Label-Hintergrund
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2

                text_size, _ = cv2.getTextSize(
                    text,
                    font,
                    font_scale,
                    thickness
                )

                text_width, text_height = text_size

                cv2.rectangle(
                    image,
                    (x1, max(y1 - text_height - 8, 0)),
                    (x1 + text_width + 4, y1),
                    color=(0, 255, 0),
                    thickness=-1
                )

                cv2.putText(
                    image,
                    text,
                    (x1 + 2, y1 - 5),
                    font,
                    font_scale,
                    color=(0, 0, 0),
                    thickness=thickness,
                    lineType=cv2.LINE_AA
                )

                detection = {
                    "image": image_path.name,
                    "label": label,
                    "confidence": confidence,
                    "bbox_xyxy": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    }
                }

                image_detections.append(detection)
                all_detections.append(detection)

        output_path = output_dir / image_path.name
        cv2.imwrite(str(output_path), image)

        print(
            f"Gespeichert: {output_path} | "
            f"angezeigte Detektionen: {len(image_detections)}"
        )

    return all_detections

def process_face_images(
    model,
    input_dir="test_images",
    output_dir="result_images",
    conf=0.25,
    imgsz=640
):
    """
    Bearbeitet alle Bilder im input_dir mit einem Face-Detection-YOLO-Modell.
    Zeichnet alle erkannten Gesichter ins Ausgabebild.
    Speichert die Ergebnisse im output_dir.
    Vorhandene Dateien mit gleichem Namen werden überschrieben.
    """

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    image_paths = [
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    ]

    if not image_paths:
        print(f"Keine Bilder in '{input_dir}' gefunden.")
        return []

    all_detections = []

    for image_path in image_paths:
        image = cv2.imread(str(image_path))

        if image is None:
            print(f"Konnte Bild nicht lesen: {image_path}")
            continue

        results = model(
            source=str(image_path),
            conf=conf,
            imgsz=imgsz,
            verbose=False
        )

        result = results[0]
        image_detections = []

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

                label = model.names.get(cls_id, "face")

                # Bounding Box zeichnen
                cv2.rectangle(
                    image,
                    (x1, y1),
                    (x2, y2),
                    color=(255, 0, 0),
                    thickness=2
                )

                text = f"{label} {confidence:.2f}"

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2

                text_size, _ = cv2.getTextSize(
                    text,
                    font,
                    font_scale,
                    thickness
                )

                text_width, text_height = text_size

                # Label-Hintergrund zeichnen
                cv2.rectangle(
                    image,
                    (x1, max(y1 - text_height - 8, 0)),
                    (x1 + text_width + 4, y1),
                    color=(255, 0, 0),
                    thickness=-1
                )

                # Label-Text zeichnen
                cv2.putText(
                    image,
                    text,
                    (x1 + 2, y1 - 5),
                    font,
                    font_scale,
                    color=(255, 255, 255),
                    thickness=thickness,
                    lineType=cv2.LINE_AA
                )

                detection = {
                    "image": image_path.name,
                    "label": label,
                    "confidence": confidence,
                    "bbox_xyxy": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    }
                }

                image_detections.append(detection)
                all_detections.append(detection)

        output_path = output_dir / image_path.name
        cv2.imwrite(str(output_path), image)

        print(
            f"Gespeichert: {output_path} | "
            f"Gesichter erkannt: {len(image_detections)}"
        )

    return all_detections

def box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def intersection_area(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)

    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(box_a, box_b):
    inter = intersection_area(box_a, box_b)
    union = box_area(box_a) + box_area(box_b) - inter

    if union == 0:
        return 0

    return inter / union


def box_center_inside(inner_box, outer_box):
    x1, y1, x2, y2 = inner_box
    ox1, oy1, ox2, oy2 = outer_box

    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    return ox1 <= cx <= ox2 and oy1 <= cy <= oy2


def draw_box(image, box, label, color, thickness=2):
    x1, y1, x2, y2 = map(int, box)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        color=color,
        thickness=thickness
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    text_thickness = 2

    text_size, _ = cv2.getTextSize(
        label,
        font,
        font_scale,
        text_thickness
    )

    text_width, text_height = text_size

    cv2.rectangle(
        image,
        (x1, max(y1 - text_height - 8, 0)),
        (x1 + text_width + 4, y1),
        color=color,
        thickness=-1
    )

    cv2.putText(
        image,
        label,
        (x1 + 2, y1 - 5),
        font,
        font_scale,
        color=(255, 255, 255),
        thickness=text_thickness,
        lineType=cv2.LINE_AA
    )

def draw_box_only(image, box, color, thickness=2):
    x1, y1, x2, y2 = map(int, box)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        color=color,
        thickness=thickness
    )

def process_combined_ppe_and_face(
    ppe_model,
    face_model,
    input_dir="test_images",
    output_dir="result_images",
    conf_ppe=0.25,
    conf_face=0.25,
    imgsz=640,
    helmet_labels=None,
    vest_labels=None,
    person_labels=None,
    face_labels=None,
    min_helmet_face_overlap=0.01,
    min_vest_person_iou=0.05,
    horizontal_tolerance_degrees=20
):
    """
    Kombiniert PPE-Detection und Face-Detection.

    Eine Person gilt als korrekt ausgerüstet, wenn:
    1. Eine Safety Vest zur Person gehört.
    2. Ein Gesicht zur Person gehört.
    3. Eine Helmet/Hardhat-Box mit der Face-Box überlappt.

    Korrekte Personen und zugehörige Boxen werden grün gezeichnet.
    Fehlerhafte Personen und zugehörige Boxen werden rot gezeichnet.

    Vorhandene Bilder in output_dir werden überschrieben.
    """

    if helmet_labels is None:
        helmet_labels = {"helmet", "hardhat", "Hardhat"}

    if vest_labels is None:
        vest_labels = {"vest", "safety vest", "Safety Vest"}

    if person_labels is None:
        person_labels = {"Person", "person"}

    if face_labels is None:
        face_labels = {"face", "Face"}

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    image_paths = [
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    ]

    if not image_paths:
        print(f"Keine Bilder in '{input_dir}' gefunden.")
        return []

    all_results = []

    for image_path in image_paths:
        image = cv2.imread(str(image_path))

        if image is None:
            print(f"Konnte Bild nicht lesen: {image_path}")
            continue

        ppe_results = ppe_model(
            source=str(image_path),
            conf=conf_ppe,
            imgsz=imgsz,
            verbose=False
        )

        face_results = face_model(
            source=str(image_path),
            conf=conf_face,
            imgsz=imgsz,
            verbose=False
        )

        ppe_result = ppe_results[0]
        face_result = face_results[0]

        persons = []
        helmets = []
        vests = []
        faces = []

        # PPE-Ergebnisse sammeln
        if ppe_result.boxes is not None:
            for box in ppe_result.boxes:
                cls_id = int(box.cls[0])
                label = ppe_model.names[cls_id]
                confidence = float(box.conf[0])
                bbox = tuple(map(int, box.xyxy[0].tolist()))

                item = {
                    "label": label,
                    "confidence": confidence,
                    "bbox": bbox
                }

                if label in person_labels:
                    persons.append(item)
                elif label in helmet_labels:
                    helmets.append(item)
                elif label in vest_labels:
                    vests.append(item)

        # Face-Ergebnisse sammeln
        if face_result.boxes is not None:
            for box in face_result.boxes:
                cls_id = int(box.cls[0])
                label = face_model.names.get(cls_id, "face")
                confidence = float(box.conf[0])
                bbox = tuple(map(int, box.xyxy[0].tolist()))

                item = {
                    "label": label,
                    "confidence": confidence,
                    "bbox": bbox
                }

                # Viele Face-Modelle haben nur eine Klasse.
                # Deshalb akzeptieren wir auch automatisch alle Boxen,
                # falls das Modell nur 1 Klasse kennt.
                if label in face_labels or len(face_model.names) == 1:
                    faces.append(item)

        image_summary = {
            "image": image_path.name,
            "persons": []
        }

        used_helmet_ids = set()
        used_vest_ids = set()
        used_face_ids = set()

        for person_idx, person in enumerate(persons):
            person_box = person["bbox"]

            # Gesichter finden, deren Mittelpunkt in der Person-Box liegt
            candidate_faces = [
                (face_idx, face)
                for face_idx, face in enumerate(faces)
                if box_center_inside(face["bbox"], person_box)
            ]

            # Vest finden, deren Mittelpunkt in der Person liegt oder die genug mit Person überlappt
            candidate_vests = []

            for vest_idx, vest in enumerate(vests):
                vest_box = vest["bbox"]

                vest_inside_person = box_center_inside(vest_box, person_box)
                vest_iou_person = iou(vest_box, person_box)

                if vest_inside_person or vest_iou_person >= min_vest_person_iou:
                    candidate_vests.append((vest_idx, vest, vest_iou_person))

            best_face = None
            best_face_idx = None

            if candidate_faces:
                # Nimm das größte Gesicht innerhalb der Person
                best_face_idx, best_face = max(
                    candidate_faces,
                    key=lambda x: box_area(x[1]["bbox"])
                )

            best_vest = None
            best_vest_idx = None

            if candidate_vests:
                # Nimm die Weste mit größter Überlappung zur Person
                best_vest_idx, best_vest, _ = max(
                    candidate_vests,
                    key=lambda x: x[2]
                )

            helmet_is_worn = False
            best_helmet = None
            best_helmet_idx = None
            best_helmet_face_overlap = 0

            if best_face is not None:
                face_box = best_face["bbox"]

                for helmet_idx, helmet in enumerate(helmets):
                    helmet_box = helmet["bbox"]

                    inter = intersection_area(helmet_box, face_box)
                    face_area = box_area(face_box)

                    if face_area == 0:
                        overlap_ratio = 0
                    else:
                        overlap_ratio = inter / face_area

                    if overlap_ratio > best_helmet_face_overlap:
                        best_helmet_face_overlap = overlap_ratio
                        best_helmet = helmet
                        best_helmet_idx = helmet_idx

                if best_helmet_face_overlap >= min_helmet_face_overlap:
                    helmet_is_worn = True

            vest_is_worn = best_vest is not None
            person_is_compliant = helmet_is_worn and vest_is_worn

            lying_down = False

            if best_face is not None:
                lying_down = person_is_lying_down(
                    person_box=person_box,
                    face_box=best_face["bbox"],
                    horizontal_tolerance_degrees=horizontal_tolerance_degrees
                )

            if lying_down:
                color = (0, 0, 255)  # rot
                person_label = "Emergency"
            elif person_is_compliant:
                color = (0, 255, 0)  # grün
                person_label = "Safety Equipment OK"
            else:
                color = (0, 255, 255)  # gelb
                person_label = "Safety Equipment NOT OK"

            # Person zeichnen: mit Status-Label
            person_label = (
                "Safety Equipment OK"
                if person_is_compliant
                else "Safety Equipment NOT OK"
            )

            draw_box(
                image,
                person_box,
                person_label,
                color=color,
                thickness=3
            )

            # Zugehöriges Gesicht zeichnen: nur Box, kein Label
            if best_face is not None:
                draw_box_only(
                    image,
                    best_face["bbox"],
                    color=color,
                    thickness=2
                )
                used_face_ids.add(best_face_idx)

            # Zugehörigen Helm zeichnen: nur Box, kein Label
            if best_helmet is not None:
                draw_box_only(
                    image,
                    best_helmet["bbox"],
                    color=color,
                    thickness=2
                )
                used_helmet_ids.add(best_helmet_idx)

            # Zugehörige Weste zeichnen: nur Box, kein Label
            if best_vest is not None:
                draw_box_only(
                    image,
                    best_vest["bbox"],
                    color=color,
                    thickness=2
                )
                used_vest_ids.add(best_vest_idx)

            person_result = {
                "person_index": person_idx,
                "person_bbox": person_box,
                "helmet_is_worn": helmet_is_worn,
                "vest_is_worn": vest_is_worn,
                "is_compliant": person_is_compliant,
                "is_lying_down": lying_down,
                "status_label": person_label,
                "face_bbox": best_face["bbox"] if best_face is not None else None,
                "helmet_bbox": best_helmet["bbox"] if best_helmet is not None else None,
                "vest_bbox": best_vest["bbox"] if best_vest is not None else None,
                "helmet_face_overlap_ratio": best_helmet_face_overlap,
                "person_face_angle_degrees": (
                    angle_between_person_and_face(person_box, best_face["bbox"])
                    if best_face is not None
                    else None
                )
            }

            image_summary["persons"].append(person_result)

        output_path = output_dir / image_path.name
        cv2.imwrite(str(output_path), image)

        all_results.append(image_summary)

        print(
            f"Gespeichert: {output_path} | "
            f"Personen: {len(persons)}"
        )

    return all_results


if __name__ == "__main__":
    pass