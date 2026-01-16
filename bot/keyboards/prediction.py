"""
Prediction Keyboards

Inline keyboards for the prediction flow.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_experience_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting experience level."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Новичок (первые походы)",
                callback_data="exp:beginner"
            )
        ],
        [
            InlineKeyboardButton(
                text="Любитель (несколько раз в год)",
                callback_data="exp:casual"
            )
        ],
        [
            InlineKeyboardButton(
                text="Регулярно (раз в месяц)",
                callback_data="exp:regular"
            )
        ],
        [
            InlineKeyboardButton(
                text="Опытный (каждую неделю)",
                callback_data="exp:experienced"
            )
        ],
    ])


def get_backpack_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting backpack weight."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Легкий (до 5 кг)",
                callback_data="bp:light"
            )
        ],
        [
            InlineKeyboardButton(
                text="Средний (5-15 кг)",
                callback_data="bp:medium"
            )
        ],
        [
            InlineKeyboardButton(
                text="Тяжелый (15+ кг)",
                callback_data="bp:heavy"
            )
        ],
    ])


def get_group_size_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting group size."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 (один)", callback_data="gs:1"),
            InlineKeyboardButton(text="2", callback_data="gs:2"),
            InlineKeyboardButton(text="3", callback_data="gs:3"),
        ],
        [
            InlineKeyboardButton(text="4", callback_data="gs:4"),
            InlineKeyboardButton(text="5", callback_data="gs:5"),
            InlineKeyboardButton(text="6+", callback_data="gs:6"),
        ],
    ])


def get_yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Generic yes/no keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"{prefix}:yes"),
            InlineKeyboardButton(text="Нет", callback_data=f"{prefix}:no"),
        ],
    ])


def get_route_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting route type."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="В одну сторону (A -> B)",
                callback_data="rt:oneway"
            )
        ],
        [
            InlineKeyboardButton(
                text="Туда и обратно (A -> B -> A)",
                callback_data="rt:roundtrip"
            )
        ],
    ])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
    ])
