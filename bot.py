"""Точка входа. Запуск: python bot.py"""

from __future__ import annotations

import asyncio
import logging
import sys

# Чтобы русский текст в логах не превращался в кракозябры в консоли Windows.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import config
import database as db
from handlers_admin import router as admin_router
from handlers_user import router as user_router


async def main() -> None:
    # Логирование настраивается ДО любых записей в лог.
    # Иначе logging.warning() сам неявно вызовет basicConfig() с уровнем WARNING,
    # и следующий basicConfig(level=INFO) уже ничего не изменит.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not config.BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN не задан.\n"
            "Скопируйте .env.example в .env и впишите токен от @BotFather."
        )
    if not config.ADMIN_IDS:
        logging.warning(
            "ADMIN_IDS пуст — заявки никому не придут. "
            "Свой ID можно узнать у бота @userinfobot."
        )

    await db.init_db()

    session = AiohttpSession(proxy=config.PROXY_URL) if config.PROXY_URL else None
    if config.PROXY_URL:
        logging.info("Работаю через прокси: %s", config.PROXY_URL)

    bot = Bot(
        token=config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    # Админский роутер идёт первым: его команды не должны перехватываться клиентскими.
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="cancel", description="Отменить заполнение заявки"),
            BotCommand(command="help", description="Помощь"),
        ]
    )

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен. Администраторы: %s", config.ADMIN_IDS)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as error:
        if str(error):
            print(error)