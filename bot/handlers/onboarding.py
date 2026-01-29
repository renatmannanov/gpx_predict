"""
Onboarding Handlers

Handles new user onboarding flow with activity type selection and Strava connection.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.onboarding import OnboardingStates
from keyboards.onboarding import (
    get_start_keyboard,
    get_activity_keyboard,
    get_strava_keyboard,
    get_strava_skip_keyboard,
    get_continue_keyboard,
    get_finish_keyboard,
    get_strava_connected_keyboard,
)
from services.api_client import api_client

logger = logging.getLogger(__name__)

router = Router()


# =============================================================================
# Onboarding Texts
# =============================================================================

WELCOME_TEXT = """
👋 <b>Привет! Я GPX Predictor</b>

Помогу рассчитать реалистичное время прохождения маршрута:

🥾 Для хайкинга и пеших походов
🏃 Для трейлраннинга

Учитываю рельеф, набор высоты, твой опыт и реальный темп из Strava.

─────────────────────────────────────

🔮 <b>В разработке:</b>
• Учёт погодных условий
• Тип покрытия тропы (грунт, камни, снег)
• Crowdsourced данные о сложности участков
• Сезонные корректировки

Давай познакомимся! Это займёт пару минут.
"""

ACTIVITY_TEXT = """
<b>Какая активность для тебя приоритетна?</b>

У меня есть два режима работы:

📊 <b>Стандартный</b> — использую проверенные научные формулы (Naismith, Tobler, GAP). Работает сразу, без настройки.

🎯 <b>Персонализированный</b> — анализирую твои реальные активности из Strava и строю профиль именно под твой темп.

Для персонализации у меня <b>ДВА отдельных профиля</b>:
• Профиль хайкера (из Hike/Walk активностей)
• Профиль бегуна (из Run/TrailRun активностей)

Я заполню оба, но начну с того, что тебе важнее:
"""

PERSONALIZATION_HIKING_TEXT = """
🥾 <b>Отлично! Расскажу, как работает прогноз для хайкинга.</b>

В стандартном режиме я использую формулы Naismith и Tobler, которые учитывают расстояние и набор/сброс высоты.

Но каждый человек ходит по-разному! Кто-то быстрее на подъёмах, кто-то на спусках, кто-то держит ровный темп.

─────────────────────────────────────

🎯 <b>Как работает персонализация:</b>

1. Я беру твои Hike/Walk активности из Strava
2. Разбиваю каждую на километровые сегменты (сплиты)
3. Для каждого сплита смотрю: темп + градиент
4. Строю твой профиль: как ты ходишь на разном рельефе

В итоге получается 7 категорий:
• Крутой спуск (&lt;-15%)
• Умеренный спуск (-15% до -8%)
• Пологий спуск (-8% до -3%)
• Ровный участок (-3% до +3%)
• Пологий подъём (+3% до +8%)
• Умеренный подъём (+8% до +15%)
• Крутой подъём (&gt;+15%)
"""

PERSONALIZATION_RUNNING_TEXT = """
🏃 <b>Отлично! Расскажу, как работает прогноз для трейла.</b>

Я использую GAP (Grade Adjusted Pace) — формулу, похожую на ту, что в Strava, но с важным отличием:

⚠️ <b>Проблема Strava:</b> их "Performance Predictions" НЕ учитывает набор высоты маршрута!

Strava скажет: "Ты пробежишь марафон за 3:45"
А на горном марафоне с набором 800м ты реально пробежишь 4:30+ и будешь удивляться, почему так медленно.

Я это исправляю! Плюс учитываю:
• Когда ты переходишь на шаг (крутые подъёмы)
• Накопление усталости на длинных дистанциях
• Замедление на техничных спусках

─────────────────────────────────────

🎯 <b>Как работает персонализация:</b>

1. Беру твои Run/TrailRun активности из Strava
2. Разбиваю на километровые сегменты (сплиты)
3. Анализирую темп на разных градиентах
4. Определяю твой порог перехода на шаг
5. Строю модель усталости под твою выносливость
"""

STRAVA_OFFER_TEXT = """
📊 <b>Твой персональный профиль</b>

Сейчас он пустой — буду использовать стандартные формулы.

• Темп на ровном: ❓ нет данных
• Темп на подъёме: ❓ нет данных
• Темп на спуске: ❓ нет данных

Подключи Strava, и я заполню профиль по твоим активностям.
Это сделает прогнозы намного точнее!
"""

STRAVA_OFFER_TEXT_LOCALHOST = """
📊 <b>Твой персональный профиль</b>

Сейчас он пустой — буду использовать стандартные формулы.

• Темп на ровном: ❓ нет данных
• Темп на подъёме: ❓ нет данных
• Темп на спуске: ❓ нет данных

Подключи Strava, и я заполню профиль по твоим активностям.

🔗 <b>Для подключения открой ссылку:</b>
<code>{auth_url}</code>
<i>(скопируй и открой в браузере)</i>
"""

STRAVA_SKIPPED_TEXT = """
⏭ <b>Понял, пропускаем Strava</b>

Без проблем! Ты сможешь подключить его позже командой /strava.

Пока будем использовать стандартные формулы расчёта.
"""

STRAVA_CONNECTED_TEXT = """
✅ <b>Strava подключён!</b>

Отлично! Теперь я смогу анализировать твои активности и делать персональные прогнозы.

Синхронизация активностей начнётся в фоне.
"""

USAGE_HIKING_TEXT = """
📖 <b>Как пользоваться (хайкинг)</b>

<b>Основной способ:</b>
Просто отправь GPX-файл маршрута, и я рассчитаю время.

<b>Что учитывается:</b>
• Рельеф и набор/сброс высоты
• Твой опыт (начинающий → опытный)
• Вес рюкзака (лёгкий → тяжёлый)
• Размер группы
• Наличие детей/пожилых

<b>Команды:</b>
/strava — управление Strava
/profile — твой профиль темпа
/help — справка
"""

USAGE_RUNNING_TEXT = """
📖 <b>Как пользоваться (трейлраннинг)</b>

<b>Основной способ:</b>
Отправь GPX-файл и выбери "🏃 Трейлраннинг".

<b>Что учитывается:</b>
• GAP (Grade Adjusted Pace) — корректировка темпа по уклону
• Автоматическое определение участков бега/ходьбы
• Модель усталости для длинных дистанций
• Твой персональный темп из Strava (если подключён)

<b>Команды:</b>
/strava — управление Strava
/profile — твой профиль темпа
/help — справка
"""

FINISH_TEXT = """
🎉 <b>Готово!</b>

Настройка завершена. Теперь просто отправь GPX-файл, и я рассчитаю время.

<b>Удачи на маршрутах!</b>
"""


# =============================================================================
# Handlers
# =============================================================================

async def start_onboarding(message: Message, state: FSMContext):
    """
    Start onboarding for a new user.

    Called from /start command in common.py when user hasn't completed onboarding.
    """
    await state.set_state(OnboardingStates.welcome)
    await message.answer(
        WELCOME_TEXT,
        reply_markup=get_start_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "onboarding:start")
async def handle_start_click(callback: CallbackQuery, state: FSMContext):
    """Handle 'Start' button click."""
    await callback.answer()
    await state.set_state(OnboardingStates.selecting_activity)
    await callback.message.edit_text(
        ACTIVITY_TEXT,
        reply_markup=get_activity_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("onboarding:activity:"))
async def handle_activity_selection(callback: CallbackQuery, state: FSMContext):
    """Handle activity type selection (hiking/running)."""
    await callback.answer()

    activity_type = callback.data.split(":")[-1]  # "hiking" or "running"
    await state.update_data(activity_type=activity_type)

    logger.info(f"User {callback.from_user.id} selected activity: {activity_type}")

    # Choose personalization text based on activity type
    if activity_type == "running":
        personalization_text = PERSONALIZATION_RUNNING_TEXT
    else:
        personalization_text = PERSONALIZATION_HIKING_TEXT

    await state.set_state(OnboardingStates.explaining_personalization)
    await callback.message.edit_text(
        personalization_text,
        reply_markup=get_continue_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(
    F.data == "onboarding:continue",
    OnboardingStates.explaining_personalization
)
async def handle_personalization_continue(callback: CallbackQuery, state: FSMContext):
    """Handle 'Continue' after personalization explanation."""
    await callback.answer()

    telegram_id = str(callback.from_user.id)

    # Get Strava auth URL
    auth_url = api_client.get_strava_auth_url(telegram_id)

    # Use different text if localhost (URL can't be in button)
    if "localhost" in auth_url or "127.0.0.1" in auth_url:
        text = STRAVA_OFFER_TEXT_LOCALHOST.format(auth_url=auth_url)
    else:
        text = STRAVA_OFFER_TEXT

    await state.set_state(OnboardingStates.offering_strava)
    await callback.message.edit_text(
        text,
        reply_markup=get_strava_keyboard(auth_url),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "onboarding:strava:skip")
async def handle_strava_skip(callback: CallbackQuery, state: FSMContext):
    """Handle 'Skip Strava' button."""
    await callback.answer()

    await state.set_state(OnboardingStates.skipped_strava)
    await callback.message.edit_text(
        STRAVA_SKIPPED_TEXT,
        reply_markup=get_strava_skip_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(
    F.data == "onboarding:continue",
    OnboardingStates.skipped_strava
)
async def handle_skipped_continue(callback: CallbackQuery, state: FSMContext):
    """Handle 'Continue' after skipping Strava."""
    await callback.answer()
    await show_usage_step(callback.message, state)


@router.callback_query(
    F.data == "onboarding:continue",
    OnboardingStates.offering_strava
)
async def handle_strava_connected_from_push(callback: CallbackQuery, state: FSMContext):
    """Handle 'Continue' from push notification when Strava connected during onboarding."""
    await callback.answer()
    await state.set_state(OnboardingStates.waiting_strava_callback)
    await show_usage_step(callback.message, state)


@router.callback_query(
    F.data == "onboarding:continue",
    OnboardingStates.waiting_strava_callback
)
async def handle_strava_connected_continue(callback: CallbackQuery, state: FSMContext):
    """Handle 'Continue' after Strava is connected."""
    await callback.answer()
    await show_usage_step(callback.message, state)


async def show_usage_step(message: Message, state: FSMContext):
    """Show usage instructions based on activity type."""
    data = await state.get_data()
    activity_type = data.get("activity_type", "hiking")

    usage_text = USAGE_RUNNING_TEXT if activity_type == "running" else USAGE_HIKING_TEXT

    await state.set_state(OnboardingStates.showing_usage)
    await message.edit_text(
        usage_text,
        reply_markup=get_finish_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "onboarding:finish")
async def handle_finish(callback: CallbackQuery, state: FSMContext):
    """Handle 'Finish' button - complete onboarding."""
    await callback.answer()

    telegram_id = str(callback.from_user.id)
    data = await state.get_data()
    activity_type = data.get("activity_type", "hiking")

    # Complete onboarding via API
    try:
        success = await api_client.complete_onboarding(telegram_id, activity_type)
        if success:
            logger.info(f"User {telegram_id} completed onboarding with {activity_type}")
        else:
            logger.warning(f"Failed to complete onboarding for user {telegram_id}")
    except Exception as e:
        logger.error(f"Error completing onboarding: {e}")

    await state.clear()
    await callback.message.edit_text(
        FINISH_TEXT,
        parse_mode="HTML"
    )


