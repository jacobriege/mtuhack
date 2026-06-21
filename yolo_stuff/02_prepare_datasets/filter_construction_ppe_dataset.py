from __future__ import annotations

import argparse
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SOURCE_CLASS_NAMES = {
    0: "helmet",
    2: "vest",
    6: "person",
}


def resolve_dataset_root(dataset_path: str | Path) -> Path:
    path = Path(dataset_path).expanduser().resolve()

    if path.is_dir():
        return path

    if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}:
        return read_dataset_root_from_yaml(path)

    raise FileNotFoundError(f"Datensatz nicht gefunden: {path}")


def read_dataset_root_from_yaml(yaml_path: Path) -> Path:
    dataset_root = yaml_path.parent

    for raw_line in yaml_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or not line.startswith("path:"):
            continue

        raw_value = line.split(":", 1)[1].strip().strip("'\"")
        if not raw_value:
            break

        candidate = Path(raw_value)
        dataset_root = candidate if candidate.is_absolute() else (yaml_path.parent / candidate)
        break

    return dataset_root.resolve()


def build_class_mapping(start_index: int) -> dict[int, int]:
    return {
        source_class_id: new_class_id
        for new_class_id, source_class_id in enumerate(SOURCE_CLASS_NAMES, start=start_index)
    }


def iter_image_paths(images_root: Path):
    for image_path in sorted(images_root.rglob("*")):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTENSIONS:
            yield image_path


def filter_label_file(
    label_path: Path,
    class_mapping: dict[int, int],
) -> tuple[list[str], int, int, bool]:
    if not label_path.is_file():
        return [], 0, 0, False

    kept_lines: list[str] = []
    kept_annotations = 0
    dropped_annotations = 0

    for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 5:
            print(f"Warnung: Ueberspringe ungueltige Zeile in {label_path}#{line_number}: {raw_line!r}")
            continue

        try:
            source_class_id = int(float(parts[0]))
        except ValueError:
            print(f"Warnung: Konnte Klassen-ID nicht lesen in {label_path}#{line_number}: {raw_line!r}")
            continue

        new_class_id = class_mapping.get(source_class_id)
        if new_class_id is None:
            dropped_annotations += 1
            continue

        kept_lines.append(" ".join([str(new_class_id), *parts[1:]]))
        kept_annotations += 1

    return kept_lines, kept_annotations, dropped_annotations, True


def write_dataset_yaml(target_root: Path, start_index: int) -> None:
    lines = [
        "path: .",
    ]

    for split_name in ("train", "val", "test"):
        if (target_root / "images" / split_name).exists():
            lines.append(f"{split_name}: images/{split_name}")

    lines.append("")
    lines.append("names:")

    for offset, class_name in enumerate(SOURCE_CLASS_NAMES.values(), start=start_index):
        lines.append(f"  {offset}: {class_name}")

    (target_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_filtered_ppe_dataset(
    dataset_path: str | Path,
    target_dir: str | Path,
    *,
    start_index: int = 0,
) -> dict[str, int]:
    source_root = resolve_dataset_root(dataset_path)
    target_root = Path(target_dir).expanduser().resolve()

    images_root = source_root / "images"
    labels_root = source_root / "labels"

    if not images_root.is_dir():
        raise FileNotFoundError(f"Kein 'images'-Ordner gefunden: {images_root}")

    if not labels_root.is_dir():
        raise FileNotFoundError(f"Kein 'labels'-Ordner gefunden: {labels_root}")

    class_mapping = build_class_mapping(start_index)
    target_root.mkdir(parents=True, exist_ok=True)

    stats = {
        "images_copied": 0,
        "label_files_written": 0,
        "annotations_kept": 0,
        "annotations_dropped": 0,
        "missing_label_files": 0,
    }

    for image_path in iter_image_paths(images_root):
        relative_image_path = image_path.relative_to(images_root)
        source_label_path = (labels_root / relative_image_path).with_suffix(".txt")

        target_image_path = target_root / "images" / relative_image_path
        target_label_path = (target_root / "labels" / relative_image_path).with_suffix(".txt")

        target_image_path.parent.mkdir(parents=True, exist_ok=True)
        target_label_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(image_path, target_image_path)
        stats["images_copied"] += 1

        filtered_lines, kept_annotations, dropped_annotations, label_exists = filter_label_file(
            source_label_path,
            class_mapping,
        )
        if not label_exists:
            stats["missing_label_files"] += 1

        label_content = "\n".join(filtered_lines)
        if label_content:
            label_content += "\n"
        target_label_path.write_text(label_content, encoding="utf-8")

        stats["label_files_written"] += 1
        stats["annotations_kept"] += kept_annotations
        stats["annotations_dropped"] += dropped_annotations

    write_dataset_yaml(target_root, start_index)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Kopiert einen Construction-PPE-Datensatz in einen neuen Ordner "
            "und behaelt nur helmet, vest und person in den Label-Dateien."
        )
    )
    parser.add_argument("dataset_path", help="Pfad zum Datensatzordner oder zur data.yaml")
    parser.add_argument("target_dir", help="Zielordner fuer den gefilterten Datensatz")
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help=(
            "Startwert fuer die neuen Klassen-IDs. Standard ist 0 fuer YOLO-Kompatibilitaet. "
            "Mit 1 erhaelt ihr 1=helmet, 2=vest, 3=person."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stats = copy_filtered_ppe_dataset(
        dataset_path=args.dataset_path,
        target_dir=args.target_dir,
        start_index=args.start_index,
    )

    print("Fertig.")
    print(f"Bilder kopiert: {stats['images_copied']}")
    print(f"Label-Dateien geschrieben: {stats['label_files_written']}")
    print(f"Annotationen behalten: {stats['annotations_kept']}")
    print(f"Annotationen entfernt: {stats['annotations_dropped']}")
    print(f"Fehlende Label-Dateien: {stats['missing_label_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
