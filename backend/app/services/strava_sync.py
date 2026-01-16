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
from sqlalchemy import select, and_

from app.config import settings
from app.models.user import User
from app.models.strava_token import StravaToken
from app.models.strava_activity import StravaActivity, StravaSyncStatus

logger = logging.getLogger(__name__)


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
    """

    def __init__(self, db: Session):
        self.db = db

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

            # Save activities
            saved_count = 0
            for activity_data in activities:
                if self._save_activity(user_id, activity_data):
                    saved_count += 1

            # Update sync status
            if activities:
                dates = [
                    datetime.fromisoformat(a["start_date"].replace("Z", "+00:00"))
                    for a in activities
                ]
                newest = max(dates)
                oldest = min(dates)

                if not sync_status.newest_synced_date or newest > sync_status.newest_synced_date:
                    sync_status.newest_synced_date = newest
                if not sync_status.oldest_synced_date or oldest < sync_status.oldest_synced_date:
                    sync_status.oldest_synced_date = oldest

            sync_status.total_activities_synced += saved_count
            sync_status.last_sync_at = datetime.utcnow()
            sync_status.last_error = None
            sync_status.sync_in_progress = 0

            self.db.commit()

            logger.info(
                f"Synced {saved_count} activities for user {user_id} "
                f"(total: {sync_status.total_activities_synced})"
            )

            return {
                "status": "success",
                "fetched": len(activities),
                "saved": saved_count,
                "total": sync_status.total_activities_synced
            }

        except Exception as e:
            logger.error(f"Sync failed for user {user_id}: {e}")
            sync_status.last_error = str(e)[:500]
            sync_status.sync_in_progress = 0
            self.db.commit()
            return {"status": "error", "error": str(e)}

    def _save_activity(self, user_id: str, data: dict) -> bool:
        """
        Save a single activity to database.

        Returns True if saved (new), False if already exists.
        """
        strava_id = data["id"]

        # Check if already exists
        existing = self.db.query(StravaActivity).filter(
            StravaActivity.strava_id == strava_id
        ).first()

        if existing:
            return False

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
        return True

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
