# utils/performance.py
"""Модуль для мониторинга производительности."""

import asyncio
import time
import psutil
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from logger import get_logger

logger = get_logger()


@dataclass
class PerformanceMetrics:
    """Метрики производительности."""

    operation_name: str
    execution_time: float
    memory_before: float
    memory_after: float
    cpu_percent: float
    timestamp: float = field(default_factory=time.time)


class PerformanceMonitor:
    """Монитор производительности системы."""

    def __init__(self, max_metrics: int = 1000):
        self.metrics: List[PerformanceMetrics] = []
        self.max_metrics = max_metrics
        self.operation_stats: Dict[str, Dict[str, float]] = {}

    def record_metric(self, metric: PerformanceMetrics):
        """Записывает метрику производительности."""
        self.metrics.append(metric)

        # Ограничиваем количество метрик
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics :]

        # Обновляем статистику по операциям
        op_name = metric.operation_name
        if op_name not in self.operation_stats:
            self.operation_stats[op_name] = {
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
                "total_memory_delta": 0.0,
                "avg_memory_delta": 0.0,
            }

        stats = self.operation_stats[op_name]
        stats["count"] += 1
        stats["total_time"] += metric.execution_time
        stats["avg_time"] = stats["total_time"] / stats["count"]
        stats["min_time"] = min(stats["min_time"], metric.execution_time)
        stats["max_time"] = max(stats["max_time"], metric.execution_time)

        memory_delta = metric.memory_after - metric.memory_before
        stats["total_memory_delta"] += memory_delta
        stats["avg_memory_delta"] = stats["total_memory_delta"] / stats["count"]

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику производительности."""
        return {
            "total_operations": len(self.metrics),
            "operations_by_type": {
                name: stats["count"] for name, stats in self.operation_stats.items()
            },
            "avg_execution_times": {
                name: stats["avg_time"] for name, stats in self.operation_stats.items()
            },
            "memory_usage": {
                name: stats["avg_memory_delta"]
                for name, stats in self.operation_stats.items()
            },
            "system_memory": psutil.virtual_memory()._asdict(),
            "system_cpu": psutil.cpu_percent(interval=0.1),
        }

    def get_slow_operations(self, threshold_seconds: float = 1.0) -> List[str]:
        """Возвращает список медленных операций."""
        return [
            name
            for name, stats in self.operation_stats.items()
            if stats["avg_time"] > threshold_seconds
        ]

    def clear_metrics(self):
        """Очищает все метрики."""
        self.metrics.clear()
        self.operation_stats.clear()
        logger.info("Performance metrics cleared")


@asynccontextmanager
async def performance_timer(
    operation_name: str, monitor: Optional[PerformanceMonitor] = None
):
    """Асинхронный контекстный менеджер для измерения производительности."""
    if monitor is None:
        monitor = global_performance_monitor

    # Получаем начальные метрики
    start_time = time.time()
    memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    cpu_before = psutil.cpu_percent()

    try:
        yield
    finally:
        # Получаем финальные метрики
        end_time = time.time()
        memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        execution_time = end_time - start_time

        # Записываем метрику
        metric = PerformanceMetrics(
            operation_name=operation_name,
            execution_time=execution_time,
            memory_before=memory_before,
            memory_after=memory_after,
            cpu_percent=cpu_before,
        )

        monitor.record_metric(metric)

        # Логируем медленные операции
        if execution_time > 5.0:  # Больше 5 секунд
            logger.warning(
                f"Slow operation detected: {operation_name} took {execution_time:.2f}s"
            )


@contextmanager
def sync_performance_timer(
    operation_name: str, monitor: Optional[PerformanceMonitor] = None
):
    """Синхронный контекстный менеджер для измерения производительности."""
    if monitor is None:
        monitor = global_performance_monitor

    # Получаем начальные метрики
    start_time = time.time()
    memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    cpu_before = psutil.cpu_percent()

    try:
        yield
    finally:
        # Получаем финальные метрики
        end_time = time.time()
        memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        execution_time = end_time - start_time

        # Записываем метрику
        metric = PerformanceMetrics(
            operation_name=operation_name,
            execution_time=execution_time,
            memory_before=memory_before,
            memory_after=memory_after,
            cpu_percent=cpu_before,
        )

        monitor.record_metric(metric)

        # Логируем медленные операции
        if execution_time > 5.0:  # Больше 5 секунд
            logger.warning(
                f"Slow operation detected: {operation_name} took {execution_time:.2f}s"
            )


class SystemHealthChecker:
    """Проверка здоровья системы."""

    def __init__(self):
        self.memory_threshold = 80.0  # %
        self.cpu_threshold = 85.0  # %
        self.disk_threshold = 90.0  # %

    def check_system_health(self) -> Dict[str, Any]:
        """Проверяет здоровье системы."""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage("/")

        health_status = {
            "memory": {
                "usage_percent": memory.percent,
                "available_gb": memory.available / 1024 / 1024 / 1024,
                "status": (
                    "healthy" if memory.percent < self.memory_threshold else "warning"
                ),
            },
            "cpu": {
                "usage_percent": cpu_percent,
                "status": "healthy" if cpu_percent < self.cpu_threshold else "warning",
            },
            "disk": {
                "usage_percent": disk.percent,
                "free_gb": disk.free / 1024 / 1024 / 1024,
                "status": (
                    "healthy" if disk.percent < self.disk_threshold else "warning"
                ),
            },
            "overall_status": "healthy",
        }

        # Определяем общий статус
        if any(
            metric["status"] == "warning"
            for metric in health_status.values()
            if isinstance(metric, dict)
        ):
            health_status["overall_status"] = "warning"

        return health_status


# Глобальные экземпляры
global_performance_monitor = PerformanceMonitor()
global_health_checker = SystemHealthChecker()
