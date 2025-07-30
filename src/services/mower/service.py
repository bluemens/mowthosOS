"""
Mower service for PyMammotion integration.

This service handles all mower-related operations including authentication,
status monitoring, and command execution.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from pymammotion.mammotion.devices.mammotion import Mammotion
from pymammotion.data.model.enums import ConnectionPreference
from pymammotion.utility.constant.device_constant import WorkMode, device_mode

from src.models.schemas import MowerStatus
from src.models.enums import WorkMode as AppWorkMode, CommandType
from src.core.session import SessionManager

logger = logging.getLogger(__name__)

class MowerService:
    """Service for managing mower operations."""
    
    def __init__(self):
        self.mammotion = Mammotion()
        self.session_manager = SessionManager()
        self.active_sessions: Dict[str, str] = {}
    
    async def authenticate_user(self, account: str, password: str, device_name: Optional[str] = None) -> str:
        """
        Authenticate user and return session ID.
        
        Args:
            account: Mammotion account email/username
            password: Account password
            device_name: Optional specific device name
            
        Returns:
            Session ID for the authenticated user
            
        Raises:
            Exception: If authentication fails
        """
        try:
            logger.info(f"Authenticating user: {account}")
            
            # Create session
            session_id = self.session_manager.create_session(account, device_name)
            
            # Store active session
            self.active_sessions[account] = session_id
            
            logger.info(f"Authentication successful for {account}, session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Authentication failed for {account}: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")
    
    async def get_device_status(self, device_name: str) -> MowerStatus:
        """
        Get real-time device status.
        
        Args:
            device_name: Name of the device
            
        Returns:
            MowerStatus object with current device status
            
        Raises:
            Exception: If status retrieval fails
        """
        try:
            logger.info(f"Getting status for device: {device_name}")
            
            # Get device status from PyMammotion
            # Note: This is a placeholder - actual implementation depends on PyMammotion API
            status_data = await self._get_device_status_from_mammotion(device_name)
            
            # Convert to our schema
            status = MowerStatus(
                device_name=device_name,
                online=status_data.get("online", False),
                work_mode=status_data.get("work_mode", "unknown"),
                work_mode_code=status_data.get("work_mode_code", 0),
                battery_level=status_data.get("battery_level", 0),
                charging_state=status_data.get("charging_state", 0),
                blade_status=status_data.get("blade_status", False),
                location=status_data.get("location"),
                work_progress=status_data.get("work_progress"),
                work_area=status_data.get("work_area"),
                last_updated=datetime.now()
            )
            
            logger.info(f"Status retrieved for {device_name}: {status.work_mode}")
            return status
            
        except Exception as e:
            logger.error(f"Failed to get status for {device_name}: {str(e)}")
            raise Exception(f"Status retrieval failed: {str(e)}")
    
    async def execute_command(self, device_name: str, command: str) -> bool:
        """
        Execute mower command.
        
        Args:
            device_name: Name of the device
            command: Command to execute
            
        Returns:
            True if command was successful, False otherwise
            
        Raises:
            Exception: If command execution fails
        """
        try:
            logger.info(f"Executing command '{command}' for device: {device_name}")
            
            # Validate command
            if command not in [cmd.value for cmd in CommandType]:
                raise ValueError(f"Invalid command: {command}")
            
            # Execute command via PyMammotion
            success = await self._execute_command_via_mammotion(device_name, command)
            
            if success:
                logger.info(f"Command '{command}' executed successfully for {device_name}")
            else:
                logger.warning(f"Command '{command}' failed for {device_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Command execution failed for {device_name}: {str(e)}")
            raise Exception(f"Command execution failed: {str(e)}")
    
    async def list_devices(self) -> List[Dict[str, Any]]:
        """
        List all available devices for the authenticated user.
        
        Returns:
            List of device information dictionaries
        """
        try:
            logger.info("Listing available devices")
            
            # Get devices from PyMammotion
            devices = await self._get_devices_from_mammotion()
            
            logger.info(f"Found {len(devices)} devices")
            return devices
            
        except Exception as e:
            logger.error(f"Failed to list devices: {str(e)}")
            raise Exception(f"Device listing failed: {str(e)}")
    
    async def _get_device_status_from_mammotion(self, device_name: str) -> Dict[str, Any]:
        """
        Get device status from PyMammotion library.
        
        This is a placeholder implementation that should be replaced with
        actual PyMammotion API calls.
        """
        # TODO: Implement actual PyMammotion status retrieval
        # For now, return mock data
        return {
            "online": True,
            "work_mode": "idle",
            "work_mode_code": 0,
            "battery_level": 85,
            "charging_state": 0,
            "blade_status": False,
            "location": {"lat": 0, "lng": 0},
            "work_progress": 0,
            "work_area": 0
        }
    
    async def _execute_command_via_mammotion(self, device_name: str, command: str) -> bool:
        """
        Execute command via PyMammotion library.
        
        This is a placeholder implementation that should be replaced with
        actual PyMammotion API calls.
        """
        # TODO: Implement actual PyMammotion command execution
        # For now, return success
        await asyncio.sleep(0.1)  # Simulate API call
        return True
    
    async def _get_devices_from_mammotion(self) -> List[Dict[str, Any]]:
        """
        Get device list from PyMammotion library.
        
        This is a placeholder implementation that should be replaced with
        actual PyMammotion API calls.
        """
        # TODO: Implement actual PyMammotion device listing
        # For now, return mock data
        return [
            {
                "device_name": "Luba-TEST",
                "device_type": "luba",
                "online": True,
                "last_seen": datetime.now()
            }
        ] 