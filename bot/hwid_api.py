"""
HWID API — FastAPI сервер для проверки/активации ключей из Minecraft плагинов / приложений.
Подключается к той же SQLite базе что и бот.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from bot.config import API_SECRET, DATABASE_PATH
from bot.database import get_db

app = FastAPI(title="KeyPulse HWID API", version="1.0.0")

class ActivateRequest(BaseModel):
    key: str
    hwid: str

class ActivateResponse(BaseModel):
    ok: bool
    message: str
    expires_at: Optional[str] = None
    days: Optional[int] = None

class VerifyRequest(BaseModel):
    key: str
    hwid: str

def _check_secret(x_api_secret: str | None):
    if API_SECRET and x_api_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API secret. Pass X-Api-Secret header.")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "KeyPulse HWID API"}

@app.post("/api/activate", response_model=ActivateResponse)
async def activate(req: ActivateRequest, x_api_secret: str | None = Header(default=None)):
    _check_secret(x_api_secret)
    key = req.key.strip()
    hwid = req.hwid.strip()
    if not key or not hwid:
        return ActivateResponse(ok=False, message="key и hwid обязательны")
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM license_keys WHERE key=?", (key,))
        row = await cur.fetchone()
        if not row:
            return ActivateResponse(ok=False, message="Ключ не найден")
        # проверка срока
        if row["expires_at"]:
            try:
                exp = datetime.fromisoformat(row["expires_at"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    return ActivateResponse(ok=False, message="Срок действия ключа истёк", expires_at=row["expires_at"])
            except Exception:
                pass
        # если уже активирован
        if row["is_activated"]:
            if row["hwid"] == hwid:
                # тот же HWID — ок
                return ActivateResponse(ok=True, message="Ключ уже активирован на этом устройстве", expires_at=row["expires_at"], days=row["tariff_days"])
            else:
                return ActivateResponse(ok=False, message="Ключ уже активирован на другом устройстве. Сбрось HWID через бота.")
        # активируем
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE license_keys SET is_activated=1, hwid=?, activated_at=? WHERE key=?",
            (hwid, now, key),
        )
        # также обновляем hwid у владельца если пусто
        if row["owner_id"]:
            cur2 = await db.execute("SELECT hwid FROM users WHERE user_id=?", (row["owner_id"],))
            u = await cur2.fetchone()
            if u and not u["hwid"]:
                await db.execute("UPDATE users SET hwid=? WHERE user_id=?", (hwid, row["owner_id"]))
        await db.commit()
        return ActivateResponse(ok=True, message="Ключ успешно активирован!", expires_at=row["expires_at"], days=row["tariff_days"])

@app.post("/api/verify", response_model=ActivateResponse)
async def verify(req: VerifyRequest, x_api_secret: str | None = Header(default=None)):
    _check_secret(x_api_secret)
    key = req.key.strip()
    hwid = req.hwid.strip()
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM license_keys WHERE key=?", (key,))
        row = await cur.fetchone()
        if not row:
            return ActivateResponse(ok=False, message="Ключ не найден")
        if not row["is_activated"]:
            return ActivateResponse(ok=False, message="Ключ ещё не активирован. Вызови /api/activate")
        if row["hwid"] != hwid:
            return ActivateResponse(ok=False, message="HWID не совпадает")
        if row["expires_at"]:
            try:
                exp = datetime.fromisoformat(row["expires_at"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    return ActivateResponse(ok=False, message="Срок действия истёк", expires_at=row["expires_at"])
            except Exception:
                pass
        return ActivateResponse(ok=True, message="Ключ валиден", expires_at=row["expires_at"], days=row["tariff_days"])

@app.post("/api/reset-hwid")
async def reset_hwid(req: VerifyRequest, x_api_secret: str | None = Header(default=None)):
    """Сброс HWID по ключу (требует секрет). Используется ботом после оплаты."""
    _check_secret(x_api_secret)
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM license_keys WHERE key=?", (req.key.strip(),))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ключ не найден")
        await db.execute("UPDATE license_keys SET hwid=NULL, is_activated=0, activated_at=NULL WHERE key=?", (req.key.strip(),))
        await db.commit()
        return {"ok": True, "message": "HWID сброшен"}

@app.get("/api/key/{key}")
async def get_key_info(key: str, x_api_secret: str | None = Header(default=None)):
    _check_secret(x_api_secret)
    async with get_db() as db:
        cur = await db.execute("SELECT key,tariff_days,label,is_activated,hwid,expires_at,created_at,owner_id FROM license_keys WHERE key=?", (key,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ключ не найден")
        return dict(row)
