# init_session.py
import asyncio
from telethon import TelegramClient  # type: ignore
import config
import os
from logger import get_logger
from telethon.errors import SessionPasswordNeededError  # type: ignore

logger = get_logger()

# Этот скрипт нужно запустить один раз для создания файла сессии .sessions/telegram_session.session
# Введите свои данные (номер телефона, код, пароль) в консоли при первом запуске.


async def main():
    logger.info("Запуск скрипта для создания сессии Telethon...")
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        raise ValueError(
            "TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть установлены в .env"
        )

    session_path = os.path.join(".sessions", "telegram_session")
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    client = TelegramClient(
        session_path, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH
    )

    await client.connect()

    if await client.is_user_authorized():
        logger.info("Вы уже авторизованы. Файл сессии существует и валиден.")
    else:
        logger.info("Требуется авторизация.")
        # Просим номер телефона. Telethon сам запросит код и пароль.
        try:
            await client.send_code_request(config.TELEGRAM_PHONE)
            code = input("Введите код, полученный в Telegram: ")
            try:
                await client.sign_in(config.TELEGRAM_PHONE, code)
            except SessionPasswordNeededError:
                # Аккаунт защищён двухфакторной аутентификацией (пароль)
                password = input("Введите пароль двухфакторной аутентификации: ")
                await client.sign_in(password=password)
        except Exception as auth_err:
            logger.error(f"Не удалось завершить авторизацию: {auth_err}")
            return
        logger.info("Авторизация прошла успешно. Файл сессии создан.")

    await client.disconnect()
    logger.info("Скрипт завершил работу.")


if __name__ == "__main__":
    asyncio.run(main())
