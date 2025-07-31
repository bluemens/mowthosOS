"""Mower service for managing robotic mower operations via PyMammotion."""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import json
import logging

from pymammotion.mammotion.devices.mammotion import Mammotion, MammotionMixedDeviceManager
from pymammotion.aliyun.cloud_gateway import CloudIOTGateway, SetupException
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowingDevice
from pymammotion.data.model.enums import ConnectionPreference
from pymammotion.data.state_manager import StateManager
from pymammotion.http.http import MammotionHTTP
from pymammotion.http.model.camera_stream import StreamSubscriptionResponse, VideoResourceResponse
from pymammotion.http.model.http import Response
from pymammotion.mammotion.devices.mammotion_bluetooth import MammotionBaseBLEDevice
from pymammotion.mammotion.devices.mammotion_cloud import MammotionBaseCloudDevice, MammotionCloud
from pymammotion.mqtt import MammotionMQTT
from pymammotion.utility.device_type import DeviceType
from pymammotion.utility.constant.device_constant import WorkMode, device_mode

from ..base import BaseService
from ...models.schemas import (
    MowerStatus, MowerCommand, MowerSession, DeviceInfo,
    MowingHistory, MowingZone, MowerSettings
)
from ...core.cache import cache_manager
from ...core.config import settings

logger = logging.getLogger(__name__)

class MowerService(BaseService):
    """Service for managing robotic mower operations."""
    
    def __init__(self):
        """Initialize the mower service."""
        super().__init__("mower")
        self.mammotion = Mammotion()
        self.active_sessions: Dict[str, MowerSession] = {}
        self.device_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 30  # Cache TTL in seconds
        
    async def initialize(self) -> None:
        """Initialize the mower service."""
        await super().initialize()
        # Additional initialization if needed
        
    async def authenticate_user(self, account: str, password: str) -> str:
        """Authenticate user and return session ID.
        
        Args:
            account: User's account email/username
            password: Account password
            
        Returns:
            Session ID for authenticated user
            
        Raises:
            Exception: If authentication fails
        """
        try:
            self.logger.info(f"Authenticating user: {account}")
            
            # Create HTTP client and login
            mammotion_http = MammotionHTTP()
            cloud_client = CloudIOTGateway(mammotion_http)
            
            # Login with retry logic
            await self.exponential_backoff(
                lambda: mammotion_http.login(account, password),
                max_retries=3,
                initial_delay=2.0
            )
            
            if not mammotion_http.login_info:
                raise Exception("Login failed: No login info received")
            
            country_code = mammotion_http.login_info.userInformation.domainAbbreviation
            
            # Execute cloud connection sequence
            await self._establish_cloud_connection(cloud_client, country_code)
            
            # Create MQTT connection
            mqtt_client = await self._create_mqtt_client(cloud_client)
            
            # Store MQTT client in global Mammotion instance
            self.mammotion.mqtt_list[account] = mqtt_client
            
            # Get devices and create device managers
            devices = await self._create_device_managers(cloud_client, mqtt_client)
            
            if not devices:
                raise Exception("No compatible devices found for this account")
            
            # Create session
            session_id = self._create_session(account, password, devices)
            
            self.logger.info(f"Authentication successful for account: {account}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Authentication failed for account {account}: {str(e)}")
            raise
            
    async def get_device_list(self, session_id: str) -> List[DeviceInfo]:
        """Get list of available devices for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            List of device information
        """
        session = self._get_session(session_id)
        
        devices = []
        for device_name, device in self.mammotion.device_manager.devices.items():
            device_info = DeviceInfo(
                device_name=device_name,
                iot_id=device.iot_id,
                model=device.mower_state.mower_state.model,
                product_key=device.mower_state.mower_state.product_key,
                connection_type=str(device.preference),
                has_cloud=device.has_cloud(),
                has_ble=device.has_ble(),
                online=device.mower_state.online
            )
            devices.append(device_info)
            
        return devices
        
    async def get_device_status(self, device_name: str, use_cache: bool = True) -> MowerStatus:
        """Get real-time device status with caching.
        
        Args:
            device_name: Name of the device
            use_cache: Whether to use cached data
            
        Returns:
            Current mower status
        """
        # Check cache first
        if use_cache and device_name in self.device_cache:
            cache_entry = self.device_cache[device_name]
            if datetime.now() - cache_entry['timestamp'] < timedelta(seconds=self._cache_ttl):
                return cache_entry['status']
        
        # Get fresh status
        device = self._get_device(device_name)
        mower_state = device.mower_state
        
        # Get work mode string
        work_mode_code = mower_state.report_data.dev.sys_status
        work_mode = device_mode(work_mode_code)
        
        # Get location info
        location = None
        if mower_state.location.device:
            location = {
                "latitude": mower_state.location.device.latitude,
                "longitude": mower_state.location.device.longitude,
                "position_type": mower_state.location.position_type,
                "orientation": mower_state.location.orientation
            }
        
        status = MowerStatus(
            device_name=device_name,
            online=mower_state.online,
            work_mode=work_mode,
            work_mode_code=work_mode_code,
            battery_level=mower_state.report_data.dev.battery_val,
            charging_state=mower_state.report_data.dev.charge_state,
            blade_status=mower_state.mower_state.blade_status,
            location=location,
            work_progress=mower_state.report_data.work.progress,
            work_area=mower_state.report_data.work.area,
            last_updated=datetime.now()
        )
        
        # Update cache
        self.device_cache[device_name] = {
            'status': status,
            'timestamp': datetime.now()
        }
        
        return status
        
    async def execute_command(self, device_name: str, command: MowerCommand) -> bool:
        """Execute a mower command with error handling.
        
        Args:
            device_name: Name of the device
            command: Command to execute
            
        Returns:
            True if command executed successfully
        """
        try:
            self.logger.info(f"Executing command '{command.command}' for device '{device_name}'")
            
            device = self._get_device(device_name)
            cloud_device = device.cloud()
            
            if not cloud_device:
                raise Exception("Cloud device not available")
            
            # Ensure communication is set up
            await self._ensure_device_communication(device_name)
            
            # Map command to PyMammotion command
            command_map = {
                "start_mowing": "start_job",
                "stop_mowing": "cancel_job",
                "pause_mowing": "pause_execute_task",
                "resume_mowing": "resume_execute_task",
                "return_to_dock": "return_to_dock",
                "start_zone_mowing": "start_job",  # With zone parameters
                "emergency_stop": "emergency_stop"
            }
            
            pymammotion_command = command_map.get(command.command)
            if not pymammotion_command:
                raise Exception(f"Unknown command: {command.command}")
            
            # Execute command with parameters if provided
            if command.parameters:
                result = await cloud_device.queue_command(pymammotion_command, **command.parameters)
            else:
                result = await cloud_device.queue_command(pymammotion_command)
            
            # Clear device cache after command
            if device_name in self.device_cache:
                del self.device_cache[device_name]
            
            return True
            
        except SetupException as e:
            error_code, iot_id = e.args
            self.logger.error(f"SetupException: code={error_code}, iot_id={iot_id}")
            
            if error_code == 29003:  # identityId is blank
                # Try to re-establish session
                await self._refresh_cloud_session(device_name)
                # Retry command
                return await self.execute_command(device_name, command)
            else:
                raise
                
        except Exception as e:
            self.logger.error(f"Command execution failed: {str(e)}")
            raise
            
    async def get_device_history(self, device_name: str, hours: int = 24) -> List[MowingHistory]:
        """Get device operation history.
        
        Args:
            device_name: Name of the device
            hours: Number of hours of history to retrieve
            
        Returns:
            List of mowing history entries
        """
        device = self._get_device(device_name)
        
        # This would typically query historical data from the cloud
        # For now, return empty list as placeholder
        # TODO: Implement actual history retrieval from PyMammotion
        return []
        
    async def get_mowing_zones(self, device_name: str) -> List[MowingZone]:
        """Get configured mowing zones for a device.
        
        Args:
            device_name: Name of the device
            
        Returns:
            List of mowing zones
        """
        device = self._get_device(device_name)
        
        # TODO: Implement zone retrieval from PyMammotion
        # This would get the configured zones/areas from the device
        return []
        
    async def update_device_settings(self, device_name: str, settings: MowerSettings) -> bool:
        """Update device settings.
        
        Args:
            device_name: Name of the device
            settings: New settings to apply
            
        Returns:
            True if settings updated successfully
        """
        device = self._get_device(device_name)
        cloud_device = device.cloud()
        
        if not cloud_device:
            raise Exception("Cloud device not available")
        
        # TODO: Implement settings update via PyMammotion
        # This would send configuration commands to the device
        return True
        
    async def get_device_diagnostics(self, device_name: str) -> Dict[str, Any]:
        """Get device diagnostics information.
        
        Args:
            device_name: Name of the device
            
        Returns:
            Dictionary containing diagnostic information
        """
        device = self._get_device(device_name)
        status = await self.get_device_status(device_name, use_cache=False)
        
        diagnostics = {
            "device_name": device_name,
            "online": status.online,
            "battery": {
                "level": status.battery_level,
                "charging": status.charging_state > 0
            },
            "blade": {
                "status": status.blade_status,
                "runtime_hours": 0  # TODO: Get from device
            },
            "connectivity": {
                "cloud": device.has_cloud(),
                "bluetooth": device.has_ble(),
                "mqtt_connected": device.cloud().mqtt.is_connected() if device.has_cloud() else False
            },
            "firmware_version": "Unknown",  # TODO: Get from device
            "last_error": None,  # TODO: Get error history
            "maintenance_due": False  # TODO: Calculate based on usage
        }
        
        return diagnostics
        
    async def stream_device_updates(self, device_name: str, callback: Any) -> None:
        """Stream real-time device updates.
        
        Args:
            device_name: Name of the device
            callback: Async callback function to receive updates
        """
        device = self._get_device(device_name)
        
        # TODO: Implement real-time update streaming
        # This would subscribe to device state changes and call the callback
        pass
        
    # Private helper methods
    
    def _get_session(self, session_id: str) -> MowerSession:
        """Get session by ID or raise exception."""
        if session_id not in self.active_sessions:
            raise Exception("Invalid or expired session")
        return self.active_sessions[session_id]
        
    def _get_device(self, device_name: str) -> MammotionMixedDeviceManager:
        """Get device by name or raise exception."""
        device = self.mammotion.get_device_by_name(device_name)
        if not device:
            raise Exception(f"Device '{device_name}' not found")
        return device
        
    def _create_session(self, account: str, password: str, devices: List[str]) -> str:
        """Create a new session."""
        session_id = f"{account}_{datetime.now().timestamp()}"
        session = MowerSession(
            session_id=session_id,
            account=account,
            password=password,  # Store encrypted in production
            devices=devices,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        self.active_sessions[session_id] = session
        return session_id
        
    async def _establish_cloud_connection(self, cloud_client: CloudIOTGateway, country_code: str) -> None:
        """Establish cloud connection sequence."""
        await self.exponential_backoff(
            lambda: cloud_client.get_region(country_code),
            max_retries=3,
            initial_delay=2.0
        )
        await asyncio.sleep(0.5)
        
        await self.exponential_backoff(
            lambda: cloud_client.connect(),
            max_retries=3,
            initial_delay=2.0
        )
        await asyncio.sleep(0.5)
        
        await self.exponential_backoff(
            lambda: cloud_client.login_by_oauth(country_code),
            max_retries=3,
            initial_delay=2.0
        )
        await asyncio.sleep(0.5)
        
        await self.exponential_backoff(
            lambda: cloud_client.aep_handle(),
            max_retries=3,
            initial_delay=2.0
        )
        await asyncio.sleep(0.5)
        
        await self.exponential_backoff(
            lambda: cloud_client.session_by_auth_code(),
            max_retries=3,
            initial_delay=2.0
        )
        await asyncio.sleep(0.5)
        
        await self.exponential_backoff(
            lambda: cloud_client.get_all_error_codes(),
            max_retries=3,
            initial_delay=2.0
        )
        
    async def _create_mqtt_client(self, cloud_client: CloudIOTGateway) -> MammotionCloud:
        """Create MQTT client for cloud communication."""
        if not cloud_client.session_by_authcode_response or not cloud_client.session_by_authcode_response.data:
            raise Exception("No session response received")
            
        if not cloud_client.session_by_authcode_response.data.identityId:
            raise Exception("identityId is missing from session response")
            
        mqtt_client = MammotionCloud(MammotionMQTT(
            region_id=cloud_client.region_response.data.regionId,
            product_key=cloud_client.aep_response.data.productKey,
            device_name=cloud_client.aep_response.data.deviceName,
            device_secret=cloud_client.aep_response.data.deviceSecret,
            iot_token=cloud_client.session_by_authcode_response.data.iotToken,
            client_id=cloud_client.client_id,
            cloud_client=cloud_client
        ), cloud_client=cloud_client)
        
        mqtt_client.connect_async()
        return mqtt_client
        
    async def _create_device_managers(
        self,
        cloud_client: CloudIOTGateway,
        mqtt_client: MammotionCloud
    ) -> List[str]:
        """Create device managers for all available devices."""
        if not cloud_client.devices_by_account_response or not cloud_client.devices_by_account_response.data:
            return []
            
        device_names = []
        for device in cloud_client.devices_by_account_response.data.data:
            if device.deviceName.startswith(("Luba-", "Yuka-")):
                mixed_device = self.mammotion.device_manager.get_device(device.deviceName)
                if mixed_device is None:
                    # Create new device
                    mixed_device = MammotionMixedDeviceManager(
                        name=device.deviceName,
                        iot_id=device.iotId,
                        cloud_client=cloud_client,
                        mammotion_http=cloud_client.mammotion_http,
                        cloud_device=device,
                        mqtt=mqtt_client,
                        preference=ConnectionPreference.WIFI,
                    )
                    mixed_device.mower_state.mower_state.product_key = device.productKey
                    mixed_device.mower_state.mower_state.model = (
                        device.productName if device.productModel is None else device.productModel
                    )
                    
                    # Disable automatic sync initially
                    if hasattr(mixed_device, 'cloud'):
                        cloud_device = mixed_device.cloud()
                        if cloud_device:
                            cloud_device.stopped = True
                    
                    self.mammotion.device_manager.add_device(mixed_device)
                else:
                    # Update existing device
                    if mixed_device.cloud() is None:
                        mixed_device.add_cloud(mqtt=mqtt_client)
                    else:
                        mixed_device.replace_mqtt(mqtt_client)
                
                device_names.append(device.deviceName)
                
        return device_names
        
    async def _ensure_device_communication(self, device_name: str) -> None:
        """Ensure device communication is established."""
        device = self._get_device(device_name)
        cloud_device = device.cloud()
        
        if not cloud_device:
            raise Exception("Cloud device not available")
            
        # Check if already set up
        for session in self.active_sessions.values():
            if device_name in session.devices and session.communication_setup.get(device_name, False):
                return
                
        # Enable the device and send sync commands
        cloud_device.stopped = False
        
        sync_commands = [
            ("send_todev_ble_sync", {"sync_type": 3}),
            ("get_report_cfg_stop", {}),
            ("get_report_cfg", {}),
            ("read_and_set_rtk_paring_code", {"op": 1}),
            ("send_todev_ble_sync", {"sync_type": 3}),
            ("read_and_set_rtk_paring_code", {"op": 1}),
        ]
        
        for cmd, params in sync_commands:
            await self.exponential_backoff(
                lambda: cloud_device.queue_command(cmd, **params),
                max_retries=3,
                initial_delay=2.0
            )
            await asyncio.sleep(1)
            
        # Mark as set up
        for session in self.active_sessions.values():
            if device_name in session.devices:
                if not hasattr(session, 'communication_setup'):
                    session.communication_setup = {}
                session.communication_setup[device_name] = True
                break
                
    async def _refresh_cloud_session(self, device_name: str) -> None:
        """Refresh cloud session for a device."""
        device = self._get_device(device_name)
        
        # Find the session containing this device
        session = None
        for s in self.active_sessions.values():
            if device_name in s.devices:
                session = s
                break
                
        if not session:
            raise Exception("No active session found for device")
            
        # Re-authenticate
        await self.authenticate_user(session.account, session.password)
