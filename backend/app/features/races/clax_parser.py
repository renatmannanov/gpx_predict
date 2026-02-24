"""CLAX XML parser for myrace.info race results."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from .models import RaceDistanceResults, RaceEditionData, RaceResult

# Distances we care about (lowercase for matching)
ALLOWED_DISTANCES = {
    "skyrunning",
    "skyrunning lite",
    "скайраннинг",
    "скайраннинг лайт",
}


def parse_clax_time(time_str: str) -> int | None:
    """Parse CLAX time format to seconds.

    Formats:
        "00h52'05"  → 3125
        "01h02'40"  → 3760
        "00h09'13"  → 553
    """
    if not time_str:
        return None
    m = re.match(r"(\d+)h(\d+)'(\d+)", time_str)
    if not m:
        return None
    hours, minutes, seconds = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _excel_date_to_iso(excel_date: str, tz_minutes: int = 300) -> str | None:
    """Convert Excel serial date number to ISO date string.

    Excel serial date 45725 = 2025-03-09 (with epoch 1899-12-30).
    TZ is offset in minutes from UTC (300 = UTC+5 Almaty).
    """
    try:
        from datetime import datetime, timedelta

        serial = int(float(excel_date))
        epoch = datetime(1899, 12, 30)
        dt = epoch + timedelta(days=serial)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


class ClaxParser:
    """Parser for CLAX XML files from myrace.info."""

    def __init__(self, filter_distances: bool = True):
        """
        Args:
            filter_distances: If True, only parse ALLOWED_DISTANCES.
                If False, parse all distances.
        """
        self.filter_distances = filter_distances

    def parse_url(self, url: str) -> RaceEditionData:
        """Download and parse a CLAX file from URL.

        Handles both formats:
        - Viewer: https://live.myrace.info/?f=bases/kz/2025/.../file.clax
        - Direct: https://live.myrace.info/bases/kz/2025/.../file.clax
        """
        direct_url = _resolve_clax_url(url)
        resp = httpx.get(direct_url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        xml_text = resp.text.lstrip("\ufeff")  # strip BOM if present
        return self._parse_xml(xml_text, source_url=url)

    def parse_file(self, path: str | Path) -> RaceEditionData:
        """Parse a local CLAX XML file."""
        path = Path(path)
        content = path.read_text(encoding="utf-8-sig")  # handles BOM
        return self._parse_xml(content, source_url=None)

    def _parse_xml(
        self, xml_content: str, source_url: str | None = None
    ) -> RaceEditionData:
        """Main parsing logic."""
        root = ET.fromstring(xml_content)

        race_name = root.get("nom", "Unknown Race")
        date_str = _excel_date_to_iso(root.get("date", ""))

        # Try to extract year from date or dates attribute
        year = self._extract_year(root, date_str)

        # Parse courses (Parcours) for distance metadata
        courses = self._parse_courses(root)

        # Parse participants (Engages)
        etape = root.find(".//Etape")
        if etape is None:
            return RaceEditionData(
                race_name=race_name,
                year=year,
                date=date_str,
                source_url=source_url,
            )

        participants = self._parse_participants(etape)
        results_map = self._parse_results(etape)

        # Group by distance, compute places, build RaceDistanceResults
        distances = self._build_distances(participants, results_map, courses)

        return RaceEditionData(
            race_name=race_name,
            year=year,
            date=date_str,
            source_url=source_url,
            distances=distances,
        )

    def _extract_year(self, root: ET.Element, date_str: str | None) -> int:
        """Extract year from date or dates attribute."""
        if date_str:
            try:
                return int(date_str[:4])
            except (ValueError, IndexError):
                pass
        # Fallback: parse from "dates" attribute (e.g., "9 mars 2025")
        dates_attr = root.get("dates", "")
        m = re.search(r"20\d{2}", dates_attr)
        if m:
            return int(m.group())
        return 0

    def _parse_courses(self, root: ET.Element) -> dict[str, float | None]:
        """Parse course definitions. Returns {course_name: distance_km}."""
        courses: dict[str, float | None] = {}
        for pcs in root.findall(".//Parcours/Pcs"):
            name = pcs.get("nom", "")
            dist_m = pcs.get("distance")
            dist_km = int(dist_m) / 1000.0 if dist_m else None
            courses[name] = dist_km
        return courses

    def _parse_participants(self, etape: ET.Element) -> dict[str, dict]:
        """Parse Engages into {bib: participant_data}."""
        participants: dict[str, dict] = {}
        for e in etape.findall(".//Engages/E"):
            bib = e.get("d")
            if not bib:
                continue
            # Skip DNS (np="1" = non-partant)
            if e.get("np") == "1":
                continue
            participants[bib] = {
                "name": e.get("n", ""),
                "gender": e.get("x"),
                "category": e.get("ca"),
                "distance": e.get("p", ""),
                "club": e.get("c"),
                "birth_year": _safe_int(e.get("a")),
                "nationality": e.get("na"),
            }
        return participants

    def _parse_results(self, etape: ET.Element) -> dict[str, dict]:
        """Parse Resultats into {bib: result_data}."""
        results: dict[str, dict] = {}
        for r in etape.findall(".//Resultats/R"):
            bib = r.get("d")
            if not bib:
                continue
            time_s = parse_clax_time(r.get("t", ""))
            if time_s is None:
                continue
            results[bib] = {
                "time_seconds": time_s,
                "pace": r.get("m"),
                "over_time_limit": r.get("hd") == "1",
            }
        return results

    def _build_distances(
        self,
        participants: dict[str, dict],
        results_map: dict[str, dict],
        courses: dict[str, float | None],
    ) -> list[RaceDistanceResults]:
        """Group participants by distance, merge with results, compute places."""
        # Group by distance name
        by_distance: dict[str, list[tuple[str, dict, dict]]] = {}
        for bib, pdata in participants.items():
            rdata = results_map.get(bib)
            if rdata is None:
                continue  # no result for this participant
            dist_name = pdata["distance"]
            if dist_name not in by_distance:
                by_distance[dist_name] = []
            by_distance[dist_name].append((bib, pdata, rdata))

        # Filter distances if needed
        if self.filter_distances:
            by_distance = {
                k: v
                for k, v in by_distance.items()
                if k.lower().strip() in ALLOWED_DISTANCES
            }

        distances: list[RaceDistanceResults] = []
        for dist_name, entries in sorted(by_distance.items()):
            # Sort by time to compute places
            entries.sort(key=lambda x: x[2]["time_seconds"])

            results: list[RaceResult] = []
            for place, (bib, pdata, rdata) in enumerate(entries, start=1):
                results.append(
                    RaceResult(
                        name=pdata["name"],
                        name_local=None,  # CLAX has Latin only
                        time_seconds=rdata["time_seconds"],
                        place=place,
                        category=pdata["category"],
                        gender=pdata["gender"],
                        club=pdata["club"],
                        bib=bib,
                        pace=rdata["pace"],
                        birth_year=pdata["birth_year"],
                        nationality=pdata["nationality"],
                        over_time_limit=rdata["over_time_limit"],
                    )
                )

            dist_km = courses.get(dist_name)
            distances.append(
                RaceDistanceResults(
                    distance_name=dist_name,
                    distance_km=dist_km,
                    elevation_gain_m=None,  # not in CLAX, add from catalog later
                    results=results,
                )
            )

        return distances


def _resolve_clax_url(url: str) -> str:
    """Convert viewer URL to direct XML URL.

    Viewer: https://live.myrace.info/?f=bases/kz/2025/.../file.clax
    Direct: https://live.myrace.info/bases/kz/2025/.../file.clax
    """
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "f" in qs:
        file_path = qs["f"][0]
        return f"{parsed.scheme}://{parsed.netloc}/{file_path}"
    return url


def _safe_int(value: str | None) -> int | None:
    """Safely convert string to int."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
