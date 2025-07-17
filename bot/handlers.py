# handlers.py - Улучшенный интерфейс бота с клавишами и фильтрами
import asyncio
from aiogram import Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from services import llm_analyzer, tavily_search

from core.config import settings as config
from logger import get_logger
from typing import Dict, Any, List

from bot.notifier import send_analysis_result
from bot import bot

logger = get_logger()
dp = Dispatcher()


def get_simple_data_manager():
    """Получает простой синхронный менеджер для бота."""
    try:
        from services.db.sync_pg_manager import get_sync_postgres_manager

        return get_sync_postgres_manager()
    except Exception as e:
        logger.error(f"Ошибка получения синхронного менеджера: {e}")
        return None


def get_main_keyboard():
    """Создает основную клавиатуру с удобными кнопками."""
    builder = ReplyKeyboardBuilder()
    builder.add(
        types.KeyboardButton(text="📊 Статистика"),
        types.KeyboardButton(text="🔔 Подписка"),
        types.KeyboardButton(text="⚙️ Настройки"),
        types.KeyboardButton(text="📈 Тренды"),
        types.KeyboardButton(text="💬 Чат с ИИ"),
        types.KeyboardButton(text="🔍 Поиск"),
        types.KeyboardButton(text="📰 Дайджест"),
        types.KeyboardButton(text="ℹ️ Помощь"),
    )
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)


def get_subscription_keyboard(chat_id: int):
    """Создает клавиатуру управления подпиской."""
    builder = InlineKeyboardBuilder()
    data_manager = get_simple_data_manager()

    if data_manager and data_manager.is_subscriber(chat_id):
        builder.button(text="🔕 Отписаться", callback_data="unsubscribe")
        builder.button(text="📋 Мои настройки", callback_data="my_settings")
    else:
        builder.button(text="🔔 Подписаться", callback_data="subscribe")

    builder.adjust(1)
    return builder.as_markup()


def get_settings_keyboard():
    """Создает клавиатуру настроек."""
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="📊 Статистика системы", callback_data="system_stats"
        ),
        types.InlineKeyboardButton(
            text="🔔 Настройки уведомлений", callback_data="notification_settings"
        ),
        types.InlineKeyboardButton(
            text="🎭 Фильтр тональности", callback_data="sentiment_filter"
        ),
        types.InlineKeyboardButton(
            text="📺 Фильтр каналов", callback_data="channel_filter"
        ),
        types.InlineKeyboardButton(text="🗑 Очистить кэш", callback_data="clear_cache"),
    )
    builder.adjust(2)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение."""
    if not message.chat:
        return

    chat_id = message.chat.id
    user_name = message.from_user.first_name if message.from_user else "Пользователь"

    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        "🤖 Я бот для анализа новостей с помощью ИИ.\n\n"
        "🔥 **Мои возможности:**\n"
        "• 📰 Анализ новостей из Telegram-каналов\n"
        "• 🎯 Определение тональности и тематики\n"
        "• 💬 Общение с ИИ-ассистентом\n"
        "• 🔍 Поиск информации в интернете\n"
        "• 📊 Статистика и тренды\n"
        "• ⚙️ Настройки уведомлений\n\n"
        "👇 **Используйте кнопки для навигации:**"
    )

    await message.answer(
        welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard()
    )

    await message.answer(
        "🔔 **Управление подпиской:**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_subscription_keyboard(chat_id),
    )


# Обработчики кнопок основного меню
@dp.message(F.text == "📊 Статистика")
async def handle_stats_button(message: types.Message):
    await cmd_stats(message)


@dp.message(F.text == "🔔 Подписка")
async def handle_subscription_button(message: types.Message):
    await cmd_subscribe(message)


@dp.message(F.text == "⚙️ Настройки")
async def handle_settings_button(message: types.Message):
    await cmd_settings(message)


@dp.message(F.text == "📈 Тренды")
async def handle_trends_button(message: types.Message):
    await cmd_trends(message)


@dp.message(F.text == "💬 Чат с ИИ")
async def handle_chat_button(message: types.Message):
    await message.answer(
        "💬 **Чат с ИИ-ассистентом**\n\n"
        "Просто напишите мне что-нибудь, и я отвечу!\n"
        "Или используйте команду `/chat <ваш вопрос>`",
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message(F.text == "🔍 Поиск")
async def handle_search_button(message: types.Message):
    await message.answer(
        "🔍 **Поиск в интернете**\n\n"
        "Используйте команду `/web <поисковый запрос>`\n\n"
        "Пример: `/web новости технологий`",
        parse_mode=ParseMode.MARKDOWN,
    )


@dp.message(F.text == "📰 Дайджест")
async def handle_digest_button(message: types.Message):
    await cmd_digest(message)


@dp.message(F.text == "ℹ️ Помощь")
async def handle_help_button(message: types.Message):
    await cmd_help(message)


# Callback handlers
@dp.callback_query(F.data == "subscribe")
async def process_callback_subscribe(callback_query: types.CallbackQuery):
    """Обрабатывает подписку."""
    await callback_query.answer()

    if not callback_query.message:
        return

    data_manager = get_simple_data_manager()
    if not data_manager:
        await callback_query.message.answer("❌ Сервис временно недоступен.")
        return

    chat_id = callback_query.message.chat.id
    try:
        if data_manager.is_subscriber(chat_id):
            await callback_query.message.answer("✅ Вы уже подписаны!")
        else:
            data_manager.add_subscriber(chat_id)
            await callback_query.message.answer("✅ Подписка оформлена!")
    except Exception as e:
        logger.error(f"Ошибка при подписке пользователя {chat_id}: {e}")
        await callback_query.message.answer("❌ Ошибка при подписке.")


@dp.callback_query(F.data == "unsubscribe")
async def process_callback_unsubscribe(callback_query: types.CallbackQuery):
    """Обрабатывает отписку."""
    await callback_query.answer()

    if not callback_query.message:
        return

    data_manager = get_simple_data_manager()
    if not data_manager:
        await callback_query.message.answer("❌ Сервис временно недоступен.")
        return

    chat_id = callback_query.message.chat.id
    try:
        if not data_manager.is_subscriber(chat_id):
            await callback_query.message.answer("❌ Вы не подписаны.")
        else:
            data_manager.remove_subscriber(chat_id)
            await callback_query.message.answer("✅ Отписка выполнена.")
    except Exception as e:
        logger.error(f"Ошибка при отписке пользователя {chat_id}: {e}")
        await callback_query.message.answer("❌ Ошибка при отписке.")


@dp.callback_query(F.data == "my_settings")
async def process_callback_my_settings(callback_query: types.CallbackQuery):
    """Показывает настройки пользователя."""
    await callback_query.answer()

    if not callback_query.message:
        return

    chat_id = callback_query.message.chat.id
    data_manager = get_simple_data_manager()

    if data_manager:
        settings = data_manager.get_user_settings(chat_id)
        is_subscribed = data_manager.is_subscriber(chat_id)

        text = (
            f"📋 **Ваши настройки:**\n\n"
            f"🔔 Подписка: {'✅ Активна' if is_subscribed else '❌ Неактивна'}\n"
            f"🎭 Фильтр тональности: {settings.get('sentiment_filter', 'all')}\n"
            f"📺 Отслеживаемые каналы: {len(config.channel_ids)}\n"
            f"🌐 Язык: {settings.get('language', 'ru')}\n"
        )

        await callback_query.message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.callback_query(F.data == "clear_cache")
async def process_callback_clear_cache(callback_query: types.CallbackQuery):
    """Очищает кэш."""
    await callback_query.answer("✅ Кэш очищен!")
    try:
        llm_analyzer.clear_cache()
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")


@dp.callback_query(F.data == "notification_settings")
async def process_callback_notification_settings(callback_query: types.CallbackQuery):
    """Показывает настройки уведомлений."""
    await callback_query.answer()

    if not callback_query.message:
        return

    chat_id = callback_query.message.chat.id
    data_manager = get_simple_data_manager()

    if not data_manager:
        await callback_query.message.answer("❌ Сервис временно недоступен.")
        return

    settings = data_manager.get_user_settings(chat_id)

    # Создаем клавиатуру для настроек уведомлений
    builder = InlineKeyboardBuilder()
    current_enabled = settings.get("notification_enabled", True)

    builder.add(
        types.InlineKeyboardButton(
            text=f"🔔 Уведомления: {'✅ Вкл' if current_enabled else '❌ Выкл'}",
            callback_data=f"toggle_notifications_{not current_enabled}",
        )
    )

    text = (
        "🔔 **Настройки уведомлений:**\n\n"
        f"Текущий статус: {'✅ Включены' if current_enabled else '❌ Выключены'}\n\n"
        "Нажмите кнопку для изменения:"
    )

    await callback_query.message.answer(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("toggle_notifications_"))
async def process_toggle_notifications(callback_query: types.CallbackQuery):
    """Переключает уведомления."""
    await callback_query.answer()

    if not callback_query.message:
        return

    chat_id = callback_query.message.chat.id
    data_manager = get_simple_data_manager()

    if not data_manager:
        await callback_query.message.answer("❌ Сервис временно недоступен.")
        return

    # Извлекаем новое значение из callback_data
    new_value = callback_query.data.split("_")[-1] == "True"

    # Обновляем настройки
    success = data_manager.update_user_settings(
        chat_id, {"notification_enabled": new_value}
    )

    if success:
        status_text = "включены" if new_value else "выключены"
        await callback_query.message.answer(
            f"✅ Уведомления {status_text}!", parse_mode=ParseMode.MARKDOWN
        )
    else:
        await callback_query.message.answer("❌ Ошибка обновления настроек.")


@dp.callback_query(F.data == "sentiment_filter")
async def process_callback_sentiment_filter(callback_query: types.CallbackQuery):
    """Показывает фильтр тональности."""
    await callback_query.answer()

    if not callback_query.message:
        return

    chat_id = callback_query.message.chat.id
    data_manager = get_simple_data_manager()

    if not data_manager:
        await callback_query.message.answer("❌ Сервис временно недоступен.")
        return

    settings = data_manager.get_user_settings(chat_id)
    current_filter = settings.get("sentiment_filter", "all")

    # Создаем клавиатуру для фильтра тональности
    builder = InlineKeyboardBuilder()

    filters = [
        ("all", "Все новости"),
        ("Позитивная", "😊 Позитивные"),
        ("Негативная", "😔 Негативные"),
        ("Нейтральная", "😐 Нейтральные"),
    ]

    for filter_value, filter_name in filters:
        is_current = filter_value == current_filter
        button_text = f"{'✅ ' if is_current else ''}{filter_name}"
        builder.add(
            types.InlineKeyboardButton(
                text=button_text, callback_data=f"set_sentiment_{filter_value}"
            )
        )

    builder.adjust(1)

    text = (
        "🎭 **Фильтр тональности:**\n\n"
        f"Текущий фильтр: {dict(filters)[current_filter]}\n\n"
        "Выберите тип новостей для получения:"
    )

    await callback_query.message.answer(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("set_sentiment_"))
async def process_set_sentiment(callback_query: types.CallbackQuery):
    """Устанавливает фильтр тональности."""
    await callback_query.answer()

    if not callback_query.message:
        return

    chat_id = callback_query.message.chat.id
    data_manager = get_simple_data_manager()

    if not data_manager:
        await callback_query.message.answer("❌ Сервис временно недоступен.")
        return

    # Извлекаем значение фильтра
    sentiment_filter = callback_query.data.replace("set_sentiment_", "")

    # Обновляем настройки
    success = data_manager.update_user_settings(
        chat_id, {"sentiment_filter": sentiment_filter}
    )

    if success:
        filter_names = {
            "all": "все новости",
            "Позитивная": "позитивные новости",
            "Негативная": "негативные новости",
            "Нейтральная": "нейтральные новости",
        }
        await callback_query.message.answer(
            f"✅ Фильтр установлен: {filter_names.get(sentiment_filter, sentiment_filter)}!",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await callback_query.message.answer("❌ Ошибка обновления настроек.")


@dp.callback_query(F.data == "channel_filter")
async def process_callback_channel_filter(callback_query: types.CallbackQuery):
    """Показывает фильтр каналов."""
    await callback_query.answer()

    if not callback_query.message:
        return

    # Получаем список отслеживаемых каналов
    try:
        channels_info = []
        if hasattr(config, "channel_ids"):
            for channel_id in config.channel_ids:
                channels_info.append(f"📺 {channel_id}")

        if channels_info:
            text = (
                "📺 Отслеживаемые каналы:\n\n"
                + "\n".join(channels_info[:10])  # Показываем первые 10
                + (
                    f"\n\n... и еще {len(channels_info) - 10}"
                    if len(channels_info) > 10
                    else ""
                )
                + "\n\n💡 Настройка каналов доступна только администратору."
            )
        else:
            text = "📺 Отслеживаемые каналы:\n\nСписок каналов пуст."

        await callback_query.message.answer(text)

    except Exception as e:
        logger.error(f"Ошибка получения списка каналов: {e}")
        await callback_query.message.answer("❌ Ошибка получения списка каналов.")


@dp.callback_query(F.data.startswith("hashtag_"))
async def process_hashtag_click(callback_query: types.CallbackQuery):
    """Обрабатывает клик по хештегу."""
    await callback_query.answer()

    if not callback_query.message:
        return

    hashtag = callback_query.data.replace("hashtag_", "")

    try:
        data_manager = get_simple_data_manager()
        if not data_manager:
            await callback_query.message.answer("❌ Сервис временно недоступен.")
            return

        # Ищем новости с данным хештегом (исправленный запрос для JSONB)
        news_with_hashtag = data_manager._execute(
            """
            SELECT a.summary, a.sentiment, m.channel_title, m.channel_username, m.message_id, m.channel_id
            FROM analyses a
            JOIN messages m ON a.message_id = m.message_id
            WHERE a.hashtags::jsonb ? %s
            ORDER BY m.date DESC
            LIMIT 5
            """,
            (hashtag,),
        )

        if not news_with_hashtag:
            await callback_query.message.answer(
                f"📰 Новости с хештегом #{hashtag} не найдены."
            )
            return

        response_text = f"🏷️ Новости с хештегом #{hashtag}:\n\n"

        for i, news in enumerate(news_with_hashtag, 1):
            emoji = {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
                news.get("sentiment", ""), "📰"
            )

            response_text += (
                f"{i}. {emoji} {news.get('summary', 'Нет описания')[:100]}...\n"
            )
            response_text += (
                f"   📺 {news.get('channel_title', 'Неизвестный канал')}\n\n"
            )

        response_text += "👇 **Выберите новость для перехода:**"

        # Создаем клавиатуру с кнопками для каждой новости
        keyboard = get_hashtag_news_keyboard(news_with_hashtag, hashtag)

        await callback_query.message.answer(
            response_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.error(f"Ошибка поиска по хештегу {hashtag}: {e}")
        await callback_query.message.answer(f"❌ Ошибка поиска по хештегу #{hashtag}.")


@dp.callback_query(F.data.startswith("hashtag_news_"))
async def process_hashtag_news_click(callback_query: types.CallbackQuery):
    """Обрабатывает клик по новости из списка трендов."""
    await callback_query.answer()

    if not callback_query.message:
        return

    try:
        # Извлекаем hashtag и news_index из callback_data
        callback_data = callback_query.data.replace("hashtag_news_", "")
        parts = callback_data.rsplit("_", 1)  # Разделяем по последнему _
        if len(parts) != 2:
            await callback_query.message.answer("❌ Неверный формат данных.")
            return

        hashtag = parts[0]
        news_index = int(parts[1])

        data_manager = get_simple_data_manager()
        if not data_manager:
            await callback_query.message.answer("❌ Сервис временно недоступен.")
            return

        # Получаем новости с данным хештегом заново
        news_with_hashtag = data_manager._execute(
            """
            SELECT a.summary, a.sentiment, m.channel_title, m.channel_username, m.message_id, m.channel_id
            FROM analyses a
            JOIN messages m ON a.message_id = m.message_id
            WHERE a.hashtags::jsonb ? %s
            ORDER BY m.date DESC
            LIMIT 5
            """,
            (hashtag,),
        )

        if not news_with_hashtag or news_index >= len(news_with_hashtag):
            await callback_query.message.answer("❌ Новость не найдена.")
            return

        news = news_with_hashtag[news_index]
        emoji = {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
            news.get("sentiment", ""), "📰"
        )

        # Формируем подробное сообщение
        news_text = f"{emoji} Новость из трендов #{hashtag}\n\n"
        news_text += f"📝 Содержание:\n{news.get('summary', 'Нет описания')}\n\n"
        news_text += f"🎭 Тональность: {news.get('sentiment', 'Неизвестно')}\n"
        news_text += f"📺 Канал: {news.get('channel_title', 'Неизвестно')}\n"

        # Создаем ссылку на оригинальное сообщение
        message_link = None
        if news.get("channel_username") and news.get("message_id"):
            username = news["channel_username"].lstrip("@")
            message_link = f"https://t.me/{username}/{news['message_id']}"
        elif news.get("channel_id") and news.get("message_id"):
            channel_id_str = str(news["channel_id"]).lstrip("-100")
            message_link = f"https://t.me/c/{channel_id_str}/{news['message_id']}"

        # Создаем клавиатуру с кнопкой для перехода к оригиналу
        keyboard = InlineKeyboardBuilder()
        if message_link:
            keyboard.button(text="🔗 Читать оригинал", url=message_link)
        keyboard.adjust(1)

        await callback_query.message.answer(
            news_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении новости из трендов: {e}")
        await callback_query.message.answer("❌ Ошибка при получении новости.")


@dp.callback_query(F.data.startswith("news_"))
async def process_news_click(callback_query: types.CallbackQuery):
    """Обрабатывает клик по новости в дайджесте."""
    await callback_query.answer()

    if not callback_query.message:
        return

    try:
        news_index = int(callback_query.data.replace("news_", ""))

        # Получаем дайджест заново
        data_manager = get_simple_data_manager()
        if not data_manager:
            await callback_query.message.answer("❌ Сервис временно недоступен.")
            return

        digest = data_manager.get_daily_digest()
        if not digest or not digest.get("news") or news_index >= len(digest["news"]):
            await callback_query.message.answer("❌ Новость не найдена.")
            return

        news = digest["news"][news_index]
        emoji = {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
            news.get("sentiment", ""), "📰"
        )

        # Формируем подробное сообщение
        news_text = f"{emoji} Новость #{news_index + 1}\n\n"
        news_text += f"📝 Содержание:\n{news.get('summary', 'Нет описания')}\n\n"
        news_text += f"🎭 Тональность: {news.get('sentiment', 'Неизвестно')}\n"
        news_text += f"📺 Канал: {news.get('channel', 'Неизвестно')}\n"

        # Добавляем хештеги если есть
        if news.get("hashtags"):
            hashtags = news["hashtags"] if isinstance(news["hashtags"], list) else []
            if hashtags:
                hashtags_str = " ".join([f"#{tag}" for tag in hashtags[:5]])
                news_text += f"🏷️ Теги: {hashtags_str}\n"

        # Создаем клавиатуру с кнопкой для перехода к оригиналу
        keyboard = InlineKeyboardBuilder()

        if news.get("message_link"):
            keyboard.button(text="📖 Читать полную новость", url=news["message_link"])
        elif news.get("channel_username"):
            # Если нет прямой ссылки, добавляем ссылку на канал
            username = news["channel_username"].lstrip("@")
            keyboard.button(
                text=f"📱 Перейти в канал @{username}", url=f"https://t.me/{username}"
            )

        await callback_query.message.answer(
            news_text, reply_markup=keyboard.as_markup(), disable_web_page_preview=True
        )

    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка обработки клика по новости: {e}")
        await callback_query.message.answer("❌ Ошибка при открытии новости.")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке новости: {e}")
        await callback_query.message.answer("❌ Произошла ошибка.")


@dp.callback_query(F.data == "system_stats")
async def process_callback_system_stats(callback_query: types.CallbackQuery):
    """Показывает статистику системы."""
    await callback_query.answer()

    if not callback_query.message:
        return

    try:
        # Получаем статистику кэша более безопасно
        try:
            cache_stats = llm_analyzer.get_cache_stats()
            cache_info = f"💾 Кэш: {cache_stats.get('cache_size', 0)} записей"
        except Exception:
            cache_info = "💾 Кэш: недоступен"

        # Получаем количество подписчиков
        try:
            data_manager = get_simple_data_manager()
            subscribers_count = (
                len(data_manager.get_all_subscribers()) if data_manager else 0
            )
        except Exception:
            subscribers_count = 0

        # Получаем количество каналов
        try:
            channels_count = (
                len(config.channel_ids) if hasattr(config, "channel_ids") else 0
            )
        except Exception:
            channels_count = 0

        # Получаем модель
        try:
            model_name = (
                config.OLLAMA_MODEL if hasattr(config, "OLLAMA_MODEL") else "неизвестно"
            )
        except Exception:
            model_name = "неизвестно"

        # Получаем интервал
        try:
            interval = (
                config.CHECK_INTERVAL_SECONDS
                if hasattr(config, "CHECK_INTERVAL_SECONDS")
                else 60
            )
        except Exception:
            interval = 60

        stats_text = (
            "📊 Статистика системы:\n\n"
            f"🤖 Бот: Онлайн\n"
            f"📺 Каналы: {channels_count}\n"
            f"🧠 LLM модель: {str(model_name)}\n"
            f"👥 Подписчики: {subscribers_count}\n"
            f"{cache_info}\n"
            f"⏱ Интервал: {interval} сек"
        )

        await callback_query.message.answer(stats_text)
    except Exception as e:
        logger.error(f"Ошибка получения статистики системы: {e}")
        await callback_query.message.answer("❌ Ошибка получения статистики системы.")


# Команды
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Показывает справку."""
    help_text = (
        "🤖 **Справка по командам:**\n\n"
        "**Основные команды:**\n"
        "`/start` - Начать работу\n"
        "`/help` - Эта справка\n"
        "`/stats` - Статистика новостей\n"
        "`/trends` - Трендовые темы\n"
        "`/digest` - Дайджест за день\n\n"
        "**Взаимодействие с ИИ:**\n"
        "`/chat <текст>` - Общение с ИИ\n"
        "`/analyze <текст>` - Анализ текста\n"
        "`/web <запрос>` - Поиск в интернете\n\n"
        "**Управление:**\n"
        "`/subscribe` - Управление подпиской\n"
        "`/status` - Статус системы\n\n"
        "💡 **Совет:** Используйте кнопки для удобной навигации!"
    )
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    """Управление подпиской."""
    if not message.chat:
        return

    await message.answer(
        "🔔 **Настройка подписки:**\n\nВыберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_subscription_keyboard(message.chat.id),
    )


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    """Показывает настройки."""
    await message.answer(
        "⚙️ **Настройки системы:**\n\nВыберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_settings_keyboard(),
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Показывает статус системы."""
    try:
        cache_stats = llm_analyzer.get_cache_stats()
        data_manager = get_simple_data_manager()
        subscribers_count = (
            len(data_manager.get_all_subscribers()) if data_manager else 0
        )

        status_text = (
            "✅ **Статус системы:**\n\n"
            f"🤖 **Бот:** Онлайн\n"
            f"📺 **Каналы:** {', '.join(config.channel_ids[:3])}{'...' if len(config.channel_ids) > 3 else ''}\n"
            f"🧠 **LLM модель:** {config.OLLAMA_MODEL}\n"
            f"👥 **Подписчики:** {subscribers_count}\n"
            f"💾 **Кэш:** {cache_stats['cache_size']} записей ({cache_stats['cache_usage_percent']:.1f}%)\n"
            f"⏱ **Интервал проверки:** {config.CHECK_INTERVAL_SECONDS}с"
        )
        await message.answer(status_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}")
        await message.answer("❌ Ошибка при получении статуса системы.")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показывает статистику новостей."""
    await send_typing_action(message)
    try:
        data_manager = get_simple_data_manager()
        if not data_manager:
            await message.answer("❌ Сервис статистики временно недоступен.")
            return

        stats = data_manager.get_detailed_statistics()

        if not stats or stats.get("total_messages", 0) == 0:
            await message.answer(
                "🤖 **Пока нет данных для статистики.**\n\n"
                "Подождите, пока система обработает первые новости из отслеживаемых каналов.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        await message.answer(
            format_statistics_message(stats), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await handle_command_error(message, e, "получении статистики")


@dp.message(Command("chat"))
async def cmd_chat(message: types.Message, command: CommandObject):
    """Чат с ИИ."""
    if not command.args:
        await message.answer(
            "🤖 **Чат с ИИ-ассистентом**\n\n"
            "Использование: `/chat <ваш вопрос>`\n\n"
            "Пример: `/chat Расскажи о погоде`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = command.args
    await send_typing_action(message)

    progress_msg = await message.answer("🤔 Думаю...")
    response = await llm_analyzer.get_chat_response(text)

    formatted_response = f"💬 **Ответ ИИ-ассистента:**\n\n{response}"
    await progress_msg.edit_text(formatted_response, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("analyze"))
async def cmd_analyze(message: types.Message, command: CommandObject):
    """Анализ текста."""
    if not command.args:
        await message.answer(
            "🔍 **Анализ текста**\n\n"
            "Использование: `/analyze <текст для анализа>`\n\n"
            "Пример: `/analyze Сегодня отличная погода!`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text_to_analyze = command.args
    await send_typing_action(message)
    progress = await message.answer("🔍 Анализирую текст...")

    analysis = await llm_analyzer.analyze_message(text_to_analyze)
    if analysis and analysis.summary:
        hashtags_str = (
            f"`{'`, `'.join(analysis.hashtags)}`" if analysis.hashtags else "нет"
        )

        sentiment_emoji = {
            "Позитивная": "😊",
            "Негативная": "😔",
            "Нейтральная": "😐",
        }.get(analysis.sentiment, "🤔")

        response = (
            f"🤖 **Результаты анализа:**\n\n"
            f"📝 **Содержание:**\n{analysis.summary}\n\n"
            f"🎭 **Тональность:** {sentiment_emoji} {analysis.sentiment}\n\n"
            f"🏷️ **Теги:**\n{hashtags_str}"
        )
        await progress.edit_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await progress.edit_text(
            "❌ Не удалось проанализировать текст. Попробуйте еще раз."
        )


@dp.message(Command("web"))
async def cmd_web(message: types.Message, command: CommandObject):
    """Поиск в интернете."""
    if not command.args:
        await message.answer(
            "🔍 **Поиск в интернете**\n\n"
            "Использование: `/web <поисковый запрос>`\n\n"
            "Пример: `/web новости технологий`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = command.args
    await send_typing_action(message)
    progress = await message.answer(f'🔍 Ищу информацию по запросу: "{query}"...')

    search_results = await tavily_search.search(query)
    if search_results is None:
        await progress.edit_text("❌ Ошибка поиска. Проверьте настройки Tavily API.")
        return
    if not search_results:
        await progress.edit_text(f"🤷‍♂️ По запросу «{query}» ничего не найдено.")
        return

    formatted = tavily_search.format_search_results(search_results, query)

    try:
        await progress.edit_text(
            formatted, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Ошибка парсинга Markdown в /web: {e}")
        simple_formatted = tavily_search.format_search_results_simple(
            search_results, query
        )
        await progress.edit_text(simple_formatted, disable_web_page_preview=True)


@dp.message(Command("trends"))
async def cmd_trends(message: types.Message):
    """Показывает трендовые темы."""
    await send_typing_action(message)
    progress = await message.answer("📈 Анализирую тренды...")

    try:
        data_manager = get_simple_data_manager()
        if not data_manager:
            await progress.edit_text("❌ Сервис трендов временно недоступен.")
            return

        stats = data_manager.get_trends_statistics()

        if not stats or not stats.get("popular_hashtags"):
            await progress.edit_text("📊 Недостаточно данных для анализа трендов.")
            return

        trends_text = "📈 **Трендовые темы за последние дни:**\n\n"

        # Показываем хештеги без обратных кавычек
        for i, hashtag in enumerate(stats["popular_hashtags"][:5], 1):
            trends_text += f"{i}. #{hashtag}\n"

        if stats.get("top_channels"):
            trends_text += "\n📺 **Самые активные каналы:**\n"
            for channel in stats["top_channels"][:3]:
                trends_text += f"• {channel.get('title', 'Неизвестный')} ({channel.get('count', 0)} сообщений)\n"

        trends_text += "\n👇 **Кликните на хештег для поиска новостей:**"

        await progress.edit_text(trends_text, parse_mode=ParseMode.MARKDOWN)

        # Отправляем кликабельные хештеги отдельно
        hashtag_keyboard = get_hashtag_keyboard(stats["popular_hashtags"][:6])
        await message.answer(
            "🏷️ **Кликабельные хештеги:**",
            reply_markup=hashtag_keyboard.as_markup(),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Ошибка при получении трендов: {e}")
        await progress.edit_text("❌ Ошибка при анализе трендов.")


@dp.message(Command("digest"))
async def cmd_digest(message: types.Message):
    """Генерирует компактный дайджест новостей за день."""
    await send_typing_action(message)
    progress = await message.answer("📰 Готовлю дайджест новостей...")

    try:
        data_manager = get_simple_data_manager()
        if not data_manager:
            await progress.edit_text("❌ Сервис дайджеста временно недоступен.")
            return

        digest = data_manager.get_daily_digest()

        if not digest or not digest.get("news"):
            await progress.edit_text("📅 Сегодня новостей пока нет.")
            return

        # Формируем компактный дайджест
        digest_text = f"📰 **Дайджест новостей на {digest.get('date', 'сегодня')}**\n\n"

        # Статистика
        positive_count = sum(
            1 for news in digest["news"] if news.get("sentiment") == "Позитивная"
        )
        negative_count = sum(
            1 for news in digest["news"] if news.get("sentiment") == "Негативная"
        )
        neutral_count = len(digest["news"]) - positive_count - negative_count

        digest_text += f"📊 **Всего новостей:** {len(digest['news'])}\n"
        digest_text += f"😊 Позитивных: {positive_count} | 😔 Негативных: {negative_count} | 😐 Нейтральных: {neutral_count}\n\n"

        # Топ новости (краткий список)
        digest_text += "🔥 **Главные новости:**\n\n"

        for i, news in enumerate(digest["news"][:8], 1):  # Показываем топ-8
            emoji = {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
                news.get("sentiment", ""), "📰"
            )

            # Краткое описание (первые 80 символов)
            summary = news.get("summary", "Нет описания")
            short_summary = summary[:80] + "..." if len(summary) > 80 else summary

            digest_text += f"{i}. {emoji} {short_summary}\n"
            digest_text += f"   📺 {news.get('channel', 'Неизвестно')[:25]}\n\n"

        # Добавляем популярные темы
        all_hashtags = []
        for news in digest["news"]:
            if news.get("hashtags"):
                hashtags = (
                    news["hashtags"] if isinstance(news["hashtags"], list) else []
                )
                all_hashtags.extend(hashtags)

        if all_hashtags:
            # Подсчитываем популярность хештегов
            hashtag_counts = {}
            for tag in all_hashtags:
                hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1

            # Топ-5 хештегов
            top_hashtags = sorted(
                hashtag_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]
            if top_hashtags:
                digest_text += "🏷️ **Популярные темы:** "
                digest_text += " ".join([f"#{tag}" for tag, _ in top_hashtags])
                digest_text += "\n\n"

        digest_text += "👇 **Выберите новость для подробного просмотра:**"

        # Создаем клавиатуру с новостями
        keyboard = get_digest_keyboard(digest["news"][:8])

        await progress.edit_text(
            digest_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard.as_markup(),
        )

    except Exception as e:
        logger.error(f"Ошибка при создании дайджеста: {e}")
        await progress.edit_text("❌ Ошибка при создании дайджеста.")


@dp.message(F.chat.type == "private")
async def handle_non_command(message: types.Message):
    """Обрабатывает обычные сообщения как чат с ИИ."""
    if (
        message.text
        and not message.text.startswith("/")
        and not message.text
        in [
            "📊 Статистика",
            "🔔 Подписка",
            "⚙️ Настройки",
            "📈 Тренды",
            "💬 Чат с ИИ",
            "🔍 Поиск",
            "📰 Дайджест",
            "ℹ️ Помощь",
        ]
    ):
        await send_typing_action(message)
        progress_msg = await message.answer("🤔 Обрабатываю ваш запрос...")

        response = await llm_analyzer.get_chat_response(message.text)
        formatted_response = f"💬 {response}"

        await progress_msg.edit_text(formatted_response)


# Вспомогательные функции
async def send_typing_action(message: types.Message):
    """Отправляет действие 'печатает'."""
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")


async def handle_command_error(message: types.Message, error: Exception, context: str):
    """Обрабатывает ошибки команд."""
    logger.error(f"Ошибка при {context}: {error}")
    await message.answer(f"❌ Произошла ошибка при {context}. Попробуйте позже.")


def format_statistics_message(stats: Dict[str, Any]) -> str:
    """Форматирует сообщение со статистикой."""
    total_messages = stats.get("total_messages", 0)
    total_analyses = stats.get("total_analyses", 0)

    sentiment_stats = stats.get("sentiment_distribution", {})
    positive = sentiment_stats.get("Позитивная", 0)
    negative = sentiment_stats.get("Негативная", 0)
    neutral = sentiment_stats.get("Нейтральная", 0)

    top_hashtags = stats.get("popular_hashtags", [])[:5]
    top_channels = stats.get("top_channels", [])[:3]

    message_text = (
        f"📊 **Статистика новостей:**\n\n"
        f"📰 **Всего сообщений:** {total_messages}\n"
        f"🔍 **Проанализировано:** {total_analyses}\n\n"
        f"🎭 **Распределение по тональности:**\n"
        f"😊 Позитивные: {positive}\n"
        f"😔 Негативные: {negative}\n"
        f"😐 Нейтральные: {neutral}\n\n"
    )

    if top_hashtags:
        message_text += "🏷️ **Популярные темы:**\n"
        for i, tag in enumerate(top_hashtags, 1):
            message_text += f"{i}. #{tag}\n"
        message_text += "\n"

    if top_channels:
        message_text += "📺 **Активные каналы:**\n"
        for channel in top_channels:
            title = channel.get("title", "Неизвестный")[:30]
            count = channel.get("count", 0)
            message_text += f"• {title}: {count} сообщений\n"

    return message_text


def get_hashtag_keyboard(hashtags: List[str]) -> InlineKeyboardBuilder:
    """Создает клавиатуру с кликабельными хештегами."""
    builder = InlineKeyboardBuilder()
    for hashtag in hashtags[:6]:  # Максимум 6 хештегов
        builder.button(text=f"#{hashtag}", callback_data=f"hashtag_{hashtag}")
    builder.adjust(2)  # По 2 кнопки в ряд
    return builder


def get_hashtag_news_keyboard(
    news_list: List[Dict[str, Any]], hashtag: str
) -> InlineKeyboardBuilder:
    """Создает клавиатуру для новостей по хештегу."""
    builder = InlineKeyboardBuilder()

    for i, news in enumerate(news_list, 1):
        emoji = {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
            news.get("sentiment", ""), "📰"
        )

        # Создаем кнопку для перехода к новости
        button_text = f"{emoji} {i}. Читать"
        builder.button(
            text=button_text,
            callback_data=f"hashtag_news_{hashtag}_{i-1}",  # Индекс новости (0-based)
        )

    builder.adjust(1)  # По 1 кнопке в ряд
    return builder


def get_digest_keyboard(news_list: List[Dict[str, Any]]) -> InlineKeyboardBuilder:
    """Создает клавиатуру для дайджеста новостей."""
    builder = InlineKeyboardBuilder()

    for i, news in enumerate(news_list, 1):
        emoji = {"Позитивная": "😊", "Негативная": "😔", "Нейтральная": "😐"}.get(
            news.get("sentiment", ""), "📰"
        )

        # Создаем короткий текст для кнопки
        button_text = f"{emoji} {i}"

        builder.button(
            text=button_text, callback_data=f"news_{i-1}"  # Индекс новости (0-based)
        )

    builder.adjust(4)  # По 4 кнопки в ряд
    return builder


@dp.channel_post()
async def handle_channel_post(message: types.Message):
    """Обрабатывает сообщения из каналов."""
    pass  # Обработка происходит в monitoring_service.py
