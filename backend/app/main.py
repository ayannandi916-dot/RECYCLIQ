import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.database.connection import engine
from app.ai.model_loader import get_model, warmup_model

from app.api.auth import router as auth_router
from app.api.scans import router as scans_router
from app.api.recycler import router as recycler_router
from app.api.recycler import admin_router as admin_recycler_router
from app.api.admin import router as admin_user_router
from app.api.admin_centres import router as admin_centres_router
from app.api.admin_analytics import router as admin_analytics_router


logger = logging.getLogger(__name__)


def _startup_warmup_enabled() -> bool:
    """Read the opt-in model warm-up flag."""
    return os.getenv("YOLO_WARMUP_ON_STARTUP", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _check_database_connection() -> None:
    """Run a short database connectivity probe."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s starting up", settings.app_name)

    try:
        if _startup_warmup_enabled():
            logger.info("YOLO startup warm-up is enabled.")
            # Model loading/inference is blocking; keep it off the event loop.
            await run_in_threadpool(warmup_model)
        else:
            logger.info(
                "YOLO startup warm-up is disabled; model will load lazily."
            )

        yield

    finally:
        logger.info("%s shutting down", settings.app_name)

        try:
            engine.dispose()
            logger.info("Database engine disposed successfully.")
        except Exception:
            logger.exception("Failed to dispose database engine.")


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


# Register API routers.
app.include_router(auth_router)
app.include_router(scans_router)
app.include_router(recycler_router)
app.include_router(admin_recycler_router)
app.include_router(admin_user_router)
app.include_router(admin_centres_router)
app.include_router(admin_analytics_router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to RECYCLIQ API",
        "status": "running",
        "version": settings.app_version,
    }


@app.get("/health")
async def health_check():
    """Liveness check: confirms the API process is responding."""
    return {
        "status": "healthy",
        "application": "RECYCLIQ",
    }


@app.get("/health/database")
async def database_health_check():
    """Database dependency check."""
    try:
        await run_in_threadpool(_check_database_connection)
        return {
            "status": "connected",
            "database": "PostgreSQL",
        }
    except Exception as exc:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is currently unavailable.",
        ) from exc


@app.get("/health/ready")
async def readiness_check():
    """
    Readiness check for traffic routing.

    Confirms both the database and YOLO model can be accessed. If the
    model has not loaded yet, this check may trigger its lazy load.
    """

    try:
        await run_in_threadpool(_check_database_connection)
        await run_in_threadpool(get_model)

        return {
            "status": "ready",
            "application": "RECYCLIQ",
            "database": "connected",
            "model": "loaded",
        }

    except Exception as exc:
        logger.exception("Application readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application dependencies are not ready.",
        ) from exc
