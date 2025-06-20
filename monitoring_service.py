# monitoring_service.py
import asyncio
from logger import get_logger
import config
from services import data_manager, llm_analyzer, telegram_monitor
from bot import send_analysis_result
from aiogram import Bot

logger = get_logger()


class MonitoringService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.monitor = telegram_monitor
        self.analyzer = llm_analyzer
        self.data_manager = data_manager
        self.channel_ids = config.TELEGRAM_CHANNEL_IDS

    async def _process_channel(self, channel_id: str):
        """Обрабатывает один канал: получает и анализирует новые сообщения."""
        logger.info(f"Проверка канала: {channel_id}")
        try:
            # Получаем ID последнего обработанного сообщения для этого канала
            last_message_id = self.data_manager.get_last_message_id(channel_id)
            if last_message_id == 0:
                logger.info(
                    f"Последний ID для '{channel_id}' не найден, получаем с канала..."
                )
                last_message_id = await self.monitor.get_initial_last_message_id(
                    channel_id
                )
                if last_message_id > 0:
                    logger.info(
                        f"Канал '{channel_id}' инициализирован с ID: {last_message_id}. Сохраняем в базу."
                    )
                    self.data_manager.set_last_message_id(channel_id, last_message_id)
                    # Пропускаем первую итерацию, чтобы не дублировать последнее сообщение
                    return

            messages = await self.monitor.get_new_messages(channel_id, last_message_id)

            if not messages:
                logger.info(f"В канале '{channel_id}' новых сообщений нет.")
                return

            logger.info(
                f"В канале '{channel_id}' найдено {len(messages)} новых сообщений."
            )

            for message in messages:
                try:
                    analysis = await self.analyzer.analyze_message(message["text"])
                    if not analysis:
                        logger.warning(
                            f"Не удалось проанализировать сообщение ID: {message['id']} из канала {channel_id}"
                        )
                        continue

                    self.data_manager.save_message(message)
                    self.data_manager.save_analysis(message["id"], analysis.dict())

                    # Формируем и отправляем уведомление
                    message_link = (
                        f"https://t.me/{message['channel_username']}/{message['id']}"
                        if message.get("channel_username")
                        else "N/A"
                    )
                    notification_data = {
                        "channel_title": message.get(
                            "channel_title", "Неизвестный источник"
                        ),
                        "message_link": message_link,
                        "summary": analysis.summary,
                        "sentiment": analysis.sentiment,
                        "hashtags_formatted": analysis.format_hashtags(),
                    }
                    await send_analysis_result(self.bot, notification_data)

                    # Обновляем ID последнего сообщения для этого канала
                    self.data_manager.set_last_message_id(channel_id, message["id"])

                except Exception as e:
                    logger.error(
                        f"Ошибка при обработке сообщения ID {message.get('id')} из канала {channel_id}: {e}",
                        exc_info=True,
                    )
                    continue
        except Exception as e:
            logger.error(
                f"Критическая ошибка при обработке канала {channel_id}: {e}",
                exc_info=True,
            )

    async def run(self):
        """Основной цикл мониторинга по всем каналам."""
        logger.info(
            "Запуск сервиса мониторинга для каналов: " + ", ".join(self.channel_ids)
        )

        is_connected = await self.monitor.connect()
        if not is_connected:
            logger.error(
                "Не удалось подключиться к Telegram. Сервис мониторинга остановлен."
            )
            return

        while True:
            logger.info("Начало нового цикла проверки всех каналов.")
            for channel_id in self.channel_ids:
                await self._process_channel(channel_id)

            logger.info(
                f"Все каналы проверены. Следующая проверка через {config.CHECK_INTERVAL_SECONDS} секунд."
            )
            await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)
