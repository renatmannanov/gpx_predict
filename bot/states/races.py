"""FSM states for races flow."""

from aiogram.fsm.state import State, StatesGroup


class RaceStates(StatesGroup):
    """States for race prediction and search flow."""

    waiting_for_pace = State()  # User entering flat pace for prediction
    waiting_for_name = State()  # User entering name for search
