from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.predict(
    source="waste_test.jpg",
    conf=0.10,
    save=True
)

for result in results:
    if result.boxes is None or len(result.boxes) == 0:
        print("No objects detected.")
        continue

    for box in result.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        print(
            f"Object: {model.names[class_id]} | "
            f"Confidence: {confidence:.2%}"
        )