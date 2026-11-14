from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app import main
from unittest.mock import MagicMock, AsyncMock
import pytest
import anyio

client = TestClient(app)


# 1. Root endpoint
def test_root_endpoint():

    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Welcome to RECYCLIQ API"
    assert data["status"] == "running"
    assert data["version"] == "0.1.0"


# 2. General health endpoint
def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["application"] == "RECYCLIQ"


# 3. Database health check succeeds
def test_database_health_success(monkeypatch):

    mock_connection = MagicMock()
    mock_engine = MagicMock()

    mock_engine.connect.return_value.__enter__.return_value = (
        mock_connection
    )

    monkeypatch.setattr(
        main,
        "engine",
        mock_engine
    )

    response = client.get("/health/database")

    assert response.status_code == 200

    assert response.json() == {
        "status": "connected",
        "database": "PostgreSQL"
    }

    mock_connection.execute.assert_called_once()


# 4. Database health check fails
def test_database_health_failure(monkeypatch):

    mock_engine = MagicMock()

    mock_engine.connect.side_effect = RuntimeError(
        "Database connection failed"
    )

    monkeypatch.setattr(
        main,
        "engine",
        mock_engine
    )

    response = client.get("/health/database")

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Database is currently unavailable."
    }

# Application lifecycle tests




def test_application_startup_and_shutdown(monkeypatch):
    mock_engine = MagicMock()

    monkeypatch.setattr(main, "engine", mock_engine)

    async def run_test():
        async with main.lifespan(app):
            mock_engine.dispose.assert_not_called()

        mock_engine.dispose.assert_called_once()

    anyio.run(run_test)


def test_lifespan_disposes_engine_after_exception(monkeypatch):
    mock_engine = MagicMock()

    monkeypatch.setattr(main, "engine", mock_engine)

    async def run_test():
        with pytest.raises(RuntimeError, match="Application failure"):
            async with main.lifespan(app):
                raise RuntimeError("Application failure")

        mock_engine.dispose.assert_called_once()

    anyio.run(run_test)


def test_lifespan_handles_engine_disposal_failure(monkeypatch):
    mock_engine = MagicMock()

    mock_engine.dispose.side_effect = RuntimeError(
        "Engine disposal failed"
    )

    monkeypatch.setattr(main, "engine", mock_engine)

    async def run_test():
        async with main.lifespan(app):
            pass

        mock_engine.dispose.assert_called_once()

    anyio.run(run_test)

def test_fastapi_client_triggers_lifespan(monkeypatch):

    mock_engine = MagicMock()

    monkeypatch.setattr(
        main,
        "engine",
        mock_engine
    )

    with TestClient(app) as test_client:
        response = test_client.get("/health")

        assert response.status_code == 200

    mock_engine.dispose.assert_called_once()

def test_cors_allows_configured_frontend_origin():

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )

    assert response.status_code == 200

    assert response.headers[
        "access-control-allow-origin"
    ] == "http://localhost:3000"

def test_database_health_does_not_expose_exception(
    monkeypatch
):

    mock_engine = MagicMock()

    mock_engine.connect.side_effect = RuntimeError(
        "Sensitive database connection details"
    )

    monkeypatch.setattr(
        main,
        "engine",
        mock_engine
    )

    response = client.get("/health/database")

    assert response.status_code == 503

    assert "Sensitive database connection details" not in (
        response.text
    )


# E7.5: readiness and model startup warm-up
def test_readiness_check_success(monkeypatch):
    mock_model = MagicMock()
    database_probe = MagicMock()

    monkeypatch.setattr(main, "_check_database_connection", database_probe)
    monkeypatch.setattr(main, "get_model", MagicMock(return_value=mock_model))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "application": "RECYCLIQ",
        "database": "connected",
        "model": "loaded",
    }
    database_probe.assert_called_once()


def test_readiness_check_returns_503_when_model_unavailable(monkeypatch):
    monkeypatch.setattr(main, "_check_database_connection", MagicMock())
    monkeypatch.setattr(
        main,
        "get_model",
        MagicMock(side_effect=RuntimeError("model load failure")),
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Application dependencies are not ready."
    }
    assert "model load failure" not in response.text


def test_readiness_check_returns_503_when_database_unavailable(monkeypatch):
    database_probe = MagicMock(
        side_effect=RuntimeError("database unavailable")
    )
    model_getter = MagicMock()

    monkeypatch.setattr(main, "_check_database_connection", database_probe)
    monkeypatch.setattr(main, "get_model", model_getter)

    response = client.get("/health/ready")

    assert response.status_code == 503
    model_getter.assert_not_called()


def test_startup_warmup_runs_when_enabled(monkeypatch):
    mock_engine = MagicMock()
    warmup = MagicMock()

    monkeypatch.setattr(main, "engine", mock_engine)
    monkeypatch.setattr(main, "_startup_warmup_enabled", lambda: True)
    monkeypatch.setattr(main, "warmup_model", warmup)

    async def run_test():
        async with main.lifespan(app):
            pass

    anyio.run(run_test)

    warmup.assert_called_once()
    mock_engine.dispose.assert_called_once()


def test_startup_warmup_is_skipped_by_default(monkeypatch):
    mock_engine = MagicMock()
    warmup = MagicMock()

    monkeypatch.setattr(main, "engine", mock_engine)
    monkeypatch.setattr(main, "_startup_warmup_enabled", lambda: False)
    monkeypatch.setattr(main, "warmup_model", warmup)

    async def run_test():
        async with main.lifespan(app):
            pass

    anyio.run(run_test)

    warmup.assert_not_called()
    mock_engine.dispose.assert_called_once()


def test_startup_warmup_failure_aborts_startup_and_disposes_engine(monkeypatch):
    mock_engine = MagicMock()
    warmup = MagicMock(side_effect=RuntimeError("warm-up failed"))

    monkeypatch.setattr(main, "engine", mock_engine)
    monkeypatch.setattr(main, "_startup_warmup_enabled", lambda: True)
    monkeypatch.setattr(main, "warmup_model", warmup)

    async def run_test():
        with pytest.raises(RuntimeError, match="warm-up failed"):
            async with main.lifespan(app):
                pass

    anyio.run(run_test)

    warmup.assert_called_once()
    mock_engine.dispose.assert_called_once()
