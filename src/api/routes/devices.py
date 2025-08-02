"""Device management API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime, date

from src.core.database import get_db
from src.core.auth import get_current_active_user
from src.models.database.users import User
from src.models.database.devices import (
    MowerDevice, MaintenanceRecord, DeviceUsageRecord,
    DeviceCommand, DeviceTelemetry
)
from src.services.mower import MowerService

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


# Request/Response Models
class RegisterDeviceRequest(BaseModel):
    """Request to register a new device"""
    device_name: str = Field(..., description="Device name from Mammotion")
    model: str = Field(..., description="Device model")
    serial_number: str = Field(..., description="Device serial number")
    firmware_version: Optional[str] = None


class UpdateDeviceRequest(BaseModel):
    """Request to update device settings"""
    nickname: Optional[str] = Field(None, max_length=100)
    cutting_height: Optional[int] = Field(None, ge=20, le=70, description="Cutting height in mm")
    blade_type: Optional[str] = None
    notification_settings: Optional[dict] = None


class MaintenanceRequest(BaseModel):
    """Request to log maintenance"""
    maintenance_type: str = Field(..., description="Type of maintenance performed")
    description: Optional[str] = None
    parts_replaced: Optional[List[str]] = None
    cost: Optional[float] = None
    performed_by: Optional[str] = None


class DeviceResponse(BaseModel):
    """Device information response"""
    id: str
    user_id: str
    device_name: str
    nickname: Optional[str]
    model: str
    serial_number: str
    firmware_version: Optional[str]
    status: str
    total_runtime_hours: float
    total_area_mowed_sqm: float
    last_maintenance: Optional[datetime]
    registered_at: datetime
    cutting_height: Optional[int]
    blade_type: Optional[str]


class MaintenanceResponse(BaseModel):
    """Maintenance record response"""
    id: str
    device_id: str
    maintenance_type: str
    description: Optional[str]
    performed_at: datetime
    runtime_hours_at_maintenance: float
    parts_replaced: Optional[List[str]]
    cost: Optional[float]
    performed_by: Optional[str]


class UsageStatsResponse(BaseModel):
    """Device usage statistics"""
    device_id: str
    period: str
    total_runtime_minutes: int
    total_area_mowed_sqm: float
    average_daily_runtime: float
    total_sessions: int
    efficiency_score: Optional[float]


class TelemetryResponse(BaseModel):
    """Device telemetry data"""
    device_id: str
    timestamp: datetime
    battery_level: int
    location: Optional[dict]
    speed: Optional[float]
    blade_rpm: Optional[int]
    temperature: Optional[float]
    signal_strength: Optional[int]
    error_codes: Optional[List[str]]


# Endpoints
@router.post("/register", response_model=DeviceResponse)
async def register_device(
    request: RegisterDeviceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a new device"""
    # Check if device already registered
    existing = await db.query(MowerDevice).filter(
        MowerDevice.device_name == request.device_name,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device already registered"
        )
    
    # Create device record
    device = MowerDevice(
        user_id=current_user.id,
        device_name=request.device_name,
        model=request.model,
        serial_number=request.serial_number,
        firmware_version=request.firmware_version,
        status="active",
        total_runtime_hours=0,
        total_area_mowed_sqm=0
    )
    
    db.add(device)
    await db.commit()
    await db.refresh(device)
    
    return DeviceResponse(
        id=str(device.id),
        user_id=str(device.user_id),
        device_name=device.device_name,
        nickname=device.nickname,
        model=device.model,
        serial_number=device.serial_number,
        firmware_version=device.firmware_version,
        status=device.status,
        total_runtime_hours=device.total_runtime_hours,
        total_area_mowed_sqm=device.total_area_mowed_sqm,
        last_maintenance=device.last_maintenance,
        registered_at=device.created_at,
        cutting_height=device.cutting_height,
        blade_type=device.blade_type
    )


@router.get("/my-devices", response_model=List[DeviceResponse])
async def get_my_devices(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all devices registered to current user"""
    devices = await db.query(MowerDevice).filter(
        MowerDevice.user_id == current_user.id
    ).all()
    
    return [
        DeviceResponse(
            id=str(device.id),
            user_id=str(device.user_id),
            device_name=device.device_name,
            nickname=device.nickname,
            model=device.model,
            serial_number=device.serial_number,
            firmware_version=device.firmware_version,
            status=device.status,
            total_runtime_hours=device.total_runtime_hours,
            total_area_mowed_sqm=device.total_area_mowed_sqm,
            last_maintenance=device.last_maintenance,
            registered_at=device.created_at,
            cutting_height=device.cutting_height,
            blade_type=device.blade_type
        )
        for device in devices
    ]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device_details(
    device_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get device details"""
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return DeviceResponse(
        id=str(device.id),
        user_id=str(device.user_id),
        device_name=device.device_name,
        nickname=device.nickname,
        model=device.model,
        serial_number=device.serial_number,
        firmware_version=device.firmware_version,
        status=device.status,
        total_runtime_hours=device.total_runtime_hours,
        total_area_mowed_sqm=device.total_area_mowed_sqm,
        last_maintenance=device.last_maintenance,
        registered_at=device.created_at,
        cutting_height=device.cutting_height,
        blade_type=device.blade_type
    )


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    request: UpdateDeviceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update device settings"""
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Update fields
    if request.nickname is not None:
        device.nickname = request.nickname
    if request.cutting_height is not None:
        device.cutting_height = request.cutting_height
    if request.blade_type is not None:
        device.blade_type = request.blade_type
    if request.notification_settings is not None:
        device.notification_settings = request.notification_settings
    
    device.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(device)
    
    return DeviceResponse(
        id=str(device.id),
        user_id=str(device.user_id),
        device_name=device.device_name,
        nickname=device.nickname,
        model=device.model,
        serial_number=device.serial_number,
        firmware_version=device.firmware_version,
        status=device.status,
        total_runtime_hours=device.total_runtime_hours,
        total_area_mowed_sqm=device.total_area_mowed_sqm,
        last_maintenance=device.last_maintenance,
        registered_at=device.created_at,
        cutting_height=device.cutting_height,
        blade_type=device.blade_type
    )


@router.post("/{device_id}/maintenance", response_model=MaintenanceResponse)
async def log_maintenance(
    device_id: str,
    request: MaintenanceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Log device maintenance"""
    # Verify device ownership
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Create maintenance record
    maintenance = MaintenanceRecord(
        device_id=device.id,
        maintenance_type=request.maintenance_type,
        description=request.description,
        runtime_hours_at_maintenance=device.total_runtime_hours,
        parts_replaced=request.parts_replaced,
        cost=request.cost,
        performed_by=request.performed_by or current_user.email
    )
    
    # Update device last maintenance
    device.last_maintenance = datetime.utcnow()
    
    db.add(maintenance)
    await db.commit()
    await db.refresh(maintenance)
    
    return MaintenanceResponse(
        id=str(maintenance.id),
        device_id=str(maintenance.device_id),
        maintenance_type=maintenance.maintenance_type,
        description=maintenance.description,
        performed_at=maintenance.performed_at,
        runtime_hours_at_maintenance=maintenance.runtime_hours_at_maintenance,
        parts_replaced=maintenance.parts_replaced,
        cost=maintenance.cost,
        performed_by=maintenance.performed_by
    )


@router.get("/{device_id}/maintenance", response_model=List[MaintenanceResponse])
async def get_maintenance_history(
    device_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get device maintenance history"""
    # Verify device ownership
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    records = await db.query(MaintenanceRecord).filter(
        MaintenanceRecord.device_id == device_id
    ).order_by(MaintenanceRecord.performed_at.desc()).all()
    
    return [
        MaintenanceResponse(
            id=str(record.id),
            device_id=str(record.device_id),
            maintenance_type=record.maintenance_type,
            description=record.description,
            performed_at=record.performed_at,
            runtime_hours_at_maintenance=record.runtime_hours_at_maintenance,
            parts_replaced=record.parts_replaced,
            cost=record.cost,
            performed_by=record.performed_by
        )
        for record in records
    ]


@router.get("/{device_id}/usage-stats", response_model=UsageStatsResponse)
async def get_usage_statistics(
    device_id: str,
    period: str = Query("week", description="Period: day, week, month, year"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get device usage statistics"""
    # Verify device ownership
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Calculate date range based on period
    from datetime import timedelta
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
    elif period == "year":
        start_date = end_date - timedelta(days=365)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Use: day, week, month, or year"
        )
    
    # Query usage records
    usage_records = await db.query(DeviceUsageRecord).filter(
        DeviceUsageRecord.device_id == device_id,
        DeviceUsageRecord.start_time >= start_date
    ).all()
    
    # Calculate statistics
    total_runtime = sum(r.runtime_minutes for r in usage_records)
    total_area = sum(r.area_mowed_sqm for r in usage_records)
    total_sessions = len(usage_records)
    
    days_in_period = (end_date - start_date).days or 1
    avg_daily_runtime = total_runtime / days_in_period
    
    # Calculate efficiency (area per hour)
    efficiency = (total_area / (total_runtime / 60)) if total_runtime > 0 else None
    
    return UsageStatsResponse(
        device_id=str(device_id),
        period=period,
        total_runtime_minutes=total_runtime,
        total_area_mowed_sqm=total_area,
        average_daily_runtime=avg_daily_runtime,
        total_sessions=total_sessions,
        efficiency_score=efficiency
    )


@router.get("/{device_id}/telemetry", response_model=List[TelemetryResponse])
async def get_device_telemetry(
    device_id: str,
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent device telemetry data"""
    # Verify device ownership
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Get recent telemetry
    telemetry = await db.query(DeviceTelemetry).filter(
        DeviceTelemetry.device_id == device_id
    ).order_by(DeviceTelemetry.timestamp.desc()).limit(limit).all()
    
    return [
        TelemetryResponse(
            device_id=str(t.device_id),
            timestamp=t.timestamp,
            battery_level=t.battery_level,
            location=t.location,
            speed=t.speed,
            blade_rpm=t.blade_rpm,
            temperature=t.temperature,
            signal_strength=t.signal_strength,
            error_codes=t.error_codes
        )
        for t in telemetry
    ]


@router.delete("/{device_id}")
async def unregister_device(
    device_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Unregister a device"""
    device = await db.query(MowerDevice).filter(
        MowerDevice.id == device_id,
        MowerDevice.user_id == current_user.id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Mark as inactive instead of deleting to preserve history
    device.status = "inactive"
    device.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Device unregistered successfully"}