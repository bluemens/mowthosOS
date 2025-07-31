"""User and authentication related database models"""
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, 
    UniqueConstraint, Index, Text, JSON, Integer,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class UserRole(str, Enum):
    """User roles for authorization"""
    ADMIN = "admin"
    HOST = "host"  # Can host clusters
    NEIGHBOR = "neighbor"  # Can join clusters
    USER = "user"  # Basic user
    SERVICE = "service"  # Service account for integrations


class User(Base):
    """Core user model with authentication and profile data"""
    __tablename__ = "users"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Profile information
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    display_name = Column(String(200), nullable=True)
    phone_number = Column(String(20), nullable=True)
    phone_verified = Column(Boolean, default=False)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Location data
    primary_address_id = Column(UUID(as_uuid=True), ForeignKey("user_addresses.id"), nullable=True)
    timezone = Column(String(50), default="UTC", nullable=False)
    locale = Column(String(10), default="en-US", nullable=False)
    
    # Roles and permissions
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    permissions = Column(JSON, default=dict, nullable=False)  # Custom permissions
    
    # Account metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    
    # Security
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(255), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # Preferences
    preferences = Column(JSON, default=dict, nullable=False)
    notification_settings = Column(JSON, default=dict, nullable=False)
    
    # Deletion (soft delete)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deletion_reason = Column(Text, nullable=True)
    
    # Relationships
    addresses = relationship("UserAddress", back_populates="user", foreign_keys="UserAddress.user_id")
    primary_address = relationship("UserAddress", foreign_keys=[primary_address_id], post_update=True)
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("MowerDevice", back_populates="owner", cascade="all, delete-orphan")
    hosted_clusters = relationship("Cluster", back_populates="host_user")
    cluster_memberships = relationship("ClusterMember", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_email_active", "email", "is_active"),
        Index("idx_user_role", "role"),
        Index("idx_user_created_at", "created_at"),
    )


class UserAddress(Base):
    """User addresses with geocoding data"""
    __tablename__ = "user_addresses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Address components
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state_province = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False)  # ISO country code
    
    # Geocoding
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    geocoding_accuracy = Column(String(50), nullable=True)
    geocoded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    label = Column(String(50), nullable=True)  # "Home", "Work", etc.
    is_primary = Column(Boolean, default=False, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    
    # Property details for mowing
    property_size_sqm = Column(Integer, nullable=True)
    lawn_size_sqm = Column(Integer, nullable=True)
    terrain_type = Column(String(50), nullable=True)
    special_instructions = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="addresses", foreign_keys=[user_id])
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "is_primary", name="uq_one_primary_per_user"),
        Index("idx_address_user_id", "user_id"),
        Index("idx_address_coordinates", "latitude", "longitude"),
    )


class UserSession(Base):
    """Active user sessions for session management"""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Session data
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_info = Column(JSON, nullable=True)
    
    # Activity tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Session flags
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    # Indexes
    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )


class RefreshToken(Base):
    """JWT refresh tokens for token rotation"""
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Token data
    token = Column(String(500), unique=True, nullable=False, index=True)
    token_family = Column(UUID(as_uuid=True), nullable=False, index=True)  # For token rotation
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Security
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by_token_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Device tracking
    device_id = Column(String(255), nullable=True)
    device_name = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
    
    # Indexes
    __table_args__ = (
        Index("idx_refresh_token_user_active", "user_id", "is_active"),
        Index("idx_refresh_token_family", "token_family"),
    )


class APIKey(Base):
    """API keys for programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Key data
    key_prefix = Column(String(20), nullable=False)  # First few chars for identification
    key_hash = Column(String(255), unique=True, nullable=False)  # Hashed full key
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Permissions
    scopes = Column(JSON, default=list, nullable=False)  # List of allowed scopes
    rate_limit_override = Column(Integer, nullable=True)  # Custom rate limit
    
    # Validity
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(255), nullable=True)
    
    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    # Indexes
    __table_args__ = (
        Index("idx_api_key_prefix", "key_prefix"),
        Index("idx_api_key_user_active", "user_id", "is_active"),
    )


class AuditLog(Base):
    """Audit trail for security and compliance"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Event data
    event_type = Column(String(100), nullable=False)
    event_category = Column(String(50), nullable=False)  # auth, profile, security, etc.
    event_description = Column(Text, nullable=False)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Additional data
    metadata = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_user_time", "user_id", "created_at"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_created_at", "created_at"),
    )