"""
Pytest configuration for MowthosOS tests.

This module contains pytest fixtures and configuration for the test suite.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from src.api.main import app

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)

@pytest.fixture
def sample_device_name():
    """Sample device name for testing."""
    return "Luba-TEST"

@pytest.fixture
def sample_account():
    """Sample account for testing."""
    return "test@example.com"

@pytest.fixture
def sample_password():
    """Sample password for testing."""
    return "testpassword123" 