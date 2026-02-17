"""
Notification text formatters.

Formats notification data into human-readable Telegram messages.

Notification types:
- first_batch_complete: After first batch (0/1-4/5-10 activities)
- sync_progress: At 30%/60% checkpoints
- sync_complete: At 100% (all activities synced)
- strava_connected: After OAuth (before sync starts)
"""

from typing import Optional


def format_notification(notification_type: str, data: Optional[dict]) -> Optional[str]:
    """
    Format notification for Telegram message.

    Args:
        notification_type: Type of notification
        data: Notification data dict

    Returns:
        Formatted text or None if unknown type
    """
    formatters = {
        "first_batch_complete": _format_first_batch_complete,
        "sync_progress": _format_sync_progress,
        "sync_complete": _format_sync_complete,
        "strava_connected": _format_strava_connected,
        # Legacy (kept for backward compatibility)
        "profile_updated": _format_profile_updated,
        "profile_complete": _format_profile_complete,
        "profile_incomplete": _format_profile_incomplete,
    }

    formatter = formatters.get(notification_type)
    if formatter:
        return formatter(data or {})
    return None


# =============================================================================
# NEW: First batch notification (after OAuth, immediate feedback)
# =============================================================================

def _format_first_batch_complete(data: dict) -> str:
    """
    Format notification after first batch.

    Quality levels:
    - none: 0 activities with splits
    - preliminary: 1-4 activities
    - basic: 5-10 activities
    """
    quality = data.get("quality", "none")
    activities = data.get("activities_with_splits", 0)
    total_synced = data.get("total_synced", 0)

    if quality == "none":
        return (
            "<b>📥 Синхронизация Strava</b>\n\n"
            f"Загружено: {total_synced} активностей\n\n"
            "❌ Нет подходящих активностей для профиля бегуна.\n"
            "Нужны Run или TrailRun активности с GPS.\n\n"
            "Синхронизация продолжается..."
        )
    elif quality == "preliminary":
        return (
            "<b>📊 Профиль бегуна создан</b>\n\n"
            f"Проанализировано: {activities} активностей\n\n"
            "⚠️ Профиль приблизительный — нужно больше активностей\n\n"
            "Синхронизация продолжается — профиль будет улучшаться.\n"
            "👉 /profile — посмотреть профиль"
        )
    else:  # basic
        return (
            "<b>📊 Профиль бегуна создан</b>\n\n"
            f"Проанализировано: {activities} активностей\n\n"
            "📊 Профиль базовый\n\n"
            "Синхронизация продолжается — профиль будет улучшаться.\n"
            "👉 /profile — посмотреть профиль"
        )


# =============================================================================
# NEW: Sync progress notification (at 30%, 60%)
# =============================================================================

def _format_sync_progress(data: dict) -> str:
    """
    Format notification at progress checkpoint (30%, 60%).
    """
    checkpoint = data.get("checkpoint_percent", 0)
    activities = data.get("activities_with_splits", 0)
    total_synced = data.get("total_synced", 0)

    return (
        "<b>📊 Профиль бегуна обновлён</b>\n\n"
        f"Проанализировано: {activities} активностей\n"
        f"Загружено: {total_synced} активностей ({checkpoint}%)\n\n"
        "Синхронизация продолжается — профиль будет улучшаться.\n"
        "👉 /profile — посмотреть профиль"
    )


# =============================================================================
# NEW: Sync complete notification (at 100%)
# =============================================================================

def _format_sync_complete(data: dict) -> str:
    """
    Format final notification when sync is 100% complete.
    """
    activities = data.get("activities_with_splits", 0)
    total_synced = data.get("total_synced", 0)

    return (
        "<b>✅ Синхронизация Strava завершена!</b>\n\n"
        f"Загружено: {total_synced} активностей\n"
        f"Проанализировано для профиля: {activities}\n\n"
        "✅ Профиль полный — прогнозы максимально точные!\n\n"
        "Теперь профиль будет обновляться автоматически "
        "с каждой новой активностью.\n\n"
        "👉 /profile — посмотреть профиль\n"
        "👉 /predict — сделать прогноз"
    )


# =============================================================================
# Legacy formatters (kept for backward compatibility)
# =============================================================================

def _format_profile_updated(data: dict) -> str:
    """Legacy: profile_updated notification."""
    profile_type = data.get("profile_type", "hiking")
    activities = data.get("activities_analyzed", data.get("activities_count", 0))
    checkpoint = data.get("checkpoint", 0)
    is_final = data.get("is_final", False)

    type_label = "бегуна" if profile_type == "running" else "хайкера"

    if is_final:
        return (
            f"<b>Профиль {type_label} готов!</b>\n\n"
            f"Проанализировано: {activities} активностей\n\n"
            "Теперь прогнозы будут персонализированы под тебя!\n"
            "Используй /profile чтобы посмотреть."
        )
    else:
        return (
            "<b>Профиль обновляется...</b>\n\n"
            f"Прогресс: {checkpoint}%\n"
            f"Проанализировано: {activities} активностей\n\n"
            f"Профиль {type_label} пересчитывается."
        )


def _format_profile_complete(data: dict) -> str:
    return (
        "<b>Профиль полный!</b>\n\n"
        "Все 7 категорий градиента заполнены.\n"
        "Теперь прогнозы будут максимально точными!\n\n"
        "Используй /profile чтобы посмотреть."
    )


def _format_profile_incomplete(data: dict) -> str:
    missing = data.get("missing_categories", [])

    if missing:
        missing_text = ", ".join(missing)
        return (
            "<b>Профиль неполный</b>\n\n"
            f"Не хватает данных для категорий: {missing_text}\n\n"
            "Для более точных прогнозов нужно больше активностей с разным рельефом."
        )
    return ""


def _format_strava_connected(data: dict) -> str:
    athlete_name = data.get("athlete_name", "Пользователь")
    return (
        "<b>Strava подключён!</b>\n\n"
        f"{athlete_name}, теперь я смогу анализировать твои активности "
        "и делать персональные прогнозы.\n\n"
        "Синхронизация активностей начнётся в фоне. "
        "Когда профиль будет готов — я сообщу!"
    )
