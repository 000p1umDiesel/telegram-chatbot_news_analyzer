"""Утилита для работы с локальной SQLite-базой.

Хранит:
1. Последний обработанный ID сообщения для каждого канала
2. Сырые сообщения
3. Результаты LLM-анализа
4. Подписчиков бота
5. Пользовательские настройки и фильтры

Используется синхронный `sqlite3`, так как все вызовы происходят внутри
асинхронных обработчиков Aiogram / Telethon, но сами операции очень быстрые
(<1 мс). Для потокобезопасности применяется глобальный `threading.Lock`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import get_logger
import config

logger = get_logger()


class DataManager:  # pylint: disable=too-few-public-methods
    _lock = threading.Lock()

    def __init__(self, db_url: str | Path = config.DATABASE_URL):
        self.db_path = Path(db_url)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # connect with write-ahead-logging for concurrency, disable same thread check
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("SQLite подключена: %s", self.db_path)

    # ---------------------------------------------------------------------
    # DB schema
    # ---------------------------------------------------------------------
    def _create_tables(self):
        with self._lock, self.conn:  # autocommit context
            # Сначала создаем базовые таблицы
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS channels (
                    channel_id     TEXT PRIMARY KEY,
                    last_message_id INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id     INTEGER,
                    channel_id     TEXT,
                    text           TEXT,
                    channel_title  TEXT,
                    channel_username TEXT,
                    date           TEXT,
                    PRIMARY KEY (channel_id, message_id)
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    message_id  INTEGER PRIMARY KEY,
                    summary     TEXT,
                    sentiment   TEXT,
                    hashtags    TEXT    -- JSON-encoded array
                );

                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id INTEGER PRIMARY KEY
                );
                """
            )

            # Теперь выполняем миграции для новых колонок и таблиц
            self._run_migrations()

    def _run_migrations(self):
        """Выполняет миграции базы данных."""
        try:
            # Миграция 1: Добавляем новые колонки в таблицу subscribers
            self._add_column_if_not_exists(
                "subscribers", "subscribed_at", "TEXT DEFAULT CURRENT_TIMESTAMP"
            )
            self._add_column_if_not_exists(
                "subscribers", "is_active", "INTEGER DEFAULT 1"
            )

            # Миграция 2: Создаем новые таблицы
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    chat_id INTEGER PRIMARY KEY,
                    notification_enabled INTEGER DEFAULT 1,
                    sentiment_filter TEXT DEFAULT 'all',  -- 'all', 'positive', 'negative', 'neutral'
                    hashtag_filters TEXT,  -- JSON array of enabled hashtags
                    quiet_hours_start TEXT,  -- HH:MM format
                    quiet_hours_end TEXT,    -- HH:MM format
                    language TEXT DEFAULT 'ru',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES subscribers (chat_id)
                );

                CREATE TABLE IF NOT EXISTS user_stats (
                    chat_id INTEGER,
                    date TEXT,  -- YYYY-MM-DD
                    messages_received INTEGER DEFAULT 0,
                    messages_clicked INTEGER DEFAULT 0,
                    PRIMARY KEY (chat_id, date),
                    FOREIGN KEY (chat_id) REFERENCES subscribers (chat_id)
                );

                CREATE TABLE IF NOT EXISTS system_stats (
                    date TEXT PRIMARY KEY,  -- YYYY-MM-DD
                    messages_processed INTEGER DEFAULT 0,
                    messages_failed INTEGER DEFAULT 0,
                    notifications_sent INTEGER DEFAULT 0,
                    new_subscribers INTEGER DEFAULT 0,
                    unsubscribes INTEGER DEFAULT 0
                );
            """
            )

            # Миграция 3: Создаем индексы
            self._create_indexes()

            # Миграция 4: Обновляем существующих подписчиков
            self._migrate_existing_subscribers()

            logger.info("Миграции базы данных выполнены успешно")

        except Exception as e:
            logger.error(f"Ошибка при выполнении миграций: {e}")
            raise

    def _add_column_if_not_exists(
        self, table_name: str, column_name: str, column_definition: str
    ):
        """Добавляет колонку в таблицу, если она не существует."""
        try:
            # Проверяем, существует ли колонка
            cursor = self.conn.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]

            if column_name not in columns:
                self.conn.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )
                logger.info(f"Добавлена колонка {column_name} в таблицу {table_name}")

        except Exception as e:
            logger.warning(f"Не удалось добавить колонку {column_name}: {e}")

    def _create_indexes(self):
        """Создает индексы для оптимизации."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)",
            "CREATE INDEX IF NOT EXISTS idx_analyses_sentiment ON analyses(sentiment)",
            "CREATE INDEX IF NOT EXISTS idx_user_stats_date ON user_stats(date)",
            "CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(is_active)",
        ]

        for index_sql in indexes:
            try:
                self.conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Не удалось создать индекс: {e}")

    def _migrate_existing_subscribers(self):
        """Обновляет существующих подписчиков для совместимости."""
        try:
            # Обновляем всех существующих подписчиков как активных
            self.conn.execute(
                """
                UPDATE subscribers 
                SET is_active = 1, subscribed_at = CURRENT_TIMESTAMP 
                WHERE is_active IS NULL OR subscribed_at IS NULL
            """
            )

            # Создаем настройки по умолчанию для существующих пользователей
            self.conn.execute(
                """
                INSERT OR IGNORE INTO user_settings (chat_id)
                SELECT chat_id FROM subscribers WHERE is_active = 1
            """
            )

        except Exception as e:
            logger.warning(f"Ошибка при миграции существующих подписчиков: {e}")

    # ------------------------------------------------------------------
    # Каналы / последняя позиция
    # ------------------------------------------------------------------
    def get_last_message_id(self, channel_id: str) -> int:
        """Возвращает последний обработанный ID сообщения в канале.

        Если канал ещё не записан — возвращает 0.
        """
        with self._lock, self.conn:
            cur = self.conn.execute(
                "SELECT last_message_id FROM channels WHERE channel_id = ?",
                (channel_id,),
            )
            row = cur.fetchone()
            return int(row["last_message_id"]) if row else 0

    def set_last_message_id(self, channel_id: str, message_id: int) -> None:
        """Обновляет последний обработанный ID сообщения для канала."""
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO channels (channel_id, last_message_id) VALUES (?, ?) "
                "ON CONFLICT(channel_id) DO UPDATE SET last_message_id = excluded.last_message_id",
                (channel_id, message_id),
            )

    # ------------------------------------------------------------------
    # Сырые сообщения / анализ
    # ------------------------------------------------------------------
    def save_message(self, message: Dict[str, Any]) -> None:
        """Сохраняет Telegram-сообщение.

        Ожидается структура:
        {
            "id": int,
            "channel_id": str,
            "text": str,
            "channel_title": str,
            "channel_username": str | None,
            "date": datetime | str,
        }
        """
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO messages (
                    message_id, channel_id, text, channel_title, channel_username, date
                ) VALUES (:id, :channel_id, :text, :channel_title, :channel_username, :date)
                """,
                message,
            )

    def save_analysis(self, message_id: int, analysis: Dict[str, Any]) -> None:
        """Сохраняет результаты анализа (summary, sentiment, hashtags)."""
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO analyses (message_id, summary, sentiment, hashtags)
                VALUES (?, ?, ?, ?)
                """,
                (
                    message_id,
                    analysis.get("summary"),
                    analysis.get("sentiment"),
                    json.dumps(analysis.get("hashtags", [])),
                ),
            )

    # ------------------------------------------------------------------
    # Подписчики
    # ------------------------------------------------------------------
    def get_all_subscribers(self) -> List[int]:
        with self._lock, self.conn:
            cur = self.conn.execute(
                "SELECT chat_id FROM subscribers WHERE is_active = 1"
            )
            return [row["chat_id"] for row in cur.fetchall()]

    def is_subscriber(self, chat_id: int) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute(
                "SELECT 1 FROM subscribers WHERE chat_id = ? AND is_active = 1 LIMIT 1",
                (chat_id,),
            )
            return cur.fetchone() is not None

    def add_subscriber(self, chat_id: int) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """INSERT INTO subscribers (chat_id, subscribed_at, is_active) 
                   VALUES (?, CURRENT_TIMESTAMP, 1)
                   ON CONFLICT(chat_id) DO UPDATE SET is_active = 1""",
                (chat_id,),
            )
            # Создаем настройки по умолчанию
            self.conn.execute(
                """INSERT OR IGNORE INTO user_settings (chat_id) VALUES (?)""",
                (chat_id,),
            )

    def remove_subscriber(self, chat_id: int) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "UPDATE subscribers SET is_active = 0 WHERE chat_id = ?", (chat_id,)
            )

    # ------------------------------------------------------------------
    # Пользовательские настройки
    # ------------------------------------------------------------------
    def get_user_settings(self, chat_id: int) -> dict:
        """Получает настройки пользователя."""
        try:
            with self._lock, self.conn:
                cur = self.conn.execute(
                    """
                    SELECT notification_enabled, sentiment_filter, hashtag_filters, 
                           quiet_hours_start, quiet_hours_end, language
                    FROM user_settings 
                    WHERE chat_id = ?
                """,
                    (chat_id,),
                )

                row = cur.fetchone()
                if row:
                    return {
                        "notification_enabled": bool(row["notification_enabled"]),
                        "sentiment_filter": row["sentiment_filter"],
                        "hashtag_filters": (
                            json.loads(row["hashtag_filters"])
                            if row["hashtag_filters"]
                            else []
                        ),
                        "quiet_hours_start": row["quiet_hours_start"],
                        "quiet_hours_end": row["quiet_hours_end"],
                        "language": row["language"],
                    }
                else:
                    # Возвращаем настройки по умолчанию
                    return {
                        "notification_enabled": True,
                        "sentiment_filter": "all",
                        "hashtag_filters": [],
                        "quiet_hours_start": None,
                        "quiet_hours_end": None,
                        "language": "ru",
                    }
        except Exception as e:
            logger.error(f"Ошибка при получении настроек пользователя {chat_id}: {e}")
            return {
                "notification_enabled": True,
                "sentiment_filter": "all",
                "hashtag_filters": [],
                "quiet_hours_start": None,
                "quiet_hours_end": None,
                "language": "ru",
            }

    def update_user_settings(self, chat_id: int, settings: dict) -> bool:
        """Обновляет настройки пользователя."""
        try:
            with self._lock, self.conn:
                # Сначала убеждаемся, что запись существует
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO user_settings (chat_id) VALUES (?)
                """,
                    (chat_id,),
                )

                # Обновляем только переданные настройки
                update_parts = []
                values = []

                if "notification_enabled" in settings:
                    update_parts.append("notification_enabled = ?")
                    values.append(int(settings["notification_enabled"]))

                if "sentiment_filter" in settings:
                    update_parts.append("sentiment_filter = ?")
                    values.append(settings["sentiment_filter"])

                if "hashtag_filters" in settings:
                    update_parts.append("hashtag_filters = ?")
                    values.append(json.dumps(settings["hashtag_filters"]))

                if "quiet_hours_start" in settings:
                    update_parts.append("quiet_hours_start = ?")
                    values.append(settings["quiet_hours_start"])

                if "quiet_hours_end" in settings:
                    update_parts.append("quiet_hours_end = ?")
                    values.append(settings["quiet_hours_end"])

                if "language" in settings:
                    update_parts.append("language = ?")
                    values.append(settings["language"])

                if update_parts:
                    update_parts.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(chat_id)

                    sql = f"UPDATE user_settings SET {', '.join(update_parts)} WHERE chat_id = ?"
                    self.conn.execute(sql, values)

                return True

        except Exception as e:
            logger.error(f"Ошибка при обновлении настроек пользователя {chat_id}: {e}")
            return False

    def should_send_notification(
        self,
        chat_id: int,
        sentiment: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
    ) -> bool:
        """Проверяет, нужно ли отправлять уведомление пользователю."""
        try:
            settings = self.get_user_settings(chat_id)

            # Проверяем, включены ли уведомления
            if not settings["notification_enabled"]:
                return False

            # Проверяем фильтр тональности
            sentiment_filter = settings["sentiment_filter"]
            if sentiment_filter != "all" and sentiment:
                sentiment_map = {
                    "positive": "Позитивная",
                    "negative": "Негативная",
                    "neutral": "Нейтральная",
                }
                if sentiment != sentiment_map.get(sentiment_filter):
                    return False

            # Проверяем тихие часы
            quiet_start = settings.get("quiet_hours_start")
            quiet_end = settings.get("quiet_hours_end")
            if quiet_start and quiet_end:
                from datetime import datetime

                now = datetime.now().time()
                start_time = datetime.strptime(quiet_start, "%H:%M").time()
                end_time = datetime.strptime(quiet_end, "%H:%M").time()

                if start_time <= now <= end_time:
                    return False

            # Проверяем фильтры хештегов (если настроены)
            hashtag_filters = settings.get("hashtag_filters", [])
            if hashtag_filters and hashtags:
                # Если есть фильтры хештегов, проверяем пересечение
                if not any(tag in hashtag_filters for tag in hashtags):
                    return False

            return True

        except Exception as e:
            logger.error(f"Ошибка при проверке настроек уведомлений для {chat_id}: {e}")
            return True  # По умолчанию отправляем уведомления

    # ------------------------------------------------------------------
    # Статистика
    # ------------------------------------------------------------------
    def get_statistics(self) -> Optional[Dict[str, Any]]:  # noqa: ANN401
        """Возвращает агрегированную статистику по сообщениям и анализам."""
        with self._lock, self.conn:
            cur_total = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM messages LIMIT 1"
            )
            total_messages = cur_total.fetchone()["cnt"]
            if total_messages == 0:
                return None

            # sentiment counts с оптимизацией
            cur_sent = self.conn.execute(
                """SELECT sentiment, COUNT(*) AS c 
                   FROM analyses 
                   WHERE sentiment IS NOT NULL
                   GROUP BY sentiment 
                   LIMIT 10"""
            )
            sentiment_counts = {
                row["sentiment"]: row["c"] for row in cur_sent.fetchall()
            }

            # top hashtags (JSON arrays) – flatten с лимитом
            cur_hashtags = self.conn.execute(
                """SELECT hashtags 
                   FROM analyses 
                   WHERE hashtags IS NOT NULL 
                   AND hashtags != '[]'
                   LIMIT 1000"""  # Ограничиваем выборку для производительности
            )
            hashtag_counter: Dict[str, int] = {}
            for row in cur_hashtags.fetchall():
                try:
                    tags = json.loads(row["hashtags"]) or []
                except json.JSONDecodeError:
                    continue
                for tag in tags:
                    hashtag_counter[tag] = hashtag_counter.get(tag, 0) + 1

            # sort by freq desc
            popular_hashtags = [
                tag
                for tag, _ in sorted(
                    hashtag_counter.items(), key=lambda kv: kv[1], reverse=True
                )[:10]
            ]

            return {
                "total_messages": total_messages,
                "sentiment_counts": sentiment_counts,
                "popular_hashtags": popular_hashtags,
            }

    def get_extended_statistics(self) -> Dict[str, Any]:
        """Возвращает расширенную статистику системы."""
        with self._lock, self.conn:
            # Основная статистика
            base_stats = self.get_statistics() or {}

            # Статистика подписчиков
            cur_subs = self.conn.execute(
                """SELECT COUNT(*) as total, 
                          COUNT(CASE WHEN is_active = 1 THEN 1 END) as active
                   FROM subscribers"""
            )
            sub_stats = cur_subs.fetchone()

            # Статистика по дням (последние 7 дней)
            cur_daily = self.conn.execute(
                """SELECT date, messages_processed, notifications_sent
                   FROM system_stats 
                   ORDER BY date DESC LIMIT 7"""
            )
            daily_stats = [dict(row) for row in cur_daily.fetchall()]

            # Топ каналы по активности
            cur_channels = self.conn.execute(
                """SELECT channel_title, COUNT(*) as message_count
                   FROM messages 
                   GROUP BY channel_title 
                   ORDER BY message_count DESC LIMIT 5"""
            )
            top_channels = [dict(row) for row in cur_channels.fetchall()]

            return {
                **base_stats,
                "subscribers": {
                    "total": sub_stats["total"],
                    "active": sub_stats["active"],
                },
                "daily_stats": daily_stats,
                "top_channels": top_channels,
            }

    def record_daily_stats(
        self,
        messages_processed: int = 0,
        notifications_sent: int = 0,
        new_subscribers: int = 0,
        unsubscribes: int = 0,
    ) -> None:
        """Записывает ежедневную статистику."""
        from datetime import date

        today = date.today().isoformat()

        with self._lock, self.conn:
            self.conn.execute(
                """INSERT INTO system_stats 
                   (date, messages_processed, messages_failed, notifications_sent, new_subscribers, unsubscribes)
                   VALUES (?, ?, 0, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                   messages_processed = messages_processed + excluded.messages_processed,
                   notifications_sent = notifications_sent + excluded.notifications_sent,
                   new_subscribers = new_subscribers + excluded.new_subscribers,
                   unsubscribes = unsubscribes + excluded.unsubscribes""",
                (
                    today,
                    messages_processed,
                    notifications_sent,
                    new_subscribers,
                    unsubscribes,
                ),
            )

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------
    def close(self):
        try:
            self.conn.close()
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------
    # Context-manager helpers
    # ------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
