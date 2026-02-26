"""
Tests for HikeRunThresholdService.

Tests the run vs walk decision logic for trail running.
"""

import pytest

from app.services.calculators.base import MacroSegment, SegmentType
from app.features.trail_run.calculators import (
    HikeRunThresholdService,
    HikeRunDecision,
    MovementMode,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def flat_segment():
    """Create a flat segment (0% gradient)."""
    return MacroSegment(
        segment_number=1,
        segment_type=SegmentType.FLAT,
        distance_km=1.0,
        elevation_gain_m=0,
        elevation_loss_m=0,
        start_elevation_m=1000,
        end_elevation_m=1000
    )


@pytest.fixture
def gentle_uphill_segment():
    """Create a gentle uphill segment (~10% gradient)."""
    return MacroSegment(
        segment_number=2,
        segment_type=SegmentType.ASCENT,
        distance_km=1.0,
        elevation_gain_m=100,
        elevation_loss_m=0,
        start_elevation_m=1000,
        end_elevation_m=1100
    )


@pytest.fixture
def steep_uphill_segment():
    """Create a steep uphill segment (~30% gradient)."""
    return MacroSegment(
        segment_number=3,
        segment_type=SegmentType.ASCENT,
        distance_km=1.0,
        elevation_gain_m=300,
        elevation_loss_m=0,
        start_elevation_m=1000,
        end_elevation_m=1300
    )


@pytest.fixture
def moderate_downhill_segment():
    """Create a moderate downhill segment (~-15% gradient)."""
    return MacroSegment(
        segment_number=4,
        segment_type=SegmentType.DESCENT,
        distance_km=1.0,
        elevation_gain_m=0,
        elevation_loss_m=150,
        start_elevation_m=1150,
        end_elevation_m=1000
    )


@pytest.fixture
def steep_downhill_segment():
    """Create a steep downhill segment (~-35% gradient)."""
    return MacroSegment(
        segment_number=5,
        segment_type=SegmentType.DESCENT,
        distance_km=1.0,
        elevation_gain_m=0,
        elevation_loss_m=350,
        start_elevation_m=1350,
        end_elevation_m=1000
    )


# =============================================================================
# Test Static Threshold Mode
# =============================================================================

class TestStaticThreshold:
    """Tests for static threshold mode (default)."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        service = HikeRunThresholdService()

        assert service.base_uphill_threshold == 30.0
        assert service.downhill_threshold == -30.0
        assert service.dynamic is False

    def test_custom_threshold(self):
        """Test custom threshold initialization."""
        service = HikeRunThresholdService(uphill_threshold=20.0)

        assert service.base_uphill_threshold == 20.0

    def test_flat_segment_should_run(self, flat_segment):
        """Flat terrain should be runnable."""
        service = HikeRunThresholdService()
        decision = service.decide(flat_segment)

        assert decision.mode == MovementMode.RUN
        assert decision.confidence >= 0.9

    def test_gentle_uphill_should_run(self, gentle_uphill_segment):
        """Gentle uphill (~10%) should be runnable with default threshold."""
        service = HikeRunThresholdService()
        decision = service.decide(gentle_uphill_segment)

        assert decision.mode == MovementMode.RUN
        assert "Runnable" in decision.reason

    def test_steep_uphill_should_hike(self, steep_uphill_segment):
        """Steep uphill (~30%) should trigger walking."""
        service = HikeRunThresholdService()
        decision = service.decide(steep_uphill_segment)

        assert decision.mode == MovementMode.HIKE
        assert "Steep uphill" in decision.reason

    def test_moderate_downhill_should_run(self, moderate_downhill_segment):
        """Moderate downhill (-15%) should be runnable."""
        service = HikeRunThresholdService()
        decision = service.decide(moderate_downhill_segment)

        assert decision.mode == MovementMode.RUN

    def test_steep_downhill_should_hike(self, steep_downhill_segment):
        """Very steep downhill (-35%) should trigger walking (technical)."""
        service = HikeRunThresholdService()
        decision = service.decide(steep_downhill_segment)

        assert decision.mode == MovementMode.HIKE
        assert "Technical descent" in decision.reason

    def test_threshold_boundary(self):
        """Test behavior at exact threshold boundary."""
        service = HikeRunThresholdService(uphill_threshold=25.0)

        # Just below threshold - should run
        segment_24 = MacroSegment(
            segment_number=1,
            segment_type=SegmentType.ASCENT,
            distance_km=1.0,
            elevation_gain_m=240,
            elevation_loss_m=0,
            start_elevation_m=1000,
            end_elevation_m=1240
        )
        decision = service.decide(segment_24)
        assert decision.mode == MovementMode.RUN

        # At threshold - should hike
        segment_25 = MacroSegment(
            segment_number=2,
            segment_type=SegmentType.ASCENT,
            distance_km=1.0,
            elevation_gain_m=250,
            elevation_loss_m=0,
            start_elevation_m=1000,
            end_elevation_m=1250
        )
        decision = service.decide(segment_25)
        assert decision.mode == MovementMode.HIKE


# =============================================================================
# Test Dynamic Threshold Mode
# =============================================================================

class TestDynamicThreshold:
    """Tests for dynamic threshold mode (fatigue-adjusted)."""

    def test_dynamic_mode_enabled(self):
        """Test dynamic mode initialization."""
        service = HikeRunThresholdService(dynamic=True)

        assert service.dynamic is True

    def test_no_fatigue_at_start(self):
        """No fatigue adjustment at start of race."""
        service = HikeRunThresholdService(uphill_threshold=35.0, dynamic=True)

        threshold = service.get_threshold(elapsed_hours=0)
        assert threshold == 35.0

    def test_fatigue_after_2_hours(self):
        """Threshold should decrease after 2 hours."""
        service = HikeRunThresholdService(uphill_threshold=35.0, dynamic=True)

        threshold = service.get_threshold(elapsed_hours=3.0)
        assert threshold < 35.0
        # After 1 hour past fatigue onset (2h): 35 - 1.5 = 33.5
        assert threshold == pytest.approx(33.5, rel=0.1)

    def test_fatigue_after_4_hours(self):
        """Threshold should decrease more after 4 hours."""
        service = HikeRunThresholdService(uphill_threshold=35.0, dynamic=True)

        threshold = service.get_threshold(elapsed_hours=4.0)
        # After 2 hours past fatigue onset: 35 - 3.0 = 32.0
        assert threshold < 33.0

    def test_minimum_threshold(self):
        """Threshold should not go below minimum."""
        service = HikeRunThresholdService(uphill_threshold=25.0, dynamic=True)

        threshold = service.get_threshold(elapsed_hours=10.0)
        assert threshold >= service.MIN_THRESHOLD

    def test_ultra_distance_adjustment(self):
        """Extra threshold reduction for ultra distances."""
        service = HikeRunThresholdService(uphill_threshold=35.0, dynamic=True)

        # 50k+ should have additional reduction
        threshold_50k = service.get_threshold(elapsed_hours=3.0, total_distance_km=60)
        threshold_normal = service.get_threshold(elapsed_hours=3.0, total_distance_km=30)

        assert threshold_50k < threshold_normal


# =============================================================================
# Test Route Processing
# =============================================================================

class TestRouteProcessing:
    """Tests for full route processing."""

    def test_process_route_mixed(
        self,
        flat_segment,
        gentle_uphill_segment,
        steep_uphill_segment,
        moderate_downhill_segment
    ):
        """Test processing a mixed route."""
        service = HikeRunThresholdService()
        segments = [
            flat_segment,
            gentle_uphill_segment,
            steep_uphill_segment,
            moderate_downhill_segment
        ]

        decisions = service.process_route(segments)

        assert len(decisions) == 4
        assert decisions[0].mode == MovementMode.RUN       # flat
        assert decisions[1].mode == MovementMode.RUN       # gentle uphill
        assert decisions[2].mode == MovementMode.HIKE      # steep uphill
        assert decisions[3].mode == MovementMode.RUN       # moderate downhill

    def test_summary_statistics(
        self,
        flat_segment,
        gentle_uphill_segment,
        steep_uphill_segment
    ):
        """Test summary statistics calculation."""
        service = HikeRunThresholdService()
        segments = [flat_segment, gentle_uphill_segment, steep_uphill_segment]

        decisions = service.process_route(segments)
        summary = service.get_summary(decisions)

        assert summary["total_segments"] == 3
        assert summary["run_segments"] == 2
        assert summary["hike_segments"] == 1
        assert summary["run_distance_km"] == 2.0
        assert summary["hike_distance_km"] == 1.0
        assert summary["run_percent"] == pytest.approx(66.7, rel=0.1)


# =============================================================================
# Test Strava Profile Detection
# =============================================================================

class TestStravaProfileDetection:
    """Tests for auto-detection from Strava data."""

    def test_from_strava_insufficient_data(self):
        """Should use defaults with insufficient data."""
        service = HikeRunThresholdService.from_strava_profile([])

        assert service.base_uphill_threshold == HikeRunThresholdService.DEFAULT_UPHILL_THRESHOLD

    def test_from_strava_with_data(self):
        """Should detect threshold from pace jump."""
        # Simulated splits: pace jumps significantly at 32% gradient
        splits = []
        for gradient in range(5, 40, 2):
            # Pace increases linearly until 32%, then jumps
            if gradient < 32:
                pace = 6.0 + gradient * 0.2  # gradual increase
            else:
                pace = 6.0 + gradient * 0.2 + 3.0  # sudden jump (walking)

            splits.append({
                "gradient_percent": gradient,
                "pace_min_km": pace
            })

        service = HikeRunThresholdService.from_strava_profile(splits)

        # Should detect threshold around 32% (clamped to MIN_THRESHOLD..MAX_THRESHOLD)
        assert 30 <= service.base_uphill_threshold <= 35

    def test_from_user_preference(self):
        """Test creation from user preference."""
        service = HikeRunThresholdService.from_user_preference(
            uphill_threshold=20.0,
            dynamic=True
        )

        assert service.base_uphill_threshold == 20.0
        assert service.dynamic is True


# =============================================================================
# Test Service Info
# =============================================================================

class TestServiceInfo:
    """Tests for service info output."""

    def test_get_info_static(self):
        """Test info output for static mode."""
        service = HikeRunThresholdService(uphill_threshold=25.0)
        info = service.get_info()

        assert info["uphill_threshold"] == 25.0
        assert info["downhill_threshold"] == -30.0
        assert info["dynamic"] is False

    def test_get_info_dynamic(self):
        """Test info output for dynamic mode."""
        service = HikeRunThresholdService(uphill_threshold=35.0, dynamic=True)
        info = service.get_info()

        assert info["dynamic"] is True
        assert "example_thresholds" in info
        assert info["example_thresholds"]["start"] == 35.0
        assert info["example_thresholds"]["after_2h"] < 35.0
