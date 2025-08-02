# MowthosOS Backend Testing Guide

## Current Implementation Status

### ✅ Completed Components

1. **API Routes**
   - ✅ Authentication (`/auth/*`) - Register, login, logout, token refresh
   - ✅ Health Check (`/health/`)
   - ✅ Mower Control (`/api/v1/mowers/*`) - Device control and status
   - ✅ Clusters (`/api/v1/clusters/*`) - Create, join, manage clusters
   - ✅ Devices (`/api/v1/devices/*`) - Register, update, maintenance tracking
   - ✅ Payments (`/api/v1/payments/*`) - Subscriptions, checkout, webhooks

2. **Database Models**
   - ✅ User management (User, Session, RefreshToken, etc.)
   - ✅ Device tracking (MowerDevice, Telemetry, Commands)
   - ✅ Clustering (Cluster, ClusterMember, Schedule)
   - ✅ Billing (Subscription, Invoice, Payment)
   - ✅ Marketplace (Product, Order)

3. **Services**
   - ✅ MowerService - Device control via PyMammotion
   - ✅ ClusterService - Geographic clustering
   - ✅ UserService - User management
   - ✅ NotificationService - Notifications
   - ✅ SchedulingService - Automated scheduling
   - ✅ StripeService - Payment processing

## Pre-Testing Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/mowthos_db

# JWT Settings
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Stripe (optional for payment testing)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Mapbox (for clustering)
MAPBOX_ACCESS_TOKEN=pk_...

# General
DEBUG=True
LOG_LEVEL=INFO
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
```

### 2. Database Setup

```bash
# Install PostgreSQL if not already installed
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE mowthos_db;
CREATE USER mowthos_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE mowthos_db TO mowthos_user;
\q

# Run migrations (if using Alembic)
alembic upgrade head
```

### 3. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Backend

```bash
# Start the FastAPI server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Or using the run script
python run.py
```

## Testing the API

### Option 1: Use the Test Script

```bash
# Make the test script executable
chmod +x test_api_routes.py

# Run the test script
python test_api_routes.py
```

### Option 2: Use FastAPI Interactive Docs

1. Start the server
2. Navigate to http://localhost:8000/docs
3. Test endpoints interactively

### Option 3: Manual cURL Testing

```bash
# Health check
curl http://localhost:8000/health/

# Register user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPassword123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPassword123"}'
```

## What's Missing Before Production

1. **Environment Configuration**
   - ❌ Proper secrets management
   - ❌ Production database configuration
   - ❌ Redis for caching
   - ❌ SSL/TLS setup

2. **Error Handling**
   - ❌ Global exception handlers
   - ❌ Proper logging configuration
   - ❌ Request validation middleware

3. **Testing**
   - ❌ Unit tests for services
   - ❌ Integration tests for routes
   - ❌ End-to-end tests

4. **DevOps**
   - ❌ Docker configuration
   - ❌ CI/CD pipeline
   - ❌ Monitoring and alerting

## Frontend Integration Points

The backend is ready for frontend integration with the following endpoints:

### Authentication Flow
1. `POST /auth/register` - User registration
2. `POST /auth/login` - User login (returns JWT tokens)
3. `GET /auth/me` - Get current user info
4. `POST /auth/refresh` - Refresh access token

### Main Features
1. **Mower Control**: `/api/v1/mowers/*`
2. **Cluster Management**: `/api/v1/clusters/*`
3. **Device Management**: `/api/v1/devices/*`
4. **Payments**: `/api/v1/payments/*`

### Headers Required
For authenticated endpoints, include:
```
Authorization: Bearer <access_token>
```

## Next Steps

1. **Set up environment variables** based on the template above
2. **Initialize the database** with proper schema
3. **Run the test script** to verify all endpoints
4. **Connect frontend** to the API endpoints
5. **Implement remaining features** as needed

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all dependencies are installed
2. **Database connection**: Check DATABASE_URL is correct
3. **Auth failures**: Verify JWT secrets are set
4. **CORS errors**: Update ALLOWED_ORIGINS in settings

### Debug Mode

Enable debug logging:
```python
# In .env
DEBUG=True
LOG_LEVEL=DEBUG
```

View logs:
```bash
tail -f logs/app.log  # If logging to file
```