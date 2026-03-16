"""Utilities for normalizing participant names from race results.

Handles both Latin (CLAX) and Cyrillic (Almaty Marathon) names.
normalize_name() produces a canonical Latin form for matching and search.
"""

from __future__ import annotations

import re

# Cyrillic → Latin transliteration table.
# Based on BGN/PCGN with adjustments derived from real CLAX↔AM pairs:
#   Руслан→Ruslan, Бекешов→Bekeshov, Рахимбаев→Rakhimbayev,
#   Шынгыс→Shyngys, Архат→Arkhat, Джанарстанов→Dzhanarstanov,
#   Иембердиев→Iyemberdiyev, Байкашев→Baikashev
_CYRILLIC_MAP = {
    # Russian
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    # Kazakh-specific
    "ә": "a",
    "ғ": "g",
    "қ": "k",
    "ң": "n",
    "ө": "o",
    "ұ": "u",
    "ү": "u",
    "һ": "h",
    "і": "i",
}


def transliterate_cyrillic(name: str) -> str:
    """Transliterate Cyrillic name to Latin.

    Uses a mapping derived from comparing real AM (Cyrillic) and CLAX (Latin)
    spellings of the same runners. Fuzzy matching (pg_trgm) compensates for
    cases where CLAX uses a different transliteration variant.

    >>> transliterate_cyrillic("Руслан Бекешов")
    'Ruslan Bekeshov'
    >>> transliterate_cyrillic("Шынгыс Байкашев")
    'Shyngys Baykashev'
    >>> transliterate_cyrillic("Тұрлыбекұлы Нартай")
    'Turlybekuly Nartay'
    """
    result = []
    for char in name:
        lower = char.lower()
        if lower in _CYRILLIC_MAP:
            trans = _CYRILLIC_MAP[lower]
            if char.isupper() and trans:
                trans = trans[0].upper() + trans[1:]
            result.append(trans)
        else:
            result.append(char)
    return "".join(result)


def _has_cyrillic(text: str) -> bool:
    """Check if text contains Cyrillic characters."""
    return any("\u0400" <= c <= "\u04ff" for c in text)


def normalize_name(name: str) -> str:
    """Normalize a participant name for matching.

    Steps:
    1. If Cyrillic — transliterate to Latin
    2. Strip whitespace, collapse multiple spaces
    3. Lowercase
    4. Sort words alphabetically (so "renat mannanov" == "mannanov renat")

    >>> normalize_name("Baikashev Shyngys")
    'baikashev shyngys'
    >>> normalize_name("Shyngys Baikashev")
    'baikashev shyngys'
    >>> normalize_name("BAIKASHEV Shyngys")
    'baikashev shyngys'
    >>> normalize_name("  Vizuete  Castro   Pedro ")
    'castro pedro vizuete'
    >>> normalize_name("Руслан Бекешов")
    'bekeshov ruslan'
    >>> normalize_name("Шынгыс Байкашев")
    'baykashev shyngys'
    """
    if _has_cyrillic(name):
        name = transliterate_cyrillic(name)
    name = re.sub(r"\s+", " ", name.strip()).lower()
    parts = sorted(name.split())
    return " ".join(parts)
