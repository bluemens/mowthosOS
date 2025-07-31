# MowthosOS - Comprehensive Documentation

**A comprehensive robotic mower management system combining PyMammotion mower control with intelligent clustering algorithms**

## Table of Contents

1. [System Overview](#system-overview)
2. [PyMammotion Component](#pymammotion-component) ⚠️ *External Submodule - Do Not Modify*
3. [Cluster Service Component](#cluster-service-component) ✅ *Integrated Clustering Logic*
4. [Integration Architecture](#integration-architecture)
5. [API Reference](#api-reference)
6. [Deployment Guide](#deployment-guide)
7. [Future Enhancements](#future-enhancements)

### 📚 Additional Documentation
- [Development Guidelines](development-guidelines.md) - **Required reading for developers**
- [Deployment Proposal](deployment-proposal.md) - Professional deployment roadmap
- [Quick Reference](quick-reference.md) - Essential functions and patterns
- [Submodule Warning](SUBMODULE-WARNING.md) - Critical warnings about external dependencies

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
│  │   Main API      │    │     Components                 │  │
│  │   (main.py)     │    │                                │  │
│  │                 │    │  ┌───────────────────────────┐  │  │
│  │ - Mower Control │    │  │      PyMammotion         │  │  │
│  │ - FastAPI       │    │  │   (Mower Interface)      │  │  │
│  │ - Session Mgmt  │    │  │                          │  │  │
│  └─────────────────┘    │  └───────────────────────────┘  │  │
│                         │                                │  │
│                         │  ┌───────────────────────────┐  │  │
│                         │  │    Cluster Service       │  │  │
│                         │  │   (Integrated Logic)     │  │  │
│                         │  │                          │  │  │
│                         │  └───────────────────────────┘  │  │
│                         └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## PyMammotion Component

### ⚠️ CRITICAL WARNING: DO NOT MODIFY PyMammotion

**PyMammotion is an external git submodule and MUST NOT be modified directly.**

- **External Repository**: `https://github.com/mikey0000/PyMammotion.git`
- **Read-Only**: Treat as a dependency, not part of our codebase
- **Updates**: Will overwrite any local modifications
- **Contributing**: Changes should be submitted to the original repository

See [Development Guidelines](development-guidelines.md) for detailed integration patterns.

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
    
    # Get device and start mowing
    device = mammotion.get_device_by_name("Luba_001")
    await mammotion.send_command("Luba_001", "start_job")
```

---

## Cluster Service Component

### ✅ INTEGRATED CLUSTERING LOGIC

**The clustering logic has been migrated from Mowthos-Cluster-Logic and is now fully integrated into our codebase.**

- **Location**: `src/services/cluster/`
- **Status**: Fully integrated and maintained
- **Dependencies**: Uses our own Mapbox service and address database
- **Benefits**: Direct control, easier maintenance, no external dependencies

### Overview

The Cluster Service provides intelligent geographic clustering capabilities for organizing homes into efficient mower-sharing groups. It uses advanced algorithms to determine which homes can be serviced by the same mower based on:

- **Geographic Proximity**: 80-meter radius clustering
- **Road-Aware Detection**: Considers road crossings for accessibility
- **Address Validation**: Mapbox geocoding for accurate location data
- **CSV Database**: Rochester address database for real-world testing

### Core Components

#### 1. Cluster Service (`service.py`)

**Main service interface for cluster management:**
```python
from src.services.cluster.service import ClusterService

cluster_service = ClusterService()

# Register a host home
cluster = await cluster_service.register_host(address, user_id)

# Find neighbors for a cluster
neighbors = await cluster_service.find_neighbors(cluster_id)

# Join a cluster
assignment = await cluster_service.join_cluster(cluster_id, address, user_id)
```

#### 2. Cluster Engine (`engine.py`)

**Core clustering algorithms and functions:**
```python
from src.services.cluster.engine import (
    register_host_home, register_neighbor_home,
    discover_neighbors_for_host, find_qualified_host_for_neighbor
)

# Register host home
result = register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)

# Discover neighbors
neighbors = discover_neighbors_for_host("123 Main St, Rochester, MN")

# Find qualified hosts
hosts = find_qualified_host_for_neighbor("456 Elm St, Rochester, MN")
```

#### 3. Mapbox Service (`mapbox.py`)

**Address validation and geocoding:**
```python
from src.services.cluster.mapbox import MapboxService

mapbox = MapboxService(settings.mapbox_access_token)

# Validate address
validated = await mapbox.validate_address(
    street="123 Main St",
    city="Rochester", 
    state="MN",
    zip_code="55901"
)
```

### Key Features

#### Geographic Clustering
- **80-meter radius**: Optimal distance for mower sharing
- **Road-aware filtering**: Excludes addresses requiring road crossings
- **Real address database**: Uses Rochester address CSV for testing
- **BallTree optimization**: Efficient neighbor search algorithms

#### Address Management
- **CSV-based storage**: Host homes and neighbor homes in CSV files
- **Automatic geocoding**: Mapbox integration for coordinate lookup
- **Address validation**: Ensures addresses are valid and accessible
- **State handling**: Supports different CSV formats (postcode vs state)

#### Cluster Operations
- **Host registration**: Register homes as cluster hosts
- **Neighbor discovery**: Find qualified neighbors for hosts
- **Cluster joining**: Add homes to existing clusters
- **Route optimization**: Calculate optimal mowing routes
- **Coverage analysis**: Analyze cluster efficiency and coverage

### Usage Examples

#### Basic Cluster Management
```python
from src.services.cluster.service import ClusterService
from src.models.schemas import Address

# Initialize service
cluster_service = ClusterService()
await cluster_service.initialize()

# Create address
address = Address(
    street="503 GERANIUM ST SE",
    city="ROCHESTER",
    state="MN",
    zip_code="55904",
    latitude=43.9607404,
    longitude=-92.4557066
)

# Register host
cluster = await cluster_service.register_host(address, user_id=123)

# Find neighbors
neighbors = await cluster_service.find_neighbors(cluster.cluster_id)
print(f"Found {len(neighbors)} qualified neighbors")
```

#### Advanced Clustering
```python
# Suggest clusters for an address
suggestions = await cluster_service.suggest_clusters(address)

# Get cluster statistics
stats = await cluster_service.get_cluster_stats(cluster_id)

# Optimize routes
optimization = await cluster_service.optimize_routes(cluster_id)
```

### Migration Benefits

#### Before (External Submodule)
- ❌ Complex import paths and dependency management
- ❌ External repository dependency
- ❌ Difficult to modify and customize
- ❌ Version conflicts and update issues

#### After (Integrated Logic)
- ✅ Direct control over clustering algorithms
- ✅ Simplified architecture and imports
- ✅ Easy customization and maintenance
- ✅ No external dependencies for core logic
- ✅ Better performance and reliability

### Configuration

#### Environment Variables
```bash
# Required for Mapbox geocoding
MAPBOX_ACCESS_TOKEN=your_mapbox_token_here
```

#### CSV Files
The service uses CSV files for address data:
- `Mowthos-Cluster-Logic/olmsted_addresses_559xx.csv` - Rochester address database
- `Mowthos-Cluster-Logic/host_homes.csv` - Registered host homes
- `Mowthos-Cluster-Logic/neighbor_homes.csv` - Registered neighbor homes

### Testing

#### Integration Test
```bash
# Test the integrated clustering functions
poetry run python test_cluster_integration.py
```

#### Local Function Test
```bash
# Test local functions without external dependencies
poetry run python test_local_cluster.py
```

---

## Integration Architecture

### System Components

**1. Main API (`main.py`)**
- FastAPI application entry point
- Route definitions and middleware
- Session management and authentication
- Integration with all services

**2. Mower Service (`src/services/mower/`)**
- PyMammotion integration wrapper
- Device management and control
- State monitoring and reporting
- Command execution and validation

**3. Cluster Service (`src/services/cluster/`)**
- Integrated geographic clustering logic
- Address validation and geocoding
- Neighbor discovery and qualification
- Route optimization and coverage analysis

**4. Core Infrastructure (`src/core/`)**
- Configuration management
- Database connections
- Logging and monitoring
- Utility functions and helpers

### Data Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│   FastAPI   │───▶│   Services  │
│  (Web/Mobile)│   │   (main.py)  │   │             │
└─────────────┘    └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  PyMammotion│    │   Cluster   │
                   │  (External) │    │   Service   │
                   └─────────────┘    └─────────────┘
```

### Service Communication

**1. Mower Control Flow:**
```
Client Request → FastAPI → MowerService → PyMammotion → Mower Device
```

**2. Clustering Flow:**
```
Client Request → FastAPI → ClusterService → Mapbox API → CSV Database
```

**3. Data Storage:**
- **Sessions**: Redis for user sessions and device states
- **Addresses**: CSV files for geographic data
- **Clusters**: Database tables for cluster management
- **Logs**: Structured logging for monitoring and debugging

### Error Handling

**1. Mower Communication:**
- Connection timeouts and retries
- Device state validation
- Command execution verification
- Fallback communication methods

**2. Clustering Operations:**
- Address validation failures
- Geocoding errors and fallbacks
- CSV file access issues
- Road detection algorithm errors

**3. System Resilience:**
- Graceful degradation for external service failures
- Comprehensive logging for debugging
- Circuit breaker patterns for external APIs
- Health checks and monitoring

---

## API Reference

### Mower Control Endpoints

**Device Management:**
```http
GET /api/v1/mowers                    # List all mowers
GET /api/v1/mowers/{device_name}      # Get specific mower
POST /api/v1/mowers/{device_name}/connect    # Connect to mower
DELETE /api/v1/mowers/{device_name}/disconnect # Disconnect from mower
```

**Mowing Operations:**
```http
POST /api/v1/mowers/{device_name}/start-job     # Start mowing job
POST /api/v1/mowers/{device_name}/cancel-job    # Cancel current job
POST /api/v1/mowers/{device_name}/pause         # Pause mowing
POST /api/v1/mowers/{device_name}/resume        # Resume mowing
POST /api/v1/mowers/{device_name}/return-dock   # Return to dock
```

**Device Status:**
```http
GET /api/v1/mowers/{device_name}/status         # Get device status
GET /api/v1/mowers/{device_name}/battery        # Get battery level
GET /api/v1/mowers/{device_name}/location       # Get GPS location
GET /api/v1/mowers/{device_name}/work-mode      # Get work mode
```

### Cluster Management Endpoints

**Cluster Operations:**
```http
POST /api/v1/clusters/register-host             # Register host home
GET /api/v1/clusters/{cluster_id}/neighbors     # Find cluster neighbors
POST /api/v1/clusters/{cluster_id}/join         # Join cluster
GET /api/v1/clusters/{cluster_id}/stats         # Get cluster statistics
POST /api/v1/clusters/{cluster_id}/optimize     # Optimize routes
```

**Address Management:**
```http
POST /api/v1/addresses/validate                 # Validate address
GET /api/v1/addresses/suggest-clusters          # Suggest clusters for address
GET /api/v1/addresses/coverage                  # Calculate coverage area
```

### Authentication & Security

**Session Management:**
```http
POST /api/v1/auth/login                         # User login
POST /api/v1/auth/logout                        # User logout
GET /api/v1/auth/session                        # Get session info
POST /api/v1/auth/refresh                       # Refresh session
```

**Rate Limiting:**
- 100 requests per minute per user
- 1000 requests per hour per IP
- Exponential backoff for repeated failures

### Response Formats

**Success Response:**
```json
{
  "success": true,
  "data": {
    "cluster_id": "cluster_123_1234567890",
    "name": "Main Street Cluster",
    "host_user_id": 123,
    "members": [123, 456, 789],
    "max_capacity": 5,
    "created_at": "2024-01-15T10:30:00Z",
    "is_active": true
  },
  "message": "Cluster created successfully"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_ADDRESS",
    "message": "Address could not be validated",
    "details": {
      "address": "123 Invalid St",
      "reason": "Geocoding failed"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Deployment Guide

### Prerequisites

**System Requirements:**
- Python 3.13+
- Redis 6.0+
- PostgreSQL 13+ (for production)
- 2GB RAM minimum
- 10GB storage

**External Dependencies:**
- Mapbox API access token
- Mammotion cloud account
- Internet connectivity for device communication

### Installation

**1. Clone Repository:**
```bash
git clone https://github.com/your-org/mowthosOS.git
cd mowthosOS
```

**2. Install Dependencies:**
```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Install PyMammotion submodule
git submodule update --init --recursive
```

**3. Environment Configuration:**
```bash
# Copy environment template
cp .env.local.example .env.local

# Edit configuration
nano .env.local
```

**Required Environment Variables:**
```bash
# Mapbox API (required for clustering)
MAPBOX_ACCESS_TOKEN=your_mapbox_token_here

# Database (for production)
DATABASE_URL=postgresql://user:pass@localhost/mowthos

# Redis (for sessions)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
```

**4. Initialize Database:**
```bash
# Create database tables
poetry run alembic upgrade head

# Load initial data
poetry run python scripts/init_data.py
```

### Development Setup

**1. Start Development Server:**
```bash
# Start with auto-reload
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or use the run script
poetry run python run.py
```

**2. Run Tests:**
```bash
# Run all tests
poetry run pytest

# Run specific test categories
poetry run pytest tests/test_mower/
poetry run pytest tests/test_cluster/

# Run with coverage
poetry run pytest --cov=src --cov-report=html
```

**3. Code Quality:**
```bash
# Format code
poetry run black src/ tests/

# Sort imports
poetry run isort src/ tests/

# Type checking
poetry run mypy src/

# Linting
poetry run flake8 src/ tests/
```

### Production Deployment

**1. Docker Deployment:**
```bash
# Build image
docker build -t mowthos:latest .

# Run container
docker run -d \
  --name mowthos \
  -p 8000:8000 \
  -e MAPBOX_ACCESS_TOKEN=$MAPBOX_TOKEN \
  -e DATABASE_URL=$DATABASE_URL \
  -e REDIS_URL=$REDIS_URL \
  mowthos:latest
```

**2. Docker Compose:**
```yaml
version: '3.8'
services:
  mowthos:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MAPBOX_ACCESS_TOKEN=${MAPBOX_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - postgres
      - redis
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=mowthos
      - POSTGRES_USER=mowthos
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

**3. Kubernetes Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mowthos
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mowthos
  template:
    metadata:
      labels:
        app: mowthos
    spec:
      containers:
      - name: mowthos
        image: mowthos:latest
        ports:
        - containerPort: 8000
        env:
        - name: MAPBOX_ACCESS_TOKEN
          valueFrom:
            secretKeyRef:
              name: mowthos-secrets
              key: mapbox-token
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mowthos-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: mowthos-secrets
              key: redis-url
```

### Monitoring & Health Checks

**1. Health Check Endpoint:**
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "mapbox": "available",
    "mammotion": "available"
  },
  "version": "1.0.0"
}
```

**2. Metrics Endpoint:**
```http
GET /metrics
```

**3. Logging Configuration:**
```python
# Structured logging for production
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    }
}
```

### Security Considerations

**1. Authentication:**
- JWT tokens for API access
- Session management with Redis
- Rate limiting per user/IP
- CORS configuration for web clients

**2. Data Protection:**
- Environment variables for secrets
- Database connection encryption
- API request/response validation
- Input sanitization and validation

**3. Network Security:**
- HTTPS/TLS for all communications
- Firewall rules for API access
- VPN for internal communications
- Regular security updates

---

## Future Enhancements

### Planned Features

**1. Advanced Clustering Algorithms:**
- Machine learning-based cluster optimization
- Dynamic cluster rebalancing
- Weather-aware scheduling
- Traffic pattern analysis

**2. Enhanced Mower Control:**
- Multi-device coordination
- Automatic error recovery
- Predictive maintenance alerts
- Battery optimization strategies

**3. User Experience:**
- Real-time notifications
- Mobile app integration
- Web dashboard improvements
- Customer support tools

**4. Analytics & Reporting:**
- Usage analytics dashboard
- Performance metrics
- Cost analysis tools
- Environmental impact tracking

### Technical Roadmap

**Phase 1 (Q1 2024):**
- ✅ Complete clustering logic migration
- ✅ Production deployment setup
- ✅ Basic monitoring and logging
- 🔄 Advanced error handling

**Phase 2 (Q2 2024):**
- 🔄 Machine learning integration
- 🔄 Real-time analytics
- 🔄 Mobile app development
- 🔄 Advanced user management

**Phase 3 (Q3 2024):**
- 🔄 Multi-tenant architecture
- 🔄 Advanced billing integration
- 🔄 IoT device integration
- 🔄 AI-powered optimization

**Phase 4 (Q4 2024):**
- 🔄 International expansion
- 🔄 Advanced security features
- 🔄 Enterprise features
- 🔄 API marketplace

### Contributing

**Development Guidelines:**
- Follow the [Development Guidelines](development-guidelines.md)
- Write comprehensive tests for new features
- Update documentation for API changes
- Use conventional commit messages

**Code Review Process:**
- All changes require pull request review
- Automated testing must pass
- Code coverage requirements enforced
- Security review for sensitive changes

**Release Process:**
- Semantic versioning for releases
- Automated deployment pipelines
- Rollback procedures documented
- Release notes for all changes

---

## Conclusion

MowthosOS represents a significant advancement in robotic mower management, combining the proven PyMammotion mower control capabilities with our integrated intelligent geographic clustering system. The proposed unified architecture provides a solid foundation for:

- **Scalable Operations**: Handle thousands of mowers and homes
- **Intelligent Automation**: Optimize routes and schedules automatically
- **User-Friendly Interface**: Simple APIs for web and mobile integration
- **Enterprise Features**: Professional monitoring, billing, and support

The migration from external submodules to integrated clustering logic has significantly improved the system's maintainability and performance, while maintaining all the advanced geographic intelligence capabilities.

For detailed technical information, see the [Development Guidelines](development-guidelines.md) and [Quick Reference](quick-reference.md) documentation.