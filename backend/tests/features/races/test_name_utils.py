"""Tests for phonetic normalization in name_utils.

Covers:
- phonetic_normalize_word(): each rule individually + identity + safety
- normalize_name(): end-to-end with real Cyrillic/Latin pairs
"""

import pytest

from app.features.races.name_utils import normalize_name, phonetic_normalize_word


# ---------------------------------------------------------------------------
# phonetic_normalize_word: individual rules
# ---------------------------------------------------------------------------

class TestPhoneticNormalizeWordRules:
    """Each regex rule tested individually."""

    def test_rule1_intervocalic_j(self):
        """Rule 1: vowel + j + vowel -> vowel + y + vowel."""
        # j between two vowels becomes y
        assert phonetic_normalize_word("ajal") == "ayal"
        assert phonetic_normalize_word("ojan") == "oyan"
        assert phonetic_normalize_word("ejan") == "eyan"
        # j NOT between vowels -- no change
        assert phonetic_normalize_word("ajgul") == "ajgul"

    def test_rule2_final_j(self):
        """Rule 2: j$ -> y."""
        assert phonetic_normalize_word("sergej") == "sergey"
        assert phonetic_normalize_word("aleksej") == "aleksey"
        assert phonetic_normalize_word("nikolaj") == "nikolay"

    def test_rule3_vowel_ev_ending(self):
        """Rule 3: vowel + ev$ -> vowel + yev."""
        assert phonetic_normalize_word("baev") == "bayev"
        assert phonetic_normalize_word("isaev") == "isayev"
        assert phonetic_normalize_word("dunaev") == "dunayev"
        # Non-vowel before ev should NOT trigger
        assert phonetic_normalize_word("medvedev") == "medvedev"

    def test_rule4_vowel_eva_ending(self):
        """Rule 4: vowel + eva$ -> vowel + yeva."""
        assert phonetic_normalize_word("baeva") == "bayeva"
        assert phonetic_normalize_word("isaeva") == "isayeva"
        # Non-vowel before eva should NOT trigger
        assert phonetic_normalize_word("medvedeva") == "medvedeva"

    def test_rule5_ii_ending(self):
        """Rule 5: ii$ -> iy."""
        assert phonetic_normalize_word("dmitrii") == "dmitriy"
        assert phonetic_normalize_word("vasilii") == "vasiliy"

    def test_rule6_ei_ending(self):
        """Rule 6: ei$ -> ey."""
        assert phonetic_normalize_word("andrei") == "andrey"
        assert phonetic_normalize_word("sergei") == "sergey"
        assert phonetic_normalize_word("aleksei") == "aleksey"

    def test_rule7_x_to_ks(self):
        """Rule 7: x -> ks."""
        assert phonetic_normalize_word("alexandr") == "aleksandr"
        assert phonetic_normalize_word("alexandra") == "aleksandra"
        assert phonetic_normalize_word("maxim") == "maksim"

    def test_rule8_ss_to_s(self):
        """Rule 8: ss -> s (CLAX doubles s)."""
        assert phonetic_normalize_word("ussin") == "usin"
        assert phonetic_normalize_word("tassin") == "tasin"
        assert phonetic_normalize_word("nossov") == "nosov"
        assert phonetic_normalize_word("anastassiya") == "anastasiya"
        # Single s stays as-is
        assert phonetic_normalize_word("ruslan") == "ruslan"

    def test_rule9_sch_to_shch(self):
        """Rule 9: sch -> shch (щ variants)."""
        assert phonetic_normalize_word("schavinskaya") == "shchavinskaya"
        assert phonetic_normalize_word("ilyuschenko") == "ilyushchenko"
        assert phonetic_normalize_word("ischanov") == "ishchanov"
        # Already-correct shch must NOT be broken
        assert phonetic_normalize_word("shchavinskaya") == "shchavinskaya"
        assert phonetic_normalize_word("shcherbakov") == "shcherbakov"

    def test_rule10_standalone_h_to_kh(self):
        """Rule 10: h -> kh, but NOT after s/c/z/k/t."""
        assert phonetic_normalize_word("suhorukov") == "sukhorukov"
        assert phonetic_normalize_word("farruh") == "farrukh"
        assert phonetic_normalize_word("harinskaya") == "kharinskaya"
        # h after s/c/z/k/t should NOT change
        assert phonetic_normalize_word("shyngys") == "shyngys"
        assert phonetic_normalize_word("chechetko") == "chechetko"
        assert phonetic_normalize_word("zheltayev") == "zheltayev"
        assert phonetic_normalize_word("khaidar") == "khaidar"

    def test_rule11_ye_to_e_at_start(self):
        """Rule 11: ye -> e at word start."""
        assert phonetic_normalize_word("yevgeniy") == "evgeniy"
        assert phonetic_normalize_word("yekaterina") == "ekaterina"
        assert phonetic_normalize_word("yelena") == "elena"
        assert phonetic_normalize_word("yerlan") == "erlan"
        # ye NOT at start should stay
        assert phonetic_normalize_word("bayev") == "bayev"
        assert phonetic_normalize_word("sergeyev") == "sergeyev"


# ---------------------------------------------------------------------------
# phonetic_normalize_word: identity (already canonical)
# ---------------------------------------------------------------------------

class TestPhoneticNormalizeWordIdentity:
    """Words already in canonical form should pass through unchanged."""

    @pytest.mark.parametrize("word", [
        "sergey",
        "andrey",
        "dmitriy",
        "aleksandr",
        "aleksandra",
        "ruslan",
        "bekeshov",
        "shyngys",
        "nartay",
        "maksim",
    ])
    def test_canonical_unchanged(self, word):
        assert phonetic_normalize_word(word) == word


# ---------------------------------------------------------------------------
# phonetic_normalize_word: safety (must NOT collapse different names)
# ---------------------------------------------------------------------------

class TestPhoneticNormalizeWordSafety:
    """Different names must remain different after normalization."""

    def test_aida_vs_aidana(self):
        assert phonetic_normalize_word("aida") != phonetic_normalize_word("aidana")

    def test_arina_vs_alina(self):
        assert phonetic_normalize_word("arina") != phonetic_normalize_word("alina")

    def test_kotov_vs_kolotov(self):
        assert phonetic_normalize_word("kotov") != phonetic_normalize_word("kolotov")

    def test_ivan_vs_ivanov(self):
        assert phonetic_normalize_word("ivan") != phonetic_normalize_word("ivanov")


# ---------------------------------------------------------------------------
# normalize_name: end-to-end with real pairs
# ---------------------------------------------------------------------------

class TestNormalizeNameSamePerson:
    """Same person within ONE alphabet -- should produce identical output.

    NOTE: cross-alphabet matching (Cyrillic AM ↔ Latin athletex) was removed
    on purpose — sources are isolated by runners.source. normalize_name now
    canonicalizes in the name's own alphabet, with NO transliteration.
    """

    # --- Latin (athletex): word order + phonetic variant collapsing ---

    def test_latin_word_order(self):
        assert normalize_name("Ladontsev Andrey") == normalize_name("Andrey Ladontsev")

    def test_latin_andrei_andrey(self):
        """ei -> ey phonetic variant collapses (both Latin)."""
        assert normalize_name("Andrei Ladontsev") == normalize_name("Ladontsev Andrey")

    def test_latin_sergei_sergey(self):
        assert normalize_name("Sergei Tkachenko") == normalize_name("Tkachenko Sergey")

    def test_latin_dmitrii_dmitriy(self):
        assert normalize_name("Dmitrii Doktorov") == normalize_name("Doktorov Dmitriy")

    def test_latin_alexandra_aleksandra(self):
        """x -> ks phonetic variant collapses (both Latin)."""
        assert normalize_name("Alexandra Pavlenko") == normalize_name("Pavlenko Aleksandra")

    # --- Cyrillic (AM): word order invariance, stays Cyrillic ---

    def test_cyrillic_word_order(self):
        assert normalize_name("Алмас Рахимбаев") == normalize_name("Рахимбаев Алмас")

    def test_cyrillic_case_invariant(self):
        assert normalize_name("РАХИМБАЕВ Алмас") == normalize_name("рахимбаев алмас")


class TestNormalizeNameDifferentPeople:
    """Real pairs that are different people -- must produce different output."""

    def test_aida_vs_aidana(self):
        assert normalize_name("Аида Нурсеитова") != normalize_name("Nurseitova Aidana")

    def test_arina_vs_alina(self):
        assert normalize_name("Arina Kuznetsova") != normalize_name("Kuznetsova Alina")

    def test_kotov_vs_kolotov(self):
        assert normalize_name("Алексей Котов") != normalize_name("Kolotov Aleksey")


# ---------------------------------------------------------------------------
# normalize_name: basic behavior preserved
# ---------------------------------------------------------------------------

class TestNormalizeNameBasic:
    """Existing behavior still works after phonetic normalization integration."""

    def test_word_order_invariant(self):
        assert normalize_name("Baikashev Shyngys") == normalize_name("Shyngys Baikashev")

    def test_case_invariant(self):
        assert normalize_name("BAIKASHEV Shyngys") == "baikashev shyngys"

    def test_extra_whitespace(self):
        assert normalize_name("  Vizuete  Castro   Pedro ") == "castro pedro vizuete"

    def test_cyrillic_canonical_stays_cyrillic(self):
        """Cyrillic is canonicalized (lowercase + sorted) but NOT transliterated."""
        assert normalize_name("Руслан Бекешов") == "бекешов руслан"

    def test_sergej_tropin(self):
        """New doctest: Sergej -> Sergey via phonetic normalization."""
        assert normalize_name("Sergej Tropin") == "sergey tropin"
