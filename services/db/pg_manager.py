from __future__ import annotations

"""Async Postgres data manager based on asyncpg.

Implements the same high-level interface that synchronous `PostgresManager`
provided earlier, но все методы асинхронные.

Usage (factory):
    data_manager = await AsyncPostgresManager.create()

Later we will adapt the application to use this implementation.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import asyncpg  # type: ignore
from asyncpg.pool import Pool

from core.config import settings as config
from logger import get_logger

logger = get_logger()


class AsyncPostgresManager:  # pylint: disable=too-few-public-methods
    """Asynchronous Postgres manager working via asyncpg connection pool."""

    def __init__(self, pool: Pool):
        self.pool = pool

    # ---------------------------------------------------------------------
    # Factory
    # ---------------------------------------------------------------------
    @classmethod
    async def create(cls, dsn: str | None = None) -> "AsyncPostgresManager":
        pool = await asyncpg.create_pool(
            dsn=dsn or config.POSTGRES_DSN,
            min_size=config.POSTGRES_POOL_MIN_SIZE,
            max_size=config.POSTGRES_POOL_MAX_SIZE,
        )
        mgr = cls(pool)
        await mgr._create_schema()
        logger.info("Async Postgres pool initialised: %s", dsn or config.POSTGRES_DSN)
        return mgr

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    async def _create_schema(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS channels (
            channel_id       TEXT PRIMARY KEY,
            last_message_id  BIGINT DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            channel_id       TEXT,
            message_id       BIGINT,
            text             TEXT,
            channel_title    TEXT,
            channel_username TEXT,
            date             TIMESTAMPTZ,
            PRIMARY KEY(channel_id, message_id)
        );

        CREATE TABLE IF NOT EXISTS analyses (
            message_id BIGINT PRIMARY KEY,
            summary    TEXT,
            sentiment  TEXT,
            hashtags   JSONB
        );

        CREATE TABLE IF NOT EXISTS llm_calls (
            id          BIGSERIAL PRIMARY KEY,
            prompt      TEXT,
            completion  TEXT,
            latency_ms  INTEGER,
            created_at  TIMESTAMPTZ DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id       BIGINT PRIMARY KEY,
            subscribed_at TIMESTAMPTZ DEFAULT now(),
            is_active     BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            chat_id              BIGINT PRIMARY KEY REFERENCES subscribers(chat_id),
            notification_enabled BOOLEAN DEFAULT TRUE,
            sentiment_filter     TEXT    DEFAULT 'all',
            hashtag_filters      JSONB,
            quiet_hours_start    TEXT,
            quiet_hours_end      TEXT,
            language             TEXT    DEFAULT 'ru',
            created_at           TIMESTAMPTZ DEFAULT now(),
            updated_at           TIMESTAMPTZ DEFAULT now()
        );
        """
        async with self.pool.acquire() as conn:
            await conn.execute(ddl)

    # ------------------------------------------------------------------
    # Каналы / последняя позиция
    # ------------------------------------------------------------------
    async def get_last_message_id(self, channel_id: str) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_message_id FROM channels WHERE channel_id=$1", channel_id
            )
            return int(row["last_message_id"]) if row else 0

    async def set_last_message_id(self, channel_id: str, message_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO channels(channel_id, last_message_id)
                VALUES ($1, $2)
                ON CONFLICT(channel_id) DO UPDATE SET last_message_id = EXCLUDED.last_message_id
                """,
                channel_id,
                message_id,
            )

    # ------------------------------------------------------------------
    # Сохранение сообщений / анализа
    # ------------------------------------------------------------------
    async def save_message(self, message: Dict[str, Any]) -> None:  # noqa: ANN401
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages(channel_id, message_id, text, channel_title, channel_username, date)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                message.get("channel_id"),
                message.get("id"),
                message.get("text"),
                message.get("channel_title"),
                message.get("channel_username"),
                message.get("date"),
            )

    async def save_analysis(
        self, message_id: int, analysis: Dict[str, Any]
    ) -> None:  # noqa: ANN401
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analyses(message_id, summary, sentiment, hashtags)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(message_id) DO UPDATE SET
                    summary   = EXCLUDED.summary,
                    sentiment = EXCLUDED.sentiment,
                    hashtags  = EXCLUDED.hashtags
                """,
                message_id,
                analysis.get("summary"),
                analysis.get("sentiment"),
                json.dumps(analysis.get("hashtags", [])),
            )

    # ------------------------------------------------------------------
    # Подписчики
    # ------------------------------------------------------------------
    async def get_all_subscribers(self) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT chat_id FROM subscribers WHERE is_active = TRUE"
            )
            return [r["chat_id"] for r in rows]

    async def is_subscriber(self, chat_id: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM subscribers WHERE chat_id=$1 AND is_active=TRUE LIMIT 1",
                chat_id,
            )
            return row is not None

    async def add_subscriber(self, chat_id: int) -> None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO subscribers(chat_id, is_active)
                    VALUES ($1, TRUE)
                    ON CONFLICT(chat_id) DO UPDATE SET is_active = TRUE
                    """,
                    chat_id,
                )
                await conn.execute(
                    """
                    INSERT INTO user_settings(chat_id) VALUES ($1)
                    ON CONFLICT DO NOTHING
                    """,
                    chat_id,
                )

    async def remove_subscriber(self, chat_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE subscribers SET is_active = FALSE WHERE chat_id=$1",
                chat_id,
            )

    # ------------------------------------------------------------------
    # LLM logging
    # ------------------------------------------------------------------
    async def log_llm_call(
        self, prompt: str, completion: str, latency_ms: int
    ) -> None:  # noqa: D401
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_calls(prompt, completion, latency_ms)
                VALUES ($1, $2, $3)
                """,
                prompt,
                completion,
                latency_ms,
            )

    # ------------------------------------------------------------------
    # Пользовательские настройки (пример одного метода)
    # ------------------------------------------------------------------
    async def get_user_settings(self, chat_id: int) -> Dict[str, Any]:  # noqa: ANN401
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT notification_enabled, sentiment_filter, hashtag_filters, \
                       quiet_hours_start, quiet_hours_end, language
                FROM user_settings WHERE chat_id=$1
                """,
                chat_id,
            )
            return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    async def close(self):  # noqa: D401
        """Close pool connections gracefully."""
        await self.pool.close()


# -----------------------------------------------------------------------------
# Convenient helper for scripts: create sync wrapper that runs event loop
# -----------------------------------------------------------------------------


def create_sync_postgres_manager() -> AsyncPostgresManager:  # noqa: D401
    """Create manager inside new event loop for legacy sync code paths."""

    async def _factory() -> AsyncPostgresManager:  # noqa: D401
        return await AsyncPostgresManager.create()

    return asyncio.run(_factory())
