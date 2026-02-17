"""
Prediction FSM States

States for the prediction flow.
"""

from aiogram.fsm.state import State, StatesGroup


class PredictionStates(StatesGroup):
    """States for hike prediction flow."""

    waiting_for_gpx = State()
    selecting_activity_type = State()
    selecting_route_type = State()
    selecting_experience = State()
    selecting_backpack = State()
    selecting_group_size = State()
    selecting_children = State()
    selecting_elderly = State()
    confirming = State()
