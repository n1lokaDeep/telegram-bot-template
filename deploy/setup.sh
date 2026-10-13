#!/usr/bin/env bash
#
# Установка и обновление бота на сервере.
#
# Запускать от root на чистом Ubuntu 22.04 или 24.04:
#
#     bash setup.sh
#
# Скрипт можно запускать повторно — он обновит код и перезапустит бота,
# не тронув базу данных и файл .env.

set -euo pipefail

APP_DIR="/opt/tgbot"
RUN_USER="tgbot"
SERVICE="tgbot"
REPO="https://github.com/n1lokaDeep/telegram-bot-template.git"
# Файл юнита лежит рядом со скриптом, если он скачан вручную.
UNIT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tgbot.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "Запусти от root: sudo bash setup.sh" >&2
    exit 1
fi

echo "==> Пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl

echo "==> Отдельный пользователь для бота"
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$RUN_USER"
    echo "    создан пользователь $RUN_USER"
else
    echo "    пользователь $RUN_USER уже есть"
fi

echo "==> Код"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch --quiet origin
    git -C "$APP_DIR" reset --hard --quiet origin/main
    echo "    обновлено до последней версии"
else
    mkdir -p "$APP_DIR"
    git clone --quiet "$REPO" "$APP_DIR"
    echo "    склонировано в $APP_DIR"
fi

echo "==> Окружение Python"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
echo "    зависимости установлены"

echo "==> Файл .env"
if [ ! -f "$APP_DIR/.env" ]; then
    echo "    Токен бота выдаёт @BotFather, свой ID — @userinfobot."
    read -rp "    BOT_TOKEN: " BOT_TOKEN
    read -rp "    ADMIN_IDS: " ADMIN_IDS
    cat > "$APP_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
DB_PATH=bot.db
PROXY_URL=
EOF
    echo "    .env создан"
else
    echo "    .env уже есть — оставляю как есть"
fi

echo "==> Проверка кода без запуска бота"
# Если есть ошибки в настройках или базе — узнаем об этом до запуска.
if ! "$APP_DIR/.venv/bin/python" "$APP_DIR/selftest.py" >/tmp/tgbot_selftest.log 2>&1; then
    echo "    ПРОВЕРКА НЕ ПРОШЛА, смотри /tmp/tgbot_selftest.log" >&2
    tail -n 20 /tmp/tgbot_selftest.log >&2
    exit 1
fi
echo "    проверки пройдены"

echo "==> Права"
chown -R "$RUN_USER:$RUN_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> Служба systemd"
if [ -f "$UNIT_SRC" ]; then
    cp "$UNIT_SRC" "/etc/systemd/system/$SERVICE.service"
    echo "    юнит взят из deploy/tgbot.service"
else
    cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/bot.py
Restart=always
RestartSec=5
MemoryMax=512M
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE

[Install]
WantedBy=multi-user.target
EOF
    echo "    юнит сгенерирован"
fi

systemctl daemon-reload
systemctl enable --quiet "$SERVICE"
systemctl restart "$SERVICE"
sleep 4

echo
echo "==> Готово. Состояние:"
systemctl status "$SERVICE" --no-pager --lines=8 || true

cat <<'DONE'

Полезные команды:

  Логи в реальном времени:   journalctl -u tgbot -f
  Состояние:                 systemctl status tgbot
  Перезапустить:             systemctl restart tgbot
  Остановить:                systemctl stop tgbot
  Править .env:              sudo -u tgbot nano /opt/tgbot/.env
                             затем: systemctl restart tgbot

Бот поднимается сам после перезагрузки сервера и после падений —
вмешиваться не нужно.

Свой ID для ADMIN_IDS можно узнать у бота анкеты: отправьте ему /start —
он покажет ID прямо в приветствии, если ADMIN_IDS ещё пуст.
DONE
