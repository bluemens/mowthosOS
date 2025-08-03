"""
Cluster management endpoints for MowthosOS API.
"""

from typing import Dict, Optional, Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_cluster_service
from src.core.auth import get_current_active_user
from src.models.database.users import User, UserRole
from src.models.database.clusters import ClusterStatus
from src.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/clusters", tags=["clusters"])

# Request/Response Models
class CreateClusterRequest(BaseModel):
    """Request model for creating a cluster."""
    address_id: UUID = Field(..., description="ID of the user's address to use as host")

class CreateClusterResponse(BaseModel):
    """Response model for cluster creation."""
    success: bool
    cluster_id: Optional[str] = None
    cluster_name: Optional[str] = None
    host_address: Optional[str] = None
    market_analysis: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class JoinClusterRequest(BaseModel):
    """Request model for joining a cluster."""
    address_id: UUID = Field(..., description="ID of the user's address")

class JoinClusterResponse(BaseModel):
    """Response model for joining a cluster."""
    success: bool
    cluster_id: Optional[str] = None
    user_id: Optional[str] = None
    member_id: Optional[str] = None
    join_order: Optional[int] = None
    status: Optional[str] = None
    message: Optional[str] = None

class LeaveClusterResponse(BaseModel):
    """Response model for leaving a cluster."""
    success: bool
    cluster_id: Optional[str] = None
    user_id: Optional[str] = None
    left_at: Optional[str] = None
    message: Optional[str] = None

class ClusterDetailsResponse(BaseModel):
    """Response model for cluster details."""
    success: bool
    cluster_id: Optional[str] = None
    cluster_name: Optional[str] = None
    host_user_id: Optional[str] = None
    host_name: Optional[str] = None
    host_address: Optional[str] = None
    status: Optional[str] = None
    current_members: Optional[int] = None
    max_members: Optional[int] = None
    is_accepting_members: Optional[bool] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    service_radius_meters: Optional[int] = None
    created_at: Optional[str] = None
    members: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None

class MarketAnalysisResponse(BaseModel):
    """Response model for market analysis."""
    success: bool
    cluster_id: Optional[str] = None
    existing_platform_users: Optional[Dict[str, Any]] = None
    addressable_market: Optional[Dict[str, Any]] = None
    market_insights: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# Helper function to verify Host role
async def get_current_host_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Verify the current user is a Host"""
    if current_user.role != UserRole.HOST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Host users can create clusters"
        )
    return current_user

# Helper function to verify Neighbor role
async def get_current_neighbor_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Verify the current user is a Neighbor"""
    if current_user.role not in [UserRole.NEIGHBOR, UserRole.USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Neighbor users can join clusters"
        )
    return current_user

@router.post("/create", response_model=CreateClusterResponse)
async def create_cluster(
    request: CreateClusterRequest,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_host_user)
):
    """Create a new cluster for a host user."""
    try:
        result = await cluster_service.create_cluster(
            db=db,
            user_id=current_user.id,
            address_id=request.address_id
        )
        
        if result.get('success'):
            return CreateClusterResponse(
                success=True,
                cluster_id=result.get('cluster_id'),
                cluster_name=result.get('cluster_name'),
                host_address=result.get('host_address'),
                market_analysis=result.get('market_analysis')
            )
        else:
            return CreateClusterResponse(
                success=False,
                message=result.get('message', 'Failed to create cluster')
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create cluster: {str(e)}"
        )

@router.post("/{cluster_id}/join", response_model=JoinClusterResponse)
async def join_cluster(
    cluster_id: UUID,
    request: JoinClusterRequest,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_neighbor_user)
):
    """Join a cluster."""
    try:
        result = await cluster_service.join_cluster(
            db=db,
            cluster_id=cluster_id,
            user_id=current_user.id,
            address_id=request.address_id
        )
        
        if result.get('success'):
            return JoinClusterResponse(
                success=True,
                cluster_id=result.get('cluster_id'),
                user_id=result.get('user_id'),
                member_id=result.get('member_id'),
                join_order=result.get('join_order'),
                status=result.get('status')
            )
        else:
            return JoinClusterResponse(
                success=False,
                message=result.get('message', 'Failed to join cluster')
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to join cluster: {str(e)}"
        )

@router.post("/{cluster_id}/leave", response_model=LeaveClusterResponse)
async def leave_cluster(
    cluster_id: UUID,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_active_user)
):
    """Leave a cluster."""
    try:
        result = await cluster_service.leave_cluster(
            db=db,
            cluster_id=cluster_id,
            user_id=current_user.id
        )
        
        if result.get('success'):
            return LeaveClusterResponse(
                success=True,
                cluster_id=result.get('cluster_id'),
                user_id=result.get('user_id'),
                left_at=result.get('left_at')
            )
        else:
            return LeaveClusterResponse(
                success=False,
                message=result.get('message', 'Failed to leave cluster')
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to leave cluster: {str(e)}"
        )

@router.get("/{cluster_id}", response_model=ClusterDetailsResponse)
async def get_cluster_details(
    cluster_id: UUID,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed information about a cluster."""
    try:
        result = await cluster_service.get_cluster_details(
            db=db,
            cluster_id=cluster_id
        )
        
        if result.get('success'):
            return ClusterDetailsResponse(
                success=True,
                cluster_id=result.get('cluster_id'),
                cluster_name=result.get('cluster_name'),
                host_user_id=result.get('host_user_id'),
                host_name=result.get('host_name'),
                host_address=result.get('host_address'),
                status=result.get('status'),
                current_members=result.get('current_members'),
                max_members=result.get('max_members'),
                is_accepting_members=result.get('is_accepting_members'),
                center_latitude=result.get('center_latitude'),
                center_longitude=result.get('center_longitude'),
                service_radius_meters=result.get('service_radius_meters'),
                created_at=result.get('created_at'),
                members=result.get('members')
            )
        else:
            return ClusterDetailsResponse(
                success=False,
                message=result.get('message', 'Failed to get cluster details')
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cluster details: {str(e)}"
        )

@router.get("/{cluster_id}/market-analysis", response_model=MarketAnalysisResponse)
async def get_cluster_market_analysis(
    cluster_id: UUID,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_active_user)
):
    """Get market analysis for a cluster."""
    try:
        result = await cluster_service.analyze_cluster_market(
            db=db,
            cluster_id=cluster_id
        )
        
        return MarketAnalysisResponse(
            success=True,
            cluster_id=result.get('cluster_id'),
            existing_platform_users=result.get('existing_platform_users'),
            addressable_market=result.get('addressable_market'),
            market_insights=result.get('market_insights')
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get market analysis: {str(e)}"
        )

@router.get("/{cluster_id}/existing-neighbors")
async def get_existing_neighbors(
    cluster_id: UUID,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_active_user)
):
    """Get existing platform users who could join the cluster."""
    try:
        neighbors = await cluster_service.discover_existing_neighbors(
            db=db,
            cluster_id=cluster_id
        )
        
        return {
            "success": True,
            "cluster_id": str(cluster_id),
            "neighbors": neighbors,
            "count": len(neighbors)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get existing neighbors: {str(e)}"
        )

@router.get("/{cluster_id}/addressable-market")
async def get_addressable_market(
    cluster_id: UUID,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_active_user)
):
    """Get addressable market analysis for a cluster."""
    try:
        market = await cluster_service.discover_addressable_market(
            db=db,
            cluster_id=cluster_id
        )
        
        return {
            "success": True,
            "cluster_id": str(cluster_id),
            "market_analysis": market
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get addressable market: {str(e)}"
        )

@router.get("/neighbor/{address_id}/qualified-clusters")
async def get_qualified_clusters_for_neighbor(
    address_id: UUID,
    db: Session = Depends(get_db),
    cluster_service = Depends(get_cluster_service),
    current_user: User = Depends(get_current_active_user)
):
    """Find qualified clusters for a neighbor address."""
    try:
        clusters = await cluster_service.find_qualified_clusters_for_neighbor(
            db=db,
            neighbor_address_id=address_id
        )
        
        return {
            "success": True,
            "address_id": str(address_id),
            "qualified_clusters": clusters,
            "count": len(clusters)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find qualified clusters: {str(e)}"
        ) 