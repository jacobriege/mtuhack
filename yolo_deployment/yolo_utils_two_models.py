from pathlib import Path
import cv2
import math
import time


# --------------------------------------------------
# Box-Hilfsfunktionen
# --------------------------------------------------

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
    0 Grad  = waagrecht
    90 Grad = senkrecht
    """

    px, py = box_center(person_box)
    fx, fy = box_center(face_box)

    dx = fx - px
    dy = fy - py

    angle = abs(math.degrees(math.atan2(dy, dx)))

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

    if width_height_ratio >= min_width_height_ratio:
        return True

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

    label_y1 = max(y1 - text_height - 10, 0)
    label_y2 = y1

    cv2.rectangle(
        image,
        (x1, label_y1),
        (x1 + text_width + 6, label_y2),
        color=color,
        thickness=-1
    )

    if color in [(0, 255, 0), (0, 255, 255)]:
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
def analyze_frame(
    frame,
    ppe_model,
    face_model=None,
    conf_ppe=0.25,
    conf_face=0.25,
    imgsz=640,
    helmet_labels=None,
    vest_labels=None,
    person_labels=None,
    face_labels=None,
    head_labels=None,
    min_helmet_face_overlap=0.01,
    min_vest_person_iou=0.05,
    horizontal_tolerance_degrees=30,
    min_lying_width_height_ratio=1.25,
    debug=False
):
    """
    Analysiert ein einzelnes Bild/Frame.

    Unterstützt zwei Varianten:

    Variante A:
        ppe_model erkennt:
            head, helmet, vest, person
        Dann kann face_model=None sein.

    Variante B:
        ppe_model erkennt:
            helmet, vest, person
        face_model erkennt:
            face/head
        Dann wird face_model zusätzlich verwendet.

    Rückgabe:
        annotated_frame, frame_results
    """

    # OpenCV BGR-Farben
    GREEN = (0, 255, 0)
    YELLOW = (0, 255, 255)
    RED = (0, 0, 255)

    if helmet_labels is None:
        helmet_labels = {"helmet", "hardhat", "Hardhat"}

    if vest_labels is None:
        vest_labels = {"vest", "safety vest", "Safety Vest"}

    if person_labels is None:
        person_labels = {"person", "Person"}

    if face_labels is None:
        face_labels = {"face", "Face"}

    if head_labels is None:
        head_labels = {"head", "Head"}

    annotated_frame = frame.copy()

    persons = []
    helmets = []
    vests = []
    heads_or_faces = []

    # --------------------------------------------------
    # PPE-Modell auf Frame anwenden
    # --------------------------------------------------

    ppe_results = ppe_model(
        source=frame,
        conf=conf_ppe,
        imgsz=imgsz,
        verbose=False
    )

    ppe_result = ppe_results[0]

    if ppe_result.boxes is not None:
        for box in ppe_result.boxes:
            cls_id = int(box.cls[0])

            if isinstance(ppe_model.names, dict):
                label = ppe_model.names.get(cls_id, str(cls_id))
            else:
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
            elif label in head_labels or label in face_labels:
                heads_or_faces.append(item)

    # --------------------------------------------------
    # Optionales Face-Modell auf Frame anwenden
    # --------------------------------------------------

    if face_model is not None:
        face_results = face_model(
            source=frame,
            conf=conf_face,
            imgsz=imgsz,
            verbose=False
        )

        face_result = face_results[0]

        if face_result.boxes is not None:
            for box in face_result.boxes:
                cls_id = int(box.cls[0])

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

                # Wenn Face-Modell nur eine Klasse hat, akzeptieren wir alle Boxen.
                if label in face_labels or label in head_labels or len(face_model.names) == 1:
                    heads_or_faces.append(item)

    frame_results = {
        "persons": []
    }

    # --------------------------------------------------
    # Jede Person einzeln bewerten
    # --------------------------------------------------

    for person_idx, person in enumerate(persons):
        person_box = person["bbox"]

        # -------------------------
        # Passendes Gesicht/Head finden
        # -------------------------

        candidate_heads = []

        for head_idx, head in enumerate(heads_or_faces):
            head_box = head["bbox"]

            head_center_in_person = box_center_inside(head_box, person_box)
            head_overlap_person = intersection_area(head_box, person_box) / max(box_area(head_box), 1)

            if head_center_in_person or head_overlap_person >= 0.50:
                candidate_heads.append((head_idx, head))

        best_head = None
        best_head_idx = None

        if candidate_heads:
            best_head_idx, best_head = max(
                candidate_heads,
                key=lambda x: box_area(x[1]["bbox"])
            )

        # -------------------------
        # Passende Weste finden
        # -------------------------

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
                candidate_vests.append(
                    (vest_idx, vest, max(vest_iou_person, vest_overlap_person))
                )

        best_vest = None
        best_vest_idx = None

        if candidate_vests:
            best_vest_idx, best_vest, _ = max(
                candidate_vests,
                key=lambda x: x[2]
            )

        # -------------------------
        # Prüfen: Helm wird getragen?
        # -------------------------

        helmet_is_worn = False
        best_helmet = None
        best_helmet_idx = None
        best_helmet_head_overlap = 0

        if best_head is not None:
            head_box = best_head["bbox"]

            for helmet_idx, helmet in enumerate(helmets):
                helmet_box = helmet["bbox"]

                helmet_center_in_person = box_center_inside(helmet_box, person_box)
                helmet_overlap_person = intersection_area(helmet_box, person_box) / max(box_area(helmet_box), 1)

                if not (helmet_center_in_person or helmet_overlap_person >= 0.50):
                    continue

                inter = intersection_area(helmet_box, head_box)
                head_area = box_area(head_box)

                if head_area == 0:
                    overlap_ratio = 0
                else:
                    overlap_ratio = inter / head_area

                if overlap_ratio > best_helmet_head_overlap:
                    best_helmet_head_overlap = overlap_ratio
                    best_helmet = helmet
                    best_helmet_idx = helmet_idx

            if best_helmet_head_overlap >= min_helmet_face_overlap:
                helmet_is_worn = True

        vest_is_worn = best_vest is not None
        person_is_compliant = helmet_is_worn and vest_is_worn

        # -------------------------
        # Emergency-Erkennung
        # -------------------------

        lying_down = person_is_lying_down(
            person_box=person_box,
            face_box=best_head["bbox"] if best_head is not None else None,
            horizontal_tolerance_degrees=horizontal_tolerance_degrees,
            min_width_height_ratio=min_lying_width_height_ratio
        )

        person_head_angle = None

        if best_head is not None:
            person_head_angle = person_face_angle_degrees(
                person_box,
                best_head["bbox"]
            )

        # -------------------------
        # Farbe und Label
        # -------------------------

        if lying_down:
            color = RED
            person_label = "Emergency"
        elif person_is_compliant:
            color = GREEN
            person_label = "Safety Equipment OK"
        else:
            color = YELLOW
            person_label = "Safety Equipment NOT OK"

        # -------------------------
        # Zeichnen
        # -------------------------

        draw_box_with_label(
            image=annotated_frame,
            box=person_box,
            label=person_label,
            color=color,
            thickness=3
        )

        if best_head is not None:
            draw_box_only(
                image=annotated_frame,
                box=best_head["bbox"],
                color=color,
                thickness=2
            )

        if best_helmet is not None:
            draw_box_only(
                image=annotated_frame,
                box=best_helmet["bbox"],
                color=color,
                thickness=2
            )

        if best_vest is not None:
            draw_box_only(
                image=annotated_frame,
                box=best_vest["bbox"],
                color=color,
                thickness=2
            )

        person_result = {
            "person_index": person_idx,
            "status_label": person_label,
            "helmet_is_worn": helmet_is_worn,
            "vest_is_worn": vest_is_worn,
            "is_compliant": person_is_compliant,
            "is_lying_down": lying_down,
            "person_bbox": person_box,
            "head_or_face_bbox": best_head["bbox"] if best_head is not None else None,
            "helmet_bbox": best_helmet["bbox"] if best_helmet is not None else None,
            "vest_bbox": best_vest["bbox"] if best_vest is not None else None,
            "helmet_head_overlap_ratio": best_helmet_head_overlap,
            "person_head_angle_degrees": person_head_angle,
            "person_width_height_ratio": box_width(person_box) / max(box_height(person_box), 1)
        }

        frame_results["persons"].append(person_result)

        if debug:
            print(person_result)

    return annotated_frame, frame_results

def process_image(
    image_path,
    output_path,
    ppe_model,
    face_model=None,
    **analyze_kwargs
):
    image_path = Path(image_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame = cv2.imread(str(image_path))

    if frame is None:
        raise ValueError(f"Bild konnte nicht gelesen werden: {image_path}")

    annotated_frame, result = analyze_frame(
        frame=frame,
        ppe_model=ppe_model,
        face_model=face_model,
        **analyze_kwargs
    )

    cv2.imwrite(str(output_path), annotated_frame)

    return result

def process_image_folder(
    input_dir,
    output_dir,
    ppe_model,
    face_model=None,
    image_extensions=None,
    **analyze_kwargs
):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if image_extensions is None:
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    image_paths = [
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    ]

    all_results = []

    for image_path in image_paths:
        output_path = output_dir / image_path.name

        result = process_image(
            image_path=image_path,
            output_path=output_path,
            ppe_model=ppe_model,
            face_model=face_model,
            **analyze_kwargs
        )

        all_results.append({
            "image": image_path.name,
            "result": result
        })

        print(f"Gespeichert: {output_path}")

    return all_results

def process_video(
    input_video_path,
    output_video_path,
    ppe_model,
    face_model=None,
    display=False,
    max_frames=None,
    output_fps=None,
    resize_output=None,
    codec="mp4v",
    **analyze_kwargs
):
    """
    Wendet die Safety-Logik auf ein Video an.

    Parameter:
        input_video_path:
            Pfad zum Eingabevideo.

        output_video_path:
            Pfad zum Ausgabevideo, z. B. "result_videos/output.mp4".

        display:
            Wenn True, wird das Video während der Verarbeitung angezeigt.
            Mit Taste q kann abgebrochen werden.

        max_frames:
            Optional. Nur die ersten n Frames verarbeiten.

        output_fps:
            Optional. Wenn None, wird die FPS aus dem Eingabevideo übernommen.

        resize_output:
            Optional, z. B. (1280, 720).

        codec:
            Für .mp4 meistens "mp4v".
            Für .avi z. B. "XVID".
    """

    input_video_path = Path(input_video_path)
    output_video_path = Path(output_video_path)
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(input_video_path))

    if not cap.isOpened():
        raise ValueError(f"Video konnte nicht geöffnet werden: {input_video_path}")

    input_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if output_fps is None or output_fps <= 0:
        output_fps = input_fps if input_fps > 0 else 25

    if resize_output is not None:
        output_width, output_height = resize_output
    else:
        output_width, output_height = frame_width, frame_height

    fourcc = cv2.VideoWriter_fourcc(*codec)

    writer = cv2.VideoWriter(
        str(output_video_path),
        fourcc,
        output_fps,
        (output_width, output_height)
    )

    if not writer.isOpened():
        cap.release()
        raise ValueError(f"Output-Video konnte nicht erstellt werden: {output_video_path}")

    all_results = []
    frame_idx = 0
    start_time = time.time()

    print(f"Starte Videoverarbeitung: {input_video_path}")
    print(f"Frames laut Video: {total_frames}")
    print(f"Auflösung: {frame_width}x{frame_height}")
    print(f"FPS: {output_fps}")

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        if max_frames is not None and frame_idx >= max_frames:
            break

        annotated_frame, frame_result = analyze_frame(
            frame=frame,
            ppe_model=ppe_model,
            face_model=face_model,
            **analyze_kwargs
        )

        if resize_output is not None:
            annotated_frame = cv2.resize(
                annotated_frame,
                (output_width, output_height)
            )

        writer.write(annotated_frame)

        all_results.append({
            "frame_index": frame_idx,
            "result": frame_result
        })

        if display:
            cv2.imshow("Safety Detection", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("Abbruch durch Benutzer.")
                break

        frame_idx += 1

        if frame_idx % 25 == 0:
            elapsed = time.time() - start_time
            fps_processing = frame_idx / max(elapsed, 1e-6)
            print(f"Verarbeitete Frames: {frame_idx} | Processing FPS: {fps_processing:.2f}")

    cap.release()
    writer.release()

    if display:
        cv2.destroyAllWindows()

    print(f"Fertig. Ausgabevideo gespeichert unter: {output_video_path}")
    print(f"Verarbeitete Frames: {frame_idx}")

    return all_results


def process_livefeed(
    camera_source=0,
    ppe_model=None,
    face_model=None,
    display=True,
    save_output=False,
    output_video_path="result_videos/livefeed_output.mp4",
    output_fps=25,
    resize_output=None,
    codec="mp4v",
    **analyze_kwargs
):
    """
    Wendet die Safety-Logik auf einen Livefeed an.

    camera_source:
        0 = Standard-Webcam
        1 = zweite Kamera
        oder RTSP/HTTP-Stream-URL als String

    Beenden mit Taste q.
    """

    if ppe_model is None:
        raise ValueError("ppe_model darf nicht None sein.")

    cap = cv2.VideoCapture(camera_source)

    if not cap.isOpened():
        raise ValueError(f"Kamera/Stream konnte nicht geöffnet werden: {camera_source}")

    input_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    input_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if resize_output is not None:
        output_width, output_height = resize_output
    else:
        output_width, output_height = input_width, input_height

    writer = None

    if save_output:
        output_video_path = Path(output_video_path)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*codec)

        writer = cv2.VideoWriter(
            str(output_video_path),
            fourcc,
            output_fps,
            (output_width, output_height)
        )

        if not writer.isOpened():
            cap.release()
            raise ValueError(f"Output-Video konnte nicht erstellt werden: {output_video_path}")

    frame_idx = 0
    all_results = []

    print("Livefeed gestartet. Beenden mit Taste q.")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Kein Frame erhalten. Beende Livefeed.")
            break

        annotated_frame, frame_result = analyze_frame(
            frame=frame,
            ppe_model=ppe_model,
            face_model=face_model,
            **analyze_kwargs
        )

        if resize_output is not None:
            annotated_frame = cv2.resize(
                annotated_frame,
                (output_width, output_height)
            )

        if save_output and writer is not None:
            writer.write(annotated_frame)

        if display:
            cv2.imshow("Live Safety Detection", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("Abbruch durch Benutzer.")
                break

        all_results.append({
            "frame_index": frame_idx,
            "result": frame_result
        })

        frame_idx += 1

    cap.release()

    if writer is not None:
        writer.release()

    cv2.destroyAllWindows()

    print(f"Livefeed beendet. Frames verarbeitet: {frame_idx}")

    if save_output:
        print(f"Video gespeichert unter: {output_video_path}")

    return all_results

