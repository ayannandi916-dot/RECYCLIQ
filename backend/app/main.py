import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.connection import engine

from app.api.auth import router as auth_router
from app.api.scans import router as scans_router

from app.api.recycler import router as recycler_router
from app.api.recycler import admin_router as admin_recycler_router
from app.api.admin import router as admin_user_router
from app.api.admin_centres import router as admin_centres_router
from app.api.admin_analytics import router as admin_analytics_router


logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("%s starting up", settings.app_name)

    try:
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
    lifespan=lifespan
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
        "OPTIONS"
    ],
    allow_headers=[
        "Authorization",
        "Content-Type"
    ],
)


# Register API routers
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
        "version": settings.app_version
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "application": "RECYCLIQ"
    }


@app.get("/health/database")
async def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "PostgreSQL"
        }

    except Exception:
        logger.exception("Database health check failed")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is currently unavailable."
        )
        