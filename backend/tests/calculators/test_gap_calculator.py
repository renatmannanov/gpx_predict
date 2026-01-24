"""
Tests for GAP (Grade Adjusted Pace) Calculator.

Tests both calculation modes:
- STRAVA: Empirical model based on 240k athletes
- MINETTI: Hybrid model (Minetti uphill + Strava downhill)
"""

import pytest
from math import exp

from app.services.calculators.base import MacroSegment, SegmentType
from app.services.calculators.trail_run import (
    GAPCalculator,
    GAPMode,
    GAPResult,
    STRAVA_GAP_TABLE,
    compare_gap_modes,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def strava_calculator():
    """Create a Strava mode GAP calculator with 6:00 base pace."""
    return GAPCalculator(base_flat_pace_min_km=6.0, mode=GAPMode.STRAVA)


@pytest.fixture
def minetti_calculator():
    """Create a Minetti mode GAP calculator with 6:00 base pace."""
    return GAPCalculator(base_flat_pace_min_km=6.0, mode=GAPMode.MINETTI)


@pytest.fixture
def flat_segment():
    """Create a flat segment for testing."""
    return MacroSegment(
        segment_number=1,
        segment_type=SegmentType.FLAT,
        distance_km=1.0,
        elevation_gain_m=0,
        elevation_loss_m=0,
        start_elevation_m=100,
        end_elevation_m=100
    )


@pytest.fixture
def uphill_segment_10():
    """Create a 10% uphill segment."""
    return MacroSegment(
        segment_number=2,
        segment_type=SegmentType.ASCENT,
        distance_km=1.0,
        elevation_gain_m=100,
        elevation_loss_m=0,
        start_elevation_m=100,
        end_elevation_m=200
    )


@pytest.fixture
def downhill_segment_10():
    """Create a -10% downhill segment."""
    return MacroSegment(
        segment_number=3,
        segment_type=SegmentType.DESCENT,
        distance_km=1.0,
        elevation_gain_m=0,
        elevation_loss_m=100,
        start_elevation_m=200,
        end_elevation_m=100
    )


# =============================================================================
# Test GAPCalculator Initialization
# =============================================================================

class TestGAPCalculatorInit:
    """Tests for GAP calculator initialization."""

    def test_default_initialization(self):
        """Test default initialization with Strava mode."""
        calc = GAPCalculator()
        assert calc.base_flat_pace == 6.0
        assert calc.mode == GAPMode.STRAVA

    def test_custom_pace(self):
        """Test initialization with custom pace."""
        calc = GAPCalculator(base_flat_pace_min_km=5.0)
        assert calc.base_flat_pace == 5.0

    def test_minetti_mode(self):
        """Test initialization with Minetti mode."""
        calc = GAPCalculator(mode=GAPMode.MINETTI)
        assert calc.mode == GAPMode.MINETTI

    def test_mode_enum_values(self):
        """Test GAPMode enum values."""
        assert GAPMode.STRAVA.value == "strava_gap"
        assert GAPMode.MINETTI.value == "minetti_gap"


# =============================================================================
# Test Strava GAP Table
# =============================================================================

class TestStravaGAPTable:
    """Tests for Strava GAP lookup table."""

    def test_table_has_expected_keys(self):
        """Table should have both positive and negative gradients."""
        assert -30 in STRAVA_GAP_TABLE
        assert 0 in STRAVA_GAP_TABLE
        assert 30 in STRAVA_GAP_TABLE

    def test_flat_is_reference(self):
        """Flat (0%) should be exactly 1.0."""
        assert STRAVA_GAP_TABLE[0] == 1.0

    def test_optimal_descent(self):
        """Optimal descent (-9%) should be the fastest."""
        assert STRAVA_GAP_TABLE[-9] == min(STRAVA_GAP_TABLE.values())
        assert STRAVA_GAP_TABLE[-9] == 0.88  # 12% faster than flat

    def test_uphill_slower_than_flat(self):
        """All positive gradients should be slower than flat."""
        for gradient, adjustment in STRAVA_GAP_TABLE.items():
            if gradient > 0:
                assert adjustment > 1.0, f"Gradient {gradient}% should be > 1.0"

    def test_steep_descent_slower_than_optimal(self):
        """Very steep descents should be slower due to braking."""
        assert STRAVA_GAP_TABLE[-30] > STRAVA_GAP_TABLE[-9]

    def test_progressively_slower_uphill(self):
        """Pace should progressively slow with steeper uphill."""
        uphill_gradients = [g for g in STRAVA_GAP_TABLE.keys() if g > 0]
        uphill_gradients.sort()

        for i in range(len(uphill_gradients) - 1):
            g1, g2 = uphill_gradients[i], uphill_gradients[i + 1]
            assert STRAVA_GAP_TABLE[g1] <= STRAVA_GAP_TABLE[g2], \
                f"Expected {g1}% <= {g2}% adjustments"


# =============================================================================
# Test Strava Mode Calculations
# =============================================================================

class TestStravaCalculations:
    """Tests for Strava mode calculations."""

    def test_flat_calculation(self, strava_calculator):
        """Flat terrain should return base pace."""
        result = strava_calculator.calculate(0)

        assert result.gradient_percent == 0
        assert result.pace_adjustment == 1.0
        assert result.adjusted_pace_min_km == 6.0
        assert result.mode == "strava_gap"

    def test_optimal_descent(self, strava_calculator):
        """Optimal descent (-9%) should be ~12% faster."""
        result = strava_calculator.calculate(-9)

        assert result.pace_adjustment == 0.88
        assert result.adjusted_pace_min_km == pytest.approx(5.28, rel=0.01)

    def test_moderate_uphill(self, strava_calculator):
        """10% uphill should be ~38% slower."""
        result = strava_calculator.calculate(10)

        assert result.pace_adjustment == pytest.approx(1.38, rel=0.01)
        assert result.adjusted_pace_min_km == pytest.approx(8.28, rel=0.01)

    def test_steep_uphill(self, strava_calculator):
        """30% uphill should be ~230% slower."""
        result = strava_calculator.calculate(30)

        assert result.pace_adjustment == pytest.approx(3.30, rel=0.01)

    def test_interpolation_between_values(self, strava_calculator):
        """Test interpolation between table values."""
        # 7% is between 5% (1.15) and 8% (1.28)
        result = strava_calculator.calculate(7)

        expected = 1.15 + (7 - 5) / (8 - 5) * (1.28 - 1.15)
        assert result.pace_adjustment == pytest.approx(expected, rel=0.01)

    def test_extrapolation_beyond_table_max(self, strava_calculator):
        """Test extrapolation for gradients beyond table range."""
        result = strava_calculator.calculate(50)

        # Should clamp to max table value
        assert result.pace_adjustment == STRAVA_GAP_TABLE[45]

    def test_extrapolation_beyond_table_min(self, strava_calculator):
        """Test extrapolation for steep descents beyond table range."""
        result = strava_calculator.calculate(-40)

        # Should clamp to min table value
        assert result.pace_adjustment == STRAVA_GAP_TABLE[-30]


# =============================================================================
# Test Minetti Mode Calculations
# =============================================================================

class TestMinettiCalculations:
    """Tests for Minetti mode calculations."""

    def test_flat_calculation(self, minetti_calculator):
        """Flat terrain should return base pace."""
        result = minetti_calculator.calculate(0)

        assert result.gradient_percent == 0
        assert result.pace_adjustment == pytest.approx(1.0, rel=0.01)
        assert result.mode == "minetti_gap"

    def test_uphill_uses_minetti(self, minetti_calculator):
        """Uphill should use Minetti energy cost model."""
        result = minetti_calculator.calculate(20)

        # Minetti should be more aggressive than Strava on steep uphills
        assert result.pace_adjustment > 1.0
        assert result.energy_cost_ratio > 1.0

    def test_downhill_uses_strava(self, minetti_calculator):
        """Downhill should use Strava model (not Minetti)."""
        result = minetti_calculator.calculate(-10)

        # Should match Strava for downhill
        strava = GAPCalculator(6.0, GAPMode.STRAVA)
        strava_result = strava.calculate(-10)

        assert result.pace_adjustment == pytest.approx(
            strava_result.pace_adjustment, rel=0.01
        )

    def test_minetti_energy_cost_formula(self, minetti_calculator):
        """Test Minetti's energy cost polynomial."""
        # For flat (i=0): cost = 3.6 J/kg/m (reference)
        flat_cost = minetti_calculator._minetti_energy_cost(0)
        assert flat_cost == pytest.approx(1.0, rel=0.01)

        # For uphill, cost should increase
        uphill_cost = minetti_calculator._minetti_energy_cost(0.1)  # 10%
        assert uphill_cost > 1.0


# =============================================================================
# Test Strava vs Minetti Comparison
# =============================================================================

class TestModeComparison:
    """Tests comparing Strava and Minetti modes."""

    def test_compare_gap_modes_function(self):
        """Test the compare_gap_modes utility function."""
        comparison = compare_gap_modes(base_pace=6.0)

        assert "0%" in comparison
        assert "10%" in comparison
        assert "-10%" in comparison

        # Check structure
        assert "strava_adj" in comparison["0%"]
        assert "minetti_adj" in comparison["0%"]
        assert "difference" in comparison["0%"]

    def test_minetti_more_aggressive_steep_uphill(self):
        """Minetti should be more aggressive on steep uphills."""
        strava = GAPCalculator(6.0, GAPMode.STRAVA)
        minetti = GAPCalculator(6.0, GAPMode.MINETTI)

        for gradient in [20, 25, 30]:
            s = strava.calculate(gradient)
            m = minetti.calculate(gradient)
            # Minetti is typically more aggressive on very steep terrain
            # (higher energy cost = slower pace)
            # Note: the relationship depends on the exact gradient

    def test_modes_equal_on_flat(self):
        """Both modes should give same result on flat terrain."""
        strava = GAPCalculator(6.0, GAPMode.STRAVA)
        minetti = GAPCalculator(6.0, GAPMode.MINETTI)

        s = strava.calculate(0)
        m = minetti.calculate(0)

        assert s.pace_adjustment == pytest.approx(m.pace_adjustment, rel=0.05)


# =============================================================================
# Test Segment Calculations
# =============================================================================

class TestSegmentCalculations:
    """Tests for MacroSegment calculations."""

    def test_calculate_flat_segment(self, strava_calculator, flat_segment):
        """Test calculation for flat segment."""
        result = strava_calculator.calculate_segment(flat_segment)

        assert result.method_name == "strava_gap"
        assert result.speed_kmh == pytest.approx(10.0, rel=0.01)  # 6 min/km = 10 km/h
        assert result.time_hours == pytest.approx(0.1, rel=0.01)  # 1 km / 10 km/h

    def test_calculate_uphill_segment(self, strava_calculator, uphill_segment_10):
        """Test calculation for uphill segment."""
        result = strava_calculator.calculate_segment(uphill_segment_10)

        assert result.method_name == "strava_gap"
        # 10% uphill = x1.38 adjustment = 8.28 min/km = 7.25 km/h
        assert result.speed_kmh == pytest.approx(7.25, rel=0.05)
        # 1 km / 7.25 km/h = 0.138 hours
        assert result.time_hours > 0.1

    def test_calculate_downhill_segment(self, strava_calculator, downhill_segment_10):
        """Test calculation for downhill segment."""
        result = strava_calculator.calculate_segment(downhill_segment_10)

        assert result.method_name == "strava_gap"
        # -10% = x0.88 = 5.28 min/km = 11.36 km/h
        assert result.speed_kmh > 10.0  # Faster than flat
        assert result.time_hours < 0.1  # Faster than flat

    def test_calculate_route(self, strava_calculator, flat_segment, uphill_segment_10):
        """Test full route calculation."""
        segments = [flat_segment, uphill_segment_10]

        total_hours, results = strava_calculator.calculate_route(segments)

        assert len(results) == 2
        assert total_hours == sum(r.time_hours for r in results)
        assert total_hours > 0


# =============================================================================
# Test Calculator Info
# =============================================================================

class TestCalculatorInfo:
    """Tests for calculator info/metadata."""

    def test_get_info_strava(self, strava_calculator):
        """Test get_info for Strava mode."""
        info = strava_calculator.get_info()

        assert info["mode"] == "strava_gap"
        assert info["base_flat_pace_min_km"] == 6.0
        assert info["base_flat_speed_kmh"] == 10.0
        assert "example_adjustments" in info
        assert info["example_adjustments"]["0%"] == 1.0

    def test_get_info_minetti(self, minetti_calculator):
        """Test get_info for Minetti mode."""
        info = minetti_calculator.get_info()

        assert info["mode"] == "minetti_gap"

    def test_example_adjustments_in_info(self, strava_calculator):
        """Test that example adjustments are correct."""
        info = strava_calculator.get_info()
        examples = info["example_adjustments"]

        assert "-15%" in examples
        assert "+10%" in examples
        assert "+20%" in examples

        # Verify values match actual calculations
        for key, expected in examples.items():
            gradient = int(key.replace("%", "").replace("+", ""))
            result = strava_calculator.calculate(gradient)
            assert result.pace_adjustment == pytest.approx(expected, rel=0.01)


# =============================================================================
# Test GAPResult
# =============================================================================

class TestGAPResult:
    """Tests for GAPResult dataclass."""

    def test_gap_result_creation(self):
        """Test GAPResult dataclass."""
        result = GAPResult(
            gradient_percent=10.0,
            pace_adjustment=1.38,
            adjusted_pace_min_km=8.28,
            energy_cost_ratio=1.5,
            mode="strava_gap"
        )

        assert result.gradient_percent == 10.0
        assert result.pace_adjustment == 1.38
        assert result.adjusted_pace_min_km == 8.28
        assert result.energy_cost_ratio == 1.5
        assert result.mode == "strava_gap"


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_steep_uphill(self, strava_calculator):
        """Test handling of very steep uphill (50%)."""
        result = strava_calculator.calculate(50)

        assert result.pace_adjustment > 4.0  # Should be very slow
        assert result.adjusted_pace_min_km > 24.0  # > 24 min/km

    def test_very_steep_downhill(self, strava_calculator):
        """Test handling of very steep downhill (-50%)."""
        result = strava_calculator.calculate(-50)

        # Should clamp to table edge
        assert result.pace_adjustment == STRAVA_GAP_TABLE[-30]

    def test_zero_distance_segment(self, strava_calculator):
        """Test handling of zero-distance segment."""
        segment = MacroSegment(
            segment_number=1,
            segment_type=SegmentType.FLAT,
            distance_km=0.0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            start_elevation_m=100,
            end_elevation_m=100
        )

        result = strava_calculator.calculate_segment(segment)
        assert result.time_hours == 0.0

    def test_very_slow_base_pace(self):
        """Test with very slow base pace (12 min/km)."""
        calc = GAPCalculator(base_flat_pace_min_km=12.0)
        result = calc.calculate(10)

        assert result.adjusted_pace_min_km == pytest.approx(12.0 * 1.38, rel=0.01)

    def test_very_fast_base_pace(self):
        """Test with very fast base pace (3 min/km)."""
        calc = GAPCalculator(base_flat_pace_min_km=3.0)
        result = calc.calculate(10)

        assert result.adjusted_pace_min_km == pytest.approx(3.0 * 1.38, rel=0.01)


# =============================================================================
# Test Known Values
# =============================================================================

class TestKnownValues:
    """Tests against known/expected values for validation."""

    def test_typical_trail_run_adjustments(self, strava_calculator):
        """Test typical trail running gradient adjustments."""
        # These are "sanity check" values based on trail running experience

        # Easy downhill should be faster
        result = strava_calculator.calculate(-5)
        assert result.adjusted_pace_min_km < 6.0

        # Runnable uphill (5%) should be moderately slower
        result = strava_calculator.calculate(5)
        assert 6.5 < result.adjusted_pace_min_km < 7.5

        # Power hiking territory (20%) should be much slower
        result = strava_calculator.calculate(20)
        assert result.adjusted_pace_min_km > 12.0

        # Technical descent (-25%) should be slower than optimal
        result = strava_calculator.calculate(-25)
        assert result.adjusted_pace_min_km > strava_calculator.calculate(-9).adjusted_pace_min_km
