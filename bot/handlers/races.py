"""
Race Handlers

Handles /races command and race browsing, prediction, search flow.
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.races import RaceStates
from keyboards.races import (
    races_calendar_keyboard,
    race_distances_keyboard,
    race_card_keyboard,
    race_predict_mode_keyboard,
    race_pace_keyboard,
    race_stats_year_keyboard,
    race_back_keyboard,
)
from services.api_client import api_client
from utils.formatters import format_pace

logger = logging.getLogger(__name__)
router = Router()


# =============================================================================
# Grade emoji mapping
# =============================================================================

GRADE_EMOJI = {
    "green": "\U0001f7e2",
    "yellow": "\U0001f7e1",
    "orange": "\U0001f7e0",
    "red": "\U0001f534",
}


# =============================================================================
# /races command — entry point
# =============================================================================


@router.message(Command("races"))
async def cmd_races(message: Message, state: FSMContext):
    """Handle /races command — show race calendar."""
    await state.clear()

    races = await api_client.races.list_races()
    if not races:
        await message.answer("Не удалось загрузить календарь гонок.")
        return

    # Filter to races with at least one distance with data
    valid_races = [r for r in races if r.get("distances")]
    if not valid_races:
        await message.answer("Пока нет доступных гонок.")
        return

    await message.answer(
        "<b>\U0001f3d4 Горные гонки Алматы 2026</b>\n\n"
        "Выбери гонку, чтобы рассчитать прогноз прохождения, "
        "найти свои результаты предыдущих гонок и посмотреть аналитику.",
        reply_markup=races_calendar_keyboard(valid_races),
    )


# =============================================================================
# Race selection → show distances or card
# =============================================================================


@router.callback_query(F.data.startswith("race:"))
async def handle_race_selection(callback: CallbackQuery, state: FSMContext):
    """Handle race selection from calendar."""
    await callback.answer()
    race_id = callback.data.split(":")[1]

    if race_id == "back":
        # Back to calendar
        races = await api_client.races.list_races()
        if not races:
            return
        valid_races = [r for r in races if r.get("distances")]
        await callback.message.edit_text(
            "<b>\U0001f3d4 Горные гонки Алматы 2026</b>\n\n"
            "Выбери гонку:",
            reply_markup=races_calendar_keyboard(valid_races),
        )
        return

    race = await api_client.races.get_race(race_id)
    if not race:
        await callback.message.edit_text("Гонка не найдена.")
        return

    await state.update_data(race_id=race_id, race_data=race)

    distances = race.get("distances", [])
    if len(distances) == 1:
        # Single distance — go directly to card
        dist = distances[0]
        await _show_race_card(callback.message, race, dist)
        await state.update_data(distance_id=dist["id"])
    else:
        # Multiple distances — ask user to choose
        await callback.message.edit_text(
            f"<b>Гонка:</b> {race['name']}\n\n"
            "Выбери дистанцию:",
            reply_markup=race_distances_keyboard(race_id, distances),
        )


# =============================================================================
# Distance selection → show card
# =============================================================================


@router.callback_query(F.data.startswith("race_dist:"))
async def handle_distance_selection(callback: CallbackQuery, state: FSMContext):
    """Handle distance selection or back-to-card navigation."""
    await callback.answer()
    parts = callback.data.split(":")
    race_id = parts[1]
    distance_id = parts[2]

    race = await api_client.races.get_race(race_id)
    if not race:
        await callback.message.edit_text("Гонка не найдена.")
        return

    dist = next((d for d in race.get("distances", []) if d["id"] == distance_id), None)
    if not dist:
        await callback.message.edit_text("Дистанция не найдена.")
        return

    await state.update_data(race_id=race_id, race_data=race, distance_id=distance_id)
    await _show_race_card(callback.message, race, dist)


GRADE_LABEL = {
    "green": "Доступно начинающим",
    "yellow": "Средний уровень",
    "orange": "Продвинутый",
    "red": "Экспертный",
}


async def _show_race_card(message, race: dict, dist: dict):
    """Show race distance card with action buttons."""
    grade = dist.get("grade")
    grade_emoji = GRADE_EMOJI.get(grade, "") if grade else ""
    grade_label = GRADE_LABEL.get(grade, "") if grade else ""

    lines = [
        f"<b>Гонка:</b> {race['name']}",
        f"<b>Дистанция:</b> {dist['name']}",
    ]

    if grade:
        lines.append(f"<b>Сложность:</b> {grade_label} {grade_emoji}")

    if race.get("location"):
        lines.append(f"<b>Локация:</b> {race['location']}")

    lines.append("")
    lines.append("<b>Маршрут:</b>")

    if dist.get("distance_km"):
        lines.append(f"  {dist['distance_km']:.1f} км")
    if dist.get("elevation_gain_m"):
        lines.append(f"  Подъём: +{dist['elevation_gain_m']} м")
    if dist.get("start_altitude_m") and dist.get("finish_altitude_m"):
        lines.append(
            f"  Высота: {dist['start_altitude_m']}м \u2192 {dist['finish_altitude_m']}м"
        )

    has_results = any(e.get("has_results") for e in race.get("editions", []))

    text = "\n".join(lines)
    keyboard = race_card_keyboard(
        race_id=race["id"],
        distance_id=dist["id"],
        has_gpx=dist.get("has_gpx", False),
        has_results=has_results,
    )

    await message.edit_text(text, reply_markup=keyboard)


# =============================================================================
# Actions: predict, search, stats
# =============================================================================


@router.callback_query(F.data.startswith("race_act:"))
async def handle_race_action(callback: CallbackQuery, state: FSMContext):
    """Handle race card action buttons."""
    await callback.answer()
    parts = callback.data.split(":")
    race_id = parts[1]
    distance_id = parts[2]
    action = parts[3]

    await state.update_data(race_id=race_id, distance_id=distance_id)

    if action == "predict":
        await _start_predict(callback.message, state, race_id, distance_id)
    elif action == "search":
        await _start_search(callback.message, state, race_id, distance_id)
    elif action == "stats":
        await _show_stats(callback.message, state, race_id, distance_id)


# =============================================================================
# PREDICT: mode → pace → result
# =============================================================================


async def _start_predict(message, state: FSMContext, race_id: str, distance_id: str):
    """Ask user: running or hiking?"""
    await message.edit_text(
        "<b>\U0001f52e Прогноз</b>\n\n"
        "Как ты планируешь проходить дистанцию?",
        reply_markup=race_predict_mode_keyboard(race_id, distance_id),
    )


@router.callback_query(F.data.startswith("race_mode:"))
async def handle_predict_mode(callback: CallbackQuery, state: FSMContext):
    """Handle running/hiking mode selection."""
    await callback.answer()
    parts = callback.data.split(":")
    race_id = parts[1]
    distance_id = parts[2]
    mode = parts[3]  # "trail_run" or "hiking"

    await state.update_data(
        race_id=race_id, distance_id=distance_id, predict_mode=mode
    )

    if mode == "hiking":
        # Hiking — predict immediately with default speed (5 km/h → ~12 min/km)
        data = await state.get_data()
        race_data = data.get("race_data")
        dist_data = _find_dist_data(race_data, distance_id)

        await callback.message.edit_text("\U0001f504 Рассчитываю...")
        result = await api_client.races.predict(
            race_id=race_id,
            distance_id=distance_id,
            flat_pace_min_km=12.0,  # ~5 km/h walking pace
            mode="hiking",
        )
        if not result:
            await callback.message.edit_text("Не удалось рассчитать прогноз.")
            return
        text = _format_prediction_result(
            result, mode="hiking", race_data=race_data, dist_data=dist_data,
        )
        await callback.message.edit_text(
            text, reply_markup=race_back_keyboard(race_id, distance_id)
        )
        return

    # Trail run — ask for pace
    telegram_id = str(callback.from_user.id)

    # Check Strava for run profile
    strava_pace = None
    strava_status = await api_client.get_strava_status(telegram_id)
    if strava_status and strava_status.connected:
        run_profile = await api_client.get_run_profile(telegram_id)
        if run_profile and run_profile.get("avg_flat_pace_min_km"):
            strava_pace = run_profile["avg_flat_pace_min_km"]

    await state.update_data(strava_pace=strava_pace)

    if strava_pace:
        text = (
            "<b>\U0001f3c3 Какой у тебя темп на ровном?</b>\n\n"
            f"<blockquote>\U0001f464 Твой темп из Strava: {format_pace(strava_pace)}/км</blockquote>\n\n"
            "Используй темп из Strava или выбери другой."
        )
    else:
        text = (
            "<b>\U0001f3c3 Какой у тебя темп на ровном?</b>\n\n"
            "Выбери свой примерный темп бега на плоской поверхности."
        )

    await state.set_state(RaceStates.waiting_for_pace)
    await callback.message.edit_text(
        text,
        reply_markup=race_pace_keyboard(race_id, distance_id, strava_pace),
    )


@router.callback_query(F.data.startswith("race_pace:"))
async def handle_pace_selection(callback: CallbackQuery, state: FSMContext):
    """Handle pace button selection."""
    await callback.answer()
    parts = callback.data.split(":")
    race_id = parts[1]
    distance_id = parts[2]
    pace_str = parts[3]

    if pace_str == "custom":
        await state.update_data(waiting_custom_pace=True)
        await callback.message.edit_text(
            "Введи свой темп в формате MM:SS (например, 6:30):"
        )
        return

    pace = float(pace_str)
    data = await state.get_data()
    race_data = data.get("race_data")
    dist_data = _find_dist_data(race_data, distance_id)
    strava_pace = data.get("strava_pace")
    await state.clear()
    await _do_predict(
        callback.message, race_id, distance_id, pace, mode="trail_run",
        race_data=race_data, dist_data=dist_data, strava_pace=strava_pace,
    )


@router.message(RaceStates.waiting_for_pace)
async def handle_custom_pace_input(message: Message, state: FSMContext):
    """Handle custom pace text input."""
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
                "\u274c Темп должен быть от 3:00 до 15:00/км. Попробуй ещё раз:"
            )
            return

        race_id = data["race_id"]
        distance_id = data["distance_id"]
        race_data = data.get("race_data")
        dist_data = _find_dist_data(race_data, distance_id)
        strava_pace = data.get("strava_pace")
        await state.clear()
        await _do_predict(
            message, race_id, distance_id, pace, mode="trail_run",
            race_data=race_data, dist_data=dist_data, strava_pace=strava_pace,
        )

    except (ValueError, IndexError):
        await message.answer(
            "\u274c Неверный формат. Введи темп как MM:SS (например, 6:30):"
        )


async def _do_predict(
    message,
    race_id: str,
    distance_id: str,
    pace: float,
    mode: str,
    race_data: dict = None,
    dist_data: dict = None,
    strava_pace: float = None,
):
    """Execute prediction and show result."""
    loading = await message.answer("\U0001f504 Рассчитываю прогноз...")

    # Main prediction with selected pace
    result = await api_client.races.predict(
        race_id=race_id,
        distance_id=distance_id,
        flat_pace_min_km=pace,
        mode=mode,
    )

    if not result:
        await loading.edit_text("\u274c Не удалось рассчитать. Попробуй позже.")
        return

    # Dual prediction with Strava pace (if available and different from selected)
    result_strava = None
    if strava_pace and abs(strava_pace - pace) > 0.01:
        result_strava = await api_client.races.predict(
            race_id=race_id,
            distance_id=distance_id,
            flat_pace_min_km=strava_pace,
            mode=mode,
        )

    text = _format_prediction_result(
        result,
        mode=mode,
        race_data=race_data,
        dist_data=dist_data,
        result_strava=result_strava,
        strava_pace=strava_pace,
    )
    await loading.edit_text(
        text, reply_markup=race_back_keyboard(race_id, distance_id)
    )


# =============================================================================
# SEARCH: enter name → show results across years
# =============================================================================


async def _start_search(message, state: FSMContext, race_id: str, distance_id: str):
    """Ask user to enter name for search."""
    await state.update_data(
        race_id=race_id, distance_id=distance_id, waiting_custom_pace=False
    )
    await state.set_state(RaceStates.waiting_for_name)
    await message.edit_text(
        "<b>\U0001f50d Поиск в результатах гонок</b>\n\n"
        "Введи имя и фамилию как при регистрации на гонку.\n"
        "Например: <i>Artem Kuznetsov</i> или <i>Артём Кузнецов</i>"
    )


@router.message(RaceStates.waiting_for_name)
async def handle_name_input(message: Message, state: FSMContext):
    """Handle name input for search."""
    data = await state.get_data()
    race_id = data.get("race_id")
    distance_id = data.get("distance_id")

    if not race_id or not distance_id:
        await state.clear()
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Введи минимум 2 символа.")
        return

    # Require at least 2 words (name + surname) to avoid ambiguous results
    if len(name.split()) < 2:
        await message.answer(
            "Введи имя и фамилию, чтобы найти точный результат.\n"
            "Например: <i>Artem Kuznetsov</i>"
        )
        return

    results = await api_client.races.search(
        race_id=race_id, name=name, distance_id=distance_id
    )

    if results is None:
        await message.answer(
            "\u274c Ошибка при поиске. Попробуй позже.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        await state.clear()
        return

    text = _format_search_results(name, results)
    await message.answer(
        text, reply_markup=race_back_keyboard(race_id, distance_id)
    )
    await state.clear()


# =============================================================================
# STATS: year selection → analytics
# =============================================================================


async def _show_stats(message, state: FSMContext, race_id: str, distance_id: str):
    """Show year selection for statistics."""
    data = await state.get_data()
    race_data = data.get("race_data")

    # Collect years with results
    years_with_results = []
    if race_data:
        for edition in race_data.get("editions", []):
            if edition.get("has_results"):
                years_with_results.append(edition["year"])

    if not years_with_results:
        await message.edit_text(
            "Нет результатов для этой гонки.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        return

    # Get race and distance names for the header
    race_name = race_data.get("name", "") if race_data else ""
    dist_data = _find_dist_data(race_data, distance_id)
    dist_name = dist_data.get("name", "") if dist_data else ""

    text = (
        f"<b>Аналитика</b>\n\n"
        f"<b>Гонка:</b> {race_name}\n"
        f"<b>Дистанция:</b> {dist_name}\n\n"
        "Выбери год:"
    )

    await message.edit_text(
        text,
        reply_markup=race_stats_year_keyboard(race_id, distance_id, years_with_results),
    )


@router.callback_query(F.data.startswith("race_stats:"))
async def handle_stats_year(callback: CallbackQuery, state: FSMContext):
    """Handle year selection for stats."""
    await callback.answer()
    parts = callback.data.split(":")
    race_id = parts[1]
    distance_id = parts[2]
    year_str = parts[3]  # "2023", "2024", "2025", or "all"

    data = await state.get_data()
    race_data = data.get("race_data")
    if not race_data:
        race_data = await api_client.races.get_race(race_id)
        if race_data:
            await state.update_data(race_data=race_data)

    race_name = race_data.get("name", "") if race_data else ""
    dist_info = _find_dist_data(race_data, distance_id)
    dist_name = dist_info.get("name", "") if dist_info else ""

    if year_str == "all":
        # Load all years and show combined summary
        years_with_results = []
        if race_data:
            for edition in race_data.get("editions", []):
                if edition.get("has_results"):
                    years_with_results.append(edition["year"])

        all_year_stats = []
        for year in sorted(years_with_results):
            results = await api_client.races.get_results(race_id, year)
            if not results:
                continue
            dist_data = _find_dist_for_stats(results, dist_name)
            if dist_data:
                all_year_stats.append((year, dist_data))

        if not all_year_stats:
            await callback.message.edit_text(
                "Нет данных.",
                reply_markup=race_back_keyboard(race_id, distance_id),
            )
            return

        text = _format_stats_all_years(all_year_stats, race_name, dist_name)
        await callback.message.edit_text(
            text,
            reply_markup=race_stats_year_keyboard(
                race_id, distance_id,
                [y for y, _ in all_year_stats],
            ),
        )
        return

    # Single year
    year = int(year_str)
    results = await api_client.races.get_results(race_id, year)
    if not results:
        await callback.message.edit_text(
            "Не удалось загрузить результаты.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        return

    dist_data = _find_dist_for_stats(results, dist_name)
    if not dist_data:
        await callback.message.edit_text(
            "Нет результатов для этой дистанции.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        return

    text = _format_stats(dist_data, year, race_name, dist_name)
    await callback.message.edit_text(
        text,
        reply_markup=race_stats_year_keyboard(
            race_id, distance_id,
            [e["year"] for e in race_data.get("editions", []) if e.get("has_results")]
            if race_data else [year],
        ),
    )


# =============================================================================
# Helpers
# =============================================================================


def _find_dist_data(race_data: dict, distance_id: str) -> dict | None:
    """Find distance dict in race_data by id."""
    if not race_data:
        return None
    for d in race_data.get("distances", []):
        if d["id"] == distance_id:
            return d
    return None


def _find_dist_for_stats(results: list[dict], dist_name: str) -> dict | None:
    """Find matching distance in API results by name."""
    for d in results:
        if dist_name and d["distance_name"].lower() == dist_name.lower():
            return d
    # Fallback: first distance
    return results[0] if results else None


# =============================================================================
# Formatters
# =============================================================================

# Method labels and dot-padding (tuned for Telegram proportional font)
METHOD_LABELS = {
    "all_run_strava": ("Strava GAP", 10),
    "all_run_minetti": ("Minetti GAP", 8),
    "all_run_strava_minetti": ("Strava+Minetti", 3),
    "tobler": ("Tobler", 14),
    "naismith": ("Naismith", 10),
}


def _format_methods(all_methods: list[dict], mode: str) -> list[str]:
    """Format GAP/hiking methods with dot-padding."""
    if mode == "hiking":
        display_names = ["tobler", "naismith"]
    else:
        display_names = [
            "all_run_strava",
            "all_run_minetti",
            "all_run_strava_minetti",
        ]

    lines = []
    for m in all_methods:
        if m["name"] in display_names:
            label, dots = METHOD_LABELS.get(m["name"], (m["name"], 3))
            lines.append(f"  {label}{'.' * dots}{m['time_formatted']}")
    return lines


def _format_card_header(
    result: dict, race_data: dict = None, dist_data: dict = None,
) -> list[str]:
    """Format race card header (name, distance, grade, location, route)."""
    lines = [
        f"<b>Гонка:</b> {result['race_name']}",
        f"<b>Дистанция:</b> {result['distance_name']}",
    ]

    # Grade from dist_data (not in API response)
    if dist_data:
        grade = dist_data.get("grade")
        if grade:
            emoji = GRADE_EMOJI.get(grade, "")
            label = GRADE_LABEL.get(grade, "")
            lines.append(f"<b>Сложность:</b> {label} {emoji}")

    # Location from race_data
    if race_data and race_data.get("location"):
        lines.append(f"<b>Локация:</b> {race_data['location']}")

    # Route details
    lines.append("")
    lines.append("<b>Маршрут:</b>")
    if result.get("distance_km"):
        lines.append(f"  {result['distance_km']:.1f} км")
    if result.get("elevation_gain_m"):
        lines.append(f"  Подъём: +{result['elevation_gain_m']} м")
    if dist_data:
        start_alt = dist_data.get("start_altitude_m")
        finish_alt = dist_data.get("finish_altitude_m")
        if start_alt and finish_alt:
            lines.append(f"  Высота: {start_alt}м \u2192 {finish_alt}м")

    return lines


def _format_comparison(result: dict) -> list[str]:
    """Format comparison with past results."""
    if not result.get("comparison_year"):
        return []

    lines = [
        "",
        "\u2501" * 24,
        "",
        f"<b>\U0001f4ca Сравнение с {result['comparison_year']}:</b>",
    ]

    if result.get("estimated_place") and result.get("total_finishers"):
        lines.append(
            f"  \U0001f3c6 ~{result['estimated_place']}-е место "
            f"из {result['total_finishers']}"
        )
    if result.get("percentile") is not None:
        pct = result["percentile"]
        lines.append(f"  \U0001f4c8 Быстрее {pct:.0f}% участников")

    if result.get("stats"):
        stats = result["stats"]
        lines.append(f"  \U0001f947 Лучший: {stats['best_time']}")
        lines.append(f"  \U0001f4ca Медиана: {stats['median_time']}")

    return lines


def _format_prediction_result(
    result: dict,
    mode: str = "trail_run",
    race_data: dict = None,
    dist_data: dict = None,
    result_strava: dict = None,
    strava_pace: float = None,
) -> str:
    """Format prediction API response for display.

    Args:
        result: Main prediction result (with selected/manual pace)
        mode: "trail_run" or "hiking"
        race_data: Race dict from catalog (for location etc.)
        dist_data: Distance dict from catalog (for grade, altitude)
        result_strava: Optional second prediction result (Strava pace)
        strava_pace: Strava pace value (for label)
    """
    # Card header
    lines = [
        "<b>Персональный прогноз:</b>",
    ]
    lines.extend(_format_card_header(result, race_data, dist_data))

    lines.append("")
    lines.append("\u2501" * 24)

    if mode == "trail_run":
        # Trail run with dual results
        if result_strava and strava_pace:
            # Strava pace results
            lines.append("")
            lines.append(
                f"На основе среднего темпа на плоском из Strava - "
                f"{format_pace(strava_pace)}/км"
            )
            lines.extend(_format_methods(result_strava["all_methods"], mode))

            # Selected pace results
            lines.append("")
            lines.append(
                f"На основе выбранного темпа - "
                f"{format_pace(result['flat_pace_used'])}/км"
            )
            lines.extend(_format_methods(result["all_methods"], mode))
        elif strava_pace and abs(strava_pace - result["flat_pace_used"]) < 0.01:
            # User selected their Strava pace — show single block with Strava label
            lines.append("")
            lines.append(
                f"На основе среднего темпа на плоском из Strava - "
                f"{format_pace(strava_pace)}/км"
            )
            lines.extend(_format_methods(result["all_methods"], mode))
        else:
            # No Strava — single block with selected pace
            lines.append("")
            lines.append(
                f"На основе выбранного темпа - "
                f"{format_pace(result['flat_pace_used'])}/км"
            )
            lines.extend(_format_methods(result["all_methods"], mode))
    else:
        # Hiking mode
        lines.append("")
        lines.append("\U0001f97e Прогноз (пешком):")
        lines.extend(_format_methods(result["all_methods"], mode))

    # Comparison with past results
    lines.extend(_format_comparison(result))

    return "\n".join(lines)


def _format_search_results(query: str, results: list[dict]) -> str:
    """Format search results across years."""
    found_any = any(r.get("result") for r in results)

    if not found_any:
        return (
            f'<b>\U0001f50d Поиск: "{query}"</b>\n\n'
            "Ничего не найдено. Попробуй другое написание имени."
        )

    # Get the actual name from first found result
    found_name = query
    for entry in results:
        r = entry.get("result")
        if r:
            found_name = r["name"]
            break

    lines = [f'<b>\U0001f50d Результаты для {found_name}</b>', ""]

    for entry in results:
        year = entry["year"]
        r = entry.get("result")
        if r:
            parts = [f"<b>{year}:</b> {r['time_formatted']}"]
            parts.append(f"{r['place']}-е место")
            if r.get("club"):
                parts.append(r["club"])
            lines.append(" / ".join(parts))
        else:
            lines.append(f"<b>{year}:</b> не участвовал")

    return "\n".join(lines)


def _format_stats(
    dist_data: dict, year: int, race_name: str = "", dist_name: str = "",
) -> str:
    """Format distance statistics for a single year."""
    stats = dist_data.get("stats", {})

    lines = [
        f"<b>Аналитика за {year} год</b>",
        "",
        f"<b>Гонка:</b> {race_name}",
        f"<b>Дистанция:</b> {dist_name}",
        "",
        f"Финишёров: {stats.get('finishers', 0)}",
        f"Лучший: {stats.get('best_time', '-')}",
        f"Медиана: {stats.get('median_time', '-')}",
        f"Топ-25%: {stats.get('p25_time', '-')}",
        f"Топ-75%: {stats.get('p75_time', '-')}",
    ]

    lines.extend(_format_buckets(stats.get("time_buckets", [])))

    return "\n".join(lines)


def _format_stats_all_years(
    all_year_stats: list[tuple[int, dict]],
    race_name: str,
    dist_name: str,
) -> str:
    """Format aggregated stats summary across all years."""
    lines = [
        "<b>Аналитика за все годы</b>",
        "",
        f"<b>Гонка:</b> {race_name}",
        f"<b>Дистанция:</b> {dist_name}",
    ]

    for year, dist_data in all_year_stats:
        stats = dist_data.get("stats", {})
        lines.append("")
        lines.append(f"<b>{year}</b>")
        lines.append(
            f"  Финишёров: {stats.get('finishers', 0)} / "
            f"Лучший: {stats.get('best_time', '-')} / "
            f"Медиана: {stats.get('median_time', '-')}"
        )

    return "\n".join(lines)


def _format_buckets(buckets: list[dict]) -> list[str]:
    """Format time distribution buckets."""
    if not buckets:
        return []

    lines = [
        "",
        "<b>Распределение по времени финиша:</b>",
    ]
    for b in buckets:
        label = b["label"]
        # Replace < and > with readable words and escape for HTML
        label = label.replace("< ", "меньше ")
        label = label.replace("> ", "больше ")
        label = label.replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"  {label} — {b['count']} чел. ({b['percent']:.0f}%)")

    return lines
