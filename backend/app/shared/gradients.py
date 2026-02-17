"""
Gradient classification for terrain categories.

Used by: profile calculation, personalization, calibration tools.
Single source of truth for gradient thresholds.

Naming convention: {direction}_{lower}_{upper} or {direction}_{bound}_over
  - direction: "up" or "down" (except "flat")
  - numbers: absolute gradient boundaries in percent
  - "over": unbounded extreme category
Examples: up_8_12 = uphill 8% to 12%, down_23_over = downhill steeper than -23%
"""

# 11-category gradient thresholds (~5% bins)
GRADIENT_THRESHOLDS = {
    'down_23_over': (-100.0, -23.0),   # < -23% (scrambling)
    'down_23_17':   (-23.0, -17.0),    # -23% to -17%
    'down_17_12':   (-17.0, -12.0),    # -17% to -12%
    'down_12_8':    (-12.0, -8.0),     # -12% to -8%
    'down_8_3':     (-8.0, -3.0),      # -8% to -3%
    'flat_3_3':     (-3.0, 3.0),       # -3% to +3%
    'up_3_8':       (3.0, 8.0),        # +3% to +8%
    'up_8_12':      (8.0, 12.0),       # +8% to +12%
    'up_12_17':     (12.0, 17.0),      # +12% to +17%
    'up_17_23':     (17.0, 23.0),      # +17% to +23%
    'up_23_over':   (23.0, 100.0),     # > +23% (scrambling)
}

# Legacy 7-category thresholds (for backward compatibility)
LEGACY_GRADIENT_THRESHOLDS = {
    'steep_downhill': (-100.0, -15.0),
    'moderate_downhill': (-15.0, -8.0),
    'gentle_downhill': (-8.0, -3.0),
    'flat': (-3.0, 3.0),
    'gentle_uphill': (3.0, 8.0),
    'moderate_uphill': (8.0, 15.0),
    'steep_uphill': (15.0, 100.0),
}

# Mapping: 11 new categories -> 7 legacy categories
LEGACY_CATEGORY_MAPPING = {
    'down_23_over': 'steep_downhill',
    'down_23_17':   'steep_downhill',
    'down_17_12':   'moderate_downhill',
    'down_12_8':    'moderate_downhill',
    'down_8_3':     'gentle_downhill',
    'flat_3_3':     'flat',
    'up_3_8':       'gentle_uphill',
    'up_8_12':      'moderate_uphill',
    'up_12_17':     'moderate_uphill',
    'up_17_23':     'steep_uphill',
    'up_23_over':   'steep_uphill',
}

# Legacy 3-category thresholds
FLAT_GRADIENT_MIN = -3.0  # %
FLAT_GRADIENT_MAX = 3.0   # %


def classify_gradient(gradient_percent: float) -> str:
    """
    Classify gradient into one of 11 categories.

    Args:
        gradient_percent: Gradient as percentage (e.g., 10.0 for 10%)

    Returns:
        Category name (e.g., 'up_8_12', 'down_23_over', 'flat_3_3')
    """
    for category, (min_grad, max_grad) in GRADIENT_THRESHOLDS.items():
        if min_grad <= gradient_percent < max_grad:
            return category
    # Edge cases: values at or beyond extreme boundaries
    if gradient_percent >= 23.0:
        return 'up_23_over'
    if gradient_percent <= -23.0:
        return 'down_23_over'
    return 'flat_3_3'


def classify_gradient_legacy(gradient_percent: float) -> str:
    """
    Classify gradient into one of 7 legacy categories.

    For backward compatibility with existing hiking profile and avg_* fields.

    Args:
        gradient_percent: Gradient as percentage

    Returns:
        Legacy category name (e.g., 'steep_uphill', 'gentle_downhill', 'flat')
    """
    return LEGACY_CATEGORY_MAPPING[classify_gradient(gradient_percent)]
