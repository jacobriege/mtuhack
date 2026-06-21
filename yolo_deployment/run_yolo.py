from run_yolo_utils import *
from ultralytics import YOLO

model = YOLO('/home/matthias/Desktop/mtuhack/yolo_deployment/best.pt')

run_mode = 3

if run_mode == 1: # Einzelbild verarbeiten
    result = process_image_single_model(
        image_path="test_images/test1.jpg",
        output_path="result_images/test1.jpg",
        model=model,
        conf=0.25,
        imgsz=640
    )
elif run_mode == 2: # Bildordner verarbeiten
    folder_results = process_image_folder_single_model(
        input_dir="test_images",
        output_dir="result_images",
        model=model,
        conf=0.25,
        imgsz=640,
        horizontal_tolerance_degrees=30,
        min_lying_width_height_ratio=1.25
    )
elif run_mode == 3: # Video verarbeiten
    video_results = process_video_single_model(
        input_video_path="/home/matthias/Desktop/mtuhack/yolo_deployment/test_video.mp4",
        output_video_path="/home/matthias/Desktop/mtuhack/yolo_deployment/output.mp4",
        model=model,
        conf=0.25,
        imgsz=512,
        horizontal_tolerance_degrees=30,
        min_lying_width_height_ratio=1.25,
        display=False
    )
elif run_mode == 4: # Live-Feed verarbeiten
    live_results = process_livefeed_single_model(
        camera_source=0,
        model=model,
        conf=0.25,
        imgsz=512,
        horizontal_tolerance_degrees=30,
        min_lying_width_height_ratio=1.25,
        display=True,
        save_output=False
    )