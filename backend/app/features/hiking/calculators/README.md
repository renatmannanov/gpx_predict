# Hiking Calculators

## Overview

Three methods for calculating hiking time:

| Method | Class | When to use |
|--------|-------|-------------|
| Tobler | ToblerCalculator | Default, mountain routes |
| Naismith | NaismithCalculator | Alternative, classic method |
| Personalized | HikePersonalizationService | If Strava profile available |

## Tobler's Hiking Function

**File:** `tobler.py`
**Formula:** `v = 6 * exp(-3.5 * |s + 0.05|)`

- Maximum speed 6 km/h at -5% gradient
- Exponential slowdown on steep sections
- Works well for mountain routes

## Naismith's Rule

**File:** `naismith.py`
**Formula:** 5 km/h + 1 hour per 600m ascent

- Classic method (1892)
- With Langmuir corrections for descent
- Good for flat routes

## Personalization

**File:** `personalization.py`
**Uses:** User profile from Strava

- 7 gradient categories
- Falls back to Tobler if no data
- Requires minimum 1 activity

## Fatigue

**File:** `fatigue.py`
**Effect:** Slowdown on long routes

- Starts after 3 hours (hiking)
- Linear + quadratic growth
