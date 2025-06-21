# main.py
import asyncio
from logger import get_logger
import config

# Импортируем единый экземпляр бота и диспетчер
from bot import dp, bot
from services import telegram_monitor, data_manager
from monitoring_service import MonitoringService
from services.simple_health_check import simple_health_check

logger = get_logger()

# (экземпляр bot импортирован выше из пакета bot)

# dp импортирован из пакета bot


async def main():
    """
    Основная функция для инициализации и запуска всех сервисов.
    """
    logger.info("🚀 Запуск системы анализа новостей...")

    # Инициализация сервиса мониторинга
    # Бот передается для отправки уведомлений
    monitoring_service = MonitoringService(bot=bot)

    # Задачи для одновременного выполнения
    tasks = []

    # Основные сервисы
    monitor_task = asyncio.create_task(monitoring_service.run(), name="news_monitor")
    bot_task = asyncio.create_task(dp.start_polling(bot), name="telegram_bot")

    # Упрощенный мониторинг здоровья системы
    health_task = asyncio.create_task(
        simple_health_check.run_periodic_check(interval_minutes=10),
        name="simple_health_monitor",
    )

    tasks.extend([monitor_task, bot_task, health_task])

    logger.info("✅ Все сервисы запущены:")
    logger.info("  📰 Мониторинг новостей")
    logger.info("  🤖 Telegram бот")
    logger.info("  🏥 Упрощенный мониторинг здоровья")
    logger.info(f"  📺 Отслеживаемые каналы: {len(config.TELEGRAM_CHANNEL_IDS)}")

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

        # Корректно отключаем клиент Telethon
        if telegram_monitor:
            try:
                await telegram_monitor.disconnect()
            except Exception as e:
                logger.warning(f"Ошибка при отключении Telegram-клиента: {e}")

        # Закрываем соединение с БД
        if data_manager:
            try:
                data_manager.close()
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
