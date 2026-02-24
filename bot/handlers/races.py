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
        "Выбери гонку:",
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
            f"<b>{race['name']}</b>\n\n"
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


async def _show_race_card(message, race: dict, dist: dict):
    """Show race distance card with action buttons."""
    grade = dist.get("grade")
    grade_emoji = GRADE_EMOJI.get(grade, "") if grade else ""

    lines = [
        f"<b>{race['name']}</b>",
        f"{dist['name']} {grade_emoji}",
        "",
    ]

    if dist.get("distance_km"):
        lines.append(f"\U0001f4cf {dist['distance_km']:.1f} км")
    if dist.get("elevation_gain_m"):
        lines.append(f"\u2b06 +{dist['elevation_gain_m']} м")
    if dist.get("start_altitude_m") and dist.get("finish_altitude_m"):
        lines.append(
            f"\U0001f3d4 {dist['start_altitude_m']}м \u2192 {dist['finish_altitude_m']}м"
        )

    if race.get("location"):
        lines.append(f"\U0001f4cd {race['location']}")

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
        text = _format_prediction_result(result, mode="hiking")
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
    await state.clear()
    await _do_predict(callback.message, race_id, distance_id, pace, mode="trail_run")


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
        await state.clear()
        await _do_predict(message, race_id, distance_id, pace, mode="trail_run")

    except (ValueError, IndexError):
        await message.answer(
            "\u274c Неверный формат. Введи темп как MM:SS (например, 6:30):"
        )


async def _do_predict(
    message, race_id: str, distance_id: str, pace: float, mode: str
):
    """Execute prediction and show result."""
    loading = await message.answer("\U0001f504 Рассчитываю прогноз...")

    result = await api_client.races.predict(
        race_id=race_id,
        distance_id=distance_id,
        flat_pace_min_km=pace,
        mode=mode,
    )

    if not result:
        await loading.edit_text("\u274c Не удалось рассчитать. Попробуй позже.")
        return

    text = _format_prediction_result(result, mode=mode)
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
        "<b>\U0001f50d Поиск в результатах</b>\n\n"
        "Введи имя (или часть имени) как при регистрации на гонку.\n"
        "Например: <i>Kuznetsov</i> или <i>Кузнецов</i>"
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
# STATS: show statistics for latest year
# =============================================================================


async def _show_stats(message, state: FSMContext, race_id: str, distance_id: str):
    """Show race statistics for latest available year."""
    data = await state.get_data()
    race_data = data.get("race_data")

    # Find latest year with results
    latest_year = None
    if race_data:
        for edition in sorted(
            race_data.get("editions", []), key=lambda e: e["year"], reverse=True
        ):
            if edition.get("has_results"):
                latest_year = edition["year"]
                break

    if not latest_year:
        await message.edit_text(
            "Нет результатов для этой гонки.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        return

    results = await api_client.races.get_results(race_id, latest_year)
    if not results:
        await message.edit_text(
            "Не удалось загрузить результаты.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        return

    # Find matching distance by name from race catalog
    dist_name = None
    if race_data:
        for d in race_data.get("distances", []):
            if d["id"] == distance_id:
                dist_name = d["name"]
                break

    dist_data = None
    for d in results:
        if dist_name and d["distance_name"].lower() == dist_name.lower():
            dist_data = d
            break
    # Fallback: first distance
    if not dist_data and results:
        dist_data = results[0]

    if not dist_data:
        await message.edit_text(
            "Нет результатов для этой дистанции.",
            reply_markup=race_back_keyboard(race_id, distance_id),
        )
        return

    text = _format_stats(dist_data, latest_year)
    await message.edit_text(
        text, reply_markup=race_back_keyboard(race_id, distance_id)
    )


# =============================================================================
# Formatters
# =============================================================================


def _format_prediction_result(result: dict, mode: str = "trail_run") -> str:
    """Format prediction API response for display."""
    lines = [
        f"<b>\U0001f52e Прогноз: {result['race_name']}</b>",
        f"{result['distance_name']}",
        "",
    ]

    if result.get("distance_km"):
        lines.append(f"\U0001f4cf {result['distance_km']:.1f} км")
    if result.get("elevation_gain_m"):
        lines.append(f"\u2b06 +{result['elevation_gain_m']} м")

    lines.append("")
    lines.append("\u2501" * 24)
    lines.append("")

    if mode == "trail_run":
        lines.append(
            f"<b>\U0001f3c3 Прогноз (темп {format_pace(result['flat_pace_used'])}/км):</b>"
        )
    else:
        lines.append("<b>\U0001f97e Прогноз (пешком):</b>")

    lines.append(f"  \u23f1 <b>{result['predicted_time']}</b>")

    # Show a few key methods
    if result.get("all_methods"):
        lines.append("")
        shown_methods = _select_display_methods(result["all_methods"], mode)
        for m in shown_methods:
            lines.append(f"  {m['name']}: {m['time_formatted']}")

    # Comparison with past results
    if result.get("comparison_year"):
        lines.append("")
        lines.append("\u2501" * 24)
        lines.append("")
        lines.append(
            f"<b>\U0001f4ca Сравнение с {result['comparison_year']}:</b>"
        )
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

    return "\n".join(lines)


def _select_display_methods(all_methods: list[dict], mode: str) -> list[dict]:
    """Select most relevant methods for display."""
    if mode == "hiking":
        # Show tobler and naismith
        display_names = {"tobler", "naismith"}
    else:
        # Show main GAP methods
        display_names = {
            "all_run_strava",
            "all_run_minetti",
            "all_run_strava_minetti",
        }

    METHOD_LABELS = {
        "all_run_strava": "Strava GAP",
        "all_run_minetti": "Minetti GAP",
        "all_run_strava_minetti": "Strava+Minetti",
        "tobler": "Tobler",
        "naismith": "Naismith",
    }

    result = []
    for m in all_methods:
        if m["name"] in display_names:
            label = METHOD_LABELS.get(m["name"], m["name"])
            result.append({"name": label, "time_formatted": m["time_formatted"]})
    return result


def _format_search_results(query: str, results: list[dict]) -> str:
    """Format search results across years."""
    found_any = any(r.get("result") for r in results)

    if not found_any:
        return (
            f'<b>\U0001f50d Поиск: "{query}"</b>\n\n'
            "Ничего не найдено. Попробуй другое написание имени."
        )

    lines = [f'<b>\U0001f50d Результаты: "{query}"</b>', ""]

    for entry in results:
        year = entry["year"]
        r = entry.get("result")
        if r:
            lines.append(
                f"<b>{year}:</b> {r['time_formatted']} "
                f"({r['place']}-е место)"
            )
            details = []
            if r.get("category"):
                details.append(r["category"])
            if r.get("club"):
                details.append(r["club"])
            if details:
                lines.append(f"  {' | '.join(details)}")
        else:
            lines.append(f"<b>{year}:</b> не участвовал")

    return "\n".join(lines)


def _format_stats(dist_data: dict, year: int) -> str:
    """Format distance statistics."""
    stats = dist_data.get("stats", {})
    dist_name = dist_data.get("distance_name", "")

    lines = [
        f"<b>\U0001f4ca Статистика {year}: {dist_name}</b>",
        "",
        f"\U0001f465 Финишёров: {stats.get('finishers', 0)}",
        f"\U0001f947 Лучший: {stats.get('best_time', '-')}",
        f"\U0001f4ca Медиана: {stats.get('median_time', '-')}",
        f"\U0001f3c5 Топ-25%: {stats.get('p25_time', '-')}",
        f"\U0001f3c5 Топ-75%: {stats.get('p75_time', '-')}",
        f"\U0001f6a9 Последний: {stats.get('worst_time', '-')}",
    ]

    # Time distribution
    buckets = stats.get("time_buckets", [])
    if buckets:
        lines.append("")
        lines.append("<b>Распределение:</b>")
        for b in buckets:
            bar_len = max(1, int(b["percent"] / 5))
            bar = "\u2588" * bar_len
            label = b["label"].replace("<", "&lt;").replace(">", "&gt;")
            lines.append(
                f"  {label}: {bar} {b['count']} ({b['percent']:.0f}%)"
            )

    return "\n".join(lines)
