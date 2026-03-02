"""Utilities for normalizing participant names from CLAX race results.

CLAX data has inconsistent naming:
- "Baikashev Shyngys" / "BAIKASHEV Shyngys" / "Shyngys Baikashev"
- "Janzakov Niyaz" / "JANZAKOV Niyaz"

normalize_name() produces a canonical form for matching and search.
"""

from __future__ import annotations

import re


def normalize_name(name: str) -> str:
    """Normalize a participant name for matching.

    Steps:
    1. Strip whitespace, collapse multiple spaces
    2. Lowercase
    3. Sort words alphabetically (so "renat mannanov" == "mannanov renat")

    >>> normalize_name("Baikashev Shyngys")
    'baikashev shyngys'
    >>> normalize_name("Shyngys Baikashev")
    'baikashev shyngys'
    >>> normalize_name("BAIKASHEV Shyngys")
    'baikashev shyngys'
    >>> normalize_name("  Vizuete  Castro   Pedro ")
    'castro pedro vizuete'
    """
    name = re.sub(r"\s+", " ", name.strip()).lower()
    parts = sorted(name.split())
    return " ".join(parts)
