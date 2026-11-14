import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from unittest.mock import MagicMock

from app.ai import model_loader


@pytest.fixture(autouse=True)
def clear_model_cache():
    model_loader.clear_model_cache()
    yield
    model_loader.clear_model_cache()


def create_checkpoint(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test-checkpoint")
    return path


def mock_yolo(monkeypatch):
    mocked = MagicMock()
    monkeypatch.setattr(model_loader, "YOLO", mocked)
    return mocked


# 1. Default checkpoint loading
def test_default_model_loading(monkeypatch, tmp_path):

    checkpoint = create_checkpoint(
        tmp_path / "recycliq_best.pt"
    )

    monkeypatch.setattr(
        model_loader,
        "DEFAULT_MODEL_PATH",
        checkpoint,
    )

    mocked = mock_yolo(monkeypatch)

    model = model_loader.get_model()

    mocked.assert_called_once_with(str(checkpoint.resolve()))

    assert model is mocked.return_value


# 2. Custom absolute checkpoint path
def test_custom_absolute_model_path(monkeypatch, tmp_path):

    checkpoint = create_checkpoint(
        tmp_path / "custom_model.pt"
    )

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(checkpoint),
    )

    mocked = mock_yolo(monkeypatch)

    model_loader.get_model()

    mocked.assert_called_once_with(str(checkpoint.resolve()))


# 3. Custom relative checkpoint path
def test_custom_relative_model_path(monkeypatch, tmp_path):

    checkpoint = create_checkpoint(
        tmp_path / "weights" / "custom_model.pt"
    )

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        "weights/custom_model.pt",
    )

    monkeypatch.setattr(
        model_loader,
        "BACKEND_DIR",
        tmp_path,
    )

    mocked = mock_yolo(monkeypatch)

    model_loader.get_model()

    mocked.assert_called_once_with(str(checkpoint.resolve()))


# 4. Missing checkpoint
def test_missing_model_checkpoint(monkeypatch, tmp_path):

    missing_checkpoint = tmp_path / "missing_model.pt"

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(missing_checkpoint),
    )

    with pytest.raises(
        FileNotFoundError,
        match="YOLO model checkpoint not found",
    ):
        model_loader.get_model()


# 5. Checkpoint path points to a directory
def test_checkpoint_path_is_directory(monkeypatch, tmp_path):

    directory = tmp_path / "weights"
    directory.mkdir()

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(directory),
    )

    with pytest.raises(
        FileNotFoundError,
        match="YOLO model checkpoint is not a file",
    ):
        model_loader.get_model()


# 6. Empty checkpoint
def test_empty_model_checkpoint(monkeypatch, tmp_path):

    checkpoint = tmp_path / "empty.pt"
    checkpoint.touch()

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(checkpoint),
    )

    with pytest.raises(
        ValueError,
        match="YOLO model checkpoint is empty",
    ):
        model_loader.get_model()


# 7. Model caching
def test_model_is_cached(monkeypatch, tmp_path):

    checkpoint = create_checkpoint(
        tmp_path / "model.pt"
    )

    monkeypatch.setattr(
        model_loader,
        "DEFAULT_MODEL_PATH",
        checkpoint,
    )

    mocked = mock_yolo(monkeypatch)

    first_model = model_loader.get_model()
    second_model = model_loader.get_model()

    assert first_model is second_model
    mocked.assert_called_once()


# 8. Environment path changes
def test_model_reloads_when_checkpoint_path_changes(
    monkeypatch,
    tmp_path,
):

    first_checkpoint = create_checkpoint(
        tmp_path / "first.pt"
    )

    second_checkpoint = create_checkpoint(
        tmp_path / "second.pt"
    )

    first_mock_model = MagicMock()
    second_mock_model = MagicMock()

    mocked = MagicMock(
        side_effect=[
            first_mock_model,
            second_mock_model,
        ]
    )

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mocked,
    )

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(first_checkpoint),
    )

    first_model = model_loader.get_model()

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(second_checkpoint),
    )

    second_model = model_loader.get_model()

    assert first_model is not second_model
    assert mocked.call_count == 2


# 9. Failed initialization is not cached
def test_failed_initialization_can_be_retried(
    monkeypatch,
    tmp_path,
):

    checkpoint = create_checkpoint(
        tmp_path / "model.pt"
    )

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(checkpoint),
    )

    mocked = MagicMock(
        side_effect=[
            ValueError("Invalid checkpoint"),
            MagicMock(),
        ]
    )

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mocked,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to initialize",
    ):
        model_loader.get_model()

    model = model_loader.get_model()

    assert model is not None
    assert mocked.call_count == 2


# 10. Concurrent initialization
def test_concurrent_requests_initialize_model_once(
    monkeypatch,
    tmp_path,
):

    checkpoint = create_checkpoint(
        tmp_path / "model.pt"
    )

    monkeypatch.setenv(
        "YOLO_MODEL_PATH",
        str(checkpoint),
    )

    call_lock = Lock()
    initialization_count = 0

    shared_model = MagicMock()

    def fake_yolo(path):

        nonlocal initialization_count

        with call_lock:
            initialization_count += 1

        time.sleep(0.1)

        return shared_model

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        fake_yolo,
    )

    with ThreadPoolExecutor(max_workers=8) as executor:

        models = list(
            executor.map(
                lambda _: model_loader.get_model(),
                range(8),
            )
        )

    assert initialization_count == 1

    assert all(
        model is shared_model
        for model in models
    )


# 11. Explicit cache clearing
def test_clear_model_cache(monkeypatch, tmp_path):

    checkpoint = create_checkpoint(
        tmp_path / "model.pt"
    )

    monkeypatch.setattr(
        model_loader,
        "DEFAULT_MODEL_PATH",
        checkpoint,
    )

    first_mock_model = MagicMock()
    second_mock_model = MagicMock()

    mocked = MagicMock(
        side_effect=[
            first_mock_model,
            second_mock_model,
        ]
    )

    monkeypatch.setattr(
        model_loader,
        "YOLO",
        mocked,
    )

    first_model = model_loader.get_model()

    model_loader.clear_model_cache()

    second_model = model_loader.get_model()

    assert first_model is not second_model
    assert mocked.call_count == 2
    