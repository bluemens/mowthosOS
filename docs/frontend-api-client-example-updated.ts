/**
 * Updated MowthosOS API Client Example with Extended Types
 * 
 * This example shows how to use the error, config, and response types properly
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { 
  APIClientConfig,
  APIError,
  NetworkError,
  APIResponse,
  APIRequestOptions,
  TokenResponse,
  UserResponse,
  APIErrorResponse
} from './frontend-api-types-extended';

// ==================== Enhanced API Client ====================

export class MowthosAPIClient {
  private axiosInstance: AxiosInstance;
  private config: APIClientConfig;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private tokenRefreshPromise: Promise<void> | null = null;

  constructor(config: APIClientConfig) {
    this.config = config;
    
    // Create axios instance with config
    this.axiosInstance = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        ...config.headers
      },
      withCredentials: config.withCredentials || false
    });

    this.setupInterceptors();
    this.loadTokens();
  }

  private setupInterceptors(): void {
    // Request interceptor
    this.axiosInstance.interceptors.request.use(
      async (config) => {
        // Custom request interceptor
        if (this.config.onRequest) {
          config = await this.config.onRequest(config);
        }

        // Add auth token
        const token = await this.getAccessToken();
        if (token && !config.headers['Authorization']) {
          config.headers['Authorization'] = `Bearer ${token}`;
        }

        // Log request
        this.log('debug', `API Request: ${config.method?.toUpperCase()} ${config.url}`);
        
        return config;
      },
      (error) => {
        if (this.config.onRequestError) {
          return this.config.onRequestError(error);
        }
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.axiosInstance.interceptors.response.use(
      async (response) => {
        // Custom response interceptor
        if (this.config.onResponse) {
          response = await this.config.onResponse(response);
        }

        // Log response
        this.log('debug', `API Response: ${response.status} ${response.config.url}`);
        
        return response;
      },
      async (error: AxiosError<APIErrorResponse>) => {
        // Handle network errors
        if (!error.response) {
          this.log('error', 'Network error occurred', error);
          return Promise.reject(new NetworkError(error.message));
        }

        // Handle 401 and token refresh
        if (error.response.status === 401 && !error.config?._retry) {
          error.config._retry = true;
          
          if (this.refreshToken && !error.config.url?.includes('/refresh')) {
            if (!this.tokenRefreshPromise) {
              this.tokenRefreshPromise = this.refreshAccessToken();
            }
            
            try {
              await this.tokenRefreshPromise;
              this.tokenRefreshPromise = null;
              
              // Retry original request
              return this.axiosInstance(error.config);
            } catch (refreshError) {
              this.tokenRefreshPromise = null;
              await this.clearTokens();
              
              // Custom error handler or redirect
              if (this.config.onResponseError) {
                return this.config.onResponseError(refreshError);
              }
              
              return Promise.reject(refreshError);
            }
          }
        }

        // Convert to APIError
        const apiError = APIError.fromAxiosError(error);
        this.log('error', `API Error: ${apiError.statusCode} ${apiError.message}`);

        // Custom error handler
        if (this.config.onResponseError) {
          return this.config.onResponseError(apiError);
        }

        return Promise.reject(apiError);
      }
    );
  }

  private async refreshAccessToken(): Promise<void> {
    try {
      const refreshToken = await this.getRefreshToken();
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await axios.post<TokenResponse>(
        `${this.config.baseURL}/api/v1/auth/refresh`,
        { refresh_token: refreshToken }
      );
      
      await this.setTokens(response.data.access_token, response.data.refresh_token);
      this.log('info', 'Token refreshed successfully');
    } catch (error) {
      this.log('error', 'Failed to refresh token', error);
      throw error;
    }
  }

  // Token management methods
  private async getAccessToken(): Promise<string | null> {
    if (this.config.tokenStorage?.getAccessToken) {
      return await this.config.tokenStorage.getAccessToken();
    }
    return this.accessToken;
  }

  private async getRefreshToken(): Promise<string | null> {
    if (this.config.tokenStorage?.getRefreshToken) {
      return await this.config.tokenStorage.getRefreshToken();
    }
    return this.refreshToken;
  }

  public async setTokens(accessToken: string, refreshToken: string): Promise<void> {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    
    if (this.config.tokenStorage?.setTokens) {
      await this.config.tokenStorage.setTokens(accessToken, refreshToken);
    } else {
      // Default storage
      localStorage.setItem('mowthos_access_token', accessToken);
      localStorage.setItem('mowthos_refresh_token', refreshToken);
    }
  }

  public async clearTokens(): Promise<void> {
    this.accessToken = null;
    this.refreshToken = null;
    
    if (this.config.tokenStorage?.clearTokens) {
      await this.config.tokenStorage.clearTokens();
    } else {
      localStorage.removeItem('mowthos_access_token');
      localStorage.removeItem('mowthos_refresh_token');
    }
  }

  private async loadTokens(): Promise<void> {
    if (this.config.tokenStorage) {
      this.accessToken = await this.config.tokenStorage.getAccessToken();
      this.refreshToken = await this.config.tokenStorage.getRefreshToken();
    } else {
      this.accessToken = localStorage.getItem('mowthos_access_token');
      this.refreshToken = localStorage.getItem('mowthos_refresh_token');
    }
  }

  // Logging helper
  private log(level: keyof NonNullable<APIClientConfig['logger']>, message: string, ...args: any[]): void {
    if (this.config.logger?.[level]) {
      this.config.logger[level](message, ...args);
    } else if (process.env.NODE_ENV === 'development') {
      console[level](message, ...args);
    }
  }

  // Generic request method with proper typing
  public async request<T = any>(
    method: string,
    url: string,
    data?: any,
    options?: APIRequestOptions
  ): Promise<APIResponse<T>> {
    try {
      const response = await this.axiosInstance.request<T>({
        method,
        url,
        data,
        ...options
      });

      return {
        data: response.data,
        status: response.status,
        statusText: response.statusText,
        headers: response.headers as Record<string, string>,
        config: response.config,
        request: response.request
      };
    } catch (error) {
      // Error is already transformed by interceptor
      throw error;
    }
  }

  // Convenience methods
  public async get<T = any>(url: string, options?: APIRequestOptions): Promise<APIResponse<T>> {
    return this.request<T>('GET', url, undefined, options);
  }

  public async post<T = any>(url: string, data?: any, options?: APIRequestOptions): Promise<APIResponse<T>> {
    return this.request<T>('POST', url, data, options);
  }

  public async put<T = any>(url: string, data?: any, options?: APIRequestOptions): Promise<APIResponse<T>> {
    return this.request<T>('PUT', url, data, options);
  }

  public async patch<T = any>(url: string, data?: any, options?: APIRequestOptions): Promise<APIResponse<T>> {
    return this.request<T>('PATCH', url, data, options);
  }

  public async delete<T = any>(url: string, options?: APIRequestOptions): Promise<APIResponse<T>> {
    return this.request<T>('DELETE', url, undefined, options);
  }
}

// ==================== Usage Examples ====================

// 1. Basic configuration
const basicClient = new MowthosAPIClient({
  baseURL: 'http://localhost:8000'
});

// 2. Advanced configuration with custom token storage
const advancedClient = new MowthosAPIClient({
  baseURL: 'http://localhost:8000',
  timeout: 15000,
  
  // Custom token storage (e.g., using secure storage)
  tokenStorage: {
    getAccessToken: async () => {
      // Use secure storage library
      return await SecureStore.getItem('access_token');
    },
    getRefreshToken: async () => {
      return await SecureStore.getItem('refresh_token');
    },
    setTokens: async (access, refresh) => {
      await SecureStore.setItem('access_token', access);
      await SecureStore.setItem('refresh_token', refresh);
    },
    clearTokens: async () => {
      await SecureStore.removeItem('access_token');
      await SecureStore.removeItem('refresh_token');
    }
  },
  
  // Custom logger
  logger: {
    debug: (msg, ...args) => console.debug(`[API] ${msg}`, ...args),
    info: (msg, ...args) => console.info(`[API] ${msg}`, ...args),
    warn: (msg, ...args) => console.warn(`[API] ${msg}`, ...args),
    error: (msg, ...args) => console.error(`[API] ${msg}`, ...args)
  },
  
  // Retry configuration
  retry: {
    enabled: true,
    maxAttempts: 3,
    backoffMultiplier: 2,
    retryableStatuses: [408, 429, 500, 502, 503, 504]
  }
});

// 3. Making requests with proper error handling
async function exampleUsage() {
  const client = new MowthosAPIClient({
    baseURL: 'http://localhost:8000'
  });
  
  try {
    // Login request
    const loginResponse = await client.post<TokenResponse>('/api/v1/auth/login', {
      email: 'user@example.com',
      password: 'password'
    });
    
    // Set tokens from response
    await client.setTokens(
      loginResponse.data.access_token,
      loginResponse.data.refresh_token
    );
    
    // Get user profile (authenticated request)
    const userResponse = await client.get<UserResponse>('/api/v1/auth/me');
    console.log('Current user:', userResponse.data);
    
    // Handle different response types
    const { data, status, headers } = userResponse;
    console.log('Status:', status);
    console.log('Headers:', headers);
    
  } catch (error) {
    if (error instanceof APIError) {
      // Handle API errors
      console.error(`API Error ${error.statusCode}: ${error.message}`);
      console.error('Error details:', error.details);
      console.error('Request ID:', error.requestId);
      
      // Handle specific error codes
      switch (error.statusCode) {
        case 400:
          // Handle validation errors
          if (error.details?.detail && Array.isArray(error.details.detail)) {
            error.details.detail.forEach((validationError: any) => {
              console.error(`Field ${validationError.loc.join('.')}: ${validationError.msg}`);
            });
          }
          break;
        case 401:
          // Handle authentication errors
          console.error('Authentication failed');
          break;
        case 403:
          // Handle authorization errors
          console.error('Access forbidden');
          break;
        case 404:
          // Handle not found errors
          console.error('Resource not found');
          break;
        default:
          // Handle other errors
          console.error('An error occurred');
      }
    } else if (error instanceof NetworkError) {
      // Handle network errors
      console.error('Network error:', error.message);
    } else {
      // Handle unexpected errors
      console.error('Unexpected error:', error);
    }
  }
}

// 4. Using with React hooks (example)
function useAPI() {
  const [client] = useState(() => new MowthosAPIClient({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    logger: {
      debug: (...args) => console.debug('[API]', ...args),
      info: (...args) => console.info('[API]', ...args),
      warn: (...args) => console.warn('[API]', ...args),
      error: (...args) => console.error('[API]', ...args)
    }
  }));
  
  return client;
}

// Export types and client
export { APIError, NetworkError, APIResponse };
export default MowthosAPIClient;