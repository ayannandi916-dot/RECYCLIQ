import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from ultralytics import YOLO


BACKEND_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BACKEND_DIR / ".env")

DEFAULT_MODEL_PATH = (
    BACKEND_DIR
    / "weights"
    / "recycliq_yolo11n_v3_best.pt"
)


@lru_cache(maxsize=1)
def get_model() -> YOLO:
    """
    Load the trained RECYCLIQ YOLO model once.

    The cached model is reused across requests.
    """

    configured_path = os.getenv("YOLO_MODEL_PATH")

    if configured_path:
        model_path = Path(configured_path)

        if not model_path.is_absolute():
            model_path = BACKEND_DIR / model_path
    else:
        model_path = DEFAULT_MODEL_PATH

    if not model_path.is_file():
        raise FileNotFoundError(
            f"YOLO model checkpoint not found: {model_path}"
        )

    print(f"Loading RECYCLIQ model: {model_path}")

    return YOLO(str(model_path))