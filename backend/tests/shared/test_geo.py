"""
Tests for shared geographic functions.

Tests the haversine distance and gradient calculations.
"""

import pytest
import math

from app.shared.geo import (
    haversine,
    calculate_gradient,
    gradient_to_percent,
    gradient_to_degrees,
    calculate_total_distance,
    EARTH_RADIUS_KM,
)


# =============================================================================
# Test Haversine Distance
# =============================================================================

class TestHaversine:
    """Tests for haversine function."""

    def test_same_point(self):
        """Distance between same point should be 0."""
        dist = haversine(43.0, 76.0, 43.0, 76.0)
        assert dist == 0.0

    def test_known_distance_almaty_astana(self):
        """Test with known distance (Almaty to Astana ~974km)."""
        # Almaty: 43.238949, 76.945465
        # Astana: 51.169392, 71.449074
        dist = haversine(43.238949, 76.945465, 51.169392, 71.449074)
        assert 950 < dist < 1000

    def test_small_distance(self):
        """Test small distance calculation."""
        # Two points ~100 meters apart
        # 0.001 degree latitude ≈ 111 meters
        dist = haversine(43.0, 76.0, 43.001, 76.0)
        assert 0.1 < dist < 0.15  # ~111 meters = 0.111 km

    def test_symmetry(self):
        """Distance A->B should equal B->A."""
        dist_ab = haversine(43.0, 76.0, 44.0, 77.0)
        dist_ba = haversine(44.0, 77.0, 43.0, 76.0)
        assert dist_ab == pytest.approx(dist_ba, rel=0.0001)

    def test_east_west_distance(self):
        """Test purely east-west distance."""
        # At equator, 1 degree longitude ≈ 111 km
        dist = haversine(0.0, 0.0, 0.0, 1.0)
        assert 110 < dist < 112

    def test_north_south_distance(self):
        """Test purely north-south distance."""
        # 1 degree latitude ≈ 111 km everywhere
        dist = haversine(0.0, 0.0, 1.0, 0.0)
        assert 110 < dist < 112

    def test_earth_radius_constant(self):
        """Verify Earth radius constant is correct."""
        assert EARTH_RADIUS_KM == 6371.0

    def test_negative_coordinates(self):
        """Test with negative (southern/western) coordinates."""
        # Sydney: -33.8688, 151.2093
        # Melbourne: -37.8136, 144.9631
        dist = haversine(-33.8688, 151.2093, -37.8136, 144.9631)
        assert 700 < dist < 900  # ~714 km actual

    def test_cross_hemisphere(self):
        """Test distance across hemispheres."""
        # North to South
        dist = haversine(45.0, 0.0, -45.0, 0.0)
        # 90 degrees = ~10,000 km (quarter of equator)
        assert 9900 < dist < 10100


# =============================================================================
# Test Calculate Gradient
# =============================================================================

class TestCalculateGradient:
    """Tests for calculate_gradient function."""

    def test_zero_distance(self):
        """Zero distance should return 0 gradient."""
        grad = calculate_gradient(0.0, 100.0)
        assert grad == 0.0

    def test_10_percent(self):
        """100m rise over 1km = 10% = 0.10."""
        grad = calculate_gradient(1.0, 100.0)
        assert abs(grad - 0.10) < 0.001

    def test_flat(self):
        """Zero elevation change should be 0 gradient."""
        grad = calculate_gradient(1.0, 0.0)
        assert grad == 0.0

    def test_negative_gradient(self):
        """Negative elevation should give negative gradient."""
        grad = calculate_gradient(1.0, -100.0)
        assert grad == pytest.approx(-0.10, rel=0.001)

    def test_steep_gradient(self):
        """Test steep gradient calculation."""
        # 500m over 1km = 50%
        grad = calculate_gradient(1.0, 500.0)
        assert grad == pytest.approx(0.50, rel=0.001)

    def test_formula(self):
        """Verify gradient = elevation_diff / (distance_km * 1000)."""
        for dist, elev in [(1.0, 100), (2.0, 200), (0.5, 50)]:
            expected = elev / (dist * 1000)
            actual = calculate_gradient(dist, elev)
            assert actual == pytest.approx(expected, rel=0.001)


# =============================================================================
# Test Gradient Conversions
# =============================================================================

class TestGradientConversions:
    """Tests for gradient conversion functions."""

    def test_gradient_to_percent(self):
        """Test decimal to percent conversion."""
        assert gradient_to_percent(0.10) == pytest.approx(10.0, rel=0.001)
        assert gradient_to_percent(0.25) == pytest.approx(25.0, rel=0.001)
        assert gradient_to_percent(-0.15) == pytest.approx(-15.0, rel=0.001)

    def test_gradient_to_degrees_flat(self):
        """Flat gradient should be 0 degrees."""
        assert gradient_to_degrees(0.0) == pytest.approx(0.0, rel=0.001)

    def test_gradient_to_degrees_45(self):
        """100% gradient (1.0) should be 45 degrees."""
        assert gradient_to_degrees(1.0) == pytest.approx(45.0, rel=0.001)

    def test_gradient_to_degrees_typical(self):
        """Test typical hiking gradients in degrees."""
        # 10% ≈ 5.7 degrees
        assert gradient_to_degrees(0.10) == pytest.approx(5.71, rel=0.02)

        # 20% ≈ 11.3 degrees
        assert gradient_to_degrees(0.20) == pytest.approx(11.31, rel=0.02)

        # 30% ≈ 16.7 degrees
        assert gradient_to_degrees(0.30) == pytest.approx(16.70, rel=0.02)

    def test_gradient_to_degrees_formula(self):
        """Verify formula: degrees = atan(gradient) * 180/pi."""
        for grad in [0.0, 0.10, 0.25, 0.50, 1.0]:
            expected = math.degrees(math.atan(grad))
            actual = gradient_to_degrees(grad)
            assert actual == pytest.approx(expected, rel=0.001)


# =============================================================================
# Test Calculate Total Distance
# =============================================================================

class TestCalculateTotalDistance:
    """Tests for calculate_total_distance function."""

    def test_single_point(self):
        """Single point should have zero distance."""
        points = [(43.0, 76.0, 1000)]
        dist = calculate_total_distance(points)
        assert dist == 0.0

    def test_two_points(self):
        """Two points should return simple distance."""
        points = [
            (43.0, 76.0, 1000),
            (43.001, 76.0, 1000),
        ]
        dist = calculate_total_distance(points)
        assert 0.1 < dist < 0.15  # ~111 meters

    def test_multiple_points(self):
        """Multiple points should sum distances."""
        points = [
            (43.0, 76.0, 1000),
            (43.001, 76.0, 1000),  # ~111m
            (43.002, 76.0, 1000),  # ~111m more
            (43.003, 76.0, 1000),  # ~111m more
        ]
        dist = calculate_total_distance(points)
        assert 0.3 < dist < 0.4  # ~333 meters

    def test_round_trip(self):
        """Round trip should be ~2x one way."""
        points = [
            (43.0, 76.0, 1000),
            (43.01, 76.0, 1000),  # 1km north
            (43.0, 76.0, 1000),   # Back to start
        ]
        dist = calculate_total_distance(points)
        one_way = haversine(43.0, 76.0, 43.01, 76.0)
        assert dist == pytest.approx(2 * one_way, rel=0.01)

    def test_elevation_ignored(self):
        """Elevation should not affect horizontal distance calculation."""
        # Same lat/lon but different elevations
        points_flat = [
            (43.0, 76.0, 1000),
            (43.01, 76.0, 1000),
        ]
        points_climb = [
            (43.0, 76.0, 1000),
            (43.01, 76.0, 2000),  # 1000m higher
        ]
        dist_flat = calculate_total_distance(points_flat)
        dist_climb = calculate_total_distance(points_climb)
        assert dist_flat == pytest.approx(dist_climb, rel=0.001)

    def test_empty_list(self):
        """Empty list should return zero."""
        dist = calculate_total_distance([])
        assert dist == 0.0


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_haversine_poles(self):
        """Test distance from North Pole to South Pole."""
        dist = haversine(90.0, 0.0, -90.0, 0.0)
        # Half circumference ≈ 20,000 km
        assert 19900 < dist < 20100

    def test_haversine_antimeridian(self):
        """Test distance across the antimeridian (180° longitude)."""
        dist = haversine(0.0, 179.0, 0.0, -179.0)
        # 2 degrees at equator ≈ 222 km
        assert 220 < dist < 225

    def test_gradient_very_small_distance(self):
        """Very small distance should not cause division issues."""
        grad = calculate_gradient(0.0001, 10.0)
        # This would be a very steep gradient
        assert grad > 0

    def test_gradient_negative_distance(self):
        """Negative distance should still work (though unusual)."""
        grad = calculate_gradient(-1.0, 100.0)
        # Returns 0 because distance <= 0
        assert grad == 0.0
