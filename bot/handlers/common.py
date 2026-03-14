"""
Common Handlers

Basic commands: /start, /help, /cancel
"""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from services.api_client import api_client
from services.notifications import notification_service
from handlers.onboarding import start_onboarding

logger = logging.getLogger(__name__)

router = Router()


WELCOME_BACK_TEXT = """
👋 <b>С возвращением!</b>

Отправь GPX файл, и я рассчитаю время прохождения маршрута.

<b>Команды:</b>
/profile — твой профиль темпа
/strava — управление Strava
/help — справка
"""


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command - check onboarding status."""
    await state.clear()

    telegram_id = message.from_user.id
    tg_user = message.from_user

    # Build display name from Telegram profile
    name_parts = [tg_user.first_name or ""]
    if tg_user.last_name:
        name_parts.append(tg_user.last_name)
    tg_name = " ".join(name_parts).strip() or None
    tg_username = tg_user.username  # without @

    try:
        # Create or update user with Telegram info
        await api_client.create_user(
            telegram_id,
            name=tg_name,
            telegram_username=tg_username,
        )

        # Check if user exists and has completed onboarding
        user_info = await api_client.get_user_info(telegram_id)

        if user_info and user_info.get("onboarding_complete"):
            # Existing user - show welcome back message
            await message.answer(WELCOME_BACK_TEXT, parse_mode="HTML")
            # Check and show pending notifications
            await notification_service.check_and_show_notifications(message, telegram_id)
        else:
            # New user or didn't complete onboarding - start onboarding
            logger.info(f"Starting onboarding for user {telegram_id}")
            await start_onboarding(message, state)

    except Exception as e:
        logger.error(f"Error in /start: {e}")
        # Fallback to onboarding on error
        await start_onboarding(message, state)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "<b>Как пользоваться ботом:</b>\n\n"
        "1. Отправь GPX файл с маршрутом\n"
        "2. Выбери тип активности (хайкинг/бег)\n"
        "3. Ответь на вопросы\n"
        "4. Получи прогноз времени!\n\n"
        "<b>Команды:</b>\n"
        "/start — начать заново\n"
        "/help — эта справка\n"
        "/cancel — отменить текущую операцию\n"
        "/profile — твой профиль темпа\n"
        "/strava — управление Strava\n"
        "/strava_stats — статистика Strava\n"
        "/strava_activities — твои активности\n\n"
        "<b>Алгоритм учитывает:</b>\n"
        "• Набор и сброс высоты\n"
        "• Высотную акклиматизацию\n"
        "• Опыт и физ. подготовку\n"
        "• Вес рюкзака\n"
        "• Размер группы\n"
        "• Данные из Strava (если подключён)\n"
        "• GAP для трейлраннинга",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Handle /cancel command."""
    current_state = await state.get_state()

    if current_state is None:
        await message.answer("Нечего отменять. Отправь GPX файл, чтобы начать.")
        return

    await state.clear()
    await message.answer(
        "Операция отменена.\n"
        "Отправь GPX файл, чтобы начать заново."
    )
