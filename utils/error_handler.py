"""Централизованная обработка ошибок и retry механизмы."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from logger import get_logger

logger = get_logger()


class ErrorCategory(Enum):
    """Категории ошибок для классификации."""

    NETWORK = "network"
    DATABASE = "database"
    LLM = "llm"
    TELEGRAM_API = "telegram_api"
    VALIDATION = "validation"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class RetryConfig:
    """Конфигурация для retry механизма."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ErrorHandler:
    """Централизованный обработчик ошибок."""

    def __init__(self):
        self.error_counts: Dict[ErrorCategory, int] = {}
        self.last_errors: Dict[ErrorCategory, List[str]] = {}

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Определяет категорию ошибки."""
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Сетевые ошибки
        if any(
            keyword in error_msg
            for keyword in ["connection", "timeout", "network", "unreachable", "dns"]
        ):
            return ErrorCategory.NETWORK

        # Ошибки базы данных
        if any(
            keyword in error_msg
            for keyword in ["database", "sqlite", "sql", "table", "column"]
        ):
            return ErrorCategory.DATABASE

        # Ошибки LLM
        if any(
            keyword in error_msg
            for keyword in ["ollama", "llm", "model", "inference", "prompt"]
        ):
            return ErrorCategory.LLM

        # Ошибки Telegram API
        if any(
            keyword in error_msg
            for keyword in [
                "telegram",
                "bot was blocked",
                "chat not found",
                "message not modified",
            ]
        ):
            return ErrorCategory.TELEGRAM_API

        # Ошибки валидации
        if any(
            keyword in error_msg
            for keyword in ["validation", "invalid", "required", "missing"]
        ):
            return ErrorCategory.VALIDATION

        # Системные ошибки
        if any(
            keyword in error_msg
            for keyword in ["memory", "disk", "permission", "file not found"]
        ):
            return ErrorCategory.SYSTEM

        return ErrorCategory.UNKNOWN

    def handle_error(
        self,
        error: Exception,
        context: str = "",
        category: Optional[ErrorCategory] = None,
    ) -> None:
        """Обрабатывает ошибку с категоризацией и логированием."""
        if category is None:
            category = self.categorize_error(error)

        # Увеличиваем счетчик
        self.error_counts[category] = self.error_counts.get(category, 0) + 1

        # Сохраняем последние ошибки
        if category not in self.last_errors:
            self.last_errors[category] = []
        self.last_errors[category].append(f"{context}: {str(error)}")

        # Оставляем только последние 10 ошибок
        if len(self.last_errors[category]) > 10:
            self.last_errors[category] = self.last_errors[category][-10:]

        # Логируем с соответствующим уровнем
        log_level = self._get_log_level(category)
        logger.log(
            log_level,
            f"[{category.value.upper()}] {context}: {error}",
            exc_info=True if log_level >= logging.ERROR else False,
        )

    def _get_log_level(self, category: ErrorCategory) -> int:
        """Определяет уровень логирования для категории."""
        critical_categories = {ErrorCategory.DATABASE, ErrorCategory.SYSTEM}
        warning_categories = {ErrorCategory.TELEGRAM_API, ErrorCategory.NETWORK}

        if category in critical_categories:
            return logging.ERROR
        elif category in warning_categories:
            return logging.WARNING
        else:
            return logging.INFO

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику ошибок."""
        return {
            "error_counts": {
                cat.value: count for cat, count in self.error_counts.items()
            },
            "total_errors": sum(self.error_counts.values()),
            "categories_with_errors": len(self.error_counts),
        }


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    exceptions: Union[Type[Exception], tuple] = Exception,
    category: Optional[ErrorCategory] = None,
):
    """Декоратор для retry с exponential backoff."""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    error_handler.handle_error(
                        e,
                        f"Attempt {attempt + 1}/{config.max_attempts} for {func.__name__}",
                        category,
                    )

                    if attempt < config.max_attempts - 1:
                        delay = min(
                            config.base_delay * (config.exponential_base**attempt),
                            config.max_delay,
                        )

                        if config.jitter:
                            import random

                            delay *= 0.5 + random.random() * 0.5

                        logger.info(f"Retrying {func.__name__} in {delay:.2f}s...")
                        await asyncio.sleep(delay)

            # Если все попытки неудачны
            logger.error(
                f"All {config.max_attempts} attempts failed for {func.__name__}"
            )
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    error_handler.handle_error(
                        e,
                        f"Attempt {attempt + 1}/{config.max_attempts} for {func.__name__}",
                        category,
                    )

                    if attempt < config.max_attempts - 1:
                        delay = min(
                            config.base_delay * (config.exponential_base**attempt),
                            config.max_delay,
                        )

                        if config.jitter:
                            import random

                            delay *= 0.5 + random.random() * 0.5

                        logger.info(f"Retrying {func.__name__} in {delay:.2f}s...")
                        time.sleep(delay)

            logger.error(
                f"All {config.max_attempts} attempts failed for {func.__name__}"
            )
            raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# Глобальный экземпляр error handler
global_error_handler = ErrorHandler()
