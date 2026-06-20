from ultralytics import YOLO

def load_yolo_models(path_to_ppe_model, path_to_face_model):
    ppe_model = YOLO(path_to_ppe_model)
    face_model = YOLO(path_to_face_model)
    return ppe_model, face_model