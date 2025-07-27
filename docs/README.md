# MowthosOS - Comprehensive Documentation

**A comprehensive robotic mower management system combining PyMammotion mower control with intelligent clustering algorithms**

## Table of Contents

1. [System Overview](#system-overview)
2. [PyMammotion Component](#pymammotion-component)
3. [Mowthos-Cluster-Logic Component](#mowthos-cluster-logic-component)
4. [Integration Architecture](#integration-architecture)
5. [API Reference](#api-reference)
6. [Deployment Guide](#deployment-guide)
7. [Future Enhancements](#future-enhancements)

---

## System Overview

MowthosOS is a sophisticated backend system designed to manage Mammotion robotic mowers at scale, enabling:

- **Individual Mower Control**: Direct control and monitoring of Mammotion mowers via PyMammotion
- **Intelligent Clustering**: Geographic clustering of homes for efficient mower sharing
- **API-First Architecture**: RESTful APIs for easy integration with web and mobile frontends
- **Scalable Backend**: Built with FastAPI for high performance and automatic documentation

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MowthosOS                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────┐  │
│  │   Main API      │    │     Submodules                 │  │
│  │   (main.py)     │    │                                │  │
│  │                 │    │  ┌───────────────────────────┐  │  │
│  │ - Mower Control │    │  │      PyMammotion         │  │  │
│  │ - FastAPI       │    │  │   (Mower Interface)      │  │  │
│  │ - Session Mgmt  │    │  │                          │  │  │
│  └─────────────────┘    │  └───────────────────────────┘  │  │
│                         │                                │  │
│                         │  ┌───────────────────────────┐  │  │
│                         │  │  Mowthos-Cluster-Logic   │  │  │
│                         │  │   (Geographic Logic)     │  │  │
│                         │  │                          │  │  │
│                         │  └───────────────────────────┘  │  │
│                         └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## PyMammotion Component

### Overview

PyMammotion is a Python library for controlling Mammotion robotic mowers (Luba, Luba 2 & Yuka) via multiple communication protocols:

- **MQTT/Cloud Communication**: Primary communication via Aliyun IoT
- **Bluetooth Low Energy (BLE)**: Direct local communication
- **HTTP API**: Web-based control interface

### Core Classes and Functions

#### 1. Main Device Management

**`Mammotion` Class** - Primary interface for mower control
```python
from pymammotion.mammotion.devices.mammotion import Mammotion

# Initialize the main controller
mammotion = Mammotion()

# Login and connect to cloud
await mammotion.login_and_initiate_cloud(account, password)

# Get available devices
devices = mammotion.device_manager.devices
```

**Key Methods:**
- `login_and_initiate_cloud(account, password)` - Authenticate with Mammotion cloud
- `get_device_by_name(device_name)` - Retrieve specific device instance
- `send_command(device_name, command)` - Send control commands to mower

#### 2. Device Communication Protocols

**`MammotionMQTT`** - Cloud-based MQTT communication
```python
from pymammotion.mqtt import MammotionMQTT

luba = MammotionMQTT(
    iot_token=token,
    region_id=region,
    product_key=product_key,
    device_name=device_name,
    device_secret=device_secret,
    client_id=client_id,
    cloud_client=cloud_client
)
```

**`MammotionBLE`** - Bluetooth Low Energy communication
```python
from pymammotion.bluetooth.ble import MammotionBLE

ble_client = MammotionBLE()
await ble_client.connect(device_address)
```

**`MammotionHTTP`** - HTTP API communication
```python
from pymammotion.http.http import MammotionHTTP

http_client = MammotionHTTP()
```

#### 3. Device Control Commands

**Movement Commands:**
```python
# Basic movement controls
command.move_forward(linear_speed)  # 0.0-1.0
command.move_back(linear_speed)
command.move_left(angular_speed)
command.move_right(angular_speed)
```

**Mowing Operations:**
```python
# Mowing control
await mammotion.send_command(device_name, "start_job")
await mammotion.send_command(device_name, "cancel_job")
await mammotion.send_command(device_name, "pause_execute_task")
await mammotion.send_command(device_name, "resume_execute_task")
await mammotion.send_command(device_name, "return_to_dock")
```

#### 4. Device State Management

**`MowingDevice`** - Complete device state representation
```python
@dataclass
class MowingDevice:
    name: str
    online: bool
    enabled: bool
    mower_state: MowerInfo
    location: Location
    work: CurrentTaskSettings
    report_data: ReportData
    device_firmwares: DeviceFirmwares
```

**State Properties:**
- `battery_level` - Current battery percentage
- `charging_state` - Charging status
- `work_mode` - Current operational mode
- `location` - GPS coordinates and orientation
- `blade_status` - Cutting blade status

#### 5. Connection Management

**Connection Preferences:**
```python
from pymammotion.data.model.enums import ConnectionPreference

ConnectionPreference.WIFI      # Cloud/WiFi connection
ConnectionPreference.BLUETOOTH # Direct BLE connection
ConnectionPreference.EITHER    # Automatic selection
```

### Usage Examples

#### Basic Mower Control
```python
import asyncio
from pymammotion.mammotion.devices.mammotion import Mammotion

async def control_mower():
    # Initialize and login
    mammotion = Mammotion()
    await mammotion.login_and_initiate_cloud("user@email.com", "password")
    
    # Get first available device
    devices = mammotion.device_manager.devices
    device_name = list(devices.keys())[0]
    
    # Start mowing
    await mammotion.send_command(device_name, "start_job")
    
    # Get status
    device = mammotion.get_device_by_name(device_name)
    print(f"Battery: {device.mower_state.report_data.dev.battery_val}%")
    print(f"Mode: {device.mower_state.report_data.dev.sys_status}")

asyncio.run(control_mower())
```

#### Advanced State Monitoring
```python
def monitor_mower_state(device):
    state = device.mower_state
    
    return {
        "online": state.online,
        "battery": state.report_data.dev.battery_val,
        "charging": state.report_data.dev.charge_state,
        "work_mode": state.report_data.dev.sys_status,
        "location": {
            "lat": state.location.device.latitude,
            "lng": state.location.device.longitude,
            "orientation": state.location.orientation
        },
        "work_progress": state.report_data.work.progress,
        "work_area": state.report_data.work.area
    }
```

---

## Mowthos-Cluster-Logic Component

### Overview

Mowthos-Cluster-Logic provides intelligent geographic clustering capabilities for organizing homes into efficient mower-sharing groups. It uses advanced algorithms to determine which homes can be serviced by the same mower based on:

- **Geographic Proximity**: Homes within 80-meter radius
- **Road-Aware Detection**: Prevents clustering across impassable roads
- **Scalable Storage**: CSV-based data management for simplicity

### Core Services and Functions

#### 1. Cluster Engine (`cluster_engine.py`)

**Core Algorithms:**
- **Ball Tree Algorithm**: Efficient spatial indexing using scikit-learn
- **Haversine Distance**: Geographic distance calculation
- **Road Detection**: OSMnx integration for road network analysis

**Key Functions:**

```python
# Host home registration
def register_host_home(address, city, state, latitude=None, longitude=None):
    """Register a host home with optional geocoding"""
    
# Neighbor home registration  
def register_neighbor_home(address, city, state, latitude=None, longitude=None):
    """Register a neighbor home with optional geocoding"""

# Neighbor discovery
def discover_neighbors_for_host(host_address):
    """Find all qualified neighbors for a host using road-aware detection"""
    
# Host discovery
def find_qualified_host_for_neighbor(neighbor_address):
    """Find all qualified host homes for a neighbor"""
```

#### 2. Geographic Services (`mapbox_service.py`)

**`MapboxService` Class** - Geolocation and mapping services

```python
class MapboxService:
    def __init__(self, access_token: str)
    
    def geocode_address(self, address: str) -> Optional[Tuple[float, float]]
    """Convert address to coordinates"""
    
    def is_accessible_without_crossing_road(self, host_coords, candidate_coords) -> bool
    """Road-aware neighbor detection using OSMnx"""
    
    def get_property_boundaries(self, lat: float, lng: float) -> Optional[Dict]
    """Get property boundary information"""
```

**Road-Aware Detection Algorithm:**
1. Download road network from OpenStreetMap (300m radius)
2. Create buffered road geometries (~5m width)
3. Test line intersection between homes and roads
4. Reject candidates that cross drivable roads

#### 3. API Endpoints (`routers/clusters.py`)

**CSV-Based Endpoints:**

```python
POST /clusters/register_host_home_csv
POST /clusters/register_neighbor_home_csv
POST /clusters/discover_neighbors_for_host_csv
POST /clusters/find_qualified_host_for_neighbor_csv
POST /clusters/geocode
```

**Request/Response Models:**
```python
class RegisterHostHomeCSVRequest(BaseModel):
    address: str
    city: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class QualifiedAddressesResponse(BaseModel):
    qualified_addresses: List[str]
```

#### 4. Data Models (`models.py`)

**Database Models** (for future enhancement):
```python
class User(Base):
    email: str
    name: str
    latitude: float
    longitude: float
    is_host: bool
    cluster_id: Optional[int]

class Cluster(Base):
    name: str
    host_user_id: int
    max_capacity: int = 5

class LawnBoundary(Base):
    user_id: int
    boundary_coordinates: str  # JSON polygon
    area_sqm: float
```

### Usage Examples

#### Registering Homes
```python
import requests

# Register a host home
response = requests.post("http://localhost:8000/clusters/register_host_home_csv", json={
    "address": "123 Main St",
    "city": "Rochester", 
    "state": "MN"
})

# Register a neighbor home
response = requests.post("http://localhost:8000/clusters/register_neighbor_home_csv", json={
    "address": "456 Elm St",
    "city": "Rochester",
    "state": "MN" 
})
```

#### Finding Neighbors
```python
# Find neighbors for a host
response = requests.post("http://localhost:8000/clusters/discover_neighbors_for_host_csv", json={
    "address": "123 Main St",
    "city": "Rochester",
    "state": "MN"
})

qualified_neighbors = response.json()["qualified_addresses"]
```

#### Geocoding Addresses
```python
# Geocode an address
response = requests.post("http://localhost:8000/clusters/geocode", json={
    "address": "123 Main St, Rochester, MN"
})

coords = response.json()
latitude = coords["latitude"]
longitude = coords["longitude"]
```

---

## Integration Architecture

### Current Integration (main.py)

The current `main.py` provides a basic FastAPI service that integrates PyMammotion for mower control:

```python
# Key integration points:
- Session management for user authentication
- Device discovery and connection
- Mower status monitoring
- Command execution (start/stop/pause/resume/dock)
- Health monitoring
```

**Current API Endpoints:**
- `POST /login` - Authenticate with Mammotion cloud
- `GET /status` - Get mower status  
- `POST /start-mow` - Start mowing operation
- `POST /stop-mow` - Stop mowing
- `POST /pause-mowing` - Pause operation
- `POST /resume-mowing` - Resume operation
- `POST /return-to-dock` - Return to charging dock
- `GET /devices` - List available devices
- `GET /health` - Health check

### Proposed Unified Architecture

#### 1. Microservices Structure

```
┌─────────────────────────────────────────────────────────────┐
│                   MowthosOS Backend                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              API Gateway Layer                          │ │
│  │                  (FastAPI)                             │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │                                                         │ │
│  │  ┌───────────────┐  ┌─────────────────┐  ┌────────────┐ │ │
│  │  │   Mower       │  │    Cluster      │  │  Payment   │ │ │
│  │  │   Service     │  │    Service      │  │  Service   │ │ │
│  │  │               │  │                 │  │            │ │ │
│  │  │ - Device Mgmt │  │ - Geographic    │  │ - Stripe   │ │ │
│  │  │ - Commands    │  │   Clustering    │  │   API      │ │ │
│  │  │ - Monitoring  │  │ - Road Analysis │  │ - Billing  │ │ │
│  │  │ - PyMammotion │  │ - Mapbox API    │  │ - Invoices │ │ │
│  │  └───────────────┘  └─────────────────┘  └────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 Data Layer                              │ │
│  │                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │ │
│  │  │ PostgreSQL  │  │    Redis    │  │    CSV Files    │  │ │
│  │  │             │  │             │  │                 │  │ │
│  │  │ - Users     │  │ - Sessions  │  │ - Host Homes    │  │ │
│  │  │ - Devices   │  │ - Cache     │  │ - Neighbors     │  │ │
│  │  │ - Billing   │  │ - Real-time │  │ - Addresses     │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 2. Service Breakdown

**Mower Service** (Enhanced PyMammotion Integration)
- Device discovery and management
- Real-time status monitoring
- Command execution and queuing
- Firmware management
- Error handling and recovery

**Cluster Service** (Enhanced Mowthos-Cluster-Logic)
- Geographic clustering algorithms
- Road-aware neighbor detection
- Dynamic cluster optimization
- Route planning for multi-home mowing
- Coverage area calculation

**Payment Service** (New - Stripe Integration)
- Subscription management
- Usage-based billing
- Payment processing
- Invoice generation
- Billing analytics

#### 3. Enhanced Data Models

```python
# Enhanced User Model
class User(BaseModel):
    id: int
    email: str
    name: str
    address: Address
    subscription_plan: SubscriptionPlan
    mower_assignments: List[MowerAssignment]
    billing_info: BillingInfo
    
# Mower Device Model
class MowerDevice(BaseModel):
    id: str
    name: str
    model: str
    firmware_version: str
    owner_id: int
    cluster_id: Optional[int]
    status: MowerStatus
    location: Location
    maintenance_schedule: MaintenanceSchedule
    
# Enhanced Cluster Model  
class Cluster(BaseModel):
    id: int
    name: str
    host_user_id: int
    member_users: List[int]
    mower_devices: List[str]
    coverage_area: GeographicArea
    mowing_schedule: Schedule
    optimization_metrics: ClusterMetrics
```

#### 4. API Consolidation

**Unified Endpoint Structure:**
```
/api/v1/
├── auth/
│   ├── POST /login
│   ├── POST /logout
│   └── POST /refresh
├── mowers/
│   ├── GET /devices
│   ├── GET /{device_id}/status
│   ├── POST /{device_id}/commands/start
│   ├── POST /{device_id}/commands/stop
│   ├── POST /{device_id}/commands/pause
│   ├── POST /{device_id}/commands/resume
│   ├── POST /{device_id}/commands/dock
│   └── GET /{device_id}/history
├── clusters/
│   ├── POST /register_host
│   ├── POST /register_neighbor  
│   ├── GET /{cluster_id}
│   ├── POST /{cluster_id}/optimize
│   └── GET /{cluster_id}/analytics
├── billing/
│   ├── GET /subscription
│   ├── POST /subscription/upgrade
│   ├── GET /invoices
│   └── POST /payment-methods
└── admin/
    ├── GET /analytics
    ├── GET /system-health
    └── POST /maintenance
```

---

## API Reference

### Authentication

All APIs require authentication via session tokens obtained from the login endpoint.

**Login**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "account": "user@example.com",
  "password": "password123"
}

Response:
{
  "success": true,
  "session_id": "abc123...",
  "user_id": 1,
  "expires_at": "2024-01-15T10:30:00Z"
}
```

### Mower Control

**Get Device Status**
```http
GET /api/v1/mowers/{device_id}/status
Authorization: Bearer {session_token}

Response:
{
  "device_id": "Luba-XXXXX",
  "online": true,
  "battery_level": 85,
  "work_mode": "MODE_WORKING",
  "location": {
    "latitude": 44.0123,
    "longitude": -92.1234,
    "orientation": 90
  },
  "work_progress": 45,
  "work_area": 150,
  "last_updated": "2024-01-15T10:30:00Z"
}
```

**Start Mowing**
```http
POST /api/v1/mowers/{device_id}/commands/start
Authorization: Bearer {session_token}

{
  "area_id": "zone_1",
  "priority": "normal"
}

Response:
{
  "success": true,
  "command_id": "cmd_123",
  "estimated_duration": 7200
}
```

### Cluster Management

**Register Host Home**
```http
POST /api/v1/clusters/register_host
Authorization: Bearer {session_token}

{
  "address": "123 Main St",
  "city": "Rochester",
  "state": "MN",
  "mower_device_ids": ["Luba-001"],
  "service_area": {
    "polygon": [[lat, lng], ...],
    "area_sqm": 500
  }
}

Response:
{
  "success": true,
  "cluster_id": 1,
  "qualified_neighbors": ["456 Elm St, Rochester, MN"]
}
```

---

## Deployment Guide

### Prerequisites

**System Requirements:**
- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (recommended)

**External Services:**
- Mapbox Access Token
- Stripe API Keys (for payment processing)
- Mammotion Cloud Account

### Environment Setup

```bash
# 1. Clone repository with submodules
git clone --recursive https://github.com/your-org/mowthosos
cd mowthosos

# 2. Create environment file
cp .env.example .env

# 3. Configure environment variables
DATABASE_URL=postgresql://user:pass@localhost:5432/mowthosos
REDIS_URL=redis://localhost:6379/0
MAPBOX_ACCESS_TOKEN=your_mapbox_token
STRIPE_SECRET_KEY=your_stripe_key
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
```

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mowthosos
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
      
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: mowthosos
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  redis:
    image: redis:6-alpine
    
volumes:
  postgres_data:
```

```bash
# Deploy with Docker Compose
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Verify deployment
curl http://localhost:8000/health
```

### Manual Deployment

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r Mowthos-Cluster-Logic/requirements.txt

# 2. Initialize submodules
git submodule update --init --recursive

# 3. Set up database
alembic upgrade head

# 4. Run the application
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Production Considerations

**Security:**
- Use HTTPS in production
- Implement rate limiting
- Set up proper CORS policies
- Use secure session management
- Implement API key authentication

**Performance:**
- Use connection pooling for database
- Implement Redis caching for frequently accessed data
- Set up load balancing for multiple instances
- Monitor with APM tools (New Relic, DataDog)

**Monitoring:**
- Set up logging aggregation (ELK stack)
- Implement health checks
- Monitor mower connectivity status
- Track API performance metrics

---

## Future Enhancements

### 1. Advanced Mower Fleet Management

**Multi-Mower Coordination**
- Intelligent scheduling across multiple mowers
- Automatic failover when mowers are offline
- Cross-cluster mower sharing during peak demand

**Predictive Maintenance**
- ML-based fault prediction
- Automated maintenance scheduling
- Parts inventory management

### 2. Enhanced Geographic Intelligence

**Advanced Clustering Algorithms**
- Machine learning-based cluster optimization
- Seasonal adaptation for mowing patterns
- Weather-aware scheduling

**Precision Mapping**
- Integration with satellite imagery
- Real-time grass growth monitoring
- Obstacle detection and mapping

### 3. Business Logic Expansion

**Dynamic Pricing**
- Demand-based pricing models
- Seasonal rate adjustments
- Loyalty program integration

**Service Quality Monitoring**
- Customer satisfaction tracking
- Automated quality assurance
- Performance-based SLA management

### 4. Integration Ecosystem

**Smart Home Integration**
- Home Assistant compatibility
- Alexa/Google Assistant voice control
- IoT sensor integration for lawn conditions

**Mobile Applications**
- Real-time mower tracking
- Push notifications for status updates
- Augmented reality lawn planning

### 5. Sustainability Features

**Energy Optimization**
- Solar charging integration
- Grid-tied energy management
- Carbon footprint tracking

**Environmental Monitoring**
- Soil health assessment
- Biodiversity impact tracking
- Water usage optimization

---

## Conclusion

MowthosOS represents a comprehensive solution for scalable robotic mower management, combining the robust device control capabilities of PyMammotion with the intelligent geographic clustering of Mowthos-Cluster-Logic. The proposed unified architecture provides a solid foundation for:

- **Seamless mower control** across multiple communication protocols
- **Intelligent clustering** for optimal service delivery
- **Scalable payment processing** for commercial viability
- **Professional deployment** with enterprise-grade features

The modular design ensures extensibility for future enhancements while maintaining stability and performance for current operations.

**Next Steps:**
1. Implement the unified API gateway
2. Integrate Stripe payment processing
3. Enhance database models for production use
4. Develop comprehensive testing suite
5. Create deployment automation scripts
6. Build monitoring and observability stack

This architecture positions MowthosOS as a market-leading solution for robotic mower fleet management and shared lawn care services.