"""
Race Keyboards

Inline keyboards for race browsing, prediction, and search flow.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


GRADE_EMOJI = {
    "green": "\U0001f7e2",
    "yellow": "\U0001f7e1",
    "orange": "\U0001f7e0",
    "red": "\U0001f534",
}


def races_calendar_keyboard(races: list[dict]) -> InlineKeyboardMarkup:
    """Build keyboard with list of races.

    Each race is a button: "Alpine Race — 1 мар"
    """
    rows = []
    for race in races:
        name = race["name"]
        next_date = race.get("next_date", "")
        # Format date nicely: "2026-03-01" → "1 мар"
        date_label = _format_short_date(next_date) if next_date else ""
        label = f"{name} — {date_label}" if date_label else name
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"race:{race['id']}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def race_distances_keyboard(race_id: str, distances: list[dict]) -> InlineKeyboardMarkup:
    """Build keyboard for distance selection (if race has multiple distances)."""
    rows = []
    for dist in distances:
        label_parts = [dist["name"]]
        if dist.get("distance_km"):
            label_parts.append(f"{dist['distance_km']:.0f}km")
        if dist.get("elevation_gain_m"):
            label_parts.append(f"+{dist['elevation_gain_m']}m")
        grade = dist.get("grade")
        if grade:
            label_parts.append(GRADE_EMOJI.get(grade, ""))

        label = " ".join(label_parts)
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"race_dist:{race_id}:{dist['id']}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="\u2190 \u041d\u0430\u0437\u0430\u0434", callback_data="race:back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def race_card_keyboard(
    race_id: str,
    distance_id: str,
    has_gpx: bool = False,
    has_results: bool = False,
) -> InlineKeyboardMarkup:
    """Build keyboard for race card actions."""
    rows = []

    if has_gpx:
        rows.append(
            [
                InlineKeyboardButton(
                    text="\U0001f3c3 \u0420\u0430\u0441\u0441\u0447\u0438\u0442\u0430\u0442\u044c \u043f\u0440\u043e\u0433\u043d\u043e\u0437",
                    callback_data=f"race_act:{race_id}:{distance_id}:predict",
                )
            ]
        )

    if has_results:
        rows.append(
            [
                InlineKeyboardButton(
                    text="\U0001f50d \u041f\u043e\u0438\u0441\u043a",
                    callback_data=f"race_act:{race_id}:{distance_id}:search",
                ),
                InlineKeyboardButton(
                    text="\U0001f4ca \u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430",
                    callback_data=f"race_act:{race_id}:{distance_id}:stats",
                ),
            ]
        )

    rows.append(
        [InlineKeyboardButton(text="\u2190 \u041d\u0430\u0437\u0430\u0434", callback_data="race:back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def race_predict_mode_keyboard(
    race_id: str, distance_id: str
) -> InlineKeyboardMarkup:
    """Choose prediction mode: running or hiking."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001f3c3 \u0411\u0435\u0433\u043e\u043c",
                    callback_data=f"race_mode:{race_id}:{distance_id}:trail_run",
                ),
                InlineKeyboardButton(
                    text="\U0001f97e \u041f\u0435\u0448\u043a\u043e\u043c",
                    callback_data=f"race_mode:{race_id}:{distance_id}:hiking",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="\u2190 \u041d\u0430\u0437\u0430\u0434",
                    callback_data=f"race_dist:{race_id}:{distance_id}",
                )
            ],
        ]
    )


def race_pace_keyboard(
    race_id: str, distance_id: str, strava_pace: float | None = None
) -> InlineKeyboardMarkup:
    """Pace selection keyboard for race prediction."""
    rows = []

    if strava_pace:
        pace_min = int(strava_pace)
        pace_sec = int((strava_pace - pace_min) * 60)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"\U0001f464 \u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c {pace_min}:{pace_sec:02d}/\u043a\u043c",
                    callback_data=f"race_pace:{race_id}:{distance_id}:{strava_pace}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="5:00/\u043a\u043c", callback_data=f"race_pace:{race_id}:{distance_id}:5.0"
            ),
            InlineKeyboardButton(
                text="5:30/\u043a\u043c", callback_data=f"race_pace:{race_id}:{distance_id}:5.5"
            ),
            InlineKeyboardButton(
                text="6:00/\u043a\u043c", callback_data=f"race_pace:{race_id}:{distance_id}:6.0"
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="6:30/\u043a\u043c", callback_data=f"race_pace:{race_id}:{distance_id}:6.5"
            ),
            InlineKeyboardButton(
                text="7:00/\u043a\u043c", callback_data=f"race_pace:{race_id}:{distance_id}:7.0"
            ),
            InlineKeyboardButton(
                text="8:00/\u043a\u043c", callback_data=f"race_pace:{race_id}:{distance_id}:8.0"
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="\u0412\u0432\u0435\u0441\u0442\u0438 \u0432\u0440\u0443\u0447\u043d\u0443\u044e",
                callback_data=f"race_pace:{race_id}:{distance_id}:custom",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def race_search_result_keyboard(
    race_id: str, distance_id: str
) -> InlineKeyboardMarkup:
    """Keyboard shown after auto-search results: manual search + back."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001f50d \u0418\u0441\u043a\u0430\u0442\u044c \u0434\u0440\u0443\u0433\u043e\u0435 \u0438\u043c\u044f",
                    callback_data=f"race_act:{race_id}:{distance_id}:srch_man",
                )
            ],
            [
                InlineKeyboardButton(
                    text="\u2190 \u041a \u0433\u043e\u043d\u043a\u0435",
                    callback_data=f"race_dist:{race_id}:{distance_id}",
                )
            ],
        ]
    )


def race_stats_year_keyboard(
    race_id: str, distance_id: str, years: list[int]
) -> InlineKeyboardMarkup:
    """Year selection keyboard for stats (individual years + all years)."""
    rows = []
    # Individual year buttons (2-3 per row, newest first)
    sorted_years = sorted(years, reverse=True)
    row: list[InlineKeyboardButton] = []
    for y in sorted_years:
        row.append(
            InlineKeyboardButton(
                text=str(y),
                callback_data=f"race_stats:{race_id}:{distance_id}:{y}",
            )
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # "All years" button
    rows.append(
        [
            InlineKeyboardButton(
                text="\U0001f4ca \u0412\u0441\u0435 \u0433\u043e\u0434\u044b",
                callback_data=f"race_stats:{race_id}:{distance_id}:all",
            )
        ]
    )
    # Back
    rows.append(
        [
            InlineKeyboardButton(
                text="\u2190 \u041a \u0433\u043e\u043d\u043a\u0435",
                callback_data=f"race_dist:{race_id}:{distance_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def race_back_keyboard(race_id: str, distance_id: str) -> InlineKeyboardMarkup:
    """Simple back button to race card."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\u2190 \u041a \u0433\u043e\u043d\u043a\u0435",
                    callback_data=f"race_dist:{race_id}:{distance_id}",
                )
            ]
        ]
    )


def _format_short_date(date_str: str) -> str:
    """Format 'YYYY-MM-DD' to short Russian: '1 мар'."""
    months = {
        1: "\u044f\u043d\u0432",
        2: "\u0444\u0435\u0432",
        3: "\u043c\u0430\u0440",
        4: "\u0430\u043f\u0440",
        5: "\u043c\u0430\u0439",
        6: "\u0438\u044e\u043d",
        7: "\u0438\u044e\u043b",
        8: "\u0430\u0432\u0433",
        9: "\u0441\u0435\u043d",
        10: "\u043e\u043a\u0442",
        11: "\u043d\u043e\u044f",
        12: "\u0434\u0435\u043a",
    }
    try:
        parts = date_str.split("-")
        month = int(parts[1])
        day = int(parts[2])
        return f"{day} {months.get(month, '')}"
    except (IndexError, ValueError):
        return date_str
