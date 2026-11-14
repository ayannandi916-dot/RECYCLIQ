"""Canonical paths for RECYCLIQ E3 evaluation tools."""
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ML_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
DATASET_DIR = BACKEND_DIR / "datasets" / "waste" / "cleaned" / "detection"
DATA_YAML = DATASET_DIR / "data.yaml"
MODEL_PATH = REPO_ROOT / "runs" / "runs" / "recycliq" / "yolo11n_100ep" / "weights" / "best.pt"


def require_paths(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Required RECYCLIQ asset(s) not found:\n" + "\n".join(missing))
