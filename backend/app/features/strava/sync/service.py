"""
Strava sync orchestration.

Coordinates activity and splits synchronization.
Main entry point for syncing user activities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User, Notification
from app.services.user_profile import UserProfileService

from ..models import StravaToken, StravaActivity, StravaSyncStatus
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

    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_sync = ActivitySyncService(db)
        self.splits_sync = SplitsSyncService(db)

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

        if not user or not user.strava_connected:
            return {"status": "skipped", "reason": "not_connected"}

        result = await self.db.execute(
            select(StravaToken).where(StravaToken.user_id == user_id)
        )
        token = result.scalar_one_or_none()

        if not token:
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
            # Get valid access token
            access_token = await self.activity_sync.get_valid_token(token)

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
                            strava_activity_id=activity.strava_id
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

            # Check if initial sync is complete
            was_initial_sync = not sync_status.initial_sync_complete
            if was_initial_sync and len(activities) < max_activities:
                sync_status.initial_sync_complete = 1
                sync_status.last_recalc_checkpoint = 100
                self._create_notification(
                    user_id=user_id,
                    notification_type="sync_complete",
                    data={
                        "activities_synced": sync_status.total_activities_synced,
                        "activities_with_splits": sync_status.activities_with_splits or 0
                    }
                )
                logger.info(f"Initial sync complete for user {user_id}")
                await self._force_final_profile_recalc(user_id)

            await self.db.commit()

            # Auto-recalculate profiles if we synced splits
            if splits_synced_count > 0:
                await self._auto_recalculate_profiles(
                    user_id, saved_activities, sync_status, splits_synced_count
                )

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
        """Determine if profile should be recalculated based on sync progress."""
        if not sync_status.initial_sync_complete:
            return self._check_initial_sync_checkpoint(sync_status)
        else:
            return self._check_post_sync_threshold(sync_status, new_splits_count)

    def _check_initial_sync_checkpoint(self, sync_status: StravaSyncStatus) -> bool:
        """Check if we've reached a recalculation checkpoint during initial sync."""
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
        """Check if we should recalculate after initial sync is complete."""
        sync_status.new_activities_since_recalc = (
            (sync_status.new_activities_since_recalc or 0) + new_splits_count
        )

        if sync_status.new_activities_since_recalc >= SyncConfig.POST_SYNC_RECALC_MIN_NEW_ACTIVITIES:
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
        """Auto-recalculate user profiles based on sync progress."""
        if not self._should_recalculate_profile(sync_status, new_splits_count):
            logger.debug(
                f"Skipping profile recalc for user {user_id} "
                f"(checkpoint: {sync_status.last_recalc_checkpoint})"
            )
            return

        has_hike_activities = any(
            a.activity_type in ACTIVITY_TYPES_FOR_HIKE_PROFILE
            for a in saved_activities
        )
        has_run_activities = any(
            a.activity_type in ACTIVITY_TYPES_FOR_RUN_PROFILE
            for a in saved_activities
        )

        try:
            checkpoint = sync_status.last_recalc_checkpoint or 0
            recalc_reason = (
                f"checkpoint_{checkpoint}"
                if not sync_status.initial_sync_complete
                else "incremental"
            )

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

            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to auto-recalculate profiles for user {user_id}: {e}")

    async def _force_final_profile_recalc(self, user_id: str):
        """Force final profile recalculation when initial sync is complete."""
        try:
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

            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed final profile recalc for user {user_id}: {e}")

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
                self._create_notification(
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
