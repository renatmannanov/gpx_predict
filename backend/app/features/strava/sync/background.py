"""
Background sync runner.

Handles scheduled background synchronization of Strava activities.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from app.features.users import User

from ..models import StravaSyncStatus
from .config import SyncConfig
from .service import StravaSyncService

logger = logging.getLogger(__name__)


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
# Background Sync Runner
# =============================================================================

class BackgroundSyncRunner:
    """
    Background task runner for activity sync.

    Call `start()` to begin background syncing.
    Call `stop()` to gracefully stop.

    Usage:
        runner = BackgroundSyncRunner()
        await runner.start(db_factory)
        # ... later ...
        await runner.stop()
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._db_factory = None

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
        user_ids = await sync_queue.get_next_users(SyncConfig.USERS_PER_BATCH)

        if not user_ids:
            await self._refresh_queue()
            return

        logger.info(f"Processing sync batch: {len(user_ids)} users")

        for user_id in user_ids:
            try:
                async with self._db_factory() as db:
                    service = StravaSyncService(db)
                    result = await service.sync_user_activities(user_id)
                    logger.debug(f"Sync result for {user_id}: {result}")

                await asyncio.sleep(SyncConfig.API_CALL_DELAY)

            except Exception as e:
                logger.error(f"Error syncing user {user_id}: {e}")

            finally:
                await sync_queue.mark_complete(user_id)

    async def _refresh_queue(self):
        """Refresh queue from database with users needing sync."""
        from sqlalchemy import select

        async with self._db_factory() as db:
            result = await db.execute(
                select(User).where(User.strava_connected == True)
            )
            users = result.scalars().all()

            cutoff = datetime.utcnow() - timedelta(
                hours=SyncConfig.MIN_SYNC_INTERVAL_HOURS
            )

            for user in users:
                result = await db.execute(
                    select(StravaSyncStatus).where(
                        StravaSyncStatus.user_id == user.id
                    )
                )
                sync_status = result.scalar_one_or_none()

                if not sync_status:
                    await sync_queue.add_user(user.id, priority=True)
                elif not sync_status.last_sync_at or sync_status.last_sync_at < cutoff:
                    await sync_queue.add_user(user.id)

            logger.info(f"Refreshed sync queue: {sync_queue.queue_size} users")


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
