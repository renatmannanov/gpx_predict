"""
Onboarding Keyboards

Inline keyboards for onboarding flow.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Get 'Start' button keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать", callback_data="onboarding:start")]
    ])


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Get activity type selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥾 Хайкинг", callback_data="onboarding:activity:hiking"),
            InlineKeyboardButton(text="🏃 Трейлраннинг", callback_data="onboarding:activity:running")
        ]
    ])


def get_strava_keyboard(auth_url: str) -> InlineKeyboardMarkup:
    """Get Strava connection keyboard."""
    # Telegram doesn't allow localhost URLs in buttons
    # If localhost, return keyboard without URL button (URL will be shown in text)
    if "localhost" in auth_url or "127.0.0.1" in auth_url:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="onboarding:strava:skip")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подключить Strava", url=auth_url)],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="onboarding:strava:skip")]
    ])


def get_strava_skip_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard when Strava is skipped."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Далее →", callback_data="onboarding:continue")]
    ])


def get_continue_keyboard() -> InlineKeyboardMarkup:
    """Get 'Continue' button keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Далее →", callback_data="onboarding:continue")]
    ])


def get_finish_keyboard() -> InlineKeyboardMarkup:
    """Get 'Finish' button keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Готово, начать!", callback_data="onboarding:finish")]
    ])


def get_strava_connected_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard after Strava is connected."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отлично, продолжить", callback_data="onboarding:continue")]
    ])
