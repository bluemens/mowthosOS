"""
Device management endpoints for Host users.
Only Hosts can register and manage devices.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.core.database import get_db
from src.core.auth import get_current_active_user
from src.models.database.users import User, UserRole
from src.services.device import DeviceService
from src.services.mower import MowerService

router = APIRouter(prefix="/devices", tags=["devices"])


# Request/Response Models
class MammotionLoginRequest(BaseModel):
    """Mammotion account credentials for device registration"""
    mammotion_email: str = Field(..., description="Mammotion account email")
    mammotion_password: str = Field(..., description="Mammotion account password")


class DeviceRegistrationRequest(BaseModel):
    """Request to register a device from Mammotion account"""
    mammotion_email: str = Field(..., description="Mammotion account email")
    mammotion_password: str = Field(..., description="Mammotion account password")
    device_name: str = Field(..., description="Mammotion device name (e.g., Luba-XXXXX)")
    device_nickname: Optional[str] = Field(None, description="User-friendly nickname for the device")


class DeviceResponse(BaseModel):
    """Device information response"""
    id: str
    device_id: str
    device_name: str
    device_nickname: Optional[str]
    device_model: str
    status: str
    battery_level: Optional[int]
    is_online: bool
    last_seen: Optional[str]
    created_at: str
    
    class Config:
        from_attributes = True


class DeviceStatusResponse(BaseModel):
    """Device status response"""
    device_id: str
    device_name: str
    status: str
    battery_level: Optional[int]
    charging_state: Optional[int]
    work_mode: Optional[str]
    work_progress: Optional[int]
    is_online: bool
    current_location: Optional[dict]
    last_updated: str


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


# Helper function to verify Host role
async def get_current_host_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Verify the current user is a Host"""
    if current_user.role != UserRole.HOST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Host users can manage devices"
        )
    return current_user


# API Endpoints
@router.get("/", response_model=List[DeviceResponse])
async def get_user_devices(
    current_user: User = Depends(get_current_host_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all devices registered by the current Host user"""
    device_service = DeviceService(db)
    
    try:
        devices = await device_service.get_user_devices(current_user.id)
        return [DeviceResponse.from_orm(device) for device in devices]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get devices: {str(e)}"
        )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    current_user: User = Depends(get_current_host_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific device details (with ownership verification)"""
    device_service = DeviceService(db)
    
    try:
        # Verify device ownership
        if not await device_service.verify_device_ownership(current_user.id, device_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found or access denied"
            )
        
        device = await device_service.get_device_by_id(device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        
        return DeviceResponse.from_orm(device)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get device: {str(e)}"
        )


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    device_data: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_host_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a new device from the user's Mammotion account"""
    device_service = DeviceService(db)
    mower_service = MowerService()
    
    try:
        # Authenticate with Mammotion to verify credentials and get device list
        session_id = await mower_service.authenticate_user(
            device_data.mammotion_email,
            device_data.mammotion_password
        )
        
        # Get available devices from Mammotion account
        available_devices = await mower_service.get_device_list(session_id)
        
        # Check if the requested device exists in the account
        device_found = None
        for device in available_devices:
            if device.device_name == device_data.device_name:
                device_found = device
                break
        
        if not device_found:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device '{device_data.device_name}' not found in Mammotion account"
            )
        
        # Check if device is already registered by this user
        existing_device = await device_service.get_device_by_mammotion_name(
            current_user.id, 
            device_data.device_name
        )
        
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device '{device_data.device_name}' is already registered"
            )
        
        # Register the device
        device = await device_service.register_device(
            user_id=current_user.id,
            mammotion_email=device_data.mammotion_email,
            device_name=device_data.device_name,
            device_nickname=device_data.device_nickname,
            device_info=device_found
        )
        
        return DeviceResponse.from_orm(device)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device: {str(e)}"
        )


@router.delete("/{device_id}", response_model=MessageResponse)
async def remove_device(
    device_id: str,
    current_user: User = Depends(get_current_host_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a device from the user's account (with ownership verification)"""
    device_service = DeviceService(db)
    
    try:
        # Verify device ownership
        if not await device_service.verify_device_ownership(current_user.id, device_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found or access denied"
            )
        
        # Remove the device
        await device_service.remove_device(device_id)
        
        return MessageResponse(message="Device removed successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove device: {str(e)}"
        )


@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
async def get_device_status(
    device_id: str,
    current_user: User = Depends(get_current_host_user),
    db: AsyncSession = Depends(get_db)
):
    """Get real-time status of a device (with ownership verification)"""
    device_service = DeviceService(db)
    mower_service = MowerService()
    
    try:
        # Verify device ownership
        if not await device_service.verify_device_ownership(current_user.id, device_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found or access denied"
            )
        
        # Get device from database
        device = await device_service.get_device_by_id(device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )
        
        # Get real-time status from Mammotion
        try:
            status = await mower_service.get_device_status(device.device_name)
            
            return DeviceStatusResponse(
                device_id=device.device_id,
                device_name=device.device_name,
                status=status.status,
                battery_level=status.battery_level,
                charging_state=status.charging_state,
                work_mode=status.work_mode,
                work_progress=status.work_progress,
                is_online=status.is_online,
                current_location=status.location.dict() if status.location else None,
                last_updated=status.last_updated
            )
            
        except Exception as e:
            # If we can't get real-time status, return cached status
            return DeviceStatusResponse(
                device_id=device.device_id,
                device_name=device.device_name,
                status=device.status.value,
                battery_level=device.battery_level,
                charging_state=device.charging_state,
                work_mode=device.work_mode,
                work_progress=device.work_progress,
                is_online=device.is_online,
                current_location={
                    "latitude": device.current_latitude,
                    "longitude": device.current_longitude
                } if device.current_latitude and device.current_longitude else None,
                last_updated=device.last_seen.isoformat() if device.last_seen else None
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get device status: {str(e)}"
        ) 