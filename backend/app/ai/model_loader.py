import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from ultralytics import YOLO


logger = logging.getLogger(__name__)

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

    if configured_path and configured_path.strip():
        model_path = Path(configured_path.strip()).expanduser()

        if not model_path.is_absolute():
            model_path = BACKEND_DIR / model_path
    else:
        model_path = DEFAULT_MODEL_PATH

    model_path = model_path.resolve()

    # Validate checkpoint existence.
    if not model_path.exists():
        logger.error(
            "YOLO model checkpoint does not exist: %s",
            model_path,
        )
        raise FileNotFoundError(
            f"YOLO model checkpoint not found: {model_path}"
        )

    if not model_path.is_file():
        logger.error(
            "YOLO model checkpoint path is not a file: %s",
            model_path,
        )
        raise FileNotFoundError(
            f"YOLO model checkpoint is not a file: {model_path}"
        )

    logger.info(
        "Loading RECYCLIQ YOLO model from: %s",
        model_path,
    )

    try:
        model = YOLO(str(model_path))

    except Exception as exc:
        logger.exception(
            "Failed to initialize RECYCLIQ YOLO model."
        )

        raise RuntimeError(
            "Unable to initialize the RECYCLIQ YOLO model."
        ) from exc

    logger.info("RECYCLIQ YOLO model loaded successfully.")

    return model