from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.predict(
    source="single_bottle.jpg",
    imgsz=640,
    conf=0.05,
    iou=0.45,
    save=True
)

for result in results:
    print("\nDETECTION REPORT")

    for box in result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])
        coordinates = box.xyxy[0].tolist()

        print({
            "class": model.names[class_id],
            "confidence": round(confidence, 3),
            "coordinates": [round(x, 2) for x in coordinates]
        })