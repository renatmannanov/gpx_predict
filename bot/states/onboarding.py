"""
Onboarding FSM States

States for new user onboarding flow.
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """FSM states for onboarding flow."""

    # Step 1: Welcome message shown
    welcome = State()

    # Step 2: Selecting activity type (hiking/running)
    selecting_activity = State()

    # Step 3: Explanation of personalization
    explaining_personalization = State()

    # Step 4: Offering Strava connection
    offering_strava = State()

    # Step 5A: Waiting for Strava OAuth callback
    waiting_strava_callback = State()

    # Step 5B: User skipped Strava
    skipped_strava = State()

    # Step 6: Showing how to use the bot
    showing_usage = State()

    # Step 7: Onboarding complete
    complete = State()
