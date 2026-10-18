"""Общий бизнес-слой: выдача ключей, сброс HWID, заявки на оплату.

Используется и пользовательскими хэндлерами, и админкой, и HWID API,
чтобы логика не дублировалась.
"""
from datetime import datetime, timezone

from bot.database import (
    get_all_settings, get_all_texts, get_db, get_user
)
from bot.utils.keygen import generate_key, parse_key_format, calc_expires


async def create_key(user_id: int | None, days: int, label: str) -> str:
    """Генерирует уникальный ключ и сохраняет в БД."""
    settings = await get_all_settings()
    fmt = settings.get("key_format", "KP-XXXX-XXXX-XXXX")
    charset = settings.get("key_charset", "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    prefix, segs, seg_len = parse_key_format(fmt)

    async with get_db() as db:
        for _ in range(30):
            key = generate_key(prefix, segs, seg_len, charset)
            try:
                await db.execute(
                    "INSERT INTO license_keys(key,tariff_days,label,owner_id,created_at,expires_at) VALUES(?,?,?,?,?,?)",
                    (key, days, label, user_id, datetime.now(timezone.utc).isoformat(), calc_expires(days)),
                )
                await db.commit()
                return key
            except Exception:
                continue
    raise RuntimeError("Не удалось сгенерировать уникальный ключ")


async def issue_key(user_id: int, tariff, rub_paid: int = 0, stars_paid: int = 0) -> tuple[str, str]:
    """Выдаёт ключ по тарифу. Возвращает (ключ, готовый HTML-текст сообщения)."""
    days = tariff["days"]
    key = await create_key(user_id, days, tariff["label"])

    async with get_db() as db:
        await db.execute(
            "UPDATE users SET spent_rub=COALESCE(spent_rub,0)+?, spent_stars=COALESCE(spent_stars,0)+? WHERE user_id=?",
            (rub_paid, stars_paid, user_id),
        )
        await db.commit()

    texts = await get_all_texts()
    template = texts.get("payment_success", "✅ Оплата прошла! Ключ: {key}")
    text = template.format(key=key)
    if days == 0:
        text += "\n\n♾️ <b>Срок: навсегда</b>"
    else:
        text += f"\n\n⏳ <b>Срок: {days} дней</b>"
    return key, text


async def reset_user_hwid(user_id: int, rub_paid: int = 0, stars_paid: int = 0) -> str:
    """Снимает привязку HWID у пользователя и всех его ключей."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET hwid=NULL, spent_rub=COALESCE(spent_rub,0)+?, spent_stars=COALESCE(spent_stars,0)+? WHERE user_id=?",
            (rub_paid, stars_paid, user_id),
        )
        await db.execute(
            "UPDATE license_keys SET hwid=NULL, is_activated=0, activated_at=NULL WHERE owner_id=?",
            (user_id,),
        )
        await db.commit()

    texts = await get_all_texts()
    return texts.get("hwid_reset_success", "✅ HWID сброшен!")


async def create_payment_request(user_id: int, kind: str, amount_rub: int,
                                 tariff_id: int | None = None) -> int:
    """Создаёт заявку на оплату, ожидающую подтверждения админом."""
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO pending_payments(user_id,tariff_id,kind,amount_rub,status,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, tariff_id, kind, amount_rub, "await_admin",
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        return cur.lastrowid


async def get_payment(payment_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM pending_payments WHERE id=?", (payment_id,))
        return await cur.fetchone()


async def set_payment_status(payment_id: int, status: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE pending_payments SET status=? WHERE id=?", (status, payment_id))
        await db.commit()


async def user_display_name(user_id: int) -> str:
    user = await get_user(user_id)
    if not user:
        return f"ID {user_id}"
    name = user["full_name"] or "без имени"
    if user["username"]:
        return f"{name} (@{user['username']})"
    return f"{name} (ID {user_id})"
