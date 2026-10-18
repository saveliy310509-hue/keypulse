# 🔑 KeyPulse

Телеграм-бот для продажи лицензионных ключей с **HWID-привязкой**: ключ активируется один раз и на одном устройстве, повторная активация невозможна ни владельцем, ни другим пользователем — пока не сделан сброс HWID.

- 🐍 Python 3.12 + aiogram 3
- 🗄 SQLite (aiosqlite), без внешних сервисов
- 🌐 FastAPI HWID API — для Minecraft-плагинов и любых приложений
- 💎 Оплата: Telegram Stars (нативно) и СБП (YooKassa или подтверждение админом)
- ⚙️ Всё редактируется из админ-панели: тексты, кнопки, цены, тарифы, формат ключей

---

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

`.env` уже заполнен:

```env
BOT_TOKEN=<BOT_TOKEN>
ADMIN_ID=8554520733
API_HOST=0.0.0.0
API_PORT=8080
API_SECRET=<API_SECRET>
DATABASE_PATH=data/keypulse.db
```

При первом запуске база создаётся автоматически и заполняется дефолтными текстами, кнопками и 4 тарифами (15 / 30 / 365 дней / Навсегда).

---

## Структура

```
KeyPulse/
├── main.py                 # запуск: polling + FastAPI в одном процессе
├── .env                    # токен, админ, секрет API
├── requirements.txt
├── bot/
│   ├── config.py           # чтение .env
│   ├── database.py         # схема + CRUD + сиды
│   ├── services.py         # выдача ключей, сброс HWID, заявки на оплату
│   ├── hwid_api.py         # FastAPI: activate / verify / reset-hwid
│   ├── handlers/
│   │   ├── user.py         # /start, магазин, профиль, HWID, оплата
│   │   └── admin.py        # /panel
│   └── utils/
│       ├── keygen.py       # генерация ключей по шаблону
│       ├── keyboards.py    # все клавиатуры
│       └── helpers.py
└── data/keypulse.db        # база (создаётся сама)
```

Всё общение идёт **в одном сообщении**: бот редактирует его (`edit_text`), а не спамит новыми.

---

## Пользовательский сценарий

**/start** → приветствие + медиа (если задано) + кнопки:

```
[ 🔑 Получить ключ ] [ 👤 Мой профиль ]
[         🔧 Сбросить HWID            ]
```

**Получить ключ** → тарифы (3 сверху, 1 снизу):

```
[ 15 дней — 199₽ ] [ 30 дней — 349₽ ] [ 365 дней — 1999₽ ]
[                   Навсегда — 4999₽                      ]
[                        ◀️ Назад                          ]
```

**Тариф** → выбор оплаты:

```
[ 💳 Оплатить СБП ] [ ⭐️ Оплатить Звёздами ]
[                 ◀️ Назад                  ]
```

- **Stars** — `send_invoice` с `currency="XTR"`, ключ приходит сразу после оплаты.
- **СБП без YooKassa** — создаётся заявка, пользователь видит реквизиты и жмёт «Я оплатил», админу приходит сообщение с кнопками `✅ Подтвердить` / `❌ Отклонить`. После подтверждения ключ уходит пользователю.
- **СБП с YooKassa** — заполни `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY`, появится реальная ссылка на оплату и проверка статуса.

**Мой профиль** — имя, ID, дата регистрации, баланс, куплено ключей, активировано, потрачено ₽/⭐️, текущий HWID.

**Сбросить HWID** — показывает цену сброса, после оплаты снимает привязку со всех ключей пользователя, и ключ снова можно активировать на другом железе.

---

## Админ-панель `/panel`

Команда видна только `ADMIN_ID`. Для остальных она **молча игнорируется** — ни ответа, ни ошибки. Чтобы скрыть её из списка команд, удали её в @BotFather (`/setcommands`).

| Раздел | Что делает |
|---|---|
| 📝 Тексты | редактирование любого текста бота (HTML) |
| 🔘 Кнопки | переименование любой кнопки, с эмодзи |
| ⚙️ Настройки | формат ключа, charset, цены сброса HWID, медиа |
| 💰 Тарифы | добавить/изменить/скрыть/удалить, цены в ₽ и ⭐️ |
| 🔑 Генерация ключей | N ключей, любые дни, любой формат, выдача конкретному ID |
| 📊 Статистика | юзеры, ключи, активации, выручка, последние платежи |
| 🔍 Найти ключ | поиск по части ключа с HWID и владельцем |
| 📋 Последние ключи | 15 последних |

### Формат ключа

Задаётся шаблоном в настройках, `X` — случайный символ из charset:

```
KP-XXXX-XXXX-XXXX   →  KP-7F3A-9K2M-QW4Z
XXXX-XXXX-XXXX-XXXX →  4 сегмента без префикса
KEY-XXXXXXXX        →  KEY-A1B2C3D4
```

### Медиа в приветствии

Отправь боту фото/видео/GIF в разделе **⚙️ Настройки → media_file_id** — бот сохранит `file_id` и тип автоматически.

---

## HWID API

Отдельный HTTP-сервер (по умолчанию `0.0.0.0:8080`), работает с той же базой.

Заголовок авторизации: `X-Api-Secret: <API_SECRET из .env>`.

| Метод | Эндпоинт | Назначение |
|---|---|---|
| GET | `/health` | проверка живости |
| POST | `/api/activate` | активировать ключ на HWID |
| POST | `/api/verify` | проверить ключ + HWID |
| POST | `/api/reset-hwid` | снять привязку (для бота) |
| GET | `/api/key/{key}` | информация о ключе |

```bash
curl -X POST http://localhost:8080/api/activate \
  -H "X-Api-Secret: <API_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"key":"KP-7F3A-9K2M-QW4Z","hwid":"AA-BB-CC-DD"}'
```

```json
{"ok": true, "message": "Ключ успешно активирован!", "expires_at": "2026-11-17T12:00:00+00:00", "days": 30}
```

Логика:
- ключ не найден → `ok: false`
- срок истёк → `ok: false`
- уже активирован на этом HWID → `ok: true`
- уже активирован на другом → `ok: false` («сбрось HWID через бота»)
- свободен → активируется, HWID пишется в ключ и в профиль владельца

Подробнее и пример для Minecraft-плагина: [docs/HWID_API.md](docs/HWID_API.md).

---

## Хостинг

**Render free без сна** → [docs/RENDER.md](docs/RENDER.md): keep-alive + база в Turso, чтобы ключи не терялись при рестарте.

**Бесплатный 24/7 на VM** → [docs/FREE_HOSTING.md](docs/FREE_HOSTING.md): GCP e2-micro и Oracle Always Free.

### Render.com (free)

`render.yaml` уже настроен. В Render задай переменные:

| Переменная | Зачем |
|---|---|
| `BOT_TOKEN`, `ADMIN_ID`, `API_SECRET` | базовое |
| `LIBSQL_URL`, `LIBSQL_AUTH_TOKEN` | база в [Turso](https://turso.tech) — на free-плане диск стирается |
| `KEEPALIVE_URL` | `https://<сервис>.onrender.com/health` — бот сам себя будит |

### Одна команда на Ubuntu/Debian VPS

```bash
sudo REPO_URL=https://github.com/USER/keypulse.git bash deploy/install.sh
sudo nano /opt/keypulse/.env     # BOT_TOKEN, ADMIN_ID, API_SECRET
sudo systemctl restart keypulse
```

Скрипт сам ставит зависимости, создаёт venv, пользователя `keypulse`, systemd-юнит с `Restart=always` и включает автозапуск.

### Docker

```bash
docker compose up -d --build
docker compose logs -f
```

Порт `8080` проброшен наружу — если HWID API не нужен снаружи, убери `ports` из `docker-compose.yml`. База живёт в volume `./data`.

### VPS + systemd вручную

```bash
apt update && apt install -y python3 python3-venv
git clone <repo> /opt/keypulse && cd /opt/keypulse
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp deploy/keypulse.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now keypulse
journalctl -u keypulse -f
```

### Railway / Render / Fly.io

- Build: `pip install -r requirements.txt`
- Start: `python main.py`
- Переменные окружения — те же, что в `.env`
- Порт API берётся из `$PORT`, которую подставляет платформа

> ⚠️ SQLite на эфемерных хостингах (Railway/Render free) теряется при ребилде — подключи постоянный volume. На free-планах Render/Railway бот ещё и засыпает, для 24/7 нужна VM.

### Бэкапы

```bash
sudo cp deploy/backup.sh /opt/keypulse/backup.sh && sudo chmod +x /opt/keypulse/backup.sh
sudo crontab -e   # 0 4 * * * /opt/keypulse/backup.sh >> /var/log/keypulse-backup.log 2>&1
```

---

## Безопасность

- `API_SECRET` — смени на длинный случайный, иначе любой сможет активировать/сбрасывать ключи.
- Не коммить `.env` в git (уже в `.gitignore`).
- Токен бота засветился в переписке — **перевыпусти его** у @BotFather и обнови `.env`.
- YooKassa-ключи держи только в переменных окружения.
- Админ-панель защищена проверкой `user_id == ADMIN_ID` на каждом колбэке, не только на входе.

---

## Проверено

- ✅ генерация ключей по шаблону, уникальность
- ✅ выдача после Stars/подтверждения админом, статистика трат
- ✅ сброс HWID снимает привязку со всех ключей пользователя
- ✅ HWID API: повторная активация на другом устройстве отклоняется
- ✅ админ-панель: тексты, кнопки, тарифы, генерация, статистика
- ✅ не-админ не видит `/panel` и не может нажать админ-кнопки
