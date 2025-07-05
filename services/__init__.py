"""Service package exports.

Упрощено: выбор и инициализация `data_manager` происходит в `main.py`.
Этот модуль предоставляет:
    • llm_analyzer  – экземпляр LLM-анализа
    • tavily_search – клиент веб-поиска
    • telegram_monitor – мониторинг Telegram каналов
    • data_manager  – заполняется во время запуска приложения
"""

from logger import get_logger

from .llm.analyzer import OllamaAnalyzer
from .tavily_search import TavilySearch
from .telegram_monitor import telegram_monitor

# Global singletons (data_manager будет инициализирован позднее)
logger = get_logger()

llm_analyzer = OllamaAnalyzer()
tavily_search = TavilySearch()

# Заполняется в точке входа после выбора реализации
data_manager = None  # type: ignore

__all__ = [
    "llm_analyzer",
    "tavily_search",
    "telegram_monitor",
    "data_manager",
]
