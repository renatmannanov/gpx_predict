"""
Prediction Handlers

Handlers for GPX upload and prediction flow.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.prediction import PredictionStates
from keyboards.prediction import (
    get_activity_type_keyboard,
    get_experience_keyboard,
    get_backpack_keyboard,
    get_group_size_keyboard,
    get_yes_no_keyboard,
    get_route_type_keyboard,
)
from handlers.trail_run import start_trail_run_flow
from services.api_client import api_client, APIError
from utils.formatters import format_time
from config import settings

logger = logging.getLogger(__name__)
router = Router()


def format_gpx_info(info) -> str:
    """Format GPX info for display."""
    name = info.name or info.filename
    return (
        f"Маршрут: {name}\n\n"
        f"Дистанция: {info.distance_km:.1f} км\n"
        f"Набор высоты: {info.elevation_gain_m:.0f} м\n"
        f"Сброс высоты: {info.elevation_loss_m:.0f} м\n"
        f"Макс. высота: {info.max_elevation_m:.0f} м\n"
        f"Мин. высота: {info.min_elevation_m:.0f} м"
    )


def format_prediction(prediction, gpx_name: str, gpx_info=None) -> str:
    """Format prediction result for display."""
    result = f"Прогноз для маршрута:\n{gpx_name}\n\n"

    # Show route info if available
    if gpx_info:
        result += (
            f"Дистанция: {gpx_info.distance_km:.1f} км\n"
            f"Набор: +{gpx_info.elevation_gain_m:.0f} м, "
            f"сброс: -{gpx_info.elevation_loss_m:.0f} м\n\n"
        )

    # Main time
    result += (
        f"Общее время: {format_time(prediction.estimated_time_hours)}\n"
        f"С запасом (+20%): {format_time(prediction.safe_time_hours)}\n\n"
    )

    # Time breakdown
    if prediction.time_breakdown:
        tb = prediction.time_breakdown
        # Calculate total breaks
        total_breaks = tb.rest_time_hours + tb.lunch_time_hours
        result += (
            f"Из них:\n"
            f"  Движение: {format_time(tb.moving_time_hours)}\n"
            f"  Остановки: {format_time(total_breaks)}"
        )
        # Detail breaks
        details = []
        if tb.rest_time_hours > 0:
            details.append(f"отдых {format_time(tb.rest_time_hours)}")
        if tb.lunch_time_hours > 0:
            details.append(f"обед {format_time(tb.lunch_time_hours)}")
        if details:
            result += f" ({', '.join(details)})"
        result += "\n\n"

    result += f"Рекомендуемый старт: {prediction.recommended_start}\n"

    if prediction.recommended_turnaround:
        result += f"Точка разворота: {prediction.recommended_turnaround}\n"

    # Show warnings
    if prediction.warnings:
        result += "\nПредупреждения:\n"
        for w in prediction.warnings:
            emoji = {"info": "i", "warning": "!", "danger": "!!"}
            level_emoji = emoji.get(w.get("level", "info"), "i")
            result += f"[{level_emoji}] {w.get('message', '')}\n"

    return result


def format_full_prediction(comparison: dict, gpx_info, old_prediction) -> str:
    """Format complete prediction with all methods in one message."""
    # Use original filename from gpx_info.name or fallback to filename
    filename = gpx_info.name if gpx_info and gpx_info.name else (gpx_info.filename if gpx_info else "Маршрут")
    # Remove .gpx extension for display
    if filename.lower().endswith('.gpx'):
        filename = filename[:-4]

    result = f"<b>Прогноз для маршрута:</b>\n{filename}\n"

    result += "\n"

    # Route summary - distance on new line
    result += (
        f"<b>Маршрут:</b>\n"
        f"  {comparison['total_distance_km']:.2f} км\n"
        f"  Подъём: {comparison['ascent_distance_km']:.2f} км (+{comparison['total_ascent_m']:.0f} м)\n"
        f"  Спуск: {comparison['descent_distance_km']:.2f} км (-{comparison['total_descent_m']:.0f} м)\n\n"
    )

    # Moving time by methods
    result += "<b>Чистое время движения:</b>\n"
    totals = comparison["totals"]
    tobler_hours = totals.get("tobler", 0)
    naismith_hours = totals.get("naismith", 0)

    result += f"  tobler: {format_time(tobler_hours)}\n"
    result += f"  naismith: {format_time(naismith_hours)}\n"

    # Personalized methods (if user has profile) or invite to connect Strava
    if "tobler_personalized" in totals:
        result += f"  📊 tobler (ваш темп): {format_time(totals['tobler_personalized'])}\n"
    if "naismith_personalized" in totals:
        result += f"  📊 naismith (ваш темп): {format_time(totals['naismith_personalized'])}\n"

    if not old_prediction.personalized:
        result += f"📊 <i>Хотите точнее? Подключите Strava для персонального расчёта на основе ваших активностей.</i>\n"

    result += "\n——————————————\n\n"

    # Additional time (was "Рекомендуем добавить")
    rest_hours = comparison.get("rest_time_hours", 0)
    lunch_hours = comparison.get("lunch_time_hours", 0)
    buffer_hours = tobler_hours * 0.2  # 20% buffer

    result += "<b>Дополнительное время:</b>\n"
    if lunch_hours > 0:
        result += f"  + {format_time(lunch_hours)} обед\n"
    if rest_hours > 0:
        result += f"  + {format_time(rest_hours)} отдых\n"
    result += f"  + {format_time(buffer_hours)} (20% на непредвиденные ситуации)\n"

    # Total estimate
    total_estimate = tobler_hours + rest_hours + lunch_hours + buffer_hours
    result += f"<b>Общее время:</b> ~{format_time(total_estimate)}\n\n"

    # Recommended start with full schedule
    sunrise = comparison.get("sunrise", "06:00")
    sunset = comparison.get("sunset", "20:00")

    # Calculate recommended start
    sunset_hour = int(sunset.split(":")[0])
    sunset_min = int(sunset.split(":")[1])
    sunrise_hour = int(sunrise.split(":")[0])
    sunrise_min = int(sunrise.split(":")[1])

    # Want to return 1 hour before sunset
    target_return = sunset_hour - 1
    needed_hours = total_estimate
    start_hour = target_return - needed_hours

    # Don't start before sunrise
    if start_hour < sunrise_hour:
        start_hour = sunrise_hour
        start_min = sunrise_min
        recommended_start = sunrise
    else:
        start_min = 0
        recommended_start = f"{int(start_hour):02d}:00"

    # Calculate finish time
    finish_hours = start_hour + start_min / 60 + total_estimate
    finish_hour = int(finish_hours)
    finish_min = int((finish_hours - finish_hour) * 60)
    finish_time = f"{finish_hour:02d}:{finish_min:02d}"

    # Check if late return (finish less than 1 hour before sunset or after sunset)
    sunset_decimal = sunset_hour + sunset_min / 60
    is_late_return = finish_hours > (sunset_decimal - 1)

    result += "<b>Рекомендуемый старт:</b>\n"
    result += f"  рассвет в {sunrise}\n"
    result += f"  {recommended_start} старт\n"
    result += f"  преодоление маршрута {format_time(total_estimate)}\n"
    result += f"  {finish_time} ориентировочный финиш\n"
    result += f"  закат в {sunset}\n"

    result += "\n"

    # Warnings section
    max_elevation = comparison.get("max_elevation_m", 0)
    warnings = []

    # Late return warning (first, most critical)
    if is_late_return:
        warnings.append(("🚨", "Риск вернуться после заката. Стартуйте раньше или выберите маршрут короче."))

    if total_estimate > 8:
        warnings.append(("ℹ️", "Длинный поход (8+ часов). Возьмите достаточно воды и еды."))

    if max_elevation > 3000:
        warnings.append(("⚠️", f"Маршрут достигает {max_elevation:.0f}м. Следите за симптомами горной болезни."))

    if warnings:
        result += "<b>Предупреждения:</b>\n"
        for emoji, message in warnings:
            result += f"{emoji} {message}\n"
        result += "\n"

    return result


def format_segments(comparison: dict) -> str:
    """Format segments as a separate message in expandable blockquote."""
    seg_type_names = {
        "ascent": "↑ Подъём",
        "descent": "↓ Спуск",
        "flat": "→ Ровный"
    }

    content = ""
    for seg in comparison["segments"]:
        seg_type = seg_type_names.get(seg["segment_type"], seg["segment_type"])
        ele_str = f"+{seg['elevation_change_m']:.0f}" if seg['elevation_change_m'] >= 0 else f"{seg['elevation_change_m']:.0f}"

        content += (
            f"<b>{seg['segment_number']}. {seg_type}</b>\n"
            f"  {seg['distance_km']} км, {ele_str} м\n"
            f"  Градиент: {seg['gradient_percent']}%\n"
        )

        # Show all methods for this segment
        for method_name, method_result in seg["methods"].items():
            content += f"  [{method_name}] {format_time(method_result['time_hours'])}\n"

        content += "\n"

    return f"<blockquote expandable><b>Разбивка по участкам:</b>\n\n{content.strip()}</blockquote>"


# === GPX Upload ===

@router.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    """Handle document upload."""
    document = message.document

    # Validate file extension
    if not document.file_name or not document.file_name.lower().endswith(".gpx"):
        await message.answer(
            "Пожалуйста, отправь файл с расширением .gpx"
        )
        return

    # Validate file size
    max_size = settings.max_file_size_mb * 1024 * 1024
    if document.file_size and document.file_size > max_size:
        await message.answer(
            f"Файл слишком большой. Максимум: {settings.max_file_size_mb} МБ"
        )
        return

    # Download file
    loading_msg = await message.answer("Загружаю файл...")

    try:
        file = await message.bot.get_file(document.file_id)
        file_content = await message.bot.download_file(file.file_path)
        content = file_content.read()
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        await message.answer("Ошибка при загрузке файла. Попробуй ещё раз.")
        return

    # Upload to backend
    try:
        gpx_info = await api_client.upload_gpx(document.file_name, content)
    except APIError as e:
        await message.answer(f"Ошибка при обработке GPX: {e.detail}")
        return
    except Exception as e:
        logger.error(f"API error: {e}")
        await message.answer("Ошибка сервера. Попробуй позже.")
        return

    # Save to state
    await state.update_data(
        gpx_id=gpx_info.gpx_id,
        gpx_name=gpx_info.name or gpx_info.filename,
        gpx_info=gpx_info,
    )

    # Show GPX info (edit loading message) and ask for activity type
    await loading_msg.edit_text(format_gpx_info(gpx_info))
    await message.answer(
        "Какой прогноз нужен?",
        reply_markup=get_activity_type_keyboard()
    )
    await state.set_state(PredictionStates.selecting_activity_type)


# === Activity Type Selection ===

@router.callback_query(PredictionStates.selecting_activity_type, F.data.startswith("activity:"))
async def handle_activity_type(callback: CallbackQuery, state: FSMContext):
    """Handle activity type selection after GPX upload."""
    activity_type = callback.data.split(":")[1]
    await state.update_data(activity_type=activity_type)

    if activity_type == "trail_run":
        # Trail run flow - delegate to trail_run handler
        data = await state.get_data()
        gpx_id = data.get("gpx_id")
        gpx_info = data.get("gpx_info")

        # Convert gpx_info to dict for trail_run module
        gpx_info_dict = {
            "gpx_id": gpx_info.gpx_id,
            "name": gpx_info.name,
            "filename": gpx_info.filename,
            "distance_km": gpx_info.distance_km,
            "elevation_gain_m": gpx_info.elevation_gain_m,
            "elevation_loss_m": gpx_info.elevation_loss_m,
            "max_elevation_m": gpx_info.max_elevation_m,
            "min_elevation_m": gpx_info.min_elevation_m,
            "is_loop": gpx_info.is_loop,
        }

        # Delete the activity type selection message and start trail run flow
        await callback.message.delete()
        user_id = str(callback.from_user.id)
        await start_trail_run_flow(callback.message, state, gpx_id, gpx_info_dict, user_id=user_id)
    else:
        # Hiking flow - continue with existing logic
        data = await state.get_data()
        gpx_info = data.get("gpx_info")

        # First handle route type question for non-loop routes
        if gpx_info and not gpx_info.is_loop:
            # Linear route - ask if round trip first
            await callback.message.edit_text(
                "Это маршрут в одну сторону или туда-обратно?",
                reply_markup=get_route_type_keyboard()
            )
            await state.set_state(PredictionStates.selecting_route_type)
        else:
            # Loop route - skip route type, proceed to experience check
            await state.update_data(is_round_trip=False)
            await _proceed_to_experience_or_backpack(callback, state)

    await callback.answer()


async def _proceed_to_experience_or_backpack(callback: CallbackQuery, state: FSMContext):
    """
    Check if user has hike profile and skip experience question if so.
    Otherwise ask about experience.
    """
    telegram_id = str(callback.from_user.id)

    # Check if user has personalized hike profile
    hike_profile = await api_client.get_hike_profile(telegram_id)
    has_profile = hike_profile and hike_profile.get("avg_flat_pace_min_km")

    if has_profile:
        # User has profile - skip experience question, go directly to backpack
        await state.update_data(experience="personalized")  # marker for personalized mode
        await callback.message.edit_text(
            "🎯 Использую твой персональный профиль!\n\nКакой вес рюкзака?",
            reply_markup=get_backpack_keyboard()
        )
        await state.set_state(PredictionStates.selecting_backpack)
    else:
        # No profile - ask about experience
        await callback.message.edit_text(
            "Какой у тебя опыт походов?",
            reply_markup=get_experience_keyboard()
        )
        await state.set_state(PredictionStates.selecting_experience)


# === Route Type Selection ===

@router.callback_query(PredictionStates.selecting_route_type, F.data.startswith("rt:"))
async def handle_route_type(callback: CallbackQuery, state: FSMContext):
    """Handle route type selection."""
    is_round_trip = callback.data.split(":")[1] == "roundtrip"
    await state.update_data(is_round_trip=is_round_trip)

    # Check if user has profile - if yes, skip experience question
    await _proceed_to_experience_or_backpack(callback, state)
    await callback.answer()


# === Experience Selection ===

@router.callback_query(PredictionStates.selecting_experience, F.data.startswith("exp:"))
async def handle_experience(callback: CallbackQuery, state: FSMContext):
    """Handle experience selection."""
    experience = callback.data.split(":")[1]
    await state.update_data(experience=experience)

    await callback.message.edit_text(
        "Какой вес рюкзака?",
        reply_markup=get_backpack_keyboard()
    )
    await state.set_state(PredictionStates.selecting_backpack)
    await callback.answer()


# === Backpack Selection ===

@router.callback_query(PredictionStates.selecting_backpack, F.data.startswith("bp:"))
async def handle_backpack(callback: CallbackQuery, state: FSMContext):
    """Handle backpack selection."""
    backpack = callback.data.split(":")[1]
    await state.update_data(backpack=backpack)

    await callback.message.edit_text(
        "Сколько человек в группе?",
        reply_markup=get_group_size_keyboard()
    )
    await state.set_state(PredictionStates.selecting_group_size)
    await callback.answer()


# === Group Size Selection ===

@router.callback_query(PredictionStates.selecting_group_size, F.data.startswith("gs:"))
async def handle_group_size(callback: CallbackQuery, state: FSMContext):
    """Handle group size selection."""
    group_size = int(callback.data.split(":")[1])
    await state.update_data(group_size=group_size)

    await callback.message.edit_text(
        "Есть ли в группе дети (до 14 лет)?",
        reply_markup=get_yes_no_keyboard("children")
    )
    await state.set_state(PredictionStates.selecting_children)
    await callback.answer()


# === Children Selection ===

@router.callback_query(PredictionStates.selecting_children, F.data.startswith("children:"))
async def handle_children(callback: CallbackQuery, state: FSMContext):
    """Handle children selection."""
    has_children = callback.data.split(":")[1] == "yes"
    await state.update_data(has_children=has_children)

    await callback.message.edit_text(
        "Есть ли в группе пожилые люди (60+ лет)?",
        reply_markup=get_yes_no_keyboard("elderly")
    )
    await state.set_state(PredictionStates.selecting_elderly)
    await callback.answer()


# === Elderly Selection ===

@router.callback_query(PredictionStates.selecting_elderly, F.data.startswith("elderly:"))
async def handle_elderly(callback: CallbackQuery, state: FSMContext):
    """Handle elderly selection and make prediction."""
    has_elderly = callback.data.split(":")[1] == "yes"
    await state.update_data(has_elderly=has_elderly)

    # Get all data
    data = await state.get_data()

    await callback.message.edit_text("Рассчитываю прогноз...")

    gpx_id = data["gpx_id"]
    experience = data.get("experience", "casual")
    backpack = data.get("backpack", "medium")
    group_size = data.get("group_size", 1)
    gpx_name = data.get("gpx_name", "")

    # Get telegram_id for personalization
    telegram_id = str(callback.from_user.id)

    # Get comparison of methods (with personalization if profile exists)
    comparison = None
    try:
        comparison = await api_client.compare_methods(
            gpx_id=gpx_id,
            experience=experience,
            backpack=backpack,
            group_size=group_size,
            telegram_id=telegram_id,
        )
    except APIError as e:
        logger.error(f"Comparison error: {e}")
    except Exception as e:
        logger.error(f"Comparison error: {e}")

    # Make prediction (with personalization if profile exists)
    try:
        prediction = await api_client.predict_hike(
            gpx_id=gpx_id,
            experience=experience,
            backpack=backpack,
            group_size=group_size,
            has_children=data.get("has_children", False),
            has_elderly=has_elderly,
            is_round_trip=data.get("is_round_trip", False),
            telegram_id=telegram_id,
        )
    except APIError as e:
        await callback.message.edit_text(f"Ошибка: {e.detail}")
        await state.clear()
        return
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        await callback.message.edit_text("Ошибка сервера. Попробуй позже.")
        await state.clear()
        return

    # Show unified prediction
    gpx_info = data.get("gpx_info")

    if comparison:
        # Main prediction message
        result = format_full_prediction(comparison, gpx_info, prediction)
        await callback.message.edit_text(result, parse_mode="HTML")

        # Segments as separate message (may be long)
        segments_text = format_segments(comparison)
        # Split into chunks if too long (Telegram limit is 4096)
        if len(segments_text) <= 4096:
            await callback.message.answer(segments_text, parse_mode="HTML")
        else:
            # Split by segments (each segment block ends with \n\n)
            chunks = []
            current_chunk = "<b>Разбивка по участкам:</b>\n\n"
            for segment_block in segments_text.split("\n\n")[1:]:  # Skip header
                if len(current_chunk) + len(segment_block) + 2 > 4000:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                current_chunk += segment_block + "\n\n"
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            for chunk in chunks:
                await callback.message.answer(chunk, parse_mode="HTML")
    else:
        # Fallback to old format
        result = format_prediction(
            prediction,
            gpx_name,
            gpx_info
        )
        await callback.message.edit_text(result)

    # Clear state
    await state.clear()
    await callback.answer()


# === Cancel Callback ===

@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    """Handle cancel button."""
    await state.clear()
    await callback.message.edit_text(
        "Операция отменена.\n"
        "Отправь GPX файл, чтобы начать заново."
    )
    await callback.answer()
