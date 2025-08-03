"""Stripe payment integration service"""
import stripe
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from decimal import Decimal
from uuid import UUID

from src.core.config import get_settings
from src.core.database import get_db
from src.models.database.billing import (
    Subscription, SubscriptionStatus, SubscriptionType, SubscriptionTier,
    PaymentMethod, Payment, PaymentStatus,
    Invoice, InvoiceStatus, InvoiceLineItem,
    ClusterSubscriptionPlan
)
from src.models.database.marketplace import Order, OrderStatus, Product
from src.models.database.users import User
from src.models.database.clusters import ClusterMember, MemberStatus
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class StripeService(BaseService):
    """Service for handling Stripe payments"""
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        # Convert SecretStr to string for Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY.get_secret_value() if settings.STRIPE_SECRET_KEY else None
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET.get_secret_value() if settings.STRIPE_WEBHOOK_SECRET else None
        
    # ==================== Customer Management ====================
    
    async def create_or_update_customer(self, user: User) -> str:
        """Create or update Stripe customer"""
        if user.stripe_customer_id:
            # Update existing customer
            customer = stripe.Customer.modify(
                user.stripe_customer_id,
                email=user.email,
                name=user.full_name,
                metadata={
                    "user_id": str(user.id),
                    "username": user.username
                }
            )
        else:
            # Create new customer
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={
                    "user_id": str(user.id),
                    "username": user.username
                }
            )
            
            # Update user with Stripe customer ID
            async with self.get_db() as db:
                user.stripe_customer_id = customer.id
                await db.commit()
                
        return customer.id
    
    # ==================== Subscription Management ====================
    
    async def create_cluster_subscription(
        self,
        user: User,
        cluster_member: ClusterMember,
        plan: ClusterSubscriptionPlan,
        trial_days: int = 30
    ) -> Subscription:
        """Create a subscription for a cluster member with trial period"""
        # Ensure customer exists in Stripe
        customer_id = await self.create_or_update_customer(user)
        
        # Create subscription in Stripe with trial
        stripe_subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{
                "price": plan.stripe_monthly_price_id,
            }],
            trial_period_days=trial_days,
            metadata={
                "user_id": str(user.id),
                "cluster_id": str(cluster_member.cluster_id),
                "cluster_member_id": str(cluster_member.id),
                "plan_id": str(plan.id)
            },
            # Enable usage-based billing for potential overages
            billing_thresholds={
                "amount_gte": 10000,  # $100 threshold
                "reset_billing_cycle_anchor": False
            }
        )
        
        # Create subscription record in database
        async with self.get_db() as db:
            subscription = Subscription(
                user_id=user.id,
                subscription_type=SubscriptionType.CLUSTER_MEMBER,
                cluster_id=cluster_member.cluster_id,
                cluster_plan_id=plan.id,
                tier=SubscriptionTier.BASIC,  # Map from plan
                status=SubscriptionStatus.TRIALING,
                stripe_customer_id=customer_id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_price_id=plan.stripe_monthly_price_id,
                monthly_price=Decimal(str(plan.monthly_price)),
                currency=plan.currency,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                trial_start=datetime.now(),
                trial_end=datetime.now() + timedelta(days=trial_days),
                features={
                    "mowing_frequency": plan.mowing_frequency,
                    "max_lawn_size_sqm": plan.max_lawn_size_sqm,
                    "included_services": plan.included_services,
                    "priority_scheduling": plan.priority_scheduling
                }
            )
            db.add(subscription)
            
            # Update cluster member status
            cluster_member.status = MemberStatus.ACTIVE
            
            await db.commit()
            await db.refresh(subscription)
            
        return subscription
    
    async def create_host_lease_subscription(
        self,
        user: User,
        product: Product,
        deposit_amount: Decimal
    ) -> Subscription:
        """Create a lease subscription for a host (subscriber host)"""
        customer_id = await self.create_or_update_customer(user)
        
        # Charge deposit first
        deposit_payment = stripe.PaymentIntent.create(
            amount=int(deposit_amount * 100),  # Convert to cents
            currency="usd",
            customer=customer_id,
            metadata={
                "type": "lease_deposit",
                "user_id": str(user.id),
                "product_id": str(product.id)
            },
            description=f"Lease deposit for {product.name}"
        )
        
        # Create recurring subscription for lease
        stripe_subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{
                "price": product.stripe_price_id,  # Monthly lease price
            }],
            metadata={
                "user_id": str(user.id),
                "product_id": str(product.id),
                "type": "host_lease"
            }
        )
        
        # Create subscription record
        async with self.get_db() as db:
            subscription = Subscription(
                user_id=user.id,
                subscription_type=SubscriptionType.CLUSTER_HOST,
                tier=SubscriptionTier.PROFESSIONAL,
                status=SubscriptionStatus.ACTIVE,
                stripe_customer_id=customer_id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_price_id=product.stripe_price_id,
                monthly_price=product.lease_monthly_price,
                currency="USD",
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                features={
                    "leased_product_id": str(product.id),
                    "deposit_payment_intent": deposit_payment.id,
                    "deposit_amount": str(deposit_amount)
                }
            )
            db.add(subscription)
            await db.commit()
            await db.refresh(subscription)
            
        return subscription
    
    async def cancel_subscription(
        self,
        subscription: Subscription,
        immediate: bool = False
    ) -> Subscription:
        """Cancel a subscription"""
        if subscription.stripe_subscription_id:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=not immediate
            )
            
            if immediate:
                stripe.Subscription.delete(subscription.stripe_subscription_id)
        
        async with self.get_db() as db:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancel_at_period_end = not immediate
            subscription.cancelled_at = datetime.now()
            await db.commit()
            
        return subscription
    
    async def update_subscription_plan(
        self,
        subscription: Subscription,
        new_plan: ClusterSubscriptionPlan,
        effective_date: Optional[str] = None
    ) -> Subscription:
        """Update subscription plan (upgrade/downgrade)"""
        if not subscription.stripe_subscription_id:
            raise ValueError("Subscription has no Stripe ID")
        
        # Parse effective date
        if effective_date:
            try:
                effective_datetime = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError("Invalid effective_date format. Use ISO format.")
        else:
            # Default to next billing cycle
            effective_datetime = subscription.current_period_end
        
        # Update Stripe subscription
        stripe_subscription = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                "id": subscription.stripe_price_id,  # Current price item
                "price": new_plan.stripe_monthly_price_id,  # New price
            }],
            proration_behavior="create_prorations",  # Prorate the change
            metadata={
                "plan_change": "true",
                "old_plan_id": str(subscription.cluster_plan_id),
                "new_plan_id": str(new_plan.id),
                "effective_date": effective_datetime.isoformat()
            }
        )
        
        # Update database subscription
        async with self.get_db() as db:
            subscription.cluster_plan_id = new_plan.id
            subscription.stripe_price_id = new_plan.stripe_monthly_price_id
            subscription.monthly_price = Decimal(str(new_plan.monthly_price))
            subscription.features = {
                "mowing_frequency": new_plan.mowing_frequency,
                "max_lawn_size_sqm": new_plan.max_lawn_size_sqm,
                "included_services": new_plan.included_services,
                "priority_scheduling": new_plan.priority_scheduling
            }
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end
            )
            
            await db.commit()
            await db.refresh(subscription)
        
        return subscription
    
    # ==================== Marketplace Payments ====================
    
    async def create_checkout_session(
        self,
        user: User,
        items: List[Dict[str, Any]],
        success_url: str,
        cancel_url: str
    ) -> str:
        """Create Stripe checkout session for marketplace purchases"""
        customer_id = await self.create_or_update_customer(user)
        
        line_items = []
        for item in items:
            product = item["product"]
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": product.name,
                        "description": product.short_description,
                        "images": [product.primary_image_url] if product.primary_image_url else [],
                        "metadata": {
                            "product_id": str(product.id)
                        }
                    },
                    "unit_amount": int(product.sale_price or product.base_price * 100),
                },
                "quantity": item["quantity"],
            })
        
        # Calculate shipping
        shipping_options = [{
            "shipping_rate_data": {
                "type": "fixed_amount",
                "fixed_amount": {
                    "amount": 9900,  # $99 shipping
                    "currency": "usd"
                },
                "display_name": "Standard Shipping",
                "delivery_estimate": {
                    "minimum": {
                        "unit": "business_day",
                        "value": 5
                    },
                    "maximum": {
                        "unit": "business_day",
                        "value": 10
                    }
                }
            }
        }]
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            customer=customer_id,
            line_items=line_items,
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            shipping_address_collection={
                "allowed_countries": ["US", "CA"]
            },
            shipping_options=shipping_options,
            metadata={
                "user_id": str(user.id)
            }
        )
        
        return session.url
    
    async def process_marketplace_order(
        self,
        session_id: str
    ) -> Order:
        """Process completed marketplace order from Stripe session"""
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["line_items", "customer"]
        )
        
        # Create order in database
        async with self.get_db() as db:
            order = Order(
                user_id=session.metadata.get("user_id"),
                order_number=f"ORD-{datetime.now().strftime('%Y%m%d')}-{session.id[-8:]}",
                customer_email=session.customer_details.email,
                customer_phone=session.customer_details.phone,
                status=OrderStatus.PAID,
                subtotal=Decimal(str(session.amount_subtotal / 100)),
                tax_amount=Decimal(str(session.total_details.amount_tax / 100)),
                shipping_amount=Decimal(str(session.shipping_cost.amount_total / 100)),
                discount_amount=Decimal(str(session.total_details.amount_discount / 100)),
                total_amount=Decimal(str(session.amount_total / 100)),
                stripe_payment_intent_id=session.payment_intent,
                paid_at=datetime.now(),
                shipping_address=session.customer_details.address,
                billing_address=session.customer_details.address
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)
            
        return order
    
    async def create_pre_join_subscription(
        self,
        user: User,
        cluster_id: UUID,
        plan: ClusterSubscriptionPlan,
        payment_method_id: str,
        address_id: UUID,
        trial_days: int = 30
    ) -> Dict[str, Any]:
        """Create subscription for cluster membership with trial period"""
        # Ensure customer exists in Stripe
        customer_id = await self.create_or_update_customer(user)
        
        # Attach payment method
        await self.attach_payment_method(
            user=user,
            payment_method_id=payment_method_id,
            set_as_default=True
        )
        
        # Create subscription in Stripe with trial (no immediate charge)
        stripe_subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{
                "price": plan.stripe_monthly_price_id,
            }],
            trial_period_days=trial_days,
            payment_behavior="default_incomplete",  # Don't charge immediately
            payment_settings={
                "save_default_payment_method": "on_subscription",
                "payment_method_types": ["card"]
            },
            metadata={
                "user_id": str(user.id),
                "cluster_id": str(cluster_id),
                "plan_id": str(plan.id),
                "address_id": str(address_id),
                "subscription_type": "cluster_member_trial"
            }
        )
        
        # Create subscription record in database
        async with self.get_db() as db:
            subscription = Subscription(
                user_id=user.id,
                subscription_type=SubscriptionType.CLUSTER_MEMBER,
                cluster_id=cluster_id,
                cluster_plan_id=plan.id,
                tier=SubscriptionTier.BASIC,  # Map from plan
                status=SubscriptionStatus.TRIALING,
                stripe_customer_id=customer_id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_price_id=plan.stripe_monthly_price_id,
                monthly_price=Decimal(str(plan.monthly_price)),
                currency=plan.currency,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                trial_start=datetime.now(),
                trial_end=datetime.now() + timedelta(days=trial_days),
                features={
                    "mowing_frequency": plan.mowing_frequency,
                    "max_lawn_size_sqm": plan.max_lawn_size_sqm,
                    "included_services": plan.included_services,
                    "priority_scheduling": plan.priority_scheduling
                }
            )
            db.add(subscription)
            await db.commit()
            await db.refresh(subscription)
            
        return {
            "subscription_id": str(subscription.id),
            "stripe_subscription_id": stripe_subscription.id,
            "status": subscription.status,
            "trial_start": subscription.trial_start.isoformat(),
            "trial_end": subscription.trial_end.isoformat(),
            "customer_id": customer_id
        }
    
    # ==================== Webhook Handling ====================
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid signature")
        
        # Handle different event types
        if event["type"] == "customer.subscription.created":
            await self._handle_subscription_created(event["data"]["object"])
        elif event["type"] == "customer.subscription.updated":
            await self._handle_subscription_updated(event["data"]["object"])
        elif event["type"] == "customer.subscription.deleted":
            await self._handle_subscription_deleted(event["data"]["object"])
        elif event["type"] == "invoice.payment_succeeded":
            await self._handle_invoice_paid(event["data"]["object"])
        elif event["type"] == "invoice.payment_failed":
            await self._handle_invoice_failed(event["data"]["object"])
        elif event["type"] == "checkout.session.completed":
            await self._handle_checkout_completed(event["data"]["object"])
            
        return {"status": "success", "event_type": event["type"]}
    
    async def _handle_subscription_updated(self, stripe_subscription):
        """Handle subscription update from Stripe"""
        async with self.get_db() as db:
            subscription = await db.query(Subscription).filter(
                Subscription.stripe_subscription_id == stripe_subscription.id
            ).first()
            
            if subscription:
                # Update subscription status
                status_map = {
                    "active": SubscriptionStatus.ACTIVE,
                    "past_due": SubscriptionStatus.PAST_DUE,
                    "canceled": SubscriptionStatus.CANCELLED,
                    "unpaid": SubscriptionStatus.PAST_DUE,
                    "trialing": SubscriptionStatus.TRIALING
                }
                
                subscription.status = status_map.get(
                    stripe_subscription.status,
                    SubscriptionStatus.ACTIVE
                )
                subscription.current_period_start = datetime.fromtimestamp(
                    stripe_subscription.current_period_start
                )
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_subscription.current_period_end
                )
                
                # Handle cluster member status changes
                if subscription.subscription_type == SubscriptionType.CLUSTER_MEMBER:
                    await self._update_cluster_member_status(subscription, stripe_subscription.status)
                
                await db.commit()
    
    async def _update_cluster_member_status(self, subscription: Subscription, stripe_status: str):
        """Update cluster member status based on subscription status"""
        from src.models.database.clusters import ClusterMember, MemberStatus
        
        async with self.get_db() as db:
            # Find cluster member for this subscription
            member = await db.query(ClusterMember).filter(
                ClusterMember.cluster_id == subscription.cluster_id,
                ClusterMember.user_id == subscription.user_id
            ).first()
            
            if member:
                if stripe_status == "active":
                    member.status = MemberStatus.ACTIVE
                elif stripe_status in ["past_due", "unpaid"]:
                    member.status = MemberStatus.SUSPENDED
                elif stripe_status == "canceled":
                    member.status = MemberStatus.REMOVED
                    member.left_at = datetime.now()
                
                await db.commit()
    
    # ==================== Payment Method Management ====================
    
    async def attach_payment_method(
        self,
        user: User,
        payment_method_id: str,
        set_as_default: bool = True
    ) -> PaymentMethod:
        """Attach a payment method to a user"""
        customer_id = await self.create_or_update_customer(user)
        
        # Attach to Stripe customer
        stripe_pm = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id
        )
        
        if set_as_default:
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )
        
        # Save to database
        async with self.get_db() as db:
            # If setting as default, unset other defaults
            if set_as_default:
                await db.execute(
                    "UPDATE payment_methods SET is_default = false WHERE user_id = :user_id",
                    {"user_id": user.id}
                )
            
            payment_method = PaymentMethod(
                user_id=user.id,
                stripe_payment_method_id=payment_method_id,
                type=stripe_pm.type,
                brand=stripe_pm.card.brand if stripe_pm.card else None,
                last4=stripe_pm.card.last4 if stripe_pm.card else None,
                exp_month=stripe_pm.card.exp_month if stripe_pm.card else None,
                exp_year=stripe_pm.card.exp_year if stripe_pm.card else None,
                is_default=set_as_default
            )
            db.add(payment_method)
            await db.commit()
            await db.refresh(payment_method)
            
        return payment_method