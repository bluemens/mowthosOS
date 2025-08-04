# MowthosOS Frontend Implementation Guide

This guide shows how to integrate the MowthosOS API into your frontend application using the provided configuration and client setup.

## Quick Start

### 1. Environment Setup

Create a `.env.local` file in your project root:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STRIPE_PUBLIC_KEY=pk_test_your_key_here
VITE_MAPBOX_TOKEN=pk.your_token_here
```

### 2. Install Dependencies

```bash
npm install axios
npm install --save-dev @types/axios

# Optional but recommended
npm install @sentry/react  # For error tracking
npm install react-query    # For data fetching
```

### 3. Copy Required Files

Copy these files from the docs folder to your project:
- `frontend-api-types.ts` → `src/api/types.ts`
- `frontend-api-types-extended.ts` → `src/api/types-extended.ts`
- `frontend-api-client-example-updated.ts` → `src/api/client.ts`
- `frontend-api-configuration.ts` → `src/api/config.ts`

### 4. Basic Implementation

#### Option A: React Context Pattern (Recommended)

**In your main App component:**

```typescript
// src/App.tsx
import React from 'react';
import { APIProvider } from './api/config';
import { Router } from './Router';

function App() {
  return (
    <APIProvider>
      <Router />
    </APIProvider>
  );
}

export default App;
```

**Using the API client in components:**

```typescript
// src/components/LoginForm.tsx
import React, { useState } from 'react';
import { useAPIClient } from '../api/config';
import { useNavigate } from 'react-router-dom';

function LoginForm() {
  const api = useAPIClient();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Login
      const response = await api.auth.login(email, password);
      
      // Get user info
      const user = await api.auth.getCurrentUser();
      
      // Redirect based on role
      if (user.role === 'host') {
        navigate('/host/dashboard');
      } else if (user.role === 'neighbor') {
        navigate('/neighbor/dashboard');
      } else {
        navigate('/onboarding');
      }
    } catch (error) {
      if (error instanceof APIError) {
        setError(error.message);
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
    </form>
  );
}
```

#### Option B: Singleton Pattern

**Setup:**

```typescript
// src/api/index.ts
import { getAPIClient } from './config';

export const api = getAPIClient();
```

**Usage:**

```typescript
// src/services/auth.ts
import { api } from '../api';

export async function loginUser(email: string, password: string) {
  const response = await api.auth.login(email, password);
  return response;
}

export async function getCurrentUser() {
  return await api.auth.getCurrentUser();
}
```

### 5. Complete Example: Host Device Management

```typescript
// src/pages/host/DeviceManagement.tsx
import React, { useState, useEffect } from 'react';
import { useAPIClient } from '../../api/config';
import { DeviceResponse, APIError } from '../../api/types';

function DeviceManagement() {
  const api = useAPIClient();
  const [devices, setDevices] = useState<DeviceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load devices
  useEffect(() => {
    loadDevices();
  }, []);

  const loadDevices = async () => {
    try {
      setLoading(true);
      const deviceList = await api.devices.listDevices();
      setDevices(deviceList);
    } catch (error) {
      if (error instanceof APIError) {
        setError(error.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleStartMowing = async (deviceName: string) => {
    try {
      await api.mowers.startMowing(deviceName);
      // Update device status
      await loadDevices();
    } catch (error) {
      console.error('Failed to start mowing:', error);
    }
  };

  const handleRegisterDevice = async () => {
    // Show modal to collect Mammotion credentials
    const credentials = await showDeviceRegistrationModal();
    
    try {
      const newDevice = await api.devices.registerDevice({
        mammotion_email: credentials.email,
        mammotion_password: credentials.password,
        device_name: credentials.deviceName,
        device_nickname: credentials.nickname
      });
      
      // Add to list
      setDevices([...devices, newDevice]);
    } catch (error) {
      if (error instanceof APIError && error.statusCode === 400) {
        // Handle validation errors
        console.error('Registration failed:', error.details);
      }
    }
  };

  if (loading) return <div>Loading devices...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h1>My Devices</h1>
      <button onClick={handleRegisterDevice}>Add Device</button>
      
      <div className="device-grid">
        {devices.map(device => (
          <DeviceCard
            key={device.id}
            device={device}
            onStart={() => handleStartMowing(device.device_name)}
          />
        ))}
      </div>
    </div>
  );
}
```

### 6. Error Handling Pattern

```typescript
// src/hooks/useAPICall.ts
import { useState, useCallback } from 'react';
import { APIError } from '../api/types-extended';

interface UseAPICallResult<T> {
  data: T | null;
  error: APIError | null;
  loading: boolean;
  execute: (...args: any[]) => Promise<T | null>;
  reset: () => void;
}

export function useAPICall<T>(
  apiCall: (...args: any[]) => Promise<T>
): UseAPICallResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<APIError | null>(null);
  const [loading, setLoading] = useState(false);

  const execute = useCallback(async (...args: any[]) => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiCall(...args);
      setData(result);
      return result;
    } catch (err) {
      const apiError = err instanceof APIError ? err : 
        new APIError('An unexpected error occurred', 500);
      setError(apiError);
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, execute, reset };
}

// Usage
function MyComponent() {
  const api = useAPIClient();
  const { data: user, error, loading, execute: loadUser } = useAPICall(
    api.auth.getCurrentUser
  );

  useEffect(() => {
    loadUser();
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorAlert error={error} />;
  if (!user) return null;

  return <UserProfile user={user} />;
}
```

### 7. Payment Integration Example

```typescript
// src/pages/neighbor/JoinCluster.tsx
import React from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { useAPIClient } from '../../api/config';

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY);

function JoinClusterForm({ clusterId, planId, addressId }) {
  const api = useAPIClient();
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setLoading(true);

    try {
      // Create payment method
      const { error, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: elements.getElement(CardElement)!,
      });

      if (error) throw error;

      // Create subscription and join cluster
      const subscription = await api.payments.createPreJoinSubscription({
        cluster_id: clusterId,
        plan_id: planId,
        payment_method_id: paymentMethod.id,
        address_id: addressId
      });

      // Success! Redirect to dashboard
      window.location.href = '/neighbor/dashboard';
    } catch (error) {
      console.error('Failed to join cluster:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <CardElement />
      <button type="submit" disabled={!stripe || loading}>
        Start 30-Day Free Trial
      </button>
    </form>
  );
}

export function JoinClusterPage() {
  return (
    <Elements stripe={stripePromise}>
      <JoinClusterForm {...props} />
    </Elements>
  );
}
```

### 8. Real-time Updates (Optional)

```typescript
// src/hooks/useDeviceStatus.ts
import { useState, useEffect } from 'react';
import { useAPIClient } from '../api/config';

export function useDeviceStatus(deviceId: string, pollingInterval = 30000) {
  const api = useAPIClient();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const fetchStatus = async () => {
      try {
        const newStatus = await api.devices.getDeviceStatus(deviceId);
        setStatus(newStatus);
      } catch (err) {
        setError(err);
      }
    };

    // Initial fetch
    fetchStatus();

    // Set up polling
    intervalId = setInterval(fetchStatus, pollingInterval);

    return () => clearInterval(intervalId);
  }, [deviceId, pollingInterval]);

  return { status, error, refetch: fetchStatus };
}
```

## Deployment Checklist

- [ ] Update environment variables for production
- [ ] Enable HTTPS for production API calls
- [ ] Configure CORS settings on backend
- [ ] Set up error tracking (Sentry)
- [ ] Configure secure token storage
- [ ] Test all user flows
- [ ] Implement proper loading states
- [ ] Add error boundaries
- [ ] Test offline functionality
- [ ] Verify Stripe webhook handling

## Common Issues & Solutions

### CORS Errors
Ensure your backend allows requests from your frontend domain:
```typescript
// Backend should include your frontend URL in CORS origins
BACKEND_CORS_ORIGINS=["http://localhost:3000", "https://app.mowthos.com"]
```

### Token Expiry
The client automatically handles token refresh. If issues persist:
```typescript
// Manually refresh
await api.auth.logout();
await api.auth.login(email, password);
```

### Type Errors
Ensure all type files are properly imported:
```typescript
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

## Support

For additional help:
- Review the API documentation in `frontend-api-integration-guide.md`
- Check type definitions in `frontend-api-types.ts`
- Refer to example implementations in `frontend-api-client-example.ts`