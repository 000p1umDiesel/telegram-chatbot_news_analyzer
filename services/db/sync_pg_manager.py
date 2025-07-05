"""
Простой синхронный PostgreSQL менеджер для бота.
Использует psycopg2 для синхронных операций.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
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

    def _execute(self, query: str, params: Optional[tuple] = None):
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

    def _execute_one(self, query: str, params: Optional[tuple] = None):
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
            return [int(row["chat_id"]) for row in rows]
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

    def update_user_settings(self, chat_id: int, settings: Dict[str, Any]) -> bool:
        """Обновляет настройки пользователя."""
        try:
            # Формируем SET клаузулу динамически
            set_clauses = []
            params = []

            for key, value in settings.items():
                if key in [
                    "notification_enabled",
                    "sentiment_filter",
                    "hashtag_filters",
                    "quiet_hours_start",
                    "quiet_hours_end",
                    "language",
                ]:
                    set_clauses.append(f"{key} = %s")
                    params.append(value)

            if not set_clauses:
                return False

            # Добавляем updated_at
            set_clauses.append("updated_at = NOW()")
            params.append(chat_id)

            query = f"""
                UPDATE user_settings 
                SET {', '.join(set_clauses)}
                WHERE chat_id = %s
            """

            self._execute(query, tuple(params))
            logger.info(f"✅ Обновлены настройки для пользователя {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления настроек для {chat_id}: {e}")
            return False

    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Возвращает детальную статистику новостей."""
        try:
            # Общая статистика
            stats_query = """
                SELECT 
                    COUNT(DISTINCT m.message_id) as total_messages,
                    COUNT(DISTINCT a.message_id) as total_analyses
                FROM messages m
                LEFT JOIN analyses a ON m.message_id = a.message_id
            """
            stats_row = self._execute_one(stats_query)

            # Статистика по тональности
            sentiment_query = """
                SELECT sentiment, COUNT(*) as count
                FROM analyses
                WHERE sentiment IS NOT NULL
                GROUP BY sentiment
            """
            sentiment_rows = self._execute(sentiment_query)
            sentiment_distribution = {
                row["sentiment"]: row["count"] for row in sentiment_rows
            }

            # Популярные хештеги
            hashtags_query = """
                SELECT jsonb_array_elements_text(hashtags) as hashtag, COUNT(*) as count
                FROM analyses
                WHERE hashtags IS NOT NULL
                GROUP BY hashtag
                ORDER BY count DESC
                LIMIT 10
            """
            hashtag_rows = self._execute(hashtags_query)
            popular_hashtags = [row["hashtag"] for row in hashtag_rows]

            # Топ каналы
            channels_query = """
                SELECT 
                    m.channel_title as title,
                    COUNT(*) as count
                FROM messages m
                JOIN analyses a ON m.message_id = a.message_id
                WHERE m.channel_title IS NOT NULL
                GROUP BY m.channel_title
                ORDER BY count DESC
                LIMIT 5
            """
            channel_rows = self._execute(channels_query)
            top_channels = [
                {"title": row["title"], "count": row["count"]} for row in channel_rows
            ]

            return {
                "total_messages": stats_row["total_messages"] if stats_row else 0,
                "total_analyses": stats_row["total_analyses"] if stats_row else 0,
                "sentiment_distribution": sentiment_distribution,
                "popular_hashtags": popular_hashtags,
                "top_channels": top_channels,
            }

        except Exception as e:
            logger.error(f"Ошибка получения детальной статистики: {e}")
            return {
                "total_messages": 0,
                "total_analyses": 0,
                "sentiment_distribution": {},
                "popular_hashtags": [],
                "top_channels": [],
            }

    def get_trends_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику трендов за последние дни."""
        try:
            # Популярные хештеги за последние 7 дней
            hashtags_query = """
                SELECT jsonb_array_elements_text(a.hashtags) as hashtag, COUNT(*) as count
                FROM analyses a
                JOIN messages m ON a.message_id = m.message_id
                WHERE m.date >= NOW() - INTERVAL '7 days'
                AND a.hashtags IS NOT NULL
                GROUP BY hashtag
                ORDER BY count DESC
                LIMIT 10
            """
            hashtag_rows = self._execute(hashtags_query)
            popular_hashtags = [row["hashtag"] for row in hashtag_rows]

            # Самые активные каналы за последние 7 дней
            channels_query = """
                SELECT 
                    m.channel_title as title,
                    COUNT(*) as count
                FROM messages m
                JOIN analyses a ON m.message_id = a.message_id
                WHERE m.date >= NOW() - INTERVAL '7 days'
                AND m.channel_title IS NOT NULL
                GROUP BY m.channel_title
                ORDER BY count DESC
                LIMIT 5
            """
            channel_rows = self._execute(channels_query)
            top_channels = [
                {"title": row["title"], "count": row["count"]} for row in channel_rows
            ]

            return {"popular_hashtags": popular_hashtags, "top_channels": top_channels}

        except Exception as e:
            logger.error(f"Ошибка получения статистики трендов: {e}")
            return {"popular_hashtags": [], "top_channels": []}

    def get_daily_digest(self) -> Dict[str, Any]:
        """Возвращает дайджест новостей за сегодня."""
        try:
            # Получаем новости за сегодня
            digest_query = """
                SELECT 
                    a.summary,
                    a.sentiment,
                    a.hashtags,
                    m.channel_title as channel,
                    m.channel_id,
                    m.channel_username,
                    m.message_id,
                    m.date
                FROM analyses a
                JOIN messages m ON a.message_id = m.message_id
                WHERE DATE(m.date) = CURRENT_DATE
                AND a.summary IS NOT NULL
                ORDER BY m.date DESC
                LIMIT 10
            """
            news_rows = self._execute(digest_query)

            if not news_rows:
                return {"date": datetime.now().strftime("%Y-%m-%d"), "news": []}

            # Формируем список новостей
            news_list = []
            for row in news_rows:
                hashtags = []
                if row["hashtags"]:
                    try:
                        hashtags = (
                            json.loads(row["hashtags"])
                            if isinstance(row["hashtags"], str)
                            else row["hashtags"]
                        )
                    except (json.JSONDecodeError, TypeError):
                        hashtags = []

                # Формируем ссылку на оригинальное сообщение
                message_link = None
                if row["channel_username"] and row["message_id"]:
                    # Убираем @ если есть
                    username = row["channel_username"].lstrip("@")
                    message_link = f"https://t.me/{username}/{row['message_id']}"
                elif row["channel_id"] and row["message_id"]:
                    # Для приватных каналов используем ID
                    channel_id_str = str(row["channel_id"]).lstrip("-100")
                    message_link = (
                        f"https://t.me/c/{channel_id_str}/{row['message_id']}"
                    )

                news_list.append(
                    {
                        "summary": row["summary"],
                        "sentiment": row["sentiment"],
                        "hashtags": hashtags,
                        "channel": row["channel"],
                        "channel_username": row["channel_username"],
                        "message_link": message_link,
                        "date": row["date"].isoformat() if row["date"] else None,
                    }
                )

            return {"date": datetime.now().strftime("%Y-%m-%d"), "news": news_list}

        except Exception as e:
            logger.error(f"Ошибка получения дайджеста: {e}")
            return {"date": datetime.now().strftime("%Y-%m-%d"), "news": []}

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
