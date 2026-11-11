import importlib

import pytest
import sqlalchemy
import sqlalchemy.orm
import dotenv

import app.database.connection as connection


def test_missing_database_url(monkeypatch):

    monkeypatch.setattr(
        dotenv,
        "load_dotenv",
        lambda *args, **kwargs: None
    )

    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(
        ValueError,
        match="DATABASE_URL is not configured"
    ):
        importlib.reload(connection)


def test_engine_creation(monkeypatch):

    monkeypatch.setattr(
        dotenv,
        "load_dotenv",
        lambda *args, **kwargs: None
    )

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test:test@localhost/testdb"
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

    assert captured["url"] == (
        "postgresql://test:test@localhost/testdb"
    )

    assert captured["kwargs"]["pool_pre_ping"] is True
    assert connection.engine == "mock_engine"


def test_session_factory_configuration(monkeypatch):

    monkeypatch.setattr(
        dotenv,
        "load_dotenv",
        lambda *args, **kwargs: None
    )

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test:test@localhost/testdb"
    )

    captured = {}

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