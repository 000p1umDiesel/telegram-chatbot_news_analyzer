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
    """Упрощенный менеджер уведомлений с улучшенной производительностью."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.stats = {
            "total_sent": 0,
            "total_failed": 0,
            "blocked_users": set(),
        }

    async def send_notification(self, analysis_data: Dict[str, Any]):
        """Отправляет уведомление всем подписчикам."""
        logger.info(f"📤 Отправка уведомления: {analysis_data.get('channel_title')}")

        subscribers = data_manager.get_all_subscribers()
        if not subscribers:
            logger.warning("⚠️ Подписчики для уведомлений не найдены.")
            return

        message_text = NotificationTemplate.format_analysis_message(analysis_data)
        keyboard = NotificationTemplate.get_notification_keyboard(
            analysis_data["message_link"]
        )

        successful_sends = 0
        failed_sends = 0
        filtered_sends = 0

        for user_id in subscribers:
            # Пропускаем заблокированных пользователей
            if user_id in self.stats["blocked_users"]:
                continue

            try:
                # Проверяем настройки пользователя
                sentiment = analysis_data.get("sentiment")
                hashtags = analysis_data.get("hashtags", [])

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

                # Небольшая задержка между отправками для избежания rate limits
                await asyncio.sleep(0.05)

            except TelegramAPIError as e:
                failed_sends += 1
                error_msg = str(e).lower()

                if "bot was blocked" in error_msg or "user is deactivated" in error_msg:
                    logger.info(
                        f"Пользователь {user_id} заблокировал бота или деактивирован"
                    )
                    self.stats["blocked_users"].add(user_id)
                    # Можно удалить из подписчиков
                    data_manager.remove_subscriber(user_id)
                else:
                    logger.warning(
                        f"Не удалось отправить уведомление пользователю {user_id}: {e}"
                    )

            except Exception as e:
                failed_sends += 1
                logger.error(
                    f"Неожиданная ошибка при отправке пользователю {user_id}: {e}"
                )

        # Обновляем статистику
        self.stats["total_sent"] += successful_sends
        self.stats["total_failed"] += failed_sends

        logger.info(
            f"📊 Уведомление отправлено: ✅ {successful_sends}, "
            f"❌ {failed_sends}, 🔇 {filtered_sends} (отфильтровано)"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику отправки уведомлений."""
        return {
            "total_sent": self.stats["total_sent"],
            "total_failed": self.stats["total_failed"],
            "blocked_users_count": len(self.stats["blocked_users"]),
            "success_rate": (
                self.stats["total_sent"]
                / (self.stats["total_sent"] + self.stats["total_failed"])
                if (self.stats["total_sent"] + self.stats["total_failed"]) > 0
                else 0
            ),
        }


# Глобальный экземпляр менеджера уведомлений
_notification_manager = None


def get_notification_manager(bot: Bot) -> NotificationManager:
    """Возвращает синглтон менеджера уведомлений."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(bot)
    return _notification_manager


async def send_analysis_result(bot: Bot, analysis_data: Dict[str, Any]):
    """Основная функция для отправки результата анализа."""
    manager = get_notification_manager(bot)
    await manager.send_notification(analysis_data)


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
