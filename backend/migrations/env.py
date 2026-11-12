
from logging.config import fileConfig

import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from app.database.base import Base

from app.models import (
    User,
    Material,
    WasteScan,
    ScanObject,
    ScanObjectMaterial,
    Recommendation,
    RecyclingCentre,
    RecyclingCentreMaterial,
    RecyclerApplication,
)


config = context.config

BASE_DIR = Path(__file__).resolve().parents[1]

USE_TEST_DATABASE = os.getenv("ALEMBIC_USE_TEST_DB") == "1"

if USE_TEST_DATABASE:
    load_dotenv(BASE_DIR / ".env.test", override=True)
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        raise ValueError("TEST_DATABASE_URL is not configured!")

else:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is not configured!")


config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Ignore unrelated Neon table during autogeneration.
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name == "playing_with_neon":
        return False

    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
