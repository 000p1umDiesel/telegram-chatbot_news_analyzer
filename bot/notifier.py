# notifier.py
from typing import Dict, Any
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from logger import get_logger
from services import data_manager

logger = get_logger()


async def send_analysis_result(bot: Bot, analysis_data: Dict[str, Any]):
    """
    Отправляет отформатированный результат анализа всем подписчикам.
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
