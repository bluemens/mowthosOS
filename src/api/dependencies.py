"""
Shared dependencies for the API layer.

This module contains common dependencies used across multiple API endpoints.
"""

from typing import Generator
from fastapi import Depends, HTTPException, status
from pymammotion.mammotion.devices.mammotion import Mammotion

from src.services.mower.service import MowerService
from src.services.cluster.service import ClusterService
from src.core.session import SessionManager

# Service dependencies
def get_mower_service() -> MowerService:
    """Get mower service instance."""
    return MowerService()

def get_cluster_service() -> ClusterService:
    """Get cluster service instance."""
    return ClusterService()

def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    return SessionManager()

# PyMammotion dependency
def get_mammotion_instance() -> Mammotion:
    """Get PyMammotion instance for direct access when needed."""
    return Mammotion()

# Database dependencies (to be added when database is implemented)
# def get_db() -> Generator:
#     """Get database session."""
#     pass 