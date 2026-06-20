from pathlib import Path
import cv2
from analyze_single_frame import analyze_frame_single_model
import time

##############################################################################
# Single image
##############################################################################

def process_image_single_model(
    image_path,
    output_path,
    model,
    **analyze_kwargs
):
    image_path = Path(image_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame = cv2.imread(str(image_path))

    if frame is None:
        raise ValueError(f"Bild konnte nicht gelesen werden: {image_path}")

    annotated_frame, result = analyze_frame_single_model(
        frame=frame,
        model=model,
        **analyze_kwargs
    )

    cv2.imwrite(str(output_path), annotated_frame)

    return result

##############################################################################
# Directory of images
##############################################################################

def process_image_folder_single_model(
    input_dir,
    output_dir,
    model,
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

        result = process_image_single_model(
            image_path=image_path,
            output_path=output_path,
            model=model,
            **analyze_kwargs
        )

        all_results.append({
            "image": image_path.name,
            "result": result
        })

        print(f"Gespeichert: {output_path}")

    return all_results

##############################################################################
# Process video
##############################################################################

def process_video_single_model(
    input_video_path,
    output_video_path,
    model,
    display=False,
    max_frames=None,
    output_fps=None,
    resize_output=None,
    codec="mp4v",
    **analyze_kwargs
):
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

        annotated_frame, frame_result = analyze_frame_single_model(
            frame=frame,
            model=model,
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

##############################################################################
# Live feed/ webcam
##############################################################################

def process_livefeed_single_model(
    camera_source=0,
    model=None,
    display=True,
    save_output=False,
    output_video_path="result_videos/livefeed_output.mp4",
    output_fps=25,
    resize_output=None,
    codec="mp4v",
    **analyze_kwargs
):
    if model is None:
        raise ValueError("model darf nicht None sein.")

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

        annotated_frame, frame_result = analyze_frame_single_model(
            frame=frame,
            model=model,
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

##############################################################################
##############################################################################
##############################################################################

if __name__ == "__main__":
    pass