"""Работа с базой данных SQLite: пользователи, заявки, выгрузка."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import aiosqlite

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
    first_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    username   TEXT,
    full_name  TEXT,
    service    TEXT NOT NULL,
    contact    TEXT NOT NULL,
    comment    TEXT,
    status     TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def remember_user(user_id: int, username: str | None, full_name: str) -> None:
    """Запоминает пользователя бота, чтобы потом можно было сделать рассылку."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, first_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username, full_name, _now()),
        )
        await db.commit()


async def create_order(
    user_id: int,
    username: str | None,
    full_name: str,
    service: str,
    contact: str,
    comment: str,
) -> int:
    """Сохраняет заявку и возвращает её номер."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders
                (user_id, username, full_name, service, contact, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, full_name, service, contact, comment, _now()),
        )
        await db.commit()
        return int(cursor.lastrowid or 0)


async def recent_orders(limit: int = 10, only_new: bool = False) -> list[dict]:
    """Последние заявки, свежие сверху."""
    query = "SELECT * FROM orders"
    params: tuple = ()
    if only_new:
        query += " WHERE status = 'new'"
    query += " ORDER BY id DESC LIMIT ?"
    params = (limit,)

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def mark_processed(order_id: int) -> None:
    """Помечает заявку обработанной."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = 'done' WHERE id = ?", (order_id,)
        )
        await db.commit()


async def stats() -> dict[str, int]:
    """Сводка: всего пользователей и заявок, из них новых."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders") as cursor:
            orders = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'new'"
        ) as cursor:
            new_orders = (await cursor.fetchone())[0]
    return {"users": users, "orders": orders, "new_orders": new_orders}


async def all_user_ids() -> list[int]:
    """ID всех, кто когда-либо запускал бота."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def export_orders_csv(path: str | Path) -> Path:
    """Выгружает все заявки в CSV для Excel."""
    rows = await recent_orders(limit=100000)
    path = Path(path)

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
            ["Номер", "Дата", "Услуга", "Имя", "Контакт", "Комментарий", "Статус"]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["service"],
                    row["full_name"],
                    row["contact"],
                    row["comment"] or "",
                    row["status"],
                ]
            )
    return path