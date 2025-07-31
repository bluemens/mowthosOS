"""
Health check endpoints for MowthosOS API.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "MowthosOS API",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    } 