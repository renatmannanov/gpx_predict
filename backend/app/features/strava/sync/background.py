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
from ..ayda_client import get_ayda_client
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
        # Keep strong references to priority sync tasks to prevent GC
        self._priority_tasks: set[asyncio.Task] = set()

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

            # Wait before next batch
            await asyncio.sleep(SyncConfig.BACKGROUND_SYNC_INTERVAL_SECONDS)

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
                    service = StravaSyncService(db, ayda_client=get_ayda_client())
                    result = await service.sync_user_activities(user_id)
                    logger.debug(f"Sync result for {user_id}: {result}")

                    # Requeue if initial sync not complete
                    if result.get("status") == "success":
                        sync_status = await self._get_sync_status(db, user_id)
                        if sync_status and not sync_status.initial_sync_complete:
                            await sync_queue.requeue_user(user_id)
                            logger.debug(f"Requeued user {user_id} (initial sync incomplete)")

                await asyncio.sleep(SyncConfig.API_CALL_DELAY)

            except Exception as e:
                logger.error(f"Error syncing user {user_id}: {e}")

            finally:
                await sync_queue.mark_complete(user_id)

    async def _get_sync_status(self, db, user_id: str) -> Optional[StravaSyncStatus]:
        """Get sync status for user."""
        from sqlalchemy import select
        result = await db.execute(
            select(StravaSyncStatus).where(StravaSyncStatus.user_id == user_id)
        )
        return result.scalar_one_or_none()

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

    # =========================================================================
    # Priority Sync (for new users after OAuth)
    # =========================================================================

    async def run_priority_sync(self, user_id: str):
        """
        Run priority sync for a user (multiple batches with short delays).

        Used after OAuth to quickly sync activities.
        Configurable via PRIORITY_SYNC_* settings.
        """
        logger.info(f"Starting priority sync for user {user_id}")

        batches_done = 0
        max_batches = SyncConfig.PRIORITY_SYNC_MAX_CONSECUTIVE_BATCHES

        while batches_done < max_batches:
            try:
                async with self._db_factory() as db:
                    service = StravaSyncService(db, ayda_client=get_ayda_client())
                    result = await service.sync_user_activities(user_id)

                    if result.get("status") != "success":
                        logger.warning(f"Priority sync batch failed: {result}")
                        break

                    # Check if sync is complete
                    sync_status = await self._get_sync_status(db, user_id)
                    if sync_status and sync_status.initial_sync_complete:
                        logger.info(f"Priority sync complete for user {user_id}")
                        break

                batches_done += 1
                logger.debug(
                    f"Priority sync batch {batches_done}/{max_batches} for {user_id}"
                )

                # Short delay between batches
                await asyncio.sleep(SyncConfig.PRIORITY_SYNC_BATCH_DELAY_SECONDS)

            except Exception as e:
                logger.error(f"Priority sync error for {user_id}: {e}")
                break

        # After priority sync: recalculate profile and send notification if needed
        if batches_done > 1:  # Only if we did more than first batch
            try:
                async with self._db_factory() as db:
                    service = StravaSyncService(db, ayda_client=get_ayda_client())
                    await service.handle_priority_sync_complete(user_id)
            except Exception as e:
                logger.error(f"Failed to handle priority sync completion: {e}")

        # If initial sync not complete, add to background queue for continuation
        try:
            async with self._db_factory() as db:
                sync_status = await self._get_sync_status(db, user_id)
                if sync_status and not sync_status.initial_sync_complete:
                    await sync_queue.add_user(user_id)
                    logger.info(
                        f"Priority sync finished, added {user_id} to background queue "
                        f"(initial sync incomplete)"
                    )
                else:
                    logger.info(
                        f"Priority sync finished for {user_id}: {batches_done} batches"
                    )
        except Exception as e:
            logger.error(f"Failed to check/requeue after priority sync: {e}")


# Global runner instance
background_sync = BackgroundSyncRunner()


# =============================================================================
# Helper Functions
# =============================================================================

async def trigger_user_sync(user_id: str, priority: bool = True):
    """
    Trigger sync for a user.

    Args:
        user_id: User ID
        priority: If True and background sync is running, runs priority sync
                  (multiple batches with short delays). Otherwise adds to queue.
    """
    if priority and background_sync._running and background_sync._db_factory:
        # Run priority sync in background task
        # IMPORTANT: Save reference to prevent garbage collection
        task = asyncio.create_task(background_sync.run_priority_sync(user_id))
        background_sync._priority_tasks.add(task)
        task.add_done_callback(background_sync._priority_tasks.discard)
        logger.info(f"Triggered priority sync for user {user_id}")
    else:
        # Add to regular queue
        await sync_queue.add_user(user_id, priority=True)
        logger.info(f"Added user {user_id} to sync queue")


def get_sync_stats() -> dict:
    """Get current sync statistics."""
    return {
        "queue_size": sync_queue.queue_size,
        "in_progress": sync_queue.in_progress_count,
    }
