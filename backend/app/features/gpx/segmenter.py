"""
Route Segmenter

Splits a GPX route into macro-segments (major ascents/descents).
Used by Tobler and Naismith calculators for time estimation.
"""

from dataclasses import dataclass
from typing import List, Tuple

# Import from shared to avoid circular import
from app.shared.calculator_types import MacroSegment, SegmentType
from app.shared.geo import haversine
from app.shared.elevation import smooth_elevations


@dataclass
class Point:
    """A point on the route."""
    lat: float
    lon: float
    elevation: float
    cumulative_distance_km: float = 0.0


class RouteSegmenter:
    """
    Segments a route into macro-segments by direction (segment_by_direction).

    Creates segments based on ascent/descent direction for use in
    Tobler/Naismith calculators. Unlike GPXParserService.segment_route()
    which creates equal-sized segments for UI display, this class creates
    segments at points where the route changes direction (up vs down).

    Two segmentation strategies in the project:
    - RouteSegmenter.segment_route() → MacroSegment (by direction, for calculators)
    - GPXParserService.segment_route() → GPXSegment (by distance, for UI)
    """

    # Minimum segment length to avoid noise
    MIN_SEGMENT_KM = 0.3

    # Gradient threshold to distinguish flat from up/down
    FLAT_THRESHOLD_PERCENT = 3.0

    # Smoothing window for elevation (reduces GPS noise)
    SMOOTHING_WINDOW = 5

    @classmethod
    def segment_route(
        cls,
        points: List[Tuple[float, float, float]]
    ) -> List[MacroSegment]:
        """
        Split route into macro-segments by direction (ascent/descent/flat).

        Used by Tobler and Naismith calculators for accurate time estimation.
        Each segment represents a continuous ascent, descent, or flat section.

        Args:
            points: List of (lat, lon, elevation) tuples

        Returns:
            List of MacroSegment objects with type ASCENT, DESCENT, or FLAT

        See also:
            GPXParserService.segment_route() for distance-based UI segments
        """
        if len(points) < 2:
            return []

        # Convert to Point objects with cumulative distance
        route_points = cls._prepare_points(points)

        # Smooth elevations to reduce noise
        route_points = cls._smooth_elevations(route_points)

        # Find direction change points
        segments = cls._find_segments(route_points)

        return segments

    @classmethod
    def _prepare_points(
        cls,
        points: List[Tuple[float, float, float]]
    ) -> List[Point]:
        """Convert raw points to Point objects with cumulative distance."""
        result = []
        cumulative = 0.0

        for i, (lat, lon, ele) in enumerate(points):
            if i > 0:
                prev_lat, prev_lon, _ = points[i - 1]
                cumulative += haversine(prev_lat, prev_lon, lat, lon)

            result.append(Point(
                lat=lat,
                lon=lon,
                elevation=ele,
                cumulative_distance_km=cumulative
            ))

        return result

    @classmethod
    def _smooth_elevations(cls, points: List[Point]) -> List[Point]:
        """Apply moving average smoothing to elevations using shared utility."""
        if len(points) <= cls.SMOOTHING_WINDOW:
            return points

        # Extract elevations and smooth them
        elevations = [p.elevation for p in points]
        smoothed_elevations = smooth_elevations(elevations, cls.SMOOTHING_WINDOW)

        # Create new Point objects with smoothed elevations
        return [
            Point(
                lat=p.lat,
                lon=p.lon,
                elevation=smoothed_ele,
                cumulative_distance_km=p.cumulative_distance_km
            )
            for p, smoothed_ele in zip(points, smoothed_elevations)
        ]

    @classmethod
    def _find_segments(cls, points: List[Point]) -> List[MacroSegment]:
        """Find segments by detecting direction changes."""
        segments = []
        segment_start = 0
        current_direction = None  # 'up', 'down', or 'flat'

        for i in range(1, len(points)):
            # Calculate gradient for this step
            dist = points[i].cumulative_distance_km - points[i-1].cumulative_distance_km
            if dist < 0.001:  # Avoid division by zero
                continue

            ele_change = points[i].elevation - points[i-1].elevation
            gradient = (ele_change / (dist * 1000)) * 100  # As percentage

            # Determine direction
            if gradient > cls.FLAT_THRESHOLD_PERCENT:
                direction = 'up'
            elif gradient < -cls.FLAT_THRESHOLD_PERCENT:
                direction = 'down'
            else:
                direction = 'flat'

            # Check for direction change
            if current_direction is None:
                current_direction = direction
            elif direction != current_direction and direction != 'flat':
                # Direction changed - finalize segment if long enough
                segment_dist = (
                    points[i-1].cumulative_distance_km -
                    points[segment_start].cumulative_distance_km
                )

                if segment_dist >= cls.MIN_SEGMENT_KM:
                    segment = cls._create_segment(
                        points[segment_start:i],
                        len(segments) + 1,
                        current_direction
                    )
                    segments.append(segment)
                    segment_start = i - 1

                current_direction = direction

        # Add final segment
        if segment_start < len(points) - 1:
            segment = cls._create_segment(
                points[segment_start:],
                len(segments) + 1,
                current_direction or 'flat'
            )
            segments.append(segment)

        return segments

    @classmethod
    def _create_segment(
        cls,
        points: List[Point],
        number: int,
        direction: str
    ) -> MacroSegment:
        """Create a MacroSegment from a list of points."""
        if len(points) < 2:
            # Edge case: single point
            p = points[0]
            return MacroSegment(
                segment_number=number,
                segment_type=SegmentType.FLAT,
                distance_km=0.0,
                elevation_gain_m=0.0,
                elevation_loss_m=0.0,
                start_elevation_m=p.elevation,
                end_elevation_m=p.elevation
            )

        # Calculate distance
        distance = points[-1].cumulative_distance_km - points[0].cumulative_distance_km

        # Calculate elevation gain/loss
        gain = 0.0
        loss = 0.0
        for i in range(1, len(points)):
            diff = points[i].elevation - points[i-1].elevation
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        # Determine segment type based on ACTUAL elevation change, not passed direction
        # This fixes bug where direction didn't match actual gradient
        elevation_change = points[-1].elevation - points[0].elevation
        if distance > 0:
            actual_gradient = (elevation_change / (distance * 1000)) * 100
        else:
            actual_gradient = 0

        if actual_gradient > cls.FLAT_THRESHOLD_PERCENT:
            seg_type = SegmentType.ASCENT
        elif actual_gradient < -cls.FLAT_THRESHOLD_PERCENT:
            seg_type = SegmentType.DESCENT
        else:
            seg_type = SegmentType.FLAT

        return MacroSegment(
            segment_number=number,
            segment_type=seg_type,
            distance_km=round(distance, 2),
            elevation_gain_m=round(gain, 0),
            elevation_loss_m=round(loss, 0),
            start_elevation_m=round(points[0].elevation, 0),
            end_elevation_m=round(points[-1].elevation, 0)
        )
