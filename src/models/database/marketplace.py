"""Marketplace and product related database models"""
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, 
    DECIMAL, Integer, JSON, Text, UniqueConstraint, Index,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class ProductStatus(str, Enum):
    """Product availability status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    COMING_SOON = "coming_soon"


class OrderStatus(str, Enum):
    """Order fulfillment status"""
    PENDING = "pending"
    PAYMENT_PROCESSING = "payment_processing"
    PAYMENT_FAILED = "payment_failed"
    PAID = "paid"
    PREPARING = "preparing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ProductCategory(str, Enum):
    """Product categories"""
    MOWER = "mower"
    ACCESSORY = "accessory"
    REPLACEMENT_PART = "replacement_part"
    SERVICE_PACKAGE = "service_package"


class Product(Base):
    """Marketplace products"""
    __tablename__ = "products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Product identification
    sku = Column(String(100), unique=True, nullable=False)
    name = Column(String(300), nullable=False)
    slug = Column(String(300), unique=True, nullable=False)
    
    # Categorization
    category = Column(SQLEnum(ProductCategory), nullable=False)
    device_model = Column(String(100), nullable=True)  # For model-specific items
    
    # Description
    short_description = Column(String(500), nullable=True)
    full_description = Column(Text, nullable=True)
    features = Column(JSON, nullable=True)  # List of feature strings
    specifications = Column(JSON, nullable=True)  # Technical specs
    
    # Pricing
    base_price = Column(DECIMAL(10, 2), nullable=False)
    sale_price = Column(DECIMAL(10, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Stripe integration
    stripe_product_id = Column(String(255), unique=True, nullable=True)
    stripe_price_id = Column(String(255), unique=True, nullable=True)
    
    # Inventory
    status = Column(SQLEnum(ProductStatus), default=ProductStatus.ACTIVE, nullable=False)
    stock_quantity = Column(Integer, default=0, nullable=False)
    track_inventory = Column(Boolean, default=True, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    
    # Shipping
    weight_kg = Column(DECIMAL(10, 2), nullable=True)
    dimensions_cm = Column(JSON, nullable=True)  # {"length": x, "width": y, "height": z}
    shipping_class = Column(String(50), nullable=True)
    
    # Media
    primary_image_url = Column(String(500), nullable=True)
    gallery_urls = Column(JSON, nullable=True)  # List of image URLs
    manual_url = Column(String(500), nullable=True)
    
    # SEO
    meta_title = Column(String(200), nullable=True)
    meta_description = Column(String(500), nullable=True)
    
    # Leasing option (for subscriber hosts)
    available_for_lease = Column(Boolean, default=False, nullable=False)
    lease_monthly_price = Column(DECIMAL(10, 2), nullable=True)
    lease_deposit = Column(DECIMAL(10, 2), nullable=True)
    lease_terms = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    orders = relationship("OrderItem", back_populates="product")
    reviews = relationship("ProductReview", back_populates="product", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_product_category_status", "category", "status"),
        Index("idx_product_slug", "slug"),
        Index("idx_product_sku", "sku"),
        Index("idx_product_stripe", "stripe_product_id"),
    )


class Order(Base):
    """Customer orders"""
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String(50), unique=True, nullable=False)
    
    # Customer
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=True)
    
    # Status
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    
    # Pricing
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    tax_amount = Column(DECIMAL(10, 2), default=0, nullable=False)
    shipping_amount = Column(DECIMAL(10, 2), default=0, nullable=False)
    discount_amount = Column(DECIMAL(10, 2), default=0, nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Payment
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=True)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    # Shipping
    shipping_address = Column(JSON, nullable=False)
    billing_address = Column(JSON, nullable=False)
    shipping_method = Column(String(100), nullable=True)
    tracking_number = Column(String(200), nullable=True)
    shipped_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notes
    customer_notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_order_user", "user_id"),
        Index("idx_order_status", "status"),
        Index("idx_order_created", "created_at"),
        Index("idx_order_number", "order_number"),
    )


class OrderItem(Base):
    """Order line items"""
    __tablename__ = "order_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    
    # Product snapshot at time of order
    product_name = Column(String(300), nullable=False)
    product_sku = Column(String(100), nullable=False)
    
    # Quantity and pricing
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    total_price = Column(DECIMAL(10, 2), nullable=False)
    
    # For lease orders
    is_lease = Column(Boolean, default=False, nullable=False)
    lease_subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    
    # Fulfillment
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    serial_number = Column(String(200), nullable=True)  # For mowers
    
    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="orders")
    
    # Indexes
    __table_args__ = (
        Index("idx_order_item_order", "order_id"),
        Index("idx_order_item_product", "product_id"),
    )


class ProductReview(Base):
    """Product reviews and ratings"""
    __tablename__ = "product_reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    
    # Review content
    rating = Column(Integer, nullable=False)  # 1-5 stars
    title = Column(String(200), nullable=True)
    comment = Column(Text, nullable=True)
    
    # Verification
    verified_purchase = Column(Boolean, default=False, nullable=False)
    helpful_count = Column(Integer, default=0, nullable=False)
    
    # Media
    image_urls = Column(JSON, nullable=True)
    
    # Status
    is_published = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="reviews")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("product_id", "user_id", name="uq_one_review_per_user_per_product"),
        Index("idx_review_product_rating", "product_id", "rating"),
        Index("idx_review_user", "user_id"),
    )