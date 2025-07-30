"""Cluster service for managing geographic clustering and neighbor detection."""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import json
import os
import sys
import logging

# Add Mowthos-Cluster-Logic to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../Mowthos-Cluster-Logic'))

from sqlalchemy.orm import Session
from sqlalchemy import and_
from geopy.distance import geodesic

from ..base import BaseService
from .engine import ClusterEngine
from .mapbox import MapboxService
from ...models.schemas import (
    Cluster, Address, HostRegistration, NeighborJoinRequest,
    ClusterAssignment, ClusterStats, RouteOptimization
)
from ...core.config import settings
from ...core.database import get_db

# Import from Mowthos-Cluster-Logic
from app.models import User as MowthosUser, Cluster as MowthosCluster, LawnBoundary
from app.schemas import HostRegistrationRequest, JoinClusterRequest, ClusterAssignmentResponse
from app.services.cluster_service import ClusterService as MowthosClusterService
from app.services.cluster_engine import ClusterEngine as MowthosClusterEngine

logger = logging.getLogger(__name__)

class ClusterService(BaseService):
    """Service for managing geographic clustering of homes."""
    
    def __init__(self):
        """Initialize the cluster service."""
        super().__init__("cluster")
        self.engine = ClusterEngine()
        self.mapbox = MapboxService(settings.mapbox_access_token)
        
        # Initialize wrapped Mowthos services
        self.mowthos_service = MowthosClusterService()
        self.mowthos_engine = MowthosClusterEngine()
        
        # Configuration
        self.max_cluster_capacity = 5
        self.min_cluster_capacity = 3
        self.max_distance_meters = 80  # 80m radius for neighbors
        self.min_battery_threshold = 20  # Minimum battery % to join work
        
    async def initialize(self) -> None:
        """Initialize the cluster service."""
        await super().initialize()
        
        # Ensure CSV files exist
        self._ensure_csv_files()
        
        # Load address data
        await self.engine.load_address_data()
        
    async def register_host(self, address: Address, user_id: int) -> Cluster:
        """Register a new host home and create cluster.
        
        Args:
            address: Address of the host home
            user_id: ID of the user registering as host
            
        Returns:
            Created cluster information
        """
        try:
            # Check if address is already registered
            existing = await self._check_existing_registration(address)
            if existing:
                raise Exception("Address is already registered")
            
            # Validate address with Mapbox
            validated = await self.mapbox.validate_address(
                address.street,
                address.city,
                address.state,
                address.zip_code
            )
            
            if not validated:
                raise Exception("Invalid address")
            
            # Create cluster
            cluster_id = f"cluster_{user_id}_{datetime.now().timestamp()}"
            cluster = Cluster(
                cluster_id=cluster_id,
                name=f"{address.street} Cluster",
                host_user_id=user_id,
                host_address=address,
                members=[user_id],
                max_capacity=self.max_cluster_capacity,
                created_at=datetime.now(),
                is_active=True
            )
            
            # Find potential neighbors
            neighbors = await self.find_neighbors(cluster_id)
            cluster.potential_neighbors = len(neighbors)
            
            # Store cluster (would go to database in production)
            await self._store_cluster(cluster)
            
            self.logger.info(f"Created cluster {cluster_id} for host at {address.street}")
            return cluster
            
        except Exception as e:
            self.logger.error(f"Failed to register host: {str(e)}")
            raise
            
    async def find_neighbors(self, cluster_id: str) -> List[Address]:
        """Find qualified neighbors for a cluster.
        
        Args:
            cluster_id: ID of the cluster
            
        Returns:
            List of neighbor addresses
        """
        cluster = await self._get_cluster(cluster_id)
        if not cluster:
            raise Exception("Cluster not found")
        
        # Get host coordinates
        host_lat = cluster.host_address.latitude
        host_lon = cluster.host_address.longitude
        
        # Use cluster engine to find neighbors
        neighbors = await self.engine.find_neighbors_within_radius(
            host_lat,
            host_lon,
            self.max_distance_meters
        )
        
        # Filter out homes across roads
        filtered_neighbors = []
        for neighbor in neighbors:
            # Check if road exists between host and neighbor
            has_road = await self.mapbox.check_road_between_points(
                host_lat, host_lon,
                neighbor.latitude, neighbor.longitude
            )
            
            if not has_road:
                filtered_neighbors.append(neighbor)
                
        self.logger.info(f"Found {len(filtered_neighbors)} qualified neighbors for cluster {cluster_id}")
        return filtered_neighbors
        
    async def join_cluster(self, cluster_id: str, address: Address, user_id: int) -> ClusterAssignment:
        """Join an existing cluster as a neighbor.
        
        Args:
            cluster_id: ID of the cluster to join
            address: Address of the neighbor
            user_id: ID of the user joining
            
        Returns:
            Cluster assignment information
        """
        cluster = await self._get_cluster(cluster_id)
        if not cluster:
            raise Exception("Cluster not found")
        
        # Check capacity
        if len(cluster.members) >= cluster.max_capacity:
            raise Exception("Cluster is at full capacity")
        
        # Validate address is within range
        distance = geodesic(
            (cluster.host_address.latitude, cluster.host_address.longitude),
            (address.latitude, address.longitude)
        ).meters
        
        if distance > self.max_distance_meters:
            raise Exception(f"Address is too far from cluster host ({distance:.0f}m)")
        
        # Check for road between addresses
        has_road = await self.mapbox.check_road_between_points(
            cluster.host_address.latitude, cluster.host_address.longitude,
            address.latitude, address.longitude
        )
        
        if has_road:
            raise Exception("Cannot join cluster - road detected between properties")
        
        # Add to cluster
        cluster.members.append(user_id)
        
        assignment = ClusterAssignment(
            cluster_id=cluster_id,
            user_id=user_id,
            role="neighbor",
            assigned_at=datetime.now(),
            distance_to_host=distance
        )
        
        await self._update_cluster(cluster)
        
        self.logger.info(f"User {user_id} joined cluster {cluster_id}")
        return assignment
        
    async def optimize_routes(self, cluster_id: str) -> RouteOptimization:
        """Optimize mowing routes for cluster efficiency.
        
        Args:
            cluster_id: ID of the cluster
            
        Returns:
            Optimized route information
        """
        cluster = await self._get_cluster(cluster_id)
        if not cluster:
            raise Exception("Cluster not found")
        
        # Get all member addresses
        member_addresses = await self._get_member_addresses(cluster)
        
        # Calculate optimal route using traveling salesman approach
        route = await self._calculate_optimal_route(member_addresses)
        
        # Estimate time and battery usage
        total_distance = 0
        for i in range(len(route) - 1):
            distance = geodesic(
                (route[i].latitude, route[i].longitude),
                (route[i+1].latitude, route[i+1].longitude)
            ).meters
            total_distance += distance
        
        # Rough estimates
        travel_time_minutes = (total_distance / 1000) * 15  # 15 min per km travel
        mowing_time_minutes = len(member_addresses) * 45  # 45 min per lawn
        total_time_minutes = travel_time_minutes + mowing_time_minutes
        battery_usage_percent = min(100, total_time_minutes * 0.5)  # 0.5% per minute
        
        optimization = RouteOptimization(
            cluster_id=cluster_id,
            route_order=[addr.address_id for addr in route],
            total_distance_m=total_distance,
            estimated_time_minutes=total_time_minutes,
            estimated_battery_usage=battery_usage_percent,
            optimized_at=datetime.now()
        )
        
        self.logger.info(f"Optimized route for cluster {cluster_id}: {total_distance}m, {total_time_minutes}min")
        return optimization
        
    async def get_cluster_stats(self, cluster_id: str) -> ClusterStats:
        """Get statistics for a cluster.
        
        Args:
            cluster_id: ID of the cluster
            
        Returns:
            Cluster statistics
        """
        cluster = await self._get_cluster(cluster_id)
        if not cluster:
            raise Exception("Cluster not found")
        
        # Calculate stats
        member_count = len(cluster.members)
        potential_savings = member_count * 50  # $50 average savings per member
        
        # Get route optimization if available
        route = await self._get_latest_route(cluster_id)
        
        stats = ClusterStats(
            cluster_id=cluster_id,
            member_count=member_count,
            capacity_utilization=member_count / cluster.max_capacity,
            average_distance_m=route.total_distance_m / member_count if route else 0,
            estimated_monthly_savings=potential_savings,
            total_area_covered_sqm=member_count * 500,  # Assume 500 sqm average lawn
            active_mowers=0,  # Would check actual mower status
            completed_sessions_month=0,  # Would query history
            last_updated=datetime.now()
        )
        
        return stats
        
    async def suggest_clusters(self, address: Address) -> List[Cluster]:
        """Suggest nearby clusters for an address.
        
        Args:
            address: Address to find clusters for
            
        Returns:
            List of nearby clusters with availability
        """
        # Find all clusters within range
        nearby_clusters = []
        
        # This would query all active clusters from database
        # For now, return empty list
        # TODO: Implement actual cluster search
        
        return nearby_clusters
        
    async def calculate_coverage(self, addresses: List[Address]) -> Dict[str, Any]:
        """Calculate coverage area and statistics for addresses.
        
        Args:
            addresses: List of addresses to analyze
            
        Returns:
            Coverage statistics
        """
        if not addresses:
            return {"total_area": 0, "clusters_possible": 0}
        
        # Group addresses into potential clusters
        clusters = await self._group_into_clusters(addresses)
        
        total_area = len(addresses) * 500  # Assume 500 sqm per address
        
        coverage = {
            "total_addresses": len(addresses),
            "total_area_sqm": total_area,
            "clusters_possible": len(clusters),
            "average_cluster_size": len(addresses) / len(clusters) if clusters else 0,
            "coverage_efficiency": 0.8,  # 80% efficiency estimate
            "unserviceable_addresses": 0  # Addresses too isolated
        }
        
        return coverage
        
    # Private helper methods
    
    def _ensure_csv_files(self) -> None:
        """Ensure required CSV files exist."""
        # This is handled by the Mowthos-Cluster-Logic engine
        from app.services.cluster_engine import ensure_host_homes_csv, ensure_neighbor_homes_csv
        ensure_host_homes_csv()
        ensure_neighbor_homes_csv()
        
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