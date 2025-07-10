"""Telegram channels monitoring service using Telethon with PostgreSQL sessions."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel, Chat
from telethon.sessions import StringSession

from logger import get_logger
from core.config import settings as config
from utils.error_handler import retry_with_backoff, RetryConfig, ErrorCategory

logger = get_logger()


class PostgreSQLSession:
    """Кастомная сессия для Telethon, которая хранит данные в PostgreSQL."""

    def __init__(self, data_manager, session_name: str = "monitor_session"):
        self.data_manager = data_manager
        self.session_name = session_name
        self._session_data = None

    async def load_session(self) -> Optional[str]:
        """Загружает сессию из PostgreSQL."""
        try:
            if not self.data_manager:
                return None

            async with self.data_manager.pool.acquire() as conn:
                # Создаем таблицу для сессий если не существует
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_sessions (
                        session_name TEXT PRIMARY KEY,
                        session_data TEXT,
                        created_at TIMESTAMPTZ DEFAULT now(),
                        updated_at TIMESTAMPTZ DEFAULT now()
                    )
                """
                )

                # Загружаем сессию
                row = await conn.fetchrow(
                    "SELECT session_data FROM telegram_sessions WHERE session_name = $1",
                    self.session_name,
                )

                if row:
                    logger.info(f"Загружена сессия {self.session_name} из PostgreSQL")
                    return row["session_data"]

                logger.info(f"Сессия {self.session_name} не найдена в PostgreSQL")
                return None

        except Exception as e:
            logger.error(f"Ошибка загрузки сессии: {e}")
            return None

    async def save_session(self, session_data: str):
        """Сохраняет сессию в PostgreSQL."""
        try:
            if not self.data_manager:
                return

            async with self.data_manager.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO telegram_sessions (session_name, session_data, updated_at)
                    VALUES ($1, $2, now())
                    ON CONFLICT (session_name) 
                    DO UPDATE SET session_data = EXCLUDED.session_data, updated_at = now()
                """,
                    self.session_name,
                    session_data,
                )

                logger.info(f"Сессия {self.session_name} сохранена в PostgreSQL")

        except Exception as e:
            logger.error(f"Ошибка сохранения сессии: {e}")


class TelegramMonitor:
    """Мониторинг Telegram каналов через Telethon с PostgreSQL сессиями."""

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
        self.data_manager = None
        self.pg_session = None

    def set_data_manager(self, data_manager):
        """Устанавливает data_manager для работы с PostgreSQL."""
        self.data_manager = data_manager
        self.pg_session = PostgreSQLSession(data_manager)

    async def connect(self) -> bool:
        """Подключение к Telegram API с PostgreSQL сессией."""
        try:
            # Проверяем наличие необходимых данных
            if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
                logger.error(
                    "TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть установлены"
                )
                return False

            if not self.data_manager:
                logger.error("Data manager не установлен")
                return False

                # Загружаем сессию из PostgreSQL
            session_string = await self.pg_session.load_session()  # type: ignore

            if session_string:
                # Используем существующую сессию
                session = StringSession(session_string)
                logger.info("Используется существующая сессия из PostgreSQL")
            else:
                # Создаем новую сессию
                session = StringSession()
                logger.info("Создается новая сессия")

            self.client = TelegramClient(
                session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH
            )

            await self.client.start()  # type: ignore

            # Проверяем авторизацию
            if not await self.client.is_user_authorized():  # type: ignore
                logger.error(
                    "Пользователь не авторизован. Запустите скрипт авторизации."
                )
                return False

            # Сохраняем сессию в PostgreSQL
            session_string = session.save()
            await self.pg_session.save_session(session_string)  # type: ignore

            self.is_connected = True
            logger.info("✅ Подключение к Telegram API успешно")
            return True

        except Exception as e:
            logger.error(f"Ошибка подключения к Telegram: {e}")
            return False

    async def disconnect(self):
        """Отключение от Telegram API."""
        if self.client:
            await self.client.disconnect()  # type: ignore
            self.is_connected = False
            logger.info("Отключение от Telegram API")

    @retry_with_backoff(
        config=RetryConfig(max_attempts=3, base_delay=2.0),
        exceptions=(FloodWaitError, ConnectionError),
        category=ErrorCategory.TELEGRAM_API,
    )
    async def get_channel_entity(self, channel_id: str):
        """Получение сущности канала."""
        if not self.client:
            raise ConnectionError("Telegram client не подключен")

        try:
            # Пробуем получить канал по username или ID
            if channel_id.startswith("@"):
                entity = await self.client.get_entity(channel_id)
            elif channel_id.startswith("-"):
                entity = await self.client.get_entity(int(channel_id))
            else:
                entity = await self.client.get_entity(channel_id)

            return entity
        except Exception as e:
            logger.error(f"Не удалось получить канал {channel_id}: {e}")
            raise

    async def get_initial_last_message_id(self, channel_id: str) -> int:
        """Получение ID последнего сообщения в канале."""
        try:
            if not self.client:
                return 0

            entity = await self.get_channel_entity(channel_id)

            # Получаем последнее сообщение
            messages = await self.client.get_messages(entity, limit=1)
            if messages and hasattr(messages, "__len__") and len(messages) > 0:  # type: ignore
                logger.info(f"Последнее сообщение в {channel_id}: {messages[0].id}")  # type: ignore
                return messages[0].id  # type: ignore

            return 0
        except Exception as e:
            logger.error(f"Ошибка получения последнего сообщения для {channel_id}: {e}")
            return 0

    async def get_new_messages(
        self, channel_id: str, last_message_id: int
    ) -> List[Dict[str, Any]]:
        """Получение новых сообщений из канала."""
        try:
            if not self.client:
                return []

            entity = await self.get_channel_entity(channel_id)

            # Получаем сообщения после last_message_id
            messages = await self.client.get_messages(
                entity, limit=config.TELETHON_MESSAGE_LIMIT, min_id=last_message_id
            )

            if not messages:
                return []

            # Конвертируем сообщения в нужный формат
            converted_messages = []
            # Обрабатываем в хронологическом порядке (от старых к новым)
            for msg in reversed(list(messages)):  # type: ignore
                if msg.text and msg.id > last_message_id:
                    message_data = {
                        "id": msg.id,
                        "text": msg.text,
                        "date": msg.date.replace(tzinfo=timezone.utc),
                        "channel_id": (
                            str(entity.id) if hasattr(entity, "id") else channel_id
                        ),
                        "channel_title": getattr(entity, "title", "Unknown Channel"),
                        "channel_username": getattr(entity, "username", None),
                    }
                    converted_messages.append(message_data)

            # КРИТИЧНО: Сортируем по ID для обеспечения правильного порядка обработки
            converted_messages.sort(key=lambda x: x["id"])

            logger.info(
                f"Найдено {len(converted_messages)} новых сообщений в {channel_id}"
            )
            if converted_messages:
                logger.debug(
                    f"Диапазон ID: {converted_messages[0]['id']} - {converted_messages[-1]['id']}"
                )
            return converted_messages

        except Exception as e:
            logger.error(f"Ошибка получения сообщений из {channel_id}: {e}")
            return []

    async def test_channel_access(self, channel_id: str) -> bool:
        """Тестирование доступа к каналу."""
        try:
            if not self.client:
                return False

            entity = await self.get_channel_entity(channel_id)

            # Пробуем получить одно сообщение
            messages = await self.client.get_messages(entity, limit=1)

            logger.info(
                f"✅ Доступ к каналу {channel_id} ({getattr(entity, 'title', 'Unknown')}) подтвержден"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Нет доступа к каналу {channel_id}: {e}")
            return False

    async def validate_all_channels(self, channel_ids: List[str]) -> List[str]:
        """Проверка доступа ко всем каналам."""
        valid_channels = []

        for channel_id in channel_ids:
            if await self.test_channel_access(channel_id):
                valid_channels.append(channel_id)

        logger.info(f"Доступно каналов: {len(valid_channels)}/{len(channel_ids)}")
        return valid_channels


# Глобальный экземпляр
telegram_monitor = TelegramMonitor()
