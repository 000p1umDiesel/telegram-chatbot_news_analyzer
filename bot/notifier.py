# notifier.py
from typing import Dict, Any, List
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from logger import get_logger
from services import data_manager
import asyncio
from datetime import datetime

logger = get_logger()


class NotificationTemplate:
    """Шаблоны для уведомлений."""

    @staticmethod
    def get_sentiment_emoji(sentiment: str) -> str:
        """Возвращает эмодзи для тональности."""
        return {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
            sentiment, "🤔"
        )

    @staticmethod
    def get_priority_emoji(hashtags: List[str]) -> str:
        """Определяет приоритет новости по хештегам."""
        high_priority = ["происшествия", "политика", "экономика"]
        if any(tag in high_priority for tag in hashtags):
            return "🔥"
        return "📰"

    @staticmethod
    def format_analysis_message(analysis_data: Dict[str, Any]) -> str:
        """Форматирует сообщение с анализом новости."""
        sentiment_emoji = NotificationTemplate.get_sentiment_emoji(
            analysis_data["sentiment"]
        )
        hashtags_list = (
            analysis_data.get("hashtags_formatted", "").replace("#", "").split()
        )
        priority_emoji = NotificationTemplate.get_priority_emoji(hashtags_list)

        # Обрезаем длинные заголовки каналов
        channel_title = analysis_data["channel_title"]
        if len(channel_title) > 30:
            channel_title = channel_title[:27] + "..."

        message_text = (
            f"{priority_emoji} Новость из «{channel_title}»\n\n"
            f"📝 Краткое содержание:\n{analysis_data['summary']}\n\n"
            f"🎭 Тональность: {sentiment_emoji} {analysis_data['sentiment']}\n\n"
            f"🏷️ Теги: {analysis_data['hashtags_formatted']}\n\n"
            f"🔗 Читать полностью: {analysis_data['message_link']}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M')}"
        )

        return message_text

    @staticmethod
    def get_notification_keyboard(message_link: str) -> InlineKeyboardBuilder:
        """Создает клавиатуру для уведомления."""
        builder = InlineKeyboardBuilder()
        builder.button(text="📖 Читать полностью", url=message_link)
        builder.adjust(1)
        return builder


class NotificationManager:
    """Менеджер уведомлений с улучшенной логикой."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.notification_queue: List[Dict[str, Any]] = []
        self.batch_size = 1  # Отправляем сразу (было 5)
        self.batch_timeout = 10  # Секунд ожидания для группировки
        self._timeout_task = None  # Задача для таймаута

    async def add_notification(self, analysis_data: Dict[str, Any]):
        """Добавляет уведомление в очередь."""
        logger.info(
            f"📥 Добавляю уведомление в очередь: {analysis_data.get('channel_title')}"
        )
        self.notification_queue.append({**analysis_data, "timestamp": datetime.now()})
        logger.info(
            f"📋 Размер очереди: {len(self.notification_queue)}/{self.batch_size}"
        )

        # Если достигли лимита батча, отправляем немедленно
        if len(self.notification_queue) >= self.batch_size:
            logger.info(f"🚀 Достигнут лимит батча, отправляю немедленно")
            if self._timeout_task:
                self._timeout_task.cancel()
                self._timeout_task = None
            await self._send_batch()
        else:
            # Если это первое уведомление в очереди, запускаем таймер
            if len(self.notification_queue) == 1:
                logger.info(f"⏰ Запускаю таймер на {self.batch_timeout}с")
                self._timeout_task = asyncio.create_task(self._timeout_handler())
            logger.info(
                f"⏳ Ждем больше уведомлений или таймаута ({self.batch_timeout}с)"
            )

    async def _timeout_handler(self):
        """Обработчик таймаута для отправки накопленных уведомлений."""
        try:
            await asyncio.sleep(self.batch_timeout)
            if self.notification_queue:
                logger.info(
                    f"⏰ Таймаут истек, отправляю {len(self.notification_queue)} уведомлений"
                )
                await self._send_batch()
        except asyncio.CancelledError:
            logger.info("⏰ Таймер отменен")
        finally:
            self._timeout_task = None

    async def _send_batch(self):
        """Отправляет батч уведомлений."""
        if not self.notification_queue:
            logger.info("📭 Очередь уведомлений пуста")
            return

        logger.info(
            f"📬 Начинаю отправку батча из {len(self.notification_queue)} уведомлений"
        )
        subscribers = data_manager.get_all_subscribers()
        logger.info(f"👥 Найдено подписчиков: {len(subscribers)} - {subscribers}")

        if not subscribers:
            logger.warning("⚠️ Подписчики для уведомлений не найдены. Очищаю очередь.")
            self.notification_queue.clear()
            return

        # Группируем по каналам
        channel_groups = {}
        for notification in self.notification_queue:
            channel = notification["channel_title"]
            if channel not in channel_groups:
                channel_groups[channel] = []
            channel_groups[channel].append(notification)

        # Отправляем уведомления
        for channel, notifications in channel_groups.items():
            if len(notifications) == 1:
                # Одиночное уведомление
                await self._send_single_notification(notifications[0], subscribers)
            else:
                # Групповое уведомление
                await self._send_group_notification(channel, notifications, subscribers)

        # Очищаем очередь
        self.notification_queue.clear()

    async def _send_single_notification(
        self, notification_data: Dict[str, Any], subscribers: List[int]
    ):
        """Отправляет одиночное уведомление."""
        message_text = NotificationTemplate.format_analysis_message(notification_data)
        keyboard = NotificationTemplate.get_notification_keyboard(
            notification_data["message_link"]
        )

        successful_sends = 0
        failed_sends = 0
        filtered_sends = 0

        for user_id in subscribers:
            try:
                # Проверяем настройки пользователя
                sentiment = notification_data.get("sentiment")
                hashtags = notification_data.get("hashtags", [])

                if not data_manager.should_send_notification(
                    user_id, sentiment, hashtags
                ):
                    filtered_sends += 1
                    continue

                await self.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode=None,  # Отключаем markdown для избежания ошибок
                    reply_markup=keyboard.as_markup(),
                    disable_web_page_preview=True,
                )
                successful_sends += 1

                # Небольшая задержка между отправками
                await asyncio.sleep(0.1)

            except TelegramAPIError as e:
                failed_sends += 1
                logger.warning(
                    f"Не удалось отправить уведомление пользователю {user_id}: {e}"
                )

                if "bot was blocked" in str(e).lower():
                    logger.info(
                        f"Пользователь {user_id} заблокировал бота. Удаляю из подписчиков."
                    )
                    data_manager.remove_subscriber(user_id)

            except Exception as e:
                failed_sends += 1
                logger.error(
                    f"Ошибка при отправке уведомления пользователю {user_id}: {e}"
                )

        logger.info(
            f"Уведомление отправлено: {successful_sends} успешно, {failed_sends} ошибок, {filtered_sends} отфильтровано"
        )

    async def _send_group_notification(
        self, channel: str, notifications: List[Dict[str, Any]], subscribers: List[int]
    ):
        """Отправляет групповое уведомление."""
        # Сокращаем название канала
        channel_short = channel[:25] + "..." if len(channel) > 25 else channel

        header = f"📰 **{len(notifications)} новостей из «{channel_short}»**\n\n"

        messages = []
        for i, notification in enumerate(
            notifications[:3], 1
        ):  # Показываем только первые 3
            sentiment_emoji = NotificationTemplate.get_sentiment_emoji(
                notification["sentiment"]
            )
            summary = notification["summary"]
            if len(summary) > 100:
                summary = summary[:97] + "..."

            messages.append(
                f"**{i}.** {sentiment_emoji} {summary}\n"
                f"🔗 [Читать]({notification['message_link']})"
            )

        if len(notifications) > 3:
            messages.append(f"\n... и еще {len(notifications) - 3} новостей")

        group_message = header + "\n\n".join(messages)
        group_message += f"\n\n⏰ {datetime.now().strftime('%H:%M')}"

        successful_sends = 0
        failed_sends = 0

        for user_id in subscribers:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=group_message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                successful_sends += 1
                await asyncio.sleep(0.1)

            except TelegramAPIError as e:
                failed_sends += 1
                logger.warning(
                    f"Не удалось отправить групповое уведомление пользователю {user_id}: {e}"
                )

                if "bot was blocked" in str(e).lower():
                    logger.info(
                        f"Пользователь {user_id} заблокировал бота. Удаляю из подписчиков."
                    )
                    data_manager.remove_subscriber(user_id)

            except Exception as e:
                failed_sends += 1
                logger.error(
                    f"Ошибка при отправке группового уведомления пользователю {user_id}: {e}"
                )

        logger.info(
            f"Групповое уведомление отправлено: {successful_sends} успешно, {failed_sends} ошибок"
        )


# Глобальный экземпляр менеджера уведомлений
_notification_manager = None


def get_notification_manager(bot: Bot) -> NotificationManager:
    """Возвращает глобальный экземпляр менеджера уведомлений."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(bot)
    return _notification_manager


async def send_analysis_result(bot: Bot, analysis_data: Dict[str, Any]):
    """
    Отправляет отформатированный результат анализа всем подписчикам.
    Использует улучшенную систему уведомлений.
    """
    logger.info(
        f"🔔 Получен запрос на отправку уведомления: канал={analysis_data.get('channel_title')}, тональность={analysis_data.get('sentiment')}"
    )
    manager = get_notification_manager(bot)
    await manager.add_notification(analysis_data)
    logger.info(f"📤 Уведомление добавлено в очередь менеджера")


# Обратная совместимость - оставляем старую функцию
async def send_analysis_result_legacy(bot: Bot, analysis_data: Dict[str, Any]):
    """
    Старая версия отправки уведомлений (для обратной совместимости).
    """
    subscribers = data_manager.get_all_subscribers()
    if not subscribers:
        logger.info("Подписчики для уведомлений не найдены. Пропускаю отправку.")
        return

    sentiment_to_hashtag = {
        "Позитивная": "#позитивная_новость",
        "Негативная": "#негативная_новость",
        "Нейтральная": "#нейтральная_новость",
    }
    sentiment_hashtag = sentiment_to_hashtag.get(analysis_data["sentiment"], "#новость")

    message_text = (
        f"Анализ из «{analysis_data['channel_title']}»\n\n"
        f"Краткое содержание:\n{analysis_data['summary']}\n\n"
        f"Оригинал: {analysis_data['message_link']}\n\n"
        f"{analysis_data['hashtags_formatted']}\n"
        f"{sentiment_hashtag}"
    )

    successful_sends = 0
    for user_id in subscribers:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode=None,
                disable_web_page_preview=True,
            )
            successful_sends += 1
        except TelegramAPIError as e:
            logger.warning(
                f"Не удалось отправить уведомление пользователю {user_id}: {e}"
            )
            if "bot was blocked" in str(e):
                logger.info(
                    f"Пользователь {user_id} заблокировал бота. Удаляю из подписчиков."
                )
                data_manager.remove_subscriber(user_id)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

    logger.info(
        f"Результат анализа отправлен {successful_sends}/{len(subscribers)} подписчикам."
    )
