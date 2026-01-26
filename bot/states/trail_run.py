"""
Trail Run FSM States

States for trail running prediction flow.
"""

from aiogram.fsm.state import State, StatesGroup


class TrailRunStates(StatesGroup):
    """FSM states for trail run prediction flow."""

    # Waiting for GPX file
    waiting_for_gpx = State()

    # Selecting route type (oneway/roundtrip)
    selecting_route_type = State()

    # Selecting GAP mode (optional, advanced)
    selecting_gap_mode = State()

    # Selecting flat pace (if no profile)
    selecting_flat_pace = State()

    # Confirming settings before calculation
    confirming = State()
