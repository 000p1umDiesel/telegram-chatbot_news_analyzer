"""Константы проекта для устранения magic numbers."""

# === ТАЙМАУТЫ И ИНТЕРВАЛЫ ===
DEFAULT_CHECK_INTERVAL_SECONDS = 60
DEFAULT_ERROR_RETRY_SECONDS = 300
DEFAULT_BATCH_TIMEOUT_SECONDS = 10
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
HEALTH_CHECK_INTERVAL_MINUTES = 10

# === ЛИМИТЫ И РАЗМЕРЫ ===
DEFAULT_CACHE_SIZE = 1000
DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 час
MAX_CONCURRENT_REQUESTS = 2
MAX_MESSAGE_LENGTH = 4096  # Telegram limit
MAX_SUMMARY_LENGTH = 700
MAX_TEXT_LENGTH_FOR_ANALYSIS = 2000
TELETHON_MESSAGE_LIMIT = 100

# === ПРОИЗВОДИТЕЛЬНОСТЬ ===
SLOW_OPERATION_THRESHOLD_SECONDS = 5.0
PERFORMANCE_METRICS_LIMIT = 1000
MEMORY_WARNING_THRESHOLD_PERCENT = 80.0
CPU_WARNING_THRESHOLD_PERCENT = 85.0
DISK_WARNING_THRESHOLD_PERCENT = 90.0

# === RETRY КОНФИГУРАЦИЯ ===
DEFAULT_MAX_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_RETRY_MAX_DELAY = 60.0
DEFAULT_RETRY_EXPONENTIAL_BASE = 2.0

# === УВЕДОМЛЕНИЯ ===
NOTIFICATION_RATE_LIMIT_DELAY = 0.05  # секунд между отправками
MAX_HASHTAGS_IN_ANALYSIS = 5
MAX_POPULAR_HASHTAGS_DISPLAY = 10
MAX_ERROR_HISTORY_PER_CATEGORY = 10

# === СТАТИСТИКА ===
STATISTICS_HASHTAGS_LIMIT = 1000
TOP_CHANNELS_LIMIT = 5
DAILY_STATS_HISTORY_DAYS = 7

# === ЭМОДЗИ ===
EMOJI_POSITIVE = "😊"
EMOJI_NEGATIVE = "😔"
EMOJI_NEUTRAL = "😐"
EMOJI_UNKNOWN = "🤔"
EMOJI_HIGH_PRIORITY = "🔥"
EMOJI_NORMAL_PRIORITY = "📰"

# === SENTIMENT MAPPING ===
SENTIMENT_EMOJI_MAP = {
    "Позитивная": EMOJI_POSITIVE,
    "Негативная": EMOJI_NEGATIVE,
    "Нейтральная": EMOJI_NEUTRAL,
}

SENTIMENT_FILTER_MAP = {
    "positive": "Позитивная",
    "negative": "Негативная",
    "neutral": "Нейтральная",
}

# === ПРИОРИТЕТНЫЕ ХЕШТЕГИ ===
HIGH_PRIORITY_HASHTAGS = [
    "происшествия",
    "политика",
    "экономика",
    "чрезвычайная_ситуация",
    "военные_действия",
]

# === КАТЕГОРИИ ХЕШТЕГОВ ===
HASHTAG_CATEGORIES = [
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
]

# === ФОРМАТИРОВАНИЕ ===
MAX_CHANNEL_TITLE_DISPLAY = 30
MAX_SUMMARY_DISPLAY_LENGTH = 400
MAX_GROUP_NOTIFICATIONS = 1

# === ЛОГИРОВАНИЕ ===
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_FILE_SIZE_MB = 10
MAX_LOG_FILES_COUNT = 3
