"""
Mower control endpoints for MowthosOS API.
"""

from typing import Dict, Optional, Any
from fastapi import APIRouter, Depends, HTTPException
from pymammotion.mammotion.devices.mammotion import Mammotion

from src.api.dependencies import get_mower_service, get_mammotion_instance
from src.models.schemas import (
    LoginRequest, LoginResponse, MowerStatus, 
    CommandRequest, CommandResponse
)

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    mower_service = Depends(get_mower_service)
):
    """Login to Mammotion account and establish session."""
    try:
        session_id = await mower_service.authenticate_user(
            request.account, 
            request.password, 
            request.device_name
        )
        
        return LoginResponse(
            success=True,
            message="Login successful",
            device_name=request.device_name,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Login failed: {str(e)}"
        )

@router.get("/{device_name}/status", response_model=MowerStatus)
async def get_mower_status(
    device_name: str,
    mower_service = Depends(get_mower_service)
):
    """Get real-time status of a mower device."""
    try:
        status = await mower_service.get_device_status(device_name)
        return status
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to get status for {device_name}: {str(e)}"
        )

@router.post("/{device_name}/commands/start", response_model=CommandResponse)
async def start_mowing(
    device_name: str,
    mower_service = Depends(get_mower_service)
):
    """Start mowing operation for a device."""
    try:
        success = await mower_service.execute_command(device_name, "start_mow")
        return CommandResponse(
            success=success,
            message="Start mowing command sent successfully" if success else "Failed to start mowing",
            command_sent="start_mow"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to start mowing: {str(e)}"
        )

@router.post("/{device_name}/commands/stop", response_model=CommandResponse)
async def stop_mowing(
    device_name: str,
    mower_service = Depends(get_mower_service)
):
    """Stop mowing operation for a device."""
    try:
        success = await mower_service.execute_command(device_name, "stop_mow")
        return CommandResponse(
            success=success,
            message="Stop mowing command sent successfully" if success else "Failed to stop mowing",
            command_sent="stop_mow"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to stop mowing: {str(e)}"
        )

@router.post("/{device_name}/commands/return", response_model=CommandResponse)
async def return_to_dock(
    device_name: str,
    mower_service = Depends(get_mower_service)
):
    """Return device to dock."""
    try:
        success = await mower_service.execute_command(device_name, "return_to_dock")
        return CommandResponse(
            success=success,
            message="Return to dock command sent successfully" if success else "Failed to return to dock",
            command_sent="return_to_dock"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to return to dock: {str(e)}"
        )

@router.post("/{device_name}/commands/pause", response_model=CommandResponse)
async def pause_mowing(
    device_name: str,
    mower_service = Depends(get_mower_service)
):
    """Pause mowing operation for a device."""
    try:
        success = await mower_service.execute_command(device_name, "pause_mowing")
        return CommandResponse(
            success=success,
            message="Pause mowing command sent successfully" if success else "Failed to pause mowing",
            command_sent="pause_mowing"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to pause mowing: {str(e)}"
        )

@router.post("/{device_name}/commands/resume", response_model=CommandResponse)
async def resume_mowing(
    device_name: str,
    mower_service = Depends(get_mower_service)
):
    """Resume mowing operation for a device."""
    try:
        success = await mower_service.execute_command(device_name, "resume_mowing")
        return CommandResponse(
            success=success,
            message="Resume mowing command sent successfully" if success else "Failed to resume mowing",
            command_sent="resume_mowing"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to resume mowing: {str(e)}"
        )

@router.get("/devices")
async def list_devices(
    mower_service = Depends(get_mower_service)
):
    """List all available devices for the authenticated user."""
    try:
        devices = await mower_service.list_devices()
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list devices: {str(e)}"
        ) 