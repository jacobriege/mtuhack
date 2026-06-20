from bbox_utils import *

def analyze_frame_single_model(
    frame,
    model,
    conf=0.25,
    imgsz=640,
    head_labels=None,
    helmet_labels=None,
    vest_labels=None,
    person_labels=None,
    min_helmet_head_overlap=0.01,
    min_vest_person_iou=0.05,
    horizontal_tolerance_degrees=30,
    min_lying_width_height_ratio=1.25,
    debug=False
):
    """
    Analysiert ein einzelnes Bild/Frame mit einem YOLO-Modell.

    Erwartete Klassen:
        0: head
        1: helmet
        2: vest
        3: person

    Logik:
        Emergency:
            Person liegt.
            Rot, Label: Emergency

        Safety Equipment OK:
            Helmet wird getragen UND Vest wird getragen.
            Grün, Label: Safety Equipment OK

        Safety Equipment NOT OK:
            Helmet oder Vest fehlt.
            Gelb, Label: Safety Equipment NOT OK

    Nur die Person-Box bekommt ein Label.
    Head, Helmet und Vest bekommen nur Boxen ohne Text.
    """

    GREEN = (0, 255, 0)
    YELLOW = (0, 255, 255)
    RED = (0, 0, 255)

    if head_labels is None:
        head_labels = {"head", "Head"}

    if helmet_labels is None:
        helmet_labels = {"helmet", "Helmet", "hardhat", "Hardhat"}

    if vest_labels is None:
        vest_labels = {"vest", "Vest", "safety vest", "Safety Vest"}

    if person_labels is None:
        person_labels = {"person", "Person"}

    annotated_frame = frame.copy()

    heads = []
    helmets = []
    vests = []
    persons = []

    results = model(
        source=frame,
        conf=conf,
        imgsz=imgsz,
        verbose=False
    )

    result = results[0]

    if result.boxes is not None:
        for box in result.boxes:
            cls_id = int(box.cls[0])

            if isinstance(model.names, dict):
                label = model.names.get(cls_id, str(cls_id))
            else:
                label = model.names[cls_id]

            confidence = float(box.conf[0])
            bbox = tuple(map(int, box.xyxy[0].tolist()))

            item = {
                "class_id": cls_id,
                "label": label,
                "confidence": confidence,
                "bbox": bbox
            }

            if label in head_labels or cls_id == 0:
                heads.append(item)
            elif label in helmet_labels or cls_id == 1:
                helmets.append(item)
            elif label in vest_labels or cls_id == 2:
                vests.append(item)
            elif label in person_labels or cls_id == 3:
                persons.append(item)

    frame_results = {
        "persons": []
    }

    for person_idx, person in enumerate(persons):
        person_box = person["bbox"]

        # -------------------------
        # Passenden Kopf finden
        # -------------------------

        candidate_heads = []

        for head_idx, head in enumerate(heads):
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
        # Prüfen, ob Helm getragen wird
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

            if best_helmet_head_overlap >= min_helmet_head_overlap:
                helmet_is_worn = True

        vest_is_worn = best_vest is not None
        person_is_compliant = helmet_is_worn and vest_is_worn

        # -------------------------
        # Emergency-Erkennung
        # -------------------------

        lying_down = person_is_lying_down(
            person_box=person_box,
            head_box=best_head["bbox"] if best_head is not None else None,
            horizontal_tolerance_degrees=horizontal_tolerance_degrees,
            min_width_height_ratio=min_lying_width_height_ratio
        )

        person_head_angle = None

        if best_head is not None:
            person_head_angle = person_head_angle_degrees(
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
            "head_bbox": best_head["bbox"] if best_head is not None else None,
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

##############################################################################
##############################################################################
##############################################################################

if __name__ == "__main__":
    pass