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

# Mower command enum and schemas
from enum import Enum

class MowerCommand(str, Enum):
    """Enum for mower commands."""
    START_MOW = "start_mow"
    STOP_MOW = "stop_mow"
    PAUSE_MOW = "pause_mow"
    RESUME_MOW = "resume_mow"
    RETURN_TO_DOCK = "return_to_dock"
    START_CHARGE = "start_charge"
    STOP_CHARGE = "stop_charge"

class MowerSession(BaseModel):
    """Model for mower session."""
    session_id: str
    account: str
    devices: List[str]
    created_at: datetime
    last_activity: datetime

class MowingHistory(BaseModel):
    """Model for mowing history."""
    device_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    area_mowed: Optional[float] = None
    battery_start: Optional[int] = None
    battery_end: Optional[int] = None

class MowingZone(BaseModel):
    """Model for mowing zone."""
    zone_id: str
    name: str
    area: float
    perimeter: List[Dict[str, float]]
    is_active: bool

class MowerSettings(BaseModel):
    """Model for mower settings."""
    device_name: str
    cutting_height: Optional[int] = None
    cutting_speed: Optional[int] = None
    blade_speed: Optional[int] = None
    auto_schedule: Optional[bool] = None

# Address schemas
class Address(BaseModel):
    """Model for address information."""
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state_province: str
    postal_code: str
    country: str = "US"
    latitude: Optional[float] = None
    longitude: Optional[float] = None

# Cluster schemas
class Cluster(BaseModel):
    """Model for cluster information."""
    id: str
    name: str
    host_user_id: str
    host_address_id: str
    status: str
    max_capacity: int
    current_capacity: int
    created_at: datetime
    updated_at: datetime

class HostRegistration(BaseModel):
    """Model for host registration."""
    user_id: str
    address_id: str
    cluster_name: Optional[str] = None

class NeighborJoinRequest(BaseModel):
    """Model for neighbor join request."""
    user_id: str
    address_id: str
    cluster_id: str

class ClusterAssignment(BaseModel):
    """Model for cluster assignment."""
    cluster_id: str
    user_id: str
    address_id: str
    assigned_at: datetime

class ClusterStats(BaseModel):
    """Model for cluster statistics."""
    cluster_id: str
    total_members: int
    total_devices: int
    average_battery: float
    last_activity: datetime

class RouteOptimization(BaseModel):
    """Model for route optimization."""
    cluster_id: str
    route: List[Address]
    total_distance: float
    estimated_duration: int
    optimized_at: datetime

# Notification schemas
class NotificationType(str, Enum):
    """Types of notifications."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBSOCKET = "websocket"
    IN_APP = "in_app"

class NotificationChannel(str, Enum):
    """Notification channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBSOCKET = "websocket"
    IN_APP = "in_app"

class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationTemplate(BaseModel):
    """Model for notification templates."""
    id: str
    name: str
    subject: str
    body: str
    channels: List[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL

class Notification(BaseModel):
    """Model for notifications."""
    id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[NotificationChannel]
    read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None

# Schedule schemas
class ScheduleType(str, Enum):
    """Types of schedules."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class ScheduleFrequency(str, Enum):
    """Schedule frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class ScheduleStatus(str, Enum):
    """Schedule status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TimeSlot(BaseModel):
    """Model for time slots."""
    start_time: datetime
    end_time: datetime
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday

class ScheduleConflict(BaseModel):
    """Model for schedule conflicts."""
    schedule_id: str
    conflict_type: str
    conflict_details: str
    conflicting_schedule_id: Optional[str] = None

class ScheduleOptimization(BaseModel):
    """Model for schedule optimization."""
    cluster_id: str
    optimized_schedules: List[Dict[str, Any]]
    total_efficiency_gain: float
    optimization_date: datetime

class Schedule(BaseModel):
    """Model for schedules."""
    id: str
    user_id: str
    device_name: str
    name: str
    schedule_type: ScheduleType
    frequency: ScheduleFrequency
    status: ScheduleStatus
    time_slots: List[TimeSlot]
    created_at: datetime
    updated_at: datetime
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None

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