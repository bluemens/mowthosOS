"""Mower device related database models"""
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, 
    Float, Integer, JSON, Text, UniqueConstraint, Index,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class DeviceStatus(str, Enum):
    """Device operational status"""
    ONLINE = "online"
    OFFLINE = "offline"
    MOWING = "mowing"
    DOCKED = "docked"
    CHARGING = "charging"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    PAUSED = "paused"
    RETURNING = "returning"


class DeviceModel(str, Enum):
    """Supported Mammotion device models"""
    LUBA_AWD_1000 = "luba_awd_1000"
    LUBA_AWD_3000 = "luba_awd_3000"
    LUBA_AWD_5000 = "luba_awd_5000"
    YUKA_1500 = "yuka_1500"
    YUKA_SWEEPER_1500 = "yuka_sweeper_1500"
    UNKNOWN = "unknown"


class MowerDevice(Base):
    """Mower device with PyMammotion integration"""
    __tablename__ = "mower_devices"
    
    # Identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(255), unique=True, nullable=False, index=True)  # Mammotion device ID
    device_name = Column(String(200), nullable=False)
    device_model = Column(SQLEnum(DeviceModel), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=True)
    
    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    
    # Device info from PyMammotion
    firmware_version = Column(String(50), nullable=True)
    hardware_version = Column(String(50), nullable=True)
    ble_mac_address = Column(String(20), nullable=True)
    wifi_mac_address = Column(String(20), nullable=True)
    
    # Current status (cached from PyMammotion)
    status = Column(SQLEnum(DeviceStatus), default=DeviceStatus.OFFLINE, nullable=False)
    battery_level = Column(Integer, nullable=True)  # 0-100
    charging_state = Column(Integer, nullable=True)
    work_mode = Column(String(50), nullable=True)
    
    # Location data
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True)
    location_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Work progress
    work_progress = Column(Integer, nullable=True)  # 0-100
    work_area_id = Column(Integer, nullable=True)
    current_zone = Column(String(100), nullable=True)
    mowing_speed = Column(Float, nullable=True)  # m/s
    
    # Device capabilities
    capabilities = Column(JSON, default=dict, nullable=False)
    supported_modes = Column(JSON, default=list, nullable=False)
    max_slope = Column(Integer, nullable=True)  # degrees
    cutting_width = Column(Integer, nullable=True)  # mm
    
    # Connection info
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_sync = Column(DateTime(timezone=True), nullable=True)
    is_online = Column(Boolean, default=False, nullable=False)
    connection_type = Column(String(20), nullable=True)  # ble, wifi, cloud
    
    # Maintenance tracking
    total_runtime_hours = Column(Float, default=0.0, nullable=False)
    total_distance_km = Column(Float, default=0.0, nullable=False)
    blade_runtime_hours = Column(Float, default=0.0, nullable=False)
    
    # Error tracking
    last_error_code = Column(String(50), nullable=True)
    last_error_message = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    
    # Configuration
    settings = Column(JSON, default=dict, nullable=False)
    schedule = Column(JSON, nullable=True)  # Mowing schedule
    boundaries = Column(JSON, nullable=True)  # Geofence boundaries
    no_go_zones = Column(JSON, nullable=True)  # Areas to avoid
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="devices")
    cluster = relationship("Cluster", back_populates="devices")
    maintenance_records = relationship("MaintenanceRecord", back_populates="device", cascade="all, delete-orphan")
    usage_records = relationship("DeviceUsageRecord", back_populates="device", cascade="all, delete-orphan")
    command_history = relationship("DeviceCommand", back_populates="device", cascade="all, delete-orphan")
    telemetry_data = relationship("DeviceTelemetry", back_populates="device", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_device_owner_status", "owner_id", "status"),
        Index("idx_device_cluster", "cluster_id"),
        Index("idx_device_last_seen", "last_seen"),
    )


class MaintenanceRecord(Base):
    """Device maintenance history and scheduling"""
    __tablename__ = "maintenance_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("mower_devices.id", ondelete="CASCADE"), nullable=False)
    
    # Maintenance type
    maintenance_type = Column(String(50), nullable=False)  # blade_change, cleaning, service, etc.
    description = Column(Text, nullable=True)
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Runtime at maintenance
    runtime_hours_at_maintenance = Column(Float, nullable=True)
    distance_km_at_maintenance = Column(Float, nullable=True)
    
    # Next maintenance
    next_due_hours = Column(Float, nullable=True)
    next_due_date = Column(DateTime(timezone=True), nullable=True)
    
    # Details
    performed_by = Column(String(200), nullable=True)
    cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    parts_replaced = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    device = relationship("MowerDevice", back_populates="maintenance_records")
    
    # Indexes
    __table_args__ = (
        Index("idx_maintenance_device_scheduled", "device_id", "scheduled_at"),
        Index("idx_maintenance_type", "maintenance_type"),
    )


class DeviceUsageRecord(Base):
    """Detailed device usage tracking"""
    __tablename__ = "device_usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("mower_devices.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    
    # Session info
    session_start = Column(DateTime(timezone=True), nullable=False)
    session_end = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    
    # Work performed
    area_covered_sqm = Column(Float, nullable=True)
    distance_traveled_m = Column(Float, nullable=True)
    energy_consumed_wh = Column(Float, nullable=True)
    
    # Location
    property_address = Column(String(500), nullable=True)
    work_zones = Column(JSON, nullable=True)  # List of zones worked
    
    # Performance metrics
    average_speed_mps = Column(Float, nullable=True)
    efficiency_score = Column(Float, nullable=True)  # 0-100
    completion_percentage = Column(Integer, nullable=True)
    
    # Issues
    pauses_count = Column(Integer, default=0, nullable=False)
    errors_count = Column(Integer, default=0, nullable=False)
    obstacles_detected = Column(Integer, default=0, nullable=False)
    
    # Billing related
    billable = Column(Boolean, default=True, nullable=False)
    billed = Column(Boolean, default=False, nullable=False)
    billing_reference = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    device = relationship("MowerDevice", back_populates="usage_records")
    
    # Indexes
    __table_args__ = (
        Index("idx_usage_device_session", "device_id", "session_start"),
        Index("idx_usage_user", "user_id"),
        Index("idx_usage_cluster", "cluster_id"),
        Index("idx_usage_billable", "billable", "billed"),
    )


class DeviceCommand(Base):
    """Command history for devices"""
    __tablename__ = "device_commands"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("mower_devices.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Command details
    command_type = Column(String(50), nullable=False)  # start, stop, pause, dock, etc.
    command_data = Column(JSON, nullable=True)
    
    # Execution
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(20), nullable=False)  # pending, sent, acknowledged, completed, failed
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Context
    source = Column(String(50), nullable=True)  # api, schedule, automation, etc.
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    device = relationship("MowerDevice", back_populates="command_history")
    
    # Indexes
    __table_args__ = (
        Index("idx_command_device_issued", "device_id", "issued_at"),
        Index("idx_command_status", "status"),
    )


class DeviceTelemetry(Base):
    """Real-time telemetry data from devices"""
    __tablename__ = "device_telemetry"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("mower_devices.id", ondelete="CASCADE"), nullable=False)
    
    # Telemetry data
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    telemetry_type = Column(String(50), nullable=False)  # location, sensor, status, etc.
    data = Column(JSON, nullable=False)
    
    # Quick access fields for common queries
    battery_level = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    
    # Data quality
    signal_strength = Column(Integer, nullable=True)
    satellites = Column(Integer, nullable=True)
    
    # Relationships
    device = relationship("MowerDevice", back_populates="telemetry_data")
    
    # Indexes
    __table_args__ = (
        Index("idx_telemetry_device_time", "device_id", "timestamp"),
        Index("idx_telemetry_type", "telemetry_type"),
        # Partial index for location data
        Index("idx_telemetry_location", "latitude", "longitude", postgresql_where=(latitude.isnot(None))),
    )