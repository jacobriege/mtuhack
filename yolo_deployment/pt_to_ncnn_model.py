from ultralytics import YOLO

model = YOLO("yolo_stuff/01_models/ppe_yolo26n.pt")
model.export(format="ncnn", imgsz=640)