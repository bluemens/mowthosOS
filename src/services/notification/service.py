"""Notification service for handling various types of notifications."""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
import asyncio
import logging
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..base import BaseService
from ..cache.service import CacheService, CacheNamespace
from ...models.schemas import (
    Notification, NotificationType, NotificationChannel,
    NotificationPriority, NotificationTemplate
)
from ...core.config import settings

logger = logging.getLogger(__name__)

class NotificationEvent(Enum):
    """Types of notification events."""
    # Mower events
    MOWER_STARTED = "mower_started"
    MOWER_COMPLETED = "mower_completed"
    MOWER_ERROR = "mower_error"
    MOWER_LOW_BATTERY = "mower_low_battery"
    MOWER_STUCK = "mower_stuck"
    MOWER_MAINTENANCE_DUE = "mower_maintenance_due"
    
    # Cluster events
    CLUSTER_CREATED = "cluster_created"
    CLUSTER_JOINED = "cluster_joined"
    CLUSTER_LEFT = "cluster_left"
    CLUSTER_FULL = "cluster_full"
    NEIGHBOR_REQUEST = "neighbor_request"
    
    # Schedule events
    SCHEDULE_REMINDER = "schedule_reminder"
    SCHEDULE_CHANGED = "schedule_changed"
    SCHEDULE_CONFLICT = "schedule_conflict"
    
    # System events
    SYSTEM_UPDATE = "system_update"
    PAYMENT_DUE = "payment_due"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"

class NotificationService(BaseService):
    """Service for managing notifications across multiple channels."""
    
    def __init__(self):
        """Initialize the notification service."""
        super().__init__("notification")
        self.cache_service = CacheService()
        self.templates: Dict[str, NotificationTemplate] = {}
        self.websocket_connections: Dict[str, Any] = {}
        self.notification_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        
        # Channel configurations
        self.email_enabled = bool(settings.smtp_host)
        self.sms_enabled = bool(settings.twilio_account_sid)
        self.push_enabled = bool(settings.fcm_server_key)
        
    async def initialize(self) -> None:
        """Initialize the notification service."""
        await super().initialize()
        
        # Initialize cache service
        await self.cache_service.initialize()
        
        # Load notification templates
        await self._load_templates()
        
        # Start notification worker
        self._worker_task = asyncio.create_task(self._notification_worker())
        
    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Stop worker
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
                
        # Close WebSocket connections
        for ws in self.websocket_connections.values():
            await ws.close()
        self.websocket_connections.clear()
        
        # Cleanup cache service
        await self.cache_service.cleanup()
        
        await super().cleanup()
        
    async def send_notification(
        self,
        user_id: int,
        event: NotificationEvent,
        data: Dict[str, Any],
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send a notification to a user.
        
        Args:
            user_id: User ID to send to
            event: Type of notification event
            data: Event data for template rendering
            channels: Specific channels to use (None for user preferences)
            priority: Notification priority
            
        Returns:
            True if notification queued successfully
        """
        try:
            # Get user preferences if channels not specified
            if channels is None:
                channels = await self._get_user_channels(user_id)
                
            # Create notification
            notification = Notification(
                notification_id=f"notif_{user_id}_{datetime.now().timestamp()}",
                user_id=user_id,
                event_type=event,
                channels=channels,
                priority=priority,
                data=data,
                created_at=datetime.now(),
                status="pending"
            )
            
            # Queue notification
            await self.notification_queue.put(notification)
            
            # Store in cache for tracking
            await self.cache_service.set(
                f"notification:{notification.notification_id}",
                notification.dict(),
                namespace=CacheNamespace.NOTIFICATION_QUEUE,
                ttl=86400  # 24 hours
            )
            
            self.logger.info(f"Notification queued: {notification.notification_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue notification: {str(e)}")
            return False
            
    async def send_bulk_notifications(
        self,
        user_ids: List[int],
        event: NotificationEvent,
        data: Dict[str, Any],
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[int, bool]:
        """Send notifications to multiple users.
        
        Args:
            user_ids: List of user IDs
            event: Type of notification event
            data: Event data for template rendering
            channels: Specific channels to use
            priority: Notification priority
            
        Returns:
            Dictionary of user_id -> success status
        """
        results = {}
        
        tasks = []
        for user_id in user_ids:
            task = self.send_notification(user_id, event, data, channels, priority)
            tasks.append((user_id, task))
            
        for user_id, task in tasks:
            results[user_id] = await task
            
        return results
        
    async def send_cluster_notification(
        self,
        cluster_id: str,
        event: NotificationEvent,
        data: Dict[str, Any],
        exclude_users: Optional[List[int]] = None
    ) -> Dict[int, bool]:
        """Send notification to all users in a cluster.
        
        Args:
            cluster_id: Cluster ID
            event: Type of notification event
            data: Event data
            exclude_users: User IDs to exclude
            
        Returns:
            Dictionary of user_id -> success status
        """
        # Get cluster members from cache or database
        cluster_members = await self._get_cluster_members(cluster_id)
        
        if exclude_users:
            cluster_members = [uid for uid in cluster_members if uid not in exclude_users]
            
        return await self.send_bulk_notifications(cluster_members, event, data)
        
    async def register_websocket(self, user_id: int, websocket: Any) -> None:
        """Register a WebSocket connection for real-time notifications.
        
        Args:
            user_id: User ID
            websocket: WebSocket connection object
        """
        ws_id = f"ws_{user_id}_{datetime.now().timestamp()}"
        self.websocket_connections[ws_id] = {
            "user_id": user_id,
            "websocket": websocket,
            "connected_at": datetime.now()
        }
        self.logger.info(f"WebSocket registered for user {user_id}")
        
    async def unregister_websocket(self, websocket: Any) -> None:
        """Unregister a WebSocket connection.
        
        Args:
            websocket: WebSocket connection object
        """
        to_remove = []
        for ws_id, conn in self.websocket_connections.items():
            if conn["websocket"] == websocket:
                to_remove.append(ws_id)
                
        for ws_id in to_remove:
            del self.websocket_connections[ws_id]
            self.logger.info(f"WebSocket unregistered: {ws_id}")
            
    async def get_user_notifications(
        self,
        user_id: int,
        limit: int = 50,
        include_read: bool = False
    ) -> List[Notification]:
        """Get notifications for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of notifications
            include_read: Whether to include read notifications
            
        Returns:
            List of notifications
        """
        # Get from cache
        pattern = f"user_notification:{user_id}:*"
        keys = await self.cache_service.get_set_members(
            f"user_notifications:{user_id}",
            CacheNamespace.NOTIFICATION_QUEUE
        )
        
        notifications = []
        for key in list(keys)[:limit]:
            notif_data = await self.cache_service.get(
                key,
                CacheNamespace.NOTIFICATION_QUEUE
            )
            if notif_data:
                notification = Notification(**notif_data)
                if include_read or notification.status != "read":
                    notifications.append(notification)
                    
        return sorted(notifications, key=lambda x: x.created_at, reverse=True)
        
    async def mark_notification_read(
        self,
        notification_id: str,
        user_id: int
    ) -> bool:
        """Mark a notification as read.
        
        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)
            
        Returns:
            True if marked successfully
        """
        notif_data = await self.cache_service.get(
            f"notification:{notification_id}",
            CacheNamespace.NOTIFICATION_QUEUE
        )
        
        if notif_data and notif_data.get("user_id") == user_id:
            notif_data["status"] = "read"
            notif_data["read_at"] = datetime.now().isoformat()
            
            await self.cache_service.set(
                f"notification:{notification_id}",
                notif_data,
                CacheNamespace.NOTIFICATION_QUEUE
            )
            return True
            
        return False
        
    async def get_notification_stats(self, user_id: int) -> Dict[str, Any]:
        """Get notification statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of statistics
        """
        notifications = await self.get_user_notifications(user_id, include_read=True)
        
        stats = {
            "total": len(notifications),
            "unread": sum(1 for n in notifications if n.status != "read"),
            "by_channel": {},
            "by_priority": {},
            "by_event": {}
        }
        
        for notif in notifications:
            # By channel
            for channel in notif.channels:
                channel_name = channel.value
                stats["by_channel"][channel_name] = stats["by_channel"].get(channel_name, 0) + 1
                
            # By priority
            priority_name = notif.priority.value
            stats["by_priority"][priority_name] = stats["by_priority"].get(priority_name, 0) + 1
            
            # By event
            event_name = notif.event_type.value
            stats["by_event"][event_name] = stats["by_event"].get(event_name, 0) + 1
            
        return stats
        
    # Private methods
    
    async def _notification_worker(self) -> None:
        """Background worker to process notification queue."""
        while True:
            try:
                # Get notification from queue
                notification = await self.notification_queue.get()
                
                # Process based on priority
                if notification.priority == NotificationPriority.URGENT:
                    await self._process_notification(notification)
                else:
                    # Batch process normal priority
                    await asyncio.sleep(1)  # Small delay for batching
                    await self._process_notification(notification)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Notification worker error: {str(e)}")
                await asyncio.sleep(5)  # Back off on error
                
    async def _process_notification(self, notification: Notification) -> None:
        """Process a single notification."""
        try:
            # Get template
            template = self.templates.get(notification.event_type.value)
            if not template:
                self.logger.warning(f"No template for event: {notification.event_type}")
                return
                
            # Render content
            content = await self._render_template(template, notification.data)
            
            # Send through each channel
            results = {}
            for channel in notification.channels:
                if channel == NotificationChannel.EMAIL:
                    results["email"] = await self._send_email(
                        notification.user_id,
                        content["subject"],
                        content["body"]
                    )
                elif channel == NotificationChannel.SMS:
                    results["sms"] = await self._send_sms(
                        notification.user_id,
                        content["sms_body"]
                    )
                elif channel == NotificationChannel.PUSH:
                    results["push"] = await self._send_push(
                        notification.user_id,
                        content["title"],
                        content["body"]
                    )
                elif channel == NotificationChannel.WEBSOCKET:
                    results["websocket"] = await self._send_websocket(
                        notification.user_id,
                        notification
                    )
                    
            # Update notification status
            all_success = all(results.values())
            notification.status = "sent" if all_success else "partial"
            notification.sent_at = datetime.now()
            notification.results = results
            
            # Update in cache
            await self.cache_service.set(
                f"notification:{notification.notification_id}",
                notification.dict(),
                CacheNamespace.NOTIFICATION_QUEUE
            )
            
            # Add to user's notification list
            await self.cache_service.add_to_set(
                f"user_notifications:{notification.user_id}",
                [f"notification:{notification.notification_id}"],
                CacheNamespace.NOTIFICATION_QUEUE
            )
            
        except Exception as e:
            self.logger.error(f"Failed to process notification: {str(e)}")
            notification.status = "failed"
            notification.error = str(e)
            
    async def _send_email(self, user_id: int, subject: str, body: str) -> bool:
        """Send email notification."""
        if not self.email_enabled:
            return False
            
        try:
            # Get user email from database/cache
            user_email = await self._get_user_email(user_id)
            if not user_email:
                return False
                
            # TODO: Implement actual email sending
            # For now, just log
            self.logger.info(f"Email to {user_email}: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"Email send failed: {str(e)}")
            return False
            
    async def _send_sms(self, user_id: int, message: str) -> bool:
        """Send SMS notification."""
        if not self.sms_enabled:
            return False
            
        try:
            # Get user phone from database/cache
            user_phone = await self._get_user_phone(user_id)
            if not user_phone:
                return False
                
            # TODO: Implement actual SMS sending via Twilio
            # For now, just log
            self.logger.info(f"SMS to {user_phone}: {message}")
            return True
            
        except Exception as e:
            self.logger.error(f"SMS send failed: {str(e)}")
            return False
            
    async def _send_push(self, user_id: int, title: str, body: str) -> bool:
        """Send push notification."""
        if not self.push_enabled:
            return False
            
        try:
            # Get user device tokens from database/cache
            device_tokens = await self._get_user_device_tokens(user_id)
            if not device_tokens:
                return False
                
            # TODO: Implement actual push notification via FCM
            # For now, just log
            self.logger.info(f"Push to user {user_id}: {title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Push send failed: {str(e)}")
            return False
            
    async def _send_websocket(self, user_id: int, notification: Notification) -> bool:
        """Send WebSocket notification."""
        try:
            sent = False
            for conn in self.websocket_connections.values():
                if conn["user_id"] == user_id:
                    websocket = conn["websocket"]
                    message = {
                        "type": "notification",
                        "data": notification.dict()
                    }
                    await websocket.send_json(message)
                    sent = True
                    
            return sent
            
        except Exception as e:
            self.logger.error(f"WebSocket send failed: {str(e)}")
            return False
            
    async def _load_templates(self) -> None:
        """Load notification templates."""
        # Default templates
        self.templates = {
            NotificationEvent.MOWER_STARTED.value: NotificationTemplate(
                subject="Mowing Started",
                body="Your mower {mower_name} has started mowing.",
                sms_body="Mower {mower_name} started",
                title="Mowing Started"
            ),
            NotificationEvent.MOWER_COMPLETED.value: NotificationTemplate(
                subject="Mowing Completed",
                body="Your mower {mower_name} has completed mowing. Area covered: {area_sqm} sqm",
                sms_body="Mower {mower_name} completed. Area: {area_sqm}sqm",
                title="Mowing Complete"
            ),
            NotificationEvent.MOWER_ERROR.value: NotificationTemplate(
                subject="Mower Error",
                body="Your mower {mower_name} encountered an error: {error_message}",
                sms_body="Mower error: {error_message}",
                title="Mower Error"
            ),
            NotificationEvent.CLUSTER_JOINED.value: NotificationTemplate(
                subject="New Neighbor Joined",
                body="{neighbor_name} has joined your cluster at {address}",
                sms_body="New neighbor joined your cluster",
                title="New Cluster Member"
            ),
            NotificationEvent.SCHEDULE_REMINDER.value: NotificationTemplate(
                subject="Mowing Schedule Reminder",
                body="Your mowing is scheduled for {schedule_time}",
                sms_body="Mowing scheduled: {schedule_time}",
                title="Schedule Reminder"
            )
        }
        
    async def _render_template(
        self,
        template: NotificationTemplate,
        data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render notification template with data."""
        rendered = {}
        
        for field in ["subject", "body", "sms_body", "title"]:
            if hasattr(template, field):
                value = getattr(template, field)
                if value:
                    # Simple string formatting
                    try:
                        rendered[field] = value.format(**data)
                    except KeyError:
                        rendered[field] = value
                        
        return rendered
        
    async def _get_user_channels(self, user_id: int) -> List[NotificationChannel]:
        """Get user's preferred notification channels."""
        # TODO: Get from user preferences in database
        # For now, return all channels
        return [
            NotificationChannel.EMAIL,
            NotificationChannel.WEBSOCKET
        ]
        
    async def _get_user_email(self, user_id: int) -> Optional[str]:
        """Get user's email address."""
        # TODO: Get from database
        return f"user{user_id}@example.com"
        
    async def _get_user_phone(self, user_id: int) -> Optional[str]:
        """Get user's phone number."""
        # TODO: Get from database
        return None
        
    async def _get_user_device_tokens(self, user_id: int) -> List[str]:
        """Get user's device tokens for push notifications."""
        # TODO: Get from database
        return []
        
    async def _get_cluster_members(self, cluster_id: str) -> List[int]:
        """Get all members of a cluster."""
        # TODO: Get from database or cluster service
        return []