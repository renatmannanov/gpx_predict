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


def _format_gap_results(totals: dict) -> list:
    """Format 3 GAP methods from totals dict."""
    lines = []
    all_run_methods = [
        ("Strava GAP", totals.get("all_run_strava", 0)),
        ("Minetti GAP", totals.get("all_run_minetti", 0)),
        ("Strava+Minetti", totals.get("all_run_strava_minetti", 0)),
    ]

    for method_name, hours in all_run_methods:
        if hours and hours > 0:
            lines.append(f"  {method_name:16} {format_time(hours)}")

    return lines


def format_trail_run_result(result: dict, gpx_name: str) -> str:
    """Format trail run prediction result for display with dual results."""
    summary = result.get("summary", {})

    distance = summary.get("total_distance_km", 0)
    gain = summary.get("total_elevation_gain_m", 0)
    loss = summary.get("total_elevation_loss_m", 0)
    run_dist = summary.get("running_distance_km", 0)
    hike_dist = summary.get("hiking_distance_km", 0)
    elevation_impact = summary.get("elevation_impact_percent", 0)

    # Get dual results
    totals_strava = result.get("totals_strava")
    totals_manual = result.get("totals_manual") or result.get("totals", {})
    strava_pace = result.get("strava_pace_used")
    manual_pace = result.get("manual_pace_used")

    lines = [
        f"🏃 <b>Trail Run: {gpx_name}</b>",
        "",
        f"📍 {distance:.1f} км | D+ {gain:.0f}м | D- {loss:.0f}м",
    ]

    # Show Strava-based results first (if available)
    if totals_strava and strava_pace:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(f"👤 <b>НА ОСНОВЕ STRAVA</b> ({format_pace(strava_pace)}/км):")
        lines.append("")
        lines.append("⏱ ВСЁ БЕГОМ:")
        lines.extend(_format_gap_results(totals_strava))

    # Show manual/selected pace results
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    if totals_strava:
        # Has both - label as "selected pace"
        lines.append(f"📊 <b>НА ОСНОВЕ ТВОЕГО ТЕМПА</b> ({format_pace(manual_pace)}/км):")
    else:
        # Only manual - simpler header
        lines.append(f"⏱ <b>ВРЕМЯ</b> (темп {format_pace(manual_pace)}/км, всё бегом):")

    lines.append("")
    if not totals_strava:
        lines.append("⏱ ВСЁ БЕГОМ:")
    lines.extend(_format_gap_results(totals_manual))

    # Show personalized if available
    if totals_manual.get("run_personalized"):
        lines.append(f"  🎯 Персональный   {format_time(totals_manual['run_personalized'])}")

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
    if totals_manual.get("combined"):
        lines.append(f"  Комбинированный: {format_time(totals_manual['combined'])}")

    lines.append("")
    lines.append(f"💪 <b>Влияние рельефа:</b> +{elevation_impact:.0f}%")

    # Fatigue info
    if result.get("fatigue_applied"):
        lines.append("")
        lines.append("😓 <b>Усталость:</b> учтена")

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
    gpx_info: dict,
    user_id: str = None
):
    """
    Start trail run prediction flow.

    Called from prediction.py when user selects trail run activity type.
    Always asks for pace, but shows different messages based on Strava status.

    Args:
        message: Message to reply to (may be bot's message from callback)
        state: FSM context
        gpx_id: GPX file ID
        gpx_info: GPX info dict
        user_id: User's Telegram ID (required when called from callback)
    """
    # Use provided user_id or try to get from message
    telegram_id = user_id or str(message.from_user.id)

    # Check if user has run profile with flat pace
    run_profile = await api_client.get_run_profile(telegram_id)

    strava_pace = None
    activities_count = 0

    if run_profile and run_profile.get("avg_flat_pace_min_km"):
        strava_pace = run_profile.get("avg_flat_pace_min_km")
        activities_count = run_profile.get("total_activities", 0)
        logger.debug(f"Trail run profile: pace={strava_pace}, activities={activities_count}")

    # Save GPX info and Strava data to state
    await state.update_data(
        gpx_id=gpx_id,
        gpx_info=gpx_info,
        activity_type="trail_run",
        gap_mode="strava_gap",
        apply_fatigue=False,
        flat_pace_min_km=None,
        strava_pace=strava_pace,
        strava_activities_count=activities_count,
    )

    await state.set_state(TrailRunStates.selecting_flat_pace)

    if strava_pace:
        # User HAS Strava profile - show their pace
        pace_formatted = format_pace(strava_pace)
        text = (
            "🏃 <b>Какой у тебя темп на ровном?</b>\n\n"
            f"<blockquote>👤 Твой темп на ровном: {pace_formatted}/км\n"
            f"На основе {activities_count} активностей из Strava</blockquote>\n\n"
            "Используй темп из Strava или введи свой, если не согласен "
            "или хочешь получить другой результат."
        )
        keyboard = get_flat_pace_keyboard(strava_pace=strava_pace)
    else:
        # User has NO Strava - warning message
        text = (
            "🏃 <b>Какой у тебя темп на ровном?</b>\n\n"
            "<blockquote>⚠️ У тебя не подключена Strava, поэтому расчёт "
            "будет приблизительный</blockquote>\n\n"
            "Выбери свой примерный темп бега на плоской поверхности или введи вручную.\n"
            "Это будет базой для расчёта с учётом рельефа."
        )
        keyboard = get_flat_pace_keyboard()

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def show_trail_run_summary(message: Message, state: FSMContext):
    """Show trail run summary before calculation."""
    data = await state.get_data()
    gpx_info = data.get("gpx_info", {})

    distance = gpx_info.get("distance_km", 0)
    gain = gpx_info.get("elevation_gain_m", 0)
    loss = gpx_info.get("elevation_loss_m", 0)
    name = gpx_info.get("name") or gpx_info.get("filename", "Маршрут")

    fatigue = data.get("apply_fatigue", False)
    flat_pace = data.get("flat_pace_min_km")
    strava_pace = data.get("strava_pace")
    strava_activities = data.get("strava_activities_count", 0)

    fatigue_text = "Да" if fatigue else "Нет"

    # Build pace info
    pace_lines = []
    if strava_pace:
        pace_lines.append(f"• Strava темп: {format_pace(strava_pace)}/км ({strava_activities} активностей)")
    pace_lines.append(f"• Твой темп: {format_pace(flat_pace)}/км")

    text = f"""
🏃 <b>Trail Run: {name}</b>

📍 Маршрут: {distance:.1f} км
📈 Набор: +{gain:.0f}м / -{loss:.0f}м

<b>Буду считать для:</b>
{chr(10).join(pace_lines)}

<b>Настройки:</b>
• Усталость: {fatigue_text}

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
