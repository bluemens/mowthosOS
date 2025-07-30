"""Cluster engine for geographic computations and neighbor detection."""

from typing import List, Optional, Tuple, Dict, Any
import csv
import numpy as np
import os
import sys
import logging

# Add Mowthos-Cluster-Logic to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../Mowthos-Cluster-Logic'))

from sklearn.neighbors import BallTree
from ...models.schemas import Address
from ...core.config import settings

# Import from Mowthos-Cluster-Logic
from app.services.cluster_engine import (
    ADDRESS_CSV, HOST_HOMES_CSV, NEIGHBOR_HOMES_CSV,
    EARTH_RADIUS_M, RADIUS_METERS, RADIUS_RADIANS
)

logger = logging.getLogger(__name__)

class ClusterEngine:
    """Engine for geographic clustering computations."""
    
    def __init__(self):
        """Initialize the cluster engine."""
        self.all_addresses: List[Dict[str, Any]] = []
        self.host_homes: List[Dict[str, Any]] = []
        self.neighbor_homes: List[Dict[str, Any]] = []
        self.ball_tree: Optional[BallTree] = None
        self.address_csv_path = os.path.join(
            os.path.dirname(__file__), 
            '../../../Mowthos-Cluster-Logic/',
            ADDRESS_CSV
        )
        
    async def load_address_data(self) -> None:
        """Load address data from CSV files."""
        try:
            # Load all addresses
            if os.path.exists(self.address_csv_path):
                with open(self.address_csv_path, 'r') as f:
                    reader = csv.DictReader(f)
                    self.all_addresses = list(reader)
                logger.info(f"Loaded {len(self.all_addresses)} addresses from CSV")
            else:
                logger.warning(f"Address CSV not found at {self.address_csv_path}")
                self.all_addresses = []
            
            # Build BallTree for efficient neighbor search
            if self.all_addresses:
                await self._build_ball_tree()
                
        except Exception as e:
            logger.error(f"Failed to load address data: {str(e)}")
            raise
            
    async def find_neighbors_within_radius(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float
    ) -> List[Address]:
        """Find all addresses within specified radius.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_meters: Search radius in meters
            
        Returns:
            List of addresses within radius
        """
        if not self.ball_tree:
            logger.warning("BallTree not initialized, loading address data...")
            await self.load_address_data()
            
        if not self.ball_tree:
            return []
            
        # Convert radius to radians
        radius_radians = radius_meters / EARTH_RADIUS_M
        
        # Query the BallTree
        center_radians = np.radians([[latitude, longitude]])
        indices = self.ball_tree.query_radius(center_radians, r=radius_radians)[0]
        
        # Convert results to Address objects
        neighbors = []
        for idx in indices:
            addr_data = self.all_addresses[idx]
            try:
                address = Address(
                    address_id=f"addr_{idx}",
                    street=addr_data.get('address', ''),
                    city=addr_data.get('city', ''),
                    state=addr_data.get('state', ''),
                    zip_code=addr_data.get('zip', ''),
                    latitude=float(addr_data.get('latitude', 0)),
                    longitude=float(addr_data.get('longitude', 0))
                )
                
                # Skip the center point itself
                if address.latitude != latitude or address.longitude != longitude:
                    neighbors.append(address)
                    
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid address data at index {idx}: {str(e)}")
                continue
                
        logger.info(f"Found {len(neighbors)} neighbors within {radius_meters}m radius")
        return neighbors
        
    async def calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate distance between two points in meters.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        # Haversine formula
        lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
        lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return EARTH_RADIUS_M * c
        
    async def find_clusters_near_point(
        self,
        latitude: float,
        longitude: float,
        search_radius_km: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Find existing clusters near a point.
        
        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            search_radius_km: Search radius in kilometers
            
        Returns:
            List of clusters with distance information
        """
        # Load host homes (cluster centers)
        host_homes_path = os.path.join(
            os.path.dirname(__file__),
            '../../../Mowthos-Cluster-Logic/',
            HOST_HOMES_CSV
        )
        
        clusters = []
        
        if os.path.exists(host_homes_path):
            with open(host_homes_path, 'r') as f:
                reader = csv.DictReader(f)
                for host in reader:
                    try:
                        host_lat = float(host.get('latitude', 0))
                        host_lon = float(host.get('longitude', 0))
                        
                        distance = await self.calculate_distance(
                            latitude, longitude, host_lat, host_lon
                        )
                        
                        if distance <= search_radius_km * 1000:
                            clusters.append({
                                "address": host.get('address', ''),
                                "city": host.get('city', ''),
                                "state": host.get('state', ''),
                                "latitude": host_lat,
                                "longitude": host_lon,
                                "distance_m": distance
                            })
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Invalid host home data: {str(e)}")
                        continue
                        
        return sorted(clusters, key=lambda x: x['distance_m'])
        
    async def validate_cluster_formation(
        self,
        host_address: Address,
        neighbor_addresses: List[Address]
    ) -> Dict[str, Any]:
        """Validate if addresses can form a valid cluster.
        
        Args:
            host_address: The host home address
            neighbor_addresses: List of potential neighbor addresses
            
        Returns:
            Validation results with details
        """
        validation = {
            "valid": True,
            "issues": [],
            "max_distance": 0,
            "min_distance": float('inf'),
            "average_distance": 0
        }
        
        if not neighbor_addresses:
            validation["valid"] = False
            validation["issues"].append("No neighbor addresses provided")
            return validation
            
        # Check distances from host
        distances = []
        for neighbor in neighbor_addresses:
            distance = await self.calculate_distance(
                host_address.latitude,
                host_address.longitude,
                neighbor.latitude,
                neighbor.longitude
            )
            distances.append(distance)
            
            if distance > RADIUS_METERS:
                validation["valid"] = False
                validation["issues"].append(
                    f"Neighbor at {neighbor.street} is too far ({distance:.0f}m > {RADIUS_METERS}m)"
                )
                
        if distances:
            validation["max_distance"] = max(distances)
            validation["min_distance"] = min(distances)
            validation["average_distance"] = sum(distances) / len(distances)
            
        # Check minimum cluster size
        total_members = 1 + len(neighbor_addresses)  # Host + neighbors
        if total_members < 3:
            validation["valid"] = False
            validation["issues"].append(f"Cluster too small ({total_members} < 3 minimum)")
            
        # Check maximum cluster size
        if total_members > 5:
            validation["valid"] = False
            validation["issues"].append(f"Cluster too large ({total_members} > 5 maximum)")
            
        return validation
        
    async def optimize_cluster_assignment(
        self,
        addresses: List[Address],
        max_clusters: Optional[int] = None
    ) -> List[List[Address]]:
        """Optimize assignment of addresses to clusters.
        
        Args:
            addresses: List of addresses to cluster
            max_clusters: Maximum number of clusters to create
            
        Returns:
            List of clusters (each cluster is a list of addresses)
        """
        if not addresses:
            return []
            
        # Simple greedy clustering algorithm
        clusters = []
        unassigned = addresses.copy()
        
        while unassigned and (max_clusters is None or len(clusters) < max_clusters):
            # Pick a random unassigned address as new cluster center
            center_idx = 0  # Could randomize this
            center = unassigned.pop(center_idx)
            cluster = [center]
            
            # Find nearby addresses
            to_remove = []
            for i, addr in enumerate(unassigned):
                distance = await self.calculate_distance(
                    center.latitude, center.longitude,
                    addr.latitude, addr.longitude
                )
                
                if distance <= RADIUS_METERS and len(cluster) < 5:
                    cluster.append(addr)
                    to_remove.append(i)
                    
            # Remove assigned addresses
            for i in reversed(to_remove):
                unassigned.pop(i)
                
            # Only keep clusters with minimum size
            if len(cluster) >= 3:
                clusters.append(cluster)
            else:
                # Return addresses to unassigned pool
                unassigned.extend(cluster)
                
        return clusters
        
    # Private helper methods
    
    async def _build_ball_tree(self) -> None:
        """Build BallTree index for efficient spatial queries."""
        if not self.all_addresses:
            logger.warning("No addresses loaded, cannot build BallTree")
            return
            
        # Extract coordinates and convert to radians
        coords = []
        for addr in self.all_addresses:
            try:
                lat = float(addr.get('latitude', 0))
                lon = float(addr.get('longitude', 0))
                coords.append([lat, lon])
            except (ValueError, KeyError):
                # Skip invalid entries
                continue
                
        if coords:
            coords_radians = np.radians(coords)
            self.ball_tree = BallTree(coords_radians, metric='haversine')
            logger.info(f"Built BallTree with {len(coords)} addresses")
        else:
            logger.warning("No valid coordinates found for BallTree")