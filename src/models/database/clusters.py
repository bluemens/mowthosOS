"""Cluster related database models"""
from typing import Optional
from datetime import datetime, time
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, 
    Float, Integer, JSON, Text, UniqueConstraint, Index,
    Time, Date, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class ClusterStatus(str, Enum):
    """Cluster operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FULL = "full"
    MAINTENANCE = "maintenance"


class MemberStatus(str, Enum):
    """Cluster member status"""
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class ScheduleType(str, Enum):
    """Types of schedules"""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class Cluster(Base):
    """Geographic cluster for coordinated mowing"""
    __tablename__ = "clusters"
    
    # Identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(20), unique=True, nullable=False)  # Short code for sharing
    
    # Host information
    host_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    host_address_id = Column(UUID(as_uuid=True), ForeignKey("user_addresses.id"), nullable=False)
    
    # Geographic data
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    service_radius_meters = Column(Integer, default=80, nullable=False)
    
    # Mapbox route data
    optimized_route = Column(JSON, nullable=True)  # GeoJSON route
    route_distance_km = Column(Float, nullable=True)
    route_duration_minutes = Column(Integer, nullable=True)
    route_last_optimized = Column(DateTime(timezone=True), nullable=True)
    
    # Configuration
    max_members = Column(Integer, default=5, nullable=False)
    min_members = Column(Integer, default=2, nullable=False)
    current_members = Column(Integer, default=0, nullable=False)
    
    # Status
    status = Column(SQLEnum(ClusterStatus), default=ClusterStatus.PENDING, nullable=False)
    is_accepting_members = Column(Boolean, default=True, nullable=False)
    
    # Schedule preferences
    schedule_type = Column(SQLEnum(ScheduleType), default=ScheduleType.WEEKLY, nullable=False)
    preferred_days = Column(JSON, nullable=True)  # List of weekday numbers
    preferred_start_time = Column(Time, nullable=True)
    preferred_end_time = Column(Time, nullable=True)
    weather_dependent = Column(Boolean, default=True, nullable=False)
    
    # Performance metrics
    total_area_sqm = Column(Float, nullable=True)
    average_mowing_time_minutes = Column(Integer, nullable=True)
    completion_rate = Column(Float, nullable=True)  # 0-100
    member_satisfaction_score = Column(Float, nullable=True)  # 1-5
    
    # Billing
    service_fee_per_member = Column(Float, nullable=True)
    host_discount_percentage = Column(Integer, default=20, nullable=False)
    
    # Rules and preferences
    rules = Column(JSON, default=dict, nullable=False)
    preferences = Column(JSON, default=dict, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    host_user = relationship("User", back_populates="hosted_clusters")
    members = relationship("ClusterMember", back_populates="cluster", cascade="all, delete-orphan")
    devices = relationship("MowerDevice", back_populates="cluster")
    schedules = relationship("ClusterSchedule", back_populates="cluster", cascade="all, delete-orphan")
    route_history = relationship("RouteOptimization", back_populates="cluster", cascade="all, delete-orphan")
    
    # Constraints and indexes
    __table_args__ = (
        CheckConstraint('max_members >= min_members', name='check_member_limits'),
        CheckConstraint('current_members <= max_members', name='check_current_members'),
        Index("idx_cluster_host", "host_user_id"),
        Index("idx_cluster_status", "status"),
        Index("idx_cluster_location", "center_latitude", "center_longitude"),
    )


class ClusterMember(Base):
    """Members of a cluster"""
    __tablename__ = "cluster_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address_id = Column(UUID(as_uuid=True), ForeignKey("user_addresses.id"), nullable=False)
    
    # Member info
    join_order = Column(Integer, nullable=False)  # Order in the route
    status = Column(SQLEnum(MemberStatus), default=MemberStatus.PENDING, nullable=False)
    
    # Property details
    property_size_sqm = Column(Float, nullable=True)
    lawn_size_sqm = Column(Float, nullable=True)
    estimated_mowing_time_minutes = Column(Integer, nullable=True)
    special_instructions = Column(Text, nullable=True)
    
    # Route optimization
    route_sequence = Column(Integer, nullable=True)  # Position in optimized route
    distance_from_previous_km = Column(Float, nullable=True)
    travel_time_from_previous_minutes = Column(Integer, nullable=True)
    
    # Preferences
    preferred_time_slot = Column(String(50), nullable=True)
    blackout_dates = Column(JSON, nullable=True)  # Dates when not available
    
    # Metrics
    services_received = Column(Integer, default=0, nullable=False)
    satisfaction_rating = Column(Float, nullable=True)  # 1-5
    on_time_percentage = Column(Float, nullable=True)
    
    # Timestamps
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    left_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    cluster = relationship("Cluster", back_populates="members")
    user = relationship("User", back_populates="cluster_memberships")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("cluster_id", "user_id", name="uq_cluster_user"),
        UniqueConstraint("cluster_id", "join_order", name="uq_cluster_order"),
        Index("idx_member_cluster_status", "cluster_id", "status"),
        Index("idx_member_user", "user_id"),
    )


class ClusterSchedule(Base):
    """Mowing schedules for clusters"""
    __tablename__ = "cluster_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False)
    
    # Schedule info
    schedule_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=True)
    
    # Execution
    status = Column(String(20), nullable=False)  # scheduled, in_progress, completed, cancelled
    device_id = Column(UUID(as_uuid=True), ForeignKey("mower_devices.id", ondelete="SET NULL"), nullable=True)
    
    # Progress tracking
    current_member_index = Column(Integer, nullable=True)
    members_completed = Column(JSON, nullable=True)  # List of member IDs completed
    
    # Weather
    weather_conditions = Column(JSON, nullable=True)
    weather_suitable = Column(Boolean, default=True, nullable=False)
    
    # Completion
    actual_start_time = Column(DateTime(timezone=True), nullable=True)
    actual_end_time = Column(DateTime(timezone=True), nullable=True)
    total_area_covered_sqm = Column(Float, nullable=True)
    total_distance_traveled_km = Column(Float, nullable=True)
    
    # Issues
    delays = Column(JSON, nullable=True)
    skipped_members = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    cluster = relationship("Cluster", back_populates="schedules")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint("cluster_id", "schedule_date", name="uq_cluster_date"),
        Index("idx_schedule_cluster_date", "cluster_id", "schedule_date"),
        Index("idx_schedule_status", "status"),
    )


class RouteOptimization(Base):
    """History of route optimizations"""
    __tablename__ = "route_optimizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False)
    
    # Optimization details
    optimization_type = Column(String(50), nullable=False)  # initial, reorder, new_member, etc.
    algorithm_version = Column(String(20), nullable=True)
    
    # Input
    member_addresses = Column(JSON, nullable=False)  # Addresses used for optimization
    constraints = Column(JSON, nullable=True)  # Time windows, priorities, etc.
    
    # Output
    optimized_sequence = Column(JSON, nullable=False)  # Ordered list of member IDs
    total_distance_km = Column(Float, nullable=False)
    total_duration_minutes = Column(Integer, nullable=False)
    
    # Route details
    route_geometry = Column(JSON, nullable=True)  # GeoJSON LineString
    turn_by_turn = Column(JSON, nullable=True)  # Navigation instructions
    
    # Comparison
    distance_saved_km = Column(Float, nullable=True)
    time_saved_minutes = Column(Integer, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    cluster = relationship("Cluster", back_populates="route_history")
    
    # Indexes
    __table_args__ = (
        Index("idx_route_cluster_created", "cluster_id", "created_at"),
    )