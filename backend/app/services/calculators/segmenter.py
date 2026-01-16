"""
Route Segmenter

Splits a GPX route into macro-segments (major ascents/descents).
"""

from dataclasses import dataclass
from typing import List, Tuple
import math

from app.services.calculators.base import MacroSegment, SegmentType


@dataclass
class Point:
    """A point on the route."""
    lat: float
    lon: float
    elevation: float
    cumulative_distance_km: float = 0.0


class RouteSegmenter:
    """
    Segments a route into major ascent/descent sections.

    Unlike micro-segments (every 500m), this creates segments
    at points where the route changes direction (up vs down).
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
        Split route into macro-segments by direction.

        Args:
            points: List of (lat, lon, elevation) tuples

        Returns:
            List of MacroSegment objects
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
                cumulative += cls._haversine(prev_lat, prev_lon, lat, lon)

            result.append(Point(
                lat=lat,
                lon=lon,
                elevation=ele,
                cumulative_distance_km=cumulative
            ))

        return result

    @classmethod
    def _smooth_elevations(cls, points: List[Point]) -> List[Point]:
        """Apply moving average smoothing to elevations."""
        if len(points) <= cls.SMOOTHING_WINDOW:
            return points

        half = cls.SMOOTHING_WINDOW // 2
        smoothed = []

        for i, p in enumerate(points):
            start = max(0, i - half)
            end = min(len(points), i + half + 1)
            avg_ele = sum(points[j].elevation for j in range(start, end)) / (end - start)

            smoothed.append(Point(
                lat=p.lat,
                lon=p.lon,
                elevation=avg_ele,
                cumulative_distance_km=p.cumulative_distance_km
            ))

        return smoothed

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

        # Determine segment type
        if direction == 'up':
            seg_type = SegmentType.ASCENT
        elif direction == 'down':
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

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        R = 6371  # Earth radius in km

        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c
