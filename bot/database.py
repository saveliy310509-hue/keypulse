import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from bot.config import DATABASE_PATH

DEFAULT_TEXTS = {
    "welcome_title": "Добро пожаловать в KeyPulse",
    "welcome_text": (
        "<b>🔑 KeyPulse — генератор лицензионных ключей</b>\n\n"
        "✨ Премиум ключи для приложений, плагинов Minecraft и не только!\n"
        "🛡️ Защита <b>HWID</b> — один ключ = одно устройство\n"
        "⚡️ Мгновенная выдача после оплаты\n"
        "💎 Поддержка <b>СБП</b> и <b>Telegram Stars</b>\n\n"
        "<i>👇 Выбери действие ниже:</i>"
    ),
    "shop_title": "<b>🛒 Магазин ключей</b>\n\nВыбери тариф:",
    "profile_template": (
        "<b>👤 Профиль — {name}</b>\n\n"
        "🆔 ID: <code>{user_id}</code>\n"
        "📅 Регистрация: {reg_date}\n"
        "💰 Баланс: <b>{balance} ₽</b>\n"
        "🔑 Ключей куплено: <b>{total_keys}</b>\n"
        "✅ Активировано: <b>{activated_keys}</b>\n"
        "💸 Потрачено: <b>{spent_rub} ₽</b> / <b>{spent_stars} ⭐️</b>\n"
        "🖥 HWID: <code>{hwid}</code>"
    ),
    "hwid_title": (
        "<b>🔧 Сброс HWID</b>\n\n"
        "Текущий HWID: <code>{hwid}</code>\n"
        "После сброса сможешь активировать тот же ключ на новом железе.\n"
        "Стоимость сброса указана на кнопке ниже."
    ),
    "payment_choose": "<b>💳 Выбери способ оплаты:</b>",
    "sbp_requisites": (
        "💳 <b>Реквизиты СБП:</b>\n"
        "<code>+7 900 000-00-00</code>\n"
        "Получатель: Иван И.\n\n"
        "<i>В комментарии к переводу укажи номер заявки.</i>"
    ),
    "sbp_request_created": (
        "<b>💳 Заявка #{payment_id} создана</b>\n\n"
        "📦 {item}\n"
        "💵 К оплате: <b>{amount} ₽</b>\n\n"
        "{requisites}\n\n"
        "<i>После перевода нажми «Я оплатил» — админ проверит и выдаст ключ.</i>"
    ),
    "payment_success": "<b>✅ Оплата прошла успешно!</b>\n\nТвой ключ:\n<code>{key}</code>\n\n<i>⚠️ Никому не показывай ключ! Он привяжется к HWID при первой активации.</i>",
    "hwid_reset_success": "<b>✅ HWID успешно сброшен!</b>\nТеперь можешь активировать ключ заново.",
    "no_hwid": "не привязан",
}

DEFAULT_SETTINGS = {
    "currency_symbol": "₽",
    "star_rate": "1",  # сколько рублей = 1 звезда
    "key_format": "KP-XXXX-XXXX-XXXX",
    "key_prefix": "KP",
    "key_segments": "4",
    "key_segment_len": "4",
    "key_charset": "ABCDEFGHJKLMNPQRSTUVWXYZ23456789",
    "hwid_reset_price_rub": "149",
    "hwid_reset_price_stars": "75",
    "media_file_id": "",  # file_id фото/видео для приветствия
    "media_type": "photo",  # photo / video / animation / none
}

DEFAULT_TARIFFS = [
    {"days": 15, "label": "15 дней", "price_rub": 199, "price_stars": 100, "is_active": 1, "sort": 1},
    {"days": 30, "label": "30 дней", "price_rub": 349, "price_stars": 175, "is_active": 1, "sort": 2},
    {"days": 365, "label": "365 дней", "price_rub": 1999, "price_stars": 1000, "is_active": 1, "sort": 3},
    {"days": 0, "label": "Навсегда", "price_rub": 4999, "price_stars": 2500, "is_active": 1, "sort": 4},
]

DEFAULT_BUTTONS = {
    "btn_get_key": "🔑 Получить ключ",
    "btn_profile": "👤 Мой профиль",
    "btn_reset_hwid": "🔧 Сбросить HWID",
    "btn_back": "◀️ Назад",
    "btn_pay_sbp": "💳 Оплатить СБП",
    "btn_pay_stars": "⭐️ Оплатить Звёздами",
    "btn_pay_sent": "✅ Я оплатил",
    "btn_reset_pay_sbp": "💳 Сбросить (СБП)",
    "btn_reset_pay_stars": "⭐️ Сбросить (Звёзды)",
    "btn_panel": "⚙️ Админ-панель",
}


@asynccontextmanager
async def get_db():
    """Асинхронный контекстный менеджер подключения к SQLite.

    Использование:  async with get_db() as db: ...
    """
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    async with get_db() as db:
        # --- users ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                reg_date TEXT,
                balance INTEGER DEFAULT 0,
                spent_rub INTEGER DEFAULT 0,
                spent_stars INTEGER DEFAULT 0,
                hwid TEXT DEFAULT NULL
            )
        """)
        # --- keys ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS license_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                tariff_days INTEGER NOT NULL,
                label TEXT,
                owner_id INTEGER,
                is_activated INTEGER DEFAULT 0,
                hwid TEXT DEFAULT NULL,
                activated_at TEXT DEFAULT NULL,
                expires_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES users(user_id)
            )
        """)
        # --- tariffs ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tariffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                days INTEGER NOT NULL,
                label TEXT NOT NULL,
                price_rub INTEGER NOT NULL,
                price_stars INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                sort INTEGER DEFAULT 0
            )
        """)
        # --- settings / texts / buttons ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS texts (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS buttons (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # --- pending payments ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tariff_id INTEGER,
                kind TEXT NOT NULL,
                amount_rub INTEGER,
                amount_stars INTEGER,
                method TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)

        # Seed defaults if empty
        cur = await db.execute("SELECT COUNT(*) FROM texts")
        if (await cur.fetchone())[0] == 0:
            for k, v in DEFAULT_TEXTS.items():
                await db.execute("INSERT INTO texts(key,value) VALUES(?,?)", (k, v))
        cur = await db.execute("SELECT COUNT(*) FROM settings")
        if (await cur.fetchone())[0] == 0:
            for k, v in DEFAULT_SETTINGS.items():
                await db.execute("INSERT INTO settings(key,value) VALUES(?,?)", (k, v))
        cur = await db.execute("SELECT COUNT(*) FROM buttons")
        if (await cur.fetchone())[0] == 0:
            for k, v in DEFAULT_BUTTONS.items():
                await db.execute("INSERT INTO buttons(key,value) VALUES(?,?)", (k, v))
        cur = await db.execute("SELECT COUNT(*) FROM tariffs")
        if (await cur.fetchone())[0] == 0:
            for t in DEFAULT_TARIFFS:
                await db.execute(
                    "INSERT INTO tariffs(days,label,price_rub,price_stars,is_active,sort) VALUES(?,?,?,?,?,?)",
                    (t["days"], t["label"], t["price_rub"], t["price_stars"], t["is_active"], t["sort"]),
                )
        await db.commit()


# ---------- CRUD helpers ----------

async def get_user(user_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()


async def ensure_user(user_id: int, username: str | None, full_name: str):
    async with get_db() as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if await cur.fetchone() is None:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO users(user_id,username,full_name,reg_date) VALUES(?,?,?,?)",
                (user_id, username or "", full_name, now),
            )
            await db.commit()
        else:
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE user_id=?",
                (username or "", full_name, user_id),
            )
            await db.commit()


async def get_all_texts() -> dict:
    async with get_db() as db:
        cur = await db.execute("SELECT key,value FROM texts")
        return {r["key"]: r["value"] for r in await cur.fetchall()}


async def get_all_settings() -> dict:
    async with get_db() as db:
        cur = await db.execute("SELECT key,value FROM settings")
        return {r["key"]: r["value"] for r in await cur.fetchall()}


async def get_all_buttons() -> dict:
    async with get_db() as db:
        cur = await db.execute("SELECT key,value FROM buttons")
        return {r["key"]: r["value"] for r in await cur.fetchall()}


async def get_tariffs(active_only=False):
    async with get_db() as db:
        q = "SELECT * FROM tariffs"
        if active_only:
            q += " WHERE is_active=1"
        q += " ORDER BY sort"
        cur = await db.execute(q)
        return await cur.fetchall()


async def get_tariff(tariff_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM tariffs WHERE id=?", (tariff_id,))
        return await cur.fetchone()


async def get_setting(key: str, default=""):
    async with get_db() as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else default


async def set_setting(key: str, value: str):
    async with get_db() as db:
        await db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        await db.commit()


async def set_text(key: str, value: str):
    async with get_db() as db:
        await db.execute("INSERT OR REPLACE INTO texts(key,value) VALUES(?,?)", (key, value))
        await db.commit()


async def set_button(key: str, value: str):
    async with get_db() as db:
        await db.execute("INSERT OR REPLACE INTO buttons(key,value) VALUES(?,?)", (key, value))
        await db.commit()


async def count_user_keys(user_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM license_keys WHERE owner_id=?", (user_id,))
        total = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM license_keys WHERE owner_id=? AND is_activated=1", (user_id,))
        activated = (await cur.fetchone())[0]
        return total, activated
