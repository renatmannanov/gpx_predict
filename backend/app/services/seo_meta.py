"""Server-side OG/meta tags for SPA pages.

Messenger and search bots don't execute JS, so the SPA fallback in main.py
injects page-specific <title> and Open Graph tags into index.html for
shareable routes: /races/{id} and /runners/{id}. All other routes are served
with the static defaults baked into index.html.
"""

from __future__ import annotations

import html
import logging
import re

from sqlalchemy.orm import Session

from app.features.races.disciplines import is_running_distance
from app.features.races.repository import RaceRepository

logger = logging.getLogger(__name__)

_RACE_PATH_RE = re.compile(r"^races/([A-Za-z0-9_\-]+)/?$")
_RUNNER_PATH_RE = re.compile(r"^runners/(\d+)/?$")

_TITLE_RE = re.compile(r"<title>.*?</title>", re.DOTALL)
# Default meta block in index.html, marked for replacement (see frontend/index.html)
_OG_BLOCK_RE = re.compile(r"<!-- og:start[^>]*-->.*?<!-- og:end -->", re.DOTALL)


def _ru_plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _race_meta(race_id: str, db: Session) -> tuple[str, str] | None:
    repo = RaceRepository(db)
    race = repo.get_race(race_id)
    if not race:
        return None

    parts = []
    if race.location:
        parts.append(race.location)
    year = max((ed.year for ed in race.editions), default=None)
    if year:
        finishers = repo.count_finishers(race.id, year)
        if finishers:
            word = _ru_plural(finishers, "финишёр", "финишёра", "финишёров")
            parts.append(f"{year}: {finishers} {word}")
    parts.append("Результаты, статистика и аналитика на ayda.run")

    title = f"{race.name} — ayda.run"
    return title, ". ".join(parts)


def _runner_meta(runner_id: int, db: Session) -> tuple[str, str] | None:
    repo = RaceRepository(db)
    runner = repo.get_runner_by_id(runner_id)
    if not runner:
        return None

    # Same scope as the runner page: finished results on running distances
    results = [
        (res, dist, ed, race)
        for res, dist, ed, race in repo.get_runner_results(runner_id)
        if res.status in ("finished", "over_time_limit") and is_running_distance(dist.name)
    ]
    parts = []
    if results:
        n = len(results)
        word = _ru_plural(n, "гонка", "гонки", "гонок")
        years = sorted({edition.year for _, _, edition, _ in results})
        span = f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])
        parts.append(f"{n} {word} ({span})")
    club = runner.club_ref.name if runner.club_ref else runner.club
    if club:
        parts.append(f"клуб {club}")
    parts.append("Результаты и прогресс на ayda.run")

    title = f"{runner.name} — ayda.run"
    return title, " · ".join(parts)


def build_page_meta(path: str, db: Session) -> tuple[str, str] | None:
    """Return (title, description) for a shareable SPA route, else None."""
    m = _RACE_PATH_RE.match(path)
    if m:
        return _race_meta(m.group(1), db)
    m = _RUNNER_PATH_RE.match(path)
    if m:
        return _runner_meta(int(m.group(1)), db)
    return None


def inject_meta(index_html: str, title: str, description: str, url: str) -> str:
    """Replace the default title/meta block in index.html with page-specific tags."""
    t = html.escape(title, quote=True)
    d = html.escape(description, quote=True)
    u = html.escape(url, quote=True)
    block = (
        f'<meta name="description" content="{d}" />\n'
        f'    <meta property="og:type" content="website" />\n'
        f'    <meta property="og:site_name" content="ayda.run" />\n'
        f'    <meta property="og:title" content="{t}" />\n'
        f'    <meta property="og:description" content="{d}" />\n'
        f'    <meta property="og:url" content="{u}" />\n'
        f'    <meta name="twitter:card" content="summary" />'
    )
    out = _TITLE_RE.sub(f"<title>{t}</title>", index_html, count=1)
    out, n = _OG_BLOCK_RE.subn(block, out, count=1)
    if n == 0:
        # index.html built without the marker block — inject before </head>
        out = out.replace("</head>", block + "\n  </head>", 1)
    return out
