"""
Strava Integration Handlers

Commands:
- /strava - Show Strava status and connect button
- /strava_stats - Show athlete statistics
- /strava_activities - Show synced activities
- /strava_disconnect - Disconnect Strava
"""

from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from services.api_client import api_client
from keyboards.strava import (
    get_strava_connect_keyboard,
    get_strava_connected_keyboard,
    get_confirm_disconnect_keyboard,
    get_activities_keyboard,
)

router = Router()


# =============================================================================
# Commands
# =============================================================================

@router.message(Command("strava"))
async def cmd_strava(message: Message):
    """
    Show Strava connection status.

    If not connected - show connect button.
    If connected - show stats summary and options.
    """
    telegram_id = message.from_user.id

    # Check connection status
    status = await api_client.get_strava_status(telegram_id)

    if status.connected:
        # Show connected status with options
        text = (
            "✅ <b>Strava подключён</b>\n\n"
            f"Athlete ID: <code>{status.athlete_id}</code>\n\n"
            "Теперь я могу использовать твою статистику "
            "для более точных прогнозов!"
        )
        await message.answer(
            text,
            reply_markup=get_strava_connected_keyboard()
        )
    else:
        # Show connect link
        auth_url = api_client.get_strava_auth_url(telegram_id)

        # Check if localhost (dev mode) - can't use inline URL button
        if "localhost" in auth_url or "127.0.0.1" in auth_url:
            text = (
                "🏃 <b>Подключи Strava</b>\n\n"
                "Подключив Strava, я смогу:\n"
                "• Учитывать твою реальную подготовку\n"
                "• Сравнивать прогнозы с фактическими результатами\n"
                "• Персонализировать расчёты под тебя\n\n"
                "🔗 <b>Для подключения открой эту ссылку:</b>\n"
                f"<code>{auth_url}</code>\n\n"
                "<i>(Скопируй и открой в браузере)</i>"
            )
            await message.answer(text)
        else:
            text = (
                "🏃 <b>Подключи Strava</b>\n\n"
                "Подключив Strava, я смогу:\n"
                "• Учитывать твою реальную подготовку\n"
                "• Сравнивать прогнозы с фактическими результатами\n"
                "• Персонализировать расчёты под тебя\n\n"
                "Нажми кнопку ниже для авторизации:"
            )
            await message.answer(
                text,
                reply_markup=get_strava_connect_keyboard(auth_url)
            )


@router.message(Command("strava_stats"))
async def cmd_strava_stats(message: Message):
    """Show detailed Strava statistics."""
    telegram_id = message.from_user.id

    # Check connection
    status = await api_client.get_strava_status(telegram_id)

    if not status.connected:
        await message.answer(
            "❌ Strava не подключён.\n"
            "Используй /strava чтобы подключить."
        )
        return

    # Fetch stats
    await message.answer("⏳ Загружаю статистику...")

    stats = await api_client.get_strava_stats(telegram_id)

    if not stats:
        await message.answer(
            "😕 Не удалось загрузить статистику.\n"
            "Попробуй позже или переподключи Strava."
        )
        return

    # Format stats
    text = (
        "📊 <b>Твоя Strava статистика</b>\n\n"
        "<b>За всё время:</b>\n"
        f"🏃 Пробежек: {stats.total_runs}\n"
        f"📏 Дистанция: {stats.total_distance_km:,.1f} км\n"
        f"⛰️ Набор высоты: {stats.total_elevation_m:,.0f} м\n\n"
        "<b>В этом году:</b>\n"
        f"🏃 Пробежек: {stats.ytd_runs}\n"
        f"📏 Дистанция: {stats.ytd_distance_km:,.1f} км\n\n"
        "<b>За последние 4 недели:</b>\n"
        f"🏃 Пробежек: {stats.recent_runs}\n"
        f"📏 Дистанция: {stats.recent_distance_km:,.1f} км"
    )

    await message.answer(text)


@router.message(Command("strava_disconnect"))
async def cmd_strava_disconnect(message: Message):
    """Disconnect Strava account."""
    telegram_id = message.from_user.id

    status = await api_client.get_strava_status(telegram_id)

    if not status.connected:
        await message.answer("Strava и так не подключён.")
        return

    await message.answer(
        "⚠️ Отключить Strava?\n\n"
        "Все сохранённые данные будут удалены.",
        reply_markup=get_confirm_disconnect_keyboard()
    )


# =============================================================================
# Callbacks
# =============================================================================

@router.callback_query(lambda c: c.data == "strava:stats")
async def callback_strava_stats(callback: CallbackQuery):
    """Handle stats button click."""
    await callback.answer()

    telegram_id = callback.from_user.id
    stats = await api_client.get_strava_stats(telegram_id)

    if not stats:
        await callback.message.answer(
            "😕 Не удалось загрузить статистику."
        )
        return

    text = (
        "📊 <b>Твоя Strava статистика</b>\n\n"
        "<b>За всё время:</b>\n"
        f"🏃 Пробежек: {stats.total_runs}\n"
        f"📏 Дистанция: {stats.total_distance_km:,.1f} км\n"
        f"⛰️ Набор высоты: {stats.total_elevation_m:,.0f} м\n\n"
        "<b>В этом году:</b>\n"
        f"🏃 Пробежек: {stats.ytd_runs}\n"
        f"📏 Дистанция: {stats.ytd_distance_km:,.1f} км\n\n"
        "<b>За последние 4 недели:</b>\n"
        f"🏃 Пробежек: {stats.recent_runs}\n"
        f"📏 Дистанция: {stats.recent_distance_km:,.1f} км"
    )

    await callback.message.answer(text)




@router.callback_query(lambda c: c.data == "strava:disconnect")
async def callback_strava_disconnect(callback: CallbackQuery):
    """Handle disconnect button click."""
    await callback.answer()

    await callback.message.edit_text(
        "⚠️ Отключить Strava?\n\n"
        "Все сохранённые данные будут удалены.",
        reply_markup=get_confirm_disconnect_keyboard()
    )


@router.callback_query(lambda c: c.data == "strava:confirm_disconnect")
async def callback_confirm_disconnect(callback: CallbackQuery):
    """Handle disconnect confirmation."""
    await callback.answer()

    telegram_id = callback.from_user.id
    success = await api_client.disconnect_strava(telegram_id)

    if success:
        await callback.message.edit_text(
            "✅ Strava отключён.\n\n"
            "Используй /strava чтобы подключить снова."
        )
    else:
        await callback.message.edit_text(
            "😕 Не удалось отключить Strava.\n"
            "Попробуй позже."
        )


@router.callback_query(lambda c: c.data == "strava:cancel")
async def callback_cancel(callback: CallbackQuery):
    """Handle cancel button click."""
    await callback.answer("Отменено")
    await callback.message.delete()


# =============================================================================
# Activities
# =============================================================================

def format_activity(a) -> str:
    """Format single activity for display."""
    # Parse date
    date_str = a.start_date[:10] if a.start_date else "?"

    # Format time
    hours = a.moving_time_min // 60
    mins = a.moving_time_min % 60
    time_str = f"{hours}:{mins:02d}" if hours else f"{mins} мин"

    # Format pace
    pace_str = ""
    if a.pace_min_km:
        pace_min = int(a.pace_min_km)
        pace_sec = int((a.pace_min_km - pace_min) * 60)
        pace_str = f" • {pace_min}:{pace_sec:02d}/км"

    # Activity type emoji
    type_emoji = {
        "Run": "🏃",
        "Hike": "🥾",
        "Walk": "🚶",
        "Trail Run": "🏃‍♂️",
    }.get(a.activity_type, "🏃")

    name = a.name[:25] + "..." if a.name and len(a.name) > 25 else (a.name or "Без названия")

    return (
        f"{type_emoji} <b>{name}</b>\n"
        f"   {date_str} • {a.distance_km:.1f} км • {time_str}{pace_str}"
    )


@router.message(Command("strava_activities"))
async def cmd_strava_activities(message: Message):
    """Show synced Strava activities."""
    telegram_id = message.from_user.id

    # Check connection
    status = await api_client.get_strava_status(telegram_id)

    if not status.connected:
        await message.answer(
            "❌ Strava не подключён.\n"
            "Используй /strava чтобы подключить."
        )
        return

    await show_activities(message, telegram_id, activity_type=None, offset=0)


async def show_activities(
    message: Message,
    telegram_id: int,
    activity_type: str = None,
    offset: int = 0,
    edit: bool = False
):
    """Show activities list."""
    activities, total, sync_status = await api_client.get_strava_activities(
        telegram_id,
        activity_type=activity_type,
        limit=10,
        offset=offset
    )

    if not activities and offset == 0:
        # No activities yet
        sync_info = ""
        if sync_status.in_progress:
            sync_info = "\n\n⏳ Синхронизация в процессе..."
        elif sync_status.total_synced == 0:
            sync_info = "\n\n💡 Нажми 'Синхронизировать' чтобы загрузить активности."

        text = f"📭 Активности пока не загружены.{sync_info}"

        if edit:
            await message.edit_text(text, reply_markup=get_strava_connected_keyboard())
        else:
            await message.answer(text, reply_markup=get_strava_connected_keyboard())
        return

    # Build header
    filter_name = {
        "Run": "пробежки",
        "Hike": "походы",
        None: "все активности"
    }.get(activity_type, activity_type or "все")

    header = f"🏃 <b>Твои {filter_name}</b>\n"
    header += f"Показано {offset + 1}-{offset + len(activities)} из {total}\n"

    if sync_status.last_sync:
        sync_date = sync_status.last_sync[:10]
        header += f"<i>Синхронизировано: {sync_date}</i>\n"

    if sync_status.in_progress:
        header += "⏳ <i>Синхронизация...</i>\n"

    header += "\n"

    # Format activities
    activity_lines = [format_activity(a) for a in activities]
    text = header + "\n\n".join(activity_lines)

    # Check if there are more
    has_more = (offset + len(activities)) < total

    keyboard = get_activities_keyboard(
        has_more=has_more,
        offset=offset,
        activity_type=activity_type
    )

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "strava:activities")
async def callback_activities(callback: CallbackQuery):
    """Handle activities button click."""
    await callback.answer()
    telegram_id = callback.from_user.id
    await show_activities(callback.message, telegram_id, activity_type=None, offset=0, edit=False)


@router.callback_query(lambda c: c.data and c.data.startswith("strava:activities:"))
async def callback_activities_page(callback: CallbackQuery):
    """Handle activities pagination/filter."""
    await callback.answer()

    # Parse callback data: strava:activities:{type}:{offset}
    parts = callback.data.split(":")
    if len(parts) != 4:
        return

    activity_type = parts[2] if parts[2] != "all" else None
    offset = int(parts[3])

    telegram_id = callback.from_user.id
    await show_activities(
        callback.message,
        telegram_id,
        activity_type=activity_type,
        offset=offset,
        edit=True
    )


@router.callback_query(lambda c: c.data == "strava:sync")
async def callback_sync(callback: CallbackQuery):
    """Handle sync button click."""
    await callback.answer("Запускаю синхронизацию...")

    telegram_id = callback.from_user.id
    success = await api_client.trigger_strava_sync(telegram_id)

    if success:
        await callback.message.answer(
            "✅ Синхронизация запущена!\n\n"
            "Активности будут загружаться в фоне.\n"
            "Проверь через пару минут командой /strava_activities"
        )
    else:
        await callback.message.answer(
            "😕 Не удалось запустить синхронизацию.\n"
            "Попробуй позже."
        )
