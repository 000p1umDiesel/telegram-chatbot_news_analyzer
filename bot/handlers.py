# handlers.py
from aiogram import Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from services import data_manager, llm_analyzer, tavily_search
import config
from logger import get_logger
from typing import Dict, Any

logger = get_logger()

dp = Dispatcher()


def get_main_keyboard():
    """Создает основную клавиатуру с одной кнопкой подписки."""
    builder = ReplyKeyboardBuilder()
    builder.add(
        types.KeyboardButton(text="🔔 Подписка"),
    )
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_subscription_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    if data_manager.is_subscriber(chat_id):
        builder.button(text="🔕 Отписаться от уведомлений", callback_data="unsubscribe")
        builder.button(text="📋 Мои подписки", callback_data="my_subscriptions")
    else:
        builder.button(text="🔔 Подписаться на уведомления", callback_data="subscribe")
    builder.adjust(1)
    return builder.as_markup()


def get_settings_keyboard():
    """Создает клавиатуру настроек."""
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="📊 Статистика системы", callback_data="system_stats"
        ),
        types.InlineKeyboardButton(text="🗑 Очистить кэш", callback_data="clear_cache"),
        types.InlineKeyboardButton(
            text="📋 Мои подписки", callback_data="my_subscriptions"
        ),
    )
    builder.adjust(1)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение и предлагает подписаться на рассылку."""
    if not message.chat:
        logger.warning("Получена команда /start без информации о чате.")
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
        "• 🔍 Поиск информации в интернете\n\n"
        "📋 **Для настройки используйте команду** `/help`\n\n"
        "👇 **Начните с подписки на уведомления:**"
    )

    await message.answer(
        welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard()
    )

    # Показываем кнопки подписки
    await message.answer(
        "🔔 **Управление подпиской:**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_subscription_keyboard(chat_id),
    )


@dp.message(F.text == "🔔 Подписка")
async def handle_subscription_button(message: types.Message):
    """Обрабатывает нажатие кнопки Подписка."""
    await cmd_subscribe(message)


@dp.callback_query(lambda c: c.data == "subscribe")
async def process_callback_subscribe(callback_query: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Подписаться'."""
    if not callback_query.message:
        await callback_query.answer("Не удалось определить чат.", show_alert=True)
        return
    chat_id = callback_query.message.chat.id
    if data_manager.is_subscriber(chat_id):
        await callback_query.answer("Этот чат уже подписан!")
    else:
        data_manager.add_subscriber(chat_id)
        await callback_query.answer("✅ Чат успешно подписан на уведомления!")
        await callback_query.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(chat_id)
        )


@dp.callback_query(lambda c: c.data == "unsubscribe")
async def process_callback_unsubscribe(callback_query: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Отписаться'."""
    if not callback_query.message:
        await callback_query.answer("Не удалось определить чат.", show_alert=True)
        return
    chat_id = callback_query.message.chat.id
    if not data_manager.is_subscriber(chat_id):
        await callback_query.answer("Этот чат и так не подписан.")
    else:
        data_manager.remove_subscriber(chat_id)
        await callback_query.answer("✅ Чат успешно отписан от уведомлений.")
        await callback_query.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(chat_id)
        )


@dp.callback_query(lambda c: c.data == "my_subscriptions")
async def process_callback_my_subscriptions(callback_query: types.CallbackQuery):
    """Показывает информацию о подписках пользователя."""
    if not callback_query.message:
        await callback_query.answer("Ошибка обработки запроса.", show_alert=True)
        return

    chat_id = callback_query.message.chat.id
    is_subscribed = data_manager.is_subscriber(chat_id)

    subscription_info = (
        f"📋 **Ваши подписки:**\n\n"
        f"🔔 Уведомления: {'✅ Включены' if is_subscribed else '❌ Отключены'}\n"
        f"📺 Отслеживаемые каналы: {len(config.TELEGRAM_CHANNEL_IDS)}\n"
        f"⏱ Интервал проверки: {config.CHECK_INTERVAL_SECONDS} сек."
    )

    await callback_query.answer()
    await callback_query.message.answer(
        subscription_info, parse_mode=ParseMode.MARKDOWN
    )


@dp.callback_query(lambda c: c.data == "clear_cache")
async def process_callback_clear_cache(callback_query: types.CallbackQuery):
    """Очищает кэш анализатора."""
    try:
        cache_stats_before = llm_analyzer.get_cache_stats()
        llm_analyzer.clear_cache()

        await callback_query.answer(
            f"✅ Кэш очищен! Освобождено {cache_stats_before['cache_size']} записей.",
            show_alert=True,
        )
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша: {e}")
        await callback_query.answer("❌ Ошибка при очистке кэша.", show_alert=True)


@dp.callback_query(lambda c: c.data == "system_stats")
async def process_callback_system_stats(callback_query: types.CallbackQuery):
    """Показывает системную статистику."""
    try:
        # Получаем статистику кэша
        cache_stats = llm_analyzer.get_cache_stats()

        # Получаем статистику подписчиков
        subscribers_count = len(data_manager.get_all_subscribers())

        system_info = (
            f"📊 **Системная статистика:**\n\n"
            f"👥 Подписчики: {subscribers_count}\n"
            f"💾 Кэш: {cache_stats['cache_size']}/{cache_stats['max_cache_size']} "
            f"({cache_stats['cache_usage_percent']:.1f}%)\n"
            f"📺 Каналы: {len(config.TELEGRAM_CHANNEL_IDS)}\n"
            f"🤖 Модель: {config.OLLAMA_MODEL}\n"
            f"🔗 Ollama: {config.OLLAMA_BASE_URL}"
        )

        await callback_query.answer()
        await callback_query.message.answer(system_info, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при получении системной статистики: {e}")
        await callback_query.answer(
            "❌ Ошибка при получении статистики.", show_alert=True
        )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🆘 **Справка по командам:**\n\n"
        "**Основные команды:**\n"
        "`/start` - Начать работу с ботом\n"
        "`/help` - Показать эту справку\n"
        "`/stats` - Статистика анализа новостей\n"
        "`/subscribe` - Управление подпиской\n"
        "`/notifications` - Настройки уведомлений\n\n"
        "**Работа с ИИ:**\n"
        "`/chat <текст>` - Пообщаться с ИИ-ассистентом\n"
        "`/analyze <текст>` - Проанализировать текст\n"
        "`/web <запрос>` - Поиск в интернете\n\n"
        "**Системные команды:**\n"
        "`/status` - Статус системы\n\n"
        "💡 **Совет:** Используйте кнопки ниже для быстрого доступа к функциям!"
    )
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    if not message.chat:
        logger.warning("Получена команда /subscribe без информации о чате.")
        return
    await message.answer(
        "🔔 **Настройка подписки:**\n\nВыберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_subscription_keyboard(message.chat.id),
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    try:
        # Получаем статистику системы
        cache_stats = llm_analyzer.get_cache_stats()
        subscribers_count = len(data_manager.get_all_subscribers())

        status_text = (
            "✅ **Статус системы:**\n\n"
            f"🤖 **Бот:** Онлайн\n"
            f"📺 **Каналы:** {', '.join(config.TELEGRAM_CHANNEL_IDS[:3])}{'...' if len(config.TELEGRAM_CHANNEL_IDS) > 3 else ''}\n"
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
    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        stats = data_manager.get_statistics()
        if not stats or stats.get("total_messages", 0) == 0:
            await message.answer(
                "😔 **Пока нет данных для статистики.**\n\n"
                "Подождите, пока система обработает первые новости из отслеживаемых каналов.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        sentiment_counts = stats.get("sentiment_counts", {})
        hashtags = stats.get("popular_hashtags", [])

        # Создаем красивую статистику
        total = stats.get("total_messages", 0)
        positive = sentiment_counts.get("Позитивная", 0)
        negative = sentiment_counts.get("Негативная", 0)
        neutral = sentiment_counts.get("Нейтральная", 0)

        # Вычисляем проценты
        pos_pct = (positive / total * 100) if total > 0 else 0
        neg_pct = (negative / total * 100) if total > 0 else 0
        neu_pct = (neutral / total * 100) if total > 0 else 0

        hashtags_str = f"`{'`, `'.join(hashtags[:10])}`" if hashtags else "нет данных"

        response = (
            f"📊 **Статистика анализа новостей:**\n\n"
            f"📝 **Всего обработано:** {total}\n\n"
            f"🎯 **Анализ тональности:**\n"
            f"📈 Позитивных: {positive} ({pos_pct:.1f}%)\n"
            f"📉 Негативных: {negative} ({neg_pct:.1f}%)\n"
            f"➖ Нейтральных: {neutral} ({neu_pct:.1f}%)\n\n"
            f"🏷️ **Популярные теги:**\n"
            f"{hashtags_str}"
        )
        await message.answer(response, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await message.answer("❌ Ошибка при получении статистики.")


@dp.message(Command("chat"))
async def cmd_chat(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer(
            "💬 **Чат с ИИ-ассистентом**\n\n"
            "Использование: `/chat <ваш вопрос>`\n\n"
            "Пример: `/chat Расскажи о погоде`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    text = command.args
    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    progress_msg = await message.answer("🤔 Думаю...")
    response = await llm_analyzer.get_chat_response(text)

    formatted_response = f"💬 **Ответ ИИ-ассистента:**\n\n{response}"
    await progress_msg.edit_text(formatted_response, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("analyze"))
async def cmd_analyze(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer(
            "🔍 **Анализ текста**\n\n"
            "Использование: `/analyze <текст для анализа>`\n\n"
            "Пример: `/analyze Сегодня отличная погода!`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    text_to_analyze = command.args
    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer("🔍 Анализирую текст...")

    analysis = await llm_analyzer.analyze_message(text_to_analyze)
    if analysis and analysis.summary:
        hashtags_str = (
            f"`{'`, `'.join(analysis.hashtags)}`" if analysis.hashtags else "нет"
        )

        # Эмодзи для тональности
        sentiment_emoji = {
            "Позитивная": "😊",
            "Негативная": "😔",
            "Нейтральная": "😐",
        }.get(analysis.sentiment, "🤔")

        response = (
            f"📊 **Результаты анализа:**\n\n"
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
    if not command.args:
        await message.answer(
            "🔍 **Поиск в интернете**\n\n"
            "Использование: `/web <поисковый запрос>`\n\n"
            "Пример: `/web новости технологий`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    query = command.args
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer(f'🔍 Ищу информацию по запросу: "{query}"...')

    search_results = await tavily_search.search(query)
    if search_results is None:
        await progress.edit_text("❌ Ошибка поиска. Проверьте настройки Tavily API.")
        return
    if not search_results:
        await progress.edit_text(f"🤷‍♂️ По запросу «{query}» ничего не найдено.")
        return
    formatted = tavily_search.format_search_results(search_results, query)
    await progress.edit_text(
        formatted, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


@dp.message(F.chat.type == "private")
async def handle_non_command(message: types.Message):
    """Обрабатывает обычные сообщения как чат с ИИ."""
    if message.text and not message.text.startswith("/"):
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Показываем индикатор обработки
        progress_msg = await message.answer("🤔 Обрабатываю ваш запрос...")

        response = await llm_analyzer.get_chat_response(message.text)
        formatted_response = f"💬 {response}"

        await progress_msg.edit_text(formatted_response)


@dp.message(Command("trends"))
async def cmd_trends(message: types.Message):
    """Показывает трендовые темы."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer("📈 Анализирую тренды...")

    try:
        # Простой анализ трендов на основе статистики
        stats = data_manager.get_extended_statistics()

        if not stats.get("popular_hashtags"):
            await progress.edit_text("📊 Недостаточно данных для анализа трендов.")
            return

        # Формируем отчет по трендам
        trends_text = "📈 **Трендовые темы за последние дни:**\n\n"

        for i, hashtag in enumerate(stats["popular_hashtags"][:5], 1):
            trends_text += f"{i}. `#{hashtag}`\n"

        # Добавляем информацию о топ-каналах
        if stats.get("top_channels"):
            trends_text += "\n📺 **Самые активные каналы:**\n"
            for channel in stats["top_channels"][:3]:
                trends_text += f"• {channel['channel_title']} ({channel['message_count']} сообщений)\n"

        await progress.edit_text(trends_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Ошибка при получении трендов: {e}")
        await progress.edit_text("❌ Ошибка при анализе трендов.")


@dp.message(Command("digest"))
async def cmd_digest(message: types.Message):
    """Генерирует дайджест новостей за день."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer("📰 Готовлю дайджест новостей...")

    try:
        from datetime import date

        today = date.today().isoformat()

        with data_manager._lock, data_manager.conn:
            # Получаем новости за сегодня
            cur = data_manager.conn.execute(
                """
                SELECT a.summary, a.sentiment, a.hashtags, m.channel_title
                FROM analyses a
                JOIN messages m ON a.message_id = m.message_id
                WHERE DATE(m.date) = ?
                ORDER BY m.date DESC
                LIMIT 10
            """,
                (today,),
            )

            news_today = cur.fetchall()

        if not news_today:
            await progress.edit_text("📅 Сегодня новостей пока нет.")
            return

        # Группируем по тональности
        positive_news = []
        negative_news = []
        neutral_news = []

        for news in news_today:
            if news["sentiment"] == "Позитивная":
                positive_news.append(news)
            elif news["sentiment"] == "Негативная":
                negative_news.append(news)
            else:
                neutral_news.append(news)

        # Формируем дайджест
        digest_text = f"📰 **Дайджест новостей на {today}**\n\n"
        digest_text += f"📊 **Всего новостей:** {len(news_today)}\n\n"

        if positive_news:
            digest_text += f"😊 **Позитивные ({len(positive_news)}):**\n"
            for news in positive_news[:3]:
                summary = (
                    news["summary"][:80] + "..."
                    if len(news["summary"]) > 80
                    else news["summary"]
                )
                digest_text += f"• {summary}\n"
            digest_text += "\n"

        if negative_news:
            digest_text += f"😔 **Негативные ({len(negative_news)}):**\n"
            for news in negative_news[:3]:
                summary = (
                    news["summary"][:80] + "..."
                    if len(news["summary"]) > 80
                    else news["summary"]
                )
                digest_text += f"• {summary}\n"
            digest_text += "\n"

        if neutral_news:
            digest_text += f"😐 **Нейтральные ({len(neutral_news)}):**\n"
            for news in neutral_news[:2]:
                summary = (
                    news["summary"][:80] + "..."
                    if len(news["summary"]) > 80
                    else news["summary"]
                )
                digest_text += f"• {summary}\n"

        await progress.edit_text(digest_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Ошибка при создании дайджеста: {e}")
        await progress.edit_text("❌ Ошибка при создании дайджеста.")


@dp.message(Command("health"))
async def cmd_health(message: types.Message):
    """Показывает состояние здоровья системы."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer("🏥 Проверяю состояние системы...")

    try:
        from services.simple_health_check import simple_health_check

        stats = simple_health_check.get_basic_stats()

        # Формируем простой отчет
        health_report = {
            "status": "healthy" if stats["database_ok"] else "warning",
            "current_metrics": {
                "uptime_hours": stats["uptime_hours"],
                "database_status": "healthy" if stats["database_ok"] else "unhealthy",
                "active_subscribers": stats["subscribers_count"],
            },
        }

        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🔴",
            "error": "❌",
        }.get(health_report.get("status", "unknown"), "❓")

        health_text = f"{status_emoji} **Состояние системы: {health_report.get('status', 'неизвестно').upper()}**\n\n"

        if health_report.get("current_metrics"):
            metrics = health_report["current_metrics"]
            health_text += "📊 **Текущие метрики:**\n"
            health_text += f"🖥 CPU: {metrics.get('cpu_usage', 0):.1f}%\n"
            health_text += f"💾 Память: {metrics.get('memory_usage', 0):.1f}%\n"
            health_text += f"💿 Диск: {metrics.get('disk_usage', 0):.1f}%\n"
            health_text += f"🧠 Кэш LLM: {metrics.get('cache_usage', 0):.1f}%\n"
            health_text += f"👥 Подписчики: {metrics.get('active_subscribers', 0)}\n"
            health_text += f"🤖 Ollama: {metrics.get('ollama_status', 'неизвестно')}\n"
            health_text += f"🗄 БД: {metrics.get('database_status', 'неизвестно')}\n\n"

        if health_report.get("uptime_hours"):
            hours = health_report["uptime_hours"]
            health_text += f"⏱ **Время работы:** {hours:.1f} ч\n\n"

        if health_report.get("warnings"):
            health_text += "⚠️ **Предупреждения:**\n"
            for warning in health_report["warnings"]:
                health_text += f"• {warning}\n"
            health_text += "\n"

        if health_report.get("issues"):
            health_text += "🔴 **Проблемы:**\n"
            for issue in health_report["issues"]:
                health_text += f"• {issue}\n"

        await progress.edit_text(health_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Ошибка при получении состояния здоровья: {e}")
        await progress.edit_text("❌ Ошибка при проверке состояния системы.")


@dp.message(Command("quick"))
async def cmd_quick(message: types.Message, command: CommandObject):
    """Быстрые команды: /quick stats, /quick clear, /quick health."""
    if not command.args:
        help_text = (
            "⚡ **Быстрые команды:**\n\n"
            "`/quick stats` - Быстрая статистика\n"
            "`/quick health` - Состояние системы\n"
            "`/quick clear` - Очистить кэш\n"
            "`/quick trends` - Трендовые темы\n"
            "`/quick digest` - Дайджест за сегодня"
        )
        await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)
        return

    action = command.args.lower()

    if action == "stats":
        await cmd_stats(message)
    elif action == "health":
        await cmd_health(message)
    elif action == "clear":
        try:
            cache_stats = llm_analyzer.get_cache_stats()
            llm_analyzer.clear_cache()
            await message.answer(
                f"✅ Кэш очищен! Освобождено {cache_stats['cache_size']} записей."
            )
        except Exception as e:
            await message.answer("❌ Ошибка при очистке кэша.")
    elif action == "trends":
        await cmd_trends(message)
    elif action == "digest":
        await cmd_digest(message)
    else:
        await message.answer(
            "❓ Неизвестная быстрая команда. Используйте `/quick` для справки."
        )


# Обработчики кнопок удалены, так как остается только кнопка "Подписка"


@dp.message(Command("notifications"))
async def cmd_notifications(message: types.Message, command: CommandObject):
    """Управление настройками уведомлений."""
    if not message.chat:
        return

    chat_id = message.chat.id

    if not command.args:
        # Проверяем подписку
        is_subscribed = data_manager.is_subscriber(chat_id)

        if not is_subscribed:
            help_text = (
                "🔔 **Настройки уведомлений:**\n\n"
                "❌ **Вы не подписаны на уведомления!**\n\n"
                "Чтобы получать уведомления, сначала подпишитесь:\n"
                "• Нажмите кнопку 🔔 **Подписка** ниже\n"
                "• Или используйте команду `/subscribe`\n\n"
                "После подписки вы сможете настроить фильтры уведомлений."
            )
            await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)
            return

        # Показываем текущие настройки для подписчиков
        settings = data_manager.get_user_settings(chat_id)

        notifications_status = (
            "🔔 Включены"
            if settings.get("notification_enabled", True)
            else "🔕 Отключены"
        )

        sentiment_names = {
            "all": "Все новости",
            "positive": "Только позитивные",
            "negative": "Только негативные",
            "neutral": "Только нейтральные",
        }
        sentiment_filter = sentiment_names.get(
            settings.get("sentiment_filter", "all"), "Все новости"
        )

        help_text = (
            f"🔔 **Настройки уведомлений:**\n\n"
            f"✅ **Вы подписаны на уведомления**\n\n"
            f"**Текущие настройки:**\n"
            f"• Уведомления: {notifications_status}\n"
            f"• Фильтр тональности: {sentiment_filter}\n\n"
            f"**Команды для изменения:**\n"
            f"`/notifications on` - Включить уведомления\n"
            f"`/notifications off` - Отключить уведомления\n"
            f"`/notifications all` - Все новости\n"
            f"`/notifications positive` - Только позитивные\n"
            f"`/notifications negative` - Только негативные\n"
            f"`/notifications neutral` - Только нейтральные\n\n"
            f"**Пример:** `/notifications positive`"
        )

        await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)
        return

    args = command.args.lower()

    # Обработка команд
    if args == "on":
        success = data_manager.update_user_settings(
            chat_id, {"notification_enabled": True}
        )
        if success:
            await message.answer(
                "🔔 **Уведомления включены!**", parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer("❌ Ошибка при сохранении настроек")

    elif args == "off":
        success = data_manager.update_user_settings(
            chat_id, {"notification_enabled": False}
        )
        if success:
            await message.answer(
                "🔕 **Уведомления отключены!**", parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer("❌ Ошибка при сохранении настроек")

    elif args in ["all", "positive", "negative", "neutral"]:
        success = data_manager.update_user_settings(chat_id, {"sentiment_filter": args})
        if success:
            filter_names = {
                "all": "все новости",
                "positive": "только позитивные новости",
                "negative": "только негативные новости",
                "neutral": "только нейтральные новости",
            }
            await message.answer(
                f"🎯 **Фильтр установлен:** {filter_names[args]}",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await message.answer("❌ Ошибка при сохранении настроек")
    else:
        await message.answer(
            "❓ **Неизвестная команда.**\n\n"
            "Используйте `/notifications` для справки.",
            parse_mode=ParseMode.MARKDOWN,
        )
