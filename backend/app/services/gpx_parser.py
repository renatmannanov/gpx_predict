"""
GPX Parser Service

Parses GPX files and extracts route information.
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple
import gpxpy
import gpxpy.gpx

from app.schemas.gpx import GPXInfo
from app.utils.geo import haversine, calculate_total_distance
from app.utils.elevation import calculate_elevation_changes

logger = logging.getLogger(__name__)


@dataclass
class GPXSegment:
    """A segment of a GPX route."""
    start_km: float
    end_km: float
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    gradient_percent: float
    start_elevation_m: float
    end_elevation_m: float


class GPXParserService:
    """Service for parsing GPX files."""

    @staticmethod
    def parse(content: bytes) -> GPXInfo:
        """
        Parse GPX content and extract route information.

        Args:
            content: GPX file content as bytes

        Returns:
            GPXInfo with parsed metadata

        Raises:
            ValueError: If GPX is invalid
        """
        try:
            gpx = gpxpy.parse(content.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to parse GPX: {e}")
            raise ValueError(f"Invalid GPX file: {e}")

        # Collect all points from tracks and routes
        points: List[Tuple[float, float, float]] = []

        # From tracks
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    ele = point.elevation if point.elevation else 0
                    points.append((point.latitude, point.longitude, ele))

        # From routes (if no tracks)
        if not points:
            for route in gpx.routes:
                for point in route.points:
                    ele = point.elevation if point.elevation else 0
                    points.append((point.latitude, point.longitude, ele))

        if not points:
            raise ValueError("GPX file contains no track or route points")

        # Calculate metrics using shared utilities
        distance_km = calculate_total_distance(points)
        elevation_gain, elevation_loss = calculate_elevation_changes(points)
        elevations = [p[2] for p in points]

        # Check if route is a loop (start and end within 500m)
        start_end_distance = haversine(
            points[0][0], points[0][1],
            points[-1][0], points[-1][1]
        )
        is_loop = start_end_distance < 0.5  # Less than 500m

        return GPXInfo(
            filename="uploaded.gpx",
            name=gpx.name or gpx.tracks[0].name if gpx.tracks else None,
            description=gpx.description,
            distance_km=round(distance_km, 2),
            elevation_gain_m=round(elevation_gain, 0),
            elevation_loss_m=round(elevation_loss, 0),
            max_elevation_m=round(max(elevations), 0) if elevations else 0,
            min_elevation_m=round(min(elevations), 0) if elevations else 0,
            start_lat=points[0][0],
            start_lon=points[0][1],
            end_lat=points[-1][0],
            end_lon=points[-1][1],
            points_count=len(points),
            is_loop=is_loop
        )

    @staticmethod
    def extract_points(content: bytes) -> List[Tuple[float, float, float]]:
        """
        Extract points from GPX content.

        Args:
            content: GPX file content as bytes

        Returns:
            List of (lat, lon, elevation) tuples
        """
        gpx = gpxpy.parse(content.decode('utf-8'))
        points: List[Tuple[float, float, float]] = []

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    ele = point.elevation if point.elevation else 0
                    points.append((point.latitude, point.longitude, ele))

        if not points:
            for route in gpx.routes:
                for point in route.points:
                    ele = point.elevation if point.elevation else 0
                    points.append((point.latitude, point.longitude, ele))

        return points

    @staticmethod
    def segment_route(
        points: List[Tuple[float, float, float]],
        min_segment_km: float = 0.5,
        gradient_threshold: float = 5.0
    ) -> List[GPXSegment]:
        """
        Segment route by distance for UI display (segment_by_distance).

        Creates roughly equal-sized segments (~0.5-1.5 km) for displaying
        per-segment predictions to users. This is different from
        RouteSegmenter.segment_route() which creates segments
        based on ascent/descent direction for calculator algorithms.

        Creates segments when:
        - Gradient changes by more than threshold
        - Distance exceeds min_segment_km

        Args:
            points: List of (lat, lon, elevation) tuples
            min_segment_km: Minimum segment distance
            gradient_threshold: Gradient change to trigger new segment (%)

        Returns:
            List of GPXSegment objects for UI display

        See also:
            RouteSegmenter.segment_route() for direction-based segmentation
        """
        if len(points) < 2:
            return []

        segments: List[GPXSegment] = []
        segment_start_idx = 0
        segment_start_km = 0.0
        cumulative_km = 0.0
        current_gradient = None

        for i in range(1, len(points)):
            lat1, lon1, ele1 = points[i - 1]
            lat2, lon2, ele2 = points[i]

            step_distance = haversine(lat1, lon1, lat2, lon2)
            cumulative_km += step_distance

            segment_distance = cumulative_km - segment_start_km

            # Calculate gradient for this step
            if step_distance > 0.01:  # Avoid division by small numbers
                step_gradient = ((ele2 - ele1) / (step_distance * 1000)) * 100
            else:
                step_gradient = 0

            # Initialize current gradient
            if current_gradient is None:
                current_gradient = step_gradient

            # Check if we should create a new segment
            gradient_changed = abs(step_gradient - current_gradient) > gradient_threshold
            distance_met = segment_distance >= min_segment_km

            if (gradient_changed and distance_met) or (segment_distance >= min_segment_km * 3):
                # Finalize current segment
                segment = GPXParserService._create_segment(
                    points, segment_start_idx, i,
                    segment_start_km, cumulative_km
                )
                segments.append(segment)

                # Start new segment
                segment_start_idx = i
                segment_start_km = cumulative_km
                current_gradient = step_gradient

        # Add final segment
        if segment_start_idx < len(points) - 1:
            segment = GPXParserService._create_segment(
                points, segment_start_idx, len(points) - 1,
                segment_start_km, cumulative_km
            )
            segments.append(segment)

        return segments

    @staticmethod
    def _create_segment(
        points: List[Tuple[float, float, float]],
        start_idx: int,
        end_idx: int,
        start_km: float,
        end_km: float
    ) -> GPXSegment:
        """Create a GPXSegment from point indices."""
        segment_points = points[start_idx:end_idx + 1]
        distance_km = end_km - start_km

        # Calculate elevation changes
        gain = 0.0
        loss = 0.0
        for j in range(1, len(segment_points)):
            diff = segment_points[j][2] - segment_points[j - 1][2]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        start_ele = segment_points[0][2]
        end_ele = segment_points[-1][2]
        ele_change = end_ele - start_ele

        # Overall gradient for segment
        if distance_km > 0:
            gradient = (ele_change / (distance_km * 1000)) * 100
        else:
            gradient = 0

        return GPXSegment(
            start_km=round(start_km, 2),
            end_km=round(end_km, 2),
            distance_km=round(distance_km, 2),
            elevation_gain_m=round(gain, 0),
            elevation_loss_m=round(loss, 0),
            gradient_percent=round(gradient, 1),
            start_elevation_m=round(start_ele, 0),
            end_elevation_m=round(end_ele, 0)
        )
