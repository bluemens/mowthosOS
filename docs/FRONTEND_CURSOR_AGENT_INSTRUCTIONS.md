# Frontend Cursor Agent Instructions: MowthosOS API Integration

## Your Mission
You are tasked with integrating the MowthosOS backend API into a frontend client application. MowthosOS is a platform that connects robotic lawn mower owners (Hosts) with neighbors who need lawn care services (Neighbors) through geographic clusters.

## Context and Architecture Understanding

### Business Model
1. **Users** start as basic users who can explore the platform
2. **Hosts** own robotic mowers and create service clusters in their area
3. **Neighbors** subscribe to clusters for automated lawn mowing services
4. **Clusters** are geographic service areas with a max of 10 members

### Key Technical Details
- RESTful API with `/api/v1/` prefix for main endpoints
- Bearer token authentication (JWT)
- Stripe integration for payments
- Mapbox integration for geographic features
- Real-time device status updates from Mammotion cloud

## Implementation Requirements

### 1. API Client Architecture
Create a modular, type-safe API client with:
- Centralized authentication handling with automatic token refresh
- Service-based organization (AuthService, DeviceService, etc.)
- Proper error handling and retry logic
- TypeScript interfaces for all request/response types

**Reference the provided files:**
- `frontend-api-types.ts` - Complete TypeScript type definitions
- `frontend-api-client-example.ts` - Example implementation pattern
- `frontend-api-integration-guide.md` - Detailed endpoint documentation

### 2. Authentication Flow Implementation
1. Implement secure token storage (consider using secure storage libraries, not just localStorage)
2. Add request interceptors to automatically include Bearer tokens
3. Handle 401 responses with automatic token refresh
4. Implement logout that clears all stored credentials
5. Add session persistence across page refreshes

### 3. Role-Based Features
Implement different UI/UX flows based on user roles:

**For Basic Users:**
- Registration and profile setup
- Address management
- Role selection (become Host or Neighbor)

**For Hosts:**
- Device registration from Mammotion account
- Cluster creation with market analysis
- Real-time mower status monitoring
- Command controls (start/stop/pause/resume/return)
- Member management and analytics

**For Neighbors:**
- Cluster discovery based on address
- Subscription plan selection
- Payment method management
- Service scheduling preferences

### 4. Critical User Flows to Implement

#### Host Onboarding Flow:
```
1. User registers → adds address → asks property questions -> connections Mammotion Account -> creates cluster -> launches host dashboard
2. Host connects Mammotion account
3. Host registers devices (mowers)
4. Host creates cluster (automatic market analysis)
5. Host monitors cluster growth and operations
```

#### Neighbor Subscription Flow:
```
1. User registers → adds address -> selects pricing plan -> views potential clusters -> joins cluster -> launches subscriber dashboard
2. System finds qualified clusters within range
3. User views plans and selects subscription
4. User adds payment method (Stripe)
5. User joins cluster (30-day free trial starts)
6. User becomes active member after trial
7. User can schedule reoccuring mows and monitor mower progress
```

### 5. Payment Integration Requirements
- Use Stripe Elements for secure payment form
- Implement subscription management with trial periods
- Handle webhook events for subscription updates
- Provide access to Stripe billing portal
- Show clear subscription status and trial information

## Key API Endpoints Summary

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Token refresh
- `GET /api/v1/auth/me` - Current user info
- `POST /api/v1/auth/addresses` - Add address

### Devices (Host only)
- `GET /api/v1/devices` - List user devices
- `POST /api/v1/devices/register` - Register device
- `GET /api/v1/devices/{id}/status` - Device status

### Mower Control
- `GET /api/v1/mowers/{name}/status` - Mower status
- `POST /api/v1/mowers/{name}/commands/*` - Mower commands

### Clusters
- `POST /api/v1/clusters/create` - Create cluster
- `POST /api/v1/clusters/{id}/join` - Join cluster
- `GET /api/v1/clusters/{id}` - Cluster details
- `GET /api/v1/clusters/neighbor/{addressId}/qualified-clusters` - Find clusters

### Payments
- `GET /api/v1/payments/plans` - Subscription plans
- `POST /api/v1/payments/subscriptions/pre-join` - Create subscription
- `POST /api/v1/payments/payment-methods` - Add payment method


## Development Workflow
1. Start with authentication implementation
2. Build role-based routing and guards
3. Implement core user flows one at a time
4. Add real-time features incrementally
5. Implement payment flows with test mode
6. Add analytics and monitoring
7. Optimize performance
8. Comprehensive testing

## Additional Resources
-Ask questions for unclear decisions

## Success Criteria
- Type-safe API integration with full TypeScript support
- Smooth authentication with automatic token management
- Role-appropriate UI/UX for all user types
- Reliable payment processing with clear trial handling
- Real-time updates for device status
- Comprehensive error handling
- Performance optimized for mobile and desktop
- Well-tested and documented code

Remember: Focus on creating a seamless experience that makes the complex backend functionality feel simple and intuitive to users. The API client should abstract away complexity while maintaining flexibility for future features.