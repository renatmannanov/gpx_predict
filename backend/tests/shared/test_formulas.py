"""
Tests for shared formulas module.

Tests the mathematical formulas used across calculators.
"""

import pytest
import math

from app.shared.formulas import tobler_hiking_speed, naismith_base_time


# =============================================================================
# Test Tobler Hiking Speed
# =============================================================================

class TestToblerHikingSpeed:
    """Tests for tobler_hiking_speed function."""

    def test_optimal_gradient(self):
        """Speed should be max (~6 km/h) at -5% gradient (slight downhill)."""
        speed = tobler_hiking_speed(-0.05)
        assert abs(speed - 6.0) < 0.01

    def test_flat_terrain(self):
        """Speed should be ~5 km/h on flat terrain."""
        speed = tobler_hiking_speed(0.0)
        # Flat is slightly slower than optimal (-5%)
        assert 4.9 < speed < 5.1

    def test_steep_uphill(self):
        """Speed should decrease significantly on steep uphill."""
        speed_10 = tobler_hiking_speed(0.10)  # 10% grade
        speed_20 = tobler_hiking_speed(0.20)  # 20% grade

        assert speed_10 < 5.0  # Slower than flat
        assert speed_20 < speed_10  # Steeper = slower
        assert speed_20 < 3.0  # Significantly slower

    def test_steep_downhill(self):
        """Speed should decrease on steep downhill (braking)."""
        speed_optimal = tobler_hiking_speed(-0.05)  # Optimal
        speed_steep = tobler_hiking_speed(-0.20)  # -20% grade

        assert speed_steep < speed_optimal  # Slower than optimal
        assert speed_steep < 4.5  # Slower due to braking

    def test_symmetry_around_optimal(self):
        """Speed should decrease both uphill and downhill from optimal."""
        speed_optimal = tobler_hiking_speed(-0.05)

        # Check various gradients
        for gradient in [-0.15, -0.10, 0.0, 0.05, 0.10, 0.15]:
            speed = tobler_hiking_speed(gradient)
            assert speed <= speed_optimal, f"Speed at {gradient*100}% should be <= optimal"

    def test_extreme_uphill(self):
        """Very steep uphill should still return positive speed."""
        speed = tobler_hiking_speed(0.50)  # 50% grade
        assert speed > 0
        assert speed < 2.0  # Very slow

    def test_extreme_downhill(self):
        """Very steep downhill should still return positive speed."""
        speed = tobler_hiking_speed(-0.50)  # -50% grade
        assert speed > 0
        assert speed < 3.0  # Slow due to braking

    def test_formula_matches_documentation(self):
        """Verify formula matches documented: v = 6 * exp(-3.5 * |s + 0.05|)."""
        for gradient in [-0.20, -0.10, -0.05, 0.0, 0.10, 0.20]:
            expected = 6.0 * math.exp(-3.5 * abs(gradient + 0.05))
            actual = tobler_hiking_speed(gradient)
            assert actual == pytest.approx(expected, rel=0.001)


# =============================================================================
# Test Naismith Base Time
# =============================================================================

class TestNaismithBaseTime:
    """Tests for naismith_base_time function."""

    def test_flat_5km(self):
        """5km flat should take 1 hour (at 5 km/h)."""
        time = naismith_base_time(5.0, 0.0)
        assert abs(time - 1.0) < 0.01

    def test_flat_10km(self):
        """10km flat should take 2 hours."""
        time = naismith_base_time(10.0, 0.0)
        assert abs(time - 2.0) < 0.01

    def test_with_elevation_600m(self):
        """600m elevation gain should add 1 hour."""
        time_flat = naismith_base_time(5.0, 0.0)  # 1 hour
        time_with_climb = naismith_base_time(5.0, 600.0)  # 1 + 1 = 2 hours

        assert time_with_climb == pytest.approx(2.0, rel=0.01)
        assert time_with_climb - time_flat == pytest.approx(1.0, rel=0.01)

    def test_10km_600m(self):
        """10km + 600m should take 3 hours."""
        time = naismith_base_time(10.0, 600.0)
        # 10km/5 = 2h + 600m/600 = 1h = 3h
        assert time == pytest.approx(3.0, rel=0.01)

    def test_zero_distance(self):
        """Zero distance should return only ascent time."""
        time = naismith_base_time(0.0, 600.0)
        assert time == pytest.approx(1.0, rel=0.01)  # Just the 600m climb

    def test_zero_elevation(self):
        """Zero elevation should return only horizontal time."""
        time = naismith_base_time(10.0, 0.0)
        assert time == pytest.approx(2.0, rel=0.01)

    def test_proportional_increase(self):
        """Time should increase proportionally with distance and elevation."""
        base = naismith_base_time(5.0, 300.0)
        double_distance = naismith_base_time(10.0, 300.0)
        double_elevation = naismith_base_time(5.0, 600.0)
        double_both = naismith_base_time(10.0, 600.0)

        # Base: 5/5 + 300/600 = 1 + 0.5 = 1.5h
        assert base == pytest.approx(1.5, rel=0.01)

        # Double distance: 10/5 + 300/600 = 2 + 0.5 = 2.5h
        assert double_distance == pytest.approx(2.5, rel=0.01)

        # Double elevation: 5/5 + 600/600 = 1 + 1 = 2h
        assert double_elevation == pytest.approx(2.0, rel=0.01)

        # Double both: 10/5 + 600/600 = 2 + 1 = 3h
        assert double_both == pytest.approx(3.0, rel=0.01)

    def test_formula_matches_documentation(self):
        """Verify formula: horizontal_time + ascent_time."""
        for distance, elevation in [(5, 300), (10, 600), (15, 900)]:
            expected = distance / 5.0 + elevation / 600.0
            actual = naismith_base_time(float(distance), float(elevation))
            assert actual == pytest.approx(expected, rel=0.001)


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_tobler_zero_gradient(self):
        """Zero gradient should work without errors."""
        speed = tobler_hiking_speed(0.0)
        assert speed > 0

    def test_naismith_zeros(self):
        """All zeros should return zero time."""
        time = naismith_base_time(0.0, 0.0)
        assert time == 0.0

    def test_tobler_very_small_gradient(self):
        """Very small gradients should not cause issues."""
        speed = tobler_hiking_speed(0.001)
        assert speed > 0
        assert speed < 6.0

    def test_naismith_small_values(self):
        """Small but non-zero values should work."""
        time = naismith_base_time(0.1, 10.0)
        assert time > 0


# =============================================================================
# Test Known Values
# =============================================================================

class TestKnownValues:
    """Tests against known/expected values for validation."""

    def test_tobler_typical_hiking_speeds(self):
        """Verify typical hiking speeds match expectations."""
        # These are sanity checks based on hiking experience

        # Flat terrain: about 5 km/h
        assert 4.8 < tobler_hiking_speed(0.0) < 5.2

        # Slight downhill: about 6 km/h (fastest)
        assert tobler_hiking_speed(-0.05) == pytest.approx(6.0, rel=0.01)

        # 10% uphill: about 3-4 km/h
        speed_10up = tobler_hiking_speed(0.10)
        assert 3.0 < speed_10up < 4.5

        # 10% downhill: about 5-5.5 km/h
        speed_10down = tobler_hiking_speed(-0.10)
        assert 5.0 < speed_10down < 6.0

    def test_naismith_typical_hikes(self):
        """Verify typical hike times match expectations."""
        # A 10km hike with 500m elevation gain
        # Should take: 10/5 + 500/600 = 2 + 0.83 = 2.83 hours
        time = naismith_base_time(10.0, 500.0)
        assert time == pytest.approx(2.83, rel=0.01)

        # A 20km hike with 1000m elevation gain
        # Should take: 20/5 + 1000/600 = 4 + 1.67 = 5.67 hours
        time = naismith_base_time(20.0, 1000.0)
        assert time == pytest.approx(5.67, rel=0.01)
