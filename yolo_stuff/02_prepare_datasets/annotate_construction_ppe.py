from __future__ import annotations

import argparse
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_TARGET_CLASSES = {
    0: "helmet",
    2: "vest",
    6: "person",
}
CLASS_COLORS = {
    0: (255, 215, 0),
    2: (0, 180, 0),
    6: (220, 60, 60),
}


@dataclass(frozen=True)
class Annotation:
    class_id: int
    class_name: str
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class Sample:
    image_key: str
    label_key: str | None
    output_rel_path: Path


class FolderDataset:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.images_root = root / "images"
        self.labels_root = root / "labels"
        if not self.images_root.is_dir():
            raise FileNotFoundError(f"Kein 'images'-Ordner gefunden: {self.images_root}")
        if not self.labels_root.is_dir():
            raise FileNotFoundError(f"Kein 'labels'-Ordner gefunden: {self.labels_root}")

    def __enter__(self) -> FolderDataset:
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        return False

    def iter_samples(self) -> Iterable[Sample]:
        for image_path in sorted(self.images_root.rglob("*")):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            relative_to_images = image_path.relative_to(self.images_root)
            label_path = (self.labels_root / relative_to_images).with_suffix(".txt")
            yield Sample(
                image_key=str(image_path),
                label_key=str(label_path) if label_path.is_file() else None,
                output_rel_path=image_path.relative_to(self.root),
            )

    @staticmethod
    def read_image_bytes(image_key: str) -> bytes:
        return Path(image_key).read_bytes()

    @staticmethod
    def read_label_text(label_key: str | None) -> str:
        if not label_key:
            return ""
        return Path(label_key).read_text(encoding="utf-8")


class ZipDataset:
    def __init__(self, zip_path: Path) -> None:
        self.zip_path = zip_path
        self._archive: zipfile.ZipFile | None = None
        self._names: list[str] = []
        self._lower_lookup: dict[str, str] = {}

    def __enter__(self) -> ZipDataset:
        self._archive = zipfile.ZipFile(self.zip_path)
        self._names = self._archive.namelist()
        self._lower_lookup = {name.lower(): name for name in self._names}
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        if self._archive is not None:
            self._archive.close()
        self._archive = None
        self._names = []
        self._lower_lookup = {}
        return False

    @property
    def archive(self) -> zipfile.ZipFile:
        if self._archive is None:
            raise RuntimeError("ZIP-Datei ist nicht geoeffnet.")
        return self._archive

    def iter_samples(self) -> Iterable[Sample]:
        for image_name in sorted(self._names):
            posix_path = PurePosixPath(image_name)
            if not image_name.startswith("images/") or posix_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label_candidate = PurePosixPath("labels") / posix_path.relative_to("images").with_suffix(".txt")
            label_name = self._lower_lookup.get(label_candidate.as_posix().lower())
            yield Sample(
                image_key=image_name,
                label_key=label_name,
                output_rel_path=Path(*posix_path.parts),
            )

    def read_image_bytes(self, image_key: str) -> bytes:
        return self.archive.read(image_key)

    def read_label_text(self, label_key: str | None) -> str:
        if not label_key:
            return ""
        return self.archive.read(label_key).decode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Annotiert im Construction-PPE-Datensatz die Klassen 0, 2 und 6 "
            "(helmet, vest, person) und speichert die Bilder in einem separaten Ordner."
        )
    )
    parser.add_argument(
        "--input",
        default="external_datasets/construction-ppe.zip",
        help="Pfad zur ZIP-Datei oder zum entpackten Datensatzordner.",
    )
    parser.add_argument(
        "--output",
        default="external_datasets/construction-ppe_annotated",
        help="Ausgabeordner fuer die annotierten Bilder.",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        type=int,
        default=sorted(DEFAULT_TARGET_CLASSES),
        help="Zu zeichnende Klassen-IDs. Standard: 0 2 6",
    )
    parser.add_argument(
        "--only-matches",
        action="store_true",
        help="Speichert nur Bilder, die mindestens eine Zielklasse enthalten.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Gibt alle N Bilder einen Fortschrittsstand aus. Standard: 100",
    )
    return parser.parse_args()


def get_dataset(input_path: Path) -> FolderDataset | ZipDataset:
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        return ZipDataset(input_path)
    if input_path.is_dir():
        return FolderDataset(input_path)
    raise FileNotFoundError(f"Eingabe nicht gefunden: {input_path}")


def load_image(image_bytes: bytes):
    if PIL_AVAILABLE:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return "pillow", image, image.size
    if CV2_AVAILABLE:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Bild konnte nicht gelesen werden.")
        height, width = image.shape[:2]
        return "opencv", image, (width, height)
    raise RuntimeError(
        "Es wurde weder Pillow noch OpenCV gefunden. Installiere z.B. 'pip install pillow'."
    )


def parse_yolo_annotations(
    label_text: str,
    image_width: int,
    image_height: int,
    target_classes: dict[int, str],
) -> list[Annotation]:
    annotations: list[Annotation] = []

    for line_number, raw_line in enumerate(label_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            print(f"Warnung: Ueberspringe ungueltige Label-Zeile {line_number}: {raw_line!r}")
            continue

        try:
            class_id = int(float(parts[0]))
            x_center, y_center, width, height = map(float, parts[1:])
        except ValueError:
            print(f"Warnung: Konnte Label-Zeile {line_number} nicht lesen: {raw_line!r}")
            continue

        if class_id not in target_classes:
            continue

        x1 = int(round((x_center - width / 2) * image_width))
        y1 = int(round((y_center - height / 2) * image_height))
        x2 = int(round((x_center + width / 2) * image_width))
        y2 = int(round((y_center + height / 2) * image_height))

        x1 = max(0, min(x1, image_width - 1))
        y1 = max(0, min(y1, image_height - 1))
        x2 = max(0, min(x2, image_width - 1))
        y2 = max(0, min(y2, image_height - 1))

        if x2 <= x1 or y2 <= y1:
            continue

        annotations.append(
            Annotation(
                class_id=class_id,
                class_name=target_classes[class_id],
                box=(x1, y1, x2, y2),
            )
        )

    return annotations


def get_text_box_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except AttributeError:
        return draw.textsize(text, font=font)


def save_with_pillow(image: Image.Image, annotations: list[Annotation], output_path: Path) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    line_width = max(2, min(image.size) // 300)

    for annotation in annotations:
        x1, y1, x2, y2 = annotation.box
        color = CLASS_COLORS.get(annotation.class_id, (255, 255, 255))
        label = f"{annotation.class_id}: {annotation.class_name}"

        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)

        text_width, text_height = get_text_box_size(draw, label, font)
        text_top = max(0, y1 - text_height - 6)
        text_bottom = text_top + text_height + 4
        text_right = min(image.size[0], x1 + text_width + 6)
        draw.rectangle((x1, text_top, text_right, text_bottom), fill=color)
        draw.text((x1 + 3, text_top + 2), label, fill=(0, 0, 0), font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def save_with_opencv(image, annotations: list[Annotation], output_path: Path) -> None:
    height, width = image.shape[:2]
    line_width = max(2, min(width, height) // 300)
    font_scale = max(0.5, min(width, height) / 1000)
    font = cv2.FONT_HERSHEY_SIMPLEX

    for annotation in annotations:
        x1, y1, x2, y2 = annotation.box
        rgb = CLASS_COLORS.get(annotation.class_id, (255, 255, 255))
        color = (rgb[2], rgb[1], rgb[0])
        label = f"{annotation.class_id}: {annotation.class_name}"

        cv2.rectangle(image, (x1, y1), (x2, y2), color, line_width)

        (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, 1)
        text_top = max(0, y1 - text_height - baseline - 8)
        text_bottom = min(height, text_top + text_height + baseline + 8)
        text_right = min(width, x1 + text_width + 8)
        cv2.rectangle(image, (x1, text_top), (text_right, text_bottom), color, -1)
        cv2.putText(
            image,
            label,
            (x1 + 4, max(text_height + 2, text_bottom - baseline - 4)),
            font,
            font_scale,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(output_path), image)
    if not success:
        raise ValueError(f"Bild konnte nicht gespeichert werden: {output_path}")


def process_dataset(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    target_classes = {
        class_id: DEFAULT_TARGET_CLASSES.get(class_id, f"class_{class_id}")
        for class_id in args.classes
    }
    dataset = get_dataset(input_path)
    with dataset:
        samples = list(dataset.iter_samples())

        total_images = len(samples)
        saved_images = 0
        matched_images = 0
        missing_labels = 0
        failed_images = 0

        print(f"Eingabe: {input_path}")
        print(f"Ausgabe: {output_dir}")
        print(
            "Klassen: "
            + ", ".join(f"{class_id}={class_name}" for class_id, class_name in target_classes.items())
        )
        print(f"Gefundene Bilder: {total_images}")

        for index, sample in enumerate(samples, start=1):
            try:
                image_bytes = dataset.read_image_bytes(sample.image_key)
                backend, image, (image_width, image_height) = load_image(image_bytes)

                label_text = dataset.read_label_text(sample.label_key)
                if sample.label_key is None:
                    missing_labels += 1

                annotations = parse_yolo_annotations(label_text, image_width, image_height, target_classes)
                if annotations:
                    matched_images += 1

                if args.only_matches and not annotations:
                    continue

                output_path = output_dir / sample.output_rel_path
                if backend == "pillow":
                    save_with_pillow(image, annotations, output_path)
                else:
                    save_with_opencv(image, annotations, output_path)

                saved_images += 1
            except Exception as exc:
                failed_images += 1
                print(f"Warnung: Ueberspringe {sample.image_key}: {exc}")

            if args.progress_every > 0 and index % args.progress_every == 0:
                print(f"[{index}/{total_images}] verarbeitet")

    print()
    print("Fertig.")
    print(f"Gespeicherte Bilder: {saved_images}")
    print(f"Bilder mit Zielklassen: {matched_images}")
    print(f"Bilder ohne Label-Datei: {missing_labels}")
    print(f"Fehlgeschlagene Bilder: {failed_images}")


def main() -> int:
    args = parse_args()
    try:
        process_dataset(args)
    except Exception as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
