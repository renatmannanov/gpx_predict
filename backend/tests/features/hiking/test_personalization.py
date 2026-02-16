"""
Tests for hiking personalization services.

Tests both:
- BasePersonalizationService (abstract base class logic)
- HikePersonalizationService (hiking-specific implementation)
- Backward compatibility (PersonalizationService alias)
"""

import pytest
from unittest.mock import MagicMock

from app.services.calculators.base import MacroSegment, SegmentType
from app.features.hiking.calculators.personalization_base import (
    BasePersonalizationService,
    GRADIENT_THRESHOLDS,
    MIN_ACTIVITIES_FOR_PROFILE,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
)
from app.features.hiking.calculators import (
    HikePersonalizationService,
    PersonalizationService,
    DEFAULT_FLAT_SPEED_KMH,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_profile():
    """Create a mock UserPerformanceProfile with full data (legacy 7-cat, no JSON)."""
    profile = MagicMock()
    profile.avg_flat_pace_min_km = 12.0        # 5 km/h
    profile.avg_uphill_pace_min_km = 18.0      # ~3.3 km/h
    profile.avg_downhill_pace_min_km = 10.0    # 6 km/h
    profile.total_activities_analyzed = 5

    # Extended gradients (legacy 7-cat)
    profile.avg_steep_downhill_pace_min_km = 12.0
    profile.avg_moderate_downhill_pace_min_km = 11.0
    profile.avg_gentle_downhill_pace_min_km = 10.5
    profile.avg_gentle_uphill_pace_min_km = 14.0
    profile.avg_moderate_uphill_pace_min_km = 17.0
    profile.avg_steep_uphill_pace_min_km = 22.0

    # No JSON data (legacy profile without 11-cat)
    profile.gradient_paces = None
    profile.gradient_percentiles = None

    # Helper methods — enough samples for legacy categories, no percentiles
    profile.get_sample_count_extended = MagicMock(return_value=10)
    profile.get_percentile = MagicMock(return_value=None)

    # get_pace_for_category returns legacy column values
    def _get_pace(category):
        mapping = {
            'flat': 12.0,
            'gentle_uphill': 14.0,
            'moderate_uphill': 17.0,
            'steep_uphill': 22.0,
            'gentle_downhill': 10.5,
            'moderate_downhill': 11.0,
            'steep_downhill': 12.0,
        }
        return mapping.get(category)
    profile.get_pace_for_category = MagicMock(side_effect=_get_pace)

    return profile


@pytest.fixture
def mock_minimal_profile():
    """Create a mock profile with only flat pace."""
    profile = MagicMock()
    profile.avg_flat_pace_min_km = 12.0
    profile.avg_uphill_pace_min_km = None
    profile.avg_downhill_pace_min_km = None
    profile.total_activities_analyzed = 1

    # No extended gradients
    profile.avg_steep_downhill_pace_min_km = None
    profile.avg_moderate_downhill_pace_min_km = None
    profile.avg_gentle_downhill_pace_min_km = None
    profile.avg_gentle_uphill_pace_min_km = None
    profile.avg_moderate_uphill_pace_min_km = None
    profile.avg_steep_uphill_pace_min_km = None

    # No JSON data
    profile.gradient_paces = None
    profile.gradient_percentiles = None
    profile.get_sample_count_extended = MagicMock(return_value=0)
    profile.get_percentile = MagicMock(return_value=None)
    profile.get_pace_for_category = MagicMock(return_value=None)

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
def uphill_segment():
    """Create an uphill segment (~10% gradient)."""
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
def downhill_segment():
    """Create a downhill segment (~-10% gradient)."""
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
# Test Gradient Classification
# =============================================================================

class TestGradientClassification:
    """Tests for gradient classification logic."""

    def test_gradient_thresholds_defined(self):
        """Verify all 7 gradient categories are defined."""
        expected_categories = [
            'steep_downhill',
            'moderate_downhill',
            'gentle_downhill',
            'flat',
            'gentle_uphill',
            'moderate_uphill',
            'steep_uphill',
        ]
        assert set(GRADIENT_THRESHOLDS.keys()) == set(expected_categories)

    def test_gradient_thresholds_coverage(self):
        """Verify gradient thresholds cover all ranges without gaps."""
        sorted_categories = sorted(
            GRADIENT_THRESHOLDS.items(),
            key=lambda x: x[1][0]  # Sort by min value
        )

        for i in range(len(sorted_categories) - 1):
            current_max = sorted_categories[i][1][1]
            next_min = sorted_categories[i + 1][1][0]
            assert current_max == next_min, f"Gap between {sorted_categories[i][0]} and {sorted_categories[i+1][0]}"

    def test_classify_gradient_extended(self, mock_profile):
        """Test 7-category gradient classification."""
        service = HikePersonalizationService(mock_profile, use_extended_gradients=True)

        assert service._classify_gradient_extended(-20) == 'steep_downhill'
        assert service._classify_gradient_extended(-12) == 'moderate_downhill'
        assert service._classify_gradient_extended(-5) == 'gentle_downhill'
        assert service._classify_gradient_extended(0) == 'flat'
        assert service._classify_gradient_extended(5) == 'gentle_uphill'
        assert service._classify_gradient_extended(10) == 'moderate_uphill'
        assert service._classify_gradient_extended(20) == 'steep_uphill'

    def test_classify_terrain_legacy(self, mock_profile):
        """Test legacy 3-category classification."""
        service = HikePersonalizationService(mock_profile, use_extended_gradients=False)

        assert service._classify_terrain(-10) == 'downhill'
        assert service._classify_terrain(0) == 'flat'
        assert service._classify_terrain(10) == 'uphill'


# =============================================================================
# Test HikePersonalizationService
# =============================================================================

class TestHikePersonalizationService:
    """Tests for hiking personalization service."""

    def test_init_with_profile(self, mock_profile):
        """Test initialization with a valid profile."""
        service = HikePersonalizationService(mock_profile)
        assert service.profile == mock_profile
        assert service.use_extended_gradients is False

    def test_init_extended_gradients(self, mock_profile):
        """Test initialization with extended gradients enabled."""
        service = HikePersonalizationService(mock_profile, use_extended_gradients=True)
        assert service.use_extended_gradients is True

    def test_calculate_segment_flat(self, mock_profile, flat_segment):
        """Test segment calculation for flat terrain."""
        service = HikePersonalizationService(mock_profile)
        result = service.calculate_segment(flat_segment, base_method="tobler")

        assert result.method_name == "tobler_personalized"
        assert result.speed_kmh == pytest.approx(5.0, rel=0.1)  # 60 / 12 min/km
        assert result.time_hours > 0

    def test_calculate_segment_uphill(self, mock_profile, uphill_segment):
        """Test segment calculation for uphill terrain."""
        service = HikePersonalizationService(mock_profile)
        result = service.calculate_segment(uphill_segment, base_method="tobler")

        assert result.method_name == "tobler_personalized"
        # Should use uphill pace (18 min/km = 3.33 km/h)
        assert result.speed_kmh == pytest.approx(3.33, rel=0.1)

    def test_calculate_segment_downhill(self, mock_profile, downhill_segment):
        """Test segment calculation for downhill terrain."""
        service = HikePersonalizationService(mock_profile)
        result = service.calculate_segment(downhill_segment, base_method="tobler")

        assert result.method_name == "tobler_personalized"
        # Should use downhill pace (10 min/km = 6 km/h)
        assert result.speed_kmh == pytest.approx(6.0, rel=0.1)

    def test_calculate_segment_extended_gradients(self, mock_profile, uphill_segment):
        """Test segment calculation with extended gradient categories."""
        service = HikePersonalizationService(mock_profile, use_extended_gradients=True)
        result = service.calculate_segment(uphill_segment, base_method="naismith")

        assert result.method_name == "naismith_personalized"
        # ~10% gradient should use moderate_uphill pace (17 min/km)
        expected_speed = 60 / 17  # ~3.53 km/h
        assert result.speed_kmh == pytest.approx(expected_speed, rel=0.1)

    def test_calculate_route(self, mock_profile, flat_segment, uphill_segment, downhill_segment):
        """Test full route calculation."""
        service = HikePersonalizationService(mock_profile)
        segments = [flat_segment, uphill_segment, downhill_segment]

        total_hours, results = service.calculate_route(segments, base_method="tobler")

        assert len(results) == 3
        assert total_hours > 0
        assert total_hours == sum(r.time_hours for r in results)

    def test_fallback_to_tobler_estimation(self, mock_minimal_profile, uphill_segment):
        """Test fallback to Tobler when profile data is missing."""
        service = HikePersonalizationService(mock_minimal_profile, use_extended_gradients=True)
        result = service.calculate_segment(uphill_segment, base_method="tobler")

        # Should use Tobler-based estimation scaled by user's flat pace
        assert result.speed_kmh > 0
        assert result.time_hours > 0

    def test_default_speed(self, mock_profile):
        """Test default speed value."""
        service = HikePersonalizationService(mock_profile)
        assert service._get_default_speed() == DEFAULT_FLAT_SPEED_KMH


# =============================================================================
# Test Profile Validation
# =============================================================================

class TestProfileValidation:
    """Tests for profile validation logic."""

    def test_is_profile_valid_with_full_profile(self, mock_profile):
        """Valid profile should return True."""
        assert HikePersonalizationService.is_profile_valid(mock_profile) is True

    def test_is_profile_valid_with_none(self):
        """None profile should return False."""
        assert HikePersonalizationService.is_profile_valid(None) is False

    def test_is_profile_valid_without_flat_pace(self, mock_profile):
        """Profile without flat pace should return False."""
        mock_profile.avg_flat_pace_min_km = None
        assert HikePersonalizationService.is_profile_valid(mock_profile) is False

    def test_is_profile_valid_without_activities(self, mock_profile):
        """Profile with no activities should return False."""
        mock_profile.total_activities_analyzed = 0
        assert HikePersonalizationService.is_profile_valid(mock_profile) is False

    def test_min_activities_requirement(self, mock_profile):
        """Test minimum activities requirement."""
        mock_profile.total_activities_analyzed = MIN_ACTIVITIES_FOR_PROFILE - 1
        assert HikePersonalizationService.is_profile_valid(mock_profile) is False

        mock_profile.total_activities_analyzed = MIN_ACTIVITIES_FOR_PROFILE
        assert HikePersonalizationService.is_profile_valid(mock_profile) is True


# =============================================================================
# Test Profile Summary
# =============================================================================

class TestProfileSummary:
    """Tests for profile summary generation."""

    def test_get_profile_summary_with_none(self):
        """Should return empty dict for None profile."""
        assert HikePersonalizationService.get_profile_summary(None) == {}

    def test_get_profile_summary_basic(self, mock_profile):
        """Test basic summary without extended data."""
        mock_profile.has_split_data = True
        mock_profile.has_extended_gradient_data = True

        summary = HikePersonalizationService.get_profile_summary(mock_profile)

        assert "activities_analyzed" in summary
        assert "flat_pace_min_km" in summary
        assert "uphill_pace_min_km" in summary
        assert "downhill_pace_min_km" in summary
        assert summary["activities_analyzed"] == 5
        assert summary["flat_pace_min_km"] == 12.0

    def test_get_profile_summary_extended(self, mock_profile):
        """Test summary with extended gradient data."""
        mock_profile.has_split_data = True
        mock_profile.has_extended_gradient_data = True

        summary = HikePersonalizationService.get_profile_summary(
            mock_profile, include_extended=True
        )

        assert "extended_gradients" in summary
        ext = summary["extended_gradients"]
        assert ext["steep_downhill_pace"] == 12.0
        assert ext["moderate_uphill_pace"] == 17.0
        assert ext["steep_uphill_pace"] == 22.0


# =============================================================================
# Test Backward Compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Tests for backward compatibility with PersonalizationService alias."""

    def test_alias_exists(self):
        """PersonalizationService should be an alias for HikePersonalizationService."""
        assert PersonalizationService is HikePersonalizationService

    def test_alias_instantiation(self, mock_profile):
        """PersonalizationService should work exactly like HikePersonalizationService."""
        service = PersonalizationService(mock_profile)
        assert isinstance(service, HikePersonalizationService)

    def test_alias_methods(self, mock_profile, flat_segment):
        """Alias should have all the same methods."""
        service = PersonalizationService(mock_profile)

        # Should have all methods
        assert hasattr(service, 'calculate_segment')
        assert hasattr(service, 'calculate_route')
        assert hasattr(service, 'is_profile_valid')
        assert hasattr(service, 'get_profile_summary')

        # And they should work
        result = service.calculate_segment(flat_segment)
        assert result.time_hours > 0


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_distance_segment(self, mock_profile):
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

        service = HikePersonalizationService(mock_profile)
        result = service.calculate_segment(segment)

        assert result.time_hours == 0.0

    def test_extreme_gradient_uphill(self, mock_profile):
        """Test handling of extreme uphill gradient (>50%)."""
        segment = MacroSegment(
            segment_number=1,
            segment_type=SegmentType.ASCENT,
            distance_km=0.5,
            elevation_gain_m=300,
            elevation_loss_m=0,
            start_elevation_m=100,
            end_elevation_m=400
        )

        service = HikePersonalizationService(mock_profile, use_extended_gradients=True)
        result = service.calculate_segment(segment)

        # Should classify as steep_uphill and still work
        assert result.speed_kmh > 0
        assert result.time_hours > 0

    def test_extreme_gradient_downhill(self, mock_profile):
        """Test handling of extreme downhill gradient (<-50%)."""
        segment = MacroSegment(
            segment_number=1,
            segment_type=SegmentType.DESCENT,
            distance_km=0.5,
            elevation_gain_m=0,
            elevation_loss_m=300,
            start_elevation_m=400,
            end_elevation_m=100
        )

        service = HikePersonalizationService(mock_profile, use_extended_gradients=True)
        result = service.calculate_segment(segment)

        # Should classify as steep_downhill and still work
        assert result.speed_kmh > 0
        assert result.time_hours > 0
