"""Billing and subscription related database models"""
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, 
    DECIMAL, Integer, JSON, Text, UniqueConstraint, Index,
    Enum as SQLEnum, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class SubscriptionTier(str, Enum):
    """Subscription tiers"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionType(str, Enum):
    """Types of subscriptions"""
    PLATFORM = "platform"  # General platform access
    CLUSTER_MEMBER = "cluster_member"  # Neighbor in a cluster
    CLUSTER_HOST = "cluster_host"  # Host leasing a mower
    MAINTENANCE = "maintenance"  # Maintenance plans


class SubscriptionStatus(str, Enum):
    """Subscription status"""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"


class PaymentStatus(str, Enum):
    """Payment status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class InvoiceStatus(str, Enum):
    """Invoice status"""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class ClusterSubscriptionPlan(Base):
    """Subscription plans for cluster members"""
    __tablename__ = "cluster_subscription_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Plan details
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Pricing
    monthly_price = Column(DECIMAL(10, 2), nullable=False)
    annual_price = Column(DECIMAL(10, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Stripe integration
    stripe_product_id = Column(String(255), unique=True, nullable=True)
    stripe_monthly_price_id = Column(String(255), unique=True, nullable=True)
    stripe_annual_price_id = Column(String(255), unique=True, nullable=True)
    
    # Service levels
    mowing_frequency = Column(String(50), nullable=False)  # weekly, biweekly, monthly
    max_lawn_size_sqm = Column(Integer, nullable=True)
    included_services = Column(JSON, nullable=False)  # edge_trimming, leaf_removal, etc.
    priority_scheduling = Column(Boolean, default=False, nullable=False)
    
    # Features
    features = Column(JSON, default=dict, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_plan_code", "code"),
        Index("idx_plan_active", "is_active"),
    )


class Subscription(Base):
    """User subscriptions"""
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Subscription type
    subscription_type = Column(SQLEnum(SubscriptionType), nullable=False)
    
    # For cluster memberships
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    cluster_plan_id = Column(UUID(as_uuid=True), ForeignKey("cluster_subscription_plans.id", ondelete="SET NULL"), nullable=True)
    
    # Subscription details
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    
    # Stripe integration
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    stripe_price_id = Column(String(255), nullable=True)
    
    # Pricing
    monthly_price = Column(DECIMAL(10, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Billing cycle
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    billing_cycle_day = Column(Integer, nullable=True)  # Day of month
    
    # Trial
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    
    # Usage limits (per billing period)
    max_devices = Column(Integer, default=1, nullable=False)
    max_clusters_hosted = Column(Integer, default=0, nullable=False)
    max_clusters_joined = Column(Integer, default=1, nullable=False)
    max_mowing_hours = Column(Integer, nullable=True)  # None = unlimited
    max_area_sqm = Column(Integer, nullable=True)  # None = unlimited
    
    # Features
    features = Column(JSON, default=dict, nullable=False)
    
    # Cancellation
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="subscription", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_subscription_user", "user_id"),
        Index("idx_subscription_status", "status"),
        Index("idx_subscription_stripe", "stripe_customer_id", "stripe_subscription_id"),
    )


class PaymentMethod(Base):
    """User payment methods"""
    __tablename__ = "payment_methods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Payment method info
    stripe_payment_method_id = Column(String(255), unique=True, nullable=False)
    type = Column(String(50), nullable=False)  # card, bank_account, etc.
    
    # Card details (for display)
    brand = Column(String(50), nullable=True)  # visa, mastercard, etc.
    last4 = Column(String(4), nullable=True)
    exp_month = Column(Integer, nullable=True)
    exp_year = Column(Integer, nullable=True)
    
    # Metadata
    is_default = Column(Boolean, default=False, nullable=False)
    billing_address = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    payments = relationship("Payment", back_populates="payment_method")
    
    # Constraints
    __table_args__ = (
        Index("idx_payment_method_user", "user_id"),
        Index("idx_payment_method_default", "user_id", "is_default"),
    )


class Invoice(Base):
    """User invoices"""
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    
    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False)
    stripe_invoice_id = Column(String(255), unique=True, nullable=True)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)
    
    # Billing period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Amounts
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    tax = Column(DECIMAL(10, 2), default=0, nullable=False)
    discount = Column(DECIMAL(10, 2), default=0, nullable=False)
    total = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Payment
    paid_at = Column(DateTime(timezone=True), nullable=True)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True)
    
    # Due date
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    # PDF
    pdf_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice")
    
    # Indexes
    __table_args__ = (
        Index("idx_invoice_user", "user_id"),
        Index("idx_invoice_status", "status"),
        Index("idx_invoice_period", "period_start", "period_end"),
    )


class InvoiceLineItem(Base):
    """Invoice line items"""
    __tablename__ = "invoice_line_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    
    # Item details
    description = Column(String(500), nullable=False)
    quantity = Column(DECIMAL(10, 2), nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    
    # Type
    item_type = Column(String(50), nullable=False)  # subscription, usage, addon, credit, etc.
    
    # Reference
    reference_type = Column(String(50), nullable=True)  # device_usage, cluster_hosting, etc.
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Period
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    item_metadata = Column(JSON, nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")
    
    # Indexes
    __table_args__ = (
        Index("idx_line_item_invoice", "invoice_id"),
        Index("idx_line_item_reference", "reference_type", "reference_id"),
    )


class Payment(Base):
    """Payment transactions"""
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True)
    
    # Payment details
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=True)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Processing
    processed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Refunds
    refunded_amount = Column(DECIMAL(10, 2), default=0, nullable=False)
    refund_reason = Column(Text, nullable=True)
    
    # Metadata
    description = Column(String(500), nullable=True)
    payment_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    payment_method = relationship("PaymentMethod", back_populates="payments")
    
    # Indexes
    __table_args__ = (
        Index("idx_payment_user", "user_id"),
        Index("idx_payment_status", "status"),
        Index("idx_payment_created", "created_at"),
    )


class UsageRecord(Base):
    """Usage tracking for billing"""
    __tablename__ = "usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    
    # Usage details
    usage_type = Column(String(50), nullable=False)  # mowing_hours, area_covered, api_calls, etc.
    quantity = Column(DECIMAL(10, 2), nullable=False)
    unit = Column(String(20), nullable=False)  # hours, sqm, calls, etc.
    
    # Reference
    reference_type = Column(String(50), nullable=True)  # device_usage, cluster_schedule, etc.
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Billing
    billable = Column(Boolean, default=True, nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=True)  # For overage charges
    
    # Period
    usage_date = Column(DateTime(timezone=True), nullable=False)
    billing_period_start = Column(DateTime(timezone=True), nullable=True)
    billing_period_end = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    usage_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="usage_records")
    
    # Indexes
    __table_args__ = (
        Index("idx_usage_user_date", "user_id", "usage_date"),
        Index("idx_usage_subscription_period", "subscription_id", "billing_period_start"),
        Index("idx_usage_type", "usage_type"),
        Index("idx_usage_reference", "reference_type", "reference_id"),
    )