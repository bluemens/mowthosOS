"""
Tests for health check endpoints.
"""

import pytest
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["service"] == "MowthosOS API"
    assert "timestamp" in data
    assert data["version"] == "1.0.0" 