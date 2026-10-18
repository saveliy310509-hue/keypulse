#!/usr/bin/env bash
# KeyPulse — установка на чистый Ubuntu/Debian VPS (Oracle Cloud, GCP, любой)
#
# Использование:
#   sudo bash install.sh                      # код уже лежит в /opt/keypulse
#   sudo REPO_URL=https://github.com/user/keypulse.git bash install.sh
#
# Что делает:
#   1. ставит python3-venv, git, sqlite3
#   2. создаёт пользователя keypulse
#   3. разворачивает код в /opt/keypulse и venv
#   4. создаёт .env из .env.example (если нет)
#   5. ставит systemd-юнит с автоперезапуском
#   6. поднимает firewall (ufw), если он есть

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/keypulse}"
APP_USER="${APP_USER:-keypulse}"
REPO_URL="${REPO_URL:-}"
SERVICE_NAME="keypulse"

log() { echo -e "\033[1;36m==> $*\033[0m"; }
warn() { echo -e "\033[1;33m[!] $*\033[0m"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Запусти через sudo: sudo bash install.sh"
    exit 1
fi

log "Ставлю системные пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git sqlite3 curl ca-certificates

log "Создаю пользователя $APP_USER"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

log "Разворачиваю код в $APP_DIR"
mkdir -p "$APP_DIR"
if [ -n "$REPO_URL" ]; then
    if [ -d "$APP_DIR/.git" ]; then
        git -C "$APP_DIR" pull --ff-only
    else
        git clone --depth 1 "$REPO_URL" "$APP_DIR"
    fi
elif [ ! -f "$APP_DIR/main.py" ]; then
    warn "В $APP_DIR нет main.py. Скопируй проект туда и запусти скрипт снова,"
    warn "либо передай REPO_URL=https://.../keypulse.git"
    exit 1
fi

cd "$APP_DIR"

log "Виртуальное окружение и зависимости"
if [ ! -x ".venv/bin/python" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

log "Файл .env"
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    warn "Создан $APP_DIR/.env — впиши BOT_TOKEN, ADMIN_ID и API_SECRET:"
    warn "  sudo nano $APP_DIR/.env"
else
    chmod 600 .env
fi

mkdir -p data
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

log "systemd-юнит"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<UNIT
[Unit]
Description=KeyPulse Telegram Bot + HWID API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/main.py
Restart=always
RestartSec=5
StartLimitIntervalSec=0
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true

if grep -q "^BOT_TOKEN=.\+" "$APP_DIR/.env"; then
    systemctl restart "$SERVICE_NAME"
    log "Сервис запущен"
else
    warn "BOT_TOKEN пустой — сервис не стартую. Заполни .env и выполни:"
    warn "  sudo systemctl start $SERVICE_NAME"
fi

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
    log "Открываю порт 8080 (HWID API) в ufw"
    ufw allow 8080/tcp >/dev/null || true
fi

log "Готово"
echo
echo "Полезные команды:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo "  sudo systemctl restart $SERVICE_NAME"
echo
echo "Проверка API: curl http://127.0.0.1:8080/health"
