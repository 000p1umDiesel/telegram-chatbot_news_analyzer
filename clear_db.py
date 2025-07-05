#!/usr/bin/env python3
"""
Скрипт для очистки данных в PostgreSQL.
"""

import asyncio
import sys
from services.db.pg_manager import AsyncPostgresManager
from logger import get_logger

logger = get_logger()


async def clear_database():
    """Очищает данные в базе данных."""
    print("🗑️ Подключение к базе данных...")

    try:
        # Создаем менеджер БД
        data_manager = await AsyncPostgresManager.create()

        # Список таблиц для очистки
        tables_to_clear = ["messages", "analyses", "llm_calls", "channels"]

        print(f"📋 Будут очищены таблицы: {', '.join(tables_to_clear)}")

        # Подтверждение
        confirm = input("⚠️ Вы уверены? Это удалит все данные! (y/N): ")
        if confirm.lower() != "y":
            print("❌ Операция отменена.")
            return

        # Очищаем таблицы
        async with data_manager.pool.acquire() as conn:
            for table in tables_to_clear:
                await conn.execute(f"TRUNCATE TABLE {table}")
                print(f"✅ Очищена таблица: {table}")

        print("🎉 База данных очищена!")

        # Показываем статистику
        async with data_manager.pool.acquire() as conn:
            subscribers_count = await conn.fetchval(
                "SELECT COUNT(*) FROM subscribers WHERE is_active = TRUE"
            )
            print(f"📊 Осталось активных подписчиков: {subscribers_count}")

    except Exception as e:
        logger.error(f"❌ Ошибка очистки БД: {e}")
        sys.exit(1)
    finally:
        if "data_manager" in locals():
            await data_manager.close()


async def clear_subscribers():
    """Очищает подписчиков (ОПАСНО!)."""
    print("⚠️ ВНИМАНИЕ: Это удалит ВСЕХ подписчиков!")

    confirm = input("Вы ТОЧНО уверены? Введите 'DELETE ALL': ")
    if confirm != "DELETE ALL":
        print("❌ Операция отменена.")
        return

    try:
        data_manager = await AsyncPostgresManager.create()

        async with data_manager.pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE user_settings")
            await conn.execute("TRUNCATE TABLE subscribers")

        print("🗑️ Все подписчики удалены!")

    except Exception as e:
        logger.error(f"❌ Ошибка удаления подписчиков: {e}")
    finally:
        if "data_manager" in locals():
            await data_manager.close()


async def show_stats():
    """Показывает статистику БД."""
    try:
        data_manager = await AsyncPostgresManager.create()

        async with data_manager.pool.acquire() as conn:
            messages_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
            analyses_count = await conn.fetchval("SELECT COUNT(*) FROM analyses")
            llm_calls_count = await conn.fetchval("SELECT COUNT(*) FROM llm_calls")
            subscribers_count = await conn.fetchval(
                "SELECT COUNT(*) FROM subscribers WHERE is_active = TRUE"
            )
            channels_count = await conn.fetchval("SELECT COUNT(*) FROM channels")

        print("📊 Статистика базы данных:")
        print(f"  📰 Сообщений: {messages_count}")
        print(f"  🔍 Анализов: {analyses_count}")
        print(f"  🤖 LLM вызовов: {llm_calls_count}")
        print(f"  👥 Подписчиков: {subscribers_count}")
        print(f"  📺 Каналов: {channels_count}")

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
    finally:
        if "data_manager" in locals():
            await data_manager.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python clear_db.py stats        - показать статистику")
        print("  python clear_db.py clear        - очистить данные (кроме подписчиков)")
        print(
            "  python clear_db.py clear-all    - очистить ВСЕ данные включая подписчиков"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "stats":
        asyncio.run(show_stats())
    elif command == "clear":
        asyncio.run(clear_database())
    elif command == "clear-all":
        asyncio.run(clear_database())
        asyncio.run(clear_subscribers())
    else:
        print(f"❌ Неизвестная команда: {command}")
        sys.exit(1)
