"""Клавиатуры бота. Собираются из списка услуг в config.py."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config

BACK = "◀ Назад"


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Услуги и цены", callback_data="menu:services")
    builder.button(text="Оставить заявку", callback_data="menu:order")
    builder.button(text="О нас", callback_data="menu:about")
    builder.button(text="Контакты", callback_data="menu:contacts")
    builder.adjust(1, 1, 2)
    return builder.as_markup()


def services() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in config.SERVICES:
        builder.button(
            text=f"{service.title} — {service.price}",
            callback_data=f"service:{service.key}",
        )
    builder.button(text=BACK, callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def service_card(key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оставить заявку", callback_data=f"start_order:{key}")
    builder.button(text=BACK, callback_data="menu:services")
    builder.adjust(1)
    return builder.as_markup()


def order_confirm() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отправить", callback_data="order:send")
    builder.button(text="Отменить", callback_data="order:cancel")
    builder.adjust(2)
    return builder.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BACK, callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Новые заявки", callback_data="admin:new")
    builder.button(text="Последние 10", callback_data="admin:last")
    builder.button(text="Статистика", callback_data="admin:stats")
    builder.button(text="Выгрузка в Excel", callback_data="admin:csv")
    builder.button(text="Рассылка", callback_data="admin:broadcast")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def order_actions(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отметить обработанной", callback_data=f"admin:done:{order_id}")
    builder.adjust(1)
    return builder.as_markup()