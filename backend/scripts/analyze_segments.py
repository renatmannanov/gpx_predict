#!/usr/bin/env python
"""
Analyze Talgar Trail segments with threshold detection details.
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import gpxpy

from app.models.gpx import GPXFile
from app.features.gpx import RouteSegmenter
from app.features.trail_run.calculators import (
    HikeRunThresholdService, MovementMode,
)


def load_gpx_from_db(db: Session, search_term: str = "talgar"):
    gpx_file = db.query(GPXFile).filter(
        GPXFile.name.ilike(f"%{search_term}%")
    ).first()
    if not gpx_file:
        gpx_file = db.query(GPXFile).filter(
            GPXFile.filename.ilike(f"%{search_term}%")
        ).first()
    return gpx_file


def parse_gpx_content(gpx_content: bytes) -> list:
    gpx = gpxpy.parse(gpx_content.decode('utf-8'))
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.elevation is not None:
                    points.append((point.latitude, point.longitude, point.elevation))
    for route in gpx.routes:
        for point in route.points:
            if point.elevation is not None:
                points.append((point.latitude, point.longitude, point.elevation))
    return points


def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return

    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        gpx_file = load_gpx_from_db(db, "talgar")
        if not gpx_file or not gpx_file.gpx_content:
            print("Talgar Trail GPX not found!")
            return

        points = parse_gpx_content(gpx_file.gpx_content)
        segments = RouteSegmenter.segment_route(points)

        # Threshold service with 25% threshold
        threshold_service = HikeRunThresholdService(uphill_threshold=25.0)
        decisions = threshold_service.process_route(segments)

        print("=" * 100)
        print("TALGAR TRAIL 25K - SEGMENT ANALYSIS WITH THRESHOLD DETECTION")
        print("=" * 100)
        print(f"Threshold: {threshold_service.base_uphill_threshold}% uphill, {threshold_service.downhill_threshold}% downhill")
        print()

        print("| # | Dist (km) | Elev +/- (m) | Gradient % | Type        | Decision | Reason                          |")
        print("|---|-----------|--------------|------------|-------------|----------|----------------------------------|")

        cumulative_dist = 0
        for i, (seg, decision) in enumerate(zip(segments, decisions)):
            cumulative_dist += seg.distance_km

            # Determine segment type
            if seg.gradient_percent > 3:
                seg_type = "Uphill"
            elif seg.gradient_percent < -3:
                seg_type = "Downhill"
            else:
                seg_type = "Flat"

            mode_str = "🏃 RUN" if decision.mode == MovementMode.RUN else "🚶 HIKE"

            print(f"| {i+1:2} | {seg.distance_km:9.2f} | +{seg.elevation_gain_m:3.0f} / -{seg.elevation_loss_m:3.0f} | {seg.gradient_percent:+10.1f} | {seg_type:11} | {mode_str:8} | {decision.reason[:32]:32} |")

        print()
        print("=" * 100)
        print("SUMMARY")
        print("=" * 100)

        summary = threshold_service.get_summary(decisions)

        print(f"Total segments:    {summary['total_segments']}")
        print(f"Run segments:      {summary['run_segments']} ({summary['run_percent']:.1f}%)")
        print(f"Hike segments:     {summary['hike_segments']} ({100 - summary['run_percent']:.1f}%)")
        print(f"Run distance:      {summary['run_distance_km']:.2f} km")
        print(f"Hike distance:     {summary['hike_distance_km']:.2f} km")
        print()

        # Show gradient distribution
        print("=" * 100)
        print("GRADIENT DISTRIBUTION")
        print("=" * 100)

        gradient_buckets = {
            "Steep downhill (<-20%)": [],
            "Moderate downhill (-20% to -10%)": [],
            "Gentle downhill (-10% to -3%)": [],
            "Flat (-3% to +3%)": [],
            "Gentle uphill (+3% to +10%)": [],
            "Moderate uphill (+10% to +20%)": [],
            "Steep uphill (+20% to +25%)": [],
            "Very steep uphill (>+25%) → HIKE": [],
        }

        for seg in segments:
            g = seg.gradient_percent
            if g < -20:
                gradient_buckets["Steep downhill (<-20%)"].append(seg)
            elif g < -10:
                gradient_buckets["Moderate downhill (-20% to -10%)"].append(seg)
            elif g < -3:
                gradient_buckets["Gentle downhill (-10% to -3%)"].append(seg)
            elif g <= 3:
                gradient_buckets["Flat (-3% to +3%)"].append(seg)
            elif g <= 10:
                gradient_buckets["Gentle uphill (+3% to +10%)"].append(seg)
            elif g <= 20:
                gradient_buckets["Moderate uphill (+10% to +20%)"].append(seg)
            elif g <= 25:
                gradient_buckets["Steep uphill (+20% to +25%)"].append(seg)
            else:
                gradient_buckets["Very steep uphill (>+25%) → HIKE"].append(seg)

        for bucket_name, segs in gradient_buckets.items():
            if segs:
                total_dist = sum(s.distance_km for s in segs)
                avg_grad = sum(s.gradient_percent for s in segs) / len(segs)
                print(f"  {bucket_name:40} : {len(segs):2} segments, {total_dist:5.2f} km, avg {avg_grad:+.1f}%")
            else:
                print(f"  {bucket_name:40} : -- no segments --")


if __name__ == "__main__":
    main()
