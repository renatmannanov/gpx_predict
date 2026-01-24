"""
Strava Activity Sync Service

Background service for gradually syncing user activities.
Designed to respect Strava API rate limits even with many users.

Strategy:
- Global queue of users to sync
- Process one batch per interval (e.g., every 5 minutes)
- Each batch syncs a few activities per user
- Prioritize new users and users who haven't synced recently
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from collections import deque

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Union

from app.config import settings
from app.models.user import User
from app.models.strava_token import StravaToken
from app.models.strava_activity import StravaActivity, StravaActivitySplit, StravaSyncStatus
from app.models.notification import Notification
from app.services.user_profile import UserProfileService

logger = logging.getLogger(__name__)


# =============================================================================
# Activity Type Constants
# =============================================================================

# Activity types for hiking profile calculation
ACTIVITY_TYPES_FOR_HIKE_PROFILE = ["Hike", "Walk"]

# Activity types for running profile calculation
ACTIVITY_TYPES_FOR_RUN_PROFILE = ["Run", "TrailRun", "VirtualRun"]

# All supported activity types
ALL_SUPPORTED_ACTIVITY_TYPES = ACTIVITY_TYPES_FOR_HIKE_PROFILE + ACTIVITY_TYPES_FOR_RUN_PROFILE


# =============================================================================
# Sync Configuration
# =============================================================================

class SyncConfig:
    """Configuration for sync behavior."""

    # How many activities to fetch per API call
    ACTIVITIES_PER_PAGE = 30

    # How many activities to sync per user per batch
    ACTIVITIES_PER_USER_BATCH = 10

    # How many users to process per batch
    USERS_PER_BATCH = 5

    # Minimum interval between syncs for same user (hours)
    MIN_SYNC_INTERVAL_HOURS = 6

    # How far back to sync (days)
    MAX_HISTORY_DAYS = 365

    # Delay between API calls (seconds) to respect rate limits
    API_CALL_DELAY = 1.5

    # ==========================================================================
    # Profile Recalculation Strategy (during initial sync)
    # ==========================================================================
    # Recalculate profile at these checkpoints to avoid spam:
    # 1. After first 5 activities (quick feedback)
    # 2. At 30% completion
    # 3. At 60% completion
    # 4. At 100% completion (initial sync done)
    INITIAL_RECALC_AFTER_N_ACTIVITIES = 5
    INITIAL_RECALC_PROGRESS_CHECKPOINTS = [30, 60]  # percent

    # ==========================================================================
    # Post-Initial Sync Strategy
    # ==========================================================================
    # After initial sync is complete, recalculate when:
    # - At least N new activities with splits have been synced
    # This avoids recalculating for every single new activity
    POST_SYNC_RECALC_MIN_NEW_ACTIVITIES = 3


# =============================================================================
# Sync Queue Manager
# =============================================================================

class SyncQueueManager:
    """
    Manages the queue of users to sync.

    Uses a simple deque-based queue with priority for:
    1. New users (never synced)
    2. Users with oldest last_sync
    """

    def __init__(self):
        self._queue: deque[str] = deque()  # user_ids
        self._in_progress: set[str] = set()
        self._lock = asyncio.Lock()

    async def add_user(self, user_id: str, priority: bool = False):
        """Add user to sync queue."""
        async with self._lock:
            if user_id not in self._queue and user_id not in self._in_progress:
                if priority:
                    self._queue.appendleft(user_id)
                else:
                    self._queue.append(user_id)
                logger.debug(f"Added user {user_id} to sync queue (priority={priority})")

    async def get_next_users(self, count: int) -> list[str]:
        """Get next users to sync."""
        async with self._lock:
            users = []
            for _ in range(min(count, len(self._queue))):
                user_id = self._queue.popleft()
                self._in_progress.add(user_id)
                users.append(user_id)
            return users

    async def mark_complete(self, user_id: str):
        """Mark user sync as complete."""
        async with self._lock:
            self._in_progress.discard(user_id)

    async def requeue_user(self, user_id: str):
        """Re-add user to back of queue (for incremental sync)."""
        async with self._lock:
            self._in_progress.discard(user_id)
            if user_id not in self._queue:
                self._queue.append(user_id)

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def in_progress_count(self) -> int:
        return len(self._in_progress)


# Global queue instance
sync_queue = SyncQueueManager()


# =============================================================================
# Sync Service
# =============================================================================

class StravaSyncService:
    """
    Service for syncing Strava activities.

    Supports both sync and async sessions.
    For async session, use async methods with 'await'.
    For sync session (legacy), methods will work but block.
    """

    def __init__(self, db: Union[Session, AsyncSession]):
        self.db = db
        self._is_async = isinstance(db, AsyncSession)

    async def sync_user_activities(
        self,
        user_id: str,
        max_activities: int = SyncConfig.ACTIVITIES_PER_USER_BATCH
    ) -> dict:
        """
        Sync activities for a single user.

        Returns dict with sync results.
        """
        # Get user and token
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.strava_connected:
            return {"status": "skipped", "reason": "not_connected"}

        token = self.db.query(StravaToken).filter(
            StravaToken.user_id == user_id
        ).first()
        if not token:
            return {"status": "skipped", "reason": "no_token"}

        # Get or create sync status
        sync_status = self.db.query(StravaSyncStatus).filter(
            StravaSyncStatus.user_id == user_id
        ).first()

        if not sync_status:
            sync_status = StravaSyncStatus(user_id=user_id)
            self.db.add(sync_status)
            self.db.flush()

        # Check if sync is already in progress
        if sync_status.sync_in_progress:
            return {"status": "skipped", "reason": "already_in_progress"}

        # Mark sync as in progress
        sync_status.sync_in_progress = 1
        self.db.commit()

        try:
            # Get valid access token
            access_token = await self._get_valid_token(token)

            # Determine sync window
            # If never synced, start from now going backwards
            # If synced before, get newer activities
            if sync_status.newest_synced_date:
                # Get newer activities
                after = sync_status.newest_synced_date
                before = None
            else:
                # First sync - get recent activities
                after = datetime.utcnow() - timedelta(days=SyncConfig.MAX_HISTORY_DAYS)
                before = None

            # Fetch activities from Strava
            activities = await self._fetch_activities(
                access_token,
                after=after,
                before=before,
                per_page=max_activities
            )

            # Save activities and sync splits for supported types
            saved_count = 0
            splits_synced_count = 0
            saved_activities = []

            for activity_data in activities:
                activity = self._save_activity(user_id, activity_data)
                if activity:
                    saved_count += 1
                    saved_activities.append(activity)

            # Commit to get activity IDs
            self.db.commit()

            # Sync splits for supported activity types (Hike, Walk, Run, TrailRun)
            for activity in saved_activities:
                if activity.activity_type in ALL_SUPPORTED_ACTIVITY_TYPES:
                    # Delay between API calls to respect rate limits
                    if splits_synced_count > 0:
                        await asyncio.sleep(SyncConfig.API_CALL_DELAY)

                    try:
                        split_result = await self.sync_activity_splits(
                            user_id=user_id,
                            activity_id=activity.id,
                            strava_activity_id=activity.strava_id
                        )
                        if split_result.get("status") == "success":
                            splits_synced_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to sync splits for activity {activity.strava_id}: {e}")
                        # Continue with other activities

            # Update sync status
            if activities:
                dates = [
                    datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")).replace(tzinfo=None)
                    for a in activities
                ]
                newest = max(dates)
                oldest = min(dates)

                if not sync_status.newest_synced_date or newest > sync_status.newest_synced_date:
                    sync_status.newest_synced_date = newest
                if not sync_status.oldest_synced_date or oldest < sync_status.oldest_synced_date:
                    sync_status.oldest_synced_date = oldest

            sync_status.total_activities_synced += saved_count
            sync_status.activities_with_splits = (sync_status.activities_with_splits or 0) + splits_synced_count
            sync_status.last_sync_at = datetime.utcnow()
            sync_status.last_error = None
            sync_status.sync_in_progress = 0

            # Check if we need to send progress notification
            if (saved_count > 0
                and sync_status.total_activities_synced % SyncConfig.PROGRESS_NOTIFICATION_INTERVAL == 0
                and not sync_status.initial_sync_complete):
                self._create_notification(
                    user_id=user_id,
                    notification_type="sync_progress",
                    data={
                        "progress_percent": int(
                            (sync_status.total_activities_synced /
                             (sync_status.total_activities_estimated or 100)) * 100
                        ),
                        "activities_synced": sync_status.total_activities_synced,
                        "total_estimated": sync_status.total_activities_estimated or 0
                    }
                )

            # Check if initial sync is complete (no more new activities)
            was_initial_sync = not sync_status.initial_sync_complete
            if was_initial_sync and len(activities) < max_activities:
                sync_status.initial_sync_complete = 1
                sync_status.last_recalc_checkpoint = 100  # Mark 100% checkpoint
                # Create sync_complete notification
                self._create_notification(
                    user_id=user_id,
                    notification_type="sync_complete",
                    data={
                        "activities_synced": sync_status.total_activities_synced,
                        "activities_with_splits": sync_status.activities_with_splits or 0
                    }
                )
                # Force final profile recalculation at 100% completion
                logger.info(f"Initial sync complete for user {user_id}, forcing final profile recalc")
                await self._force_final_profile_recalc(user_id)

            self.db.commit()

            # Auto-recalculate profiles if we synced splits
            if splits_synced_count > 0:
                await self._auto_recalculate_profiles(
                    user_id, saved_activities, sync_status, splits_synced_count
                )

            logger.info(
                f"Synced {saved_count} activities for user {user_id}: "
                f"{splits_synced_count} activities got splits synced "
                f"(total activities: {sync_status.total_activities_synced}, "
                f"total with splits: {sync_status.activities_with_splits})"
            )

            return {
                "status": "success",
                "fetched": len(activities),
                "saved": saved_count,
                "splits_synced": splits_synced_count,
                "total": sync_status.total_activities_synced
            }

        except Exception as e:
            logger.error(f"Sync failed for user {user_id}: {e}")
            sync_status.last_error = str(e)[:500]
            sync_status.sync_in_progress = 0
            self.db.commit()
            return {"status": "error", "error": str(e)}

    def _create_notification(
        self,
        user_id: str,
        notification_type: str,
        data: Optional[dict] = None
    ):
        """Create a notification for the user."""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            data=data
        )
        self.db.add(notification)
        logger.debug(f"Created notification {notification_type} for user {user_id}")

    def _should_recalculate_profile(
        self,
        sync_status: StravaSyncStatus,
        new_splits_count: int
    ) -> bool:
        """
        Determine if profile should be recalculated based on sync progress.

        During initial sync (4-point strategy):
        1. After first 5 activities with splits
        2. At 30% completion
        3. At 60% completion
        4. At 100% completion

        After initial sync:
        - When at least N new activities have been synced
        """
        if not sync_status.initial_sync_complete:
            # Initial sync - use checkpoint strategy
            return self._check_initial_sync_checkpoint(sync_status)
        else:
            # Post-initial sync - use activity count strategy
            return self._check_post_sync_threshold(sync_status, new_splits_count)

    def _check_initial_sync_checkpoint(self, sync_status: StravaSyncStatus) -> bool:
        """
        Check if we've reached a recalculation checkpoint during initial sync.

        Checkpoints:
        - 5: After first 5 activities with splits
        - 30: At 30% completion
        - 60: At 60% completion
        - 100: At 100% completion (handled separately in sync_complete)
        """
        activities_with_splits = sync_status.activities_with_splits or 0
        last_checkpoint = sync_status.last_recalc_checkpoint or 0
        total_estimated = sync_status.total_activities_estimated or 100

        # Checkpoint 1: After first 5 activities
        if (last_checkpoint < 5 and
            activities_with_splits >= SyncConfig.INITIAL_RECALC_AFTER_N_ACTIVITIES):
            sync_status.last_recalc_checkpoint = 5
            return True

        # Checkpoint 2 & 3: At 30% and 60% completion
        if total_estimated > 0:
            current_percent = (activities_with_splits / total_estimated) * 100

            for checkpoint in SyncConfig.INITIAL_RECALC_PROGRESS_CHECKPOINTS:
                if last_checkpoint < checkpoint and current_percent >= checkpoint:
                    sync_status.last_recalc_checkpoint = checkpoint
                    return True

        return False

    def _check_post_sync_threshold(
        self,
        sync_status: StravaSyncStatus,
        new_splits_count: int
    ) -> bool:
        """
        Check if we should recalculate after initial sync is complete.

        Returns True if enough new activities have accumulated.
        """
        # Track new activities since last recalc
        sync_status.new_activities_since_recalc = (
            (sync_status.new_activities_since_recalc or 0) + new_splits_count
        )

        if sync_status.new_activities_since_recalc >= SyncConfig.POST_SYNC_RECALC_MIN_NEW_ACTIVITIES:
            # Reset counter
            sync_status.new_activities_since_recalc = 0
            return True

        return False

    async def _auto_recalculate_profiles(
        self,
        user_id: str,
        saved_activities: list[StravaActivity],
        sync_status: StravaSyncStatus,
        new_splits_count: int
    ):
        """
        Auto-recalculate user profiles based on sync progress.

        Uses 4-point strategy during initial sync to avoid spam:
        1. After 5 activities
        2. At 30% completion
        3. At 60% completion
        4. At 100% completion
        """
        # Check if we should recalculate
        if not self._should_recalculate_profile(sync_status, new_splits_count):
            logger.debug(
                f"Skipping profile recalc for user {user_id} "
                f"(checkpoint: {sync_status.last_recalc_checkpoint}, "
                f"new since recalc: {sync_status.new_activities_since_recalc})"
            )
            return

        # Determine which profiles need recalculation
        has_hike_activities = any(
            a.activity_type in ACTIVITY_TYPES_FOR_HIKE_PROFILE
            for a in saved_activities
        )
        has_run_activities = any(
            a.activity_type in ACTIVITY_TYPES_FOR_RUN_PROFILE
            for a in saved_activities
        )

        # Need AsyncSession for profile calculation
        if not self._is_async:
            logger.warning("Cannot auto-recalculate profiles with sync session")
            return

        try:
            checkpoint = sync_status.last_recalc_checkpoint or 0
            recalc_reason = f"checkpoint_{checkpoint}" if not sync_status.initial_sync_complete else "incremental"

            # Recalculate hiking profile if we have hike/walk activities
            if has_hike_activities:
                hike_profile = await UserProfileService.calculate_profile_with_splits(
                    user_id, self.db
                )
                if hike_profile:
                    logger.info(
                        f"Auto-recalculated hiking profile for user {user_id} "
                        f"(reason: {recalc_reason})"
                    )
                    self._create_notification(
                        user_id=user_id,
                        notification_type="profile_updated",
                        data={
                            "profile_type": "hiking",
                            "checkpoint": checkpoint,
                            "activities_analyzed": hike_profile.total_hike_activities
                        }
                    )

            # Recalculate running profile if we have run/trail activities
            if has_run_activities:
                run_profile = await UserProfileService.calculate_run_profile_with_splits(
                    user_id, self.db
                )
                if run_profile:
                    logger.info(
                        f"Auto-recalculated running profile for user {user_id} "
                        f"(reason: {recalc_reason})"
                    )
                    self._create_notification(
                        user_id=user_id,
                        notification_type="profile_updated",
                        data={
                            "profile_type": "running",
                            "checkpoint": checkpoint,
                            "activities_analyzed": run_profile.total_activities
                        }
                    )

            if self._is_async:
                await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to auto-recalculate profiles for user {user_id}: {e}")
            # Don't fail the whole sync if profile calculation fails

    async def _force_final_profile_recalc(self, user_id: str):
        """
        Force final profile recalculation when initial sync is complete.

        This is the 4th checkpoint (100%) - always recalculates both profiles.
        """
        if not self._is_async:
            logger.warning("Cannot recalculate profiles with sync session")
            return

        try:
            # Recalculate hiking profile
            hike_profile = await UserProfileService.calculate_profile_with_splits(
                user_id, self.db
            )
            if hike_profile:
                logger.info(f"Final hiking profile recalc for user {user_id}")
                self._create_notification(
                    user_id=user_id,
                    notification_type="profile_updated",
                    data={
                        "profile_type": "hiking",
                        "checkpoint": 100,
                        "activities_analyzed": hike_profile.total_hike_activities,
                        "is_final": True
                    }
                )

            # Recalculate running profile
            run_profile = await UserProfileService.calculate_run_profile_with_splits(
                user_id, self.db
            )
            if run_profile:
                logger.info(f"Final running profile recalc for user {user_id}")
                self._create_notification(
                    user_id=user_id,
                    notification_type="profile_updated",
                    data={
                        "profile_type": "running",
                        "checkpoint": 100,
                        "activities_analyzed": run_profile.total_activities,
                        "is_final": True
                    }
                )

            if self._is_async:
                await self.db.commit()

        except Exception as e:
            logger.error(f"Failed final profile recalc for user {user_id}: {e}")

    def _save_activity(self, user_id: str, data: dict) -> Optional[StravaActivity]:
        """
        Save a single activity to database.

        Returns StravaActivity if saved (new), None if already exists.
        """
        strava_id = data["id"]

        # Check if already exists
        existing = self.db.query(StravaActivity).filter(
            StravaActivity.strava_id == strava_id
        ).first()

        if existing:
            return None

        # Parse start date
        start_date = datetime.fromisoformat(
            data["start_date"].replace("Z", "+00:00")
        )

        activity = StravaActivity(
            user_id=user_id,
            strava_id=strava_id,
            name=data.get("name"),
            activity_type=data.get("type", "Unknown"),
            start_date=start_date,
            distance_m=data.get("distance"),
            moving_time_s=data.get("moving_time"),
            elapsed_time_s=data.get("elapsed_time"),
            elevation_gain_m=data.get("total_elevation_gain"),
            elevation_loss_m=data.get("elev_low"),  # Note: API returns elev_high/low, not loss
            avg_speed_mps=data.get("average_speed"),
            max_speed_mps=data.get("max_speed"),
            avg_heartrate=data.get("average_heartrate"),
            max_heartrate=data.get("max_heartrate"),
            avg_cadence=data.get("average_cadence"),
            suffer_score=data.get("suffer_score"),
        )

        self.db.add(activity)
        self.db.flush()  # Get the ID assigned
        return activity

    async def _get_valid_token(self, token: StravaToken) -> str:
        """Get valid access token, refreshing if needed."""
        if token.expires_at < datetime.utcnow().timestamp() + 300:
            logger.info(f"Refreshing token for user {token.user_id}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://www.strava.com/oauth/token",
                    data={
                        "client_id": settings.strava_client_id,
                        "client_secret": settings.strava_client_secret,
                        "refresh_token": token.refresh_token,
                        "grant_type": "refresh_token"
                    }
                )
                response.raise_for_status()
                new_tokens = response.json()

            token.access_token = new_tokens["access_token"]
            token.refresh_token = new_tokens["refresh_token"]
            token.expires_at = new_tokens["expires_at"]
            token.updated_at = datetime.utcnow()

            if self._is_async:
                await self.db.commit()
            else:
                self.db.commit()

        return token.access_token

    async def _fetch_activities(
        self,
        access_token: str,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        per_page: int = 30
    ) -> list[dict]:
        """Fetch activities from Strava API."""
        params = {"per_page": per_page}

        if after:
            params["after"] = int(after.timestamp())
        if before:
            params["before"] = int(before.timestamp())

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params
            )
            response.raise_for_status()
            return response.json()

    async def sync_activity_splits(
        self,
        user_id: str,
        activity_id: int,
        strava_activity_id: int
    ) -> dict:
        """
        Sync splits for a specific activity.

        Args:
            user_id: User ID
            activity_id: Local database activity ID
            strava_activity_id: Strava's activity ID

        Returns:
            dict with sync results
        """
        # Get token
        if self._is_async:
            result = await self.db.execute(
                select(StravaToken).where(StravaToken.user_id == user_id)
            )
            token = result.scalar_one_or_none()
        else:
            token = self.db.query(StravaToken).filter(
                StravaToken.user_id == user_id
            ).first()

        if not token:
            return {"status": "error", "reason": "no_token"}

        try:
            access_token = await self._get_valid_token(token)

            # Fetch detailed activity with splits
            activity_data = await self._fetch_activity_detail(
                access_token,
                strava_activity_id
            )

            splits_data = activity_data.get("splits_metric", [])
            if not splits_data:
                return {"status": "success", "splits_saved": 0, "reason": "no_splits"}

            # Save splits
            saved_count = 0
            for split_data in splits_data:
                split = StravaActivitySplit(
                    activity_id=activity_id,
                    split_number=split_data.get("split"),
                    distance_m=split_data.get("distance"),
                    moving_time_s=split_data.get("moving_time"),
                    elapsed_time_s=split_data.get("elapsed_time"),
                    elevation_diff_m=split_data.get("elevation_difference"),
                    average_speed_mps=split_data.get("average_speed"),
                    average_heartrate=split_data.get("average_heartrate"),
                    pace_zone=split_data.get("pace_zone")
                )
                self.db.add(split)
                saved_count += 1

            # Mark activity as splits_synced
            if self._is_async:
                result = await self.db.execute(
                    select(StravaActivity).where(StravaActivity.id == activity_id)
                )
                activity = result.scalar_one_or_none()
            else:
                activity = self.db.query(StravaActivity).filter(
                    StravaActivity.id == activity_id
                ).first()

            if activity:
                activity.splits_synced = 1

            if self._is_async:
                await self.db.commit()
            else:
                self.db.commit()

            logger.info(f"Synced {saved_count} splits for activity {strava_activity_id}")

            return {
                "status": "success",
                "splits_saved": saved_count
            }

        except Exception as e:
            logger.error(f"Failed to sync splits for activity {strava_activity_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def sync_splits_for_user(
        self,
        user_id: str,
        max_activities: int = 10,
        activity_types: list[str] = None
    ) -> dict:
        """
        Sync splits for user's activities that don't have splits yet.

        Args:
            user_id: User ID
            max_activities: Maximum number of activities to sync splits for
            activity_types: Filter by activity types (default: Hike, Walk)

        Returns:
            dict with sync results
        """
        if activity_types is None:
            activity_types = ACTIVITY_TYPES_FOR_HIKE_PROFILE

        # Find activities without splits
        if self._is_async:
            query = select(StravaActivity).where(
                StravaActivity.user_id == user_id,
                StravaActivity.activity_type.in_(activity_types),
                StravaActivity.splits_synced == 0
            ).order_by(StravaActivity.start_date.desc()).limit(max_activities)
            result = await self.db.execute(query)
            activities = result.scalars().all()
        else:
            query = self.db.query(StravaActivity).filter(
                StravaActivity.user_id == user_id,
                StravaActivity.activity_type.in_(activity_types),
                StravaActivity.splits_synced == 0
            ).order_by(StravaActivity.start_date.desc()).limit(max_activities)
            activities = query.all()

        if not activities:
            return {"status": "success", "activities_processed": 0, "reason": "no_activities_to_sync"}

        results = {
            "status": "success",
            "activities_processed": 0,
            "total_splits_saved": 0,
            "errors": []
        }

        for activity in activities:
            # Delay between API calls
            if results["activities_processed"] > 0:
                await asyncio.sleep(SyncConfig.API_CALL_DELAY)

            result = await self.sync_activity_splits(
                user_id=user_id,
                activity_id=activity.id,
                strava_activity_id=activity.strava_id
            )

            results["activities_processed"] += 1

            if result["status"] == "success":
                results["total_splits_saved"] += result.get("splits_saved", 0)
            else:
                results["errors"].append({
                    "activity_id": activity.strava_id,
                    "error": result.get("error", result.get("reason"))
                })

        # Update activities_with_splits counter in sync status
        if results["total_splits_saved"] > 0:
            if self._is_async:
                result = await self.db.execute(
                    select(StravaSyncStatus).where(StravaSyncStatus.user_id == user_id)
                )
                sync_status = result.scalar_one_or_none()
            else:
                sync_status = self.db.query(StravaSyncStatus).filter(
                    StravaSyncStatus.user_id == user_id
                ).first()

            if sync_status:
                sync_status.activities_with_splits = (
                    (sync_status.activities_with_splits or 0) +
                    results["activities_processed"] -
                    len(results["errors"])
                )

                # Create profile_updated notification
                self._create_notification(
                    user_id=user_id,
                    notification_type="profile_updated",
                    data={
                        "profile_type": "hiking" if activity_types == ACTIVITY_TYPES_FOR_HIKE_PROFILE else "running",
                        "activities_count": results["activities_processed"],
                        "splits_count": results["total_splits_saved"]
                    }
                )

                if self._is_async:
                    await self.db.commit()
                else:
                    self.db.commit()

        logger.info(
            f"Synced splits for user {user_id}: "
            f"{results['activities_processed']} activities, "
            f"{results['total_splits_saved']} splits"
        )

        return results

    async def _fetch_activity_detail(
        self,
        access_token: str,
        activity_id: int
    ) -> dict:
        """Fetch detailed activity from Strava API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"include_all_efforts": "false"}
            )
            response.raise_for_status()
            return response.json()

    async def sync_run_splits_for_user(
        self,
        user_id: str,
        max_activities: int = 10
    ) -> dict:
        """
        Sync splits for user's Run activities that don't have splits yet.

        Convenience method for Run/TrailRun activities.

        Args:
            user_id: User ID
            max_activities: Maximum number of activities to sync splits for

        Returns:
            dict with sync results
        """
        return await self.sync_splits_for_user(
            user_id=user_id,
            max_activities=max_activities,
            activity_types=ACTIVITY_TYPES_FOR_RUN_PROFILE
        )

    async def sync_splits_prioritized(
        self,
        user_id: str,
        max_activities: int = 20
    ) -> dict:
        """
        Sync splits with priority based on user's preferred_activity_type.

        First syncs splits for preferred activity type, then for other types.

        Args:
            user_id: User ID
            max_activities: Maximum activities total

        Returns:
            dict with sync results
        """
        # Get user's preferred activity type
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "error", "reason": "user_not_found"}

        preferred = user.preferred_activity_type or "hiking"

        # Determine priority types
        if preferred == "running":
            priority_types = ACTIVITY_TYPES_FOR_RUN_PROFILE
            secondary_types = ACTIVITY_TYPES_FOR_HIKE_PROFILE
        else:
            priority_types = ACTIVITY_TYPES_FOR_HIKE_PROFILE
            secondary_types = ACTIVITY_TYPES_FOR_RUN_PROFILE

        results = {
            "status": "success",
            "priority_synced": 0,
            "secondary_synced": 0,
            "total_splits": 0
        }

        # Sync priority types first (more activities)
        priority_result = await self.sync_splits_for_user(
            user_id=user_id,
            max_activities=max_activities // 2 + max_activities % 2,  # Give priority more
            activity_types=priority_types
        )
        if priority_result["status"] == "success":
            results["priority_synced"] = priority_result.get("activities_processed", 0)
            results["total_splits"] += priority_result.get("total_splits_saved", 0)

        # Sync secondary types
        secondary_result = await self.sync_splits_for_user(
            user_id=user_id,
            max_activities=max_activities // 2,
            activity_types=secondary_types
        )
        if secondary_result["status"] == "success":
            results["secondary_synced"] = secondary_result.get("activities_processed", 0)
            results["total_splits"] += secondary_result.get("total_splits_saved", 0)

        return results


# =============================================================================
# Background Sync Runner
# =============================================================================

class BackgroundSyncRunner:
    """
    Background task runner for activity sync.

    Call `start()` to begin background syncing.
    Call `stop()` to gracefully stop.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, db_factory):
        """Start background sync loop."""
        if self._running:
            return

        self._running = True
        self._db_factory = db_factory
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Background sync started")

    async def stop(self):
        """Stop background sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background sync stopped")

    async def _run_loop(self):
        """Main sync loop."""
        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.error(f"Sync batch error: {e}")

            # Wait before next batch (5 minutes)
            await asyncio.sleep(300)

    async def _process_batch(self):
        """Process one batch of users."""
        # Get users to sync
        user_ids = await sync_queue.get_next_users(SyncConfig.USERS_PER_BATCH)

        if not user_ids:
            # Queue empty - refresh from database
            await self._refresh_queue()
            return

        logger.info(f"Processing sync batch: {len(user_ids)} users")

        for user_id in user_ids:
            try:
                db = self._db_factory()
                try:
                    service = StravaSyncService(db)
                    result = await service.sync_user_activities(user_id)
                    logger.debug(f"Sync result for {user_id}: {result}")
                finally:
                    db.close()

                # Delay between users
                await asyncio.sleep(SyncConfig.API_CALL_DELAY)

            except Exception as e:
                logger.error(f"Error syncing user {user_id}: {e}")

            finally:
                await sync_queue.mark_complete(user_id)

    async def _refresh_queue(self):
        """Refresh queue from database with users needing sync."""
        db = self._db_factory()
        try:
            # Find users with Strava connected
            users = db.query(User).filter(
                User.strava_connected == True
            ).all()

            cutoff = datetime.utcnow() - timedelta(
                hours=SyncConfig.MIN_SYNC_INTERVAL_HOURS
            )

            for user in users:
                # Check sync status
                sync_status = db.query(StravaSyncStatus).filter(
                    StravaSyncStatus.user_id == user.id
                ).first()

                # Add to queue if:
                # 1. Never synced
                # 2. Last sync was long ago
                if not sync_status:
                    await sync_queue.add_user(user.id, priority=True)
                elif not sync_status.last_sync_at or sync_status.last_sync_at < cutoff:
                    await sync_queue.add_user(user.id)

            logger.info(f"Refreshed sync queue: {sync_queue.queue_size} users")

        finally:
            db.close()


# Global runner instance
background_sync = BackgroundSyncRunner()


# =============================================================================
# Helper Functions
# =============================================================================

async def trigger_user_sync(user_id: str):
    """
    Trigger immediate sync for a user (e.g., after OAuth).

    Adds user to front of queue with priority.
    """
    await sync_queue.add_user(user_id, priority=True)
    logger.info(f"Triggered priority sync for user {user_id}")


def get_sync_stats() -> dict:
    """Get current sync statistics."""
    return {
        "queue_size": sync_queue.queue_size,
        "in_progress": sync_queue.in_progress_count,
    }
