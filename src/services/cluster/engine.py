"""Cluster engine for geographic computations and neighbor detection."""

from typing import List, Optional, Tuple, Dict, Any
import csv
import numpy as np
import os
import logging
import time
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, text
from sklearn.neighbors import BallTree
from geopy.distance import geodesic

from ...models.schemas import Address
from ...models.database.users import User, UserRole, UserAddress
from ...models.database.clusters import Cluster, ClusterStatus
from ...core.config import settings
from .mapbox import MapboxService

logger = logging.getLogger(__name__)

# Constants from Mowthos-Cluster-Logic
EARTH_RADIUS_M = 6371000
RADIUS_METERS = 80
RADIUS_RADIANS = RADIUS_METERS / EARTH_RADIUS_M

# CSV file paths for addressable market discovery
ADDRESS_CSV = os.path.join(os.path.dirname(__file__), '../../../Mowthos-Cluster-Logic/olmsted_addresses_559xx.csv')

class ClusterEngine:
    """Engine for geographic clustering computations."""
    
    def __init__(self):
        """Initialize the cluster engine."""
        self.all_addresses: List[Dict[str, Any]] = []
        self.ball_tree: Optional[BallTree] = None
        self.mapbox_service = MapboxService(settings.MAPBOX_ACCESS_TOKEN)
        
    async def load_address_data(self) -> None:
        """Load address data from CSV files for addressable market discovery."""
        try:
            if os.path.exists(ADDRESS_CSV):
                self.all_addresses = load_addresses_from_csv(ADDRESS_CSV)
                logger.info(f"Loaded {len(self.all_addresses)} addresses from CSV for market discovery")
            else:
                logger.warning(f"Address CSV not found at {ADDRESS_CSV}")
                self.all_addresses = []
            
            # Build BallTree for efficient neighbor search
            if self.all_addresses:
                await self._build_ball_tree()
                
        except Exception as e:
            logger.error(f"Failed to load address data: {str(e)}")
            raise

    async def register_host_home_db(
        self,
        db: AsyncSession,
        user_id: UUID,
        address_id: UUID,
        mapbox_service: MapboxService
    ) -> Dict[str, Any]:
        """
        Register a host home in the database and create a cluster.
        
        Args:
            db: Database session
            user_id: ID of the user registering as host
            address_id: ID of the user's address
            mapbox_service: Mapbox service for geocoding
            
        Returns:
            Dictionary with registration results
        """
        try:
            from sqlalchemy import select
            # 1. Verify user role
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user or user.role != UserRole.HOST:
                return {"success": False, "message": "User must be HOST role to register as host"}
            
            # 2. Verify address ownership
            stmt = select(UserAddress).where(
                UserAddress.id == address_id,
                UserAddress.user_id == user_id
            )
            result = await db.execute(stmt)
            address = result.scalar_one_or_none()
            if not address:
                return {"success": False, "message": "Address not found or not owned by user"}
            
            # 3. Check if user already hosts a cluster
            stmt = select(Cluster).where(
                Cluster.host_user_id == user_id,
                Cluster.status.in_([ClusterStatus.ACTIVE, ClusterStatus.PENDING])
            )
            result = await db.execute(stmt)
            existing_cluster = result.scalar_one_or_none()
            if existing_cluster:
                return {"success": False, "message": "User already hosts a cluster"}
            
            # 4. Validate address with Mapbox
            address_str = f"{address.address_line1}, {address.city}, {address.state_province}"
            validated = await mapbox_service.validate_address(address_str)
            if not validated:
                return {"success": False, "message": "Invalid address"}
            
            # 5. Update address with geocoding data
            address.latitude = str(validated['latitude'])
            address.longitude = str(validated['longitude'])
            address.verified = True
            address.geocoded_at = datetime.now()
            
            # 6. Create cluster
            cluster = Cluster(
                host_user_id=user_id,
                host_address_id=address_id,
                center_latitude=validated['latitude'],
                center_longitude=validated['longitude'],
                name=f"{address.address_line1} Cluster",
                status=ClusterStatus.PENDING,
                max_members=5,
                current_members=0
            )
            db.add(cluster)
            await db.commit()
            
            logger.info(f"Created cluster {cluster.id} for host {user_id} at {address_str}")
            
            return {
                "success": True,
                "cluster_id": str(cluster.id),
                "cluster_name": cluster.name,
                "address": address_str,
                "latitude": validated['latitude'],
                "longitude": validated['longitude']
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to register host: {str(e)}")
            return {"success": False, "message": f"Registration failed: {str(e)}"}

    async def discover_existing_neighbors_for_host_db(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        mapbox_service: MapboxService,
        radius_meters: int = 80
    ) -> List[Dict[str, Any]]:
        """
        Find existing platform users who could join the cluster.
        Returns verified user addresses within radius.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            mapbox_service: Mapbox service for road-aware filtering
            radius_meters: Search radius in meters
            
        Returns:
            List of qualified neighbor addresses with user information
        """
        try:
            # Get cluster details
            cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
            if not cluster:
                logger.warning(f"Cluster {cluster_id} not found")
                return []
            
            # Find verified user addresses within radius
            query = text("""
                SELECT 
                    ua.id,
                    ua.address_line1,
                    ua.city,
                    ua.state_province,
                    ua.postal_code,
                    ua.latitude,
                    ua.longitude,
                    u.id as user_id,
                    u.role,
                    u.display_name,
                    u.email
                FROM user_addresses ua
                JOIN users u ON ua.user_id = u.id
                WHERE ua.verified = true
                AND ua.id != :host_address_id
                AND u.role IN ('neighbor', 'user')
                AND ST_DWithin(
                    ST_MakePoint(ua.longitude::float, ua.latitude::float),
                    ST_MakePoint(:host_lon::float, :host_lat::float),
                    :radius_meters
                )
            """)
            
            candidates = db.execute(query, {
                "host_address_id": cluster.host_address_id,
                "host_lat": cluster.center_latitude,
                "host_lon": cluster.center_longitude,
                "radius_meters": radius_meters
            }).fetchall()
            
            # Road-aware filtering
            qualified_neighbors = []
            for candidate in candidates:
                try:
                    is_accessible = await mapbox_service.is_accessible_without_crossing_road(
                        (cluster.center_latitude, cluster.center_longitude),
                        (float(candidate.latitude), float(candidate.longitude))
                    )
                    
                    if is_accessible:
                        qualified_neighbors.append({
                            "address_id": str(candidate.id),
                            "user_id": str(candidate.user_id),
                            "address": f"{candidate.address_line1}, {candidate.city}, {candidate.state_province}",
                            "user_role": candidate.role,
                            "user_name": candidate.display_name,
                            "user_email": candidate.email,
                            "latitude": float(candidate.latitude),
                            "longitude": float(candidate.longitude),
                            "source": "platform_user"
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid coordinates for address {candidate.id}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(qualified_neighbors)} qualified existing neighbors for cluster {cluster_id}")
            return qualified_neighbors
            
        except Exception as e:
            logger.error(f"Failed to discover existing neighbors: {str(e)}")
            return []

    async def discover_addressable_market_for_host_db(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        mapbox_service: MapboxService,
        radius_meters: int = 80
    ) -> Dict[str, Any]:
        """
        Find total addressable market size using CSV data.
        Returns market statistics and potential addresses.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            mapbox_service: Mapbox service for road-aware filtering
            radius_meters: Search radius in meters
            
        Returns:
            Dictionary with market analysis
        """
        try:
            # Get cluster details
            cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
            if not cluster:
                return {"total_addresses": 0, "qualified_addresses": 0, "potential_addresses": []}
            
            # Load address data if not already loaded
            if not self.all_addresses:
                await self.load_address_data()
            
            if not self.all_addresses:
                logger.warning("No address data available for market discovery")
                return {"total_addresses": 0, "qualified_addresses": 0, "potential_addresses": []}
            
            # Build BallTree for all candidates
            candidate_coords = np.array([[c['latitude'], c['longitude']] for c in self.all_addresses])
            candidate_coords_rad = np.radians(candidate_coords)
            tree = BallTree(candidate_coords_rad, metric='haversine')
            
            # Find addresses within radius
            host_latlon_rad = np.radians([[cluster.center_latitude, cluster.center_longitude]])
            idxs = tree.query_radius(host_latlon_rad, r=RADIUS_RADIANS)[0]
            
            # Road-aware filtering
            qualified_addresses = []
            for idx in idxs:
                candidate = self.all_addresses[idx]
                
                # Skip if this is the host address
                host_address_str = f"{cluster.host_address.address_line1}, {cluster.host_address.city}, {cluster.host_address.state_province}"
                if candidate['full_address'].lower() == host_address_str.lower():
                    continue
                
                # Road-aware check
                try:
                    is_accessible = await mapbox_service.is_accessible_without_crossing_road(
                        (cluster.center_latitude, cluster.center_longitude),
                        (candidate['latitude'], candidate['longitude'])
                    )
                    
                    if is_accessible:
                        qualified_addresses.append({
                            "address": candidate['full_address'],
                            "latitude": candidate['latitude'],
                            "longitude": candidate['longitude'],
                            "source": "addressable_market"
                        })
                except Exception as e:
                    logger.warning(f"Failed road-aware check for {candidate['full_address']}: {str(e)}")
                    continue
            
            market_coverage = (len(qualified_addresses) / len(self.all_addresses)) * 100 if self.all_addresses else 0
            
            logger.info(f"Market analysis for cluster {cluster_id}: {len(qualified_addresses)} qualified out of {len(self.all_addresses)} total addresses")
            
            return {
                "total_addresses": len(self.all_addresses),
                "addresses_within_radius": len(idxs),
                "qualified_addresses": len(qualified_addresses),
                "potential_addresses": qualified_addresses,
                "market_coverage_percentage": market_coverage
            }
            
        except Exception as e:
            logger.error(f"Failed to discover addressable market: {str(e)}")
            return {"total_addresses": 0, "qualified_addresses": 0, "potential_addresses": []}

    async def analyze_cluster_market_db(
        self,
        db: AsyncSession,
        cluster_id: UUID,
        mapbox_service: MapboxService,
        radius_meters: int = 80
    ) -> Dict[str, Any]:
        """
        Complete market analysis for a cluster.
        Returns both existing platform users and total addressable market.
        
        Args:
            db: Database session
            cluster_id: ID of the cluster
            mapbox_service: Mapbox service for road-aware filtering
            radius_meters: Search radius in meters
            
        Returns:
            Dictionary with complete market analysis
        """
        try:
            # Get existing platform users
            existing_neighbors = await self.discover_existing_neighbors_for_host_db(
                db, cluster_id, mapbox_service, radius_meters
            )
            
            # Get total addressable market
            market_analysis = await self.discover_addressable_market_for_host_db(
                db, cluster_id, mapbox_service, radius_meters
            )
            
            # Calculate insights
            adoption_rate = (len(existing_neighbors) / market_analysis["qualified_addresses"]) * 100 if market_analysis["qualified_addresses"] > 0 else 0
            growth_potential = market_analysis["qualified_addresses"] - len(existing_neighbors)
            
            return {
                "cluster_id": str(cluster_id),
                "existing_platform_users": {
                    "count": len(existing_neighbors),
                    "users": existing_neighbors
                },
                "addressable_market": {
                    "total_addresses": market_analysis["total_addresses"],
                    "qualified_addresses": market_analysis["qualified_addresses"],
                    "market_coverage_percentage": market_analysis["market_coverage_percentage"],
                    "potential_addresses": market_analysis["potential_addresses"]
                },
                "market_insights": {
                    "platform_adoption_rate": adoption_rate,
                    "growth_potential": growth_potential,
                    "radius_meters": radius_meters
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze cluster market: {str(e)}")
            return {
                "cluster_id": str(cluster_id),
                "existing_platform_users": {"count": 0, "users": []},
                "addressable_market": {"total_addresses": 0, "qualified_addresses": 0, "potential_addresses": []},
                "market_insights": {"platform_adoption_rate": 0, "growth_potential": 0, "radius_meters": radius_meters}
            }

    async def find_qualified_host_for_neighbor_db(
        self,
        db: AsyncSession,
        neighbor_address_id: UUID,
        mapbox_service: MapboxService,
        radius_meters: int = 80
    ) -> List[Dict[str, Any]]:
        """
        For a given neighbor address, find all registered host homes for which this address qualifies as a neighbor.
        
        Args:
            db: Database session
            neighbor_address_id: ID of the neighbor's address
            mapbox_service: Mapbox service for road-aware filtering
            radius_meters: Search radius in meters
            
        Returns:
            List of qualified host clusters
        """
        try:
            # Get neighbor address details
            neighbor_address = db.query(UserAddress).filter(
                UserAddress.id == neighbor_address_id,
                UserAddress.verified == True
            ).first()
            if not neighbor_address:
                logger.warning(f"Neighbor address {neighbor_address_id} not found or not verified")
                return []
            
            # Find all active clusters within radius
            query = text("""
                SELECT 
                    c.id as cluster_id,
                    c.name,
                    c.center_latitude,
                    c.center_longitude,
                    c.max_members,
                    c.current_members,
                    c.status,
                    ua.address_line1,
                    ua.city,
                    ua.state_province,
                    u.display_name as host_name
                FROM clusters c
                JOIN user_addresses ua ON c.host_address_id = ua.id
                JOIN users u ON c.host_user_id = u.id
                WHERE c.status = 'active'
                AND c.is_accepting_members = true
                AND c.current_members < c.max_members
                AND ST_DWithin(
                    ST_MakePoint(ua.longitude::float, ua.latitude::float),
                    ST_MakePoint(:neighbor_lon::float, :neighbor_lat::float),
                    :radius_meters
                )
            """)
            
            candidates = db.execute(query, {
                "neighbor_lat": float(neighbor_address.latitude),
                "neighbor_lon": float(neighbor_address.longitude),
                "radius_meters": radius_meters
            }).fetchall()
            
            # Road-aware filtering
            qualified_hosts = []
            for candidate in candidates:
                try:
                    is_accessible = await mapbox_service.is_accessible_without_crossing_road(
                        (candidate.center_latitude, candidate.center_longitude),
                        (float(neighbor_address.latitude), float(neighbor_address.longitude))
                    )
                    
                    if is_accessible:
                        qualified_hosts.append({
                            "cluster_id": str(candidate.cluster_id),
                            "cluster_name": candidate.name,
                            "host_address": f"{candidate.address_line1}, {candidate.city}, {candidate.state_province}",
                            "host_name": candidate.host_name,
                            "max_members": candidate.max_members,
                            "current_members": candidate.current_members,
                            "available_slots": candidate.max_members - candidate.current_members,
                            "status": candidate.status
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid coordinates for cluster {candidate.cluster_id}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(qualified_hosts)} qualified hosts for neighbor address {neighbor_address_id}")
            return qualified_hosts
            
        except Exception as e:
            logger.error(f"Failed to find qualified hosts: {str(e)}")
            return []

    async def find_neighbors_within_radius(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float
    ) -> List[Address]:
        """Find all addresses within specified radius."""
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
        """Calculate distance between two points."""
        distance = geodesic((lat1, lon1), (lat2, lon2)).meters
        return distance

    async def _build_ball_tree(self) -> None:
        """Build BallTree for efficient neighbor search."""
        if not self.all_addresses:
            return
            
        try:
            # Extract coordinates
            coords = []
            for addr in self.all_addresses:
                try:
                    lat = float(addr.get('latitude', 0))
                    lon = float(addr.get('longitude', 0))
                    if lat != 0 and lon != 0:
                        coords.append([lat, lon])
                except (ValueError, TypeError):
                    continue
            
            if coords:
                # Convert to radians for BallTree
                coords_radians = np.radians(coords)
                self.ball_tree = BallTree(coords_radians, metric='haversine')
                logger.info(f"Built BallTree with {len(coords)} valid coordinates")
            else:
                logger.warning("No valid coordinates found for BallTree")
                
        except Exception as e:
            logger.error(f"Failed to build BallTree: {str(e)}")
            self.ball_tree = None

# Helper function for loading CSV data (kept for addressable market discovery)
def load_addresses_from_csv(path: str) -> List[dict]:
    """Load addresses from a CSV file, returning a list of dicts with full address and lat/lon."""
    addresses = []
    try:
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle different CSV structures
                if 'state' in row:
                    state = row['state']
                else:
                    state = 'MN'  # Default to MN for Rochester addresses
                
                # Compose full address
                full_address = f"{row['address']}, {row['city']}, {state}"
                addresses.append({
                    'full_address': full_address,
                    'address': row['address'],
                    'city': row['city'],
                    'state': state,
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude'])
                })
    except Exception as e:
        logger.error(f"Failed to load addresses from CSV {path}: {str(e)}")
        return []
    
    return addresses