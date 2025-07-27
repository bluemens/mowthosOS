# MowthosOS Tech Stack Guidelines

**Comprehensive technical implementation guide for building the unified MowthosOS backend**

## Overview

This document provides detailed technical guidelines for implementing the proposed MowthosOS unified architecture. It covers technology choices, implementation patterns, best practices, and step-by-step implementation guidance.

## 📋 Table of Contents

1. [Technology Stack Overview](#technology-stack-overview)
2. [Backend Framework & API](#backend-framework--api)
3. [Database & Data Layer](#database--data-layer)
4. [Caching & Session Management](#caching--session-management)
5. [Task Processing & Background Jobs](#task-processing--background-jobs)
6. [External Service Integration](#external-service-integration)
7. [Security & Authentication](#security--authentication)
8. [Monitoring & Observability](#monitoring--observability)
9. [Development Tools & Workflow](#development-tools--workflow)
10. [Testing Framework](#testing-framework)
11. [Deployment & Infrastructure](#deployment--infrastructure)
12. [Implementation Roadmap](#implementation-roadmap)

---

## Technology Stack Overview

### Core Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    MowthosOS Tech Stack                     │
├─────────────────────────────────────────────────────────────┤
│ API Layer        │ FastAPI 0.104+ + Uvicorn + Pydantic 2.0 │
│ Authentication   │ JWT + PassLib + Python-JOSE             │
│ Database         │ PostgreSQL 15+ + SQLAlchemy 2.0 + Alembic│
│ Caching          │ Redis 7+ + aioredis                     │
│ Task Queue       │ Celery 5.3+ + Redis broker              │
│ Payment          │ Stripe API 7.0+                         │
│ Mapping          │ Mapbox API + OSMnx + GeoPandas          │
│ Monitoring       │ Prometheus + Grafana + Sentry           │
│ Testing          │ Pytest + Factory Boy + AsyncIO          │
│ Deployment       │ Docker + Docker Compose + Kubernetes    │
│ CI/CD            │ GitHub Actions + Pre-commit hooks       │
├─────────────────────────────────────────────────────────────┤
│ External Deps    │ PyMammotion (submodule) + Cluster Logic │
└─────────────────────────────────────────────────────────────┘
```

### Technology Decision Matrix

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| **Web Framework** | FastAPI | 0.104+ | High performance, automatic OpenAPI docs, type hints |
| **ASGI Server** | Uvicorn | 0.24+ | Production-ready async server with excellent performance |
| **Database** | PostgreSQL | 15+ | ACID compliance, JSON support, spatial extensions |
| **ORM** | SQLAlchemy | 2.0+ | Mature ORM with async support and advanced features |
| **Cache/Broker** | Redis | 7+ | High performance, multiple data structures, pub/sub |
| **Task Queue** | Celery | 5.3+ | Mature, scalable task processing with Redis broker |
| **HTTP Client** | aiohttp | 3.9+ | Async HTTP client for external API calls |
| **Validation** | Pydantic | 2.0+ | Fast serialization, validation, type safety |
| **Migration** | Alembic | 1.13+ | Database schema versioning and migrations |
| **Payment** | Stripe | 7.0+ | Comprehensive payment processing platform |

---

## Backend Framework & API

### FastAPI Configuration

**Core Setup:**
```python
# src/api/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from src.core.config import settings
from src.api.middleware import RequestLoggingMiddleware, RateLimitMiddleware
from src.api.routers import auth, mowers, clusters, billing, admin

def create_app() -> FastAPI:
    """Application factory pattern"""
    
    # Sentry integration for error tracking
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration(auto_enable=True)],
            traces_sample_rate=0.1,
            environment=settings.environment
        )
    
    app = FastAPI(
        title="MowthosOS API",
        description="Professional robotic mower management system",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None
    )
    
    # Security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
    # Include routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(mowers.router, prefix="/api/v1/mowers", tags=["Mowers"])
    app.include_router(clusters.router, prefix="/api/v1/clusters", tags=["Clusters"])
    app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
    
    # Global exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "type": "validation_error"}
        )
    
    return app

app = create_app()
```

**API Structure:**
```python
# src/api/routers/mowers.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from src.services.mower.service import MowerService
from src.services.auth.dependencies import get_current_user
from src.models.schemas import MowerStatus, MowerCommand, User
from src.core.monitoring import monitor_endpoint

router = APIRouter()

@router.get("/{device_id}/status", response_model=MowerStatus)
@monitor_endpoint
async def get_device_status(
    device_id: str,
    current_user: User = Depends(get_current_user),
    mower_service: MowerService = Depends(get_mower_service)
) -> MowerStatus:
    """Get real-time mower status with caching"""
    if not await mower_service.user_can_access_device(current_user.id, device_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await mower_service.get_device_status(device_id)

@router.post("/{device_id}/commands/{command}")
@monitor_endpoint
async def execute_command(
    device_id: str,
    command: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    mower_service: MowerService = Depends(get_mower_service)
):
    """Execute mower command asynchronously"""
    # Add billing tracking as background task
    background_tasks.add_task(
        track_command_usage, 
        user_id=current_user.id, 
        device_id=device_id, 
        command=command
    )
    
    return await mower_service.execute_command(device_id, command)
```

### Pydantic Models

**Request/Response Schemas:**
```python
# src/models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class MowerStatus(BaseModel):
    """Enhanced mower status with MowthosOS features"""
    device_id: str
    device_name: str
    online: bool
    battery_level: int = Field(..., ge=0, le=100)
    charging_state: int
    work_mode: str
    location: Optional[Dict[str, float]] = None
    work_progress: Optional[int] = Field(None, ge=0, le=100)
    work_area: Optional[int] = None
    last_updated: datetime
    
    # MowthosOS custom fields
    cluster_id: Optional[int] = None
    usage_minutes_today: int = Field(default=0, ge=0)
    next_maintenance: Optional[datetime] = None
    subscription_status: str = Field(default="active")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ClusterRegistration(BaseModel):
    """Cluster registration request"""
    address: str = Field(..., min_length=5, max_length=200)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=50)
    coordinates: Optional[Dict[str, float]] = None
    service_area_sqm: Optional[int] = Field(None, gt=0)
    max_neighbors: int = Field(default=5, ge=1, le=10)
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if v and ('latitude' not in v or 'longitude' not in v):
            raise ValueError('Coordinates must include latitude and longitude')
        return v

class PaymentSubscription(BaseModel):
    """Subscription management"""
    plan_id: str
    customer_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    usage_limits: Dict[str, int]
    overage_rates: Dict[str, float]
```

---

## Database & Data Layer

### PostgreSQL Configuration

**Database Setup:**
```python
# src/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from src.core.config import settings

# Async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool if settings.environment == "testing" else None,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncSession:
    """Database dependency"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Enhanced Data Models:**
```python
# src/models/database.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

class User(Base):
    """Enhanced user model with billing integration"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Address information
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Billing integration
    stripe_customer_id = Column(String, unique=True, nullable=True)
    subscription_status = Column(String, default="inactive")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    devices = relationship("MowerDevice", back_populates="owner")
    clusters = relationship("Cluster", back_populates="host_user")
    usage_records = relationship("UsageRecord", back_populates="user")

class MowerDevice(Base):
    """Mower device with enhanced tracking"""
    __tablename__ = "mower_devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_name = Column(String, unique=True, nullable=False, index=True)
    device_model = Column(String, nullable=False)
    firmware_version = Column(String, nullable=True)
    
    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id"), nullable=True)
    
    # Device status (cached from PyMammotion)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    battery_level = Column(Integer, nullable=True)
    is_online = Column(Boolean, default=False)
    current_location = Column(JSON, nullable=True)
    
    # Maintenance tracking
    total_runtime_hours = Column(Float, default=0.0)
    last_maintenance = Column(DateTime(timezone=True), nullable=True)
    next_maintenance_due = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="devices")
    cluster = relationship("Cluster", back_populates="devices")
    usage_records = relationship("UsageRecord", back_populates="device")

class Cluster(Base):
    """Enhanced cluster with route optimization"""
    __tablename__ = "clusters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    
    # Host information
    host_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    host_address = Column(String, nullable=False)
    host_coordinates = Column(JSON, nullable=False)  # {"lat": float, "lng": float}
    
    # Cluster configuration
    max_neighbors = Column(Integer, default=5)
    service_radius_meters = Column(Integer, default=80)
    is_active = Column(Boolean, default=True)
    
    # Route optimization
    optimized_route = Column(JSON, nullable=True)  # List of address order
    route_last_updated = Column(DateTime(timezone=True), nullable=True)
    estimated_coverage_time = Column(Integer, nullable=True)  # minutes
    
    # Performance metrics
    total_area_sqm = Column(Float, nullable=True)
    average_completion_time = Column(Integer, nullable=True)  # minutes
    neighbor_satisfaction_score = Column(Float, nullable=True)  # 1-5 rating
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    host_user = relationship("User", back_populates="clusters")
    devices = relationship("MowerDevice", back_populates="cluster")
    neighbors = relationship("ClusterMember", back_populates="cluster")

class UsageRecord(Base):
    """Detailed usage tracking for billing"""
    __tablename__ = "usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # References
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("mower_devices.id"), nullable=False)
    
    # Usage details
    command_type = Column(String, nullable=False)  # start_job, pause, etc.
    session_start = Column(DateTime(timezone=True), nullable=False)
    session_end = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    area_covered_sqm = Column(Float, nullable=True)
    
    # Billing
    billable_units = Column(Float, nullable=False, default=0.0)
    rate_per_unit = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False, default=0.0)
    billing_period = Column(String, nullable=False)  # YYYY-MM format
    
    # Metadata
    metadata = Column(JSON, nullable=True)  # Additional tracking data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="usage_records")
    device = relationship("MowerDevice", back_populates="usage_records")
```

**Database Migrations:**
```python
# migrations/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from src.models.database import Base
from src.core.config import settings

# Add your model imports here
from src.models.database import User, MowerDevice, Cluster, UsageRecord

target_metadata = Base.metadata

def run_migrations_online():
    """Run migrations in 'online' mode."""
    configuration = context.config
    configuration.set_main_option("sqlalchemy.url", settings.database_url)
    
    connectable = engine_from_config(
        configuration.get_section(configuration.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()
```

---

## Caching & Session Management

### Redis Configuration

**Redis Setup:**
```python
# src/core/cache.py
import aioredis
import json
import pickle
from typing import Any, Optional, Union
from datetime import timedelta
from src.core.config import settings

class CacheManager:
    """Async Redis cache manager"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection"""
        self.redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=False,
            max_connections=20,
            retry_on_timeout=True
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis:
            await self.connect()
        
        value = await self.redis.get(key)
        if value:
            try:
                return pickle.loads(value)
            except (pickle.PickleError, TypeError):
                return json.loads(value.decode())
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache"""
        if not self.redis:
            await self.connect()
        
        try:
            serialized = pickle.dumps(value)
        except (pickle.PickleError, TypeError):
            serialized = json.dumps(value).encode()
        
        return await self.redis.set(key, serialized, ex=expire)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis:
            await self.connect()
        return bool(await self.redis.delete(key))
    
    async def get_pattern(self, pattern: str) -> List[bytes]:
        """Get keys matching pattern"""
        if not self.redis:
            await self.connect()
        return await self.redis.keys(pattern)

# Global cache manager
cache_manager = CacheManager()

# Decorator for caching function results
def cache_result(expire_seconds: int = 300, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached = await cache_manager.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, expire_seconds)
            return result
        return wrapper
    return decorator
```

**Session Management:**
```python
# src/services/auth/session.py
from typing import Optional, Dict
from datetime import datetime, timedelta
import jwt
from src.core.cache import cache_manager
from src.core.config import settings

class SessionManager:
    """JWT-based session management with Redis storage"""
    
    def __init__(self):
        self.algorithm = "HS256"
        self.secret_key = settings.secret_key
        self.access_token_expire = timedelta(minutes=settings.access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=30)
    
    async def create_session(self, user_id: str, user_data: Dict) -> Dict[str, str]:
        """Create new session with access and refresh tokens"""
        now = datetime.utcnow()
        
        # Access token payload
        access_payload = {
            "user_id": user_id,
            "type": "access",
            "iat": now,
            "exp": now + self.access_token_expire
        }
        
        # Refresh token payload
        refresh_payload = {
            "user_id": user_id,
            "type": "refresh", 
            "iat": now,
            "exp": now + self.refresh_token_expire
        }
        
        # Generate tokens
        access_token = jwt.encode(access_payload, self.secret_key, self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, self.algorithm)
        
        # Store session data in Redis
        session_key = f"session:{user_id}:{now.timestamp()}"
        session_data = {
            "user_id": user_id,
            "user_data": user_data,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": now.isoformat(),
            "last_activity": now.isoformat()
        }
        
        await cache_manager.set(
            session_key, 
            session_data, 
            expire=int(self.refresh_token_expire.total_seconds())
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(self.access_token_expire.total_seconds())
        }
    
    async def validate_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if session exists in Redis
            user_id = payload["user_id"]
            session_pattern = f"session:{user_id}:*"
            session_keys = await cache_manager.get_pattern(session_pattern)
            
            for key in session_keys:
                session_data = await cache_manager.get(key.decode())
                if session_data and session_data.get("access_token") == token:
                    # Update last activity
                    session_data["last_activity"] = datetime.utcnow().isoformat()
                    await cache_manager.set(key.decode(), session_data)
                    return payload
            
            return None
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

---

## Task Processing & Background Jobs

### Celery Configuration

**Celery Setup:**
```python
# src/core/celery.py
from celery import Celery
from src.core.config import settings

# Initialize Celery
celery_app = Celery(
    "mowthosos",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.tasks.mower_tasks",
        "src.tasks.billing_tasks", 
        "src.tasks.cluster_tasks",
        "src.tasks.notification_tasks"
    ]
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "sync-mower-status": {
        "task": "src.tasks.mower_tasks.sync_all_mower_status",
        "schedule": 60.0,  # Every minute
    },
    "process-billing": {
        "task": "src.tasks.billing_tasks.process_daily_billing",
        "schedule": 24 * 60 * 60,  # Daily
    },
    "optimize-clusters": {
        "task": "src.tasks.cluster_tasks.optimize_all_clusters",
        "schedule": 6 * 60 * 60,  # Every 6 hours
    },
    "cleanup-sessions": {
        "task": "src.tasks.auth_tasks.cleanup_expired_sessions",
        "schedule": 60 * 60,  # Hourly
    }
}
```

**Background Tasks:**
```python
# src/tasks/mower_tasks.py
from celery import shared_task
from typing import List, Dict
import asyncio
from src.services.mower.service import MowerService
from src.services.notification.service import NotificationService
from src.core.database import AsyncSessionLocal

@shared_task(bind=True, max_retries=3)
def sync_mower_status(self, device_id: str) -> Dict:
    """Sync individual mower status"""
    try:
        return asyncio.run(_sync_mower_status_async(device_id))
    except Exception as exc:
        self.retry(countdown=60, exc=exc)

async def _sync_mower_status_async(device_id: str) -> Dict:
    """Async implementation of mower status sync"""
    async with AsyncSessionLocal() as db:
        mower_service = MowerService(db)
        
        # Get status from PyMammotion
        status = await mower_service.get_live_status(device_id)
        
        # Update database
        await mower_service.update_cached_status(device_id, status)
        
        # Check for alerts
        if status.battery_level < 20:
            notification_service = NotificationService()
            await notification_service.send_low_battery_alert(device_id)
        
        return {"device_id": device_id, "status": "synced", "battery": status.battery_level}

@shared_task
def sync_all_mower_status() -> List[str]:
    """Sync status for all active mowers"""
    return asyncio.run(_sync_all_mower_status_async())

async def _sync_all_mower_status_async() -> List[str]:
    """Get all active devices and queue individual sync tasks"""
    async with AsyncSessionLocal() as db:
        mower_service = MowerService(db)
        active_devices = await mower_service.get_active_device_ids()
        
        # Queue individual sync tasks
        for device_id in active_devices:
            sync_mower_status.delay(device_id)
        
        return active_devices

# src/tasks/billing_tasks.py
@shared_task(bind=True, max_retries=3)
def process_user_billing(self, user_id: str, billing_period: str) -> Dict:
    """Process billing for a specific user"""
    try:
        return asyncio.run(_process_user_billing_async(user_id, billing_period))
    except Exception as exc:
        self.retry(countdown=300, exc=exc)  # Retry after 5 minutes

async def _process_user_billing_async(user_id: str, billing_period: str) -> Dict:
    """Calculate and process billing for user"""
    async with AsyncSessionLocal() as db:
        from src.services.billing.service import BillingService
        
        billing_service = BillingService(db)
        
        # Calculate usage charges
        usage_charges = await billing_service.calculate_usage_charges(user_id, billing_period)
        
        # Process payment via Stripe
        payment_result = await billing_service.process_payment(user_id, usage_charges)
        
        # Update usage records
        await billing_service.mark_usage_billed(user_id, billing_period)
        
        return {
            "user_id": user_id,
            "period": billing_period,
            "amount": usage_charges["total"],
            "payment_status": payment_result["status"]
        }

# src/tasks/cluster_tasks.py
@shared_task
def optimize_cluster_routes(cluster_id: str) -> Dict:
    """Optimize mowing routes for a cluster"""
    return asyncio.run(_optimize_cluster_routes_async(cluster_id))

async def _optimize_cluster_routes_async(cluster_id: str) -> Dict:
    """Async cluster route optimization"""
    async with AsyncSessionLocal() as db:
        from src.services.cluster.service import ClusterService
        
        cluster_service = ClusterService(db)
        
        # Get cluster data
        cluster = await cluster_service.get_cluster(cluster_id)
        
        # Run optimization algorithm
        optimized_route = await cluster_service.optimize_route(cluster)
        
        # Update cluster with new route
        await cluster_service.update_cluster_route(cluster_id, optimized_route)
        
        return {
            "cluster_id": cluster_id,
            "route_length": len(optimized_route["addresses"]),
            "estimated_time": optimized_route["estimated_minutes"],
            "efficiency_improvement": optimized_route["efficiency_gain"]
        }
```

---

## External Service Integration

### PyMammotion Integration Service

**Safe Integration Wrapper:**
```python
# src/services/mower/mammotion_wrapper.py
from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime

# ⚠️ IMPORTANT: PyMammotion is external submodule - DO NOT MODIFY
from pymammotion.mammotion.devices.mammotion import Mammotion
from pymammotion.data.model.enums import ConnectionPreference

from src.core.cache import cache_manager, cache_result
from src.models.schemas import MowerStatus, MowerCommand
from src.core.config import settings

logger = logging.getLogger(__name__)

class MammotionIntegrationService:
    """
    Safe wrapper around PyMammotion external library.
    DO NOT MODIFY PyMammotion - use composition patterns only.
    """
    
    def __init__(self):
        self._mammotion: Optional[Mammotion] = None
        self._authenticated_users: Dict[str, str] = {}  # account -> session_id
        self._device_cache_ttl = 30  # seconds
        
    async def get_mammotion_instance(self) -> Mammotion:
        """Get or create PyMammotion instance"""
        if not self._mammotion:
            self._mammotion = Mammotion()
        return self._mammotion
    
    async def authenticate_user(self, account: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with Mammotion cloud.
        Wrapper around PyMammotion login functionality.
        """
        try:
            mammotion = await self.get_mammotion_instance()
            
            # Use PyMammotion unchanged
            await mammotion.login_and_initiate_cloud(account, password)
            
            # Get available devices
            devices = mammotion.device_manager.devices
            device_list = [
                {
                    "name": name,
                    "iot_id": device.iot_id,
                    "preference": str(device.preference),
                    "has_cloud": device.has_cloud(),
                    "has_ble": device.has_ble()
                }
                for name, device in devices.items()
            ]
            
            # Store session in our format
            session_id = f"mowthosos_{account}_{datetime.now().timestamp()}"
            self._authenticated_users[account] = session_id
            
            # Cache authentication for 1 hour
            await cache_manager.set(
                f"mammotion_auth:{account}", 
                {"session_id": session_id, "devices": device_list},
                expire=3600
            )
            
            return {
                "success": True,
                "session_id": session_id,
                "devices": device_list,
                "account": account
            }
            
        except Exception as e:
            logger.error(f"PyMammotion authentication failed for {account}: {e}")
            raise ValueError(f"Authentication failed: {str(e)}")
    
    @cache_result(expire_seconds=30, key_prefix="mower_status")
    async def get_device_status(self, device_name: str) -> MowerStatus:
        """
        Get device status with caching.
        Transforms PyMammotion data to our format.
        """
        try:
            mammotion = await self.get_mammotion_instance()
            
            # Get device using PyMammotion unchanged
            device = mammotion.get_device_by_name(device_name)
            if not device:
                raise ValueError(f"Device '{device_name}' not found")
            
            # Extract data from PyMammotion state
            state = device.mower_state
            raw_data = {
                "online": state.online,
                "battery_level": state.report_data.dev.battery_val,
                "charging_state": state.report_data.dev.charge_state,
                "work_mode": state.report_data.dev.sys_status,
                "work_progress": state.report_data.work.progress,
                "work_area": state.report_data.work.area
            }
            
            # Get location if available
            location = None
            if state.location.device:
                location = {
                    "latitude": state.location.device.latitude,
                    "longitude": state.location.device.longitude,
                    "orientation": state.location.orientation
                }
            
            # Transform to our enhanced format
            return MowerStatus(
                device_id=device_name,
                device_name=device_name,
                online=raw_data["online"],
                battery_level=raw_data["battery_level"],
                charging_state=raw_data["charging_state"],
                work_mode=self._translate_work_mode(raw_data["work_mode"]),
                location=location,
                work_progress=raw_data["work_progress"],
                work_area=raw_data["work_area"],
                last_updated=datetime.now(),
                # Our custom fields (not from PyMammotion)
                cluster_id=await self._get_device_cluster(device_name),
                usage_minutes_today=await self._get_usage_today(device_name),
                next_maintenance=await self._get_next_maintenance(device_name),
                subscription_status="active"  # From our billing system
            )
            
        except Exception as e:
            logger.error(f"Failed to get status for device {device_name}: {e}")
            raise
    
    async def execute_command(self, device_name: str, command: str) -> Dict[str, Any]:
        """
        Execute mower command with error handling and logging.
        Uses PyMammotion unchanged, adds our enhancements.
        """
        try:
            mammotion = await self.get_mammotion_instance()
            
            # Validate command
            valid_commands = [
                "start_job", "cancel_job", "pause_execute_task", 
                "resume_execute_task", "return_to_dock"
            ]
            if command not in valid_commands:
                raise ValueError(f"Invalid command: {command}")
            
            # Log command attempt
            logger.info(f"Executing command '{command}' on device '{device_name}'")
            
            # Execute using PyMammotion unchanged
            await mammotion.send_command(device_name, command)
            
            # Log successful execution
            await self._log_command_execution(device_name, command, success=True)
            
            # Clear status cache to force refresh
            cache_key = f"mower_status:get_device_status:{hash(device_name)}"
            await cache_manager.delete(cache_key)
            
            return {
                "success": True,
                "command": command,
                "device_name": device_name,
                "timestamp": datetime.now().isoformat(),
                "message": f"Command '{command}' executed successfully"
            }
            
        except Exception as e:
            logger.error(f"Command '{command}' failed for device '{device_name}': {e}")
            await self._log_command_execution(device_name, command, success=False, error=str(e))
            raise ValueError(f"Command execution failed: {str(e)}")
    
    def _translate_work_mode(self, mode_code: int) -> str:
        """Translate PyMammotion work mode codes to readable strings"""
        mode_map = {
            0: "MODE_NOT_ACTIVE",
            1: "MODE_ONLINE", 
            2: "MODE_OFFLINE",
            8: "MODE_DISABLE",
            10: "MODE_INITIALIZATION",
            11: "MODE_READY",
            13: "MODE_WORKING",
            14: "MODE_RETURNING",
            15: "MODE_CHARGING",
            16: "MODE_UPDATING",
            17: "MODE_LOCK",
            19: "MODE_PAUSE",
            20: "MODE_MANUAL_MOWING"
        }
        return mode_map.get(mode_code, f"UNKNOWN_MODE_{mode_code}")
    
    async def _get_device_cluster(self, device_name: str) -> Optional[int]:
        """Get cluster ID for device (our custom logic)"""
        cluster_info = await cache_manager.get(f"device_cluster:{device_name}")
        return cluster_info.get("cluster_id") if cluster_info else None
    
    async def _get_usage_today(self, device_name: str) -> int:
        """Get today's usage minutes (our custom tracking)"""
        usage_key = f"usage_today:{device_name}:{datetime.now().strftime('%Y-%m-%d')}"
        usage = await cache_manager.get(usage_key)
        return usage or 0
    
    async def _get_next_maintenance(self, device_name: str) -> Optional[datetime]:
        """Get next maintenance date (our custom scheduling)"""
        maintenance_info = await cache_manager.get(f"maintenance:{device_name}")
        if maintenance_info and "next_date" in maintenance_info:
            return datetime.fromisoformat(maintenance_info["next_date"])
        return None
    
    async def _log_command_execution(self, device_name: str, command: str, success: bool, error: str = None):
        """Log command execution for auditing and billing"""
        log_entry = {
            "device_name": device_name,
            "command": command,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
        
        # Store in Redis for billing and auditing
        log_key = f"command_log:{device_name}:{datetime.now().timestamp()}"
        await cache_manager.set(log_key, log_entry, expire=30*24*60*60)  # 30 days
```

### Stripe Payment Integration

**Payment Service:**
```python
# src/services/payment/stripe_service.py
import stripe
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
import logging

from src.core.config import settings
from src.models.schemas import PaymentSubscription
from src.core.cache import cache_manager

stripe.api_key = settings.stripe_secret_key
logger = logging.getLogger(__name__)

class StripePaymentService:
    """Stripe integration for subscription and usage billing"""
    
    def __init__(self):
        self.webhook_secret = settings.stripe_webhook_secret
        
    async def create_customer(self, user_id: str, email: str, name: str) -> str:
        """Create Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"mowthosos_user_id": user_id}
            )
            
            # Cache customer data
            await cache_manager.set(
                f"stripe_customer:{user_id}",
                {"customer_id": customer.id, "email": email},
                expire=24*60*60  # 24 hours
            )
            
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            raise ValueError(f"Payment system error: {str(e)}")
    
    async def create_subscription(
        self, 
        customer_id: str, 
        price_id: str,
        usage_limits: Dict[str, int] = None
    ) -> PaymentSubscription:
        """Create subscription with usage-based billing"""
        try:
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent"],
                metadata={
                    "usage_limits": str(usage_limits or {}),
                    "service": "mowthosos_mowing"
                }
            )
            
            # Transform to our format
            return PaymentSubscription(
                plan_id=price_id,
                customer_id=customer_id,
                status=subscription.status,
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                usage_limits=usage_limits or {"mowing_minutes": 500},
                overage_rates={"mowing_minutes": 0.10}  # $0.10 per minute over limit
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {e}")
            raise ValueError(f"Subscription error: {str(e)}")
    
    async def record_usage(
        self, 
        subscription_id: str, 
        usage_type: str, 
        quantity: int,
        timestamp: datetime = None
    ) -> Dict[str, Any]:
        """Record usage for billing"""
        try:
            # Get subscription items
            subscription = stripe.Subscription.retrieve(subscription_id)
            usage_item = None
            
            for item in subscription["items"]["data"]:
                if usage_type in item.price.metadata.get("usage_type", ""):
                    usage_item = item
                    break
            
            if not usage_item:
                raise ValueError(f"No usage item found for type: {usage_type}")
            
            # Record usage
            usage_record = stripe.UsageRecord.create(
                subscription_item=usage_item.id,
                quantity=quantity,
                timestamp=int(timestamp.timestamp()) if timestamp else None
            )
            
            return {
                "success": True,
                "usage_record_id": usage_record.id,
                "quantity": quantity,
                "usage_type": usage_type
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Usage recording failed: {e}")
            raise ValueError(f"Usage billing error: {str(e)}")
    
    async def process_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_type = event["type"]
            event_data = event["data"]["object"]
            
            # Handle different event types
            if event_type == "invoice.payment_succeeded":
                return await self._handle_payment_success(event_data)
            elif event_type == "invoice.payment_failed":
                return await self._handle_payment_failure(event_data)
            elif event_type == "customer.subscription.updated":
                return await self._handle_subscription_update(event_data)
            else:
                logger.info(f"Unhandled webhook event: {event_type}")
                return {"handled": False, "event_type": event_type}
                
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid webhook signature")
            raise ValueError("Invalid webhook signature")
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            raise
    
    async def _handle_payment_success(self, invoice_data: Dict) -> Dict[str, Any]:
        """Handle successful payment"""
        customer_id = invoice_data["customer"]
        amount_paid = invoice_data["amount_paid"] / 100  # Convert from cents
        
        # Update user subscription status
        # This would trigger database updates via our service layer
        logger.info(f"Payment succeeded for customer {customer_id}: ${amount_paid}")
        
        return {
            "handled": True,
            "action": "payment_success",
            "customer_id": customer_id,
            "amount": amount_paid
        }
```

### Mapbox & Geographic Services

**Enhanced Geographic Service:**
```python
# src/services/geo/enhanced_mapbox_service.py
import aiohttp
import asyncio
from typing import Tuple, Optional, List, Dict, Any
import logging

# External dependency integration - DO NOT MODIFY original files
from Mowthos_Cluster_Logic.app.services.mapbox_service import MapboxService as OriginalMapboxService

from src.core.config import settings
from src.core.cache import cache_manager, cache_result

logger = logging.getLogger(__name__)

class EnhancedGeographicService:
    """
    Enhanced wrapper around Mowthos-Cluster-Logic MapboxService.
    DO NOT MODIFY the original - use composition patterns.
    """
    
    def __init__(self):
        # Use original service unchanged
        self._original_service = OriginalMapboxService(settings.mapbox_access_token)
        self._batch_geocoding_limit = 25
        
    @cache_result(expire_seconds=24*60*60, key_prefix="geocode")  # Cache for 24 hours
    async def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode address with caching.
        Wrapper around original Mapbox service.
        """
        try:
            # Use original service unchanged
            result = self._original_service.geocode_address(address)
            
            if result:
                logger.info(f"Geocoded address: {address} -> {result}")
                return result
            else:
                logger.warning(f"Failed to geocode address: {address}")
                return None
                
        except Exception as e:
            logger.error(f"Geocoding error for {address}: {e}")
            return None
    
    async def batch_geocode(self, addresses: List[str]) -> Dict[str, Optional[Tuple[float, float]]]:
        """
        Batch geocode multiple addresses with rate limiting.
        Enhancement over original service.
        """
        results = {}
        
        # Process in batches to respect API limits
        for i in range(0, len(addresses), self._batch_geocoding_limit):
            batch = addresses[i:i + self._batch_geocoding_limit]
            
            # Create async tasks for this batch
            tasks = [self.geocode_address(addr) for addr in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for addr, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Geocoding failed for {addr}: {result}")
                    results[addr] = None
                else:
                    results[addr] = result
            
            # Rate limiting pause
            if i + self._batch_geocoding_limit < len(addresses):
                await asyncio.sleep(0.1)  # 100ms between batches
        
        return results
    
    async def check_road_accessibility(
        self, 
        host_coords: Tuple[float, float], 
        candidate_coords: Tuple[float, float]
    ) -> Dict[str, Any]:
        """
        Enhanced road accessibility check with detailed results.
        Wrapper around original service with additional metadata.
        """
        try:
            # Use original service unchanged
            is_accessible = self._original_service.is_accessible_without_crossing_road(
                host_coords, candidate_coords
            )
            
            # Calculate distance for additional context
            distance = self._calculate_distance(host_coords, candidate_coords)
            
            return {
                "is_accessible": is_accessible,
                "distance_meters": distance,
                "host_coordinates": {"lat": host_coords[0], "lng": host_coords[1]},
                "candidate_coordinates": {"lat": candidate_coords[0], "lng": candidate_coords[1]},
                "checked_at": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error(f"Road accessibility check failed: {e}")
            return {
                "is_accessible": False,
                "error": str(e),
                "distance_meters": None
            }
    
    async def analyze_cluster_geography(self, cluster_data: Dict) -> Dict[str, Any]:
        """
        Comprehensive geographic analysis for cluster optimization.
        Our custom enhancement using original services.
        """
        host_coords = (cluster_data["host_lat"], cluster_data["host_lng"])
        neighbors = cluster_data.get("neighbors", [])
        
        analysis = {
            "host_location": {"lat": host_coords[0], "lng": host_coords[1]},
            "neighbor_count": len(neighbors),
            "accessibility_matrix": {},
            "route_optimization": {},
            "coverage_statistics": {}
        }
        
        # Check accessibility for all neighbors
        accessibility_tasks = []
        for neighbor in neighbors:
            neighbor_coords = (neighbor["latitude"], neighbor["longitude"])
            task = self.check_road_accessibility(host_coords, neighbor_coords)
            accessibility_tasks.append((neighbor["address"], task))
        
        # Execute accessibility checks
        for address, task in accessibility_tasks:
            result = await task
            analysis["accessibility_matrix"][address] = result
        
        # Calculate route optimization
        accessible_neighbors = [
            addr for addr, data in analysis["accessibility_matrix"].items()
            if data.get("is_accessible", False)
        ]
        
        analysis["route_optimization"] = await self._optimize_route(
            host_coords, accessible_neighbors
        )
        
        # Coverage statistics
        analysis["coverage_statistics"] = self._calculate_coverage_stats(
            analysis["accessibility_matrix"]
        )
        
        return analysis
    
    def _calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Calculate distance between coordinates using Haversine formula"""
        from math import radians, cos, sin, asin, sqrt
        
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Earth radius in meters
        
        return c * r
    
    async def _optimize_route(self, host_coords: Tuple[float, float], addresses: List[str]) -> Dict:
        """Simple route optimization algorithm"""
        if not addresses:
            return {"optimized_order": [], "total_distance": 0, "estimated_time": 0}
        
        # For now, simple nearest neighbor algorithm
        # In production, would use more sophisticated algorithms
        geocoded = await self.batch_geocode(addresses)
        
        route_order = []
        current_pos = host_coords
        remaining = list(addresses)
        total_distance = 0
        
        while remaining:
            nearest = min(
                remaining,
                key=lambda addr: self._calculate_distance(
                    current_pos, geocoded.get(addr, (0, 0))
                ) if geocoded.get(addr) else float('inf')
            )
            
            nearest_coords = geocoded.get(nearest)
            if nearest_coords:
                distance = self._calculate_distance(current_pos, nearest_coords)
                total_distance += distance
                current_pos = nearest_coords
                route_order.append(nearest)
            
            remaining.remove(nearest)
        
        # Return to host
        if route_order:
            total_distance += self._calculate_distance(current_pos, host_coords)
        
        return {
            "optimized_order": route_order,
            "total_distance": total_distance,
            "estimated_time": int(total_distance / 1.5)  # Rough estimate: 1.5 m/s walking speed
        }
    
    def _calculate_coverage_stats(self, accessibility_matrix: Dict) -> Dict:
        """Calculate coverage statistics"""
        total_neighbors = len(accessibility_matrix)
        accessible_count = sum(
            1 for data in accessibility_matrix.values()
            if data.get("is_accessible", False)
        )
        
        if total_neighbors == 0:
            return {"coverage_ratio": 0, "efficiency_score": 0}
        
        coverage_ratio = accessible_count / total_neighbors
        
        # Calculate average distance to accessible neighbors
        accessible_distances = [
            data.get("distance_meters", 0)
            for data in accessibility_matrix.values()
            if data.get("is_accessible", False) and data.get("distance_meters")
        ]
        
        avg_distance = sum(accessible_distances) / len(accessible_distances) if accessible_distances else 0
        
        # Efficiency score based on coverage and proximity
        efficiency_score = coverage_ratio * (1 - min(avg_distance / 100, 0.5))  # Penalize long distances
        
        return {
            "coverage_ratio": coverage_ratio,
            "accessible_neighbors": accessible_count,
            "total_neighbors": total_neighbors,
            "average_distance": avg_distance,
            "efficiency_score": efficiency_score
        }
```

---

## Security & Authentication

### JWT Authentication System

**Security Configuration:**
```python
# src/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import secrets
from typing import Optional

from src.core.config import settings
from src.core.cache import cache_manager

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecurityManager:
    """Comprehensive security management"""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token with expiration"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload if payload.get("type") == "access" else None
        except JWTError:
            return None
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def generate_api_key(self) -> str:
        """Generate secure API key for service-to-service communication"""
        return secrets.token_urlsafe(32)

security_manager = SecurityManager()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = security_manager.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
        # Get user from cache or database
        user_data = await cache_manager.get(f"user:{user_id}")
        if user_data is None:
            # Fetch from database if not in cache
            from src.services.user.service import UserService
            user_service = UserService()
            user_data = await user_service.get_user_by_id(user_id)
            
            if user_data:
                await cache_manager.set(f"user:{user_id}", user_data, expire=300)
        
        if user_data is None:
            raise credentials_exception
            
        return user_data
        
    except JWTError:
        raise credentials_exception
```

**Rate Limiting Middleware:**
```python
# src/api/middleware/rate_limit.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Dict
from src.core.cache import cache_manager

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis"""
    
    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.window_size = 60  # 1 minute window
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Get client identifier
        client_ip = request.client.host
        user_id = None
        
        # Try to get user from authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = security_manager.verify_token(token)
            if payload:
                user_id = payload.get("sub")
        
        # Use user ID if available, otherwise IP
        identifier = user_id or client_ip
        
        # Check rate limit
        current_time = int(time.time())
        window_start = current_time - (current_time % self.window_size)
        
        rate_limit_key = f"rate_limit:{identifier}:{window_start}"
        
        # Get current count
        current_count = await cache_manager.get(rate_limit_key) or 0
        
        if current_count >= self.calls_per_minute:
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                headers={"Content-Type": "application/json"}
            )
        
        # Increment counter
        await cache_manager.set(rate_limit_key, current_count + 1, expire=self.window_size)
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.calls_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(self.calls_per_minute - current_count - 1)
        
        return response
```

---

## Monitoring & Observability

### Prometheus Metrics

**Metrics Configuration:**
```python
# src/core/monitoring.py
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from functools import wraps
import time
from typing import Dict, Any
from fastapi import Request, Response

# Application metrics
REQUEST_COUNT = Counter(
    'mowthosos_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'mowthosos_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_MOWERS = Gauge(
    'mowthosos_active_mowers',
    'Number of currently active mowers'
)

CLUSTER_SIZE = Gauge(
    'mowthosos_cluster_size',
    'Current cluster sizes',
    ['cluster_id']
)

COMMAND_EXECUTIONS = Counter(
    'mowthosos_commands_total',
    'Total mower commands executed',
    ['command_type', 'device_id', 'status']
)

BILLING_REVENUE = Gauge(
    'mowthosos_revenue_total',
    'Total revenue in USD'
)

CACHE_HITS = Counter(
    'mowthosos_cache_hits_total',
    'Cache hit/miss statistics',
    ['cache_type', 'status']
)

# Application info
APP_INFO = Info('mowthosos_app', 'Application information')

def setup_metrics():
    """Initialize application metrics"""
    APP_INFO.info({
        'version': '1.0.0',
        'environment': settings.environment,
        'python_version': platform.python_version()
    })

def monitor_endpoint(func):
    """Decorator to monitor API endpoint performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        # Extract request info
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        endpoint = func.__name__
        method = request.method if request else "UNKNOWN"
        
        try:
            result = await func(*args, **kwargs)
            
            # Record successful request
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=200
            ).inc()
            
            return result
            
        except Exception as e:
            # Record failed request
            status_code = getattr(e, 'status_code', 500)
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            raise
            
        finally:
            # Record request duration
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(time.time() - start_time)
    
    return wrapper

class MetricsCollector:
    """Collect and update business metrics"""
    
    def __init__(self):
        self._cache = {}
    
    async def update_mower_metrics(self):
        """Update mower-related metrics"""
        from src.services.mower.service import MowerService
        
        mower_service = MowerService()
        
        # Count active mowers
        active_count = await mower_service.get_active_mower_count()
        ACTIVE_MOWERS.set(active_count)
        
        # Update cluster sizes
        cluster_stats = await mower_service.get_cluster_statistics()
        for cluster_id, size in cluster_stats.items():
            CLUSTER_SIZE.labels(cluster_id=cluster_id).set(size)
    
    async def update_billing_metrics(self):
        """Update billing and revenue metrics"""
        from src.services.billing.service import BillingService
        
        billing_service = BillingService()
        total_revenue = await billing_service.get_total_revenue()
        BILLING_REVENUE.set(total_revenue)
    
    def record_command_execution(self, command_type: str, device_id: str, success: bool):
        """Record mower command execution"""
        status = "success" if success else "failure"
        COMMAND_EXECUTIONS.labels(
            command_type=command_type,
            device_id=device_id,
            status=status
        ).inc()
    
    def record_cache_hit(self, cache_type: str, hit: bool):
        """Record cache hit/miss"""
        status = "hit" if hit else "miss"
        CACHE_HITS.labels(cache_type=cache_type, status=status).inc()

# Global metrics collector
metrics_collector = MetricsCollector()

async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    # Update metrics before serving
    await metrics_collector.update_mower_metrics()
    await metrics_collector.update_billing_metrics()
    
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

### Structured Logging

**Logging Configuration:**
```python
# src/core/logging.py
import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any
from pythonjsonlogger import jsonlogger

from src.core.config import settings

class MowthosOSFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['service'] = 'mowthosos'
        log_record['environment'] = settings.environment
        
        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'device_id'):
            log_record['device_id'] = record.device_id

def setup_logging():
    """Configure application logging"""
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = MowthosOSFormatter(
        '%(timestamp)s %(level)s %(logger)s %(message)s'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific log levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("stripe").setLevel(logging.INFO)
    
    # Sentry integration for error tracking
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        
        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        )
        
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[sentry_logging, SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            environment=settings.environment
        )

class ContextLogger:
    """Logger with request context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set logging context"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context"""
        self.context.clear()
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        """Log with context"""
        extra = kwargs.get('extra', {})
        extra.update(self.context)
        kwargs['extra'] = extra
        self.logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)

# Request context middleware
class LoggingContextMiddleware:
    """Middleware to add request context to logs"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request_id = f"req_{int(time.time() * 1000)}"
        
        # Add context to all loggers in this request
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers:
                if hasattr(handler, 'setFormatter'):
                    old_format = handler.format
                    
                    def new_format(record):
                        record.request_id = request_id
                        return old_format(record)
                    
                    handler.format = new_format
        
        await self.app(scope, receive, send)
```

---

## Development Tools & Workflow

### Pre-commit Hooks

**Pre-commit Configuration:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements
      
  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        language_version: python3.11
        
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
        
  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-docstrings]
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.6.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        
  - repo: https://github.com/Lucas-C/pre-commit-hooks-safety
    rev: v1.3.2
    hooks:
      - id: python-safety-dependencies-check
```

**Development Dependencies:**
```toml
# pyproject.toml - Development section
[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-cov = "^4.1.0"
pytest-mock = "^3.11.0"
factory-boy = "^3.3.0"
faker = "^19.6.0"
httpx = "^0.24.0"  # For async client testing
black = "^23.9.0"
isort = "^5.12.0"
flake8 = "^6.1.0"
mypy = "^1.6.0"
bandit = "^1.7.5"
safety = "^2.3.0"
pre-commit = "^3.5.0"
pytest-xdist = "^3.3.0"  # Parallel test execution

[tool.black]
line-length = 100
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
    PyMammotion
    | Mowthos-Cluster-Logic
)/
'''

[tool.isort]
profile = "black"
line_length = 100
skip_glob = ["PyMammotion/*", "Mowthos-Cluster-Logic/*"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
exclude = ["PyMammotion/", "Mowthos-Cluster-Logic/"]

[tool.bandit]
exclude_dirs = ["tests", "PyMammotion", "Mowthos-Cluster-Logic"]
skips = ["B101", "B601"]
```

### Development Environment

**Docker Development Setup:**
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /app/PyMammotion
      - /app/Mowthos-Cluster-Logic
    environment:
      - DATABASE_URL=postgresql://mowthosos:devpass@db:5432/mowthosos_dev
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=development
      - DEBUG=true
    depends_on:
      - db
      - redis
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
    
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mowthosos_dev
      POSTGRES_USER: mowthosos
      POSTGRES_PASSWORD: devpass
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
      
  celery:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://mowthosos:devpass@db:5432/mowthosos_dev
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    command: celery -A src.core.celery worker --loglevel=info --reload
    
  pgadmin:
    image: dpage/pgadmin4
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@mowthosos.dev
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - db

volumes:
  postgres_dev_data:
```

**Development Dockerfile:**
```dockerfile
# Dockerfile.dev
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    gdal-bin \
    libgdal-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --with dev

# Copy application code
COPY . .

# Development command (overridden in docker-compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## Testing Framework

### Test Configuration

**Pytest Setup:**
```python
# conftest.py
import pytest
import asyncio
from typing import AsyncGenerator
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from src.api.main import app
from src.core.database import get_db, Base
from src.core.config import settings

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True
)

TestingSessionLocal = sessionmaker(
    test_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        
        async with TestingSessionLocal() as session:
            yield session
            await session.rollback()

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_mammotion():
    """Mock PyMammotion for testing."""
    from unittest.mock import AsyncMock, Mock
    
    mock = Mock()
    mock.login_and_initiate_cloud = AsyncMock()
    mock.get_device_by_name = Mock()
    mock.send_command = AsyncMock()
    mock.device_manager.devices = {
        "Luba-TEST": Mock(
            name="Luba-TEST",
            iot_id="test_iot_id",
            preference="WIFI",
            has_cloud=lambda: True,
            has_ble=lambda: False,
            mower_state=Mock(
                online=True,
                report_data=Mock(
                    dev=Mock(
                        battery_val=85,
                        charge_state=0,
                        sys_status=13
                    ),
                    work=Mock(
                        progress=45,
                        area=150
                    )
                ),
                location=Mock(
                    device=Mock(
                        latitude=44.0123,
                        longitude=-92.1234
                    ),
                    orientation=90
                )
            )
        )
    }
    
    return mock

@pytest.fixture
def test_user_data():
    """Test user data factory."""
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "full_name": "Test User",
        "is_active": True,
        "is_verified": True
    }
```

**Service Tests:**
```python
# tests/test_services/test_mower_service.py
import pytest
from unittest.mock import AsyncMock, patch
from src.services.mower.mammotion_wrapper import MammotionIntegrationService
from src.models.schemas import MowerStatus

class TestMammotionIntegrationService:
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_mammotion):
        """Test successful user authentication."""
        service = MammotionIntegrationService()
        
        with patch.object(service, 'get_mammotion_instance', return_value=mock_mammotion):
            result = await service.authenticate_user("test@example.com", "password")
            
            assert result["success"] is True
            assert "session_id" in result
            assert len(result["devices"]) == 1
            assert result["devices"][0]["name"] == "Luba-TEST"
    
    @pytest.mark.asyncio
    async def test_get_device_status_success(self, mock_mammotion):
        """Test getting device status."""
        service = MammotionIntegrationService()
        
        with patch.object(service, 'get_mammotion_instance', return_value=mock_mammotion):
            with patch.object(service, '_get_device_cluster', return_value=1):
                with patch.object(service, '_get_usage_today', return_value=120):
                    with patch.object(service, '_get_next_maintenance', return_value=None):
                        
                        status = await service.get_device_status("Luba-TEST")
                        
                        assert isinstance(status, MowerStatus)
                        assert status.device_name == "Luba-TEST"
                        assert status.battery_level == 85
                        assert status.online is True
                        assert status.cluster_id == 1
                        assert status.usage_minutes_today == 120
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_mammotion):
        """Test successful command execution."""
        service = MammotionIntegrationService()
        
        with patch.object(service, 'get_mammotion_instance', return_value=mock_mammotion):
            with patch.object(service, '_log_command_execution') as mock_log:
                
                result = await service.execute_command("Luba-TEST", "start_job")
                
                assert result["success"] is True
                assert result["command"] == "start_job"
                assert result["device_name"] == "Luba-TEST"
                mock_mammotion.send_command.assert_called_once_with("Luba-TEST", "start_job")
                mock_log.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_invalid_command(self, mock_mammotion):
        """Test invalid command execution."""
        service = MammotionIntegrationService()
        
        with patch.object(service, 'get_mammotion_instance', return_value=mock_mammotion):
            with pytest.raises(ValueError, match="Invalid command"):
                await service.execute_command("Luba-TEST", "invalid_command")
```

**API Tests:**
```python
# tests/test_api/test_mowers.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

class TestMowerAPI:
    
    @pytest.mark.asyncio
    async def test_get_device_status_success(self, client: AsyncClient, test_user_data):
        """Test getting device status endpoint."""
        
        # Mock authentication
        with patch('src.api.dependencies.get_current_user', return_value=test_user_data):
            # Mock mower service
            with patch('src.services.mower.service.MowerService') as mock_service:
                mock_service.return_value.user_can_access_device = AsyncMock(return_value=True)
                mock_service.return_value.get_device_status = AsyncMock(return_value={
                    "device_id": "Luba-TEST",
                    "device_name": "Luba-TEST",
                    "online": True,
                    "battery_level": 85,
                    "charging_state": 0,
                    "work_mode": "MODE_WORKING",
                    "location": {"latitude": 44.0123, "longitude": -92.1234},
                    "work_progress": 45,
                    "work_area": 150,
                    "last_updated": "2024-01-15T10:30:00",
                    "cluster_id": 1,
                    "usage_minutes_today": 120,
                    "next_maintenance": None,
                    "subscription_status": "active"
                })
                
                response = await client.get(
                    "/api/v1/mowers/Luba-TEST/status",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["device_name"] == "Luba-TEST"
                assert data["battery_level"] == 85
                assert data["online"] is True
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, client: AsyncClient, test_user_data):
        """Test command execution endpoint."""
        
        with patch('src.api.dependencies.get_current_user', return_value=test_user_data):
            with patch('src.services.mower.service.MowerService') as mock_service:
                mock_service.return_value.user_can_access_device = AsyncMock(return_value=True)
                mock_service.return_value.execute_command = AsyncMock(return_value={
                    "success": True,
                    "command": "start_job",
                    "device_name": "Luba-TEST",
                    "message": "Command executed successfully"
                })
                
                response = await client.post(
                    "/api/v1/mowers/Luba-TEST/commands/start_job",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["command"] == "start_job"
    
    @pytest.mark.asyncio
    async def test_access_denied(self, client: AsyncClient, test_user_data):
        """Test access denied to device."""
        
        with patch('src.api.dependencies.get_current_user', return_value=test_user_data):
            with patch('src.services.mower.service.MowerService') as mock_service:
                mock_service.return_value.user_can_access_device = AsyncMock(return_value=False)
                
                response = await client.get(
                    "/api/v1/mowers/Luba-TEST/status",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 403
                assert "Access denied" in response.json()["detail"]
```

**Load Testing:**
```python
# tests/performance/test_load.py
import asyncio
import aiohttp
import time
from typing import List
import pytest

class TestAPIPerformance:
    
    @pytest.mark.asyncio
    async def test_concurrent_status_requests(self):
        """Test API performance under concurrent load."""
        
        async def make_request(session: aiohttp.ClientSession, device_id: str):
            """Make a single status request."""
            start_time = time.time()
            async with session.get(f"http://localhost:8000/api/v1/mowers/{device_id}/status") as response:
                await response.text()
                return time.time() - start_time, response.status
        
        async def run_load_test(num_requests: int, concurrency: int):
            """Run load test with specified parameters."""
            async with aiohttp.ClientSession(
                headers={"Authorization": "Bearer test_token"}
            ) as session:
                tasks = []
                for i in range(num_requests):
                    task = make_request(session, f"Luba-TEST-{i % 10}")
                    tasks.append(task)
                    
                    # Control concurrency
                    if len(tasks) >= concurrency:
                        batch_results = await asyncio.gather(*tasks)
                        tasks = []
                        
                        # Check performance
                        response_times = [result[0] for result in batch_results]
                        status_codes = [result[1] for result in batch_results]
                        
                        avg_response_time = sum(response_times) / len(response_times)
                        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time}s"
                        assert all(code < 500 for code in status_codes), "Server errors detected"
                
                # Process remaining tasks
                if tasks:
                    await asyncio.gather(*tasks)
        
        # Test with different load levels
        await run_load_test(num_requests=100, concurrency=10)
        await run_load_test(num_requests=500, concurrency=25)
```

---

## Deployment & Infrastructure

### Production Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    gdal-bin \
    libgdal-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry for production
RUN poetry config virtualenvs.create false

# Install production dependencies only
RUN poetry install --only=main --no-dev

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Remove development files
RUN rm -rf tests/ docs/ .git/ .pytest_cache/ .mypy_cache/

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Production command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Kubernetes Configuration

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mowthosos

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mowthosos-config
  namespace: mowthosos
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  DATABASE_URL: "postgresql://mowthosos:$(DB_PASSWORD)@postgres:5432/mowthosos"
  REDIS_URL: "redis://redis:6379/0"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: mowthosos-secret
  namespace: mowthosos
type: Opaque
data:
  DB_PASSWORD: <base64-encoded-password>
  SECRET_KEY: <base64-encoded-secret>
  STRIPE_SECRET_KEY: <base64-encoded-stripe-key>
  MAPBOX_ACCESS_TOKEN: <base64-encoded-mapbox-token>
  SENTRY_DSN: <base64-encoded-sentry-dsn>

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mowthosos-api
  namespace: mowthosos
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mowthosos-api
  template:
    metadata:
      labels:
        app: mowthosos-api
    spec:
      containers:
      - name: api
        image: mowthosos/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mowthosos-secret
              key: DB_PASSWORD
        envFrom:
        - configMapRef:
            name: mowthosos-config
        - secretRef:
            name: mowthosos-secret
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: mowthosos-api-service
  namespace: mowthosos
spec:
  selector:
    app: mowthosos-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mowthosos-ingress
  namespace: mowthosos
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.mowthosos.com
    secretName: mowthosos-tls
  rules:
  - host: api.mowthosos.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mowthosos-api-service
            port:
              number: 80
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
**Goal: Set up core infrastructure and development environment**

**Week 1:**
- [ ] Repository restructuring with proper src/ layout
- [ ] Set up Poetry for dependency management
- [ ] Configure pre-commit hooks and linting
- [ ] Implement basic FastAPI application structure
- [ ] Set up PostgreSQL with SQLAlchemy 2.0
- [ ] Create initial database models and migrations

**Week 2:**
- [ ] Implement Redis caching layer
- [ ] Set up JWT authentication system
- [ ] Create security middleware (rate limiting, CORS)
- [ ] Implement basic logging and monitoring
- [ ] Set up development Docker environment
- [ ] Create PyMammotion integration wrapper (read-only)

### Phase 2: Core Services (Weeks 3-4)
**Goal: Implement mower control and cluster services**

**Week 3:**
- [ ] Complete MammotionIntegrationService implementation
- [ ] Create mower control API endpoints
- [ ] Implement device status caching and synchronization
- [ ] Set up Celery for background tasks
- [ ] Create Mowthos-Cluster-Logic wrapper service

**Week 4:**
- [ ] Implement cluster management APIs
- [ ] Create enhanced geographic services
- [ ] Set up route optimization algorithms
- [ ] Implement real-time status updates
- [ ] Create comprehensive API documentation

### Phase 3: Enterprise Features (Weeks 5-6)
**Goal: Add production-ready features**

**Week 5:**
- [ ] Implement Stripe payment integration
- [ ] Create billing and subscription services
- [ ] Set up usage tracking and metering
- [ ] Implement user management and permissions
- [ ] Create admin dashboard APIs

**Week 6:**
- [ ] Set up Prometheus metrics collection
- [ ] Implement structured logging with Sentry
- [ ] Create health checks and monitoring
- [ ] Set up automated alerting
- [ ] Implement backup and recovery procedures

### Phase 4: Testing & Quality (Weeks 7-8)
**Goal: Ensure reliability and performance**

**Week 7:**
- [ ] Create comprehensive test suite (unit, integration, e2e)
- [ ] Implement test factories and mocks
- [ ] Set up continuous integration pipeline
- [ ] Perform load testing and optimization
- [ ] Security audit and penetration testing

**Week 8:**
- [ ] Performance tuning and optimization
- [ ] Database query optimization
- [ ] Caching strategy refinement
- [ ] Error handling and resilience testing
- [ ] Documentation review and updates

### Phase 5: Production Deployment (Weeks 9-10)
**Goal: Deploy to production environment**

**Week 9:**
- [ ] Set up production infrastructure (AWS/GCP/Azure)
- [ ] Configure Kubernetes cluster
- [ ] Set up CI/CD pipeline with GitHub Actions
- [ ] Implement blue-green deployment strategy
- [ ] Configure monitoring and alerting

**Week 10:**
- [ ] Production deployment and testing
- [ ] Performance monitoring and tuning
- [ ] User acceptance testing
- [ ] Documentation finalization
- [ ] Team training and handover

### Success Metrics

**Technical Metrics:**
- API response time < 200ms (95th percentile)
- System uptime > 99.9%
- Test coverage > 90%
- Zero-downtime deployments
- Error rate < 0.1%

**Business Metrics:**
- Support for 1000+ concurrent users
- Multi-tenant architecture ready
- Payment processing integration complete
- Real-time mower fleet monitoring
- Scalable to 10,000+ devices

**Quality Metrics:**
- All external dependencies properly wrapped
- Comprehensive documentation
- Automated testing and deployment
- Security best practices implemented
- Production monitoring and alerting

---

This comprehensive tech stack guidelines document provides detailed implementation guidance for every component of the MowthosOS architecture. The document emphasizes safe integration patterns that respect the external submodules while building a professional, scalable system around them.

**Key highlights:**
- **Strict adherence to not modifying external submodules**
- **Composition patterns throughout**
- **Production-ready configurations**
- **Comprehensive error handling**
- **Caching and performance optimization**
- **Monitoring and observability**
- **Scalable architecture patterns**

The guidelines provide enough detail for a development team to implement the system following best practices and enterprise standards.