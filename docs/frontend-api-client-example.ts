/**
 * MowthosOS API Client Example Implementation
 * 
 * This is a reference implementation for the frontend API client.
 * Shows best practices for authentication, error handling, and service organization.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { 
  TokenResponse, 
  UserResponse, 
  ErrorResponse,
  APIClientConfig 
} from './frontend-api-types';

// ==================== Base API Client ====================

export class MowthosAPIClient {
  private axiosInstance: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private tokenRefreshPromise: Promise<void> | null = null;

  constructor(config: APIClientConfig) {
    this.axiosInstance = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        ...config.headers
      }
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request interceptor - add auth token
    this.axiosInstance.interceptors.request.use(
      (config) => {
        if (this.accessToken && !config.headers['Authorization']) {
          config.headers['Authorization'] = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle token refresh
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ErrorResponse>) => {
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
        
        if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
          originalRequest._retry = true;
          
          // Avoid multiple simultaneous refresh attempts
          if (!this.tokenRefreshPromise) {
            this.tokenRefreshPromise = this.refreshAccessToken();
          }
          
          try {
            await this.tokenRefreshPromise;
            this.tokenRefreshPromise = null;
            return this.axiosInstance(originalRequest);
          } catch (refreshError) {
            this.tokenRefreshPromise = null;
            this.clearTokens();
            // Redirect to login or emit auth failure event
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }
        
        return Promise.reject(error);
      }
    );
  }

  private async refreshAccessToken(): Promise<void> {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await axios.post<TokenResponse>(
        `${this.axiosInstance.defaults.baseURL}/api/v1/auth/refresh`,
        { refresh_token: this.refreshToken }
      );
      
      this.setTokens(response.data.access_token, response.data.refresh_token);
    } catch (error) {
      throw new Error('Failed to refresh token');
    }
  }

  public setTokens(accessToken: string, refreshToken: string): void {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    
    // Store tokens securely (consider using secure storage libraries)
    localStorage.setItem('mowthos_access_token', accessToken);
    localStorage.setItem('mowthos_refresh_token', refreshToken);
  }

  public clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('mowthos_access_token');
    localStorage.removeItem('mowthos_refresh_token');
  }

  public loadTokens(): void {
    this.accessToken = localStorage.getItem('mowthos_access_token');
    this.refreshToken = localStorage.getItem('mowthos_refresh_token');
  }

  public get axios(): AxiosInstance {
    return this.axiosInstance;
  }

  public isAuthenticated(): boolean {
    return !!this.accessToken;
  }
}

// ==================== Service Classes ====================

// Auth Service
export class AuthService {
  constructor(private client: MowthosAPIClient) {}

  async register(data: UserRegisterRequest): Promise<UserResponse> {
    const response = await this.client.axios.post<UserResponse>(
      '/api/v1/auth/register',
      data
    );
    return response.data;
  }

  async login(email: string, password: string, deviceName?: string): Promise<TokenResponse> {
    const response = await this.client.axios.post<TokenResponse>(
      '/api/v1/auth/login',
      { email, password, device_name: deviceName }
    );
    
    // Store tokens
    this.client.setTokens(response.data.access_token, response.data.refresh_token);
    
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.axios.post('/api/v1/auth/logout');
    } finally {
      this.client.clearTokens();
    }
  }

  async getCurrentUser(): Promise<UserResponse> {
    const response = await this.client.axios.get<UserResponse>('/api/v1/auth/me');
    return response.data;
  }

  async updateProfile(data: UserUpdateRequest): Promise<UserResponse> {
    const response = await this.client.axios.put<UserResponse>(
      '/api/v1/auth/profile',
      data
    );
    return response.data;
  }

  async addAddress(data: AddressRequest): Promise<AddressResponse> {
    const response = await this.client.axios.post<AddressResponse>(
      '/api/v1/auth/addresses',
      data
    );
    return response.data;
  }
}

// Device Service (Host only)
export class DeviceService {
  constructor(private client: MowthosAPIClient) {}

  async listDevices(): Promise<DeviceResponse[]> {
    const response = await this.client.axios.get<DeviceResponse[]>('/api/v1/devices');
    return response.data;
  }

  async registerDevice(data: DeviceRegistrationRequest): Promise<DeviceResponse> {
    const response = await this.client.axios.post<DeviceResponse>(
      '/api/v1/devices/register',
      data
    );
    return response.data;
  }

  async getDeviceStatus(deviceId: string): Promise<DeviceStatusResponse> {
    const response = await this.client.axios.get<DeviceStatusResponse>(
      `/api/v1/devices/${deviceId}/status`
    );
    return response.data;
  }

  async removeDevice(deviceId: string): Promise<MessageResponse> {
    const response = await this.client.axios.delete<MessageResponse>(
      `/api/v1/devices/${deviceId}`
    );
    return response.data;
  }
}

// Mower Service
export class MowerService {
  constructor(private client: MowthosAPIClient) {}

  async getMowerStatus(deviceName: string): Promise<MowerStatus> {
    const response = await this.client.axios.get<MowerStatus>(
      `/api/v1/mowers/${deviceName}/status`
    );
    return response.data;
  }

  async startMowing(deviceName: string): Promise<CommandResponse> {
    const response = await this.client.axios.post<CommandResponse>(
      `/api/v1/mowers/${deviceName}/commands/start`
    );
    return response.data;
  }

  async stopMowing(deviceName: string): Promise<CommandResponse> {
    const response = await this.client.axios.post<CommandResponse>(
      `/api/v1/mowers/${deviceName}/commands/stop`
    );
    return response.data;
  }

  async pauseMowing(deviceName: string): Promise<CommandResponse> {
    const response = await this.client.axios.post<CommandResponse>(
      `/api/v1/mowers/${deviceName}/commands/pause`
    );
    return response.data;
  }

  async resumeMowing(deviceName: string): Promise<CommandResponse> {
    const response = await this.client.axios.post<CommandResponse>(
      `/api/v1/mowers/${deviceName}/commands/resume`
    );
    return response.data;
  }

  async returnToDock(deviceName: string): Promise<CommandResponse> {
    const response = await this.client.axios.post<CommandResponse>(
      `/api/v1/mowers/${deviceName}/commands/return`
    );
    return response.data;
  }
}

// Cluster Service
export class ClusterService {
  constructor(private client: MowthosAPIClient) {}

  async createCluster(addressId: string): Promise<CreateClusterResponse> {
    const response = await this.client.axios.post<CreateClusterResponse>(
      '/api/v1/clusters/create',
      { address_id: addressId }
    );
    return response.data;
  }

  async joinCluster(clusterId: string, addressId: string): Promise<JoinClusterResponse> {
    const response = await this.client.axios.post<JoinClusterResponse>(
      `/api/v1/clusters/${clusterId}/join`,
      { address_id: addressId }
    );
    return response.data;
  }

  async leaveCluster(clusterId: string): Promise<LeaveClusterResponse> {
    const response = await this.client.axios.post<LeaveClusterResponse>(
      `/api/v1/clusters/${clusterId}/leave`
    );
    return response.data;
  }

  async getClusterDetails(clusterId: string): Promise<ClusterDetailsResponse> {
    const response = await this.client.axios.get<ClusterDetailsResponse>(
      `/api/v1/clusters/${clusterId}`
    );
    return response.data;
  }

  async findQualifiedClusters(addressId: string): Promise<any> {
    const response = await this.client.axios.get(
      `/api/v1/clusters/neighbor/${addressId}/qualified-clusters`
    );
    return response.data;
  }

  async getMarketAnalysis(clusterId: string): Promise<MarketAnalysisResponse> {
    const response = await this.client.axios.get<MarketAnalysisResponse>(
      `/api/v1/clusters/${clusterId}/market-analysis`
    );
    return response.data;
  }
}

// Payment Service
export class PaymentService {
  constructor(private client: MowthosAPIClient) {}

  async getSubscriptionPlans(): Promise<SubscriptionPlanResponse[]> {
    const response = await this.client.axios.get<SubscriptionPlanResponse[]>(
      '/api/v1/payments/plans'
    );
    return response.data;
  }

  async createPreJoinSubscription(
    data: CreatePreJoinSubscriptionRequest
  ): Promise<any> {
    const response = await this.client.axios.post(
      '/api/v1/payments/subscriptions/pre-join',
      data
    );
    return response.data;
  }

  async attachPaymentMethod(
    paymentMethodId: string,
    setAsDefault: boolean = true
  ): Promise<PaymentMethodResponse> {
    const response = await this.client.axios.post<PaymentMethodResponse>(
      '/api/v1/payments/payment-methods',
      { payment_method_id: paymentMethodId, set_as_default: setAsDefault }
    );
    return response.data;
  }

  async listPaymentMethods(): Promise<PaymentMethodResponse[]> {
    const response = await this.client.axios.get<PaymentMethodResponse[]>(
      '/api/v1/payments/payment-methods'
    );
    return response.data;
  }

  async getSubscriptionDetails(subscriptionId: string): Promise<SubscriptionDetailsResponse> {
    const response = await this.client.axios.get<SubscriptionDetailsResponse>(
      `/api/v1/payments/subscriptions/${subscriptionId}`
    );
    return response.data;
  }

  async cancelSubscription(
    subscriptionId: string,
    immediate: boolean = false
  ): Promise<any> {
    const response = await this.client.axios.post(
      `/api/v1/payments/subscriptions/${subscriptionId}/cancel`,
      null,
      { params: { immediate } }
    );
    return response.data;
  }

  async createBillingPortalSession(returnUrl: string): Promise<{ portal_url: string }> {
    const response = await this.client.axios.post<{ portal_url: string }>(
      '/api/v1/payments/billing-portal',
      null,
      { params: { return_url: returnUrl } }
    );
    return response.data;
  }
}

// ==================== Main API Instance ====================

export class MowthosAPI {
  private client: MowthosAPIClient;
  public auth: AuthService;
  public devices: DeviceService;
  public mowers: MowerService;
  public clusters: ClusterService;
  public payments: PaymentService;

  constructor(config: APIClientConfig) {
    this.client = new MowthosAPIClient(config);
    
    // Initialize services
    this.auth = new AuthService(this.client);
    this.devices = new DeviceService(this.client);
    this.mowers = new MowerService(this.client);
    this.clusters = new ClusterService(this.client);
    this.payments = new PaymentService(this.client);
    
    // Load stored tokens on initialization
    this.client.loadTokens();
  }

  get isAuthenticated(): boolean {
    return this.client.isAuthenticated();
  }
}

// ==================== Usage Example ====================

/*
// Initialize API client
const api = new MowthosAPI({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
});

// Login
const tokens = await api.auth.login('user@example.com', 'password');

// Get current user
const user = await api.auth.getCurrentUser();

// For Hosts: Register a device
if (user.role === UserRole.HOST) {
  const device = await api.devices.registerDevice({
    mammotion_email: 'host@mammotion.com',
    mammotion_password: 'password',
    device_name: 'Luba-12345',
    device_nickname: 'Front Yard Mower'
  });
  
  // Start mowing
  await api.mowers.startMowing(device.device_name);
}

// For Neighbors: Find and join cluster
if (user.role === UserRole.NEIGHBOR) {
  const clusters = await api.clusters.findQualifiedClusters(user.addressId);
  
  if (clusters.qualified_clusters.length > 0) {
    const cluster = clusters.qualified_clusters[0];
    const plans = await api.payments.getSubscriptionPlans();
    
    // Create subscription and join cluster
    const subscription = await api.payments.createPreJoinSubscription({
      cluster_id: cluster.cluster_id,
      plan_id: plans[0].id,
      payment_method_id: 'pm_card_visa',
      address_id: user.addressId
    });
  }
}
*/