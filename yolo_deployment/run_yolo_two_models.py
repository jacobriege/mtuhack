from yolo_utils_two_models import *
from ultralytics import YOLO

path_to_ppe_model = '/home/matthias/Desktop/mtuhack/yolo_deployment/ppe_yolo26n_ncnn_model'
path_to_face_model = '/home/matthias/Desktop/mtuhack/yolo_deployment/best_head_ncnn_model'
#path_to_head_model = ''

ppe_model = YOLO(path_to_ppe_model)
face_model = YOLO(path_to_face_model)

run_mode = 3

if run_mode == 1: # Einzelbild verarbeiten
        result = process_image(
        image_path="test_images/test1.jpg",
        output_path="result_images/test1.jpg",
        ppe_model=ppe_model,
        face_model=face_model,
        conf_ppe=0.25,
        conf_face=0.25,
        imgsz=640
    )
elif run_mode == 2: # Bildordner verarbeiten
    folder_results = process_image_folder(
        input_dir="test_images",
        output_dir="result_images",
        ppe_model=ppe_model,
        face_model=face_model,
        conf_ppe=0.25,
        conf_face=0.25,
        imgsz=640,
        horizontal_tolerance_degrees=30,
        min_lying_width_height_ratio=1.25
    )
elif run_mode == 3: # Video verarbeiten
    video_results = process_video(
        input_video_path="/home/matthias/Desktop/mtuhack/yolo_deployment/test_video.mp4",
        output_video_path="/home/matthias/Desktop/mtuhack/yolo_deployment/output.mp4",
        ppe_model=ppe_model,
        face_model=face_model,
        conf_ppe=0.25,
        conf_face=0.25,
        imgsz=640,
        horizontal_tolerance_degrees=30,
        min_lying_width_height_ratio=1.25,
        display=False
    )
elif run_mode == 4: # Live-Feed verarbeiten
    live_results = process_livefeed(
        camera_source=0,
        ppe_model=ppe_model,
        face_model=face_model,
        conf_ppe=0.25,
        conf_face=0.25,
        imgsz=512,
        horizontal_tolerance_degrees=30,
        min_lying_width_height_ratio=1.25,
        display=True,
        save_output=False
    )
