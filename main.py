"""KeyPulse — телеграм-бот для продажи лицензионных ключей с HWID-защитой.

Запускает одновременно:
  • aiogram long-polling (бот)
  • FastAPI/uvicorn (HWID API для плагинов и приложений)
  • keep-alive пинг собственного URL (чтобы Render free не усыплял сервис)
"""
import asyncio
import contextlib
import logging
import sys

import aiohttp
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import (
    ADMIN_ID, API_HOST, API_PORT, BOT_TOKEN,
    KEEPALIVE_INTERVAL, KEEPALIVE_URL, LIBSQL_URL,
)
from bot.database import init_db, close_db
from bot.handlers import user_router, admin_router
from bot.hwid_api import app as api_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("keypulse")


def build_bot() -> Bot:
    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
    dp.include_router(admin_router)
    return dp


async def run_api():
    config = uvicorn.Config(
        api_app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def ping_once(url: str) -> None:
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            await response.read()
            log.info("keep-alive: %s -> HTTP %s", url, response.status)


async def keepalive_loop(url: str, interval: int) -> None:
    """Пингует собственный публичный URL, чтобы Render не усыпил free-инстанс.

    Render гасит сервис после 15 минут без входящих запросов, поэтому интервал
    по умолчанию 600 секунд (10 минут) держит его постоянно активным.
    """
    if not url:
        return
    interval = max(60, interval)
    log.info("keep-alive включён: %s каждые %s сек", url, interval)
    while True:
        try:
            await ping_once(url)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("keep-alive ошибка: %s", exc)
        await asyncio.sleep(interval)


async def main():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN не задан в .env — запуск невозможен")
        return
    if not ADMIN_ID:
        log.warning("ADMIN_ID не задан — админ-панель будет недоступна")

    await init_db()
    log.info("База данных готова (%s)", "Turso/libSQL" if LIBSQL_URL else "SQLite")

    bot = build_bot()
    dp = build_dispatcher()

    me = await bot.get_me()
    log.info("Бот @%s запущен", me.username)

    api_task = asyncio.create_task(run_api(), name="hwid-api")
    log.info("HWID API слушает http://%s:%s", API_HOST, API_PORT)

    keepalive_task = asyncio.create_task(
        keepalive_loop(KEEPALIVE_URL, KEEPALIVE_INTERVAL), name="keepalive"
    )

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in (api_task, keepalive_task):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await bot.session.close()
        await close_db()
        log.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Выход")
