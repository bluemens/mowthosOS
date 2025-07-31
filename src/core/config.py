import os
from typing import Optional, List
from datetime import timedelta
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, PostgresDsn, validator


class Settings(BaseSettings):
    """Application settings with validation"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    APP_NAME: str = "MowthosOS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development", regex="^(development|staging|production)$")
    IS_SERVERLESS: bool = Field(default=False)
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    
    # Database
    POSTGRES_USER: str = Field(default="mowthos")
    POSTGRES_PASSWORD: SecretStr = Field(default=SecretStr("mowthos_secure_password"))
    POSTGRES_SERVER: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="mowthos_db")
    DATABASE_URL: Optional[PostgresDsn] = None
    
    # Database Pool Settings
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)
    DATABASE_POOL_TIMEOUT: int = Field(default=30)
    DATABASE_POOL_RECYCLE: int = Field(default=3600)
    DATABASE_ECHO: bool = Field(default=False)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_USE_SSL: bool = Field(default=False)
    REDIS_DECODE_RESPONSES: bool = Field(default=True)
    
    # JWT Authentication
    JWT_SECRET_KEY: SecretStr = Field(
        default=SecretStr("your-super-secret-jwt-key-change-this-in-production")
    )
    JWT_REFRESH_SECRET_KEY: SecretStr = Field(
        default=SecretStr("your-super-secret-refresh-key-change-this-in-production")
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    
    # Security
    SECRET_KEY: SecretStr = Field(
        default=SecretStr("your-secret-key-for-other-crypto-operations")
    )
    BCRYPT_ROUNDS: int = Field(default=12)
    PASSWORD_MIN_LENGTH: int = Field(default=8)
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_PER_HOUR: int = Field(default=1000)
    
    # Mammotion Integration
    MAMMOTION_ACCOUNT: Optional[str] = None
    MAMMOTION_PASSWORD: Optional[SecretStr] = None
    
    # Mapbox Integration
    MAPBOX_ACCESS_TOKEN: Optional[SecretStr] = None
    
    # Stripe Integration (for future billing)
    STRIPE_SECRET_KEY: Optional[SecretStr] = None
    STRIPE_WEBHOOK_SECRET: Optional[SecretStr] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    
    # Email Settings (for notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None
    SMTP_USE_TLS: bool = Field(default=True)
    EMAIL_FROM_ADDRESS: Optional[str] = None
    EMAIL_FROM_NAME: str = Field(default="MowthosOS")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field(default="json")
    
    # Cluster Settings
    DEFAULT_CLUSTER_RADIUS_METERS: int = Field(default=80)
    MAX_CLUSTER_NEIGHBORS: int = Field(default=10)
    MIN_CLUSTER_NEIGHBORS: int = Field(default=1)
    
    # Maintenance Settings
    MAINTENANCE_CHECK_HOURS: int = Field(default=50)  # Check maintenance every 50 hours
    BLADE_REPLACEMENT_HOURS: int = Field(default=200)
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> str:
        if v:
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD", SecretStr("")).get_secret_value(),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"{values.get('POSTGRES_DB', '')}",
        )
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @property
    def access_token_expire_timedelta(self) -> timedelta:
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    @property
    def refresh_token_expire_timedelta(self) -> timedelta:
        return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
