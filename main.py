# main.py
import asyncio

# Импортируем быструю конфигурацию ПЕРЕД основной
# Единая конфигурация теперь в core/config.py

from logger import get_logger
from core.config import settings as config
from services.db.pg_manager import AsyncPostgresManager
from services import telegram_monitor
from bot import dp, bot
from services.simple_health_check import simple_health_check
from monitoring_service import MonitoringService

logger = get_logger()

# Глобальный менеджер данных
data_manager = None


async def main():
    """
    Основная функция для инициализации и запуска всех сервисов.
    """
    global data_manager

    logger.info("🚀 Запуск системы анализа новостей...")

    # Инициализируем менеджер БД (Postgres) - асинхронно
    data_manager = await AsyncPostgresManager.create()

    # Устанавливаем глобальный data_manager для других модулей
    import services

    services.data_manager = data_manager

    # Устанавливаем data_manager для telegram_monitor
    telegram_monitor.set_data_manager(data_manager)

    # Подключаемся к Telegram для мониторинга
    if not await telegram_monitor.connect():
        logger.error(
            "❌ Не удалось подключиться к Telegram. Мониторинг каналов недоступен."
        )
        return

    # Проверяем доступ к каналам
    valid_channels = await telegram_monitor.validate_all_channels(config.channel_ids)
    if not valid_channels:
        logger.error("❌ Нет доступа ни к одному каналу. Проверьте настройки.")
        return

    # Задачи для одновременного выполнения
    tasks = []

    # Telegram бот
    bot_task = asyncio.create_task(dp.start_polling(bot), name="telegram_bot")
    tasks.append(bot_task)

    # Мониторинг каналов
    monitoring_service = MonitoringService(bot, data_manager)
    monitoring_task = asyncio.create_task(
        monitoring_service.run(), name="channel_monitoring"
    )
    tasks.append(monitoring_task)

    # Упрощенный мониторинг здоровья системы
    health_task = asyncio.create_task(
        simple_health_check.run_periodic_check(interval_minutes=10),
        name="simple_health_monitor",
    )
    tasks.append(health_task)

    logger.info("✅ Все сервисы запущены:")
    logger.info("  🤖 Telegram бот")
    logger.info("  📺 Мониторинг каналов")
    logger.info("  🏥 Упрощенный мониторинг здоровья")
    logger.info(f"  📺 Отслеживаемые каналы: {len(valid_channels)}")

    try:
        # Ожидаем завершения всех задач
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка в main: {e}", exc_info=True)
    finally:
        logger.info("🔄 Завершение работы сервисов...")

        # Отменяем все задачи
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Отключаемся от Telegram
        if telegram_monitor:
            await telegram_monitor.disconnect()  # type: ignore

        # Закрываем соединение с БД
        if data_manager:
            try:
                await data_manager.close()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии БД: {e}")

        logger.info("✅ Все сервисы остановлены.")


if __name__ == "__main__":
    try:
        logger.info("🎯 Инициализация системы анализа новостей...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Система остановлена пользователем.")
    except Exception as e:
        logger.critical(
            f"💀 Непредвиденная ошибка на верхнем уровне: {e}", exc_info=True
        )
