"""Утилита для работы с локальной SQLite-базой.

Хранит:
1. Последний обработанный ID сообщения для каждого канала
2. Сырые сообщения
3. Результаты LLM-анализа
4. Подписчиков бота

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
            cur = self.conn.execute("SELECT chat_id FROM subscribers")
            return [row["chat_id"] for row in cur.fetchall()]

    def is_subscriber(self, chat_id: int) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute(
                "SELECT 1 FROM subscribers WHERE chat_id = ? LIMIT 1", (chat_id,)
            )
            return cur.fetchone() is not None

    def add_subscriber(self, chat_id: int) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (chat_id,)
            )

    def remove_subscriber(self, chat_id: int) -> None:
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))

    # ------------------------------------------------------------------
    # Статистика
    # ------------------------------------------------------------------
    def get_statistics(self) -> Optional[Dict[str, Any]]:  # noqa: ANN401
        """Возвращает агрегированную статистику по сообщениям и анализам."""
        with self._lock, self.conn:
            cur_total = self.conn.execute("SELECT COUNT(*) AS cnt FROM messages")
            total_messages = cur_total.fetchone()["cnt"]
            if total_messages == 0:
                return None

            # sentiment counts
            cur_sent = self.conn.execute(
                "SELECT sentiment, COUNT(*) AS c FROM analyses GROUP BY sentiment"
            )
            sentiment_counts = {
                row["sentiment"]: row["c"] for row in cur_sent.fetchall()
            }

            # top hashtags (JSON arrays) – flatten
            cur_hashtags = self.conn.execute(
                "SELECT hashtags FROM analyses WHERE hashtags IS NOT NULL"
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
