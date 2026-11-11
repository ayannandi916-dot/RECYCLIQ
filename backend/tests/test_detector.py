import cv2
import numpy as np
import pytest

from unittest.mock import MagicMock

from app.ai import detector


# Generate a real image in memory
def create_test_image(width=640, height=480):
    image = np.zeros((height, width, 3), dtype=np.uint8)

    success, encoded = cv2.imencode(".jpg", image)

    assert success

    return encoded.tobytes()


# Simulate YOLO tensor behaviour
class FakeTensor:
    def __init__(self, value):
        self.value = value

    def cpu(self):
        return self

    def tolist(self):
        return self.value

    def item(self):
        return self.value


# Simulate one YOLO bounding box
class FakeBox:
    def __init__(self, coordinates, class_id, confidence):
        self.xyxy = [FakeTensor(coordinates)]
        self.cls = [FakeTensor(class_id)]
        self.conf = [FakeTensor(confidence)]


# Simulate YOLO detection results
class FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


# Simulate YOLO model
class FakeModel:
    def __init__(self, boxes, names=None):
        self.names = names or {
            0: "PLASTIC",
            1: "METAL",
            2: "GLASS"
        }

        self.boxes = boxes
        self.predict = MagicMock(
            return_value=[FakeResult(boxes)]
        )


# 1. Empty image bytes
def test_empty_image():
    with pytest.raises(ValueError, match="Image data is empty"):
        detector.detect_waste(b"")


# 2. Invalid image bytes
def test_invalid_image():
    with pytest.raises(ValueError, match="Unable to decode image"):
        detector.detect_waste(b"invalid image data")


# 3. Valid image with no detections
def test_no_detections(monkeypatch):
    model = FakeModel(boxes=[])

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    result = detector.detect_waste(create_test_image())

    assert result["image_width"] == 640
    assert result["image_height"] == 480
    assert result["total_detections"] == 0
    assert result["detections"] == []


# 4. Single object detection
def test_single_object_detection(monkeypatch):
    boxes = [
        FakeBox(
            coordinates=[100.123, 120.456, 300.789, 350.123],
            class_id=0,
            confidence=0.95678
        )
    ]

    model = FakeModel(boxes)

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    result = detector.detect_waste(create_test_image())

    assert result["total_detections"] == 1

    detection = result["detections"][0]

    assert detection["class_id"] == 0
    assert detection["label"] == "PLASTIC"
    assert detection["confidence"] == 0.9568

    assert detection["bounding_box"] == {
        "x1": 100.12,
        "y1": 120.46,
        "x2": 300.79,
        "y2": 350.12
    }


# 5. Multiple object detections
def test_multiple_object_detections(monkeypatch):
    boxes = [
        FakeBox([10, 20, 100, 120], 0, 0.95),
        FakeBox([150, 160, 250, 260], 1, 0.87),
        FakeBox([300, 310, 400, 410], 2, 0.91)
    ]

    model = FakeModel(boxes)

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    result = detector.detect_waste(create_test_image())

    assert result["total_detections"] == 3

    labels = [
        detection["label"]
        for detection in result["detections"]
    ]

    assert labels == ["PLASTIC", "METAL", "GLASS"]


# 6. Confidence values must be between 0 and 1
def test_detection_confidence_range(monkeypatch):
    boxes = [
        FakeBox([10, 20, 100, 120], 0, 0.75)
    ]

    model = FakeModel(boxes)

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    result = detector.detect_waste(create_test_image())

    confidence = result["detections"][0]["confidence"]

    assert 0 <= confidence <= 1


# 7. Bounding box coordinates must be valid
def test_bounding_box_coordinates(monkeypatch):
    boxes = [
        FakeBox([50, 60, 200, 250], 0, 0.90)
    ]

    model = FakeModel(boxes)

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    result = detector.detect_waste(create_test_image())

    box = result["detections"][0]["bounding_box"]

    assert box["x1"] < box["x2"]
    assert box["y1"] < box["y2"]


# 8. YOLO prediction configuration
def test_model_prediction_configuration(monkeypatch):
    model = FakeModel(boxes=[])

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    detector.detect_waste(create_test_image())

    model.predict.assert_called_once()

    kwargs = model.predict.call_args.kwargs

    assert kwargs["conf"] == 0.25
    assert kwargs["iou"] == 0.70
    assert kwargs["imgsz"] == 640
    assert kwargs["device"] == "cpu"
    assert kwargs["verbose"] is False


# 9. Model names provided as a list
def test_model_names_as_list(monkeypatch):
    boxes = [
        FakeBox([10, 20, 100, 120], 1, 0.88)
    ]

    model = FakeModel(
        boxes,
        names=["BIODEGRADABLE", "CARDBOARD", "GLASS"]
    )

    monkeypatch.setattr(
        detector,
        "get_model",
        lambda: model
    )

    result = detector.detect_waste(create_test_image())

    assert result["detections"][0]["label"] == "CARDBOARD"