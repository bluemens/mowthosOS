"""Cluster management API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime, time

from src.core.database import get_db
from src.core.auth import get_current_active_user
from src.models.database.users import User
from src.models.database.clusters import Cluster, ClusterMember, ClusterSchedule
from src.services.cluster import ClusterService
from src.services.mower import MowerService

router = APIRouter(prefix="/api/v1/clusters", tags=["clusters"])


# Request/Response Models
class CreateClusterRequest(BaseModel):
    """Request to create a new cluster"""
    name: str = Field(..., min_length=3, max_length=100)
    address: str = Field(..., description="Host home address")
    max_members: int = Field(default=5, ge=2, le=10)
    description: Optional[str] = None


class JoinClusterRequest(BaseModel):
    """Request to join an existing cluster"""
    cluster_code: str = Field(..., description="Unique cluster invitation code")
    address: str = Field(..., description="Member's home address")


class UpdateScheduleRequest(BaseModel):
    """Request to update cluster schedule"""
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: str = Field(..., description="Start time in HH:MM format")
    duration_hours: float = Field(..., ge=0.5, le=8)
    enabled: bool = True


class ClusterResponse(BaseModel):
    """Cluster information response"""
    id: str
    name: str
    code: str
    host_id: str
    host_address: str
    member_count: int
    max_members: int
    status: str
    created_at: datetime
    next_scheduled_run: Optional[datetime]


class ClusterMemberResponse(BaseModel):
    """Cluster member information"""
    id: str
    user_id: str
    user_name: str
    address: str
    role: str
    joined_at: datetime
    contribution_minutes: int
    device_name: Optional[str]
    device_status: Optional[str]


# Endpoints
@router.post("/create", response_model=ClusterResponse)
async def create_cluster(
    request: CreateClusterRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new cluster as host"""
    cluster_service = ClusterService()
    
    try:
        # Check if user is already a host
        existing_host = await db.query(Cluster).filter(
            Cluster.host_id == current_user.id
        ).first()
        
        if existing_host:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already hosting a cluster"
            )
        
        # Create cluster
        cluster = await cluster_service.create_cluster(
            host_user=current_user,
            name=request.name,
            address=request.address,
            max_members=request.max_members,
            description=request.description
        )
        
        return ClusterResponse(
            id=str(cluster.id),
            name=cluster.name,
            code=cluster.code,
            host_id=str(cluster.host_id),
            host_address=cluster.host_address,
            member_count=1,  # Host counts as a member
            max_members=cluster.max_members,
            status=cluster.status,
            created_at=cluster.created_at,
            next_scheduled_run=None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create cluster: {str(e)}"
        )


@router.post("/join", response_model=dict)
async def join_cluster(
    request: JoinClusterRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Join an existing cluster as a neighbor"""
    cluster_service = ClusterService()
    
    try:
        # Find cluster by code
        cluster = await db.query(Cluster).filter(
            Cluster.code == request.cluster_code,
            Cluster.status == "active"
        ).first()
        
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid cluster code or cluster is not active"
            )
        
        # Check if already a member
        existing_member = await db.query(ClusterMember).filter(
            ClusterMember.cluster_id == cluster.id,
            ClusterMember.user_id == current_user.id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already a member of this cluster"
            )
        
        # Join cluster
        member = await cluster_service.join_cluster(
            user=current_user,
            cluster=cluster,
            address=request.address
        )
        
        return {
            "message": "Successfully joined cluster",
            "cluster_id": str(cluster.id),
            "member_id": str(member.id),
            "role": member.role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to join cluster: {str(e)}"
        )


@router.get("/my-clusters", response_model=List[ClusterResponse])
async def get_my_clusters(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all clusters where user is a member"""
    # Get clusters where user is host
    hosted_clusters = await db.query(Cluster).filter(
        Cluster.host_id == current_user.id
    ).all()
    
    # Get clusters where user is member
    memberships = await db.query(ClusterMember).filter(
        ClusterMember.user_id == current_user.id
    ).all()
    
    cluster_ids = [m.cluster_id for m in memberships]
    member_clusters = await db.query(Cluster).filter(
        Cluster.id.in_(cluster_ids)
    ).all() if cluster_ids else []
    
    # Combine and format response
    all_clusters = hosted_clusters + member_clusters
    
    responses = []
    for cluster in all_clusters:
        member_count = await db.query(ClusterMember).filter(
            ClusterMember.cluster_id == cluster.id
        ).count()
        
        responses.append(ClusterResponse(
            id=str(cluster.id),
            name=cluster.name,
            code=cluster.code,
            host_id=str(cluster.host_id),
            host_address=cluster.host_address,
            member_count=member_count,
            max_members=cluster.max_members,
            status=cluster.status,
            created_at=cluster.created_at,
            next_scheduled_run=cluster.next_scheduled_run
        ))
    
    return responses


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster_details(
    cluster_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get cluster details"""
    # Verify user is member of cluster
    is_member = await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == cluster_id,
        ClusterMember.user_id == current_user.id
    ).first()
    
    cluster = await db.query(Cluster).filter(
        Cluster.id == cluster_id
    ).first()
    
    if not cluster or (not is_member and cluster.host_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found or access denied"
        )
    
    member_count = await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == cluster.id
    ).count()
    
    return ClusterResponse(
        id=str(cluster.id),
        name=cluster.name,
        code=cluster.code,
        host_id=str(cluster.host_id),
        host_address=cluster.host_address,
        member_count=member_count,
        max_members=cluster.max_members,
        status=cluster.status,
        created_at=cluster.created_at,
        next_scheduled_run=cluster.next_scheduled_run
    )


@router.get("/{cluster_id}/members", response_model=List[ClusterMemberResponse])
async def get_cluster_members(
    cluster_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all members of a cluster"""
    # Verify access
    cluster = await db.query(Cluster).filter(
        Cluster.id == cluster_id
    ).first()
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )
    
    # Check if user has access
    is_member = await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == cluster_id,
        ClusterMember.user_id == current_user.id
    ).first()
    
    if not is_member and cluster.host_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get members
    members = await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == cluster_id
    ).all()
    
    # Get mower service for device status
    mower_service = MowerService()
    
    responses = []
    for member in members:
        # Get user info
        user = await db.query(User).filter(
            User.id == member.user_id
        ).first()
        
        # Get device status if available
        device_status = None
        if member.device_name:
            try:
                status = await mower_service.get_device_status(member.device_name)
                device_status = status.work_mode
            except:
                device_status = "offline"
        
        responses.append(ClusterMemberResponse(
            id=str(member.id),
            user_id=str(member.user_id),
            user_name=user.display_name or user.email,
            address=member.address,
            role=member.role,
            joined_at=member.joined_at,
            contribution_minutes=member.contribution_minutes,
            device_name=member.device_name,
            device_status=device_status
        ))
    
    return responses


@router.put("/{cluster_id}/schedule")
async def update_cluster_schedule(
    cluster_id: str,
    schedules: List[UpdateScheduleRequest],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update cluster mowing schedule (host only)"""
    # Verify user is host
    cluster = await db.query(Cluster).filter(
        Cluster.id == cluster_id,
        Cluster.host_id == current_user.id
    ).first()
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only cluster host can update schedule"
        )
    
    # Delete existing schedules
    await db.query(ClusterSchedule).filter(
        ClusterSchedule.cluster_id == cluster_id
    ).delete()
    
    # Create new schedules
    for schedule in schedules:
        new_schedule = ClusterSchedule(
            cluster_id=cluster.id,
            day_of_week=schedule.day_of_week,
            start_time=datetime.strptime(schedule.start_time, "%H:%M").time(),
            duration_hours=schedule.duration_hours,
            enabled=schedule.enabled
        )
        db.add(new_schedule)
    
    await db.commit()
    
    return {
        "message": "Schedule updated successfully",
        "schedules_count": len(schedules)
    }


@router.delete("/{cluster_id}/leave")
async def leave_cluster(
    cluster_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Leave a cluster (members only, not host)"""
    cluster = await db.query(Cluster).filter(
        Cluster.id == cluster_id
    ).first()
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )
    
    if cluster.host_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host cannot leave cluster. Delete cluster instead."
        )
    
    # Remove membership
    member = await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == cluster_id,
        ClusterMember.user_id == current_user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this cluster"
        )
    
    await db.delete(member)
    await db.commit()
    
    return {"message": "Successfully left cluster"}


@router.delete("/{cluster_id}")
async def delete_cluster(
    cluster_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a cluster (host only)"""
    cluster = await db.query(Cluster).filter(
        Cluster.id == cluster_id,
        Cluster.host_id == current_user.id
    ).first()
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only cluster host can delete cluster"
        )
    
    # Delete all related data
    await db.query(ClusterSchedule).filter(
        ClusterSchedule.cluster_id == cluster_id
    ).delete()
    
    await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == cluster_id
    ).delete()
    
    await db.delete(cluster)
    await db.commit()
    
    return {"message": "Cluster deleted successfully"}