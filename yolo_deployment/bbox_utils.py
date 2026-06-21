from pathlib import Path
import cv2
import math

##############################################################################
# Box-Hilfsfunktionen
##############################################################################

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


def person_head_angle_degrees(person_box, head_box):
    """
    0 Grad  = waagrecht
    90 Grad = senkrecht
    """

    px, py = box_center(person_box)
    hx, hy = box_center(head_box)

    dx = hx - px
    dy = hy - py

    angle = abs(math.degrees(math.atan2(dy, dx)))

    if angle > 90:
        angle = 180 - angle

    return angle


def person_is_lying_down(
    person_box,
    head_box=None,
    horizontal_tolerance_degrees=30,
    min_width_height_ratio=1.25
):
    """
    Eine Person gilt als liegend, wenn:
    1. die Person-Box deutlich breiter als hoch ist
       ODER
    2. die Verbindungslinie Person-Mitte -> Head-Mitte ungefähr waagrecht ist.
    """

    width = box_width(person_box)
    height = box_height(person_box)

    if height == 0:
        return False

    width_height_ratio = width / height

    if width_height_ratio >= min_width_height_ratio:
        return True

    if head_box is not None:
        angle = person_head_angle_degrees(person_box, head_box)

        if angle <= horizontal_tolerance_degrees:
            return True

    return False

##############################################################################
# Hilfsfunktionen für das Zeichnen der BBoxes
##############################################################################

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

if __name__ == "__main__":
    pass