#!/usr/bin/env python3
"""
Скрипт для инициализации Telegram сессии.
Запустите этот скрипт один раз для авторизации в Telegram API.
"""

import asyncio
import os
from telethon import TelegramClient
from core.config import settings as config


async def main():
    """Инициализация Telegram сессии."""
    print("🔐 Инициализация Telegram сессии...")

    # Проверяем наличие необходимых данных
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        print(
            "❌ Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть установлены в .env"
        )
        return

    if not config.TELEGRAM_PHONE:
        print("❌ Ошибка: TELEGRAM_PHONE должен быть установлен в .env")
        return

    # Создаем директорию для сессий
    os.makedirs(".sessions", exist_ok=True)

    session_file = ".sessions/monitor_session"

    client = TelegramClient(
        session_file, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH
    )

    try:
        print(f"📱 Подключение к Telegram с номером {config.TELEGRAM_PHONE}...")
        await client.start(phone=config.TELEGRAM_PHONE)

        if await client.is_user_authorized():
            print("✅ Авторизация успешна!")

            # Тестируем доступ к каналам
            print(f"🔍 Проверка доступа к каналам: {config.channel_ids}")

            for channel_id in config.channel_ids:
                try:
                    if channel_id.startswith("@"):
                        entity = await client.get_entity(channel_id)
                    elif channel_id.startswith("-"):
                        entity = await client.get_entity(int(channel_id))
                    else:
                        entity = await client.get_entity(channel_id)

                    print(f"  ✅ {channel_id} - {getattr(entity, 'title', 'Unknown')}")
                except Exception as e:
                    print(f"  ❌ {channel_id} - Ошибка: {e}")

            print(
                "\n🎉 Инициализация завершена! Теперь можно запускать основное приложение."
            )
        else:
            print("❌ Авторизация не удалась")

    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
