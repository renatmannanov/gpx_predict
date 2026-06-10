"""Utilities for normalizing participant names from race results.

Handles both Latin (CLAX) and Cyrillic (Almaty Marathon) names.
normalize_name() canonicalizes a name in its OWN alphabet (no cross-alphabet
transliteration) — sources are isolated by runners.source, so AM Cyrillic and
athletex Latin are never matched against each other.

transliterate_cyrillic() is retained for reference / possible future
cross-source merge tooling, but is NOT used by normalize_name() anymore.
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


def phonetic_normalize_word(word: str) -> str:
    """Normalize a single word to collapse transliteration variants.

    Applies deterministic regex rules that map common Cyrillic-to-Latin
    transliteration variants to a single canonical form. Must be called
    on a single lowercase word (no spaces).

    Rules (applied in order):
    1. Intervocalic j → y  (vowel-j-vowel, e.g. ojan → oyan)
    2. Final j → y         (sergej → sergey)
    3. Vowel + ev$ → yev   (baev → bayev)
    4. Vowel + eva$ → yeva (baeva → bayeva)
    5. ii$ → iy            (dmitrii → dmitriy)
    6. ei$ → ey            (andrei → andrey)
    7. x → ks              (alexandr → aleksandr)
    8. ss → s              (CLAX doubles s: ussin → usin, tassin → tasin)
    9. sch → shch           (щ variants: schavinskaya → shchavinskaya)
       If input already has 'shch', the substitution is safe: shshch → shch
    10. standalone h → kh   (х variants, but NOT sh/ch/zh/kh/th)
    11. ye → e at word start (Е at start: yevgeniy → evgeniy)

    >>> phonetic_normalize_word("sergej")
    'sergey'
    >>> phonetic_normalize_word("andrei")
    'andrey'
    >>> phonetic_normalize_word("dmitrii")
    'dmitriy'
    >>> phonetic_normalize_word("alexandr")
    'aleksandr'
    >>> phonetic_normalize_word("sergey")
    'sergey'
    >>> phonetic_normalize_word("ussin")
    'usin'
    >>> phonetic_normalize_word("suhorukov")
    'sukhorukov'
    >>> phonetic_normalize_word("yevgeniy")
    'evgeniy'
    >>> phonetic_normalize_word("schavinskaya")
    'shchavinskaya'
    """
    # 1. Intervocalic j → y: vowel + j + vowel
    word = re.sub(r"([aeiou])j(?=[aeiou])", r"\1y", word)
    # 2. Final j → y
    word = re.sub(r"j$", "y", word)
    # 3. vowel + ev$ → vowel + yev
    word = re.sub(r"([aeiou])ev$", r"\1yev", word)
    # 4. vowel + eva$ → vowel + yeva
    word = re.sub(r"([aeiou])eva$", r"\1yeva", word)
    # 5. ii$ → iy
    word = re.sub(r"ii$", "iy", word)
    # 6. ei$ → ey
    word = re.sub(r"ei$", "ey", word)
    # 7. x → ks (simple replacement, not regex)
    word = word.replace("x", "ks")
    # 8. ss → s (CLAX doubles s: Ussin→Usin, Tassin→Tasin)
    word = word.replace("ss", "s")
    # 9. sch → shch (when not already shch; щ variants)
    word = re.sub(r"sch", "shch", word)
    # But if that created 'shshch' from existing 'shch', fix it:
    word = word.replace("shshch", "shch")
    # 10. standalone h → kh (х variants, but NOT sh/ch/zh/kh/th)
    word = re.sub(r"(?<![sczkt])h", "kh", word)
    # 11. ye → e at word start (Е at start: Yevgeniy→Evgeniy)
    word = re.sub(r"^ye", "e", word)
    return word


def normalize_name(name: str) -> str:
    """Normalize a participant name for matching, in its OWN alphabet.

    We canonicalize (lowercase, collapse spaces, sort words) but do NOT
    transliterate across alphabets. Sources are isolated by runners.source
    (AM Cyrillic vs athletex Latin never match), so there is no need — and
    transliterating Cyrillic→Latin only produced wrong, lossy forms
    (Ким/Kim, double-ss, Kazakh names). As-is in, as-is out.

    Cyrillic input  → canonical Cyrillic  (lowercase + sorted words)
    Latin input     → canonical Latin     (+ phonetic variant collapsing)

    Phonetic normalization is Latin-only (its rules assume Latin), so it is
    applied only to Latin names.

    >>> normalize_name("Baikashev Shyngys")
    'baikashev shyngys'
    >>> normalize_name("Shyngys Baikashev")
    'baikashev shyngys'
    >>> normalize_name("BAIKASHEV Shyngys")
    'baikashev shyngys'
    >>> normalize_name("  Vizuete  Castro   Pedro ")
    'castro pedro vizuete'
    >>> normalize_name("Руслан Бекешов")
    'бекешов руслан'
    >>> normalize_name("Бекешов Руслан")
    'бекешов руслан'
    >>> normalize_name("Sergej Tropin")
    'sergey tropin'
    """
    is_cyrillic = _has_cyrillic(name)
    name = re.sub(r"\s+", " ", name.strip()).lower()
    if is_cyrillic:
        # Canonicalize in Cyrillic: no transliteration, no Latin phonetics.
        words = name.split()
    else:
        words = [phonetic_normalize_word(w) for w in name.split()]
    return " ".join(sorted(words))
