# main.py
import asyncio
from logger import get_logger
import config

# Импортируем единый экземпляр бота и диспетчер
from bot import dp, bot
from services import telegram_monitor, data_manager
from monitoring_service import MonitoringService

logger = get_logger()

# (экземпляр bot импортирован выше из пакета bot)

# dp импортирован из пакета bot


async def main():
    """
    Основная функция для инициализации и запуска всех сервисов.
    """
    # Инициализация сервиса мониторинга
    # Бот передается для отправки уведомлений
    monitoring_service = MonitoringService(bot=bot)

    # Задачи для одновременного выполнения
    monitor_task = asyncio.create_task(monitoring_service.run())
    bot_task = asyncio.create_task(dp.start_polling(bot))

    logger.info("Все сервисы запущены.")

    try:
        # Ожидаем завершения обеих задач
        await asyncio.gather(monitor_task, bot_task)
    except Exception as e:
        logger.error(f"Произошла критическая ошибка в main: {e}", exc_info=True)
    finally:
        logger.info("Завершение работы сервисов...")
        # Корректно отключаем клиент Telethon
        if telegram_monitor:
            await telegram_monitor.disconnect()
        # Закрываем соединение с БД
        if data_manager:
            data_manager.close()
        logger.info("Все сервисы остановлены.")


if __name__ == "__main__":
    try:
        logger.info("Запуск системы...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Система остановлена пользователем.")
    except Exception as e:
        logger.critical(f"Непредвиденная ошибка на верхнем уровне: {e}", exc_info=True)
