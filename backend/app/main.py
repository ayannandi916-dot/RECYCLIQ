from fastapi import FastAPI

app = FastAPI(
    title="RECYCLIQ API",
    description="AI-powered circular economy platform",
    version="0.1.0"
)


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