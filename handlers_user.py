"""Клиентская часть бота: меню, услуги, приём заявок."""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import database as db
import keyboards as kb

router = Router()


class OrderForm(StatesGroup):
    name = State()
    contact = State()
    comment = State()
    confirm = State()


def esc(value: object) -> str:
    """Экранирует пользовательский текст, чтобы он не ломал разметку."""
    return html.escape(str(value or ""), quote=False)


def order_summary(service: str, data: dict) -> str:
    return (
        f"{config.ASK_CONFIRM}\n\n"
        f"<b>Услуга:</b> {esc(service)}\n"
        f"<b>Имя:</b> {esc(data.get('name'))}\n"
        f"<b>Контакт:</b> {esc(data.get('contact'))}\n"
        f"<b>Комментарий:</b> {esc(data.get('comment') or '—')}"
    )


async def notify_admins(bot: Bot, text: str) -> None:
    """Отправляет заявку всем администраторам."""
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            # Администратор мог не запустить бота или заблокировать его.
            continue


# ───────────────────────────── команды ─────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    if user is not None:
        await db.remember_user(user.id, user.username, user.full_name)

    await message.answer(
        f"{config.GREETING}\n\nВыберите, что вас интересует:",
        reply_markup=kb.main_menu(),
    )

    # Пока ADMIN_IDS не заполнен, бот не может отправлять заявки владельцу.
    # Поэтому показываем тому, кто его запустил, его собственный ID —
    # это избавляет от необходимости искать @userinfobot.
    if not config.ADMIN_IDS and user is not None:
        await message.answer(
            "⚠️ <b>Бот ещё не настроен.</b>\n\n"
            f"Ваш ID: <code>{user.id}</code>\n\n"
            "Скопируйте это число в файл <code>.env</code> в строку "
            "<code>ADMIN_IDS</code> и перезапустите бота. "
            "Без этого заявки не будут приходить вам в личку."
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(config.ORDER_CANCELLED, reply_markup=kb.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — главное меню\n"
        "/cancel — отменить заполнение заявки",
        reply_markup=kb.main_menu(),
    )


# ──────────────────────────── навигация ────────────────────────────


@router.callback_query(F.data == "menu:main")
async def cb_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            f"{config.GREETING}\n\nВыберите, что вас интересует:",
            reply_markup=kb.main_menu(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:services")
async def cb_services(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            "Услуги и цены — нажмите на нужную, чтобы посмотреть подробности:",
            reply_markup=kb.services(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:order")
async def cb_order_from_menu(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            "Выберите услугу, по которой хотите оставить заявку:",
            reply_markup=kb.services(),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:about")
async def cb_about(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(config.ABOUT, reply_markup=kb.back_to_main())
    await callback.answer()


@router.callback_query(F.data == "menu:contacts")
async def cb_contacts(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            config.CONTACTS, reply_markup=kb.back_to_main()
        )
    await callback.answer()


@router.callback_query(F.data.startswith("service:"))
async def cb_service_card(callback: CallbackQuery) -> None:
    key = (callback.data or "").split(":", 1)[1]
    service = config.SERVICES_BY_KEY.get(key)
    if service is None:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    text = (
        f"<b>{esc(service.title)}</b>\n"
        f"Цена: {esc(service.price)}\n\n"
        f"{esc(service.details)}"
    )
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=kb.service_card(key))
    await callback.answer()


# ─────────────────────────── приём заявки ───────────────────────────


@router.callback_query(F.data.startswith("start_order:"))
async def cb_start_order(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":", 1)[1]
    service = config.SERVICES_BY_KEY.get(key)
    if service is None:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.clear()
    await state.update_data(service=service.title)
    await state.set_state(OrderForm.name)

    if callback.message is not None:
        await callback.message.edit_text(
            f"Заявка на «{esc(service.title)}».\n\n{config.ASK_NAME}"
        )
    await callback.answer()


@router.message(OrderForm.name)
async def form_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Напишите, как к вам обращаться.")
        return
    await state.update_data(name=name[:100])
    await state.set_state(OrderForm.contact)
    await message.answer(config.ASK_CONTACT)


@router.message(OrderForm.contact)
async def form_contact(message: Message, state: FSMContext) -> None:
    contact = (message.text or "").strip()
    if len(contact) < 3:
        await message.answer("Не похоже на контакт. Напишите телефон, Telegram или e-mail.")
        return
    await state.update_data(contact=contact[:200])
    await state.set_state(OrderForm.comment)
    await message.answer(config.ASK_COMMENT)


@router.message(OrderForm.comment)
async def form_comment(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if comment == "-":
        comment = ""
    await state.update_data(comment=comment[:500])
    await state.set_state(OrderForm.confirm)

    data = await state.get_data()
    await message.answer(
        order_summary(data.get("service", ""), data),
        reply_markup=kb.order_confirm(),
    )


@router.callback_query(F.data == "order:cancel", OrderForm.confirm)
async def cb_order_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            config.ORDER_CANCELLED, reply_markup=kb.main_menu()
        )
    await callback.answer()


@router.callback_query(F.data == "order:send", OrderForm.confirm)
async def cb_order_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    user = callback.from_user

    order_id = await db.create_order(
        user_id=user.id,
        username=user.username,
        full_name=data.get("name", ""),
        service=data.get("service", ""),
        contact=data.get("contact", ""),
        comment=data.get("comment", ""),
    )

    admin_text = (
        f"<b>Новая заявка №{order_id}</b>\n\n"
        f"<b>Услуга:</b> {esc(data.get('service'))}\n"
        f"<b>Имя:</b> {esc(data.get('name'))}\n"
        f"<b>Контакт:</b> {esc(data.get('contact'))}\n"
        f"<b>Комментарий:</b> {esc(data.get('comment') or '—')}\n"
        f"<b>Telegram:</b> {esc('@' + user.username) if user.username else 'скрыт'}"
    )
    await notify_admins(bot, admin_text)

    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(
            f"{config.ORDER_ACCEPTED}\n\nНомер вашей заявки: <b>{order_id}</b>",
            reply_markup=kb.main_menu(),
        )
    await callback.answer("Заявка отправлена")


# ──────────────────────────── заглушка ────────────────────────────


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(config.FALLBACK, reply_markup=kb.main_menu())