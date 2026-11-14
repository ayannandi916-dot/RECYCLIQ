import logging
import os
import threading
from pathlib import Path
from typing import Optional

import numpy as np
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

# Keep model initialization/cache replacement serialized.
_MODEL_LOCK = threading.Lock()

_MODEL: Optional[YOLO] = None
_MODEL_PATH: Optional[Path] = None


def _resolve_model_path() -> Path:
    """Resolve the configured checkpoint path."""

    configured_path = os.getenv("YOLO_MODEL_PATH")

    if configured_path and configured_path.strip():
        model_path = Path(configured_path.strip()).expanduser()

        if not model_path.is_absolute():
            model_path = BACKEND_DIR / model_path
    else:
        model_path = DEFAULT_MODEL_PATH

    return model_path.resolve()


def _validate_checkpoint(model_path: Path) -> None:
    """Validate checkpoint existence, type and size."""

    if not model_path.exists():
        logger.error("YOLO model checkpoint does not exist: %s", model_path)
        raise FileNotFoundError(
            f"YOLO model checkpoint not found: {model_path}"
        )

    if not model_path.is_file():
        logger.error("YOLO model checkpoint is not a file: %s", model_path)
        raise FileNotFoundError(
            f"YOLO model checkpoint is not a file: {model_path}"
        )

    try:
        checkpoint_size = model_path.stat().st_size
    except OSError as exc:
        logger.exception("Unable to inspect YOLO checkpoint: %s", model_path)
        raise OSError(
            f"Unable to inspect YOLO model checkpoint: {model_path}"
        ) from exc

    if checkpoint_size == 0:
        raise ValueError(
            f"YOLO model checkpoint is empty: {model_path}"
        )


def get_model() -> YOLO:
    """
    Return the initialized RECYCLIQ YOLO model.

    Initialization is serialized and cached by resolved checkpoint path.
    Changing YOLO_MODEL_PATH loads the newly configured checkpoint.
    Failed initialization is not cached.
    """

    global _MODEL, _MODEL_PATH

    model_path = _resolve_model_path()

    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_PATH == model_path:
            return _MODEL

        _validate_checkpoint(model_path)

        logger.info("Loading RECYCLIQ YOLO model from: %s", model_path)

        try:
            model = YOLO(str(model_path))
        except Exception as exc:
            logger.exception("Failed to initialize RECYCLIQ YOLO model.")
            raise RuntimeError(
                "Unable to initialize the RECYCLIQ YOLO model."
            ) from exc

        # Cache only after successful initialization.
        _MODEL = model
        _MODEL_PATH = model_path

        logger.info("RECYCLIQ YOLO model loaded successfully.")
        return _MODEL


def warmup_model(image_size: int = 640) -> None:
    """
    Load the model and run one synthetic inference to initialize its
    prediction path before real scan traffic arrives.

    This is opt-in at application startup because it adds startup time
    and consumes CPU. Warm-up failures are allowed to propagate.
    """

    if not isinstance(image_size, int) or image_size <= 0:
        raise ValueError("Warm-up image_size must be a positive integer.")

    model = get_model()
    sample_image = np.zeros(
        (image_size, image_size, 3),
        dtype=np.uint8,
    )

    logger.info("Warming up RECYCLIQ YOLO model.")
    model.predict(
        source=sample_image,
        conf=0.25,
        iou=0.70,
        imgsz=image_size,
        device="cpu",
        verbose=False,
    )
    logger.info("RECYCLIQ YOLO model warm-up completed.")


def clear_model_cache() -> None:
    """
    Clear the cached model.

    Intended for tests and controlled maintenance.
    Coordinate with active inference before production use.
    """

    global _MODEL, _MODEL_PATH

    with _MODEL_LOCK:
        _MODEL = None
        _MODEL_PATH = None
