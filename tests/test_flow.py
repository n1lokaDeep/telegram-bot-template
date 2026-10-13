"""
Сквозной прогон бота без токена и без интернета.

Подменяет сетевой слой aiogram заглушкой, которая записывает все обращения
к Telegram API. Обработчики, состояния FSM, клавиатуры и база данных —
настоящие.

Запуск:
    python tests/test_flow.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, Update, User  # noqa: E402

import config  # noqa: E402
import database as db  # noqa: E402
from handlers_admin import router as admin_router  # noqa: E402
from handlers_user import router as user_router  # noqa: E402

TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
USER_ID = 555000111
ADMIN_ID = 999888777


class MockSession(BaseSession):
    """Заглушка Telegram: ничего не отправляет, только записывает вызовы."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    async def close(self) -> None:
        return None

    async def stream_content(self, bot, method, timeout=None, chunk_size=65536):
        """Скачивание файлов в тесте не используется."""
        yield b""

    def _fake_result(self, method) -> object:
        name = type(method).__name__
        chat_id = getattr(method, "chat_id", 0) or 0

        if name == "GetMe":
            return {
                "id": 123456789,
                "is_bot": True,
                "first_name": "TestBot",
                "username": "test_bot",
            }
        if name in ("SendMessage", "SendDocument", "EditMessageText",
                    "EditMessageReplyMarkup", "SendChatAction"):
            return {
                "message_id": len(self.calls),
                "date": int(datetime.now().timestamp()),
                "chat": {"id": chat_id, "type": "private"},
                "text": getattr(method, "text", "") or "",
            }
        return True

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        body = json.dumps({"ok": True, "result": self._fake_result(method)})
        return self.check_response(bot, method, 200, body).result

    # помощники для проверок

    OUTGOING = ("SendMessage", "EditMessageText")

    def outgoing(self) -> list:
        """Только сообщения, без служебных ответов вида answerCallbackQuery."""
        return [c for c in self.calls if type(c).__name__ in self.OUTGOING]

    def edits(self) -> list:
        return [c for c in self.calls if type(c).__name__ == "EditMessageText"]

    def texts(self) -> list[str]:
        return [c.text for c in self.outgoing() if getattr(c, "text", None)]

    def last_text(self) -> str:
        found = self.texts()
        return found[-1] if found else ""

    def messages_to(self, chat_id: int) -> list:
        from aiogram.methods import SendMessage

        return [c for c in self.calls if isinstance(c, SendMessage)
                and c.chat_id == chat_id]

    def reset(self) -> None:
        self.calls.clear()


def _user(user_id: int, name: str) -> User:
    return User(id=user_id, is_bot=False, first_name=name, username=f"user{user_id}")


def message_update(update_id: int, user_id: int, text: str) -> Update:
    chat = Chat(id=user_id, type="private")
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(),
            chat=chat,
            from_user=_user(user_id, "Тест"),
            text=text,
        ),
    )


def callback_update(update_id: int, user_id: int, data: str) -> Update:
    chat = Chat(id=user_id, type="private")
    bot_user = User(id=123456789, is_bot=True, first_name="TestBot")
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=str(update_id),
            from_user=_user(user_id, "Тест"),
            chat_instance="test-instance",
            data=data,
            message=Message(
                message_id=update_id,
                date=datetime.now(),
                chat=chat,
                from_user=bot_user,
                text="предыдущее сообщение",
            ),
        ),
    )


class Runner:
    def __init__(self) -> None:
        self.session = MockSession()
        self.bot = Bot(
            token=TOKEN,
            session=self.session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher(storage=MemoryStorage())
        self.dp.include_router(admin_router)
        self.dp.include_router(user_router)
        self.n = 1000

    async def send(self, user_id: int, text: str) -> None:
        self.n += 1
        await self.dp.feed_update(self.bot, message_update(self.n, user_id, text))

    async def click(self, user_id: int, data: str) -> None:
        self.n += 1
        await self.dp.feed_update(self.bot, callback_update(self.n, user_id, data))


PASSED = 0


def check(condition: bool, label: str) -> None:
    global PASSED
    if condition:
        PASSED += 1
        print(f"[OK] {label}")
    else:
        print(f"[ПРОВАЛ] {label}")
        raise SystemExit(1)


async def main() -> None:
    tmp_db = Path(tempfile.gettempdir()) / "flowtest_bot.db"
    tmp_db.unlink(missing_ok=True)
    config.DB_PATH = str(tmp_db)
    config.ADMIN_IDS = [ADMIN_ID]

    await db.init_db()
    run = Runner()
    s = run.session

    print("Сквозной прогон бота (сеть подменена заглушкой)\n")

    # 1. Старт
    s.reset()
    await run.send(USER_ID, "/start")
    check("Здравствуйте" in s.last_text(), "команда /start отвечает приветствием")
    check(len(await db.all_user_ids()) == 1, "пользователь запомнен в базе")
    check(s.calls[-1].reply_markup is not None, "к приветствию приложено меню")

    # 2. Список услуг
    s.reset()
    await run.click(USER_ID, "menu:services")
    check(len(s.edits()) == 1,
          "клик по «Услуги» редактирует ровно одно сообщение, нового не шлёт")
    keys = [b.callback_data for row in s.edits()[0].reply_markup.inline_keyboard
            for b in row]
    check(any(k.startswith("service:") for k in keys),
          f"в списке есть кнопки услуг ({len(keys)} кнопок)")

    # 3. Карточка услуги
    s.reset()
    await run.click(USER_ID, "service:basic")
    txt = s.last_text()
    check("Базовая услуга" in txt, "карточка показывает название услуги")
    check("от 1 000 ₽" in txt, "карточка показывает цену из конфига")

    # 4. Начало заявки
    s.reset()
    await run.click(USER_ID, "start_order:basic")
    check(config.ASK_NAME in s.last_text(), "после выбора услуги бот спрашивает имя")

    # 5. Слишком короткое имя не пропускаем
    s.reset()
    await run.send(USER_ID, "Я")
    check("слишком короткое" in s.last_text().lower(),
          "короткое имя отклоняется с подсказкой")

    # 6. Имя принято
    s.reset()
    await run.send(USER_ID, "Иван Петров")
    check(config.ASK_CONTACT in s.last_text(), "после имени бот спрашивает контакт")

    # 7. Контакт
    s.reset()
    await run.send(USER_ID, "+7 999 123-45-67")
    check(config.ASK_COMMENT in s.last_text(), "после контакта бот спрашивает комментарий")

    # 8. Комментарий и подтверждение
    s.reset()
    await run.send(USER_ID, "Нужен бот с оплатой <важно> & срочно")
    check("Иван Петров" in s.last_text(), "в подтверждении есть имя")
    check("+7 999 123-45-67" in s.last_text(), "в подтверждении есть контакт")
    check("&lt;важно&gt;" in s.last_text() or "&amp;" in s.last_text(),
          "опасные символы экранированы — разметка не сломается")

    # 9. Отправка
    s.reset()
    await run.click(USER_ID, "order:send")
    check("Заявка отправлена" in s.last_text(), "пользователь получает подтверждение")

    orders = await db.recent_orders(limit=10)
    check(len(orders) == 1, "заявка попала в базу")
    check(orders[0]["service"] == "Базовая услуга", "в заявке верная услуга")
    check(orders[0]["contact"] == "+7 999 123-45-67", "в заявке верный контакт")
    check(orders[0]["comment"] == "Нужен бот с оплатой <важно> & срочно",
          "комментарий сохранён как есть, без потерь")

    admin_msgs = s.messages_to(ADMIN_ID)
    check(len(admin_msgs) == 1, "администратор получил уведомление")
    check("Новая заявка №1" in admin_msgs[0].text, "в уведомлении есть номер заявки")
    check("&lt;важно&gt;" in admin_msgs[0].text,
          "в уведомлении администратора символы тоже экранированы")

    # 10. Состояние очищено — бот не зациклился
    s.reset()
    await run.send(USER_ID, "случайный текст")
    check("Не понял сообщение" in s.last_text(),
          "после заявки состояние сброшено, работает заглушка")

    # 11. Отмена на середине
    s.reset()
    await run.click(USER_ID, "start_order:pro")
    await run.send(USER_ID, "Пётр")
    s.reset()
    await run.send(USER_ID, "/cancel")
    check("отменена" in s.last_text(), "команда /cancel отменяет заполнение")

    # 12. Админ-панель
    s.reset()
    await run.send(ADMIN_ID, "/admin")
    check("Админ-панель" in s.last_text(), "админ получает панель по /admin")

    s.reset()
    await run.click(ADMIN_ID, "admin:stats")
    txt = s.last_text()
    check("Всего заявок: 1" in txt, "статистика считает заявки верно")
    check("Пользователей в боте: 1" in txt,
          "статистика считает пользователей верно (админ не делал /start)")

    s.reset()
    await run.click(ADMIN_ID, "admin:last")
    check(len(s.messages_to(ADMIN_ID)) >= 2, "список последних заявок отправлен")

    s.reset()
    await run.click(ADMIN_ID, "admin:done:1")
    orders = await db.recent_orders(limit=10, only_new=True)
    check(len(orders) == 0, "кнопка «обработана» меняет статус заявки")

    # 13. Обычный пользователь не имеет доступа к админке
    s.reset()
    await run.click(USER_ID, "admin:stats")
    check("Статистика" not in s.last_text(),
          "обычный пользователь не может открыть админку")

    # 14. Отмена заявки на шаге подтверждения
    s.reset()
    await run.click(USER_ID, "start_order:consult")
    await run.send(USER_ID, "Анна")
    await run.send(USER_ID, "anna@example.com")
    await run.send(USER_ID, "-")
    s.reset()
    await run.click(USER_ID, "order:cancel")
    check("отменена" in s.last_text(), "заявку можно отменить на подтверждении")
    orders = await db.recent_orders(limit=10)
    check(len(orders) == 1, "отменённая заявка в базу не попала")

    # 15. Прочерк в комментарии даёт пустую строку
    s.reset()
    await run.click(USER_ID, "start_order:urgent")
    await run.send(USER_ID, "Олег")
    await run.send(USER_ID, "tg: @oleg")
    await run.send(USER_ID, "-")
    check("Комментарий:</b> —" in s.last_text(),
          "прочерк показывается как «—», а не как пустота")
    await run.click(USER_ID, "order:send")
    orders = await db.recent_orders(limit=10)
    check(orders[0]["comment"] == "", "прочерк сохраняется пустой строкой")

    await run.bot.session.close()
    tmp_db.unlink(missing_ok=True)

    print(f"\nВсе {PASSED} проверок пройдены. Сценарий работает целиком.")


if __name__ == "__main__":
    asyncio.run(main())