from logger import get_logger
from .llm_analyzer import OllamaAnalyzer
from .data_manager import DataManager
from .tavily_search import TavilySearch
from .telegram_monitor import TelegramMonitor

logger = get_logger()

try:
    llm_analyzer = OllamaAnalyzer()
    data_manager = DataManager()
    tavily_search = TavilySearch()
    telegram_monitor = TelegramMonitor()
    logger.info("Все сервисы успешно инициализированы.")
except Exception as e:
    logger.error(f"Критическая ошибка при инициализации сервисов: {e}", exc_info=True)
    raise

__all__ = [
    "llm_analyzer",
    "data_manager",
    "tavily_search",
    "telegram_monitor",
]
