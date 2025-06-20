# telegram_monitor.py
from telethon import TelegramClient
from telethon.tl.types import Message, User
from logger import get_logger
import config
from typing import List, Dict, Any, Optional
import os

logger = get_logger()


class TelegramMonitor:
    """
    Класс для мониторинга Telegram канала с использованием Telethon.
    """

    def __init__(self, session_name: str = "telegram_session"):
        if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
            raise ValueError(
                "TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть установлены в .env"
            )

        self.api_id = int(config.TELEGRAM_API_ID)
        self.api_hash = config.TELEGRAM_API_HASH

        # Создаем директорию для сессий, если её нет
        session_path = os.path.join(".sessions", session_name)
        os.makedirs(os.path.dirname(session_path), exist_ok=True)

        self.client = TelegramClient(session_path, self.api_id, self.api_hash)
        logger.info("Клиент Telethon инициализирован.")

    async def connect(self) -> bool:
        """
        Подключается к Telegram.
        Для первого запуска может потребоваться интерактивная авторизация.
        Запустите `python init_session.py` для создания файла сессии.
        """
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.warning("Клиент не авторизован.")
                logger.warning(
                    "Пожалуйста, запустите `python init_session.py` для создания файла сессии "
                    "и прохождения интерактивной авторизации."
                )
                return False
            me = await self.client.get_me()
            if isinstance(me, User):
                logger.info(f"Клиент Telethon успешно авторизован как: {me.first_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при подключении клиента Telethon: {e}")
            return False

    async def disconnect(self):
        """Отключает клиент от Telegram."""
        if self.client.is_connected():
            await self.client.disconnect()
            logger.info("Клиент Telethon отключен.")

    async def get_new_messages(
        self, channel_id: str, last_message_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получает новые сообщения из канала, начиная с определенного ID.
        """
        if not self.client.is_connected():
            logger.error("Клиент Telethon не подключен.")
            return []

        try:
            channel_entity = await self.client.get_entity(channel_id)

            # Безопасно получаем имя пользователя и заголовок
            channel_username = getattr(channel_entity, "username", None)
            channel_title = getattr(channel_entity, "title", "Неизвестный канал")

            messages = await self.client.get_messages(
                channel_entity,
                min_id=last_message_id,
                limit=100,  # Ограничение на количество сообщений за один раз
            )

            result = []
            if messages and isinstance(messages, list):
                # Telethon возвращает сообщения в обратном хронологическом порядке
                for msg in reversed(messages):
                    if isinstance(msg, Message) and msg.text:
                        result.append(
                            {
                                "id": msg.id,
                                "text": msg.text,
                                "date": msg.date.isoformat(),
                                "channel_id": channel_id,
                                "channel_title": channel_title,
                                "channel_username": channel_username,
                            }
                        )
            return result
        except Exception as e:
            logger.error(
                f"Ошибка при получении новых сообщений из канала {channel_id}: {e}"
            )
            return []

    async def get_initial_last_message_id(self, channel_id: str) -> int:
        """Получает ID последнего сообщения в канале для инициализации."""
        if not self.client.is_connected():
            logger.error("Клиент Telethon не подключен.")
            return 0
        try:
            channel_entity = await self.client.get_entity(channel_id)
            # Берем одно самое последнее сообщение
            async for message in self.client.iter_messages(channel_entity, limit=1):
                if isinstance(message, Message):
                    return message.id
            return 0
        except Exception as e:
            logger.error(f"Ошибка при получении начального ID сообщения: {e}")
            return 0
