"""
Упрощенная система мониторинга здоровья без критических ошибок.
"""

import asyncio
import time
from datetime import datetime
from logger import get_logger
from services import data_manager

logger = get_logger()


class SimpleHealthCheck:
    """Упрощенная проверка здоровья системы."""

    def __init__(self):
        self.start_time = time.time()
        self.last_check = None

    def check_database(self) -> bool:
        """Проверяет базу данных."""
        try:
            with data_manager._lock, data_manager.conn:
                cursor = data_manager.conn.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception:
            return False

    def get_uptime_hours(self) -> float:
        """Возвращает время работы в часах."""
        return (time.time() - self.start_time) / 3600

    def get_basic_stats(self) -> dict:
        """Возвращает базовую статистику."""
        try:
            subscribers = len(data_manager.get_all_subscribers())
        except Exception:
            subscribers = 0

        return {
            "uptime_hours": self.get_uptime_hours(),
            "database_ok": self.check_database(),
            "subscribers_count": subscribers,
            "last_check": datetime.now().isoformat(),
        }

    async def run_periodic_check(self, interval_minutes: int = 10):
        """Запускает периодическую проверку."""
        logger.info(
            f"🏥 Запуск упрощенного мониторинга (каждые {interval_minutes} мин)"
        )

        while True:
            try:
                stats = self.get_basic_stats()
                self.last_check = datetime.now()

                # Логируем только важные события
                if not stats["database_ok"]:
                    logger.warning("База данных недоступна")
                else:
                    # Логируем статистику раз в час
                    if int(stats["uptime_hours"]) % 1 == 0:
                        logger.info(
                            f"✅ Система работает {stats['uptime_hours']:.1f}ч, подписчиков: {stats['subscribers_count']}"
                        )

                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error(f"Ошибка в мониторинге: {e}")
                await asyncio.sleep(300)  # 5 минут при ошибке


# Глобальный экземпляр
simple_health_check = SimpleHealthCheck()
