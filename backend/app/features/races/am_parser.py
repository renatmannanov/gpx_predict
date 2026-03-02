"""Parser for almaty-marathon.kz race results (HTML scraping).

Site uses Yii GridView with server-rendered HTML tables.
Each race page has a distance selector (?d=ID) and pagination (?Results_page=N).
"""

from __future__ import annotations

import re
import time

import httpx
from bs4 import BeautifulSoup, Tag

from .models import RaceDistanceResults, RaceEditionData, RaceResult

# Column indices (0-based) that are always present
# Место | Участник | Страна | Город | Номер | [splits...] | Финиш | Чип время | Сертификат
COL_PLACE = 0
COL_NAME = 1
COL_COUNTRY = 2
COL_CITY = 3
COL_BIB = 4
# Splits are variable, Финиш/Чип время are last 3 and last 2 before Сертификат
# We parse by counting from the end: cert=-1, chip=-2, finish=-3


def _parse_time_to_seconds(time_str: str) -> int | None:
    """Parse HH:MM:SS.xx or HH:MM:SS format to total seconds.

    Examples:
        "00:32:16" → 1936
        "00:09:18.90" → 558
        "01:02:40.50" → 3760
    """
    if not time_str or time_str.strip() == "":
        return None
    time_str = time_str.strip()
    # Remove fractional seconds
    time_str = re.sub(r"\.\d+$", "", time_str)
    m = re.match(r"(\d+):(\d+):(\d+)", time_str)
    if not m:
        return None
    h, mins, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h * 3600 + mins * 60 + s


def _extract_country(td: Tag) -> str | None:
    """Extract country code from flag image in a <td>."""
    img = td.find("img")
    if not img:
        return None
    src = img.get("alt") or img.get("src") or ""
    # alt="Kazakhstan.png" → "KAZ", src may contain flag filename
    name = re.sub(r"\.\w+$", "", src).strip()
    return _country_to_code(name) if name else None


# Common country mappings from flag filenames
_COUNTRY_MAP = {
    "kazakhstan": "KAZ",
    "russia": "RUS",
    "uzbekistan": "UZB",
    "kyrgyzstan": "KGZ",
    "tajikistan": "TJK",
    "turkmenistan": "TKM",
    "china": "CHN",
    "india": "IND",
    "turkey": "TUR",
    "usa": "USA",
    "united states": "USA",
    "germany": "GER",
    "france": "FRA",
    "italy": "ITA",
    "spain": "ESP",
    "united kingdom": "GBR",
    "uk": "GBR",
    "canada": "CAN",
    "japan": "JPN",
    "south korea": "KOR",
    "korea": "KOR",
    "kenya": "KEN",
    "ethiopia": "ETH",
    "morocco": "MAR",
    "brazil": "BRA",
    "australia": "AUS",
    "armenia": "ARM",
    "georgia": "GEO",
    "azerbaijan": "AZE",
    "mongolia": "MGL",
    "belarus": "BLR",
    "ukraine": "UKR",
    "poland": "POL",
    "czech republic": "CZE",
    "iran": "IRI",
    "pakistan": "PAK",
    "afghanistan": "AFG",
    "netherlands": "NED",
    "belgium": "BEL",
    "sweden": "SWE",
    "norway": "NOR",
    "finland": "FIN",
    "denmark": "DEN",
    "austria": "AUT",
    "switzerland": "SUI",
    "ireland": "IRL",
    "portugal": "POR",
    "romania": "ROU",
    "hungary": "HUN",
    "serbia": "SRB",
    "croatia": "CRO",
    "mexico": "MEX",
    "argentina": "ARG",
    "colombia": "COL",
    "chile": "CHI",
    "new zealand": "NZL",
    "south africa": "RSA",
    "nigeria": "NGR",
    "egypt": "EGY",
    "tunisia": "TUN",
    "israel": "ISR",
    "philippines": "PHI",
    "indonesia": "INA",
    "malaysia": "MAS",
    "thailand": "THA",
    "singapore": "SGP",
    "vietnam": "VIE",
    "nepal": "NEP",
    "sri lanka": "SRI",
    "latvia": "LAT",
    "lithuania": "LTU",
    "estonia": "EST",
    "moldova": "MDA",
    "bulgaria": "BUL",
    "greece": "GRE",
    "slovakia": "SVK",
    "slovenia": "SLO",
}


def _country_to_code(name: str) -> str:
    """Convert country name from flag filename to 3-letter code."""
    return _COUNTRY_MAP.get(name.lower(), name[:3].upper())


class AlmatyMarathonParser:
    """Parser for almaty-marathon.kz HTML result pages."""

    def __init__(self, delay: float = 0.3):
        """
        Args:
            delay: Seconds to wait between HTTP requests (rate limiting).
        """
        self.delay = delay
        self._client = httpx.Client(timeout=30, follow_redirects=True)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def parse_race(self, race_url: str) -> RaceEditionData:
        """Parse all distances and all pages for a race.

        Args:
            race_url: e.g. "https://almaty-marathon.kz/ru/results/winter_run_2025"

        Returns:
            RaceEditionData with all distances and results.
        """
        # Fetch initial page to get race name and distance list
        soup = self._fetch(race_url)

        race_name = self._extract_race_name(soup)
        year = self._extract_year(race_url, race_name)
        distance_options = self._extract_distances(soup)

        distances: list[RaceDistanceResults] = []
        for dist_id, dist_name in distance_options:
            results = self._parse_distance(race_url, dist_id)

            dist_km = self._guess_distance_km(dist_name)
            distances.append(
                RaceDistanceResults(
                    distance_name=dist_name,
                    distance_km=dist_km,
                    elevation_gain_m=None,
                    results=results,
                )
            )

        return RaceEditionData(
            race_name=race_name,
            year=year,
            date=None,  # not available on the page
            source_url=race_url,
            distances=distances,
        )

    def _fetch(self, url: str) -> BeautifulSoup:
        """Fetch URL and return parsed soup."""
        resp = self._client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _extract_race_name(self, soup: BeautifulSoup) -> str:
        """Extract race name from <h1>."""
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)
            # Remove trailing slash
            return name.rstrip("/").strip()
        return "Unknown Race"

    def _extract_year(self, url: str, race_name: str) -> int:
        """Extract year from URL slug or race name."""
        # Try URL first: .../winter_run_2025
        m = re.search(r"_(\d{4})$", url.rstrip("/").split("?")[0])
        if m:
            return int(m.group(1))
        # Try race name: "WINTER RUN 2025"
        m = re.search(r"20\d{2}", race_name)
        if m:
            return int(m.group())
        return 0

    def _extract_distances(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Extract distance options from the <select> dropdown.

        Returns list of (distance_id, distance_name) tuples.
        """
        select = soup.select_one(".filter-distance select")
        if not select:
            return []
        options = select.find_all("option")
        return [(opt.get("value", ""), opt.get_text(strip=True)) for opt in options]

    def _parse_distance(
        self, race_url: str, dist_id: str
    ) -> list[RaceResult]:
        """Parse all pages for one distance."""
        all_results: list[RaceResult] = []
        page = 1

        while True:
            url = f"{race_url}?d={dist_id}&Results_page={page}"
            if page > 1:
                time.sleep(self.delay)
            soup = self._fetch(url)

            rows = self._parse_table_rows(soup)
            if not rows:
                break

            all_results.extend(rows)

            # Check if there's a next page
            last_page = self._get_last_page(soup)
            if page >= last_page:
                break
            page += 1

        # Re-number places sequentially (1-based) by chip time
        all_results.sort(key=lambda r: r.time_seconds)
        for i, r in enumerate(all_results, start=1):
            r.place = i

        return all_results

    def _parse_table_rows(self, soup: BeautifulSoup) -> list[RaceResult]:
        """Parse result rows from the table on a single page."""
        table = soup.select_one("#data-grid table.items")
        if not table:
            return []

        # Get headers to find column count
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if len(headers) < 7:
            return []

        # Find the indices: columns from end are stable
        # ..., Финиш, Чип время, Сертификат
        n = len(headers)
        idx_chip = n - 2  # "Чип время"
        idx_finish = n - 3  # "Финиш"

        rows: list[RaceResult] = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue

            # Skip "Нет результатов." row
            if len(tds) == 1:
                continue

            name = tds[COL_NAME].get_text(strip=True)
            if not name:
                continue

            # Use chip time (more accurate), fall back to finish time
            chip_time_str = tds[idx_chip].get_text(strip=True)
            finish_time_str = tds[idx_finish].get_text(strip=True)
            time_s = _parse_time_to_seconds(chip_time_str) or _parse_time_to_seconds(finish_time_str)
            if time_s is None or time_s == 0:
                continue

            place_str = tds[COL_PLACE].get_text(strip=True)
            place = int(place_str) if place_str.isdigit() else 0

            bib = tds[COL_BIB].get_text(strip=True) or None
            country = _extract_country(tds[COL_COUNTRY])
            city = tds[COL_CITY].get_text(strip=True) or None

            rows.append(
                RaceResult(
                    name=name,
                    name_local=None,
                    time_seconds=time_s,
                    place=place,
                    category=None,  # not available on this site
                    gender=None,  # not in main table
                    club=None,
                    city=city,  # город — не клуб
                    bib=bib,
                    pace=None,
                    birth_year=None,
                    nationality=country,
                    over_time_limit=False,
                )
            )

        return rows

    def _get_last_page(self, soup: BeautifulSoup) -> int:
        """Get the last page number from pagination."""
        # Look for "В конец" link
        pager = soup.select_one("#data-grid .pager")
        if not pager:
            return 1

        last_link = pager.find("a", string="В конец")
        if last_link:
            href = last_link.get("href", "")
            m = re.search(r"Results_page=(\d+)", href)
            if m:
                return int(m.group(1))

        # Fallback: find max page number from pagination links
        max_page = 1
        for a in pager.find_all("a", href=True):
            m = re.search(r"Results_page=(\d+)", a.get("href", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))
        return max_page

    def _guess_distance_km(self, name: str) -> float | None:
        """Try to extract distance in km from the distance name."""
        # "10 км" → 10.0
        # "21 км 97,5 м" → 21.0975
        # "42 км 195 м" → 42.195
        # "3000 м" → 3.0
        # "Эстафета Copa Run" → None

        # Try "X км Y м" pattern
        m = re.match(r"(\d+)\s*км\s*(\d+[,.]?\d*)\s*м", name)
        if m:
            km = int(m.group(1))
            meters = float(m.group(2).replace(",", "."))
            return km + meters / 1000

        # Try "X км" pattern
        m = re.match(r"(\d+)\s*км", name)
        if m:
            return float(m.group(1))

        # Try "X м" pattern (meters only)
        m = re.match(r"(\d+)\s*м", name)
        if m:
            return int(m.group(1)) / 1000

        return None
