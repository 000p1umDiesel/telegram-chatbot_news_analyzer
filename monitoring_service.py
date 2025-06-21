# monitoring_service.py
import asyncio
from logger import get_logger
import config
from services import data_manager, llm_analyzer, telegram_monitor
from bot import send_analysis_result
from aiogram import Bot
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import time

logger = get_logger()


class MonitoringService:
    def __init__(self, bot: Bot, max_concurrent_tasks: int = 3):
        self.bot = bot
        self.monitor = telegram_monitor
        self.analyzer = llm_analyzer
        self.data_manager = data_manager
        self.channel_ids = config.TELEGRAM_CHANNEL_IDS
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.stats = {
            "processed_messages": 0,
            "failed_messages": 0,
            "start_time": time.time(),
        }

    async def _process_single_message(
        self, message: Dict[str, Any], channel_id: str
    ) -> bool:
        """Обрабатывает одно сообщение с семафором для ограничения параллелизма."""
        async with self.semaphore:
            try:
                analysis = await self.analyzer.analyze_message(message["text"])
                if not analysis:
                    logger.warning(
                        f"Не удалось проанализировать сообщение ID: {message['id']} из канала {channel_id}"
                    )
                    self.stats["failed_messages"] += 1
                    return False

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
                self.stats["processed_messages"] += 1
                return True

            except Exception as e:
                logger.error(
                    f"Ошибка при обработке сообщения ID {message.get('id')} из канала {channel_id}: {e}",
                    exc_info=True,
                )
                self.stats["failed_messages"] += 1
                return False

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

            # Обрабатываем сообщения параллельно
            tasks = [
                self._process_single_message(message, channel_id)
                for message in messages
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Подсчитываем результаты
            successful = sum(1 for result in results if result is True)
            failed = len(results) - successful

            logger.info(
                f"Канал '{channel_id}': обработано {successful}/{len(messages)} сообщений, "
                f"ошибок: {failed}"
            )

        except Exception as e:
            logger.error(
                f"Критическая ошибка при обработке канала {channel_id}: {e}",
                exc_info=True,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику работы сервиса."""
        uptime = time.time() - self.stats["start_time"]
        return {
            "processed_messages": self.stats["processed_messages"],
            "failed_messages": self.stats["failed_messages"],
            "uptime_seconds": uptime,
            "messages_per_hour": (
                (self.stats["processed_messages"] / (uptime / 3600))
                if uptime > 0
                else 0
            ),
        }

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

        cycle_count = 0
        while True:
            cycle_count += 1
            start_time = time.time()
            logger.info(f"Начало цикла #{cycle_count} проверки всех каналов.")

            # Обрабатываем каналы параллельно
            channel_tasks = [
                self._process_channel(channel_id) for channel_id in self.channel_ids
            ]
            await asyncio.gather(*channel_tasks, return_exceptions=True)

            cycle_time = time.time() - start_time
            stats = self.get_stats()

            logger.info(
                f"Цикл #{cycle_count} завершен за {cycle_time:.2f}с. "
                f"Всего обработано: {stats['processed_messages']}, "
                f"ошибок: {stats['failed_messages']}, "
                f"скорость: {stats['messages_per_hour']:.1f} сообщений/час"
            )
            logger.info(
                f"Следующая проверка через {config.CHECK_INTERVAL_SECONDS} секунд."
            )
            await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)
