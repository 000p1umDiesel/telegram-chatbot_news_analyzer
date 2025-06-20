# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# --- Telegram API ---
# Для работы с Telethon (мониторинг канала)
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

# --- Telegram Bot ---
# Токен для вашего бота (получается у @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Проверка наличия обязательных переменных
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN должен быть установлен в .env файле")

# --- Monitoring ---
# ID или юзернеймы каналов для мониторинга (через запятую)
# Пример: "channel1,channel2,-100123456789"
raw_channels = os.getenv("TELEGRAM_CHANNEL_IDS")
if not raw_channels:
    raise ValueError("TELEGRAM_CHANNEL_IDS должен быть установлен в .env файле")
TELEGRAM_CHANNEL_IDS = [channel.strip() for channel in raw_channels.split(",")]

# Интервал проверки новых сообщений в секундах
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL", "60"))
# Интервал для повторной попытки в случае ошибки
ERROR_RETRY_SECONDS = int(os.getenv("ERROR_RETRY_INTERVAL", "300"))

# --- LLM ---
# URL для Ollama API
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Название модели Ollama для использования
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ilyagusev/saiga_llama3")

# --- Web Search ---
# API ключ для Tavily Search
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# --- Database ---
# Путь к файлу базы данных SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "data/storage.db")
