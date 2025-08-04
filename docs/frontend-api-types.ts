/**
 * MowthosOS API TypeScript Type Definitions
 * 
 * This file contains all TypeScript interfaces for the MowthosOS API
 * to ensure type safety in frontend applications.
 */

// ==================== Enums ====================

export enum UserRole {
  USER = 'user',
  NEIGHBOR = 'neighbor',
  HOST = 'host',
  ADMIN = 'admin'
}

export enum MowerCommand {
  START_MOW = 'start_mow',
  STOP_MOW = 'stop_mow',
  PAUSE_MOW = 'pause_mow',
  RESUME_MOW = 'resume_mow',
  RETURN_TO_DOCK = 'return_to_dock',
  START_CHARGE = 'start_charge',
  STOP_CHARGE = 'stop_charge'
}

export enum ClusterStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  FULL = 'full'
}

export enum MemberStatus {
  PENDING = 'pending',
  ACTIVE = 'active',
  SUSPENDED = 'suspended',
  CANCELLED = 'cancelled'
}

export enum SubscriptionStatus {
  ACTIVE = 'active',
  TRIALING = 'trialing',
  PAST_DUE = 'past_due',
  CANCELLED = 'cancelled'
}

// ==================== Authentication Types ====================

export interface UserRegisterRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  username?: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
  device_name?: string;
}

export interface TokenRefreshRequest {
  refresh_token: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: string;
  email: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface UserUpdateRequest {
  first_name?: string;
  last_name?: string;
  phone_number?: string;
  bio?: string;
  timezone?: string;
  locale?: string;
}

export interface EmailUpdateRequest {
  new_email: string;
  password: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

// ==================== Address Types ====================

export interface AddressRequest {
  address_line1: string;
  address_line2?: string;
  city: string;
  state_province: string;
  postal_code: string;
  country: string;
  label?: string;
  is_primary: boolean;
}

export interface AddressUpdateRequest {
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state_province?: string;
  postal_code?: string;
  country?: string;
}

export interface AddressResponse {
  id: string;
  address_line1: string;
  address_line2?: string;
  city: string;
  state_province: string;
  postal_code: string;
  country: string;
  latitude?: string;
  longitude?: string;
  label?: string;
  is_primary: boolean;
  verified: boolean;
  created_at: string;
}

// ==================== Device Types ====================

export interface MammotionLoginRequest {
  mammotion_email: string;
  mammotion_password: string;
}

export interface DeviceRegistrationRequest {
  mammotion_email: string;
  mammotion_password: string;
  device_name: string;
  device_nickname?: string;
}

export interface DeviceResponse {
  id: string;
  device_id: string;
  device_name: string;
  device_nickname?: string;
  device_model: string;
  status: string;
  battery_level?: number;
  is_online: boolean;
  last_seen?: string;
  created_at: string;
}

export interface DeviceStatusResponse {
  device_id: string;
  device_name: string;
  status: string;
  battery_level?: number;
  charging_state?: number;
  work_mode?: string;
  work_progress?: number;
  is_online: boolean;
  current_location?: {
    latitude: number;
    longitude: number;
  };
  last_updated: string;
}

// ==================== Mower Types ====================

export interface MowerStatus {
  device_name: string;
  online: boolean;
  work_mode: string;
  work_mode_code: number;
  battery_level: number;
  charging_state: number;
  blade_status: boolean;
  location?: Record<string, any>;
  work_progress?: number;
  work_area?: number;
  last_updated: string;
}

export interface CommandRequest {
  device_name: string;
}

export interface CommandResponse {
  success: boolean;
  message: string;
  command_sent: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  device_name?: string;
  session_id?: string;
}

// ==================== Cluster Types ====================

export interface CreateClusterRequest {
  address_id: string;
}

export interface CreateClusterResponse {
  success: boolean;
  cluster_id?: string;
  cluster_name?: string;
  host_address?: string;
  market_analysis?: Record<string, any>;
  message?: string;
}

export interface JoinClusterRequest {
  address_id: string;
}

export interface JoinClusterResponse {
  success: boolean;
  cluster_id?: string;
  user_id?: string;
  member_id?: string;
  join_order?: number;
  status?: string;
  message?: string;
}

export interface LeaveClusterResponse {
  success: boolean;
  cluster_id?: string;
  user_id?: string;
  left_at?: string;
  message?: string;
}

export interface ClusterDetailsResponse {
  success: boolean;
  cluster_id?: string;
  cluster_name?: string;
  host_user_id?: string;
  host_name?: string;
  host_address?: string;
  status?: string;
  current_members?: number;
  max_members?: number;
  is_accepting_members?: boolean;
  center_latitude?: number;
  center_longitude?: number;
  service_radius_meters?: number;
  created_at?: string;
  members?: Array<{
    member_id: string;
    user_id: string;
    name: string;
    join_order: number;
    status: MemberStatus;
    joined_at: string;
  }>;
  message?: string;
}

export interface MarketAnalysisResponse {
  success: boolean;
  cluster_id?: string;
  existing_platform_users?: Record<string, any>;
  addressable_market?: Record<string, any>;
  market_insights?: Record<string, any>;
  message?: string;
}

// ==================== Payment Types ====================

export interface SubscriptionPlanResponse {
  id: string;
  name: string;
  code: string;
  description?: string;
  monthly_price: number;
  annual_price?: number;
  currency: string;
  mowing_frequency: string;
  max_lawn_size_sqm?: number;
  included_services: string[];
  priority_scheduling: boolean;
  features: Record<string, any>;
}

export interface CreateSubscriptionRequest {
  cluster_id: string;
  plan_id: string;
  payment_method_id: string;
}

export interface CreatePreJoinSubscriptionRequest {
  cluster_id: string;
  plan_id: string;
  payment_method_id: string;
  address_id: string;
}

export interface CreateCheckoutRequest {
  items: Array<{
    product_id: string;
    quantity: number;
  }>;
  success_url: string;
  cancel_url: string;
}

export interface PaymentMethodRequest {
  payment_method_id: string;
  set_as_default: boolean;
}

export interface UpdateSubscriptionPlanRequest {
  new_plan_id: string;
  effective_date?: string;
}

export interface PaymentMethodResponse {
  id: string;
  type: string;
  last4: string;
  brand: string;
  exp_month?: number;
  exp_year?: number;
  is_default: boolean;
}

export interface SubscriptionDetailsResponse {
  subscription_id: string;
  status: SubscriptionStatus;
  trial_start?: string;
  trial_end?: string;
  current_period_start?: string;
  current_period_end?: string;
  monthly_price?: number;
  currency: string;
  plan?: {
    id: string;
    name: string;
    mowing_frequency: string;
    included_services: string[];
  };
  cluster_member?: {
    member_id: string;
    status: MemberStatus;
    join_order: number;
  };
  is_trial_active: boolean;
}

// ==================== Generic Response Types ====================

export interface MessageResponse {
  message: string;
}

export interface ErrorResponse {
  detail: string;
}

// ==================== API Client Types ====================

export interface APIClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
}

export interface APIRequestConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  data?: any;
  params?: Record<string, any>;
  headers?: Record<string, string>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}