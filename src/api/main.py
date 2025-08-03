"""
FastAPI application for MowthosOS.

This module contains the main FastAPI application setup and configuration.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api.routes import mower, health, auth, devices, clusters, payments
    
# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="MowthosOS API",
        description="Professional robotic mower management system",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(devices.router, prefix="/api/v1", tags=["devices"])
    app.include_router(mower.router, prefix="/api/v1/mowers", tags=["mowers"])
    app.include_router(clusters.router, prefix="/api/v1", tags=["clusters"])
    app.include_router(payments.router, tags=["payments"])
    
    @app.on_event("startup")
    async def startup_event():
        """Application startup event."""
        logger.info("Starting MowthosOS API server...")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event."""
        logger.info("Shutting down MowthosOS API server...")
    
    return app

# Create the application instance
app = create_app() 