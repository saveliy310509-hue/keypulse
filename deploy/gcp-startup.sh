#!/usr/bin/env bash
# Cloud-init / startup-script для Google Cloud e2-micro (Always Free).
#
# Как использовать:
#   1. Создай VM (см. docs/FREE_HOSTING.md)
#   2. В "Metadata" добавь ключ startup-script и вставь этот файл
#   3. Через 2-3 минуты бот уже работает
#
# Или одной командой при создании:
#   gcloud compute instances create keypulse \
#     --zone=us-central1-a --machine-type=e2-micro \
#     --image-family=debian-12 --image-project=debian-cloud \
#     --metadata=startup-script-url=https://raw.githubusercontent.com/USER/REPO/main/deploy/gcp-startup.sh

set -euo pipefail

exec > >(tee -a /var/log/keypulse-install.log) 2>&1

REPO_URL="${REPO_URL:-}"          # например https://github.com/user/keypulse.git
BOT_TOKEN="${BOT_TOKEN:-}"
ADMIN_ID="${ADMIN_ID:-}"
API_SECRET="${API_SECRET:-}"

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git sqlite3

if ! id -u keypulse >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin keypulse
fi

APP_DIR=/opt/keypulse
if [ -n "$REPO_URL" ] && [ ! -d "$APP_DIR/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

if [ ! -f "$APP_DIR/main.py" ]; then
    echo "Нет кода в $APP_DIR — передай REPO_URL в metadata"
    exit 0
fi

cd "$APP_DIR"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
    # безопасно подставляем значения (без sed-экранирования спецсимволов)
    BOT_TOKEN="$BOT_TOKEN" ADMIN_ID="$ADMIN_ID" API_SECRET="$API_SECRET" python3 - <<'PY'
import os, pathlib

path = pathlib.Path(".env")
values = {
    "BOT_TOKEN": os.environ.get("BOT_TOKEN", ""),
    "ADMIN_ID": os.environ.get("ADMIN_ID", ""),
    "API_SECRET": os.environ.get("API_SECRET", ""),
}
lines = []
for line in path.read_text(encoding="utf-8").splitlines():
    key = line.split("=", 1)[0].strip()
    if key in values and values[key]:
        lines.append(f"{key}={values[key]}")
    else:
        lines.append(line)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
fi
chmod 600 .env

mkdir -p data
chown -R keypulse:keypulse "$APP_DIR"

cat > /etc/systemd/system/keypulse.service <<UNIT
[Unit]
Description=KeyPulse Telegram Bot + HWID API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=keypulse
Group=keypulse
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=5
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now keypulse
echo "KeyPulse установлен и запущен"
