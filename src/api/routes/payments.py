"""Payment and subscription API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import stripe

from src.core.auth import get_current_active_user
from src.models.database.users import User
from src.models.database.billing import ClusterSubscriptionPlan
from src.models.database.clusters import ClusterMember
from src.models.database.marketplace import Product
from src.services.payment.stripe_service import StripeService
from src.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# ==================== Request/Response Models ====================

class SubscriptionPlanResponse(BaseModel):
    """Subscription plan details"""
    id: str
    name: str
    code: str
    description: Optional[str]
    monthly_price: float
    annual_price: Optional[float]
    currency: str
    mowing_frequency: str
    max_lawn_size_sqm: Optional[int]
    included_services: List[str]
    priority_scheduling: bool
    features: dict


class CreateSubscriptionRequest(BaseModel):
    """Request to create a subscription"""
    cluster_id: str
    plan_id: str
    payment_method_id: str


class CreateCheckoutRequest(BaseModel):
    """Request to create marketplace checkout"""
    items: List[dict] = Field(..., description="List of {product_id, quantity}")
    success_url: str
    cancel_url: str


class PaymentMethodRequest(BaseModel):
    """Request to attach payment method"""
    payment_method_id: str
    set_as_default: bool = True


class WebhookResponse(BaseModel):
    """Webhook processing response"""
    status: str
    event_type: Optional[str]


# ==================== Subscription Plans ====================

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    db: AsyncSession = Depends(get_db)
):
    """Get available subscription plans"""
    plans = await db.query(ClusterSubscriptionPlan).filter(
        ClusterSubscriptionPlan.is_active == True
    ).order_by(ClusterSubscriptionPlan.display_order).all()
    
    return [SubscriptionPlanResponse(
        id=str(plan.id),
        name=plan.name,
        code=plan.code,
        description=plan.description,
        monthly_price=float(plan.monthly_price),
        annual_price=float(plan.annual_price) if plan.annual_price else None,
        currency=plan.currency,
        mowing_frequency=plan.mowing_frequency,
        max_lawn_size_sqm=plan.max_lawn_size_sqm,
        included_services=plan.included_services,
        priority_scheduling=plan.priority_scheduling,
        features=plan.features
    ) for plan in plans]


# ==================== Subscription Management ====================

@router.post("/subscriptions/cluster")
async def create_cluster_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a subscription for cluster membership"""
    stripe_service = StripeService()
    
    # Verify user is member of the cluster
    member = await db.query(ClusterMember).filter(
        ClusterMember.cluster_id == request.cluster_id,
        ClusterMember.user_id == current_user.id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Not a member of this cluster")
    
    # Get the plan
    plan = await db.query(ClusterSubscriptionPlan).filter(
        ClusterSubscriptionPlan.id == request.plan_id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Attach payment method
    await stripe_service.attach_payment_method(
        current_user,
        request.payment_method_id,
        set_as_default=True
    )
    
    # Create subscription with 30-day trial
    subscription = await stripe_service.create_cluster_subscription(
        user=current_user,
        cluster_member=member,
        plan=plan,
        trial_days=30
    )
    
    return {
        "subscription_id": str(subscription.id),
        "status": subscription.status,
        "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
        "message": "Subscription created successfully with 30-day free trial"
    }


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    immediate: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a subscription"""
    stripe_service = StripeService()
    
    # Get user's subscription
    subscription = await db.query(Subscription).filter(
        Subscription.id == subscription_id,
        Subscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Cancel subscription
    subscription = await stripe_service.cancel_subscription(
        subscription,
        immediate=immediate
    )
    
    return {
        "status": "cancelled",
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "current_period_end": subscription.current_period_end.isoformat()
    }


# ==================== Marketplace ====================

@router.post("/checkout/session")
async def create_checkout_session(
    request: CreateCheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create Stripe checkout session for marketplace purchase"""
    stripe_service = StripeService()
    
    # Get products
    items_with_products = []
    for item in request.items:
        product = await db.query(Product).filter(
            Product.id == item["product_id"],
            Product.status == "active"
        ).first()
        
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item['product_id']} not found"
            )
        
        items_with_products.append({
            "product": product,
            "quantity": item["quantity"]
        })
    
    # Create checkout session
    checkout_url = await stripe_service.create_checkout_session(
        user=current_user,
        items=items_with_products,
        success_url=request.success_url,
        cancel_url=request.cancel_url
    )
    
    return {"checkout_url": checkout_url}


# ==================== Payment Methods ====================

@router.post("/payment-methods")
async def attach_payment_method(
    request: PaymentMethodRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Attach a payment method to user account"""
    stripe_service = StripeService()
    
    payment_method = await stripe_service.attach_payment_method(
        user=current_user,
        payment_method_id=request.payment_method_id,
        set_as_default=request.set_as_default
    )
    
    return {
        "id": str(payment_method.id),
        "type": payment_method.type,
        "last4": payment_method.last4,
        "brand": payment_method.brand,
        "is_default": payment_method.is_default
    }


@router.get("/payment-methods")
async def list_payment_methods(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's payment methods"""
    methods = await db.query(PaymentMethod).filter(
        PaymentMethod.user_id == current_user.id
    ).all()
    
    return [{
        "id": str(method.id),
        "type": method.type,
        "last4": method.last4,
        "brand": method.brand,
        "exp_month": method.exp_month,
        "exp_year": method.exp_year,
        "is_default": method.is_default
    } for method in methods]


# ==================== Webhooks ====================

@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request
):
    """Handle Stripe webhook events"""
    stripe_service = StripeService()
    
    # Get the webhook payload and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature header")
    
    try:
        result = await stripe_service.handle_webhook(payload, sig_header)
        return WebhookResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the error but return success to Stripe
        print(f"Webhook error: {e}")
        return WebhookResponse(status="error", event_type=None)


# ==================== Billing Portal ====================

@router.post("/billing-portal")
async def create_billing_portal_session(
    return_url: str,
    current_user: User = Depends(get_current_active_user)
):
    """Create Stripe billing portal session for subscription management"""
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No payment information on file"
        )
    
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=return_url
    )
    
    return {"portal_url": session.url}