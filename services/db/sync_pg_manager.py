"""
Простой синхронный PostgreSQL менеджер для бота.
Использует psycopg2 для синхронных операций.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from core.config import settings as config
from logger import get_logger

logger = get_logger()


class SyncPostgresManager:
    """Простой синхронный PostgreSQL менеджер для бота."""

    def __init__(self):
        self.connection = None
        self._connect()

    def _connect(self):
        """Подключается к PostgreSQL."""
        try:
            # Парсим DSN
            dsn_parts = config.POSTGRES_DSN.replace("postgresql://", "").split("@")
            user_pass = dsn_parts[0]
            host_db = dsn_parts[1]

            if ":" in user_pass:
                user, password = user_pass.split(":", 1)
            else:
                user = user_pass
                password = None

            host_port, database = host_db.split("/", 1)
            if ":" in host_port:
                host, port = host_port.split(":", 1)
                port = int(port)
            else:
                host = host_port
                port = 5432

            self.connection = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                cursor_factory=RealDictCursor,
            )
            self.connection.autocommit = True
            logger.info(
                f"Синхронное подключение к PostgreSQL: {host}:{port}/{database}"
            )

        except Exception as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise

    def _execute(self, query: str, params: tuple = None):
        """Выполняет SQL запрос."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            # Переподключаемся при ошибке
            try:
                self._connect()
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
            except Exception as e2:
                logger.error(f"Ошибка повторного выполнения запроса: {e2}")
                raise

    def _execute_one(self, query: str, params: tuple = None):
        """Выполняет SQL запрос и возвращает одну строку."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            # Переподключаемся при ошибке
            try:
                self._connect()
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchone()
            except Exception as e2:
                logger.error(f"Ошибка повторного выполнения запроса: {e2}")
                raise

    # Методы для работы с подписчиками
    def is_subscriber(self, chat_id: int) -> bool:
        """Проверяет, подписан ли пользователь."""
        try:
            row = self._execute_one(
                "SELECT 1 FROM subscribers WHERE chat_id=%s AND is_active=TRUE LIMIT 1",
                (chat_id,),
            )
            return row is not None
        except Exception as e:
            logger.error(f"Ошибка проверки подписки для {chat_id}: {e}")
            return False

    def add_subscriber(self, chat_id: int) -> None:
        """Добавляет подписчика."""
        try:
            # Добавляем подписчика
            self._execute(
                """
                INSERT INTO subscribers(chat_id, is_active)
                VALUES (%s, TRUE)
                ON CONFLICT(chat_id) DO UPDATE SET is_active = TRUE
                """,
                (chat_id,),
            )

            # Добавляем настройки пользователя
            self._execute(
                """
                INSERT INTO user_settings(chat_id) VALUES (%s)
                ON CONFLICT DO NOTHING
                """,
                (chat_id,),
            )

            logger.info(f"✅ Добавлен подписчик: {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка добавления подписчика {chat_id}: {e}")

    def remove_subscriber(self, chat_id: int) -> None:
        """Удаляет подписчика."""
        try:
            self._execute(
                "UPDATE subscribers SET is_active = FALSE WHERE chat_id=%s", (chat_id,)
            )
            logger.info(f"❌ Удален подписчик: {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления подписчика {chat_id}: {e}")

    def get_all_subscribers(self) -> List[int]:
        """Возвращает список всех активных подписчиков."""
        try:
            rows = self._execute(
                "SELECT chat_id FROM subscribers WHERE is_active = TRUE"
            )
            return [row["chat_id"] for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения подписчиков: {e}")
            return []

    def get_user_settings(self, chat_id: int) -> Dict[str, Any]:
        """Возвращает настройки пользователя."""
        try:
            row = self._execute_one(
                """
                SELECT notification_enabled, sentiment_filter, hashtag_filters, 
                       quiet_hours_start, quiet_hours_end, language
                FROM user_settings WHERE chat_id=%s
                """,
                (chat_id,),
            )
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"Ошибка получения настроек для {chat_id}: {e}")
            return {"notification_enabled": True, "sentiment_filter": "all"}

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику."""
        try:
            subscribers = self.get_all_subscribers()
            return {
                "subscribers": len(subscribers),
                "total_messages": 0,  # Можно добавить подсчет сообщений
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"subscribers": 0, "total_messages": 0}

    def close(self):
        """Закрывает соединение."""
        if self.connection:
            self.connection.close()


# Глобальный экземпляр
_sync_manager = None


def get_sync_postgres_manager() -> SyncPostgresManager:
    """Возвращает синглтон синхронного менеджера."""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncPostgresManager()
    return _sync_manager
