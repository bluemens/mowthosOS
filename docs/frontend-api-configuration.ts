/**
 * MowthosOS Frontend API Configuration
 * 
 * This file provides a complete configuration setup for the frontend API client
 */

import { APIClientConfig } from './frontend-api-types-extended';

// ==================== Environment Configuration ====================

interface EnvironmentConfig {
  API_BASE_URL: string;
  STRIPE_PUBLIC_KEY: string;
  MAPBOX_TOKEN: string;
  SENTRY_DSN?: string;
  ENVIRONMENT: 'development' | 'staging' | 'production';
  ENABLE_DEBUG_LOGGING: boolean;
}

// Get environment configuration
function getEnvironmentConfig(): EnvironmentConfig {
  // For Vite projects
  if (typeof import.meta !== 'undefined' && import.meta.env) {
    return {
      API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
      STRIPE_PUBLIC_KEY: import.meta.env.VITE_STRIPE_PUBLIC_KEY || '',
      MAPBOX_TOKEN: import.meta.env.VITE_MAPBOX_TOKEN || '',
      SENTRY_DSN: import.meta.env.VITE_SENTRY_DSN,
      ENVIRONMENT: import.meta.env.MODE as any || 'development',
      ENABLE_DEBUG_LOGGING: import.meta.env.DEV || false
    };
  }
  
  // For CRA or other webpack projects
  return {
    API_BASE_URL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
    STRIPE_PUBLIC_KEY: process.env.REACT_APP_STRIPE_PUBLIC_KEY || '',
    MAPBOX_TOKEN: process.env.REACT_APP_MAPBOX_TOKEN || '',
    SENTRY_DSN: process.env.REACT_APP_SENTRY_DSN,
    ENVIRONMENT: (process.env.NODE_ENV as any) || 'development',
    ENABLE_DEBUG_LOGGING: process.env.NODE_ENV === 'development'
  };
}

// ==================== Token Storage Implementation ====================

class SecureTokenStorage {
  private static ACCESS_TOKEN_KEY = 'mowthos_access_token';
  private static REFRESH_TOKEN_KEY = 'mowthos_refresh_token';
  private static TOKEN_EXPIRY_KEY = 'mowthos_token_expiry';

  static async getAccessToken(): Promise<string | null> {
    try {
      // Check if token is expired
      const expiry = localStorage.getItem(this.TOKEN_EXPIRY_KEY);
      if (expiry && new Date(expiry) < new Date()) {
        await this.clearTokens();
        return null;
      }
      
      return localStorage.getItem(this.ACCESS_TOKEN_KEY);
    } catch (error) {
      console.error('Failed to get access token:', error);
      return null;
    }
  }

  static async getRefreshToken(): Promise<string | null> {
    try {
      return localStorage.getItem(this.REFRESH_TOKEN_KEY);
    } catch (error) {
      console.error('Failed to get refresh token:', error);
      return null;
    }
  }

  static async setTokens(accessToken: string, refreshToken: string, expiresIn?: number): Promise<void> {
    try {
      localStorage.setItem(this.ACCESS_TOKEN_KEY, accessToken);
      localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);
      
      // Set token expiry if provided (expiresIn is in seconds)
      if (expiresIn) {
        const expiry = new Date();
        expiry.setSeconds(expiry.getSeconds() + expiresIn);
        localStorage.setItem(this.TOKEN_EXPIRY_KEY, expiry.toISOString());
      }
    } catch (error) {
      console.error('Failed to store tokens:', error);
      throw error;
    }
  }

  static async clearTokens(): Promise<void> {
    try {
      localStorage.removeItem(this.ACCESS_TOKEN_KEY);
      localStorage.removeItem(this.REFRESH_TOKEN_KEY);
      localStorage.removeItem(this.TOKEN_EXPIRY_KEY);
    } catch (error) {
      console.error('Failed to clear tokens:', error);
    }
  }
}

// ==================== Logger Implementation ====================

class APILogger {
  private isDevelopment: boolean;
  private sentryEnabled: boolean;

  constructor(isDevelopment: boolean, sentryDSN?: string) {
    this.isDevelopment = isDevelopment;
    this.sentryEnabled = !!sentryDSN;
    
    // Initialize Sentry if DSN provided
    if (this.sentryEnabled && typeof window !== 'undefined' && (window as any).Sentry) {
      (window as any).Sentry.init({
        dsn: sentryDSN,
        environment: isDevelopment ? 'development' : 'production',
        tracesSampleRate: isDevelopment ? 1.0 : 0.1,
      });
    }
  }

  debug(message: string, ...args: any[]): void {
    if (this.isDevelopment) {
      console.debug(`[MowthosAPI] ${message}`, ...args);
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.isDevelopment) {
      console.info(`[MowthosAPI] ${message}`, ...args);
    }
  }

  warn(message: string, ...args: any[]): void {
    console.warn(`[MowthosAPI] ${message}`, ...args);
    
    if (this.sentryEnabled && (window as any).Sentry) {
      (window as any).Sentry.captureMessage(message, 'warning');
    }
  }

  error(message: string, error?: any, ...args: any[]): void {
    console.error(`[MowthosAPI] ${message}`, error, ...args);
    
    if (this.sentryEnabled && (window as any).Sentry) {
      (window as any).Sentry.captureException(error || new Error(message));
    }
  }
}

// ==================== Main Configuration Factory ====================

export function createAPIClientConfig(): APIClientConfig {
  const env = getEnvironmentConfig();
  const logger = new APILogger(env.ENABLE_DEBUG_LOGGING, env.SENTRY_DSN);

  const config: APIClientConfig = {
    // Base configuration
    baseURL: env.API_BASE_URL,
    timeout: env.ENVIRONMENT === 'production' ? 60000 : 30000,
    withCredentials: true, // Enable cookies for CSRF protection
    
    // Default headers
    headers: {
      'X-Client-Version': '1.0.0',
      'X-Client-Platform': 'web',
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    
    // Token storage
    tokenStorage: {
      getAccessToken: () => SecureTokenStorage.getAccessToken(),
      getRefreshToken: () => SecureTokenStorage.getRefreshToken(),
      setTokens: (access, refresh) => SecureTokenStorage.setTokens(access, refresh),
      clearTokens: () => SecureTokenStorage.clearTokens()
    },
    
    // Logger
    logger: {
      debug: (msg, ...args) => logger.debug(msg, ...args),
      info: (msg, ...args) => logger.info(msg, ...args),
      warn: (msg, ...args) => logger.warn(msg, ...args),
      error: (msg, ...args) => logger.error(msg, args[0], ...args.slice(1))
    },
    
    // Retry configuration
    retry: {
      enabled: true,
      maxAttempts: env.ENVIRONMENT === 'production' ? 3 : 2,
      backoffMultiplier: 2,
      retryableStatuses: [408, 429, 500, 502, 503, 504]
    },
    
    // Request interceptor
    onRequest: async (config) => {
      // Add request ID for tracking
      config.headers['X-Request-ID'] = generateRequestId();
      
      // Add timestamp
      config.headers['X-Request-Timestamp'] = new Date().toISOString();
      
      return config;
    },
    
    // Response error interceptor
    onResponseError: async (error) => {
      // Log to analytics/monitoring service
      if (typeof window !== 'undefined' && (window as any).analytics) {
        (window as any).analytics.track('API Error', {
          endpoint: error.config?.url,
          status: error.response?.status,
          message: error.message
        });
      }
      
      // Return the error to be handled by the caller
      return Promise.reject(error);
    }
  };

  return config;
}

// ==================== Helper Functions ====================

function generateRequestId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// ==================== Environment-Specific Configurations ====================

export const API_CONFIGS = {
  development: {
    baseURL: 'http://localhost:8000',
    timeout: 30000,
    enableDebug: true
  },
  staging: {
    baseURL: 'https://staging-api.mowthos.com',
    timeout: 45000,
    enableDebug: true
  },
  production: {
    baseURL: 'https://api.mowthos.com',
    timeout: 60000,
    enableDebug: false
  }
} as const;

// ==================== React Integration ====================

import { createContext, useContext, ReactNode, useMemo } from 'react';
import MowthosAPIClient from './frontend-api-client-example-updated';

// Create context
const APIContext = createContext<MowthosAPIClient | null>(null);

// Provider component
export function APIProvider({ children }: { children: ReactNode }) {
  const apiClient = useMemo(() => {
    const config = createAPIClientConfig();
    return new MowthosAPIClient(config);
  }, []);

  return (
    <APIContext.Provider value={apiClient}>
      {children}
    </APIContext.Provider>
  );
}

// Hook to use API client
export function useAPIClient(): MowthosAPIClient {
  const client = useContext(APIContext);
  if (!client) {
    throw new Error('useAPIClient must be used within APIProvider');
  }
  return client;
}

// ==================== Singleton Pattern (Alternative) ====================

let apiClientInstance: MowthosAPIClient | null = null;

export function getAPIClient(): MowthosAPIClient {
  if (!apiClientInstance) {
    const config = createAPIClientConfig();
    apiClientInstance = new MowthosAPIClient(config);
  }
  return apiClientInstance;
}

// Reset client (useful for testing or logout)
export function resetAPIClient(): void {
  if (apiClientInstance) {
    apiClientInstance.clearTokens();
    apiClientInstance = null;
  }
}

// ==================== Export Configuration ====================

export default {
  createConfig: createAPIClientConfig,
  getClient: getAPIClient,
  resetClient: resetAPIClient,
  APIProvider,
  useAPIClient,
  SecureTokenStorage,
  APILogger
};