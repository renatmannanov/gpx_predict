"""
Trail Run Keyboards

Inline keyboards for trail run prediction flow.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_gap_mode_keyboard() -> InlineKeyboardMarkup:
    """Get GAP mode selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Strava GAP (рек.)", callback_data="tr:gap:strava_gap"),
            InlineKeyboardButton(text="Minetti GAP", callback_data="tr:gap:minetti_gap")
        ],
        [
            InlineKeyboardButton(text="Авто", callback_data="tr:gap:auto")
        ]
    ])


def get_flat_pace_keyboard(strava_pace: float = None) -> InlineKeyboardMarkup:
    """
    Get flat pace selection keyboard.

    Args:
        strava_pace: If provided, adds "Use Strava pace" button at top
    """
    rows = []

    # Add Strava pace button if available
    if strava_pace:
        pace_min = int(strava_pace)
        pace_sec = int((strava_pace - pace_min) * 60)
        rows.append([
            InlineKeyboardButton(
                text=f"👤 Использовать {pace_min}:{pace_sec:02d}/км",
                callback_data=f"tr:pace:{strava_pace}"
            )
        ])

    # Common paces
    rows.append([
        InlineKeyboardButton(text="5:00/км", callback_data="tr:pace:5.0"),
        InlineKeyboardButton(text="5:30/км", callback_data="tr:pace:5.5"),
        InlineKeyboardButton(text="6:00/км", callback_data="tr:pace:6.0"),
    ])
    rows.append([
        InlineKeyboardButton(text="6:30/км", callback_data="tr:pace:6.5"),
        InlineKeyboardButton(text="7:00/км", callback_data="tr:pace:7.0"),
        InlineKeyboardButton(text="8:00/км", callback_data="tr:pace:8.0"),
    ])
    rows.append([
        InlineKeyboardButton(text="Ввести вручную", callback_data="tr:pace:custom")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_fatigue_keyboard() -> InlineKeyboardMarkup:
    """Get fatigue mode selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="С учётом усталости", callback_data="tr:fatigue:yes"),
            InlineKeyboardButton(text="Без усталости", callback_data="tr:fatigue:no")
        ]
    ])


def get_route_type_keyboard() -> InlineKeyboardMarkup:
    """Get route type selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="A → B (в одну сторону)", callback_data="tr:rt:oneway"),
            InlineKeyboardButton(text="A → B → A (туда-обратно)", callback_data="tr:rt:roundtrip")
        ]
    ])


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏃 Рассчитать!", callback_data="tr:confirm"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="tr:settings")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="tr:cancel")
        ]
    ])


def get_settings_keyboard(current_settings: dict) -> InlineKeyboardMarkup:
    """Get settings keyboard with current values."""
    gap_mode = current_settings.get("gap_mode", "strava_gap")
    fatigue = current_settings.get("apply_fatigue", False)

    gap_text = "Strava" if gap_mode == "strava_gap" else "Minetti"
    fatigue_text = "Вкл" if fatigue else "Выкл"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"GAP режим: {gap_text}", callback_data="tr:set:gap")],
        [InlineKeyboardButton(text=f"Усталость: {fatigue_text}", callback_data="tr:set:fatigue")],
        [InlineKeyboardButton(text="← Назад", callback_data="tr:back")]
    ])
