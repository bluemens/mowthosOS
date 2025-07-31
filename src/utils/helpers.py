"""
Helper utilities for MowthosOS.

This module contains common utility functions used throughout the application.
"""

import logging
import hashlib
import secrets
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_session_id(account: str) -> str:
    """
    Generate a unique session ID.
    
    Args:
        account: User account identifier
        
    Returns:
        Unique session ID
    """
    timestamp = str(datetime.now().timestamp())
    random_suffix = secrets.token_hex(8)
    return f"{account}_{timestamp}_{random_suffix}"

def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()

def validate_device_name(device_name: str) -> bool:
    """
    Validate device name format.
    
    Args:
        device_name: Device name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not device_name:
        return False
    
    # Check length
    if len(device_name) > 50:
        return False
    
    # Check for invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
    if any(char in device_name for char in invalid_chars):
        return False
    
    return True

def sanitize_input(input_string: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        input_string: Input string to sanitize
        
    Returns:
        Sanitized string
    """
    if not input_string:
        return ""
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`', '$']
    sanitized = input_string
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    return sanitized.strip()

def format_timestamp(timestamp: datetime) -> str:
    """
    Format timestamp for API responses.
    
    Args:
        timestamp: Datetime object
        
    Returns:
        Formatted timestamp string
    """
    return timestamp.isoformat()

def safe_get_nested(data: Dict[str, Any], *keys, default: Any = None) -> Any:
    """
    Safely get nested dictionary values.
    
    Args:
        data: Dictionary to search
        *keys: Keys to traverse
        default: Default value if key not found
        
    Returns:
        Value at the specified path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def log_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """
    Log API request details.
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    logger.info(
        f"API Request: {method} {endpoint} - {status_code} - {duration:.3f}s"
    )

def validate_email(email: str) -> bool:
    """
    Basic email validation.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid email format, False otherwise
    """
    if not email:
        return False
    
    # Basic email format check
    if '@' not in email or '.' not in email:
        return False
    
    # Check for basic structure
    parts = email.split('@')
    if len(parts) != 2:
        return False
    
    local_part, domain = parts
    if not local_part or not domain:
        return False
    
    return True 