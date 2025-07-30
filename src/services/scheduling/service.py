"""Scheduling service for managing mowing schedules and optimization."""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, time
from enum import Enum
import asyncio
import logging
from collections import defaultdict
import uuid

from ..base import BaseService
from ..cache.service import CacheService, CacheNamespace
from ..notification.service import NotificationService, NotificationEvent
from ...models.schemas import (
    Schedule, ScheduleType, ScheduleFrequency, ScheduleStatus,
    TimeSlot, ScheduleConflict, ScheduleOptimization
)
from ...core.config import settings

logger = logging.getLogger(__name__)

class ScheduleEvent(Enum):
    """Types of schedule events."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CONFLICTED = "conflicted"

class SchedulingService(BaseService):
    """Service for managing mowing schedules."""
    
    def __init__(self):
        """Initialize the scheduling service."""
        super().__init__("scheduling")
        self.cache_service = CacheService()
        self.notification_service = NotificationService()
        self.active_schedules: Dict[str, Schedule] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.max_daily_sessions = 3
        self.min_session_gap_minutes = 30
        self.default_session_duration_minutes = 60
        self.weather_check_enabled = True
        self.battery_threshold = 30  # Minimum battery % to start
        
    async def initialize(self) -> None:
        """Initialize the scheduling service."""
        await super().initialize()
        
        # Initialize dependent services
        await self.cache_service.initialize()
        
        # Load active schedules
        await self._load_active_schedules()
        
        # Start scheduler task
        self._scheduler_task = asyncio.create_task(self._scheduler_worker())
        
    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Stop scheduler
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
                
        await super().cleanup()
        
    async def create_schedule(
        self,
        user_id: int,
        device_name: str,
        schedule_type: ScheduleType,
        time_slots: List[TimeSlot],
        frequency: ScheduleFrequency = ScheduleFrequency.WEEKLY,
        name: Optional[str] = None
    ) -> Schedule:
        """Create a new mowing schedule.
        
        Args:
            user_id: User ID
            device_name: Device to schedule
            schedule_type: Type of schedule
            time_slots: Time slots for mowing
            frequency: Schedule frequency
            name: Optional schedule name
            
        Returns:
            Created schedule
        """
        try:
            # Validate time slots
            await self._validate_time_slots(time_slots)
            
            # Check for conflicts
            conflicts = await self.check_conflicts(
                user_id, device_name, time_slots
            )
            
            if conflicts:
                raise Exception(f"Schedule conflicts detected: {len(conflicts)} conflicts")
                
            # Create schedule
            schedule_id = f"schedule_{user_id}_{uuid.uuid4().hex[:8]}"
            schedule = Schedule(
                schedule_id=schedule_id,
                user_id=user_id,
                device_name=device_name,
                name=name or f"Schedule for {device_name}",
                schedule_type=schedule_type,
                frequency=frequency,
                time_slots=time_slots,
                is_active=True,
                created_at=datetime.now(),
                next_run=await self._calculate_next_run(time_slots, frequency)
            )
            
            # Store schedule
            await self._store_schedule(schedule)
            
            # Send notification
            await self.notification_service.send_notification(
                user_id,
                NotificationEvent.SCHEDULE_CHANGED,
                {
                    "schedule_name": schedule.name,
                    "device_name": device_name,
                    "action": "created"
                }
            )
            
            self.logger.info(f"Created schedule {schedule_id} for user {user_id}")
            return schedule
            
        except Exception as e:
            self.logger.error(f"Failed to create schedule: {str(e)}")
            raise
            
    async def update_schedule(
        self,
        schedule_id: str,
        user_id: int,
        updates: Dict[str, Any]
    ) -> Schedule:
        """Update an existing schedule.
        
        Args:
            schedule_id: Schedule ID
            user_id: User ID (for verification)
            updates: Fields to update
            
        Returns:
            Updated schedule
        """
        schedule = await self.get_schedule(schedule_id)
        
        if not schedule or schedule.user_id != user_id:
            raise Exception("Schedule not found or unauthorized")
            
        # Update fields
        for field, value in updates.items():
            if hasattr(schedule, field):
                setattr(schedule, field, value)
                
        schedule.updated_at = datetime.now()
        
        # Recalculate next run if time slots changed
        if "time_slots" in updates:
            schedule.next_run = await self._calculate_next_run(
                schedule.time_slots, schedule.frequency
            )
            
        # Store updated schedule
        await self._store_schedule(schedule)
        
        # Send notification
        await self.notification_service.send_notification(
            user_id,
            NotificationEvent.SCHEDULE_CHANGED,
            {
                "schedule_name": schedule.name,
                "device_name": schedule.device_name,
                "action": "updated"
            }
        )
        
        return schedule
        
    async def delete_schedule(
        self,
        schedule_id: str,
        user_id: int
    ) -> bool:
        """Delete a schedule.
        
        Args:
            schedule_id: Schedule ID
            user_id: User ID (for verification)
            
        Returns:
            True if deleted successfully
        """
        schedule = await self.get_schedule(schedule_id)
        
        if not schedule or schedule.user_id != user_id:
            return False
            
        # Mark as deleted
        schedule.is_active = False
        schedule.deleted_at = datetime.now()
        
        await self._store_schedule(schedule)
        
        # Remove from active schedules
        if schedule_id in self.active_schedules:
            del self.active_schedules[schedule_id]
            
        # Send notification
        await self.notification_service.send_notification(
            user_id,
            NotificationEvent.SCHEDULE_CHANGED,
            {
                "schedule_name": schedule.name,
                "device_name": schedule.device_name,
                "action": "deleted"
            }
        )
        
        return True
        
    async def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID.
        
        Args:
            schedule_id: Schedule ID
            
        Returns:
            Schedule or None
        """
        # Check cache first
        cached = await self.cache_service.get(
            schedule_id,
            CacheNamespace.SCHEDULE_DATA
        )
        
        if cached:
            return Schedule(**cached)
            
        # TODO: Get from database
        return self.active_schedules.get(schedule_id)
        
    async def get_user_schedules(
        self,
        user_id: int,
        active_only: bool = True
    ) -> List[Schedule]:
        """Get all schedules for a user.
        
        Args:
            user_id: User ID
            active_only: Whether to return only active schedules
            
        Returns:
            List of schedules
        """
        schedules = []
        
        for schedule in self.active_schedules.values():
            if schedule.user_id == user_id:
                if not active_only or schedule.is_active:
                    schedules.append(schedule)
                    
        return sorted(schedules, key=lambda x: x.created_at, reverse=True)
        
    async def get_device_schedules(
        self,
        device_name: str,
        active_only: bool = True
    ) -> List[Schedule]:
        """Get all schedules for a device.
        
        Args:
            device_name: Device name
            active_only: Whether to return only active schedules
            
        Returns:
            List of schedules
        """
        schedules = []
        
        for schedule in self.active_schedules.values():
            if schedule.device_name == device_name:
                if not active_only or schedule.is_active:
                    schedules.append(schedule)
                    
        return sorted(schedules, key=lambda x: x.created_at, reverse=True)
        
    async def check_conflicts(
        self,
        user_id: int,
        device_name: str,
        time_slots: List[TimeSlot],
        exclude_schedule_id: Optional[str] = None
    ) -> List[ScheduleConflict]:
        """Check for scheduling conflicts.
        
        Args:
            user_id: User ID
            device_name: Device name
            time_slots: Time slots to check
            exclude_schedule_id: Schedule ID to exclude from check
            
        Returns:
            List of conflicts
        """
        conflicts = []
        
        # Get existing schedules
        existing_schedules = await self.get_device_schedules(device_name)
        
        for schedule in existing_schedules:
            if schedule.schedule_id == exclude_schedule_id:
                continue
                
            # Check each time slot
            for new_slot in time_slots:
                for existing_slot in schedule.time_slots:
                    if self._slots_overlap(new_slot, existing_slot):
                        conflict = ScheduleConflict(
                            schedule_id=schedule.schedule_id,
                            conflicting_slot=existing_slot,
                            reason="Time slot overlap"
                        )
                        conflicts.append(conflict)
                        
        # Check cluster conflicts
        cluster_conflicts = await self._check_cluster_conflicts(
            user_id, time_slots
        )
        conflicts.extend(cluster_conflicts)
        
        return conflicts
        
    async def optimize_cluster_schedules(
        self,
        cluster_id: str
    ) -> ScheduleOptimization:
        """Optimize schedules for a cluster.
        
        Args:
            cluster_id: Cluster ID
            
        Returns:
            Schedule optimization results
        """
        # Get all schedules in cluster
        cluster_schedules = await self._get_cluster_schedules(cluster_id)
        
        if not cluster_schedules:
            return ScheduleOptimization(
                cluster_id=cluster_id,
                original_schedules=0,
                optimized_schedules=0,
                conflicts_resolved=0,
                efficiency_gain=0.0
            )
            
        # Group by time slots
        slot_groups = defaultdict(list)
        for schedule in cluster_schedules:
            for slot in schedule.time_slots:
                key = (slot.day_of_week, slot.start_time.hour)
                slot_groups[key].append((schedule, slot))
                
        # Optimize by spreading out schedules
        optimizations = []
        conflicts_resolved = 0
        
        for key, group in slot_groups.items():
            if len(group) > 1:
                # Stagger start times
                for i, (schedule, slot) in enumerate(group):
                    new_start = slot.start_time.replace(
                        minute=i * 15  # 15-minute intervals
                    )
                    if new_start != slot.start_time:
                        optimizations.append({
                            "schedule_id": schedule.schedule_id,
                            "old_slot": slot,
                            "new_slot": TimeSlot(
                                day_of_week=slot.day_of_week,
                                start_time=new_start,
                                duration_minutes=slot.duration_minutes
                            )
                        })
                        conflicts_resolved += 1
                        
        # Calculate efficiency gain
        total_time_before = len(cluster_schedules) * self.default_session_duration_minutes
        unique_time_slots_after = len(set(
            (opt["new_slot"].day_of_week, opt["new_slot"].start_time)
            for opt in optimizations
        ))
        efficiency_gain = (1 - unique_time_slots_after / len(cluster_schedules)) * 100
        
        return ScheduleOptimization(
            cluster_id=cluster_id,
            original_schedules=len(cluster_schedules),
            optimized_schedules=len(optimizations),
            conflicts_resolved=conflicts_resolved,
            efficiency_gain=efficiency_gain,
            recommendations=optimizations
        )
        
    async def get_next_scheduled_session(
        self,
        device_name: str
    ) -> Optional[Tuple[Schedule, datetime]]:
        """Get the next scheduled session for a device.
        
        Args:
            device_name: Device name
            
        Returns:
            Tuple of (schedule, next_run_time) or None
        """
        schedules = await self.get_device_schedules(device_name)
        
        if not schedules:
            return None
            
        # Find the earliest next run
        earliest_schedule = None
        earliest_time = None
        
        for schedule in schedules:
            if schedule.next_run:
                if earliest_time is None or schedule.next_run < earliest_time:
                    earliest_schedule = schedule
                    earliest_time = schedule.next_run
                    
        if earliest_schedule:
            return (earliest_schedule, earliest_time)
            
        return None
        
    async def skip_next_session(
        self,
        schedule_id: str,
        user_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """Skip the next scheduled session.
        
        Args:
            schedule_id: Schedule ID
            user_id: User ID (for verification)
            reason: Optional reason for skipping
            
        Returns:
            True if skipped successfully
        """
        schedule = await self.get_schedule(schedule_id)
        
        if not schedule or schedule.user_id != user_id:
            return False
            
        # Record skip
        if not hasattr(schedule, 'skip_history'):
            schedule.skip_history = []
            
        schedule.skip_history.append({
            "skipped_at": datetime.now(),
            "scheduled_time": schedule.next_run,
            "reason": reason
        })
        
        # Calculate next run after skip
        schedule.next_run = await self._calculate_next_run(
            schedule.time_slots,
            schedule.frequency,
            skip_current=True
        )
        
        await self._store_schedule(schedule)
        
        # Send notification
        await self.notification_service.send_notification(
            user_id,
            NotificationEvent.SCHEDULE_CHANGED,
            {
                "schedule_name": schedule.name,
                "action": "skipped",
                "reason": reason or "User requested"
            }
        )
        
        return True
        
    async def get_schedule_history(
        self,
        schedule_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get execution history for a schedule.
        
        Args:
            schedule_id: Schedule ID
            days: Number of days of history
            
        Returns:
            List of historical executions
        """
        # TODO: Get from database
        # For now, return empty list
        return []
        
    # Private methods
    
    async def _scheduler_worker(self) -> None:
        """Background worker to process schedules."""
        while True:
            try:
                # Check schedules every minute
                await asyncio.sleep(60)
                
                now = datetime.now()
                
                for schedule in self.active_schedules.values():
                    if not schedule.is_active or not schedule.next_run:
                        continue
                        
                    # Check if it's time to run
                    if schedule.next_run <= now:
                        await self._execute_schedule(schedule)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Scheduler worker error: {str(e)}")
                await asyncio.sleep(5)
                
    async def _execute_schedule(self, schedule: Schedule) -> None:
        """Execute a scheduled mowing session."""
        try:
            self.logger.info(f"Executing schedule {schedule.schedule_id}")
            
            # Check conditions
            if not await self._check_execution_conditions(schedule):
                self.logger.info(f"Conditions not met for schedule {schedule.schedule_id}")
                return
                
            # Send reminder notification
            await self.notification_service.send_notification(
                schedule.user_id,
                NotificationEvent.SCHEDULE_REMINDER,
                {
                    "schedule_name": schedule.name,
                    "device_name": schedule.device_name,
                    "schedule_time": schedule.next_run.isoformat()
                }
            )
            
            # TODO: Actually start mowing via MowerService
            # For now, just log
            self.logger.info(f"Starting mowing for schedule {schedule.schedule_id}")
            
            # Update schedule
            schedule.last_run = datetime.now()
            schedule.run_count = getattr(schedule, 'run_count', 0) + 1
            schedule.next_run = await self._calculate_next_run(
                schedule.time_slots,
                schedule.frequency
            )
            
            await self._store_schedule(schedule)
            
        except Exception as e:
            self.logger.error(f"Failed to execute schedule: {str(e)}")
            
    async def _check_execution_conditions(self, schedule: Schedule) -> bool:
        """Check if conditions are met to execute schedule."""
        # Check weather if enabled
        if self.weather_check_enabled:
            weather_ok = await self._check_weather_conditions()
            if not weather_ok:
                return False
                
        # TODO: Check device battery level
        # TODO: Check if device is available
        
        return True
        
    async def _check_weather_conditions(self) -> bool:
        """Check if weather conditions are suitable for mowing."""
        # TODO: Integrate with weather API
        # For now, always return True
        return True
        
    async def _validate_time_slots(self, time_slots: List[TimeSlot]) -> None:
        """Validate time slots."""
        if not time_slots:
            raise ValueError("At least one time slot is required")
            
        for slot in time_slots:
            if slot.duration_minutes < 15:
                raise ValueError("Minimum duration is 15 minutes")
            if slot.duration_minutes > 240:
                raise ValueError("Maximum duration is 4 hours")
                
    def _slots_overlap(self, slot1: TimeSlot, slot2: TimeSlot) -> bool:
        """Check if two time slots overlap."""
        if slot1.day_of_week != slot2.day_of_week:
            return False
            
        # Convert to minutes for easier comparison
        slot1_start = slot1.start_time.hour * 60 + slot1.start_time.minute
        slot1_end = slot1_start + slot1.duration_minutes
        
        slot2_start = slot2.start_time.hour * 60 + slot2.start_time.minute
        slot2_end = slot2_start + slot2.duration_minutes
        
        return not (slot1_end <= slot2_start or slot2_end <= slot1_start)
        
    async def _calculate_next_run(
        self,
        time_slots: List[TimeSlot],
        frequency: ScheduleFrequency,
        skip_current: bool = False
    ) -> Optional[datetime]:
        """Calculate the next run time for a schedule."""
        if not time_slots:
            return None
            
        now = datetime.now()
        current_weekday = now.weekday()
        
        # Find next matching time slot
        for days_ahead in range(7 if not skip_current else 1, 14):
            check_date = now + timedelta(days=days_ahead)
            check_weekday = check_date.weekday()
            
            for slot in time_slots:
                if slot.day_of_week == check_weekday:
                    next_run = check_date.replace(
                        hour=slot.start_time.hour,
                        minute=slot.start_time.minute,
                        second=0,
                        microsecond=0
                    )
                    
                    if next_run > now:
                        # Check frequency
                        if frequency == ScheduleFrequency.DAILY:
                            return next_run
                        elif frequency == ScheduleFrequency.WEEKLY:
                            return next_run
                        elif frequency == ScheduleFrequency.BIWEEKLY:
                            # Only on even weeks
                            if check_date.isocalendar()[1] % 2 == 0:
                                return next_run
                        elif frequency == ScheduleFrequency.MONTHLY:
                            # Only if day of month matches
                            if check_date.day <= 7:  # First week of month
                                return next_run
                                
        return None
        
    async def _store_schedule(self, schedule: Schedule) -> None:
        """Store schedule in cache and database."""
        # Store in cache
        await self.cache_service.set(
            schedule.schedule_id,
            schedule.dict(),
            CacheNamespace.SCHEDULE_DATA
        )
        
        # Store in active schedules
        if schedule.is_active:
            self.active_schedules[schedule.schedule_id] = schedule
        elif schedule.schedule_id in self.active_schedules:
            del self.active_schedules[schedule.schedule_id]
            
        # TODO: Store in database
        
    async def _load_active_schedules(self) -> None:
        """Load active schedules from database."""
        # TODO: Load from database
        # For now, just log
        self.logger.info("Loading active schedules...")
        
    async def _check_cluster_conflicts(
        self,
        user_id: int,
        time_slots: List[TimeSlot]
    ) -> List[ScheduleConflict]:
        """Check for conflicts within a cluster."""
        # TODO: Get user's cluster and check neighbor schedules
        return []
        
    async def _get_cluster_schedules(self, cluster_id: str) -> List[Schedule]:
        """Get all schedules in a cluster."""
        # TODO: Get from database
        return []