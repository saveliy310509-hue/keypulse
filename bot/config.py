import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

# Платформы (Railway/Render/Fly/Heroku) сами задают порт через $PORT — он приоритетнее
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("PORT") or os.getenv("API_PORT") or "8080")

API_SECRET: str = os.getenv("API_SECRET", "secret")

YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")

# Локальная SQLite (VPS, свой ПК, Docker с volume)
# На платформах с volume путь обычно абсолютный: /app/data/keypulse.db
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/keypulse.db")

# Turso / libSQL — внешняя база для Render/Fly free, где диск стирается.
# Если задан LIBSQL_URL, SQLite-файл не используется.
LIBSQL_URL: str = os.getenv("LIBSQL_URL", "")
LIBSQL_AUTH_TOKEN: str = os.getenv("LIBSQL_AUTH_TOKEN", "")

# Keep-alive: бот сам пингует свой публичный URL, чтобы Render не усыпил сервис
KEEPALIVE_URL: str = os.getenv("KEEPALIVE_URL", "")
KEEPALIVE_INTERVAL: int = int(os.getenv("KEEPALIVE_INTERVAL") or "600")
