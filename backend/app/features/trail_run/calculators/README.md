# Trail Run Calculators

## Overview

| Method | Class | When to use |
|--------|-------|-------------|
| GAP Strava | GAPCalculator(STRAVA) | Default |
| GAP Minetti | GAPCalculator(MINETTI) | Scientific method |
| Threshold | HikeRunThresholdService | Auto-switch run/walk |
| Personalized | RunPersonalizationService | If profile available |

## GAP (Grade Adjusted Pace)

**File:** `gap.py`

Two modes:
- **Strava:** Empirical (240k athletes)
- **Minetti:** Scientific (uphills) + Strava (downhills)

## Threshold

**File:** `threshold.py`

Determines when to switch from running to walking:
- Dynamic: from user data
- Manual: user sets threshold

## Fatigue

**File:** `fatigue.py`

Enhanced model for runners:
- Starts after 2 hours (vs 3 for hiking)
- Greater fatigue increase
