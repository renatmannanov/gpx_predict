"""
Notification text formatters.

Formats notification data into human-readable Telegram messages.
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
        "profile_updated": _format_profile_updated,
        "sync_complete": _format_sync_complete,
        "sync_progress": _format_sync_progress,
        "profile_complete": _format_profile_complete,
        "profile_incomplete": _format_profile_incomplete,
        "strava_connected": _format_strava_connected,
    }

    formatter = formatters.get(notification_type)
    if formatter:
        return formatter(data or {})
    return None


def _format_profile_updated(data: dict) -> str:
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


def _format_sync_complete(data: dict) -> str:
    activities = data.get("activities_synced", 0)
    with_splits = data.get("activities_with_splits", 0)

    return (
        "<b>Синхронизация завершена!</b>\n\n"
        f"Синхронизировано: {activities} активностей\n"
        f"С детальными данными: {with_splits}\n\n"
        "Теперь прогнозы будут персонализированы!"
    )


def _format_sync_progress(data: dict) -> str:
    progress = data.get("progress_percent", 0)
    synced = data.get("activities_synced", 0)
    total = data.get("total_estimated", 0)

    return (
        "<b>Прогресс синхронизации</b>\n\n"
        f"Загружено: {synced} из ~{total} активностей ({progress}%)\n\n"
        "Синхронизация продолжается в фоне..."
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
