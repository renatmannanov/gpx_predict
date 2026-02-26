"""
Tests for TrailRunService.

Tests the main orchestrator for trail running predictions.
"""

import pytest
from unittest.mock import MagicMock

from app.features.trail_run import TrailRunService, TrailRunResult
from app.features.trail_run.calculators import GAPMode, MovementMode
from app.shared.constants import DEFAULT_HIKE_THRESHOLD_PERCENT


# =============================================================================
# Test Data
# =============================================================================

# Simple route with flat, uphill, and downhill segments
SIMPLE_ROUTE_POINTS = [
    # Flat start
    (43.23, 76.94, 1000),
    (43.231, 76.941, 1000),
    # Moderate uphill (10%)
    (43.232, 76.942, 1010),
    (43.233, 76.943, 1020),
    (43.234, 76.944, 1050),
    (43.235, 76.945, 1100),
    # Steep uphill (30%) - should trigger hiking
    (43.236, 76.946, 1200),
    (43.237, 76.947, 1350),
    # Downhill
    (43.238, 76.948, 1300),
    (43.239, 76.949, 1200),
    (43.240, 76.950, 1100),
]

# Route with only moderate grades (all runnable)
RUNNABLE_ROUTE_POINTS = [
    (43.23, 76.94, 1000),
    (43.231, 76.941, 1010),
    (43.232, 76.942, 1020),
    (43.233, 76.943, 1030),
    (43.234, 76.944, 1020),
    (43.235, 76.945, 1010),
    (43.236, 76.946, 1000),
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_run_profile():
    """Create a mock UserRunProfile."""
    profile = MagicMock()
    profile.avg_flat_pace_min_km = 5.5
    profile.total_activities = 15
    profile.walk_threshold_percent = DEFAULT_HIKE_THRESHOLD_PERCENT

    # 7-category paces
    profile.avg_steep_downhill_pace_min_km = 5.0
    profile.avg_moderate_downhill_pace_min_km = 5.2
    profile.avg_gentle_downhill_pace_min_km = 5.3
    profile.avg_gentle_uphill_pace_min_km = 6.5
    profile.avg_moderate_uphill_pace_min_km = 8.0
    profile.avg_steep_uphill_pace_min_km = 11.0

    profile.has_profile_data = True
    profile.has_extended_gradient_data = True

    # Return enough samples for personalization
    profile.get_sample_count.return_value = 10
    profile.get_sample_count_extended.return_value = 10

    # No 11-category JSON data (use legacy 7-cat)
    profile.gradient_paces = None

    # Percentile data not available (falls back to avg)
    profile.get_percentile.return_value = None
    profile.get_pace_for_category.side_effect = lambda cat: {
        "steep_downhill": 5.0,
        "moderate_downhill": 5.2,
        "gentle_downhill": 5.3,
        "flat": 5.5,
        "gentle_uphill": 6.5,
        "moderate_uphill": 8.0,
        "steep_uphill": 11.0,
    }.get(cat)

    return profile


@pytest.fixture
def mock_hike_profile():
    """Create a mock UserPerformanceProfile."""
    profile = MagicMock()
    profile.avg_flat_pace_min_km = 12.0  # Hiking pace
    profile.total_activities_analyzed = 8

    profile.avg_steep_downhill_pace_min_km = 10.0
    profile.avg_moderate_downhill_pace_min_km = 11.0
    profile.avg_gentle_downhill_pace_min_km = 11.5
    profile.avg_gentle_uphill_pace_min_km = 14.0
    profile.avg_moderate_uphill_pace_min_km = 18.0
    profile.avg_steep_uphill_pace_min_km = 25.0

    profile.has_split_data = True
    profile.has_extended_gradient_data = True

    # Sample counts for personalization
    profile.get_sample_count.return_value = 10
    profile.get_sample_count_extended.return_value = 10

    # No 11-category JSON data
    profile.gradient_paces = None

    # Percentile data not available
    profile.get_percentile.return_value = None
    profile.get_pace_for_category.side_effect = lambda cat: {
        "steep_downhill": 10.0,
        "moderate_downhill": 11.0,
        "gentle_downhill": 11.5,
        "flat": 12.0,
        "gentle_uphill": 14.0,
        "moderate_uphill": 18.0,
        "steep_uphill": 25.0,
    }.get(cat)

    return profile


# =============================================================================
# Test Initialization
# =============================================================================

class TestInitialization:
    """Tests for service initialization."""

    def test_init_default(self):
        """Test default initialization."""
        service = TrailRunService()

        assert service.gap_mode == GAPMode.STRAVA
        assert service.flat_pace == 6.0  # Default
        assert service._run_pers is None
        assert service._hike_pers is None

    def test_init_with_custom_pace(self):
        """Test initialization with custom flat pace."""
        service = TrailRunService(flat_pace_min_km=5.0)

        assert service.flat_pace == 5.0

    def test_init_with_minetti_mode(self):
        """Test initialization with Minetti GAP mode."""
        service = TrailRunService(gap_mode=GAPMode.MINETTI)

        assert service.gap_mode == GAPMode.MINETTI

    def test_init_pace_from_profile(self, mock_run_profile):
        """Flat pace is set explicitly by caller, profile is for personalization."""
        service = TrailRunService(
            flat_pace_min_km=6.0,
            run_profile=mock_run_profile
        )

        # Service uses the explicitly provided flat_pace
        assert service.flat_pace == 6.0

    def test_init_with_fatigue(self):
        """Test initialization with fatigue enabled."""
        service = TrailRunService(apply_fatigue=True)

        assert service._apply_fatigue is True
        assert service._fatigue_service.enabled is True

    def test_init_with_dynamic_threshold(self):
        """Test initialization with dynamic threshold."""
        service = TrailRunService(apply_dynamic_threshold=True)

        assert service._threshold_service.dynamic is True

    def test_init_threshold_override(self):
        """Test walk threshold override."""
        service = TrailRunService(walk_threshold_override=20.0)

        assert service._threshold_service.base_uphill_threshold == 20.0


# =============================================================================
# Test Route Calculation
# =============================================================================

class TestRouteCalculation:
    """Tests for route calculation."""

    def test_calculate_simple_route(self):
        """Test calculation on simple route."""
        service = TrailRunService(flat_pace_min_km=6.0)
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        assert isinstance(result, TrailRunResult)
        assert len(result.segments) > 0
        assert result.summary.total_distance_km > 0
        assert result.totals["all_run_strava"] > 0
        assert result.totals["combined"] > 0

    def test_calculate_all_runnable_route(self):
        """Test route with only runnable grades."""
        service = TrailRunService(flat_pace_min_km=6.0)
        result = service.calculate_route(RUNNABLE_ROUTE_POINTS)

        # All segments should be running
        for seg in result.segments:
            # With default 30% threshold, moderate grades should be runnable
            if seg.segment.gradient_percent < 30:
                assert seg.movement.mode == MovementMode.RUN

    def test_calculate_with_fatigue(self):
        """Test that fatigue increases total time."""
        service_no_fatigue = TrailRunService(flat_pace_min_km=6.0, apply_fatigue=False)
        service_fatigue = TrailRunService(flat_pace_min_km=6.0, apply_fatigue=True)

        result_no_fatigue = service_no_fatigue.calculate_route(SIMPLE_ROUTE_POINTS)
        result_fatigue = service_fatigue.calculate_route(SIMPLE_ROUTE_POINTS)

        # Fatigue should add time (for short routes, might be minimal)
        assert result_fatigue.totals["combined"] >= result_no_fatigue.totals["combined"]

    def test_calculate_totals_include_both_gap_modes(self):
        """Both Strava and Minetti GAP should be in totals."""
        service = TrailRunService(flat_pace_min_km=6.0)
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        assert "all_run_strava" in result.totals
        assert "all_run_minetti" in result.totals
        assert "combined" in result.totals

    def test_summary_distance_matches_segments(self):
        """Summary distance should match sum of segments."""
        service = TrailRunService()
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        segment_total = sum(s.segment.distance_km for s in result.segments)
        assert result.summary.total_distance_km == pytest.approx(segment_total, rel=0.01)

    def test_run_hike_distance_sum(self):
        """Running + hiking distance should equal total."""
        service = TrailRunService()
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        total = result.summary.running_distance_km + result.summary.hiking_distance_km
        assert total == pytest.approx(result.summary.total_distance_km, rel=0.01)


# =============================================================================
# Test Personalization
# =============================================================================

class TestPersonalization:
    """Tests for personalized predictions."""

    def test_with_run_profile(self, mock_run_profile):
        """Test calculation with run profile."""
        service = TrailRunService(run_profile=mock_run_profile)
        result = service.calculate_route(RUNNABLE_ROUTE_POINTS)

        assert result.personalized is True
        assert result.run_activities_used == 15
        assert "run_personalized" in result.totals

    def test_with_hike_profile(self, mock_hike_profile):
        """Test calculation with hike profile."""
        service = TrailRunService(hike_profile=mock_hike_profile)
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        # Hike profile used for hiking segments
        assert result.hike_activities_used == 8

    def test_with_both_profiles(self, mock_run_profile, mock_hike_profile):
        """Test calculation with both profiles."""
        service = TrailRunService(
            run_profile=mock_run_profile,
            hike_profile=mock_hike_profile
        )
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        assert result.personalized is True
        assert result.total_activities_used == 15 + 8

    def test_faster_pace_reduces_time(self):
        """Faster flat pace should reduce total time."""
        service_slow = TrailRunService(flat_pace_min_km=7.0)
        service_fast = TrailRunService(flat_pace_min_km=5.0)

        result_slow = service_slow.calculate_route(RUNNABLE_ROUTE_POINTS)
        result_fast = service_fast.calculate_route(RUNNABLE_ROUTE_POINTS)

        assert result_fast.totals["combined"] < result_slow.totals["combined"]


# =============================================================================
# Test Threshold Detection
# =============================================================================

class TestThresholdDetection:
    """Tests for run/hike threshold detection."""

    def test_default_threshold(self):
        """Default threshold should be 30%."""
        service = TrailRunService()

        assert service._threshold_service.base_uphill_threshold == DEFAULT_HIKE_THRESHOLD_PERCENT

    def test_threshold_from_profile(self, mock_run_profile):
        """Threshold should come from profile if available."""
        mock_run_profile.walk_threshold_percent = 22.0
        service = TrailRunService(run_profile=mock_run_profile)

        assert service._threshold_service.base_uphill_threshold == 22.0

    def test_threshold_override_beats_profile(self, mock_run_profile):
        """Manual override should beat profile threshold."""
        mock_run_profile.walk_threshold_percent = 22.0
        service = TrailRunService(
            run_profile=mock_run_profile,
            walk_threshold_override=18.0
        )

        assert service._threshold_service.base_uphill_threshold == 18.0


# =============================================================================
# Test Result Structure
# =============================================================================

class TestResultStructure:
    """Tests for result data structure."""

    def test_result_has_all_fields(self):
        """Result should have all required fields."""
        service = TrailRunService()
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        assert hasattr(result, 'segments')
        assert hasattr(result, 'totals')
        assert hasattr(result, 'summary')
        assert hasattr(result, 'personalized')
        assert hasattr(result, 'walk_threshold_used')
        assert hasattr(result, 'gap_mode')
        assert hasattr(result, 'fatigue_applied')

    def test_segment_has_movement_info(self):
        """Each segment should have movement info."""
        service = TrailRunService()
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        for seg in result.segments:
            assert hasattr(seg, 'movement')
            assert seg.movement.mode in [MovementMode.RUN, MovementMode.HIKE]
            assert seg.movement.confidence >= 0
            assert seg.movement.confidence <= 1

    def test_to_dict(self):
        """Result should convert to dict properly."""
        service = TrailRunService()
        result = service.calculate_route(SIMPLE_ROUTE_POINTS)

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "segments" in result_dict
        assert "totals" in result_dict
        assert "summary" in result_dict

    def test_get_info(self):
        """Service info should be accessible."""
        service = TrailRunService(
            gap_mode=GAPMode.MINETTI,
            flat_pace_min_km=5.5,
            apply_fatigue=True
        )

        info = service.get_info()

        assert info["gap_mode"] == "minetti_gap"
        assert info["flat_pace_min_km"] == 5.5
        assert info["fatigue_enabled"] is True


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_short_route(self):
        """Test with very short route."""
        short_points = [
            (43.23, 76.94, 1000),
            (43.231, 76.941, 1010),
        ]
        service = TrailRunService()
        result = service.calculate_route(short_points)

        assert result.summary.total_distance_km > 0
        assert result.totals["combined"] > 0

    def test_flat_route(self):
        """Test completely flat route."""
        flat_points = [
            (43.23, 76.94, 1000),
            (43.231, 76.941, 1000),
            (43.232, 76.942, 1000),
            (43.233, 76.943, 1000),
        ]
        service = TrailRunService()
        result = service.calculate_route(flat_points)

        # All should be running
        assert result.summary.hiking_distance_km == pytest.approx(0, abs=0.1)

    def test_all_hiking_route(self):
        """Test route that's all hiking (very steep)."""
        steep_points = [
            (43.23, 76.94, 1000),
            (43.2301, 76.9401, 1100),  # Very steep
            (43.2302, 76.9402, 1200),
            (43.2303, 76.9403, 1350),
        ]
        service = TrailRunService(walk_threshold_override=15.0)  # Low threshold
        result = service.calculate_route(steep_points)

        # Most/all should be hiking due to low threshold
        assert result.summary.hiking_distance_km > 0
