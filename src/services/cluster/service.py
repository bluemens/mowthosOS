"""Cluster service for managing geographic clustering and neighbor detection."""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_
from geopy.distance import geodesic

from ..base import BaseService
from .engine import ClusterEngine, register_host_home, register_neighbor_home, discover_neighbors_for_host, find_qualified_host_for_neighbor, ensure_host_homes_csv, ensure_neighbor_homes_csv
from .mapbox import MapboxService
from ...models.schemas import (
    Cluster, Address, HostRegistration, NeighborJoinRequest,
    ClusterAssignment, ClusterStats, RouteOptimization
)
from ...core.config import settings
from ...core.database import get_db

logger = logging.getLogger(__name__)

class ClusterService(BaseService):
    """Service for managing geographic clustering of homes."""
    
    def __init__(self):
        """Initialize the cluster service."""
        super().__init__("cluster")
        self.engine = ClusterEngine()
        self.mapbox = MapboxService(settings.mapbox_access_token)
        
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
            
            # Use function to register host home
            host_result = register_host_home(
                address.street,
                address.city,
                address.state,
                validated.get('latitude'),
                validated.get('longitude')
            )
            
            if not host_result.get('success'):
                raise Exception(f"Failed to register host: {host_result.get('message')}")
            
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
        try:
            # Get cluster details
            cluster = await self._get_cluster(cluster_id)
            if not cluster:
                return []
            
            # Use engine to discover neighbors
            host_address = f"{cluster.host_address.street}, {cluster.host_address.city}, {cluster.host_address.state}"
            neighbor_addresses = discover_neighbors_for_host(host_address)
            
            # Convert to Address objects
            neighbors = []
            for addr_str in neighbor_addresses:
                # Parse address string (format: "street, city, state")
                parts = addr_str.split(', ')
                if len(parts) >= 3:
                    address = Address(
                        address_id=f"neighbor_{len(neighbors)}",
                        street=parts[0],
                        city=parts[1],
                        state=parts[2],
                        zip_code=parts[3] if len(parts) > 3 else "",
                        latitude=0.0,  # Would be geocoded in production
                        longitude=0.0
                    )
                    neighbors.append(address)
            
            self.logger.info(f"Found {len(neighbors)} neighbors for cluster {cluster_id}")
            return neighbors
            
        except Exception as e:
            self.logger.error(f"Failed to find neighbors: {str(e)}")
            return []
            
    async def join_cluster(self, cluster_id: str, address: Address, user_id: int) -> ClusterAssignment:
        """Join a cluster.
        
        Args:
            cluster_id: ID of the cluster to join
            address: Address of the joining user
            user_id: ID of the joining user
            
        Returns:
            Cluster assignment information
        """
        try:
            # Check if cluster exists and has capacity
            cluster = await self._get_cluster(cluster_id)
            if not cluster:
                raise Exception("Cluster not found")
            
            if len(cluster.members) >= cluster.max_capacity:
                raise Exception("Cluster is at maximum capacity")
            
            # Use engine to register neighbor home
            neighbor_result = register_neighbor_home(
                address.street,
                address.city,
                address.state
            )
            
            if not neighbor_result.get('success'):
                raise Exception(f"Failed to register neighbor: {neighbor_result.get('message')}")
            
            # Find qualified host for this neighbor
            neighbor_address = f"{address.street}, {address.city}, {address.state}"
            qualified_hosts = find_qualified_host_for_neighbor(neighbor_address)
            
            # Check if our target cluster is in the qualified hosts
            target_cluster_found = False
            for host_addr in qualified_hosts:
                if cluster_id in host_addr:  # Simple check - would be more sophisticated in production
                    target_cluster_found = True
                    break
            
            if not target_cluster_found:
                raise Exception("Address is not within range of this cluster")
            
            # Add user to cluster
            cluster.members.append(user_id)
            await self._update_cluster(cluster)
            
            assignment = ClusterAssignment(
                cluster_id=cluster_id,
                user_id=user_id,
                assigned_at=datetime.now(),
                status="active"
            )
            
            self.logger.info(f"User {user_id} joined cluster {cluster_id}")
            return assignment
            
        except Exception as e:
            self.logger.error(f"Failed to join cluster: {str(e)}")
            raise
            
    async def optimize_routes(self, cluster_id: str) -> RouteOptimization:
        """Optimize routes for a cluster.
        
        Args:
            cluster_id: ID of the cluster
            
        Returns:
            Route optimization results
        """
        try:
            # Get cluster and member addresses
            cluster = await self._get_cluster(cluster_id)
            if not cluster:
                raise Exception("Cluster not found")
            
            addresses = await self._get_member_addresses(cluster)
            if not addresses:
                raise Exception("No addresses found for cluster")
            
            # Use engine for route optimization
            optimal_route = await self._calculate_optimal_route(addresses)
            
            # Calculate total distance
            total_distance = 0
            for i in range(len(optimal_route) - 1):
                distance = geodesic(
                    (optimal_route[i].latitude, optimal_route[i].longitude),
                    (optimal_route[i + 1].latitude, optimal_route[i + 1].longitude)
                ).meters
                total_distance += distance
            
            optimization = RouteOptimization(
                cluster_id=cluster_id,
                route=optimal_route,
                total_distance_meters=total_distance,
                estimated_duration_minutes=total_distance / 100,  # Rough estimate
                optimized_at=datetime.now()
            )
            
            self.logger.info(f"Optimized route for cluster {cluster_id}: {total_distance:.0f}m")
            return optimization
            
        except Exception as e:
            self.logger.error(f"Failed to optimize routes: {str(e)}")
            raise
            
    async def get_cluster_stats(self, cluster_id: str) -> ClusterStats:
        """Get cluster statistics.
        
        Args:
            cluster_id: ID of the cluster
            
        Returns:
            Cluster statistics
        """
        try:
            cluster = await self._get_cluster(cluster_id)
            if not cluster:
                raise Exception("Cluster not found")
            
            # Get member addresses
            addresses = await self._get_member_addresses(cluster)
            
            # Calculate coverage area
            coverage_info = await self.calculate_coverage(addresses)
            
            stats = ClusterStats(
                cluster_id=cluster_id,
                member_count=len(cluster.members),
                max_capacity=cluster.max_capacity,
                coverage_area_sqm=coverage_info.get('total_area', 0),
                average_distance_km=coverage_info.get('average_distance', 0),
                efficiency_score=coverage_info.get('coverage_efficiency', 0),
                last_updated=datetime.now()
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get cluster stats: {str(e)}")
            raise
            
    async def suggest_clusters(self, address: Address) -> List[Cluster]:
        """Suggest clusters for an address.
        
        Args:
            address: Address to find clusters for
            
        Returns:
            List of suggested clusters
        """
        try:
            # Use engine to find qualified hosts
            address_str = f"{address.street}, {address.city}, {address.state}"
            qualified_hosts = find_qualified_host_for_neighbor(address_str)
            
            # Convert to cluster suggestions
            suggestions = []
            for host_addr in qualified_hosts:
                # Create a mock cluster for suggestion
                # In production, this would query actual clusters
                suggestion = Cluster(
                    cluster_id=f"suggested_{len(suggestions)}",
                    name=f"Cluster near {host_addr}",
                    host_user_id=0,  # Would be actual host ID
                    host_address=address,
                    members=[0],  # Would be actual member IDs
                    max_capacity=self.max_cluster_capacity,
                    created_at=datetime.now(),
                    is_active=True
                )
                suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Failed to suggest clusters: {str(e)}")
            return []
            
    async def calculate_coverage(self, addresses: List[Address]) -> Dict[str, Any]:
        """Calculate coverage area for addresses.
        
        Args:
            addresses: List of addresses to calculate coverage for
            
        Returns:
            Coverage information
        """
        try:
            if not addresses:
                return {
                    "total_area": 0,
                    "average_distance": 0,
                    "coverage_efficiency": 0,
                    "unserviceable_addresses": 0
                }
            
            # Calculate total area (simplified - would use actual property boundaries)
            total_area = len(addresses) * 1000  # 1000 sqm per property estimate
            
            # Calculate average distance between addresses
            total_distance = 0
            distance_count = 0
            
            for i in range(len(addresses)):
                for j in range(i + 1, len(addresses)):
                    distance = geodesic(
                        (addresses[i].latitude, addresses[i].longitude),
                        (addresses[j].latitude, addresses[j].longitude)
                    ).kilometers
                    total_distance += distance
                    distance_count += 1
            
            average_distance = total_distance / distance_count if distance_count > 0 else 0
            
            return {
                "total_area": total_area,
                "average_distance": average_distance,
                "coverage_efficiency": 0.8,  # 80% efficiency estimate
                "unserviceable_addresses": 0  # Addresses too isolated
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate coverage: {str(e)}")
            return {
                "total_area": 0,
                "average_distance": 0,
                "coverage_efficiency": 0,
                "unserviceable_addresses": 0
            }
        
    # Private helper methods
    
    def _ensure_csv_files(self) -> None:
        """Ensure required CSV files exist."""
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