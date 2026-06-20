from pathlib import Path
import cv2
from ultralytics import YOLO
import math

from pathlib import Path
import cv2
import math


# -----------------------------
# Hilfsfunktionen
# -----------------------------

def box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def box_width(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1)


def box_height(box):
    x1, y1, x2, y2 = box
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


def person_face_angle_degrees(person_box, face_box):
    """
    Berechnet den Winkel der Verbindungslinie zwischen Mittelpunkt
    der Person-Box und Mittelpunkt der Face-Box.

    0 Grad  = waagrecht
    90 Grad = senkrecht
    """

    px, py = box_center(person_box)
    fx, fy = box_center(face_box)

    dx = fx - px
    dy = fy - py

    angle = abs(math.degrees(math.atan2(dy, dx)))

    # Auf 0..90 Grad normalisieren
    if angle > 90:
        angle = 180 - angle

    return angle


def person_is_lying_down(
    person_box,
    face_box=None,
    horizontal_tolerance_degrees=30,
    min_width_height_ratio=1.25
):
    """
    Eine Person gilt als liegend, wenn:
    1. die Person-Box deutlich breiter als hoch ist
       ODER
    2. die Verbindungslinie Person-Mitte -> Face-Mitte ungefähr waagrecht ist.
    """

    width = box_width(person_box)
    height = box_height(person_box)

    if height == 0:
        return False

    width_height_ratio = width / height

    # Regel 1: Person-Bounding-Box ist deutlich breiter als hoch
    if width_height_ratio >= min_width_height_ratio:
        return True

    # Regel 2: Gesicht liegt seitlich vom Person-Mittelpunkt
    if face_box is not None:
        angle = person_face_angle_degrees(person_box, face_box)

        if angle <= horizontal_tolerance_degrees:
            return True

    return False


def draw_box_with_label(image, box, label, color, thickness=3):
    x1, y1, x2, y2 = map(int, box)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        color=color,
        thickness=thickness
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    text_thickness = 2

    text_size, _ = cv2.getTextSize(
        label,
        font,
        font_scale,
        text_thickness
    )

    text_width, text_height = text_size

    # Label-Hintergrund
    cv2.rectangle(
        image,
        (x1, max(y1 - text_height - 10, 0)),
        (x1 + text_width + 6, y1),
        color=color,
        thickness=-1
    )

    # Textfarbe: schwarz auf gelb/grün, weiß auf rot
    if color == (0, 255, 255) or color == (0, 255, 0):
        text_color = (0, 0, 0)
    else:
        text_color = (255, 255, 255)

    cv2.putText(
        image,
        label,
        (x1 + 3, y1 - 6),
        font,
        font_scale,
        color=text_color,
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


# -----------------------------
# Hauptfunktion
# -----------------------------

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
    horizontal_tolerance_degrees=30,
    min_lying_width_height_ratio=1.25,
    debug=False
):
    """
    Kombiniert PPE-Detection und Face-Detection.

    Logik pro Person:
    - Emergency:
        Wenn Person als liegend erkannt wird.
        Farbe: rot
        Label: "Emergency"

    - Safety Equipment OK:
        Wenn Helm getragen wird UND Safety Vest getragen wird.
        Farbe: grün
        Label: "Safety Equipment OK"

    - Safety Equipment NOT OK:
        Wenn Helm oder Safety Vest fehlt.
        Farbe: gelb
        Label: "Safety Equipment NOT OK"

    Helm gilt als getragen, wenn eine Helmet/Hardhat-Box
    mit der Face-Box überlappt.

    Bei Helmet, Vest und Face werden nur Bounding Boxes gezeichnet,
    ohne Label und ohne Confidence.
    Nur die Person-Box bekommt ein Label.

    Ergebnisse werden in output_dir gespeichert.
    Vorhandene Dateien mit gleichem Namen werden überschrieben.
    """

    # OpenCV nutzt BGR, nicht RGB
    GREEN = (0, 255, 0)
    YELLOW = (0, 255, 255)
    RED = (0, 0, 255)

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

        # -----------------------------
        # Modelle anwenden
        # -----------------------------

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

        # -----------------------------
        # PPE-Ergebnisse sammeln
        # -----------------------------

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

        # -----------------------------
        # Face-Ergebnisse sammeln
        # -----------------------------

        if face_result.boxes is not None:
            for box in face_result.boxes:
                cls_id = int(box.cls[0])

                # Manche Face-Modelle haben model.names als dict,
                # manche als Liste. Diese Variante ist robust.
                if isinstance(face_model.names, dict):
                    label = face_model.names.get(cls_id, "face")
                else:
                    label = face_model.names[cls_id]

                confidence = float(box.conf[0])
                bbox = tuple(map(int, box.xyxy[0].tolist()))

                item = {
                    "label": label,
                    "confidence": confidence,
                    "bbox": bbox
                }

                # Wenn das Face-Modell nur eine Klasse hat,
                # akzeptieren wir alle Boxen als Gesicht.
                if label in face_labels or len(face_model.names) == 1:
                    faces.append(item)

        image_summary = {
            "image": image_path.name,
            "persons": []
        }

        # -----------------------------
        # Personen einzeln auswerten
        # -----------------------------

        for person_idx, person in enumerate(persons):
            person_box = person["bbox"]

            # -----------------------------
            # Passendes Gesicht zur Person finden
            # -----------------------------

            candidate_faces = []

            for face_idx, face in enumerate(faces):
                face_box = face["bbox"]

                face_center_in_person = box_center_inside(face_box, person_box)
                face_overlap_person = intersection_area(face_box, person_box) / max(box_area(face_box), 1)

                if face_center_in_person or face_overlap_person >= 0.50:
                    candidate_faces.append((face_idx, face))

            best_face = None
            best_face_idx = None

            if candidate_faces:
                # Nimm das größte erkannte Gesicht innerhalb/nahe der Person
                best_face_idx, best_face = max(
                    candidate_faces,
                    key=lambda x: box_area(x[1]["bbox"])
                )

            # -----------------------------
            # Passende Weste zur Person finden
            # -----------------------------

            candidate_vests = []

            for vest_idx, vest in enumerate(vests):
                vest_box = vest["bbox"]

                vest_center_in_person = box_center_inside(vest_box, person_box)
                vest_iou_person = iou(vest_box, person_box)
                vest_overlap_person = intersection_area(vest_box, person_box) / max(box_area(vest_box), 1)

                if (
                    vest_center_in_person
                    or vest_iou_person >= min_vest_person_iou
                    or vest_overlap_person >= 0.50
                ):
                    candidate_vests.append((vest_idx, vest, max(vest_iou_person, vest_overlap_person)))

            best_vest = None
            best_vest_idx = None

            if candidate_vests:
                # Nimm die Weste mit bester Zuordnung zur Person
                best_vest_idx, best_vest, _ = max(
                    candidate_vests,
                    key=lambda x: x[2]
                )

            # -----------------------------
            # Prüfen, ob Helm getragen wird
            # -----------------------------

            helmet_is_worn = False
            best_helmet = None
            best_helmet_idx = None
            best_helmet_face_overlap = 0

            if best_face is not None:
                face_box = best_face["bbox"]

                for helmet_idx, helmet in enumerate(helmets):
                    helmet_box = helmet["bbox"]

                    # Helm muss zur Person gehören
                    helmet_center_in_person = box_center_inside(helmet_box, person_box)
                    helmet_overlap_person = intersection_area(helmet_box, person_box) / max(box_area(helmet_box), 1)

                    if not (helmet_center_in_person or helmet_overlap_person >= 0.50):
                        continue

                    # Helm gilt als getragen, wenn er mit Face-Box überlappt
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

            # -----------------------------
            # Emergency-Erkennung
            # -----------------------------

            lying_down = person_is_lying_down(
                person_box=person_box,
                face_box=best_face["bbox"] if best_face is not None else None,
                horizontal_tolerance_degrees=horizontal_tolerance_degrees,
                min_width_height_ratio=min_lying_width_height_ratio
            )

            person_face_angle = None

            if best_face is not None:
                person_face_angle = person_face_angle_degrees(
                    person_box,
                    best_face["bbox"]
                )

            # -----------------------------
            # Farbe und Label festlegen
            # -----------------------------

            if lying_down:
                color = RED
                person_label = "Emergency"
            elif person_is_compliant:
                color = GREEN
                person_label = "Safety Equipment OK"
            else:
                color = YELLOW
                person_label = "Safety Equipment NOT OK"

            # -----------------------------
            # Debug-Ausgabe
            # -----------------------------

            if debug:
                width_height_ratio = box_width(person_box) / max(box_height(person_box), 1)

                print("Bild:", image_path.name)
                print("Person:", person_idx)
                print("Person bbox:", person_box)
                print("Face bbox:", best_face["bbox"] if best_face is not None else None)
                print("Helmet bbox:", best_helmet["bbox"] if best_helmet is not None else None)
                print("Vest bbox:", best_vest["bbox"] if best_vest is not None else None)
                print("Helmet is worn:", helmet_is_worn)
                print("Vest is worn:", vest_is_worn)
                print("Is compliant:", person_is_compliant)
                print("Person width/height:", round(width_height_ratio, 2))
                print(
                    "Person-Face angle:",
                    round(person_face_angle, 2) if person_face_angle is not None else None
                )
                print("Lying down:", lying_down)
                print("Label:", person_label)
                print("---")

            # -----------------------------
            # Zeichnen
            # -----------------------------

            # Person-Box mit Label
            draw_box_with_label(
                image=image,
                box=person_box,
                label=person_label,
                color=color,
                thickness=3
            )

            # Face-Box ohne Label
            if best_face is not None:
                draw_box_only(
                    image=image,
                    box=best_face["bbox"],
                    color=color,
                    thickness=2
                )

            # Helmet-Box ohne Label
            if best_helmet is not None:
                draw_box_only(
                    image=image,
                    box=best_helmet["bbox"],
                    color=color,
                    thickness=2
                )

            # Vest-Box ohne Label
            if best_vest is not None:
                draw_box_only(
                    image=image,
                    box=best_vest["bbox"],
                    color=color,
                    thickness=2
                )

            # -----------------------------
            # Ergebnis speichern
            # -----------------------------

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
                "person_face_angle_degrees": person_face_angle,
                "person_width_height_ratio": box_width(person_box) / max(box_height(person_box), 1)
            }

            image_summary["persons"].append(person_result)

        output_path = output_dir / image_path.name
        cv2.imwrite(str(output_path), image)

        all_results.append(image_summary)

        print(
            f"Gespeichert: {output_path} | "
            f"Personen erkannt: {len(persons)}"
        )

    return all_results

if __name__ == "__main__":
    pass