"""
FastAPI microservice for Mammotion robotic mower control.

This service provides a REST API interface to the PyMammotion library,
allowing remote control of Mammotion robotic mowers.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from pymammotion.mammotion.devices.mammotion import Mammotion
from pymammotion.data.model.enums import ConnectionPreference
from pymammotion.utility.constant.device_constant import WorkMode, device_mode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Mammotion Mower Control API",
    description="REST API for controlling Mammotion robotic mowers",
    version="1.0.0"
)

# Pydantic models for request/response
class LoginRequest(BaseModel):
    account: str = Field(..., description="Mammotion account email/username")
    password: str = Field(..., description="Account password")
    device_name: Optional[str] = Field(None, description="Specific device name to connect to")

class LoginResponse(BaseModel):
    success: bool
    message: str
    device_name: Optional[str] = None
    session_id: Optional[str] = None

class MowerStatus(BaseModel):
    device_name: str
    online: bool
    work_mode: str
    work_mode_code: int
    battery_level: int
    charging_state: int
    blade_status: bool
    location: Optional[Dict[str, Any]] = None
    work_progress: Optional[int] = None
    work_area: Optional[int] = None
    last_updated: datetime

class CommandRequest(BaseModel):
    device_name: str = Field(..., description="Name of the device to control")

class CommandResponse(BaseModel):
    success: bool
    message: str
    command_sent: str

# Session manager for maintaining user sessions
class MammotionSessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.mammotion = Mammotion()
    
    def create_session(self, account: str, device_name: Optional[str] = None) -> str:
        """Create a new session for a user."""
        session_id = f"{account}_{datetime.now().timestamp()}"
        self.sessions[session_id] = {
            "account": account,
            "device_name": device_name,
            "created_at": datetime.now()
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

# Global session manager
session_manager = MammotionSessionManager()

def get_session_manager() -> MammotionSessionManager:
    """Dependency to get session manager."""
    return session_manager

async def get_mammotion_instance() -> Mammotion:
    """Dependency to get Mammotion instance."""
    return session_manager.mammotion

@app.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Login to Mammotion cloud and initialize device connection.
    
    This endpoint authenticates with the Mammotion cloud service and
    establishes a connection to the user's mower devices.
    """
    try:
        logger.info(f"Login attempt for account: {request.account}")
        
        # Login to Mammotion cloud
        await mammotion.login_and_initiate_cloud(request.account, request.password)
        
        # Get available devices
        devices = mammotion.device_manager.devices
        
        if not devices:
            raise HTTPException(status_code=404, detail="No devices found for this account")
        
        # If specific device requested, verify it exists
        target_device = None
        if request.device_name:
            target_device = mammotion.get_device_by_name(request.device_name)
            if not target_device:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Device '{request.device_name}' not found"
                )
        else:
            # Use first available device
            target_device = list(devices.values())[0]
            request.device_name = target_device.name
        
        # Create session
        session_id = session_manager.create_session(request.account, request.device_name)
        
        logger.info(f"Login successful for account: {request.account}, device: {request.device_name}")
        
        return LoginResponse(
            success=True,
            message="Login successful",
            device_name=request.device_name,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"Login failed for account {request.account}: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Login failed: {str(e)}")

@app.get("/status", response_model=MowerStatus)
async def get_mower_status(
    device_name: str,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Get the current status of a mower device.
    
    Returns detailed information about the mower's current state,
    including work mode, battery level, and location.
    """
    try:
        # Get device
        device = mammotion.get_device_by_name(device_name)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_name}' not found")
        
        # Get mower state
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
        
        return MowerStatus(
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
        
    except Exception as e:
        logger.error(f"Failed to get status for device {device_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.post("/start-mow", response_model=CommandResponse)
async def start_mowing(
    request: CommandRequest,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Start mowing operation.
    
    Sends a command to the mower to begin its mowing task.
    """
    try:
        logger.info(f"Starting mowing for device: {request.device_name}")
        
        # Send start job command
        result = await mammotion.send_command(request.device_name, "start_job")
        
        return CommandResponse(
            success=True,
            message="Mowing started successfully",
            command_sent="start_job"
        )
        
    except Exception as e:
        logger.error(f"Failed to start mowing for device {request.device_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start mowing: {str(e)}")

@app.post("/stop-mow", response_model=CommandResponse)
async def stop_mowing(
    request: CommandRequest,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Stop mowing operation.
    
    Sends a command to the mower to stop its current mowing task.
    """
    try:
        logger.info(f"Stopping mowing for device: {request.device_name}")
        
        # Send cancel job command
        result = await mammotion.send_command(request.device_name, "cancel_job")
        
        return CommandResponse(
            success=True,
            message="Mowing stopped successfully",
            command_sent="cancel_job"
        )
        
    except Exception as e:
        logger.error(f"Failed to stop mowing for device {request.device_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop mowing: {str(e)}")

@app.post("/return-to-dock", response_model=CommandResponse)
async def return_to_dock(
    request: CommandRequest,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Send mower back to charging dock.
    
    Commands the mower to return to its charging station.
    """
    try:
        logger.info(f"Sending device {request.device_name} to dock")
        
        # Send return to dock command
        result = await mammotion.send_command(request.device_name, "return_to_dock")
        
        return CommandResponse(
            success=True,
            message="Mower returning to dock",
            command_sent="return_to_dock"
        )
        
    except Exception as e:
        logger.error(f"Failed to send device {request.device_name} to dock: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to return to dock: {str(e)}")

@app.post("/pause-mowing", response_model=CommandResponse)
async def pause_mowing(
    request: CommandRequest,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Pause the current mowing operation.
    
    Temporarily pauses the mower's current task.
    """
    try:
        logger.info(f"Pausing mowing for device: {request.device_name}")
        
        # Send pause command
        result = await mammotion.send_command(request.device_name, "pause_execute_task")
        
        return CommandResponse(
            success=True,
            message="Mowing paused successfully",
            command_sent="pause_execute_task"
        )
        
    except Exception as e:
        logger.error(f"Failed to pause mowing for device {request.device_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to pause mowing: {str(e)}")

@app.post("/resume-mowing", response_model=CommandResponse)
async def resume_mowing(
    request: CommandRequest,
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    Resume a paused mowing operation.
    
    Resumes the mower's previously paused task.
    """
    try:
        logger.info(f"Resuming mowing for device: {request.device_name}")
        
        # Send resume command
        result = await mammotion.send_command(request.device_name, "resume_execute_task")
        
        return CommandResponse(
            success=True,
            message="Mowing resumed successfully",
            command_sent="resume_execute_task"
        )
        
    except Exception as e:
        logger.error(f"Failed to resume mowing for device {request.device_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resume mowing: {str(e)}")

@app.get("/devices")
async def list_devices(
    mammotion: Mammotion = Depends(get_mammotion_instance)
):
    """
    List all available devices for the current session.
    
    Returns a list of all mower devices that are available.
    """
    try:
        devices = mammotion.device_manager.devices
        
        device_list = []
        for device_name, device in devices.items():
            device_info = {
                "name": device_name,
                "iot_id": device.iot_id,
                "preference": str(device.preference),
                "has_cloud": device.has_cloud(),
                "has_ble": device.has_ble()
            }
            device_list.append(device_info)
        
        return {"devices": device_list}
        
    except Exception as e:
        logger.error(f"Failed to list devices: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list devices: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the API service.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Mammotion Mower Control API"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 