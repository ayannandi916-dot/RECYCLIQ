import os

import pytest

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from app.main import app
from app.database.base import Base
from app.database.dependencies import get_db


@pytest.fixture(scope="session")
def test_engine():

    if os.getenv("ALEMBIC_USE_TEST_DB") == "1":
        pytest.fail(
            "Do not run integration tests while Alembic test mode is active."
        )

    env = dotenv_values(".env.test")
    database_url = env.get("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail(
            "TEST_DATABASE_URL is missing from backend/.env.test"
        )

    if not database_url.startswith(
        ("postgresql://", "postgresql+psycopg://")
    ):
        pytest.fail(
            "TEST_DATABASE_URL must be a PostgreSQL connection URL."
        )

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            print(f"\nConnected to test database: {result}")

        yield engine

    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine):

    connection = test_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    session = TestingSessionLocal()

    try:
        yield session

    finally:
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


@pytest.fixture
def api_client(db_session):

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client

    finally:
        app.dependency_overrides.pop(get_db, None)