"""
Pydantic schemas for MowthosOS API.

This module contains all request/response models for the API endpoints.
"""

from typing import Dict, Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

# Authentication schemas
class LoginRequest(BaseModel):
    """Request model for user login."""
    account: str = Field(..., description="Mammotion account email/username")
    password: str = Field(..., description="Account password")
    device_name: Optional[str] = Field(None, description="Specific device name to connect to")

class LoginResponse(BaseModel):
    """Response model for login endpoint."""
    success: bool
    message: str
    device_name: Optional[str] = None
    session_id: Optional[str] = None

# Mower status schemas
class MowerStatus(BaseModel):
    """Model for mower device status."""
    device_name: str
    online: bool
    work_mode: str
    work_mode_code: int
    battery_level: int
    charging_state: int
    blade_status: bool
    location: Optional[Dict[str, Any]] = None
    work_progress: Optional[int] = None
    work_area: Optional[int] = None
    last_updated: datetime

# Command schemas
class CommandRequest(BaseModel):
    """Request model for mower commands."""
    device_name: str = Field(..., description="Name of the device to control")

class CommandResponse(BaseModel):
    """Response model for command endpoints."""
    success: bool
    message: str
    command_sent: str

# Device schemas
class DeviceInfo(BaseModel):
    """Model for device information."""
    device_name: str
    device_type: str
    online: bool
    last_seen: Optional[datetime] = None

class DeviceList(BaseModel):
    """Response model for device listing."""
    devices: List[DeviceInfo]

# Error schemas
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# Health check schemas
class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    service: str
    timestamp: datetime
    version: str 