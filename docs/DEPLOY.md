# Деплой KeyPulse на Railway / Render / Fly.io

Все три платформы запускают один процесс `python main.py` — он поднимает и бота, и HWID API.
Порт берётся из переменной `PORT`, которую платформа подставляет сама.

---

## Переменные окружения (обязательные на любой платформе)

| Переменная | Значение |
|---|---|
| `BOT_TOKEN` | токен от @BotFather |
| `ADMIN_ID` | `8554520733` |
| `API_SECRET` | длинная случайная строка |
| `DATABASE_PATH` | путь на постоянном диске (см. ниже) |

Опционально: `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`.

---

## Railway

**Вариант A — через сайт (проще)**

1. [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub repo** (залей папку в репозиторий).
2. В сервисе → **Variables** добавь `BOT_TOKEN`, `ADMIN_ID`, `API_SECRET`.
3. **Settings → Volumes** → *Add Volume*, mount path: `/app/data`.
4. Добавь переменную `DATABASE_PATH` = `/app/data/keypulse.db`.
5. **Settings → Networking → Generate Domain** — получишь URL для `/health`.
6. Deploy. Логи: **Deployments → View Logs**.

**Вариант B — через CLI**

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set BOT_TOKEN=... ADMIN_ID=8554520733 API_SECRET=...
railway volume add -m /app/data
railway up
```

> Без volume контейнер пересоздаётся и база обнуляется — все проданные ключи пропадут.

---

## Render

1. Запушь репозиторий на GitHub.
2. Render → **New → Blueprint**, выбери репозиторий (подхватит `render.yaml`).
3. Введи `BOT_TOKEN`, `ADMIN_ID`, `API_SECRET` в панели.
4. Blueprint создаст диск `/var/data` и пропишет `DATABASE_PATH=/var/data/keypulse.db`.

⚠️ На **free**-плане:
- диски недоступны → база теряется при деплое;
- инстанс засыпает после 15 минут без HTTP-трафика → бот перестаёт отвечать.

Для бота нужен план **Starter** ($7/мес) или выше.

---

## Fly.io

```bash
# 1. Установка CLI: https://fly.io/docs/flyctl/install/
fly auth signup

# 2. В папке проекта
fly launch --no-deploy --copy-config --name keypulse-bot --region ams

# 3. Постоянный диск под базу
fly volumes create keypulse_data --size 1 --region ams

# 4. Секреты
fly secrets set BOT_TOKEN="..." ADMIN_ID="8554520733" API_SECRET="..."

# 5. Деплой
fly deploy

# 6. Логи
fly logs
```

`fly.toml` уже настроен: `min_machines_running = 1` (машина не засыпает), healthcheck на `/health`, volume в `/data`.

Проверка: `curl https://keypulse-bot.fly.dev/health`

---

## После деплоя

1. Открой бота в Telegram → `/start` — должно прийти приветствие с кнопками.
2. `/panel` → проверь тарифы и тексты.
3. HWID API: `curl https://<домен>/health` → `{"status":"ok"}`.
4. Если API должен быть доступен плагину снаружи — оставь публичный домен; если нет — закрой порт/домен, бот продолжит работать.
5. Пропиши в `/panel → Настройки` реквизиты СБП (`sbp_requisites`), они показываются покупателю.

---

## Обновление

- **Railway/Render** — `git push`, платформа пересоберёт сама.
- **Fly.io** — `fly deploy`.

База на volume сохраняется между деплоями.

---

## Если платформа засыпает

Признак: бот молчит несколько часов, потом отвечает с задержкой; в логах «machine stopped».
Решение: отключить sleep (`min_machines_running = 1` на Fly, платный план на Render, `restartPolicyType: ALWAYS` на Railway).
