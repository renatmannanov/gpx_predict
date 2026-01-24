"""
Tests for RunnerFatigueService.

Tests the fatigue model adapted for trail runners.
"""

import pytest

from app.services.calculators.trail_run.runner_fatigue import (
    RunnerFatigueService,
    RunnerFatigueConfig,
    FATIGUE_THRESHOLD_HOURS,
    LINEAR_DEGRADATION,
    QUADRATIC_DEGRADATION,
    DOWNHILL_FATIGUE_MULTIPLIER,
    ULTRA_THRESHOLD_50K,
    ULTRA_THRESHOLD_100K,
)


# =============================================================================
# Test Configuration
# =============================================================================

class TestConfiguration:
    """Tests for fatigue configuration."""

    def test_default_config_disabled(self):
        """Default config should be disabled."""
        config = RunnerFatigueConfig()

        assert config.enabled is False
        assert config.threshold_hours == FATIGUE_THRESHOLD_HOURS

    def test_create_disabled(self):
        """Test factory for disabled service."""
        service = RunnerFatigueService.create_disabled()

        assert service.enabled is False
        assert service.calculate_multiplier(10.0) == 1.0

    def test_create_enabled_default(self):
        """Test factory for enabled service with defaults."""
        service = RunnerFatigueService.create_enabled()

        assert service.enabled is True
        assert service.config.threshold_hours == FATIGUE_THRESHOLD_HOURS

    def test_create_enabled_with_distance(self):
        """Test ultra distance threshold adaptation."""
        # 50k+
        service_50k = RunnerFatigueService.create_enabled(distance_km=60)
        assert service_50k.config.threshold_hours == ULTRA_THRESHOLD_50K

        # 100k+
        service_100k = RunnerFatigueService.create_enabled(distance_km=110)
        assert service_100k.config.threshold_hours == ULTRA_THRESHOLD_100K

    def test_create_enabled_with_manual_threshold(self):
        """Test manual threshold override."""
        service = RunnerFatigueService.create_enabled(threshold_hours=5.0)

        assert service.config.threshold_hours == 5.0


# =============================================================================
# Test Multiplier Calculation
# =============================================================================

class TestMultiplierCalculation:
    """Tests for fatigue multiplier calculation."""

    def test_no_fatigue_before_threshold(self):
        """No fatigue before threshold hours."""
        service = RunnerFatigueService.create_enabled()

        # At and before threshold
        assert service.calculate_multiplier(0.0) == 1.0
        assert service.calculate_multiplier(1.0) == 1.0
        assert service.calculate_multiplier(2.0) == 1.0

    def test_linear_fatigue_component(self):
        """Test linear fatigue component."""
        service = RunnerFatigueService.create_enabled()

        # 1 hour after threshold
        mult_3h = service.calculate_multiplier(3.0)
        # Expected: 1.0 + 0.05 * 1 + 0.008 * 1 = 1.058
        assert mult_3h == pytest.approx(1.058, rel=0.01)

    def test_quadratic_fatigue_component(self):
        """Test quadratic fatigue component (later hours)."""
        service = RunnerFatigueService.create_enabled()

        # 4 hours after threshold (6h total)
        mult_6h = service.calculate_multiplier(6.0)
        # Expected: 1.0 + 0.05 * 4 + 0.008 * 16 = 1.328
        assert mult_6h == pytest.approx(1.328, rel=0.01)

    def test_progressive_fatigue(self):
        """Fatigue should increase progressively."""
        service = RunnerFatigueService.create_enabled()

        multipliers = [service.calculate_multiplier(h) for h in [2, 4, 6, 8, 10]]

        # Each should be greater than the previous
        for i in range(1, len(multipliers)):
            assert multipliers[i] > multipliers[i-1]

    def test_documented_examples(self):
        """Test the documented example multipliers."""
        service = RunnerFatigueService.create_enabled()

        # From docstring:
        # 2h  -> 1.00
        # 3h  -> 1.058 (+5.8%)
        # 4h  -> 1.13 (+13%)
        # 5h  -> 1.22 (+22%)
        # 6h  -> 1.33 (+33%)

        assert service.calculate_multiplier(2.0) == 1.0
        assert service.calculate_multiplier(3.0) == pytest.approx(1.058, rel=0.02)
        assert service.calculate_multiplier(4.0) == pytest.approx(1.13, rel=0.02)
        assert service.calculate_multiplier(5.0) == pytest.approx(1.22, rel=0.02)
        assert service.calculate_multiplier(6.0) == pytest.approx(1.33, rel=0.02)


# =============================================================================
# Test Downhill Penalty
# =============================================================================

class TestDownhillPenalty:
    """Tests for extra downhill fatigue penalty."""

    def test_downhill_multiplier_applied(self):
        """Downhill should have extra penalty when tired."""
        service = RunnerFatigueService.create_enabled()

        mult_normal = service.calculate_multiplier(6.0, is_downhill=False)
        mult_downhill = service.calculate_multiplier(6.0, is_downhill=True)

        # Downhill should be 1.5x the normal fatigue
        expected = mult_normal * DOWNHILL_FATIGUE_MULTIPLIER
        assert mult_downhill == pytest.approx(expected, rel=0.01)

    def test_no_downhill_penalty_before_threshold(self):
        """No downhill penalty before threshold."""
        service = RunnerFatigueService.create_enabled()

        mult_normal = service.calculate_multiplier(1.0, is_downhill=False)
        mult_downhill = service.calculate_multiplier(1.0, is_downhill=True)

        # Both should be 1.0 before threshold
        assert mult_normal == 1.0
        assert mult_downhill == 1.0

    def test_downhill_example(self):
        """Test documented downhill example."""
        service = RunnerFatigueService.create_enabled()

        # From docstring: Downhill at 6h -> 1.33 * 1.5 = 2.0 (+100%)
        mult = service.calculate_multiplier(6.0, is_downhill=True)
        assert mult == pytest.approx(2.0, rel=0.05)


# =============================================================================
# Test Segment Application
# =============================================================================

class TestSegmentApplication:
    """Tests for applying fatigue to segments."""

    def test_apply_no_fatigue(self):
        """Test segment application before threshold."""
        service = RunnerFatigueService.create_enabled()

        adjusted_time, multiplier = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=1.0,
            gradient_percent=0
        )

        assert multiplier == 1.0
        assert adjusted_time == 0.5

    def test_apply_with_fatigue(self):
        """Test segment application with fatigue."""
        service = RunnerFatigueService.create_enabled()

        adjusted_time, multiplier = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=5.0,  # 3h past threshold
            gradient_percent=0
        )

        assert multiplier > 1.0
        assert adjusted_time > 0.5

    def test_apply_downhill_detected(self):
        """Test that steep downhill triggers downhill penalty."""
        service = RunnerFatigueService.create_enabled()

        # Steep downhill (-10%)
        _, mult_downhill = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=5.0,
            gradient_percent=-10.0
        )

        # Flat
        _, mult_flat = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=5.0,
            gradient_percent=0
        )

        assert mult_downhill > mult_flat

    def test_downhill_threshold(self):
        """Test downhill detection threshold."""
        service = RunnerFatigueService.create_enabled()

        # -4% is not steep enough
        _, mult_gentle = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=5.0,
            gradient_percent=-4.0
        )

        # -6% should trigger downhill penalty
        _, mult_steep = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=5.0,
            gradient_percent=-6.0
        )

        assert mult_steep > mult_gentle

    def test_disabled_service(self):
        """Test that disabled service returns unchanged values."""
        service = RunnerFatigueService.create_disabled()

        adjusted_time, multiplier = service.apply_to_segment(
            base_time_hours=0.5,
            elapsed_hours=10.0,
            gradient_percent=-20.0
        )

        assert multiplier == 1.0
        assert adjusted_time == 0.5


# =============================================================================
# Test Service Info
# =============================================================================

class TestServiceInfo:
    """Tests for service info output."""

    def test_info_disabled(self):
        """Test info output for disabled service."""
        service = RunnerFatigueService.create_disabled()
        info = service.get_info()

        assert info["enabled"] is False
        assert info["model"] == "runner"

    def test_info_enabled(self):
        """Test info output for enabled service."""
        service = RunnerFatigueService.create_enabled()
        info = service.get_info()

        assert info["enabled"] is True
        assert info["model"] == "runner"
        assert info["threshold_hours"] == FATIGUE_THRESHOLD_HOURS
        assert info["linear_rate"] == LINEAR_DEGRADATION
        assert info["quadratic_rate"] == QUADRATIC_DEGRADATION
        assert info["downhill_multiplier"] == DOWNHILL_FATIGUE_MULTIPLIER
        assert "example_multipliers" in info

    def test_info_example_multipliers(self):
        """Test that example multipliers are calculated."""
        service = RunnerFatigueService.create_enabled()
        info = service.get_info()

        examples = info["example_multipliers"]

        assert "2h" in examples
        assert "6h" in examples
        assert "6h_downhill" in examples
        assert examples["2h"] == 1.0
        assert examples["6h"] > 1.0
        assert examples["6h_downhill"] > examples["6h"]


# =============================================================================
# Test Comparison with Hiking Fatigue
# =============================================================================

class TestComparisonWithHiking:
    """Tests comparing runner fatigue with hiking fatigue."""

    def test_runner_fatigue_starts_earlier(self):
        """Runner fatigue should start earlier than hiking (2h vs 3h)."""
        # This is by design - runners start feeling fatigue earlier
        assert FATIGUE_THRESHOLD_HOURS == 2.0
        # Hiking threshold from fatigue.py would be 3.0

    def test_runner_degradation_faster(self):
        """Runner degradation should be faster than hiking."""
        # Linear: 0.05 vs 0.03 for hiking
        # Quadratic: 0.008 vs 0.005 for hiking
        assert LINEAR_DEGRADATION == 0.05
        assert QUADRATIC_DEGRADATION == 0.008

    def test_downhill_penalty_unique_to_running(self):
        """Downhill penalty is unique to running (muscle damage)."""
        assert DOWNHILL_FATIGUE_MULTIPLIER == 1.5
