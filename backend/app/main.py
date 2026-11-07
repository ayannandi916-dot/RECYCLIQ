from fastapi import FastAPI
from sqlalchemy import text
from app.database.connection import engine
from app.api.auth import router as auth_router

app = FastAPI(
    title="RECYCLIQ API",
    description="AI-powered circular economy platform",
    version="0.1.0"
)
app.include_router(auth_router)

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