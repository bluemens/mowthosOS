"""Cluster engine for geographic computations and neighbor detection."""

from typing import List, Optional, Tuple, Dict, Any
import csv
import numpy as np
import os
import logging
import time

from sklearn.neighbors import BallTree
from ...models.schemas import Address
from ...core.config import settings
from .mapbox import MapboxService

logger = logging.getLogger(__name__)

# Constants from Mowthos-Cluster-Logic
EARTH_RADIUS_M = 6371000
RADIUS_METERS = 80
RADIUS_RADIANS = RADIUS_METERS / EARTH_RADIUS_M

# CSV file paths
ADDRESS_CSV = os.path.join(os.path.dirname(__file__), '../../../Mowthos-Cluster-Logic/olmsted_addresses_559xx.csv')
HOST_HOMES_CSV = os.path.join(os.path.dirname(__file__), '../../../Mowthos-Cluster-Logic/host_homes.csv')
NEIGHBOR_HOMES_CSV = os.path.join(os.path.dirname(__file__), '../../../Mowthos-Cluster-Logic/neighbor_homes.csv')

class ClusterEngine:
    """Engine for geographic clustering computations."""
    
    def __init__(self):
        """Initialize the cluster engine."""
        self.all_addresses: List[Dict[str, Any]] = []
        self.host_homes: List[Dict[str, Any]] = []
        self.neighbor_homes: List[Dict[str, Any]] = []
        self.ball_tree: Optional[BallTree] = None
        self.mapbox_service = MapboxService(settings.mapbox_access_token)
        
    async def load_address_data(self) -> None:
        """Load address data from CSV files."""
        try:
            if os.path.exists(ADDRESS_CSV):
                self.all_addresses = load_addresses_from_csv(ADDRESS_CSV)
                logger.info(f"Loaded {len(self.all_addresses)} addresses from CSV")
            else:
                logger.warning(f"Address CSV not found at {ADDRESS_CSV}")
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
        """Calculate distance between two points.
        
        Args:
            lat1: First point latitude
            lon1: First point longitude
            lat2: Second point latitude
            lon2: Second point longitude
            
        Returns:
            Distance in meters
        """
        from geopy.distance import geodesic
        
        distance = geodesic((lat1, lon1), (lat2, lon2)).meters
        return distance
        
    async def find_clusters_near_point(
        self,
        latitude: float,
        longitude: float,
        search_radius_km: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Find clusters near a point.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            search_radius_km: Search radius in kilometers
            
        Returns:
            List of nearby clusters
        """
        try:
            # Convert to address string for functions
            address_str = f"Unknown Street, Unknown City, Unknown State"
            
            # Use function to find qualified hosts
            qualified_hosts = find_qualified_host_for_neighbor(address_str)
            
            # Convert to cluster format
            clusters = []
            for host_addr in qualified_hosts:
                cluster_info = {
                    "cluster_id": f"cluster_{len(clusters)}",
                    "host_address": host_addr,
                    "distance_km": 0,  # Would calculate actual distance
                    "member_count": 0,  # Would get from database
                    "max_capacity": 5
                }
                clusters.append(cluster_info)
            
            logger.info(f"Found {len(clusters)} clusters near point ({latitude}, {longitude})")
            return clusters
            
        except Exception as e:
            logger.error(f"Failed to find clusters near point: {str(e)}")
            return []
            
    async def validate_cluster_formation(
        self,
        host_address: Address,
        neighbor_addresses: List[Address]
    ) -> Dict[str, Any]:
        """Validate if a cluster formation is valid.
        
        Args:
            host_address: Address of the host home
            neighbor_addresses: List of potential neighbor addresses
            
        Returns:
            Validation results
        """
        try:
            # Register host home
            host_result = register_host_home(
                host_address.street,
                host_address.city,
                host_address.state,
                host_address.latitude,
                host_address.longitude
            )
            
            if not host_result.get('success'):
                return {
                    "valid": False,
                    "reason": f"Failed to register host: {host_result.get('message')}",
                    "qualified_neighbors": []
                }
            
            # Register neighbor homes
            qualified_neighbors = []
            for neighbor in neighbor_addresses:
                neighbor_result = register_neighbor_home(
                    neighbor.street,
                    neighbor.city,
                    neighbor.state,
                    neighbor.latitude,
                    neighbor.longitude
                )
                
                if neighbor_result.get('success'):
                    qualified_neighbors.append(neighbor)
            
            # Use function to discover neighbors for this host
            host_address_str = f"{host_address.street}, {host_address.city}, {host_address.state}"
            discovered_neighbors = discover_neighbors_for_host(host_address_str)
            
            validation_result = {
                "valid": len(qualified_neighbors) >= 3,  # Minimum 3 homes for cluster
                "qualified_neighbors": qualified_neighbors,
                "discovered_neighbors": discovered_neighbors,
                "total_neighbors": len(qualified_neighbors),
                "min_neighbors_required": 3
            }
            
            logger.info(f"Cluster validation: {validation_result['valid']}, {len(qualified_neighbors)} qualified neighbors")
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate cluster formation: {str(e)}")
            return {
                "valid": False,
                "reason": f"Validation error: {str(e)}",
                "qualified_neighbors": []
            }
            
    async def optimize_cluster_assignment(
        self,
        addresses: List[Address],
        max_clusters: Optional[int] = None
    ) -> List[List[Address]]:
        """Optimize cluster assignment.
        
        Args:
            addresses: List of addresses to assign to clusters
            max_clusters: Maximum number of clusters to create
            
        Returns:
            List of address clusters
        """
        try:
            if not addresses:
                return []
            
            # Register all addresses as potential hosts first
            host_results = []
            for addr in addresses:
                result = register_host_home(
                    addr.street,
                    addr.city,
                    addr.state,
                    addr.latitude,
                    addr.longitude
                )
                host_results.append((addr, result))
            
            # Find qualified neighbors for each potential host
            clusters = []
            used_addresses = set()
            
            for addr, host_result in host_results:
                if addr in used_addresses:
                    continue
                
                if not host_result.get('success'):
                    continue
                
                # Use function to find qualified neighbors
                addr_str = f"{addr.street}, {addr.city}, {addr.state}"
                qualified_neighbors = find_qualified_host_for_neighbor(addr_str)
                
                # Create cluster with this host and its qualified neighbors
                cluster = [addr]
                used_addresses.add(addr)
                
                # Add qualified neighbors to this cluster
                for neighbor_addr in addresses:
                    if neighbor_addr in used_addresses:
                        continue
                    
                    neighbor_str = f"{neighbor_addr.street}, {neighbor_addr.city}, {neighbor_addr.state}"
                    if neighbor_str in qualified_neighbors:
                        cluster.append(neighbor_addr)
                        used_addresses.add(neighbor_addr)
                        
                        # Stop if cluster is full
                        if len(cluster) >= 5:  # Max cluster size
                            break
                
                # Only add cluster if it meets minimum size
                if len(cluster) >= 3:
                    clusters.append(cluster)
                
                # Stop if we've reached max clusters
                if max_clusters and len(clusters) >= max_clusters:
                    break
            
            logger.info(f"Optimized cluster assignment: {len(clusters)} clusters created")
            return clusters
            
        except Exception as e:
            logger.error(f"Failed to optimize cluster assignment: {str(e)}")
            return []
            
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

# Core Mowthos functions (copied from Mowthos-Cluster-Logic)

def ensure_host_homes_csv():
    """Create a template host_homes.csv if it doesn't exist."""
    if not os.path.exists(HOST_HOMES_CSV):
        with open(HOST_HOMES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['address', 'city', 'state', 'latitude', 'longitude'])
            writer.writeheader()
            # Example row
            writer.writerow({
                'address': '123 Main St',
                'city': 'Rochester',
                'state': 'MN',
                'latitude': 44.0123,
                'longitude': -92.1234
            })

def ensure_neighbor_homes_csv():
    """Create a template neighbor_homes.csv if it doesn't exist."""
    if not os.path.exists(NEIGHBOR_HOMES_CSV):
        with open(NEIGHBOR_HOMES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['address', 'city', 'state', 'latitude', 'longitude'])
            writer.writeheader()
            # Example row
            writer.writerow({
                'address': '456 Elm St',
                'city': 'Rochester',
                'state': 'MN',
                'latitude': 44.0124,
                'longitude': -92.1235
            })

def load_addresses_from_csv(path: str) -> List[dict]:
    """Load addresses from a CSV file, returning a list of dicts with full address and lat/lon."""
    addresses = []
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
    return addresses

def register_host_home(address: str, city: str, state: str, latitude: Optional[float]=None, longitude: Optional[float]=None) -> dict:
    """Register a host home, geocoding if lat/lon not provided. Appends to host_homes.csv."""
    ensure_host_homes_csv()
    if latitude is None or longitude is None:
        # Use your existing mapbox service for geocoding
        from .mapbox import MapboxService
        mapbox_service = MapboxService(settings.mapbox_access_token)
        coords = mapbox_service.geocode_address(f"{address}, {city}, {state}")
        if not coords:
            return {"success": False, "message": "Could not geocode address."}
        latitude, longitude = coords
    full_address = f"{address}, {city}, {state}"
    with open(HOST_HOMES_CSV, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'city', 'state', 'latitude', 'longitude'])
        writer.writerow({'address': address, 'city': city, 'state': state, 'latitude': latitude, 'longitude': longitude})
    return {"success": True, "full_address": full_address, "latitude": latitude, "longitude": longitude}

def register_neighbor_home(address: str, city: str, state: str, latitude: Optional[float]=None, longitude: Optional[float]=None) -> dict:
    """Register a neighbor home, geocoding if lat/lon not provided. Appends to neighbor_homes.csv."""
    ensure_neighbor_homes_csv()
    if latitude is None or longitude is None:
        # Use your existing mapbox service for geocoding
        from .mapbox import MapboxService
        mapbox_service = MapboxService(settings.mapbox_access_token)
        coords = mapbox_service.geocode_address(f"{address}, {city}, {state}")
        if not coords:
            return {"success": False, "message": "Could not geocode address."}
        latitude, longitude = coords
    full_address = f"{address}, {city}, {state}"
    with open(NEIGHBOR_HOMES_CSV, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'city', 'state', 'latitude', 'longitude'])
        writer.writerow({'address': address, 'city': city, 'state': state, 'latitude': latitude, 'longitude': longitude})
    return {"success": True, "full_address": full_address, "latitude": latitude, "longitude": longitude}

def discover_neighbors_for_host(host_address: str) -> List[str]:
    """
    Find all qualified neighbors for a host home using road-aware detection.
    Only considers registered host homes as the host.
    Returns a list of qualified neighbor full addresses (street, city, state).
    """
    ensure_host_homes_csv()
    # Geocode the host address
    from .mapbox import MapboxService
    mapbox_service = MapboxService(settings.mapbox_access_token)
    host_coords = mapbox_service.geocode_address(host_address)
    if not host_coords:
        print(f"[ERROR] Could not geocode host address: {host_address}")
        return []
    # Load all candidate addresses (from the big CSV)
    candidates = load_addresses_from_csv(ADDRESS_CSV)
    # Load the host home full address (from host_homes.csv)
    host_homes = load_addresses_from_csv(HOST_HOMES_CSV)
    # Find the host home entry that matches the input address
    host_home = None
    for h in host_homes:
        if host_address.lower() in h['full_address'].lower():
            host_home = h
            break
    if not host_home:
        print(f"[ERROR] Host home not found in host_homes.csv: {host_address}")
        return []
    # Build BallTree for all candidates
    candidate_coords = np.array([[c['latitude'], c['longitude']] for c in candidates])
    candidate_coords_rad = np.radians(candidate_coords)
    tree = BallTree(candidate_coords_rad, metric='haversine')
    host_latlon_rad = np.radians([[host_home['latitude'], host_home['longitude']]])
    idxs = tree.query_radius(host_latlon_rad, r=RADIUS_RADIANS)[0]
    qualified_neighbors = []
    start = time.time()
    for idx in idxs:
        candidate = candidates[idx]
        if candidate['full_address'].lower() == host_home['full_address'].lower():
            continue  # skip self
        # Road-aware check
        if mapbox_service.is_accessible_without_crossing_road(
            (host_home['latitude'], host_home['longitude']),
            (candidate['latitude'], candidate['longitude'])
        ):
            qualified_neighbors.append(candidate['full_address'])
    elapsed = time.time() - start
    print(f"[DEBUG] Checked {len(idxs)} candidates, found {len(qualified_neighbors)} qualified neighbors. Avg time: {elapsed/max(1,len(idxs)):.2f}s per neighbor.")
    return qualified_neighbors

def find_qualified_host_for_neighbor(neighbor_address: str) -> List[str]:
    """
    For a given neighbor address, find all registered host homes for which this address qualifies as a neighbor.
    Returns a list of host home full addresses (street, city, state).
    """
    ensure_host_homes_csv()
    # Geocode neighbor address
    from .mapbox import MapboxService
    mapbox_service = MapboxService(settings.mapbox_access_token)
    neighbor_coords = mapbox_service.geocode_address(neighbor_address)
    if not neighbor_coords:
        print(f"[ERROR] Could not geocode neighbor address: {neighbor_address}")
        return []
    # Load all host homes
    host_homes = load_addresses_from_csv(HOST_HOMES_CSV)
    # Build BallTree for all host homes
    host_coords = np.array([[h['latitude'], h['longitude']] for h in host_homes])
    host_coords_rad = np.radians(host_coords)
    tree = BallTree(host_coords_rad, metric='haversine')
    neighbor_latlon_rad = np.radians([[neighbor_coords[0], neighbor_coords[1]]])
    idxs = tree.query_radius(neighbor_latlon_rad, r=RADIUS_RADIANS)[0]
    qualified_hosts = []
    start = time.time()
    for idx in idxs:
        host = host_homes[idx]
        # Road-aware check
        if mapbox_service.is_accessible_without_crossing_road(
            (host['latitude'], host['longitude']),
            (neighbor_coords[0], neighbor_coords[1])
        ):
            qualified_hosts.append(host['full_address'])
    elapsed = time.time() - start
    print(f"[DEBUG] Checked {len(idxs)} hosts, found {len(qualified_hosts)} qualified hosts. Avg time: {elapsed/max(1,len(idxs)):.2f}s per host.")
    return qualified_hosts