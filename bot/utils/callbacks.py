"""
Callback data prefixes for inline keyboards.

Format: {prefix}:{action}:{param}
Example: st:sync:123456
"""


class CallbackPrefix:
    """Prefixes for callback data."""

    ONBOARDING = "ob"      # Onboarding flow
    PREDICTION = "pr"      # Hiking prediction
    TRAIL_RUN = "tr"       # Trail run prediction
    STRAVA = "st"          # Strava integration
    PROFILE = "pf"         # Profile management
    ACTIVITIES = "act"     # Strava activities


# Usage examples:
# f"{CallbackPrefix.STRAVA}:sync"
# f"{CallbackPrefix.PREDICTION}:experience:beginner"
# f"{CallbackPrefix.TRAIL_RUN}:gap:strava"
