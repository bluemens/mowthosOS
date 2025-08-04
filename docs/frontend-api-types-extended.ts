/**
 * Extended Type Definitions for MowthosOS API Client
 * 
 * This file contains detailed types for errors, configuration, and responses
 */

import { AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';

// ==================== Error Types ====================

/**
 * Base error response from the API
 */
export interface APIErrorResponse {
  detail: string;
  status_code?: number;
  error_code?: string;
  timestamp?: string;
  path?: string;
  request_id?: string;
}

/**
 * Validation error details
 */
export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * Validation error response (400 Bad Request)
 */
export interface ValidationErrorResponse extends APIErrorResponse {
  detail: ValidationError[];
}

/**
 * Extended error class for API errors
 */
export class APIError extends Error {
  public statusCode: number;
  public errorCode?: string;
  public details?: any;
  public requestId?: string;

  constructor(
    message: string, 
    statusCode: number, 
    errorCode?: string, 
    details?: any,
    requestId?: string
  ) {
    super(message);
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.details = details;
    this.requestId = requestId;
  }

  static fromAxiosError(error: AxiosError<APIErrorResponse>): APIError {
    const response = error.response;
    const data = response?.data;
    
    return new APIError(
      data?.detail || error.message || 'Unknown error occurred',
      response?.status || 500,
      data?.error_code,
      data,
      data?.request_id
    );
  }
}

/**
 * Network error class
 */
export class NetworkError extends Error {
  constructor(message: string = 'Network error occurred') {
    super(message);
    this.name = 'NetworkError';
  }
}

/**
 * Authentication error class
 */
export class AuthenticationError extends APIError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401, 'AUTH_FAILED');
    this.name = 'AuthenticationError';
  }
}

// ==================== Configuration Types ====================

/**
 * Complete API client configuration
 */
export interface APIClientConfig {
  // Required
  baseURL: string;
  
  // Optional
  timeout?: number;
  headers?: Record<string, string>;
  withCredentials?: boolean;
  
  // Retry configuration
  retry?: {
    enabled: boolean;
    maxAttempts?: number;
    backoffMultiplier?: number;
    retryableStatuses?: number[];
  };
  
  // Interceptors
  onRequest?: (config: AxiosRequestConfig) => AxiosRequestConfig | Promise<AxiosRequestConfig>;
  onRequestError?: (error: any) => any;
  onResponse?: (response: AxiosResponse) => AxiosResponse | Promise<AxiosResponse>;
  onResponseError?: (error: any) => any;
  
  // Token management
  tokenStorage?: {
    getAccessToken: () => string | null | Promise<string | null>;
    getRefreshToken: () => string | null | Promise<string | null>;
    setTokens: (accessToken: string, refreshToken: string) => void | Promise<void>;
    clearTokens: () => void | Promise<void>;
  };
  
  // Logging
  logger?: {
    debug: (message: string, ...args: any[]) => void;
    info: (message: string, ...args: any[]) => void;
    warn: (message: string, ...args: any[]) => void;
    error: (message: string, ...args: any[]) => void;
  };
}

/**
 * Request configuration for individual API calls
 */
export interface APIRequestOptions extends Omit<AxiosRequestConfig, 'url' | 'method' | 'baseURL'> {
  // Custom retry for this request
  retry?: boolean | number;
  
  // Skip auth for this request
  skipAuth?: boolean;
  
  // Custom timeout for this request
  timeout?: number;
  
  // Request metadata
  metadata?: Record<string, any>;
}

// ==================== Response Types ====================

/**
 * Standard API response wrapper
 */
export interface APIResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
  config: AxiosRequestConfig;
  request?: any;
}

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

/**
 * List response wrapper
 */
export interface ListResponse<T> {
  items: T[];
  count: number;
}

/**
 * Success response with metadata
 */
export interface SuccessResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  metadata?: Record<string, any>;
}

/**
 * Batch operation response
 */
export interface BatchResponse<T = any> {
  successful: T[];
  failed: Array<{
    item: any;
    error: APIErrorResponse;
  }>;
  total: number;
  succeeded: number;
  failed_count: number;
}

/**
 * File upload response
 */
export interface FileUploadResponse {
  file_id: string;
  filename: string;
  size: number;
  mime_type: string;
  url?: string;
  thumbnail_url?: string;
  metadata?: Record<string, any>;
}

// ==================== WebSocket Types ====================

/**
 * WebSocket message types
 */
export enum WSMessageType {
  DEVICE_STATUS = 'device_status',
  MOWING_EVENT = 'mowing_event',
  CLUSTER_UPDATE = 'cluster_update',
  NOTIFICATION = 'notification',
  ERROR = 'error',
  PING = 'ping',
  PONG = 'pong'
}

/**
 * WebSocket message wrapper
 */
export interface WSMessage<T = any> {
  type: WSMessageType;
  payload: T;
  timestamp: string;
  id?: string;
}

/**
 * WebSocket configuration
 */
export interface WSConfig {
  url: string;
  protocols?: string[];
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onMessage?: (message: WSMessage) => void;
}

// ==================== Utility Types ====================

/**
 * Make all properties optional recursively
 */
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

/**
 * Extract keys of type T that have values of type U
 */
export type KeysOfType<T, U> = {
  [K in keyof T]: T[K] extends U ? K : never;
}[keyof T];

/**
 * Omit multiple properties from type
 */
export type OmitMultiple<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;

/**
 * Make specific properties required
 */
export type RequireFields<T, K extends keyof T> = T & Required<Pick<T, K>>;

/**
 * API method type
 */
export type APIMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Query parameters type
 */
export interface QueryParams {
  [key: string]: string | number | boolean | undefined | null | (string | number | boolean)[];
}

// ==================== Hook Types (for React) ====================

/**
 * API hook state
 */
export interface APIHookState<T> {
  data: T | null;
  error: APIError | null;
  loading: boolean;
  refetch: () => Promise<void>;
}

/**
 * Mutation hook state
 */
export interface MutationHookState<TData, TVariables> {
  data: TData | null;
  error: APIError | null;
  loading: boolean;
  mutate: (variables: TVariables) => Promise<TData>;
  reset: () => void;
}

/**
 * Query options for hooks
 */
export interface QueryOptions {
  enabled?: boolean;
  refetchInterval?: number;
  refetchOnWindowFocus?: boolean;
  refetchOnReconnect?: boolean;
  retry?: boolean | number;
  retryDelay?: number;
  staleTime?: number;
  cacheTime?: number;
  onSuccess?: (data: any) => void;
  onError?: (error: APIError) => void;
  onSettled?: () => void;
}

// ==================== Form Types ====================

/**
 * Form field error
 */
export interface FieldError {
  field: string;
  message: string;
  code?: string;
}

/**
 * Form submission result
 */
export interface FormSubmissionResult<T = any> {
  success: boolean;
  data?: T;
  errors?: FieldError[];
  message?: string;
}

// ==================== Cache Types ====================

/**
 * Cache entry
 */
export interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl?: number;
  etag?: string;
}

/**
 * Cache configuration
 */
export interface CacheConfig {
  enabled: boolean;
  defaultTTL?: number;
  maxSize?: number;
  storage?: 'memory' | 'localStorage' | 'sessionStorage';
  keyPrefix?: string;
}