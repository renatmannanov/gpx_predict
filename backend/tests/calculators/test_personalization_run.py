"""
Tests for RunPersonalizationService.

Tests running personalization using GAP calculator as fallback.
"""

import pytest
from unittest.mock import MagicMock

from app.services.calculators.base import MacroSegment, SegmentType
from app.features.trail_run.calculators.personalization import (
    RunPersonalizationService,
    DEFAULT_FLAT_PACE_MIN_KM,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_run_profile():
    """Create a mock UserRunProfile with full data."""
    profile = MagicMock()
    profile.avg_flat_pace_min_km = 6.0  # 10 km/h
    profile.total_activities = 10

    # 7-category paces
    profile.avg_steep_downhill_pace_min_km = 5.5
    profile.avg_moderate_downhill_pace_min_km = 5.8
    profile.avg_gentle_downhill_pace_min_km = 5.9
    profile.avg_gentle_uphill_pace_min_km = 7.0
    profile.avg_moderate_uphill_pace_min_km = 8.5
    profile.avg_steep_uphill_pace_min_km = 12.0

    profile.walk_threshold_percent = 25.0

    return profile


@pytest.fixture
def mock_minimal_profile():
    """Create a mock profile with only flat pace."""
    profile = MagicMock()
    profile.avg_flat_pace_min_km = 6.0
    profile.total_activities = 5

    # No extended data
    profile.avg_steep_downhill_pace_min_km = None
    profile.avg_moderate_downhill_pace_min_km = None
    profile.avg_gentle_downhill_pace_min_km = None
    profile.avg_gentle_uphill_pace_min_km = None
    profile.avg_moderate_uphill_pace_min_km = None
    profile.avg_steep_uphill_pace_min_km = None

    profile.walk_threshold_percent = 25.0

    return profile


@pytest.fixture
def flat_segment():
    """Create a flat segment for testing."""
    return MacroSegment(
        segment_number=1,
        segment_type=SegmentType.FLAT,
        distance_km=1.0,
        elevation_gain_m=10,
        elevation_loss_m=10,
        start_elevation_m=100,
        end_elevation_m=100
    )


@pytest.fixture
def moderate_uphill_segment():
    """Create a moderate uphill segment (~10% gradient)."""
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
def steep_uphill_segment():
    """Create a steep uphill segment (~20% gradient)."""
    return MacroSegment(
        segment_number=3,
        segment_type=SegmentType.ASCENT,
        distance_km=1.0,
        elevation_gain_m=200,
        elevation_loss_m=0,
        start_elevation_m=100,
        end_elevation_m=300
    )


@pytest.fixture
def gentle_downhill_segment():
    """Create a gentle downhill segment (~-5% gradient)."""
    return MacroSegment(
        segment_number=4,
        segment_type=SegmentType.DESCENT,
        distance_km=1.0,
        elevation_gain_m=0,
        elevation_loss_m=50,
        start_elevation_m=150,
        end_elevation_m=100
    )


# =============================================================================
# Test Initialization
# =============================================================================

class TestInitialization:
    """Tests for service initialization."""

    def test_init_with_profile(self, mock_run_profile):
        """Test initialization with a valid profile."""
        service = RunPersonalizationService(mock_run_profile)

        assert service.profile == mock_run_profile
        assert service.use_extended_gradients is True  # Default for running

    def test_init_extended_gradients_default_true(self, mock_run_profile):
        """Extended gradients should default to True for running."""
        service = RunPersonalizationService(mock_run_profile)

        assert service.use_extended_gradients is True

    def test_init_creates_gap_calculator(self, mock_run_profile):
        """GAP calculator should be created with profile's flat pace."""
        service = RunPersonalizationService(mock_run_profile)

        assert service._gap_calculator is not None
        # GAP calculator stores flat pace internally
        result = service._gap_calculator.calculate(0)  # flat gradient
        assert result.adjusted_pace_min_km == 6.0  # matches profile's flat pace


# =============================================================================
# Test Segment Calculation
# =============================================================================

class TestSegmentCalculation:
    """Tests for segment time calculation."""

    def test_calculate_flat_segment(self, mock_run_profile, flat_segment):
        """Test calculation for flat terrain with profile data."""
        service = RunPersonalizationService(mock_run_profile)
        result = service.calculate_segment(flat_segment, base_method="strava_gap")

        assert result.method_name == "strava_gap_personalized"
        assert result.speed_kmh == pytest.approx(10.0, rel=0.1)  # 60 / 6 min/km
        assert result.time_hours > 0

    def test_calculate_moderate_uphill(self, mock_run_profile, moderate_uphill_segment):
        """Test calculation for moderate uphill with profile data."""
        service = RunPersonalizationService(mock_run_profile)
        result = service.calculate_segment(moderate_uphill_segment, base_method="strava_gap")

        # Should use moderate_uphill pace (8.5 min/km = ~7.1 km/h)
        assert result.speed_kmh == pytest.approx(7.06, rel=0.1)

    def test_calculate_steep_uphill(self, mock_run_profile, steep_uphill_segment):
        """Test calculation for steep uphill with profile data."""
        service = RunPersonalizationService(mock_run_profile)
        result = service.calculate_segment(steep_uphill_segment, base_method="strava_gap")

        # Should use steep_uphill pace (12.0 min/km = 5 km/h)
        assert result.speed_kmh == pytest.approx(5.0, rel=0.1)

    def test_calculate_gentle_downhill(self, mock_run_profile, gentle_downhill_segment):
        """Test calculation for gentle downhill with profile data."""
        service = RunPersonalizationService(mock_run_profile)
        result = service.calculate_segment(gentle_downhill_segment, base_method="strava_gap")

        # Should use gentle_downhill pace (5.9 min/km = ~10.2 km/h)
        assert result.speed_kmh == pytest.approx(10.17, rel=0.1)


# =============================================================================
# Test GAP Fallback
# =============================================================================

class TestGAPFallback:
    """Tests for GAP calculator fallback when profile data missing."""

    def test_fallback_when_category_missing(self, mock_minimal_profile, moderate_uphill_segment):
        """Should fall back to GAP when extended gradient data is missing."""
        service = RunPersonalizationService(mock_minimal_profile)
        result = service.calculate_segment(moderate_uphill_segment, base_method="strava_gap")

        # Should use GAP estimation, not crash
        assert result.speed_kmh > 0
        assert result.time_hours > 0

    def test_fallback_uses_correct_gap_mode(self, mock_minimal_profile, moderate_uphill_segment):
        """Fallback should use Strava GAP mode."""
        service = RunPersonalizationService(mock_minimal_profile)
        result = service.calculate_segment(moderate_uphill_segment, base_method="strava_gap")

        # GAP at ~10% gradient with 6:00 base should give ~8:17 (1.38x)
        expected_speed = 60 / 8.28  # ~7.25 km/h
        assert result.speed_kmh == pytest.approx(expected_speed, rel=0.15)


# =============================================================================
# Test Route Calculation
# =============================================================================

class TestRouteCalculation:
    """Tests for full route calculation."""

    def test_calculate_route(
        self,
        mock_run_profile,
        flat_segment,
        moderate_uphill_segment,
        gentle_downhill_segment
    ):
        """Test full route calculation."""
        service = RunPersonalizationService(mock_run_profile)
        segments = [flat_segment, moderate_uphill_segment, gentle_downhill_segment]

        total_hours, results = service.calculate_route(segments, base_method="strava_gap")

        assert len(results) == 3
        assert total_hours > 0
        assert total_hours == pytest.approx(sum(r.time_hours for r in results), rel=0.001)


# =============================================================================
# Test Profile Validation
# =============================================================================

class TestProfileValidation:
    """Tests for profile validation."""

    def test_valid_profile(self, mock_run_profile):
        """Profile with flat pace and enough activities is valid."""
        assert RunPersonalizationService.is_profile_valid(mock_run_profile) is True

    def test_invalid_none(self):
        """None profile is invalid."""
        assert RunPersonalizationService.is_profile_valid(None) is False

    def test_invalid_no_flat_pace(self, mock_run_profile):
        """Profile without flat pace is invalid."""
        mock_run_profile.avg_flat_pace_min_km = None
        assert RunPersonalizationService.is_profile_valid(mock_run_profile) is False

    def test_invalid_no_activities(self, mock_run_profile):
        """Profile with zero activities is invalid."""
        mock_run_profile.total_activities = 0
        assert RunPersonalizationService.is_profile_valid(mock_run_profile) is False


# =============================================================================
# Test Profile Summary
# =============================================================================

class TestProfileSummary:
    """Tests for profile summary generation."""

    def test_summary_none_profile(self):
        """Should return empty dict for None profile."""
        summary = RunPersonalizationService.get_profile_summary(None)
        assert summary == {}

    def test_summary_basic(self, mock_run_profile):
        """Test basic summary fields."""
        mock_run_profile.has_profile_data = True
        mock_run_profile.has_extended_gradient_data = True

        summary = RunPersonalizationService.get_profile_summary(mock_run_profile)

        assert summary["activities_analyzed"] == 10
        assert summary["flat_pace_min_km"] == 6.0
        assert summary["walk_threshold_percent"] == 25.0

    def test_summary_with_extended(self, mock_run_profile):
        """Test summary with extended gradient data."""
        mock_run_profile.has_profile_data = True
        mock_run_profile.has_extended_gradient_data = True

        summary = RunPersonalizationService.get_profile_summary(
            mock_run_profile, include_extended=True
        )

        assert "extended_gradients" in summary
        ext = summary["extended_gradients"]
        assert ext["steep_downhill_pace"] == 5.5
        assert ext["moderate_uphill_pace"] == 8.5
        assert ext["steep_uphill_pace"] == 12.0


# =============================================================================
# Test Default Speed
# =============================================================================

class TestDefaultSpeed:
    """Tests for default speed behavior."""

    def test_default_speed_value(self, mock_run_profile):
        """Test default speed is correct."""
        service = RunPersonalizationService(mock_run_profile)

        assert service._get_default_speed() == 10.0  # 60 / 6 min/km

    def test_default_pace_constant(self):
        """Test default flat pace constant."""
        assert DEFAULT_FLAT_PACE_MIN_KM == 6.0
