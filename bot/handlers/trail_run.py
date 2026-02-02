"""
Trail Run Handlers

Handles trail running prediction flow.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.trail_run import TrailRunStates
from keyboards.trail_run import (
    get_flat_pace_keyboard,
    get_fatigue_keyboard,
    get_confirm_keyboard,
    get_settings_keyboard,
    get_gap_mode_keyboard,
)
from services.api_client import api_client
from utils.formatters import format_time, format_pace

logger = logging.getLogger(__name__)

router = Router()


def format_trail_run_result(result: dict, gpx_name: str) -> str:
    """Format trail run prediction result for display."""
    summary = result.get("summary", {})
    totals = result.get("totals", {})

    distance = summary.get("total_distance_km", 0)
    gain = summary.get("total_elevation_gain_m", 0)
    loss = summary.get("total_elevation_loss_m", 0)

    run_time = summary.get("running_time_hours", 0)
    hike_time = summary.get("hiking_time_hours", 0)
    run_dist = summary.get("running_distance_km", 0)
    hike_dist = summary.get("hiking_distance_km", 0)

    elevation_impact = summary.get("elevation_impact_percent", 0)

    lines = [
        f"🏃 <b>Trail Run: {gpx_name}</b>",
        "",
        f"📍 {distance:.1f} км | D+ {gain:.0f}м | D- {loss:.0f}м",
        "",
        "⏱ <b>ВРЕМЯ (всё бегом):</b>",
    ]

    # Show all 3 GAP methods for full route
    all_run_methods = [
        ("Strava GAP", totals.get("all_run_strava", 0)),
        ("Minetti GAP", totals.get("all_run_minetti", 0)),
        ("Strava+Minetti", totals.get("all_run_strava_minetti", 0)),
    ]

    for method_name, hours in all_run_methods:
        if hours and hours > 0:
            lines.append(f"  {method_name:16} {format_time(hours)}")

    # Show personalized if available
    if totals.get("run_personalized"):
        lines.append(f"  🎯 Персональный   {format_time(totals['run_personalized'])}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # Run/Hike breakdown (based on threshold)
    threshold = result.get("walk_threshold_used", 25)
    run_pct = (run_dist / distance * 100) if distance > 0 else 0
    hike_pct = (hike_dist / distance * 100) if distance > 0 else 0

    lines.append(f"📊 <b>БЕГ + ШАГ</b> (порог {threshold:.0f}%):")
    lines.append(f"  🏃 {run_dist:.1f}км ({run_pct:.0f}%) | 🚶 {hike_dist:.1f}км ({hike_pct:.0f}%)")
    lines.append("")

    # Combined time (uses threshold logic)
    if totals.get("combined"):
        lines.append(f"  Комбинированный: {format_time(totals['combined'])}")

    lines.append("")
    lines.append(f"💪 <b>Влияние рельефа:</b> +{elevation_impact:.0f}%")

    # Fatigue info
    if result.get("fatigue_applied"):
        lines.append("")
        lines.append("😓 <b>Усталость:</b> учтена")

    # Personalization info
    if result.get("personalized"):
        activities = result.get("total_activities_used", 0)
        lines.append("")
        lines.append(f"👤 На основе {activities} активностей")

    return "\n".join(lines)


def format_segments(result: dict) -> str:
    """Format ALL segments in quote block for display."""
    segments = result.get("segments", [])
    if not segments:
        return ""

    lines = [f"<blockquote>📊 СЕГМЕНТЫ ({len(segments)}):"]
    lines.append("")

    for i, seg in enumerate(segments, 1):
        distance = seg.get("distance_km", 0)
        gradient = seg.get("gradient_percent", 0)
        movement = seg.get("movement", {})
        mode = movement.get("mode", "run")
        times = seg.get("times", {})

        # Get time from strava_gap as primary
        time_hours = times.get("strava_gap", 0)

        mode_icon = "🏃" if mode == "run" else "🚶"
        gradient_sign = "+" if gradient > 0 else ""

        from utils.formatters import format_time
        lines.append(
            f"{i}. {mode_icon} {distance:.1f}км ({gradient_sign}{gradient:.0f}%) — {format_time(time_hours)}"
        )

    lines.append("</blockquote>")

    return "\n".join(lines)


# =============================================================================
# Flow entry point (called from prediction.py)
# =============================================================================

async def start_trail_run_flow(
    message: Message,
    state: FSMContext,
    gpx_id: str,
    gpx_info: dict
):
    """
    Start trail run prediction flow.

    Called from prediction.py when user selects trail run activity type.
    """
    telegram_id = str(message.from_user.id)

    # Save GPX info to state
    await state.update_data(
        gpx_id=gpx_id,
        gpx_info=gpx_info,
        activity_type="trail_run",
        gap_mode="strava_gap",
        apply_fatigue=False,
        flat_pace_min_km=None,
    )

    # Check if user has run profile
    run_profile = await api_client.get_run_profile(telegram_id)
    has_profile = run_profile and run_profile.get("avg_flat_pace_min_km")

    if has_profile:
        # User has profile - go directly to calculation or settings
        await state.update_data(has_profile=True)
        await show_trail_run_summary(message, state)
    else:
        # No profile - ask for flat pace
        await state.update_data(has_profile=False)
        await state.set_state(TrailRunStates.selecting_flat_pace)
        await message.answer(
            "🏃 <b>Какой у тебя темп на ровном?</b>\n\n"
            "Выбери свой примерный темп бега на плоской поверхности.\n"
            "Это будет базой для расчёта с учётом рельефа.",
            reply_markup=get_flat_pace_keyboard(),
            parse_mode="HTML"
        )


async def show_trail_run_summary(message: Message, state: FSMContext):
    """Show trail run summary before calculation."""
    data = await state.get_data()
    gpx_info = data.get("gpx_info", {})

    distance = gpx_info.get("distance_km", 0)
    gain = gpx_info.get("elevation_gain_m", 0)
    loss = gpx_info.get("elevation_loss_m", 0)
    name = gpx_info.get("name") or gpx_info.get("filename", "Маршрут")

    gap_mode = data.get("gap_mode", "strava_gap")
    fatigue = data.get("apply_fatigue", False)
    has_profile = data.get("has_profile", False)
    flat_pace = data.get("flat_pace_min_km")

    gap_text = "Strava GAP" if gap_mode == "strava_gap" else "Minetti GAP"
    fatigue_text = "Да" if fatigue else "Нет"
    profile_text = "Да (из Strava)" if has_profile else f"Нет ({format_pace(flat_pace)}/км)" if flat_pace else "Нет"

    text = f"""
🏃 <b>Trail Run: {name}</b>

📍 Маршрут: {distance:.1f} км
📈 Набор: +{gain:.0f}м / -{loss:.0f}м

<b>Настройки:</b>
• GAP режим: {gap_text}
• Усталость: {fatigue_text}
• Персонализация: {profile_text}

Нажми "Рассчитать!" или измени настройки.
"""

    await state.set_state(TrailRunStates.confirming)
    await message.answer(text, reply_markup=get_confirm_keyboard(), parse_mode="HTML")


# =============================================================================
# Callbacks
# =============================================================================

@router.callback_query(F.data.startswith("tr:pace:"))
async def handle_pace_selection(callback: CallbackQuery, state: FSMContext):
    """Handle flat pace selection."""
    await callback.answer()

    pace_str = callback.data.split(":")[-1]

    if pace_str == "custom":
        await callback.message.edit_text(
            "Введи свой темп в формате MM:SS (например, 6:30):",
            parse_mode="HTML"
        )
        await state.set_state(TrailRunStates.selecting_flat_pace)
        await state.update_data(waiting_custom_pace=True)
        return

    pace = float(pace_str)
    await state.update_data(flat_pace_min_km=pace, waiting_custom_pace=False)

    logger.info(f"User selected pace: {pace} min/km")

    await show_trail_run_summary(callback.message, state)


@router.message(TrailRunStates.selecting_flat_pace)
async def handle_custom_pace(message: Message, state: FSMContext):
    """Handle custom pace input."""
    data = await state.get_data()
    if not data.get("waiting_custom_pace"):
        return

    text = message.text.strip()

    try:
        if ":" in text:
            parts = text.split(":")
            minutes = int(parts[0])
            seconds = int(parts[1])
            pace = minutes + seconds / 60
        else:
            pace = float(text)

        if pace < 3 or pace > 15:
            await message.answer(
                "❌ Темп должен быть от 3:00 до 15:00/км. Попробуй ещё раз:",
                parse_mode="HTML"
            )
            return

        await state.update_data(flat_pace_min_km=pace, waiting_custom_pace=False)
        await show_trail_run_summary(message, state)

    except (ValueError, IndexError):
        await message.answer(
            "❌ Неверный формат. Введи темп как MM:SS (например, 6:30):",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "tr:confirm")
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    """Handle calculation confirmation."""
    await callback.answer()

    data = await state.get_data()
    telegram_id = str(callback.from_user.id)

    gpx_id = data.get("gpx_id")
    gpx_info = data.get("gpx_info", {})
    gap_mode = data.get("gap_mode", "strava_gap")
    apply_fatigue = data.get("apply_fatigue", False)
    flat_pace = data.get("flat_pace_min_km")

    await callback.message.edit_text("🔄 Рассчитываю...", parse_mode="HTML")

    try:
        result = await api_client.predict_trail_run(
            gpx_id=gpx_id,
            telegram_id=telegram_id,
            gap_mode=gap_mode,
            flat_pace_min_km=flat_pace,
            apply_fatigue=apply_fatigue,
        )

        if not result:
            await callback.message.edit_text(
                "❌ Не удалось рассчитать. Попробуй позже.",
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Format and send result
        gpx_name = gpx_info.get("name") or gpx_info.get("filename", "Маршрут")
        result_text = format_trail_run_result(result, gpx_name)

        await callback.message.edit_text(result_text, parse_mode="HTML")

        # Send segments in separate message if many
        segments_text = format_segments(result)
        if segments_text:
            await callback.message.answer(segments_text, parse_mode="HTML")

        await state.clear()

    except Exception as e:
        logger.error(f"Trail run prediction error: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "tr:settings")
async def handle_settings(callback: CallbackQuery, state: FSMContext):
    """Show settings menu."""
    await callback.answer()

    data = await state.get_data()
    await callback.message.edit_text(
        "⚙️ <b>Настройки расчёта</b>\n\n"
        "Выбери параметр для изменения:",
        reply_markup=get_settings_keyboard(data),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "tr:set:gap")
async def handle_set_gap(callback: CallbackQuery, state: FSMContext):
    """Show GAP mode selection."""
    await callback.answer()
    await callback.message.edit_text(
        "🔧 <b>Выбери режим GAP:</b>\n\n"
        "<b>Strava GAP</b> — на основе данных 240k атлетов (рекомендуется)\n"
        "<b>Minetti GAP</b> — научная формула энергозатрат",
        reply_markup=get_gap_mode_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tr:gap:"))
async def handle_gap_selection(callback: CallbackQuery, state: FSMContext):
    """Handle GAP mode selection."""
    await callback.answer()

    mode = callback.data.split(":")[-1]
    if mode == "auto":
        mode = "strava_gap"  # Default to Strava

    await state.update_data(gap_mode=mode)
    await show_trail_run_summary(callback.message, state)


@router.callback_query(F.data == "tr:set:fatigue")
async def handle_set_fatigue(callback: CallbackQuery, state: FSMContext):
    """Show fatigue selection."""
    await callback.answer()
    await callback.message.edit_text(
        "😓 <b>Учёт усталости:</b>\n\n"
        "Модель усталости добавляет время после 2ч бега.\n"
        "Рекомендуется для дистанций >25км.",
        reply_markup=get_fatigue_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tr:fatigue:"))
async def handle_fatigue_selection(callback: CallbackQuery, state: FSMContext):
    """Handle fatigue selection."""
    await callback.answer()

    value = callback.data.split(":")[-1] == "yes"
    await state.update_data(apply_fatigue=value)
    await show_trail_run_summary(callback.message, state)


@router.callback_query(F.data == "tr:back")
async def handle_back(callback: CallbackQuery, state: FSMContext):
    """Go back to summary."""
    await callback.answer()
    await show_trail_run_summary(callback.message, state)


@router.callback_query(F.data == "tr:cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel trail run flow."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Расчёт отменён.\n\nОтправь GPX файл, чтобы начать заново.",
        parse_mode="HTML"
    )
