"""
Profile Keyboards

Inline keyboards for /profile command.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_profile_keyboard(current_type: str, has_other_profile: bool) -> InlineKeyboardMarkup:
    """
    Get keyboard for profile view.

    Args:
        current_type: Currently displayed profile type ("hiking" or "running")
        has_other_profile: Whether the other profile has data
    """
    buttons = []

    # Switch profile button
    if has_other_profile:
        if current_type == "hiking":
            buttons.append(
                InlineKeyboardButton(
                    text="🏃 Профиль бегуна",
                    callback_data="profile:running"
                )
            )
        else:
            buttons.append(
                InlineKeyboardButton(
                    text="🥾 Профиль хайкера",
                    callback_data="profile:hiking"
                )
            )

    # Recalculate button
    buttons.append(
        InlineKeyboardButton(
            text="🔄 Пересчитать",
            callback_data="profile:recalculate"
        )
    )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def get_empty_profile_keyboard(strava_connected: bool = False) -> InlineKeyboardMarkup:
    """Get keyboard for empty profile."""
    if strava_connected:
        # Strava connected - show recalculate button
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Пересчитать профиль",
                callback_data="profile:recalculate"
            )]
        ])
    else:
        # Strava not connected - show connect button
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 Подключить Strava",
                callback_data="profile:connect_strava"
            )]
        ])
