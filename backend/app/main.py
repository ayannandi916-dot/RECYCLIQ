from fastapi import FastAPI
from sqlalchemy import text
from app.database.connection import engine
from app.api.auth import router as auth_router
from app.api.scans import router as scans_router
from app.api.ai import router as ai_router
from fastapi.middleware.cors import CORSMiddleware
from app.api.recycler import router as recycler_router
from app.api.recycler import admin_router as admin_recycler_router

app = FastAPI(
    title="RECYCLIQ API",
    description="AI-powered circular economy platform",
    version="0.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(scans_router)
app.include_router(ai_router)
app.include_router(recycler_router)
app.include_router(admin_recycler_router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to RECYCLIQ API",
        "status": "running",
        "version": "0.1.0"
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
            "database": "Neon PostgreSQL"
        }

    except Exception as e:
        return {
            "status": "disconnected",
            "error": str(e)
        }