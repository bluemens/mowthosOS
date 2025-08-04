# MowthosOS Frontend API Integration Guide for Cursor Agent

## Overview
This guide provides comprehensive instructions for integrating the MowthosOS backend API into a frontend client application. MowthosOS is a robotic lawn mower management platform that allows Hosts (with mowers) to create clusters and provide services to Neighbors (subscribers).

## Core Business Model
- **Hosts**: Own robotic mowers and create service clusters
- **Neighbors**: Subscribe to clusters for lawn mowing services  
- **Clusters**: Geographic service areas managed by hosts

## API Base Configuration

### Base URL
```
Production: https://api.mowthos.com
Development: http://localhost:8000
```

### API Versioning
All main endpoints use `/api/v1/` prefix (except health and webhook endpoints)

### Authentication
- Bearer token authentication required for most endpoints
- Tokens obtained via `/api/v1/auth/login` endpoint
- Include token in headers: `Authorization: Bearer <token>`

## API Client Structure Recommendations

### 1. Create Base API Client Class
```typescript
// Example structure for API client
class MowthosAPIClient {
  private baseURL: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  
  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }
  
  // Implement request interceptors for auth
  // Implement automatic token refresh
  // Implement error handling
}
```

### 2. Implement Module-Based Services
Create separate service classes for each API module:
- `AuthService` - Authentication & user management
- `DeviceService` - Device management (Host only)
- `MowerService` - Mower control operations
- `ClusterService` - Cluster management
- `PaymentService` - Payments & subscriptions

## API Endpoints Documentation

### Authentication Module (`/api/v1/auth`)

#### User Registration
```http
POST /api/v1/auth/register
```
**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe"
}
```
**Response:** `UserResponse` with user details

#### User Login
```http
POST /api/v1/auth/login
```
**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "device_name": "Web Browser"
}
```
**Response:** `TokenResponse` with access/refresh tokens

#### Token Refresh
```http
POST /api/v1/auth/refresh
```
**Request Body:**
```json
{
  "refresh_token": "<refresh_token>"
}
```

#### Get Current User
```http
GET /api/v1/auth/me
```
**Headers:** `Authorization: Bearer <token>`
**Response:** Current user details

#### Update Profile
```http
PUT /api/v1/auth/profile
```
**Request Body:** Partial user update fields

#### Address Management
```http
POST /api/v1/auth/addresses - Add new address
GET /api/v1/auth/addresses/home - Get home address
PUT /api/v1/auth/addresses/home - Update home address
```

### Device Management Module (`/api/v1/devices`) - HOST ONLY

#### List User Devices
```http
GET /api/v1/devices
```

#### Register Device
```http
POST /api/v1/devices/register
```
**Request Body:**
```json
{
  "mammotion_email": "user@mammotion.com",
  "mammotion_password": "password",
  "device_name": "Luba-XXXXX",
  "device_nickname": "Front Yard Mower"
}
```

#### Get Device Status
```http
GET /api/v1/devices/{device_id}/status
```

### Mower Control Module (`/api/v1/mowers`)

#### Mower Commands
```http
POST /api/v1/mowers/{device_name}/commands/start
POST /api/v1/mowers/{device_name}/commands/stop
POST /api/v1/mowers/{device_name}/commands/pause
POST /api/v1/mowers/{device_name}/commands/resume
POST /api/v1/mowers/{device_name}/commands/return
```

#### Get Mower Status
```http
GET /api/v1/mowers/{device_name}/status
```

### Cluster Management Module (`/api/v1/clusters`)

#### Create Cluster (Host only)
```http
POST /api/v1/clusters/create
```
**Request Body:**
```json
{
  "address_id": "<uuid>"
}
```

#### Join Cluster (Neighbor only)
```http
POST /api/v1/clusters/{cluster_id}/join
```
**Request Body:**
```json
{
  "address_id": "<uuid>"
}
```

#### Get Cluster Details
```http
GET /api/v1/clusters/{cluster_id}
```

#### Find Qualified Clusters for Address
```http
GET /api/v1/clusters/neighbor/{address_id}/qualified-clusters
```

#### Market Analysis
```http
GET /api/v1/clusters/{cluster_id}/market-analysis
GET /api/v1/clusters/{cluster_id}/existing-neighbors
GET /api/v1/clusters/{cluster_id}/addressable-market
```

### Payment Module (`/api/v1/payments`)

#### Get Subscription Plans
```http
GET /api/v1/payments/plans
```

#### Create Pre-Join Subscription (with 30-day trial)
```http
POST /api/v1/payments/subscriptions/pre-join
```
**Request Body:**
```json
{
  "cluster_id": "<cluster_uuid>",
  "plan_id": "<plan_uuid>",
  "payment_method_id": "<stripe_payment_method_id>",
  "address_id": "<address_uuid>"
}
```

#### Manage Payment Methods
```http
POST /api/v1/payments/payment-methods - Attach payment method
GET /api/v1/payments/payment-methods - List payment methods
```

#### Subscription Management
```http
GET /api/v1/payments/subscriptions/{subscription_id}
POST /api/v1/payments/subscriptions/{subscription_id}/cancel
POST /api/v1/payments/subscriptions/{subscription_id}/update-plan
```

## Error Handling

### Standard Error Response Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden (wrong user role)
- `404` - Not Found
- `500` - Internal Server Error

## Implementation Guidelines

### 1. Type Safety
Create TypeScript interfaces/types for all request/response models based on the Pydantic schemas:

```typescript
interface UserResponse {
  id: string;
  email: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  role: 'user' | 'neighbor' | 'host' | 'admin';
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}
```

### 2. State Management
Implement proper state management for:
- User authentication state
- Active devices and their statuses
- Cluster memberships
- Subscription status
- Payment methods

### 3. Real-time Updates
Consider implementing:
- WebSocket connections for live mower status
- Polling for device status updates
- Push notifications for mowing events

### 4. Role-Based UI/UX
Implement different UI flows based on user role:
- **Hosts**: Device management, cluster creation, analytics
- **Neighbors**: Cluster browsing, subscription management
- **Regular Users**: Can become either Host or Neighbor

### 5. Error Recovery
Implement:
- Automatic token refresh on 401 errors
- Retry logic for network failures
- Offline mode capabilities
- Graceful degradation

### 6. Security Considerations
- Never store passwords in plain text
- Use secure storage for tokens
- Implement proper CORS handling
- Validate all user inputs
- Use HTTPS in production

### 7. Testing Strategy
- Mock API responses for development
- Implement integration tests
- Test error scenarios
- Test role-based access

### 8. Performance Optimization
- Implement request caching where appropriate
- Use pagination for list endpoints
- Lazy load device statuses
- Optimize image/map data loading

## User Flow Examples

### Host Registration Flow
1. User registers account
2. User adds home address
3. User registers as Host (role change)
4. Host registers Mammotion devices
5. Host creates cluster
6. Host monitors cluster growth

### Neighbor Subscription Flow
1. User registers account
2. User adds home address
3. User searches for nearby clusters
4. User selects cluster and plan
5. User adds payment method
6. User joins cluster (30-day trial starts)
7. User receives mowing services

## Additional Considerations

### Stripe Integration
- Use Stripe Elements for payment UI
- Handle webhook events for subscription updates
- Implement proper PCI compliance

### Mapbox Integration
- Clusters use geographic boundaries
- Show service areas on maps
- Calculate distances for cluster eligibility

### Device Communication
- Devices connect via Mammotion's cloud API
- Real-time status updates available
- Command execution may have delays

## Environment Variables
Ensure the frontend has access to:
```
VITE_API_BASE_URL=http://localhost:8000
VITE_STRIPE_PUBLIC_KEY=pk_test_...
VITE_MAPBOX_TOKEN=pk_...
```

## Next Steps for Implementation
1. Set up base API client with interceptors
2. Implement authentication flow
3. Create service classes for each module
4. Build role-based routing
5. Implement core user flows
6. Add real-time features
7. Implement payment flows
8. Add analytics and monitoring