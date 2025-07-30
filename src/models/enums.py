"""
Enums and constants for MowthosOS.

This module contains all enumerations and constants used throughout the application.
"""

from enum import Enum
from typing import Dict, Any

class WorkMode(Enum):
    """Mower work mode enumeration."""
    IDLE = "idle"
    MOWING = "mowing"
    CHARGING = "charging"
    RETURNING = "returning"
    PAUSED = "paused"
    ERROR = "error"

class ChargingState(Enum):
    """Mower charging state enumeration."""
    NOT_CHARGING = 0
    CHARGING = 1
    FULLY_CHARGED = 2

class CommandType(Enum):
    """Mower command types."""
    START_MOW = "start_mow"
    STOP_MOW = "stop_mow"
    PAUSE_MOWING = "pause_mowing"
    RESUME_MOWING = "resume_mowing"
    RETURN_TO_DOCK = "return_to_dock"

class DeviceType(Enum):
    """Device type enumeration."""
    LUBA = "luba"
    UNKNOWN = "unknown"

# Mapping from PyMammotion work mode codes to our enums
WORK_MODE_MAPPING: Dict[int, WorkMode] = {
    0: WorkMode.IDLE,
    1: WorkMode.MOWING,
    2: WorkMode.CHARGING,
    3: WorkMode.RETURNING,
    4: WorkMode.PAUSED,
    5: WorkMode.ERROR,
}

# API response status codes
class APIStatus(Enum):
    """API response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"

# Session management constants
SESSION_TIMEOUT_MINUTES = 30
MAX_SESSIONS_PER_USER = 5

# Device constants
DEFAULT_DEVICE_TIMEOUT = 30  # seconds
MAX_DEVICE_NAME_LENGTH = 50

# API rate limiting
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds 