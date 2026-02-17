"""
Profile Handlers

Handles /profile command to show user's hiking/running profile.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards.profile import (
    get_profile_keyboard,
    get_empty_profile_keyboard,
)
from services.api_client import api_client
from utils.formatters import format_pace

logger = logging.getLogger(__name__)

router = Router()


def format_hike_profile(profile: dict) -> str:
    """Format hiking profile for display."""
    activities = profile.get("total_hike_activities", 0)

    lines = [
        "📊 <b>Твой профиль хайкера</b>",
        "",
        f"Проанализировано: {activities} активностей",
        "",
    ]

    # Try 11-category from gradient_paces JSON
    gradient_paces = profile.get("gradient_paces")
    if gradient_paces:
        for key, label in _RUN_GRADIENT_CATEGORIES:  # Same 11-cat labels
            cat_data = gradient_paces.get(key, {})
            pace = cat_data.get("avg")
            samples = cat_data.get("samples", 0)
            pace_str = format_pace(pace)
            count_str = f" ({samples})" if samples else ""
            lines.append(f"• {label}: {pace_str}/км{count_str}")
    else:
        # Fallback to legacy 7 categories
        legacy_categories = [
            ("steep_downhill", "Крутой спуск (&lt;-15%)", "avg_steep_downhill_pace_min_km"),
            ("moderate_downhill", "Умеренный спуск", "avg_moderate_downhill_pace_min_km"),
            ("gentle_downhill", "Пологий спуск", "avg_gentle_downhill_pace_min_km"),
            ("flat", "Ровный участок", "avg_flat_pace_min_km"),
            ("gentle_uphill", "Пологий подъём", "avg_gentle_uphill_pace_min_km"),
            ("moderate_uphill", "Умеренный подъём", "avg_moderate_uphill_pace_min_km"),
            ("steep_uphill", "Крутой подъём (&gt;15%)", "avg_steep_uphill_pace_min_km"),
        ]
        for key, label, pace_field in legacy_categories:
            pace = profile.get(pace_field)
            count = profile.get(f"{key}_sample_count")
            pace_str = format_pace(pace)
            count_str = f" ({count})" if count else ""
            lines.append(f"• {label}: {pace_str}/км{count_str}")

    # Vertical ability
    va = profile.get("vertical_ability", 1.0)
    if va and va != 1.0:
        if va < 1.0:
            va_text = "быстрее среднего на вертикали"
        else:
            va_text = "медленнее среднего на вертикали"
        lines.append("")
        lines.append(f"Вертикальная способность: {va:.2f}")
        lines.append(f"({va_text})")

    return "\n".join(lines)


# 11-category gradient labels for run profile (ordered downhill→uphill)
_RUN_GRADIENT_CATEGORIES = [
    ("down_23_over", "Экстр. спуск (&lt;-23%)"),
    ("down_23_17",   "Крутой спуск (-23%..-17%)"),
    ("down_17_12",   "Умеренный спуск (-17%..-12%)"),
    ("down_12_8",    "Лёгкий спуск (-12%..-8%)"),
    ("down_8_3",     "Пологий спуск (-8%..-3%)"),
    ("flat_3_3",     "Ровный участок (-3%..+3%)"),
    ("up_3_8",       "Пологий подъём (+3%..+8%)"),
    ("up_8_12",      "Лёгкий подъём (+8%..+12%)"),
    ("up_12_17",     "Умеренный подъём (+12%..+17%)"),
    ("up_17_23",     "Крутой подъём (+17%..+23%)"),
    ("up_23_over",   "Экстр. подъём (&gt;+23%)"),
]

# Legacy 7-category fallback
_LEGACY_RUN_CATEGORIES = [
    ("steep_downhill", "Крутой спуск (&lt;-15%)", "avg_steep_downhill_pace_min_km"),
    ("moderate_downhill", "Умеренный спуск", "avg_moderate_downhill_pace_min_km"),
    ("gentle_downhill", "Пологий спуск", "avg_gentle_downhill_pace_min_km"),
    ("flat", "Ровный участок", "avg_flat_pace_min_km"),
    ("gentle_uphill", "Пологий подъём", "avg_gentle_uphill_pace_min_km"),
    ("moderate_uphill", "Умеренный подъём", "avg_moderate_uphill_pace_min_km"),
    ("steep_uphill", "Крутой подъём (&gt;15%)", "avg_steep_uphill_pace_min_km"),
]


def format_run_profile(profile: dict) -> str:
    """Format running profile for display."""
    activities = profile.get("total_activities", 0)

    lines = [
        "📊 <b>Твой профиль бегуна</b>",
        "",
        f"Проанализировано: {activities} активностей",
        "",
    ]

    # Try 11-category from gradient_paces JSON
    gradient_paces = profile.get("gradient_paces")
    if gradient_paces:
        for key, label in _RUN_GRADIENT_CATEGORIES:
            cat_data = gradient_paces.get(key, {})
            pace = cat_data.get("avg")
            samples = cat_data.get("samples", 0)
            pace_str = format_pace(pace)
            count_str = f" ({samples})" if samples else ""
            lines.append(f"• {label}: {pace_str}/км{count_str}")
    else:
        # Fallback to legacy 7 categories
        for key, label, pace_field in _LEGACY_RUN_CATEGORIES:
            pace = profile.get(pace_field)
            count = profile.get(f"{key}_sample_count")
            pace_str = format_pace(pace)
            count_str = f" ({count})" if count else ""
            lines.append(f"• {label}: {pace_str}/км{count_str}")

    # Walk threshold
    threshold = profile.get("walk_threshold_percent", 25.0)
    lines.append("")
    lines.append(f"Порог перехода на шаг: {threshold:.0f}%")
    lines.append(f"(на подъёмах круче {threshold:.0f}% ты переходишь на шаг)")

    return "\n".join(lines)


def format_empty_profile(profile_type: str) -> str:
    """Format message when profile is empty."""
    type_label = "бегуна" if profile_type == "running" else "хайкера"
    activity_types = "Run/TrailRun" if profile_type == "running" else "Hike/Walk"
    return f"""
📊 <b>Профиль {type_label}</b>

❌ <b>Профиль пока не рассчитан</b>

Для персонализации нужно:
1. Подключить Strava (/strava)
2. Иметь хотя бы 3 {activity_types} активности
3. Синхронизировать сплиты
4. Нажать "Пересчитать профиль"

💡 Если Strava подключён, нажми кнопку ниже чтобы пересчитать.
"""


# =============================================================================
# Handlers
# =============================================================================

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Handle /profile command."""
    telegram_id = str(message.from_user.id)

    try:
        # Get user info to determine preferred activity type
        user_info = await api_client.get_user_info(telegram_id)

        if not user_info:
            await message.answer(
                "❌ Пользователь не найден. Используй /start для начала.",
                parse_mode="HTML"
            )
            return

        # Determine which profile to show first
        preferred = user_info.get("preferred_activity_type", "hiking")

        # Get both profiles
        hike_profile = await api_client.get_hike_profile(telegram_id)
        run_profile = await api_client.get_run_profile(telegram_id)

        # Determine which profile to show
        if preferred == "running":
            primary_profile = run_profile
            primary_type = "running"
            other_profile = hike_profile
            other_type = "hiking"
        else:
            primary_profile = hike_profile
            primary_type = "hiking"
            other_profile = run_profile
            other_type = "running"

        # Check if primary profile has data
        has_primary = primary_profile and has_profile_data(primary_profile)
        has_other = other_profile and has_profile_data(other_profile)
        strava_connected = user_info.get("strava_connected", False)

        if has_primary:
            if primary_type == "running":
                text = format_run_profile(primary_profile)
            else:
                text = format_hike_profile(primary_profile)
            keyboard = get_profile_keyboard(primary_type, has_other)
        else:
            text = format_empty_profile(primary_type)
            keyboard = get_empty_profile_keyboard(strava_connected)

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        await message.answer(
            "❌ Ошибка при загрузке профиля. Попробуй позже.",
            parse_mode="HTML"
        )


def has_profile_data(profile: dict) -> bool:
    """Check if profile has meaningful data."""
    if not profile:
        return False
    # Check if at least flat pace is set
    return profile.get("avg_flat_pace_min_km") is not None


@router.callback_query(F.data.startswith("profile:"))
async def handle_profile_callback(callback: CallbackQuery):
    """Handle profile-related callbacks."""
    await callback.answer()

    action = callback.data.split(":", 1)[1]
    telegram_id = str(callback.from_user.id)

    if action == "recalculate":
        # Trigger profile recalculation
        await callback.message.edit_text(
            "🔄 Пересчитываю профиль...",
            parse_mode="HTML"
        )

        try:
            # Determine profile type from the current message text
            current_text = callback.message.text or ""
            profile_type = "running" if "бегуна" in current_text else "hiking"

            result = await api_client.recalculate_profile(telegram_id, profile_type)
            if result:
                type_label = "бегуна" if profile_type == "running" else "хайкера"
                await callback.message.edit_text(
                    f"✅ Профиль {type_label} пересчитан! Используй /profile чтобы посмотреть.",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось пересчитать профиль. Возможно, недостаточно данных.",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Error recalculating profile: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при пересчёте профиля.",
                parse_mode="HTML"
            )

    elif action in ("hiking", "running"):
        # Switch to different profile view
        try:
            if action == "running":
                profile = await api_client.get_run_profile(telegram_id)
                if profile and has_profile_data(profile):
                    text = format_run_profile(profile)
                else:
                    text = format_empty_profile("running")
            else:
                profile = await api_client.get_hike_profile(telegram_id)
                if profile and has_profile_data(profile):
                    text = format_hike_profile(profile)
                else:
                    text = format_empty_profile("hiking")

            # Get other profile to check availability
            other_type = "hiking" if action == "running" else "running"
            other_profile = (
                await api_client.get_hike_profile(telegram_id)
                if other_type == "hiking"
                else await api_client.get_run_profile(telegram_id)
            )
            has_other = other_profile and has_profile_data(other_profile)

            keyboard = get_profile_keyboard(action, has_other)
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error switching profile: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при загрузке профиля.",
                parse_mode="HTML"
            )

    elif action == "connect_strava":
        # Redirect to Strava connection
        auth_url = api_client.get_strava_auth_url(telegram_id)
        await callback.message.edit_text(
            f"🔗 Для подключения Strava перейди по ссылке:\n{auth_url}",
            parse_mode="HTML"
        )
