#!/usr/bin/env python
"""
Full analysis of run profile data:
1. Detailed segment breakdown with personalization
2. Comparison across different routes
3. Strava activities analysis
4. Outlier splits with Strava links
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from statistics import mean, stdev
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import gpxpy

from app.models.user import User
from app.features.hiking import UserHikingProfile as UserPerformanceProfile
from app.features.trail_run import UserTrailRunProfile as UserRunProfile
from app.models.strava_activity import StravaActivity, StravaActivitySplit
from app.models.gpx import GPXFile
from app.features.trail_run import TrailRunService
from app.features.trail_run.calculators import GAPMode
from app.features.gpx import RouteSegmenter


def format_time(hours: float) -> str:
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m:02d}min"


def format_pace(pace: float) -> str:
    if pace is None:
        return "N/A"
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}/km"


def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        # Get user
        user = db.query(User).filter(User.strava_connected == True).first()
        if not user:
            print("No user found!")
            return

        print("=" * 80)
        print(f"FULL RUN PROFILE ANALYSIS FOR: {user.name}")
        print("=" * 80)
        print()

        # Get profiles
        run_profile = db.query(UserRunProfile).filter(UserRunProfile.user_id == user.id).first()
        hike_profile = db.query(UserPerformanceProfile).filter(UserPerformanceProfile.user_id == user.id).first()

        # =====================================================================
        # PART 1: STRAVA ACTIVITIES ANALYSIS
        # =====================================================================
        print("=" * 80)
        print("PART 1: YOUR STRAVA RUNNING ACTIVITIES")
        print("=" * 80)
        print()

        run_activities = db.query(StravaActivity).filter(
            StravaActivity.user_id == user.id,
            StravaActivity.activity_type.in_(["Run", "TrailRun"])
        ).order_by(StravaActivity.start_date.desc()).all()

        print(f"Total running activities: {len(run_activities)}")
        print()

        print("Recent running activities:")
        print("-" * 80)
        print(f"{'Date':<12} {'Name':<35} {'Dist':>7} {'Elev':>6} {'Pace':>8} {'Strava Link'}")
        print("-" * 80)

        for act in run_activities[:15]:
            date = act.start_date.strftime("%Y-%m-%d") if act.start_date else "N/A"
            name = (act.name or "Unnamed")[:33]
            dist = f"{act.distance_m/1000:.1f}km" if act.distance_m else "N/A"
            elev = f"+{act.elevation_gain_m:.0f}m" if act.elevation_gain_m else "N/A"

            if act.distance_m and act.moving_time_s:
                pace_min_km = (act.moving_time_s / 60) / (act.distance_m / 1000)
                pace = format_pace(pace_min_km)
            else:
                pace = "N/A"

            link = f"https://www.strava.com/activities/{act.strava_id}"
            print(f"{date:<12} {name:<35} {dist:>7} {elev:>6} {pace:>8} {link}")

        print()

        # =====================================================================
        # PART 2: OUTLIER SPLITS ANALYSIS
        # =====================================================================
        print("=" * 80)
        print("PART 2: OUTLIER SPLITS (filtered from profile calculation)")
        print("=" * 80)
        print()

        PACE_MIN = 2.5
        PACE_MAX = 15.0

        all_splits = db.query(StravaActivitySplit).join(StravaActivity).filter(
            StravaActivity.user_id == user.id,
            StravaActivity.activity_type.in_(["Run", "TrailRun"])
        ).all()

        outliers = []
        valid_splits = []

        for split in all_splits:
            if split.pace_min_km is None:
                continue

            if split.pace_min_km < PACE_MIN or split.pace_min_km > PACE_MAX:
                # Get activity info
                activity = db.query(StravaActivity).filter(
                    StravaActivity.id == split.activity_id
                ).first()
                outliers.append({
                    'split': split,
                    'activity': activity
                })
            else:
                valid_splits.append(split)

        print(f"Total splits: {len(all_splits)}")
        print(f"Valid splits: {len(valid_splits)}")
        print(f"Outliers: {len(outliers)}")
        print(f"Filter range: {PACE_MIN}-{PACE_MAX} min/km")
        print()

        print("OUTLIER SPLITS (too fast or too slow):")
        print("-" * 100)
        print(f"{'Pace':>8} {'Gradient':>9} {'Reason':<12} {'Activity Name':<30} {'Strava Link'}")
        print("-" * 100)

        # Sort by pace
        outliers_sorted = sorted(outliers, key=lambda x: x['split'].pace_min_km or 0)

        for item in outliers_sorted:
            split = item['split']
            activity = item['activity']

            pace = format_pace(split.pace_min_km)
            gradient = f"{split.gradient_percent:+.1f}%" if split.gradient_percent else "N/A"

            if split.pace_min_km < PACE_MIN:
                reason = "TOO FAST"
            else:
                reason = "TOO SLOW"

            name = (activity.name or "Unnamed")[:28] if activity else "Unknown"
            link = f"https://www.strava.com/activities/{activity.strava_id}" if activity else "N/A"

            print(f"{pace:>8} {gradient:>9} {reason:<12} {name:<30} {link}")

        print()

        # Group outliers by activity
        print("Outliers grouped by activity:")
        print("-" * 80)

        activity_outliers = {}
        for item in outliers:
            act_id = item['activity'].strava_id if item['activity'] else None
            if act_id not in activity_outliers:
                activity_outliers[act_id] = {
                    'activity': item['activity'],
                    'splits': []
                }
            activity_outliers[act_id]['splits'].append(item['split'])

        for strava_id, data in activity_outliers.items():
            act = data['activity']
            splits = data['splits']
            if act:
                print(f"\n{act.name} ({len(splits)} outliers)")
                print(f"  Link: https://www.strava.com/activities/{strava_id}")
                print(f"  Outlier paces: {', '.join(format_pace(s.pace_min_km) for s in splits)}")

        print()

        # =====================================================================
        # PART 3: VALID SPLITS DISTRIBUTION
        # =====================================================================
        print("=" * 80)
        print("PART 3: VALID SPLITS DISTRIBUTION BY GRADIENT")
        print("=" * 80)
        print()

        GRADIENT_THRESHOLDS = {
            'steep_downhill': (-100.0, -15.0),
            'moderate_downhill': (-15.0, -8.0),
            'gentle_downhill': (-8.0, -3.0),
            'flat': (-3.0, 3.0),
            'gentle_uphill': (3.0, 8.0),
            'moderate_uphill': (8.0, 15.0),
            'steep_uphill': (15.0, 100.0),
        }

        splits_by_cat = {cat: [] for cat in GRADIENT_THRESHOLDS}

        for split in valid_splits:
            if split.gradient_percent is None:
                continue
            gradient = split.gradient_percent
            for cat, (min_g, max_g) in GRADIENT_THRESHOLDS.items():
                if min_g <= gradient < max_g:
                    splits_by_cat[cat].append(split.pace_min_km)
                    break

        print(f"{'Category':<20} {'Count':>6} {'Avg Pace':>10} {'Min':>8} {'Max':>8} {'StdDev':>8}")
        print("-" * 70)

        for cat in ['steep_downhill', 'moderate_downhill', 'gentle_downhill',
                    'flat', 'gentle_uphill', 'moderate_uphill', 'steep_uphill']:
            paces = splits_by_cat[cat]
            if paces:
                avg = mean(paces)
                min_p = min(paces)
                max_p = max(paces)
                std = stdev(paces) if len(paces) > 1 else 0
                print(f"{cat:<20} {len(paces):>6} {format_pace(avg):>10} {format_pace(min_p):>8} {format_pace(max_p):>8} {std:>7.1f}")
            else:
                print(f"{cat:<20} {0:>6} {'N/A':>10}")

        print()

        # =====================================================================
        # PART 4: DETAILED SEGMENT BREAKDOWN ON TALGAR TRAIL
        # =====================================================================
        print("=" * 80)
        print("PART 4: DETAILED SEGMENT BREAKDOWN ON TALGAR TRAIL")
        print("=" * 80)
        print()

        gpx_file = db.query(GPXFile).filter(GPXFile.name.ilike("%talgar%")).first()
        if not gpx_file:
            print("Talgar Trail not found!")
            return

        gpx = gpxpy.parse(gpx_file.gpx_content.decode('utf-8'))
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    if point.elevation is not None:
                        points.append((point.latitude, point.longitude, point.elevation))

        # Create services
        service_generic = TrailRunService(
            gap_mode=GAPMode.STRAVA,
            flat_pace_min_km=run_profile.avg_flat_pace_min_km or 6.0,
            apply_fatigue=False,
        )

        service_personalized = TrailRunService(
            gap_mode=GAPMode.STRAVA,
            flat_pace_min_km=run_profile.avg_flat_pace_min_km or 6.0,
            run_profile=run_profile,
            hike_profile=hike_profile,
            apply_fatigue=False,
        )

        result_generic = service_generic.calculate_route(points)
        result_personalized = service_personalized.calculate_route(points)

        print(f"Your flat pace: {format_pace(run_profile.avg_flat_pace_min_km)}")
        print()

        print("Segment-by-segment comparison (Generic GAP vs Personalized):")
        print("-" * 100)
        print(f"{'#':>2} {'Type':<8} {'Dist':>6} {'Elev':>7} {'Grad':>7} {'Mode':<5} {'Generic':>10} {'Personal':>10} {'Diff':>8}")
        print("-" * 100)

        total_generic = 0
        total_personal = 0

        for seg_g, seg_p in zip(result_generic.segments, result_personalized.segments):
            seg = seg_g.segment
            mode = seg_p.movement.mode.value.upper()[:4]

            # Get times
            if seg_p.movement.mode.value == "run":
                generic_time = seg_g.times.get('strava_gap', 0)
                personal_time = seg_p.times.get('run_personalized', seg_p.times.get('strava_gap', 0))
            else:
                generic_time = seg_g.times.get('tobler', 0)
                personal_time = seg_p.times.get('hike_personalized', seg_p.times.get('tobler', 0))

            total_generic += generic_time
            total_personal += personal_time

            diff_min = (personal_time - generic_time) * 60
            diff_str = f"{diff_min:+.1f}min"

            generic_str = f"{generic_time*60:.1f}min"
            personal_str = f"{personal_time*60:.1f}min"

            print(f"{seg.segment_number:>2} {seg.segment_type:<8} {seg.distance_km:>5.2f}km {seg.elevation_change_m:>+6.0f}m {seg.gradient_percent:>+6.1f}% {mode:<5} {generic_str:>10} {personal_str:>10} {diff_str:>8}")

        print("-" * 100)
        print(f"{'TOTAL':<38} {'':<5} {format_time(total_generic):>10} {format_time(total_personal):>10} {(total_personal-total_generic)*60:+.0f}min")
        print()

        # =====================================================================
        # PART 5: COMPARISON ACROSS DIFFERENT ROUTES
        # =====================================================================
        print("=" * 80)
        print("PART 5: COMPARISON ACROSS ALL YOUR GPX ROUTES")
        print("=" * 80)
        print()

        all_gpx = db.query(GPXFile).filter(GPXFile.gpx_content != None).all()

        # Deduplicate by name
        seen_names = set()
        unique_gpx = []
        for gpx_f in all_gpx:
            if gpx_f.name not in seen_names:
                seen_names.add(gpx_f.name)
                unique_gpx.append(gpx_f)

        print(f"{'Route Name':<45} {'Dist':>7} {'Elev':>7} {'Generic':>10} {'Personal':>10} {'Diff':>8}")
        print("-" * 95)

        for gpx_f in unique_gpx[:10]:
            try:
                gpx_data = gpxpy.parse(gpx_f.gpx_content.decode('utf-8'))
                pts = []
                for track in gpx_data.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            if point.elevation is not None:
                                pts.append((point.latitude, point.longitude, point.elevation))

                if len(pts) < 10:
                    continue

                svc_g = TrailRunService(
                    gap_mode=GAPMode.STRAVA,
                    flat_pace_min_km=run_profile.avg_flat_pace_min_km or 6.0,
                    apply_fatigue=False,
                )
                svc_p = TrailRunService(
                    gap_mode=GAPMode.STRAVA,
                    flat_pace_min_km=run_profile.avg_flat_pace_min_km or 6.0,
                    run_profile=run_profile,
                    hike_profile=hike_profile,
                    apply_fatigue=False,
                )

                res_g = svc_g.calculate_route(pts)
                res_p = svc_p.calculate_route(pts)

                name = (gpx_f.name or gpx_f.filename)[:43]
                dist = f"{res_g.summary.total_distance_km:.1f}km"
                elev = f"+{res_g.summary.total_elevation_gain_m:.0f}m"
                gen_time = format_time(res_g.totals['combined'])
                pers_time = format_time(res_p.totals['combined'])
                diff = (res_p.totals['combined'] - res_g.totals['combined']) * 60

                print(f"{name:<45} {dist:>7} {elev:>7} {gen_time:>10} {pers_time:>10} {diff:>+7.0f}min")

            except Exception as e:
                continue

        print()

        # =====================================================================
        # SUMMARY
        # =====================================================================
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()

        print("Your Run Profile:")
        print(f"  Flat pace:            {format_pace(run_profile.avg_flat_pace_min_km)}")
        print(f"  Gentle uphill:        {format_pace(run_profile.avg_gentle_uphill_pace_min_km)}")
        print(f"  Moderate uphill:      {format_pace(run_profile.avg_moderate_uphill_pace_min_km)}")
        print(f"  Steep uphill:         {format_pace(run_profile.avg_steep_uphill_pace_min_km)}")
        print(f"  Gentle downhill:      {format_pace(run_profile.avg_gentle_downhill_pace_min_km)}")
        print(f"  Moderate downhill:    {format_pace(run_profile.avg_moderate_downhill_pace_min_km)}")
        print(f"  Steep downhill:       {format_pace(run_profile.avg_steep_downhill_pace_min_km)}")
        print()

        print("Data quality:")
        print(f"  Running activities:   {len(run_activities)}")
        print(f"  Valid splits:         {len(valid_splits)}")
        print(f"  Outlier splits:       {len(outliers)}")
        print(f"  Outlier rate:         {len(outliers)/len(all_splits)*100:.1f}%")
        print()

        print("Recommendation:")
        if len(outliers) > len(valid_splits) * 0.3:
            print("  ⚠️  High outlier rate suggests many stops/pauses in your runs.")
            print("     Consider syncing more continuous running activities.")
        else:
            print("  ✅ Good data quality for personalization.")


if __name__ == "__main__":
    main()
