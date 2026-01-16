"""
Common Handlers

Basic commands: /start, /help, /cancel
"""

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    await message.answer(
        "Привет! Я помогу рассчитать время похода.\n\n"
        "Отправь мне GPX файл с маршрутом, и я:\n"
        "- Проанализирую дистанцию и набор высоты\n"
        "- Учту твой опыт и вес рюкзака\n"
        "- Рассчитаю безопасное время прохождения\n"
        "- Дам рекомендации по времени старта\n\n"
        "Просто отправь .gpx файл, чтобы начать!"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "<b>Как пользоваться ботом:</b>\n\n"
        "1. Отправь GPX файл с маршрутом\n"
        "2. Выбери свой уровень опыта\n"
        "3. Укажи вес рюкзака\n"
        "4. Укажи размер группы\n"
        "5. Получи прогноз времени!\n\n"
        "<b>Команды:</b>\n"
        "/start - начать заново\n"
        "/help - эта справка\n"
        "/cancel - отменить текущую операцию\n"
        "/strava - подключить Strava\n"
        "/strava_stats - статистика Strava\n"
        "/strava_activities - твои активности\n\n"
        "<b>Алгоритм учитывает:</b>\n"
        "• Набор и сброс высоты\n"
        "• Высотную акклиматизацию\n"
        "• Опыт и физ. подготовку\n"
        "• Вес рюкзака\n"
        "• Размер группы\n"
        "• Данные из Strava (если подключён)"
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
