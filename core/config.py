from __future__ import annotations

"""
🔧 Единая конфигурация системы анализа новостей

Этот файл содержит ВСЕ настройки системы:
- Переменные окружения из .env
- Константы и лимиты
- Настройки по умолчанию

Для быстрой настройки измените значения по умолчанию ниже или используйте .env файл.
"""

from functools import lru_cache
from typing import List, Dict

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Единая конфигурация приложения.
    Настройки загружаются из переменных окружения или .env файла.
    """

    # =====================================
    # 📱 TELEGRAM API
    # =====================================

    # Данные для Telegram API (получить на https://my.telegram.org)
    TELEGRAM_API_ID: str | None = Field(
        None, description="ID приложения Telegram (обязательно для мониторинга каналов)"
    )
    TELEGRAM_API_HASH: str | None = Field(
        None,
        description="Hash приложения Telegram (обязательно для мониторинга каналов)",
    )
    TELEGRAM_PHONE: str | None = Field(
        None, description="Номер телефона для авторизации в Telegram (+7XXXXXXXXXX)"
    )

    # Токен бота (получить у @BotFather)
    TELEGRAM_BOT_TOKEN: str = Field(
        ..., description="Токен Telegram бота (получить у @BotFather)"
    )

    # =====================================
    # 📺 МОНИТОРИНГ КАНАЛОВ
    # =====================================

    # Каналы для мониторинга (через запятую)
    TELEGRAM_CHANNEL_IDS: str = Field(
        "meduzalive,lentach,rbc_news",
        description="Список каналов для мониторинга (username или ID через запятую)",
    )

    # Интервал проверки новых сообщений (секунды)
    CHECK_INTERVAL_SECONDS: int = Field(
        30,
        ge=10,
        le=3600,
        description="Интервал проверки новых сообщений в каналах (10-3600 сек, рекомендуется 30-300)",
    )

    # Интервал повтора при ошибках (секунды)
    ERROR_RETRY_SECONDS: int = Field(
        300,
        ge=60,
        le=3600,
        description="Интервал повтора при ошибках подключения (60-3600 сек)",
    )

    # Лимит сообщений за один запрос к Telethon
    TELETHON_MESSAGE_LIMIT: int = Field(
        100,
        ge=1,
        le=500,
        description="Максимальное количество сообщений для получения за один запрос",
    )

    # =====================================
    # 🤖 LLM НАСТРОЙКИ
    # =====================================

    # URL сервера Ollama
    OLLAMA_BASE_URL: str = Field(
        "http://localhost:11434", description="URL сервера Ollama для LLM анализа"
    )

    # Название модели для анализа
    OLLAMA_MODEL: str = Field(
        "ilyagusev/saiga_llama3",
        description="Название LLM модели (например: ilyagusev/saiga_llama3, llama3.2, gemma2)",
    )

    # Максимальная длина текста для анализа (символы)
    MAX_TEXT_LENGTH_FOR_ANALYSIS: int = Field(
        9000,
        ge=500,
        le=10000,
        description="Максимальная длина текста для анализа LLM (символы)",
    )

    # Максимальная длина краткого содержания (символы)
    MAX_SUMMARY_LENGTH: int = Field(
        700,
        ge=100,
        le=2000,
        description="Максимальная длина краткого содержания новости (символы)",
    )

    # Максимальное количество хештегов в анализе
    MAX_HASHTAGS_IN_ANALYSIS: int = Field(
        5, ge=1, le=20, description="Максимальное количество хештегов в анализе новости"
    )

    # =====================================
    # 🗄️ БАЗА ДАННЫХ
    # =====================================

    # Движок БД (только PostgreSQL)
    DB_ENGINE: str = Field(
        "postgres", description="Движок базы данных (только postgres поддерживается)"
    )

    # Строка подключения к PostgreSQL
    POSTGRES_DSN: str = Field(
        "postgresql://postgres:postgres@localhost:5432/news_analyzer",
        description="Строка подключения к PostgreSQL (postgresql://пользователь:пароль@хост:порт/база)",
    )

    # Минимальный размер пула соединений
    POSTGRES_POOL_MIN_SIZE: int = Field(
        2, ge=1, le=50, description="Минимальный размер пула соединений к БД"
    )

    # Максимальный размер пула соединений
    POSTGRES_POOL_MAX_SIZE: int = Field(
        10, ge=1, le=100, description="Максимальный размер пула соединений к БД"
    )

    # =====================================
    # 🔍 ВЕБ-ПОИСК
    # =====================================

    # API ключ для Tavily (поиск в интернете)
    TAVILY_API_KEY: str | None = Field(
        None,
        description="API ключ для Tavily веб-поиска (получить на https://tavily.com/)",
    )

    # =====================================
    # ⚡ ПРОИЗВОДИТЕЛЬНОСТЬ И ЛИМИТЫ
    # =====================================

    # Максимальное количество одновременных запросов к LLM
    MAX_CONCURRENT_REQUESTS: int = Field(
        2,
        ge=1,
        le=20,
        description="Максимальное количество одновременных запросов к LLM",
    )

    # Размер кэша для LLM анализов
    DEFAULT_CACHE_SIZE: int = Field(
        1000,
        ge=100,
        le=10000,
        description="Размер кэша для хранения результатов LLM анализов",
    )

    # Время жизни кэша (секунды)
    DEFAULT_CACHE_TTL_SECONDS: int = Field(
        3600,
        ge=300,
        le=86400,
        description="Время жизни записей в кэше (секунды, 1 час по умолчанию)",
    )

    # Максимальная длина сообщения Telegram
    MAX_MESSAGE_LENGTH: int = Field(
        8192, description="Максимальная длина сообщения в Telegram (лимит API)"
    )

    # =====================================
    # 🔄 RETRY И ТАЙМАУТЫ
    # =====================================

    # Максимальное количество попыток при ошибках
    DEFAULT_MAX_RETRY_ATTEMPTS: int = Field(
        3, ge=1, le=10, description="Максимальное количество попыток при ошибках"
    )

    # Базовая задержка между попытками (секунды)
    DEFAULT_RETRY_BASE_DELAY: float = Field(
        1.0, ge=0.1, le=60.0, description="Базовая задержка между попытками (секунды)"
    )

    # Максимальная задержка между попытками (секунды)
    DEFAULT_RETRY_MAX_DELAY: float = Field(
        60.0,
        ge=1.0,
        le=600.0,
        description="Максимальная задержка между попытками (секунды)",
    )

    # Экспоненциальный множитель для задержки
    DEFAULT_RETRY_EXPONENTIAL_BASE: float = Field(
        2.0,
        ge=1.1,
        le=10.0,
        description="Экспоненциальный множитель для увеличения задержки",
    )

    # Таймаут для пакетных операций (секунды)
    DEFAULT_BATCH_TIMEOUT_SECONDS: int = Field(
        10, ge=1, le=300, description="Таймаут для пакетных операций (секунды)"
    )

    # Таймаут для HTTP запросов (секунды)
    DEFAULT_REQUEST_TIMEOUT_SECONDS: int = Field(
        30, ge=5, le=300, description="Таймаут для HTTP запросов (секунды)"
    )

    # =====================================
    # 📊 МОНИТОРИНГ И СТАТИСТИКА
    # =====================================

    # Интервал проверки здоровья системы (минуты)
    HEALTH_CHECK_INTERVAL_MINUTES: int = Field(
        10, ge=1, le=60, description="Интервал проверки здоровья системы (минуты)"
    )

    # Порог для медленных операций (секунды)
    SLOW_OPERATION_THRESHOLD_SECONDS: float = Field(
        5.0,
        ge=0.1,
        le=60.0,
        description="Порог времени для определения медленных операций (секунды)",
    )

    # Лимит метрик производительности
    PERFORMANCE_METRICS_LIMIT: int = Field(
        1000,
        ge=100,
        le=10000,
        description="Максимальное количество метрик производительности в памяти",
    )

    # Пороги предупреждений для ресурсов (проценты)
    MEMORY_WARNING_THRESHOLD_PERCENT: float = Field(
        80.0,
        ge=50.0,
        le=95.0,
        description="Порог предупреждения об использовании памяти (%)",
    )
    CPU_WARNING_THRESHOLD_PERCENT: float = Field(
        85.0,
        ge=50.0,
        le=95.0,
        description="Порог предупреждения об использовании CPU (%)",
    )
    DISK_WARNING_THRESHOLD_PERCENT: float = Field(
        90.0,
        ge=50.0,
        le=95.0,
        description="Порог предупреждения об использовании диска (%)",
    )

    # =====================================
    # 📢 УВЕДОМЛЕНИЯ
    # =====================================

    # Задержка между отправками уведомлений (секунды)
    NOTIFICATION_RATE_LIMIT_DELAY: float = Field(
        0.05,
        ge=0.01,
        le=1.0,
        description="Задержка между отправками уведомлений для избежания rate limit",
    )

    # Максимальное количество популярных хештегов для отображения
    MAX_POPULAR_HASHTAGS_DISPLAY: int = Field(
        10,
        ge=5,
        le=50,
        description="Максимальное количество популярных хештегов для отображения",
    )

    # Максимальное количество ошибок в истории по категории
    MAX_ERROR_HISTORY_PER_CATEGORY: int = Field(
        10,
        ge=5,
        le=100,
        description="Максимальное количество ошибок в истории по каждой категории",
    )

    # =====================================
    # 📈 СТАТИСТИКА И ОТЧЕТЫ
    # =====================================

    # Лимит хештегов для статистики
    STATISTICS_HASHTAGS_LIMIT: int = Field(
        1000,
        ge=100,
        le=10000,
        description="Максимальное количество хештегов для статистики",
    )

    # Количество топ каналов для отображения
    TOP_CHANNELS_LIMIT: int = Field(
        5,
        ge=3,
        le=20,
        description="Количество топ каналов для отображения в статистике",
    )

    # Количество дней для хранения ежедневной статистики
    DAILY_STATS_HISTORY_DAYS: int = Field(
        7,
        ge=1,
        le=365,
        description="Количество дней для хранения ежедневной статистики",
    )

    # =====================================
    # 🎨 ОТОБРАЖЕНИЕ И ФОРМАТИРОВАНИЕ
    # =====================================

    # Максимальная длина названия канала для отображения
    MAX_CHANNEL_TITLE_DISPLAY: int = Field(
        30,
        ge=10,
        le=100,
        description="Максимальная длина названия канала для отображения",
    )

    # Максимальная длина краткого содержания для отображения
    MAX_SUMMARY_DISPLAY_LENGTH: int = Field(
        1000,
        ge=100,
        le=1000,
        description="Максимальная длина краткого содержания для отображения",
    )

    # Максимальное количество уведомлений в группе
    MAX_GROUP_NOTIFICATIONS: int = Field(
        10,
        ge=1,
        le=10,
        description="Максимальное количество уведомлений в одной группе",
    )

    # =====================================
    # 📝 ЛОГИРОВАНИЕ
    # =====================================

    # Формат логов
    LOG_FORMAT: str = Field(
        "%(asctime)s - %(levelname)s - %(message)s",
        description="Формат записей в логах",
    )

    # Формат даты в логах
    LOG_DATE_FORMAT: str = Field(
        "%Y-%m-%d %H:%M:%S", description="Формат даты и времени в логах"
    )

    # Максимальный размер файла лога (МБ)
    MAX_LOG_FILE_SIZE_MB: int = Field(
        10, ge=1, le=100, description="Максимальный размер файла лога в мегабайтах"
    )

    # Максимальное количество файлов логов
    MAX_LOG_FILES_COUNT: int = Field(
        3, ge=1, le=20, description="Максимальное количество файлов логов для ротации"
    )

    # =====================================
    # 🎭 ЭМОДЗИ И ВИЗУАЛИЗАЦИЯ
    # =====================================

    EMOJI_POSITIVE: str = Field("😊", description="Эмодзи для позитивных новостей")
    EMOJI_NEGATIVE: str = Field("😔", description="Эмодзи для негативных новостей")
    EMOJI_NEUTRAL: str = Field("😐", description="Эмодзи для нейтральных новостей")
    EMOJI_UNKNOWN: str = Field("🤔", description="Эмодзи для неопределенных новостей")
    EMOJI_HIGH_PRIORITY: str = Field("🔥", description="Эмодзи для важных новостей")
    EMOJI_NORMAL_PRIORITY: str = Field("📰", description="Эмодзи для обычных новостей")

    # =====================================
    # 🏷️ КАТЕГОРИИ И ХЕШТЕГИ
    # =====================================

    # Приоритетные хештеги (список строк)
    HIGH_PRIORITY_HASHTAGS: List[str] = Field(
        default_factory=lambda: [
            "происшествия",
            "политика",
            "экономика",
            "чрезвычайная_ситуация",
            "военные_действия",
        ],
        description="Список приоритетных хештегов для важных новостей",
    )

    # Категории хештегов (список строк)
    HASHTAG_CATEGORIES: List[str] = Field(
        default_factory=lambda: [
            "политика",
            "экономика",
            "происшествия",
            "спорт",
            "наука_и_технологии",
            "культура",
            "общество",
            "другие_страны",
            "медицина",
            "образование",
            "экология",
            "транспорт",
        ],
        description="Список доступных категорий хештегов",
    )

    # =====================================
    # ⚙️ НАСТРОЙКИ PYDANTIC
    # =====================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # =====================================
    # 🔍 ВАЛИДАТОРЫ
    # =====================================

    @field_validator("DB_ENGINE")
    @classmethod
    def _lower_db_engine(cls, v):
        return v.lower() if isinstance(v, str) else v

    @field_validator("TELEGRAM_PHONE")
    @classmethod
    def _validate_phone(cls, v):
        if v and not v.startswith("+"):
            return f"+{v}"
        return v

    # =====================================
    # 🎯 ВСПОМОГАТЕЛЬНЫЕ СВОЙСТВА
    # =====================================

    @property
    def channel_ids(self) -> List[str]:
        """Возвращает список ID каналов для мониторинга."""
        return [c.strip() for c in self.TELEGRAM_CHANNEL_IDS.split(",") if c.strip()]

    @property
    def sentiment_emoji_map(self) -> Dict[str, str]:
        """Маппинг тональности на эмодзи."""
        return {
            "Позитивная": self.EMOJI_POSITIVE,
            "Негативная": self.EMOJI_NEGATIVE,
            "Нейтральная": self.EMOJI_NEUTRAL,
        }

    @property
    def sentiment_filter_map(self) -> Dict[str, str]:
        """Маппинг фильтров тональности."""
        return {
            "positive": "Позитивная",
            "negative": "Негативная",
            "neutral": "Нейтральная",
        }


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек (кэшированный)."""
    return Settings()


# Единственный экземпляр настроек
settings = get_settings()


# =====================================
# 📋 СПРАВКА ПО НАСТРОЙКАМ
# =====================================


def print_settings_help():
    """Выводит справку по всем настройкам."""
    print("🔧 Справка по настройкам системы анализа новостей")
    print("=" * 60)
    print()

    categories = [
        (
            "📱 TELEGRAM API",
            [
                "TELEGRAM_API_ID",
                "TELEGRAM_API_HASH",
                "TELEGRAM_PHONE",
                "TELEGRAM_BOT_TOKEN",
            ],
        ),
        (
            "📺 МОНИТОРИНГ",
            ["TELEGRAM_CHANNEL_IDS", "CHECK_INTERVAL_SECONDS", "ERROR_RETRY_SECONDS"],
        ),
        ("🤖 LLM", ["OLLAMA_BASE_URL", "OLLAMA_MODEL", "MAX_TEXT_LENGTH_FOR_ANALYSIS"]),
        (
            "🗄️ БАЗА ДАННЫХ",
            ["POSTGRES_DSN", "POSTGRES_POOL_MIN_SIZE", "POSTGRES_POOL_MAX_SIZE"],
        ),
        (
            "⚡ ПРОИЗВОДИТЕЛЬНОСТЬ",
            [
                "MAX_CONCURRENT_REQUESTS",
                "DEFAULT_CACHE_SIZE",
                "DEFAULT_CACHE_TTL_SECONDS",
            ],
        ),
    ]

    for category_name, fields in categories:
        print(f"{category_name}:")
        for field_name in fields:
            field = Settings.model_fields.get(field_name)
            if field and field.description:
                print(f"  {field_name}: {field.description}")
        print()


if __name__ == "__main__":
    print_settings_help()
