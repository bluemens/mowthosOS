# Mammotion Mower Control API

A FastAPI microservice that provides a REST API interface to the PyMammotion library for controlling Mammotion robotic mowers.

## Features

- **Authentication**: Login to Mammotion cloud service
- **Device Management**: List and manage multiple mower devices
- **Status Monitoring**: Get real-time mower status including battery, work mode, and location
- **Mowing Control**: Start, stop, pause, and resume mowing operations
- **Dock Control**: Command mower to return to charging dock
- **Session Management**: Maintain user sessions for device control

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the FastAPI server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication

#### POST /login
Login to Mammotion cloud and initialize device connection.

**Request Body:**
```json
{
  "account": "your_email@example.com",
  "password": "your_password",
  "device_name": "Luba-XXXXX"  // Optional: specific device name
}
```

**Response:**
```json
{
  "success": true,
  "message": "Login successful",
  "device_name": "Luba-XXXXX",
  "session_id": "your_email@example.com_1234567890.123"
}
```

### Device Status

#### GET /status?device_name=Luba-XXXXX
Get the current status of a mower device.

**Response:**
```json
{
  "device_name": "Luba-XXXXX",
  "online": true,
  "work_mode": "MODE_WORKING",
  "work_mode_code": 13,
  "battery_level": 85,
  "charging_state": 0,
  "blade_status": true,
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "position_type": 1,
    "orientation": 90
  },
  "work_progress": 45,
  "work_area": 150,
  "last_updated": "2024-01-15T10:30:00"
}
```

### Mowing Control

#### POST /start-mow
Start mowing operation.

**Request Body:**
```json
{
  "device_name": "Luba-XXXXX"
}
```

#### POST /stop-mow
Stop mowing operation.

#### POST /pause-mowing
Pause the current mowing operation.

#### POST /resume-mowing
Resume a paused mowing operation.

#### POST /return-to-dock
Send mower back to charging dock.

### Device Management

#### GET /devices
List all available devices for the current session.

**Response:**
```json
{
  "devices": [
    {
      "name": "Luba-XXXXX",
      "iot_id": "device_iot_id",
      "preference": "ConnectionPreference.WIFI",
      "has_cloud": true,
      "has_ble": false
    }
  ]
}
```

### Health Check

#### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "service": "Mammotion Mower Control API"
}
```

## Work Modes

The API uses the following work mode codes from the Mammotion system:

- `0`: MODE_NOT_ACTIVE
- `1`: MODE_ONLINE
- `2`: MODE_OFFLINE
- `8`: MODE_DISABLE
- `10`: MODE_INITIALIZATION
- `11`: MODE_READY
- `13`: MODE_WORKING
- `14`: MODE_RETURNING
- `15`: MODE_CHARGING
- `16`: MODE_UPDATING
- `17`: MODE_LOCK
- `19`: MODE_PAUSE
- `20`: MODE_MANUAL_MOWING

## Usage Example

```python
import requests

# Login to the service
login_response = requests.post("http://localhost:8000/login", json={
    "account": "your_email@example.com",
    "password": "your_password"
})

# Get device status
status_response = requests.get("http://localhost:8000/status?device_name=Luba-XXXXX")
print(status_response.json())

# Start mowing
start_response = requests.post("http://localhost:8000/start-mow", json={
    "device_name": "Luba-XXXXX"
})

# Stop mowing
stop_response = requests.post("http://localhost:8000/stop-mow", json={
    "device_name": "Luba-XXXXX"
})
```

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized (login failed)
- `404`: Not Found (device not found)
- `500`: Internal Server Error

## Security Notes

- This is a basic implementation without authentication/authorization
- In production, implement proper security measures
- Consider using HTTPS in production
- Add rate limiting and input validation as needed

## Dependencies

- `fastapi`: Web framework for building APIs
- `uvicorn`: ASGI server for running FastAPI
- `pydantic`: Data validation using Python type annotations
- `pymammotion`: Mammotion robotic mower control library 