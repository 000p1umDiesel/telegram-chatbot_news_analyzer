from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import config

# Единственный экземпляр бота
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# Импорт хендлеров после создания bot, чтобы они могли использовать Dispatcher
from .handlers import dp  # noqa: E402
from .notifier import send_analysis_result  # noqa: E402

__all__ = [
    "dp",
    "send_analysis_result",
]
