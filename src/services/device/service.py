"""Device service for managing Host device operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import MowerDevice, DeviceStatus, DeviceModel
from src.services.base import BaseService


class DeviceNotFoundError(Exception):
    """Device not found error"""
    pass


class DeviceAlreadyRegisteredError(Exception):
    """Device already registered error"""
    pass


class DeviceService(BaseService):
    """Service for managing device operations for Host users."""
    
    def __init__(self, db: AsyncSession):
        super().__init__("device")
        self.db = db
    
    async def get_user_devices(self, user_id: str) -> List[MowerDevice]:
        """Get all devices registered by a user"""
        stmt = (
            select(MowerDevice)
            .where(MowerDevice.owner_id == user_id)
            .order_by(MowerDevice.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_device_by_id(self, device_id: str) -> Optional[MowerDevice]:
        """Get device by ID"""
        stmt = select(MowerDevice).where(MowerDevice.id == device_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_device_by_mammotion_name(
        self, 
        user_id: str, 
        mammotion_device_name: str
    ) -> Optional[MowerDevice]:
        """Get device by Mammotion device name for a specific user"""
        stmt = (
            select(MowerDevice)
            .where(
                and_(
                    MowerDevice.owner_id == user_id,
                    MowerDevice.device_name == mammotion_device_name
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def verify_device_ownership(self, user_id: str, device_id: str) -> bool:
        """Verify that a device belongs to a user"""
        device = await self.get_device_by_id(device_id)
        return device is not None and device.owner_id == user_id
    
    async def register_device(
        self,
        user_id: str,
        mammotion_email: str,
        device_name: str,
        device_nickname: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> MowerDevice:
        """Register a new device for a user"""
        # Check if device is already registered by this user
        existing_device = await self.get_device_by_mammotion_name(user_id, device_name)
        if existing_device:
            raise DeviceAlreadyRegisteredError(f"Device {device_name} is already registered")
        
        # Determine device model from device info or default to unknown
        device_model = DeviceModel.UNKNOWN
        if device_info and hasattr(device_info, 'model'):
            model_mapping = {
                'luba_awd_1000': DeviceModel.LUBA_AWD_1000,
                'luba_awd_3000': DeviceModel.LUBA_AWD_3000,
                'luba_awd_5000': DeviceModel.LUBA_AWD_5000,
                'yuka_1500': DeviceModel.YUKA_1500,
                'yuka_sweeper_1500': DeviceModel.YUKA_SWEEPER_1500,
            }
            device_model = model_mapping.get(device_info.model.lower(), DeviceModel.UNKNOWN)
        
        # Create device record
        device = MowerDevice(
            device_id=str(uuid.uuid4()),  # Internal device ID
            device_name=device_name,  # Mammotion device name
            device_nickname=device_nickname,
            device_model=device_model,
            owner_id=user_id,
            mammotion_account=mammotion_email,
            status=DeviceStatus.OFFLINE,
            is_online=False,
            capabilities={},  # Will be populated from device info
            supported_modes=[],  # Will be populated from device info
            settings={},  # Default settings
        )
        
        # Set device capabilities if available
        if device_info:
            if hasattr(device_info, 'has_cloud'):
                device.capabilities['cloud'] = device_info.has_cloud
            if hasattr(device_info, 'has_ble'):
                device.capabilities['bluetooth'] = device_info.has_ble
            if hasattr(device_info, 'connection_type'):
                device.connection_type = device_info.connection_type
        
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        
        return device
    
    async def remove_device(self, device_id: str) -> None:
        """Remove a device from the user's account"""
        device = await self.get_device_by_id(device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        # Soft delete by setting deleted_at timestamp
        device.deleted_at = datetime.utcnow()
        device.is_active = False
        
        await self.db.commit()
    
    async def update_device_status(
        self, 
        device_id: str, 
        status_data: Dict[str, Any]
    ) -> MowerDevice:
        """Update device status from Mammotion data"""
        device = await self.get_device_by_id(device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        # Update status fields
        if 'status' in status_data:
            device.status = DeviceStatus(status_data['status'])
        
        if 'battery_level' in status_data:
            device.battery_level = status_data['battery_level']
        
        if 'charging_state' in status_data:
            device.charging_state = status_data['charging_state']
        
        if 'work_mode' in status_data:
            device.work_mode = status_data['work_mode']
        
        if 'work_progress' in status_data:
            device.work_progress = status_data['work_progress']
        
        if 'is_online' in status_data:
            device.is_online = status_data['is_online']
        
        if 'location' in status_data:
            location = status_data['location']
            if location and 'latitude' in location and 'longitude' in location:
                device.current_latitude = location['latitude']
                device.current_longitude = location['longitude']
                device.location_updated_at = datetime.utcnow()
        
        # Update last seen timestamp
        device.last_seen = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(device)
        
        return device
    
    async def get_device_statistics(self, device_id: str) -> Dict[str, Any]:
        """Get device usage statistics"""
        device = await self.get_device_by_id(device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        # Calculate statistics
        total_runtime = device.total_runtime_hours or 0
        total_distance = device.total_distance_km or 0
        error_count = device.error_count or 0
        
        # Get recent usage records (last 30 days)
        from src.models.database import DeviceUsageRecord
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        stmt = (
            select(DeviceUsageRecord)
            .where(
                and_(
                    DeviceUsageRecord.device_id == device_id,
                    DeviceUsageRecord.session_start >= thirty_days_ago
                )
            )
        )
        result = await self.db.execute(stmt)
        recent_usage = result.scalars().all()
        
        recent_runtime = sum(record.duration_minutes or 0 for record in recent_usage) / 60
        recent_distance = sum(record.distance_traveled_m or 0 for record in recent_usage) / 1000
        
        return {
            "total_runtime_hours": total_runtime,
            "total_distance_km": total_distance,
            "error_count": error_count,
            "recent_runtime_hours": recent_runtime,
            "recent_distance_km": recent_distance,
            "recent_sessions": len(recent_usage),
            "last_maintenance": device.last_maintenance.isoformat() if device.last_maintenance else None,
            "next_maintenance_due": device.next_maintenance_due.isoformat() if device.next_maintenance_due else None,
        }
    
    async def get_devices_by_cluster(self, cluster_id: str) -> List[MowerDevice]:
        """Get all devices in a cluster"""
        stmt = (
            select(MowerDevice)
            .where(MowerDevice.cluster_id == cluster_id)
            .order_by(MowerDevice.created_at)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def assign_device_to_cluster(
        self, 
        device_id: str, 
        cluster_id: str
    ) -> MowerDevice:
        """Assign a device to a cluster"""
        device = await self.get_device_by_id(device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        device.cluster_id = cluster_id
        await self.db.commit()
        await self.db.refresh(device)
        
        return device
    
    async def remove_device_from_cluster(self, device_id: str) -> MowerDevice:
        """Remove a device from its cluster"""
        device = await self.get_device_by_id(device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        device.cluster_id = None
        await self.db.commit()
        await self.db.refresh(device)
        
        return device 