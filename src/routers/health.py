"""GET /health — Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "healthy", "version": "0.1.0"}
