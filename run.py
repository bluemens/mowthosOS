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
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    ) 