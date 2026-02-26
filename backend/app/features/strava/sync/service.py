"""
Strava sync orchestration.

Coordinates activity and splits synchronization.
Main entry point for syncing user activities.

Sync Flow:
1. First batch (after OAuth):
   - Fetch 10 activities
   - Calculate profile
   - Send notification based on quality (0/1-4/5-10 activities)

2. Background sync (by percent checkpoints):
   - At 30%: recalculate profile + notification
   - At 60%: recalculate profile + notification
   - At 100%: final recalculation + "sync complete" notification
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.features.users import NotificationService
from app.services.user_profile import UserProfileService

from ..models import StravaToken, StravaActivity, StravaSyncStatus
from ..client import fetch_athlete_stats
from ..ayda_client import AydaRunClient
from .config import (
    SyncConfig,
    ACTIVITY_TYPES_FOR_HIKE_PROFILE,
    ACTIVITY_TYPES_FOR_RUN_PROFILE,
    ALL_SUPPORTED_ACTIVITY_TYPES,
)
from .activities import ActivitySyncService
from .splits import SplitsSyncService

logger = logging.getLogger(__name__)


class StravaSyncService:
    """
    Main sync orchestrator.

    Coordinates activity fetching, splits syncing, and profile recalculation.

    Usage:
        service = StravaSyncService(db)
        result = await service.sync_user_activities(user_id)
    """

    def __init__(self, db: AsyncSession, ayda_client: AydaRunClient | None = None):
        self.db = db
        self.ayda_client = ayda_client
        self.activity_sync = ActivitySyncService(db)
        self.splits_sync = SplitsSyncService(db)
        self.notification_service = NotificationService(db)

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
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "skipped", "reason": "user_not_found"}

        # Get local token (may be None if user authorized via ayda_run only)
        result = await self.db.execute(
            select(StravaToken).where(StravaToken.user_id == user_id)
        )
        token = result.scalar_one_or_none()

        if not token and not self.ayda_client:
            if not user.strava_connected:
                return {"status": "skipped", "reason": "not_connected"}
            return {"status": "skipped", "reason": "no_token"}

        # Get or create sync status
        result = await self.db.execute(
            select(StravaSyncStatus).where(StravaSyncStatus.user_id == user_id)
        )
        sync_status = result.scalar_one_or_none()

        if not sync_status:
            sync_status = StravaSyncStatus(user_id=user_id)
            self.db.add(sync_status)
            await self.db.flush()

        # Check if sync is already in progress
        if sync_status.sync_in_progress:
            return {"status": "skipped", "reason": "already_in_progress"}

        # Mark sync as in progress
        sync_status.sync_in_progress = 1
        await self.db.commit()

        try:
            # Get valid access token: local first, then ayda_run fallback
            access_token = None
            if token:
                access_token = await self.activity_sync.get_valid_token(token)

            if not access_token and self.ayda_client and user.telegram_id:
                token_data = await self.ayda_client.get_strava_token(user.telegram_id)
                if token_data:
                    access_token = token_data["access_token"]
                    # Update athlete_id if not set
                    if not user.strava_athlete_id and token_data.get("athlete_id"):
                        user.strava_athlete_id = token_data["athlete_id"]
                        user.strava_connected = True
                    logger.info(f"Using ayda_run token for user {user_id}")

            if not access_token:
                sync_status.sync_in_progress = 0
                await self.db.commit()
                return {"status": "skipped", "reason": "no_token"}

            # Fetch total_activities_estimated on first sync
            if sync_status.total_activities_estimated is None:
                athlete_id = (
                    user.strava_athlete_id
                    or (token.strava_athlete_id if token else None)
                )
                if athlete_id:
                    await self._fetch_and_set_estimated(
                        access_token, athlete_id, sync_status
                    )

            # Determine sync window
            if sync_status.newest_synced_date:
                after = sync_status.newest_synced_date
                before = None
            else:
                after = datetime.utcnow() - timedelta(days=SyncConfig.MAX_HISTORY_DAYS)
                before = None

            # Fetch activities from Strava
            activities = await self.activity_sync.fetch_activities(
                access_token,
                after=after,
                before=before,
                per_page=max_activities
            )

            # Save activities and sync splits
            saved_count = 0
            splits_synced_count = 0
            saved_activities = []

            for activity_data in activities:
                activity = await self.activity_sync.save_activity(user_id, activity_data)
                if activity:
                    saved_count += 1
                    saved_activities.append(activity)

            # Commit to get activity IDs
            await self.db.commit()

            # Sync splits for supported activity types
            for activity in saved_activities:
                if activity.activity_type in ALL_SUPPORTED_ACTIVITY_TYPES:
                    if splits_synced_count > 0:
                        await asyncio.sleep(SyncConfig.API_CALL_DELAY)

                    try:
                        split_result = await self.splits_sync.sync_activity_splits(
                            user_id=user_id,
                            activity_id=activity.id,
                            strava_activity_id=activity.strava_id,
                            access_token=access_token,
                        )
                        if split_result.get("status") == "success":
                            splits_synced_count += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to sync splits for activity {activity.strava_id}: {e}"
                        )

            # Update sync status
            if activities:
                dates = [
                    datetime.fromisoformat(
                        a["start_date"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    for a in activities
                ]
                newest = max(dates)
                oldest = min(dates)

                if not sync_status.newest_synced_date or newest > sync_status.newest_synced_date:
                    sync_status.newest_synced_date = newest
                if not sync_status.oldest_synced_date or oldest < sync_status.oldest_synced_date:
                    sync_status.oldest_synced_date = oldest

            sync_status.total_activities_synced += saved_count
            sync_status.activities_with_splits = (
                (sync_status.activities_with_splits or 0) + splits_synced_count
            )
            sync_status.last_sync_at = datetime.utcnow()
            sync_status.last_error = None
            sync_status.sync_in_progress = 0

            # =================================================================
            # NEW LOGIC: First batch notification
            # =================================================================
            if not sync_status.first_batch_notified:
                await self._handle_first_batch_complete(user_id, sync_status)

            # =================================================================
            # NEW LOGIC: Check progress checkpoints (30%, 60%, 100%)
            # =================================================================
            elif not sync_status.initial_sync_complete:
                await self._check_progress_checkpoint(user_id, sync_status)

            # =================================================================
            # Check if initial sync is complete
            # =================================================================
            if not sync_status.initial_sync_complete and len(activities) < max_activities:
                sync_status.initial_sync_complete = 1
                # Final notification is sent by _check_progress_checkpoint at 100%
                logger.info(f"Initial sync complete for user {user_id}")

            await self.db.commit()

            # =================================================================
            # Post-initial sync: incremental recalculation
            # =================================================================
            if sync_status.initial_sync_complete and splits_synced_count > 0:
                await self._handle_post_sync_recalc(user_id, sync_status, splits_synced_count)

            logger.info(
                f"Synced {saved_count} activities for user {user_id}: "
                f"{splits_synced_count} activities got splits synced"
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
            await self.db.commit()
            return {"status": "error", "error": str(e)}

    async def _create_notification(
        self,
        user_id: str,
        notification_type: str,
        data: Optional[dict] = None
    ):
        """Create a notification and send push to Telegram."""
        await self.notification_service.create_and_send(
            user_id=user_id,
            notification_type=notification_type,
            data=data
        )

    # =========================================================================
    # NEW: Fetch total_activities_estimated from Strava stats
    # =========================================================================

    async def _fetch_and_set_estimated(
        self,
        access_token: str,
        athlete_id: int,
        sync_status: StravaSyncStatus
    ):
        """Fetch athlete stats and set total_activities_estimated."""
        try:
            stats = await fetch_athlete_stats(access_token, athlete_id)
            # Strava only provides run totals, not hike
            run_count = stats.get("all_run_totals", {}).get("count", 0)
            sync_status.total_activities_estimated = run_count
            logger.info(f"Set total_activities_estimated={run_count} for user")
        except Exception as e:
            logger.warning(f"Failed to fetch athlete stats: {e}")
            # Leave as None, checkpoints will handle gracefully

    # =========================================================================
    # NEW: First batch handling
    # =========================================================================

    async def _handle_first_batch_complete(
        self,
        user_id: str,
        sync_status: StravaSyncStatus
    ):
        """
        Handle first batch completion.

        Always recalculates profile and sends notification based on quality:
        - 0 activities: "no suitable activities"
        - 1-4 activities: "preliminary profile"
        - 5+ activities: "basic profile"
        """
        activities_with_splits = sync_status.activities_with_splits or 0

        # Determine quality level
        if activities_with_splits == 0:
            quality = "none"
        elif activities_with_splits < SyncConfig.FIRST_BATCH_QUALITY_THRESHOLD:
            quality = "preliminary"
        else:
            quality = "basic"

        # Recalculate profile if we have data
        if activities_with_splits > 0:
            await self._recalculate_all_profiles(user_id)

        # Send notification
        await self._create_notification(
            user_id=user_id,
            notification_type="first_batch_complete",
            data={
                "quality": quality,
                "activities_with_splits": activities_with_splits,
                "total_synced": sync_status.total_activities_synced
            }
        )

        # Mark first batch as notified
        sync_status.first_batch_notified = 1
        logger.info(
            f"First batch complete for user {user_id}: "
            f"quality={quality}, activities={activities_with_splits}"
        )

    # =========================================================================
    # NEW: Priority sync complete handling
    # =========================================================================

    async def _get_sync_status(self, user_id: str) -> Optional[StravaSyncStatus]:
        """Get sync status for user."""
        result = await self.db.execute(
            select(StravaSyncStatus).where(StravaSyncStatus.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def handle_priority_sync_complete(self, user_id: str):
        """
        Handle completion of priority sync (after all priority batches done).

        Recalculates profile and sends notification with current progress.
        Called after priority sync finishes (if more than 1 batch was done).
        """
        sync_status = await self._get_sync_status(user_id)
        if not sync_status:
            return

        activities_with_splits = sync_status.activities_with_splits or 0
        total_synced = sync_status.total_activities_synced or 0
        total_estimated = sync_status.total_activities_estimated or 0

        # Calculate current percent
        current_percent = 0
        if total_estimated > 0:
            current_percent = int((total_synced / total_estimated) * 100)

        # Recalculate profile
        if activities_with_splits > 0:
            await self._recalculate_all_profiles(user_id)

        # Send notification
        await self._create_notification(
            user_id=user_id,
            notification_type="sync_progress",
            data={
                "checkpoint_percent": current_percent,
                "activities_with_splits": activities_with_splits,
                "total_synced": total_synced
            }
        )

        logger.info(
            f"Priority sync complete for user {user_id}: "
            f"{activities_with_splits} activities, {current_percent}% synced"
        )

    # =========================================================================
    # NEW: Progress checkpoint handling (30%, 60%, 100%)
    # =========================================================================

    async def _check_progress_checkpoint(
        self,
        user_id: str,
        sync_status: StravaSyncStatus
    ):
        """
        Check if we've reached a progress checkpoint.

        Checkpoints: 30%, 60%, 100% of total_activities_estimated.
        At each checkpoint: recalculate profile + send notification.
        """
        total_estimated = sync_status.total_activities_estimated
        if not total_estimated or total_estimated == 0:
            return

        current_percent = (sync_status.total_activities_synced / total_estimated) * 100
        last_checkpoint = sync_status.last_recalc_checkpoint or 0

        for checkpoint in SyncConfig.SYNC_PROGRESS_CHECKPOINTS:
            if last_checkpoint < checkpoint <= current_percent:
                # Reached new checkpoint
                sync_status.last_recalc_checkpoint = checkpoint

                # Recalculate profiles
                await self._recalculate_all_profiles(user_id)

                # Determine notification type
                if checkpoint == 100:
                    notification_type = "sync_complete"
                else:
                    notification_type = "sync_progress"

                # Send notification
                await self._create_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    data={
                        "checkpoint_percent": checkpoint,
                        "activities_with_splits": sync_status.activities_with_splits or 0,
                        "total_synced": sync_status.total_activities_synced
                    }
                )

                logger.info(
                    f"Progress checkpoint {checkpoint}% for user {user_id}: "
                    f"synced={sync_status.total_activities_synced}, "
                    f"with_splits={sync_status.activities_with_splits}"
                )

                break  # One checkpoint per batch

    # =========================================================================
    # NEW: Post-initial sync incremental recalculation
    # =========================================================================

    async def _handle_post_sync_recalc(
        self,
        user_id: str,
        sync_status: StravaSyncStatus,
        new_splits_count: int
    ):
        """
        Handle profile recalculation after initial sync is complete.

        Recalculates every POST_SYNC_RECALC_MIN_NEW_ACTIVITIES new activities.
        """
        sync_status.new_activities_since_recalc = (
            (sync_status.new_activities_since_recalc or 0) + new_splits_count
        )

        if sync_status.new_activities_since_recalc >= SyncConfig.POST_SYNC_RECALC_MIN_NEW_ACTIVITIES:
            sync_status.new_activities_since_recalc = 0
            await self._recalculate_all_profiles(user_id)
            logger.info(f"Incremental profile recalc for user {user_id}")

    # =========================================================================
    # Helper: Recalculate all profiles
    # =========================================================================

    async def _recalculate_all_profiles(self, user_id: str):
        """Recalculate both hiking and running profiles."""
        try:
            hike_profile = await UserProfileService.calculate_profile_with_splits(
                user_id, self.db
            )
            if hike_profile:
                logger.debug(f"Recalculated hiking profile for user {user_id}")

            run_profile = await UserProfileService.calculate_run_profile_with_splits(
                user_id, self.db
            )
            if run_profile:
                logger.debug(f"Recalculated running profile for user {user_id}")

            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to recalculate profiles for user {user_id}: {e}")

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
        query = select(StravaActivity).where(
            StravaActivity.user_id == user_id,
            StravaActivity.activity_type.in_(activity_types),
            StravaActivity.splits_synced == 0
        ).order_by(StravaActivity.start_date.desc()).limit(max_activities)
        result = await self.db.execute(query)
        activities = result.scalars().all()

        if not activities:
            return {"status": "success", "activities_processed": 0, "reason": "no_activities_to_sync"}

        results = {
            "status": "success",
            "activities_processed": 0,
            "total_splits_saved": 0,
            "errors": []
        }

        for activity in activities:
            if results["activities_processed"] > 0:
                await asyncio.sleep(SyncConfig.API_CALL_DELAY)

            result = await self.splits_sync.sync_activity_splits(
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

        # Update activities_with_splits counter
        if results["total_splits_saved"] > 0:
            result = await self.db.execute(
                select(StravaSyncStatus).where(StravaSyncStatus.user_id == user_id)
            )
            sync_status = result.scalar_one_or_none()

            if sync_status:
                sync_status.activities_with_splits = (
                    (sync_status.activities_with_splits or 0) +
                    results["activities_processed"] -
                    len(results["errors"])
                )

                profile_type = (
                    "hiking"
                    if activity_types == ACTIVITY_TYPES_FOR_HIKE_PROFILE
                    else "running"
                )
                await self._create_notification(
                    user_id=user_id,
                    notification_type="profile_updated",
                    data={
                        "profile_type": profile_type,
                        "activities_count": results["activities_processed"],
                        "splits_count": results["total_splits_saved"]
                    }
                )

                await self.db.commit()

        logger.info(
            f"Synced splits for user {user_id}: "
            f"{results['activities_processed']} activities, "
            f"{results['total_splits_saved']} splits"
        )

        return results

    async def sync_run_splits_for_user(
        self,
        user_id: str,
        max_activities: int = 10
    ) -> dict:
        """Sync splits for user's Run activities that don't have splits yet."""
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
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "error", "reason": "user_not_found"}

        preferred = user.preferred_activity_type or "hiking"

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

        # Sync priority types first
        priority_result = await self.sync_splits_for_user(
            user_id=user_id,
            max_activities=max_activities // 2 + max_activities % 2,
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
