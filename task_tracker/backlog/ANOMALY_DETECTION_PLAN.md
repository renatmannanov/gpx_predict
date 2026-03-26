# Plan: Personalized Anomaly Detection for Pace Data

**Created:** 2025-01-22
**Status:** Planning

## Background

During profile calculation, we discovered that fixed pace thresholds (4-25 min/km) work well for filtering obvious outliers, but have limitations:
- For experienced hikers, 25 min/km is clearly a stop
- For beginners on steep terrain, 25 min/km might be normal hiking pace

## Current Implementation

### Fixed Thresholds
```python
PACE_MIN_THRESHOLD = 4.0   # min/km - faster than this is likely running/error
PACE_MAX_THRESHOLD = 25.0  # min/km - slower than this is likely a stop
```

### Discovered Anomalies (17 total)

#### 1. Morning Bana Hills Walk
**Link:** https://www.strava.com/activities/15467383727
**Context:** Walking in an amusement park, lots of stops to look at things

| Km | Pace | Gradient | Issue | User Comment |
|----|------|----------|-------|--------------|
| 7 | 28.5 min/km | +4.1% | Too slow | Stopped to look at something |
| 9 | 28.7 min/km | -0.7% | Too slow | Waiting in line for funicular |
| 11 | 4.0 min/km | -35.5% | Too fast | Descending on funicular |
| 12 | 3.8 min/km | -7.1% | Too fast | Descending on funicular |
| 13 | 3.9 min/km | -28.4% | Too fast | Descending on funicular |
| 14 | 3.5 min/km | -27.6% | Too fast | Descending on funicular |
| 17 | 1.4 min/km | +0.1% | Too fast | On funicular/transport |
| 18 | 2.0 min/km | +1.3% | Too fast | On funicular/transport |

---

#### 2. Evening Hike
**Link:** https://www.strava.com/activities/14598242604
**Context:** Forgot to start watch at beginning, spent time at viewpoint

| Km | Pace | Gradient | Issue | User Comment |
|----|------|----------|-------|--------------|
| 1 | 31.1 min/km | +1.2% | Too slow | Started watch late, stood at viewpoint talking and looking |

---

#### 3. Big Almata Lake Hike
**Link:** https://www.strava.com/activities/12755520952
**Context:** Steep mountain hike

| Km | Pace | Gradient | Issue | User Comment |
|----|------|----------|-------|--------------|
| 5 | 30.9 min/km | +31.1% | Too slow | Very steep climb, going slowly without rushing |

**Note:** This might actually be valid data for steep uphill! 30 min/km on +31% gradient could be normal.

---

#### 4. Morning Eco Hike
**Link:** https://www.strava.com/activities/12477081374
**Context:** Very slow hike with complete beginners, lots of rest stops, user was collecting trash out of boredom

| Km | Pace | Gradient | Issue | User Comment |
|----|------|----------|-------|--------------|
| 2 | 25.6 min/km | +18.8% | Too slow | Beginners needed rest |
| 4 | 28.2 min/km | +12.6% | Too slow | Beginners needed rest |
| 5 | 25.5 min/km | +10.8% | Too slow | Beginners needed rest |
| 6 | 25.7 min/km | +15.9% | Too slow | Beginners needed rest |
| 7 | 34.7 min/km | +0.3% | Too slow | Beginners needed rest |
| 10 | 37.4 min/km | -13.3% | Too slow | Beginners needed rest |
| 13 | 39.1 min/km | -14.3% | Too slow | Beginners needed rest |

**Note:** This activity represents hiking with beginners - a different use case than personal pace calibration.

---

## Anomaly Categories

Based on analysis, we identified these categories:

| Category | Pattern | Example |
|----------|---------|---------|
| `stop_rest` | Slow pace on any gradient | Viewpoint, photos, eating |
| `transport` | Very fast pace (<4 min/km) | Funicular, bus, taxi |
| `gps_error` | Unrealistic pace + gradient combo | Tunnel, signal loss |
| `queue_waiting` | Slow pace, flat gradient | Waiting for funicular |
| `social` | Slow pace throughout activity | Hiking with beginners |
| `technical_terrain` | Slow pace on steep gradient | Scrambling, via ferrata |

---

## Problem Statement

**Key Question:** Should anomaly detection be personalized or global?

### Global Thresholds
**Pros:**
- Simple to implement
- Works for obvious cases (transport <3 min/km)

**Cons:**
- What's an anomaly for one person is normal for another
- Fixed thresholds don't account for gradient

### Personalized Thresholds
**Pros:**
- More accurate for each user
- Can detect true outliers relative to user's own data

**Cons:**
- Chicken-and-egg: need data to calculate thresholds
- More complex implementation

---

## Proposed Solutions

### Option 1: Gradient-Dependent Thresholds
Different thresholds for different gradients:

```python
PACE_THRESHOLDS_BY_GRADIENT = {
    'steep_downhill': (3.0, 25.0),    # Can go fast downhill
    'moderate_downhill': (4.0, 25.0),
    'gentle_downhill': (4.0, 22.0),
    'flat': (5.0, 20.0),
    'gentle_uphill': (6.0, 25.0),
    'moderate_uphill': (8.0, 30.0),
    'steep_uphill': (10.0, 40.0),     # Very slow on steep is OK
}
```

### Option 2: Personalized Thresholds
Calculate thresholds from user's own data:

```python
def calculate_user_thresholds(splits_by_category):
    thresholds = {}
    for category, paces in splits_by_category.items():
        if len(paces) >= 3:
            median = statistics.median(paces)
            # Outliers are outside 2x median
            thresholds[category] = (median * 0.5, median * 2.0)
    return thresholds
```

### Option 3: IQR Method
Use interquartile range to detect outliers statistically:

```python
def filter_outliers_iqr(paces):
    q1 = percentile(paces, 25)
    q3 = percentile(paces, 75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [p for p in paces if lower <= p <= upper]
```

### Option 4: Hybrid Approach
1. Use global thresholds for obvious cases (transport <3 min/km, stops >40 min/km)
2. Use gradient-dependent thresholds for moderate cases
3. Use personalized thresholds (when enough data) for fine-tuning

---

## Additional Considerations

### Activity Type Filtering
Some activities should be excluded entirely from profile calculation:
- Activities with group of beginners (like Morning Eco Hike)
- Amusement park walks with transport (like Bana Hills)
- Activities marked as "sightseeing" or similar

**Possible solution:** Allow users to mark activities as "exclude from profile"

### Context Detection
Can we automatically detect problematic activities?
- High variance in pace within activity = lots of stops
- Unrealistic speed changes = transport
- Activity name contains "park", "tour", etc.

### User Feedback Loop
Allow users to:
1. View detected anomalies
2. Confirm/reject anomaly classification
3. Mark entire activities as "exclude from calibration"

---

## Next Steps

1. **Research:** Look at how other apps (Strava, TrainingPeaks) handle outlier detection
2. **Implement:** Start with Option 1 (gradient-dependent thresholds) as quick win
3. **Test:** Compare results with current fixed thresholds
4. **Iterate:** Add personalization if needed based on user feedback

---

## Related Files

- `backend/app/services/user_profile.py` - Current outlier filtering
- `backend/app/services/calculators/personalization.py` - Uses profile data
- `docs/ARCHITECTURE_CALCULATIONS.md` - Overall calculation architecture
