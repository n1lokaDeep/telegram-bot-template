"""Админ-панель: заявки, статистика, выгрузка, рассылка."""

from __future__ import annotations

import asyncio
import html
import tempfile
import time
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

import config
import database as db
import keyboards as kb

router = Router()


class Broadcast(StatesGroup):
    text = State()


class IsAdmin(BaseFilter):
    """Пропускает дальше только администраторов из config.ADMIN_IDS."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and user.id in config.ADMIN_IDS


# Весь этот роутер доступен только администраторам.
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def render_order(row: dict) -> str:
    status = "новая" if row["status"] == "new" else "обработана"
    username = f"@{row['username']}" if row["username"] else "скрыт"
    return (
        f"<b>Заявка №{row['id']}</b> · {esc(row['created_at'])} · {status}\n"
        f"<b>Услуга:</b> {esc(row['service'])}\n"
        f"<b>Имя:</b> {esc(row['full_name'])}\n"
        f"<b>Контакт:</b> {esc(row['contact'])}\n"
        f"<b>Комментарий:</b> {esc(row['comment'] or '—')}\n"
        f"<b>Telegram:</b> {esc(username)}"
    )


async def send_orders(
    bot: Bot, chat_id: int, only_new: bool, title: str
) -> None:
    rows = await db.recent_orders(limit=10, only_new=only_new)
    if not rows:
        await bot.send_message(chat_id, f"{title}\n\nЗаявок нет.")
        return

    await bot.send_message(chat_id, title)
    for row in rows:
        markup = kb.order_actions(row["id"]) if row["status"] == "new" else None
        await bot.send_message(chat_id, render_order(row), reply_markup=markup)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Админ-панель. Что показать?", reply_markup=kb.admin_menu())


@router.callback_query(F.data == "admin:new")
async def cb_new(callback: CallbackQuery, bot: Bot) -> None:
    await send_orders(bot, callback.from_user.id, True, "<b>Новые заявки</b>")
    await callback.answer()


@router.callback_query(F.data == "admin:last")
async def cb_last(callback: CallbackQuery, bot: Bot) -> None:
    await send_orders(bot, callback.from_user.id, False, "<b>Последние 10 заявок</b>")
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def cb_stats(callback: CallbackQuery) -> None:
    data = await db.stats()
    text = (
        "<b>Статистика</b>\n\n"
        f"Пользователей в боте: {data['users']}\n"
        f"Всего заявок: {data['orders']}\n"
        f"Из них необработанных: {data['new_orders']}"
    )
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=kb.admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:csv")
async def cb_csv(callback: CallbackQuery, bot: Bot) -> None:
    path = Path(tempfile.gettempdir()) / f"orders_{int(time.time())}.csv"
    await db.export_orders_csv(path)
    try:
        await bot.send_document(
            callback.from_user.id,
            FSInputFile(path, filename="заявки.csv"),
            caption="Все заявки выгрузкой для Excel",
        )
    finally:
        path.unlink(missing_ok=True)
    await callback.answer("Готово")


@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Broadcast.text)
    if callback.message is not None:
        await callback.message.edit_text(
            f"{config.BROADCAST_ASK}\n\nОтмена — /admin"
        )
    await callback.answer()


@router.message(Broadcast.text)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    text = message.html_text
    user_ids = await db.all_user_ids()

    await message.answer(f"Рассылаю на {len(user_ids)} пользователей...")

    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await message.answer(
        config.BROADCAST_DONE.format(sent=sent, failed=failed),
        reply_markup=kb.admin_menu(),
    )


@router.callback_query(F.data.startswith("admin:done:"))
async def cb_done(callback: CallbackQuery) -> None:
    raw = (callback.data or "").rsplit(":", 1)[-1]
    if not raw.isdigit():
        await callback.answer("Некорректный номер", show_alert=True)
        return

    await db.mark_processed(int(raw))
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отмечено обработанной")