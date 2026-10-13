"""
Самопроверка установки. Токен бота не нужен.

Запуск:
    python selftest.py

Если все строки начинаются с [OK] — шаблон готов к работе.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

# Чтобы русский текст не превращался в кракозябры в консоли Windows.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

import config
import database as db


def check(condition: bool, label: str) -> None:
    mark = "[OK]" if condition else "[ОШИБКА]"
    print(f"{mark} {label}")
    if not condition:
        raise SystemExit(1)


async def run() -> None:
    # Работаем во временной базе, чтобы не трогать настоящую.
    tmp_db = Path(tempfile.gettempdir()) / "selftest_bot.db"
    tmp_db.unlink(missing_ok=True)
    config.DB_PATH = str(tmp_db)

    print("Проверка шаблона Telegram-бота\n")

    check(len(config.SERVICES) > 0, f"услуги описаны: {len(config.SERVICES)} шт.")
    check(
        all(s.key and s.title and s.price for s in config.SERVICES),
        "у каждой услуги заполнены key, title и price",
    )
    check(
        len(config.SERVICES_BY_KEY) == len(config.SERVICES),
        "коды услуг уникальны",
    )

    await db.init_db()
    check(tmp_db.exists(), "база данных создаётся")

    await db.remember_user(111, "test_user", "Тестовый Пользователь")
    await db.remember_user(222, None, "Второй Пользователь")

    order_id = await db.create_order(
        user_id=111,
        username="test_user",
        full_name="Тестовый Пользователь",
        service=config.SERVICES[0].title,
        contact="+7 000 000-00-00",
        comment="Проверка <тег> и «кавычек»",
    )
    check(order_id == 1, f"заявка сохраняется, номер {order_id}")

    rows = await db.recent_orders(limit=10)
    check(len(rows) == 1, "заявка читается из базы")
    check(rows[0]["service"] == config.SERVICES[0].title, "услуга записана верно")

    new_rows = await db.recent_orders(limit=10, only_new=True)
    check(len(new_rows) == 1, "фильтр по новым заявкам работает")

    await db.mark_processed(order_id)
    new_rows = await db.recent_orders(limit=10, only_new=True)
    check(len(new_rows) == 0, "отметка «обработана» работает")

    summary = await db.stats()
    check(summary["users"] == 2, f"пользователей в базе: {summary['users']}")
    check(summary["orders"] == 1, f"заявок в базе: {summary['orders']}")

    ids = await db.all_user_ids()
    check(sorted(ids) == [111, 222], "список для рассылки собирается")

    csv_path = await db.export_orders_csv(Path(tempfile.gettempdir()) / "selftest.csv")
    text = csv_path.read_text(encoding="utf-8-sig")
    check("Тестовый Пользователь" in text, "выгрузка в CSV работает")
    csv_path.unlink(missing_ok=True)

    tmp_db.unlink(missing_ok=True)
    print("\nВсё в порядке. Дальше: заполните .env и запустите python bot.py")


if __name__ == "__main__":
    asyncio.run(run())