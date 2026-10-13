"""
Настройки бота.

ЭТО ЕДИНСТВЕННЫЙ ФАЙЛ, который правится под нового заказчика.
Код в остальных файлах менять не нужно.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# ───────────────────────────── доступ ─────────────────────────────

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")


def _parse_admins(raw: str) -> list[int]:
    """Разбирает строку вида "123456, 789012" в список чисел."""
    ids: list[int] = []
    for chunk in raw.replace(" ", "").split(","):
        if chunk.lstrip("-").isdigit():
            ids.append(int(chunk))
    return ids


# Кто получает заявки и видит админ-панель.
# Свой ID можно узнать у бота @userinfobot.
ADMIN_IDS: list[int] = _parse_admins(os.getenv("ADMIN_IDS", ""))

DB_PATH: str = os.getenv("DB_PATH", "bot.db")

# Прокси для доступа к Telegram API.
#
# В России api.telegram.org блокируется на уровне TCP: пинг проходит,
# а соединение не устанавливается. Симптом — бот запускается и молчит.
# В этом случае укажите прокси, например:
#   socks5://127.0.0.1:1080
#   http://127.0.0.1:8080
# Если Telegram доступен напрямую, оставьте пустым.
PROXY_URL: str = os.getenv("PROXY_URL", "")

# ─────────────────────── тексты для заказчика ─────────────────────

COMPANY_NAME = "Название компании"
TAGLINE = "одной строкой, чем вы занимаетесь"

GREETING = (
    f"Здравствуйте! Это бот «{COMPANY_NAME}».\n\n"
    "Здесь можно посмотреть услуги и цены, а также оставить заявку — "
    "мы свяжемся с вами и ответим на вопросы."
)

ABOUT = (
    f"«{COMPANY_NAME}» — {TAGLINE}.\n\n"
    "Работаем по будням с 9:00 до 19:00."
)

CONTACTS = (
    "Телефон: +7 000 000-00-00\n"
    "Адрес: город, улица, дом\n"
    "Сайт: example.ru"
)

FALLBACK = "Не понял сообщение. Воспользуйтесь кнопками ниже или отправьте /start."

# ────────────────────────────── услуги ──────────────────────────────
# key     — служебный код, латиницей, менять не нужно
# title   — название в списке
# price   — как показывать цену
# details — текст в карточке услуги


@dataclass(frozen=True)
class Service:
    key: str
    title: str
    price: str
    details: str


SERVICES: list[Service] = [
    Service(
        key="consult",
        title="Консультация",
        price="бесплатно",
        details="Разберём ваш вопрос и подскажем, что делать дальше.",
    ),
    Service(
        key="basic",
        title="Базовая услуга",
        price="от 1 000 ₽",
        details="Что входит в услугу, сколько времени занимает и что нужно от вас.",
    ),
    Service(
        key="pro",
        title="Услуга «под ключ»",
        price="от 3 000 ₽",
        details="Полный цикл: подготовка, выполнение, проверка результата.",
    ),
    Service(
        key="urgent",
        title="Срочно, в день обращения",
        price="от 5 000 ₽",
        details="Берём в работу вне очереди и сдаём в тот же день.",
    ),
]

SERVICES_BY_KEY: dict[str, Service] = {s.key: s for s in SERVICES}

# ──────────────────────── сценарий заявки ────────────────────────

ASK_NAME = "Как вас зовут?"
ASK_CONTACT = "Как с вами связаться? Телефон, Telegram или e-mail."
ASK_COMMENT = "Опишите задачу коротко. Если нечего добавить — отправьте «-»."
ASK_CONFIRM = "Проверьте заявку перед отправкой:"

ORDER_ACCEPTED = "Заявка отправлена! Мы свяжемся с вами, как только увидим её."
ORDER_CANCELLED = "Заявка отменена. Если понадобится — просто напишите снова."

BROADCAST_ASK = "Отправьте текст, который нужно разослать всем пользователям бота."
BROADCAST_DONE = "Рассылка завершена: доставлено {sent}, не доставлено {failed}."