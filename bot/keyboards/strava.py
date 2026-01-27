"""Keyboards for Strava integration."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional


def get_strava_connect_keyboard(auth_url: str) -> InlineKeyboardMarkup:
    """Keyboard with Strava connect button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔗 Подключить Strava",
            url=auth_url
        )]
    ])


def get_strava_connected_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for connected Strava account."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="strava:stats")],
        [InlineKeyboardButton(text="🏃 Мои активности", callback_data="strava:activities")],
        [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="strava:sync")],
        [InlineKeyboardButton(text="❌ Отключить Strava", callback_data="strava:disconnect")]
    ])


def get_confirm_disconnect_keyboard() -> InlineKeyboardMarkup:
    """Keyboard to confirm Strava disconnect."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, отключить", callback_data="strava:confirm_disconnect"),
            InlineKeyboardButton(text="Отмена", callback_data="strava:cancel")
        ]
    ])


def get_activities_keyboard(
    has_more: bool = False,
    offset: int = 0,
    activity_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Keyboard for activities list with filters and pagination."""
    buttons = []

    # Filter buttons
    filter_row = []
    types = [("🏃 Бег", "Run"), ("🥾 Поход", "Hike"), ("🚶 Все", None)]
    for label, type_val in types:
        cb_data = f"strava:activities:{type_val or 'all'}:0"
        filter_row.append(InlineKeyboardButton(text=label, callback_data=cb_data))
    buttons.append(filter_row)

    # Pagination
    if offset > 0 or has_more:
        nav_row = []
        if offset > 0:
            prev_offset = max(0, offset - 10)
            cb_type = activity_type or "all"
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"strava:activities:{cb_type}:{prev_offset}"
            ))
        if has_more:
            next_offset = offset + 10
            cb_type = activity_type or "all"
            nav_row.append(InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"strava:activities:{cb_type}:{next_offset}"
            ))
        buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
