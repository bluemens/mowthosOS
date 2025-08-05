"""Cluster service for managing geographic clustering and neighbor detection."""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from geopy.distance import geodesic

from ..base import BaseService
from .engine import ClusterEngine
from .mapbox import MapboxService
from ...models.schemas import (
    Cluster, Address, HostRegistration, NeighborJoinRequest,
    ClusterAssignment, ClusterStats, RouteOptimization
)
from ...models.database.users import User, UserRole, UserAddress
from ...models.database.clusters import Cluster as ClusterModel, ClusterStatus
from ...core.config import settings
from ...core.database import get_db

logger = logging.getLogger(__name__)

class ClusterService(BaseService):
    """Service for managing geographic clustering of homes."""
    
    def __init__(self):
        """Initialize the cluster service."""
        super().__init__("cluster")
        self.engine = ClusterEngine()
        # Get the actual string value from SecretStr
        mapbox_token = settings.MAPBOX_ACCESS_TOKEN.get_secret_value() if settings.MAPBOX_ACCESS_TOKEN else None
        self.mapbox = MapboxService(mapbox_token)
        
        # Configuration
        self.max_cluster_capacity = 5
        self.min_cluster_capacity = 3
        self.max_distance_meters = 80  # 80m radius for neighbors
        self.min_battery_threshold = 20  # Minimum battery % to join work
        
    async def initialize(self) -> None:
        """Initialize the cluster service."""
        await super().initialize()
        
        # Load address data for market discovery
        await self.engine.load_address_data()
        
    async def create_cluster(
        self,
        db: AsyncSession,
        user_id: UUID,
        address_id: UUID
    ) -> Dict[str, Any]:
        """Create a new cluster for a host user.
        
        Args:
            db: Database session
            user_id: ID of the user creating the cluster
            address_id: ID of the user's address to use as host
            
        Returns:
            Dictionary with cluster creation results and market analysis
        """
        try:
            # Register host and create cluster
            cluster_result = await self.engine.register_host_home_db(
                db, user_id, address_id, self.mapbox
            )
            
            if not cluster_result.get('success'):
                return cluster_result
            
            # Analyze complete market
            market_analysis = await self.engine.analyze_cluster_market_db(
                db, UUID(cluster_result['cluster_id']), self.mapbox
            )
            
            return {
                "success": True,
                "cluster_id": cluster_result['cluster_id'],
                "cluster_name": cluster_result['cluster_name'],
                "host_address": cluster_result['address'],
                "market_analysis": market_analysis
            }
            
        except Exception as e:
            logger.error(f"Failed to create cluster: {str(e)}")
            return {"success": False, "message": f"Cluster creation failed: {str(e)}"}

    async def discover_existing_neighbors(
        self,
        db: AsyncSession,
        cluster_id: UUID
    ) -> List[Dict[str, Any]]:
        """Find existing platform users who could join the cluster.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            
        Returns:
            List of qualified neighbor addresses with user information
        """
        try:
            return await self.engine.discover_existing_neighbors_for_host_db(
                db, cluster_id, self.mapbox
            )
        except Exception as e:
            logger.error(f"Failed to discover existing neighbors: {str(e)}")
            return []

    async def discover_addressable_market(
        self,
        db: AsyncSession,
        cluster_id: UUID
    ) -> Dict[str, Any]:
        """Find total addressable market size using CSV data.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            
        Returns:
            Dictionary with market analysis
        """
        try:
            return await self.engine.discover_addressable_market_for_host_db(
                db, cluster_id, self.mapbox
            )
        except Exception as e:
            logger.error(f"Failed to discover addressable market: {str(e)}")
            return {"total_addresses": 0, "qualified_addresses": 0, "potential_addresses": []}

    async def analyze_cluster_market(
        self,
        db: AsyncSession,
        cluster_id: UUID
    ) -> Dict[str, Any]:
        """Complete market analysis for a cluster.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            
        Returns:
            Dictionary with complete market analysis
        """
        try:
            return await self.engine.analyze_cluster_market_db(
                db, cluster_id, self.mapbox
            )
        except Exception as e:
            logger.error(f"Failed to analyze cluster market: {str(e)}")
            return {
                "cluster_id": str(cluster_id),
                "existing_platform_users": {"count": 0, "users": []},
                "addressable_market": {"total_addresses": 0, "qualified_addresses": 0, "potential_addresses": []},
                "market_insights": {"platform_adoption_rate": 0, "growth_potential": 0, "radius_meters": 80}
            }

    async def find_qualified_clusters_for_neighbor(
        self,
        db: AsyncSession,
        neighbor_address_id: UUID
    ) -> List[Dict[str, Any]]:
        """Find qualified clusters for a neighbor address.
        
        Args:
            db: Database session
            neighbor_address_id: ID of the neighbor's address
            
        Returns:
            List of qualified host clusters
        """
        try:
            return await self.engine.find_qualified_host_for_neighbor_db(
                db, neighbor_address_id, self.mapbox
            )
        except Exception as e:
            logger.error(f"Failed to find qualified clusters: {str(e)}")
            return []

    async def join_cluster(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        user_id: UUID,
        address_id: UUID
    ) -> Dict[str, Any]:
        """Join a cluster.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster to join
            user_id: ID of the joining user
            address_id: ID of the user's address
            
        Returns:
            Dictionary with join results
        """
        try:
            # Verify user role
            user = db.query(User).filter(User.id == user_id).first()
            if not user or user.role not in [UserRole.NEIGHBOR, UserRole.USER]:
                return {"success": False, "message": "User must be NEIGHBOR or USER role to join clusters"}
            
            # Verify address ownership
            address = db.query(UserAddress).filter(
                UserAddress.id == address_id,
                UserAddress.user_id == user_id,
                UserAddress.verified == True
            ).first()
            if not address:
                return {"success": False, "message": "Address not found, not owned by user, or not verified"}
            
            # Get cluster details
            cluster = db.query(ClusterModel).filter(ClusterModel.id == cluster_id).first()
            if not cluster:
                return {"success": False, "message": "Cluster not found"}
            
            if cluster.status != ClusterStatus.ACTIVE:
                return {"success": False, "message": "Cluster is not active"}
            
            if not cluster.is_accepting_members:
                return {"success": False, "message": "Cluster is not accepting new members"}
            
            if cluster.current_members >= cluster.max_members:
                return {"success": False, "message": "Cluster is at maximum capacity"}
            
            # Check if user is already a member
            existing_member = db.query(ClusterModel).join(
                ClusterModel.members
            ).filter(
                ClusterModel.id == cluster_id,
                ClusterModel.members.any(user_id=user_id)
            ).first()
            
            if existing_member:
                return {"success": False, "message": "User is already a member of this cluster"}
            
            # Verify the address is within range and accessible
            qualified_clusters = await self.find_qualified_clusters_for_neighbor(db, address_id)
            cluster_found = any(str(c['cluster_id']) == str(cluster_id) for c in qualified_clusters)
            
            if not cluster_found:
                return {"success": False, "message": "Address is not within range of this cluster"}
            
            # Add user to cluster
            from ...models.database.clusters import ClusterMember, MemberStatus
            
            # Get the next join order
            max_join_order = db.query(ClusterMember.join_order).filter(
                ClusterMember.cluster_id == cluster_id
            ).order_by(ClusterMember.join_order.desc()).first()
            
            next_join_order = (max_join_order[0] if max_join_order else 0) + 1
            
            member = ClusterMember(
                cluster_id=cluster_id,
                user_id=user_id,
                address_id=address_id,
                join_order=next_join_order,
                status=MemberStatus.PENDING
            )
            
            db.add(member)
            
            # Update cluster member count
            cluster.current_members += 1
            
            db.commit()
            
            logger.info(f"User {user_id} joined cluster {cluster_id}")
            
            return {
                "success": True,
                "cluster_id": str(cluster_id),
                "user_id": str(user_id),
                "member_id": str(member.id),
                "join_order": member.join_order,
                "status": member.status.value
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to join cluster: {str(e)}")
            return {"success": False, "message": f"Failed to join cluster: {str(e)}"}

    async def leave_cluster(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Leave a cluster.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster to leave
            user_id: ID of the user leaving
            
        Returns:
            Dictionary with leave results
        """
        try:
            from ...models.database.clusters import ClusterMember, MemberStatus
            
            # Find the member record
            member = db.query(ClusterMember).filter(
                ClusterMember.cluster_id == cluster_id,
                ClusterMember.user_id == user_id,
                ClusterMember.status.in_([MemberStatus.ACTIVE, MemberStatus.PENDING])
            ).first()
            
            if not member:
                return {"success": False, "message": "User is not a member of this cluster"}
            
            # Check if user is the host
            cluster = db.query(ClusterModel).filter(ClusterModel.id == cluster_id).first()
            if cluster and cluster.host_user_id == user_id:
                return {"success": False, "message": "Host cannot leave their own cluster. Transfer ownership first."}
            
            # Update member status
            member.status = MemberStatus.REMOVED
            member.left_at = datetime.now()
            
            # Update cluster member count
            cluster.current_members -= 1
            
            db.commit()
            
            logger.info(f"User {user_id} left cluster {cluster_id}")
            
            return {
                "success": True,
                "cluster_id": str(cluster_id),
                "user_id": str(user_id),
                "left_at": member.left_at.isoformat()
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to leave cluster: {str(e)}")
            return {"success": False, "message": f"Failed to leave cluster: {str(e)}"}

    async def get_cluster_details(
        self,
        db: AsyncSession,
        cluster_id: UUID
    ) -> Dict[str, Any]:
        """Get detailed information about a cluster.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            
        Returns:
            Dictionary with cluster details
        """
        try:
            cluster = db.query(ClusterModel).filter(ClusterModel.id == cluster_id).first()
            if not cluster:
                return {"success": False, "message": "Cluster not found"}
            
            # Get cluster members
            members = []
            for member in cluster.members:
                if member.status.value in ['active', 'pending']:
                    members.append({
                        "user_id": str(member.user_id),
                        "user_name": member.user.display_name,
                        "user_email": member.user.email,
                        "join_order": member.join_order,
                        "status": member.status.value,
                        "joined_at": member.joined_at.isoformat()
                    })
            
            return {
                "success": True,
                "cluster_id": str(cluster.id),
                "cluster_name": cluster.name,
                "host_user_id": str(cluster.host_user_id),
                "host_name": cluster.host_user.display_name,
                "host_address": f"{cluster.host_address.address_line1}, {cluster.host_address.city}, {cluster.host_address.state_province}",
                "status": cluster.status.value,
                "current_members": cluster.current_members,
                "max_members": cluster.max_members,
                "is_accepting_members": cluster.is_accepting_members,
                "center_latitude": cluster.center_latitude,
                "center_longitude": cluster.center_longitude,
                "service_radius_meters": cluster.service_radius_meters,
                "created_at": cluster.created_at.isoformat(),
                "members": members
            }
            
        except Exception as e:
            logger.error(f"Failed to get cluster details: {str(e)}")
            return {"success": False, "message": f"Failed to get cluster details: {str(e)}"}

            
            
    
        
    # Private helper methods (kept for backward compatibility)
    
    async def _check_existing_registration(self, address: Address) -> bool:
        """Check if address is already registered."""
        # Would query database
        # For now, return False
        return False
        
    async def _store_cluster(self, cluster: Cluster) -> None:
        """Store cluster in database."""
        # Would store in database
        # For now, just log
        self.logger.info(f"Stored cluster: {cluster.cluster_id}")
        
    async def _get_cluster(self, cluster_id: str) -> Optional[Cluster]:
        """Get cluster by ID."""
        # Would query database
        # For now, return None
        return None
        
    async def _update_cluster(self, cluster: Cluster) -> None:
        """Update cluster in database."""
        # Would update database
        self.logger.info(f"Updated cluster: {cluster.cluster_id}")
        
    async def _get_member_addresses(self, cluster: Cluster) -> List[Address]:
        """Get addresses for all cluster members."""
        # Would query user addresses from database
        # For now, return host address only
        return [cluster.host_address]
        
    async def _calculate_optimal_route(self, addresses: List[Address]) -> List[Address]:
        """Calculate optimal route through addresses."""
        # Simple nearest-neighbor algorithm
        if not addresses:
            return []
            
        route = [addresses[0]]
        remaining = addresses[1:]
        
        while remaining:
            current = route[-1]
            nearest = min(remaining, key=lambda addr: geodesic(
                (current.latitude, current.longitude),
                (addr.latitude, addr.longitude)
            ).meters)
            route.append(nearest)
            remaining.remove(nearest)
            
        return route
        
    async def _get_latest_route(self, cluster_id: str) -> Optional[RouteOptimization]:
        """Get latest route optimization for cluster."""
        # Would query database
        return None
        
    async def _group_into_clusters(self, addresses: List[Address]) -> List[List[Address]]:
        """Group addresses into potential clusters."""
        # Simple clustering algorithm
        clusters = []
        assigned = set()
        
        for i, addr in enumerate(addresses):
            if i in assigned:
                continue
                
            cluster = [addr]
            assigned.add(i)
            
            # Find nearby addresses
            for j, other in enumerate(addresses):
                if j in assigned or j == i:
                    continue
                    
                distance = geodesic(
                    (addr.latitude, addr.longitude),
                    (other.latitude, other.longitude)
                ).meters
                
                if distance <= self.max_distance_meters and len(cluster) < self.max_cluster_capacity:
                    cluster.append(other)
                    assigned.add(j)
                    
            if len(cluster) >= self.min_cluster_capacity:
                clusters.append(cluster)
                
        return clusters