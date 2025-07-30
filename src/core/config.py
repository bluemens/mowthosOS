"""
Configuration management for MowthosOS.

This module handles all application configuration including environment variables,
settings validation, and configuration defaults.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""
    
    # Application settings
    app_name: str = "MowthosOS"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS settings
    allowed_origins: List[str] = ["*"]
    allowed_methods: List[str] = ["*"]
    allowed_headers: List[str] = ["*"]
    
    # Security settings
    secret_key: str = "your-secret-key-here"
    access_token_expire_minutes: int = 30
    
    # Database settings (for future use)
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    
    # External API settings (for future use)
    mapbox_access_token: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    
    # Monitoring settings (for future use)
    sentry_dsn: Optional[str] = None
    
    # Session settings
    session_timeout_minutes: int = 30
    max_sessions_per_user: int = 5
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "MOWTHOS_"

# Create settings instance
settings = Settings() 