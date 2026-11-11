from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app import main


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
        "database": "Neon PostgreSQL"
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

    assert response.status_code == 200

    assert response.json() == {
        "status": "disconnected",
        "error": "Database connection failed"
    }
    