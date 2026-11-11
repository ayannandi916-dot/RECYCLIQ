import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.ai import model_loader


@pytest.fixture(autouse=True)
def clear_model_cache():
    model_loader.get_model.cache_clear()
    yield
    model_loader.get_model.cache_clear()


# 1. Load model using default checkpoint
def test_default_model_loading(monkeypatch, tmp_path):

    checkpoint = tmp_path / "recycliq_best.pt"
    checkpoint.touch()

    monkeypatch.setattr(
        model_loader,
        "DEFAULT_MODEL_PATH",
        checkpoint
    )

    mock_yolo = MagicMock()

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mock_yolo
    )

    model = model_loader.get_model()

    mock_yolo.assert_called_once_with(str(checkpoint))

    assert model is mock_yolo.return_value


# 2. Load model using custom absolute path
def test_custom_absolute_model_path(monkeypatch, tmp_path):

    checkpoint = tmp_path / "custom_model.pt"
    checkpoint.touch()

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(checkpoint)
    )

    mock_yolo = MagicMock()

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mock_yolo
    )

    model_loader.get_model()

    mock_yolo.assert_called_once_with(str(checkpoint))


# 3. Load model using custom relative path
def test_custom_relative_model_path(monkeypatch, tmp_path):

    checkpoint = tmp_path / "weights" / "custom_model.pt"
    checkpoint.parent.mkdir()
    checkpoint.touch()

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        "weights/custom_model.pt"
    )

    monkeypatch.setattr(
        model_loader,
        "BACKEND_DIR",
        tmp_path
    )

    mock_yolo = MagicMock()

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mock_yolo
    )

    model_loader.get_model()

    assert mock_yolo.call_args.args[0] == str(checkpoint)
# 4. Missing checkpoint
def test_missing_model_checkpoint(monkeypatch, tmp_path):

    missing_checkpoint = tmp_path / "missing_model.pt"

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(missing_checkpoint)
    )

    with pytest.raises(
        FileNotFoundError,
        match="YOLO model checkpoint not found"
    ):
        model_loader.get_model()


# 5. Model should be cached
def test_model_is_cached(monkeypatch, tmp_path):

    checkpoint = tmp_path / "model.pt"
    checkpoint.touch()

    monkeypatch.setattr(
        model_loader,
        "DEFAULT_MODEL_PATH",
        checkpoint
    )

    mock_yolo = MagicMock()

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mock_yolo
    )

    first_model = model_loader.get_model()
    second_model = model_loader.get_model()

    assert first_model is second_model

    mock_yolo.assert_called_once()