"""KeyPulse — телеграм-бот для продажи лицензионных ключей с HWID-защитой.

Запускает одновременно:
  • aiogram long-polling (бот)
  • FastAPI/uvicorn (HWID API для плагинов и приложений)
"""
import asyncio
import contextlib
import logging
import sys

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import API_HOST, API_PORT, BOT_TOKEN, ADMIN_ID
from bot.database import init_db
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
    # user_router первым: он не должен перехватывать состояния админки,
    # но и админские хэндлеры состояний ниже по приоритету
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


async def main():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN не задан в .env — запуск невозможен")
        return
    if not ADMIN_ID:
        log.warning("ADMIN_ID не задан — админ-панель будет недоступна")

    await init_db()
    log.info("База данных готова")

    bot = build_bot()
    dp = build_dispatcher()

    me = await bot.get_me()
    log.info("Бот @%s запущен", me.username)

    api_task = asyncio.create_task(run_api(), name="hwid-api")
    log.info("HWID API слушает http://%s:%s", API_HOST, API_PORT)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        api_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_task
        await bot.session.close()
        log.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Выход")
