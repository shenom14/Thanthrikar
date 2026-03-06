import os
from fastapi import APIRouter
from backend.routers import candidates, interviews

# Create a master router that includes all modular API routers
api_router = APIRouter()

api_router.include_router(candidates.router)
api_router.include_router(interviews.router)

# Health endpoint for DevOps monitoring (e.g., Kubernetes liveness probe)
@api_router.get("/health", tags=["system"])
def health_check():
    """
    Simple probe checking if the API is responsive.
    Could be expanded to ping SQLite or Chroma.
    """
    return {
        "status": "healthy",
        "service": "AI Interview Copilot",
        "environment": os.getenv("ENVIRONMENT", "development")
    }
