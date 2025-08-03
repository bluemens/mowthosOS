#!/usr/bin/env python3
"""
Entry point for MowthosOS API server.

This script starts the FastAPI application using the reorganized code structure.
"""

import uvicorn
from src.api.main import app
from src.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    ) 