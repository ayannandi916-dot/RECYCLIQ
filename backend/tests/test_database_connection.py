import importlib

import pytest
import sqlalchemy
import sqlalchemy.orm
from pydantic import ValidationError

from app.core.config import Settings
import app.database.connection as connection


def test_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_engine_creation(monkeypatch):
    test_database_url = "postgresql://test:test@localhost/testdb"

    monkeypatch.setattr(
        connection.settings,
        "database_url",
        test_database_url
    )

    captured = {}

    def mock_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return "mock_engine"

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        mock_create_engine
    )

    importlib.reload(connection)

    assert captured["url"] == test_database_url
    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_size"] == 5
    assert captured["kwargs"]["max_overflow"] == 10
    assert connection.engine == "mock_engine"


def test_session_factory_configuration(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        connection.settings,
        "database_url",
        "postgresql://test:test@localhost/testdb"
    )

    monkeypatch.setattr(
        sqlalchemy,
        "create_engine",
        lambda *args, **kwargs: "mock_engine"
    )

    def mock_sessionmaker(**kwargs):
        captured.update(kwargs)
        return "mock_session"

    monkeypatch.setattr(
        sqlalchemy.orm,
        "sessionmaker",
        mock_sessionmaker
    )

    importlib.reload(connection)

    assert captured["autocommit"] is False
    assert captured["autoflush"] is False
    assert captured["bind"] == "mock_engine"
    assert connection.SessionLocal == "mock_session"