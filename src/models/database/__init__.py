"""Database models package"""

# Import all models to ensure they are registered with SQLAlchemy
from src.models.database.users import (
    User, UserAddress, UserSession, RefreshToken, 
    APIKey, AuditLog, UserRole
)
from src.models.database.devices import (
    MowerDevice, MaintenanceRecord, DeviceUsageRecord, 
    DeviceCommand, DeviceTelemetry, DeviceStatus, DeviceModel
)
from src.models.database.clusters import (
    Cluster, ClusterMember, ClusterSchedule, 
    RouteOptimization, ClusterStatus, MemberStatus, ScheduleType
)
from src.models.database.billing import (
    Subscription, PaymentMethod, Invoice, InvoiceLineItem, 
    Payment, UsageRecord, SubscriptionTier, SubscriptionStatus,
    PaymentStatus, InvoiceStatus
)

# Export all models
__all__ = [
    # User models
    "User", "UserAddress", "UserSession", "RefreshToken", 
    "APIKey", "AuditLog", "UserRole",
    
    # Device models
    "MowerDevice", "MaintenanceRecord", "DeviceUsageRecord", 
    "DeviceCommand", "DeviceTelemetry", "DeviceStatus", "DeviceModel",
    
    # Cluster models
    "Cluster", "ClusterMember", "ClusterSchedule", 
    "RouteOptimization", "ClusterStatus", "MemberStatus", "ScheduleType",
    
    # Billing models
    "Subscription", "PaymentMethod", "Invoice", "InvoiceLineItem", 
    "Payment", "UsageRecord", "SubscriptionTier", "SubscriptionStatus",
    "PaymentStatus", "InvoiceStatus",
]