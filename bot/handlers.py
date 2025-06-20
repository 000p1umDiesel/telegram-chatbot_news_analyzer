# handlers.py
from aiogram import Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import data_manager, llm_analyzer, tavily_search
import config
from logger import get_logger

logger = get_logger()

dp = Dispatcher()


def get_subscription_keyboard(chat_id: int):
    builder = InlineKeyboardBuilder()
    if data_manager.is_subscriber(chat_id):
        builder.button(text="✅ Отписаться от уведомлений", callback_data="unsubscribe")
    else:
        builder.button(text="🔔 Подписаться на уведомления", callback_data="subscribe")
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение и предлагает подписаться на рассылку."""
    if not message.chat:
        logger.warning("Получена команда /start без информации о чате.")
        return
    chat_id = message.chat.id
    welcome_text = (
        "Привет! Я бот для анализа новостей и работы с LLM.\n\n"
        "Чтобы посмотреть доступные команды, нажми /help.\n\n"
        "Вы можете подписаться на уведомления, чтобы получать актуальные новости."
    )
    await message.answer(welcome_text, reply_markup=get_subscription_keyboard(chat_id))


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


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "**Доступные команды:**\n"
        "/help - Показать это сообщение\n"
        "/status - Показать статус системы\n"
        "/stats - Показать статистику анализа\n"
        "/subscribe - Управление подпиской на уведомления\n"
        "/chat `<текст>` - Пообщаться с LLM\n"
        "/web `<запрос>` - Поиск в интернете\n"
        "/analyze `<текст>` - Проанализировать произвольный текст"
    )
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    if not message.chat:
        logger.warning("Получена команда /subscribe без информации о чате.")
        return
    await message.answer(
        "Настройте подписку для этого чата:",
        reply_markup=get_subscription_keyboard(message.chat.id),
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    status_text = (
        "✅ **Статус системы:**\n\n"
        "• **Бот:** Онлайн\n"
        f"• **Мониторинг канала:** `{config.TELEGRAM_CHANNEL_ID}`\n"
        f"• **LLM модель:** `{config.OLLAMA_MODEL}`"
    )
    await message.answer(status_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        stats = data_manager.get_statistics()
        if not stats or stats.get("total_messages", 0) == 0:
            await message.answer("😔 Пока нет данных для статистики.")
            return

        sentiment_counts = stats.get("sentiment_counts", {})
        hashtags = stats.get("popular_hashtags", [])
        hashtags_str = f"`{'`, `'.join(hashtags)}`" if hashtags else "нет"

        response = (
            f"📊 **Статистика анализа:**\n\n"
            f"📝 **Всего:** {stats.get('total_messages', 0)}\n"
            f"📈 **Позитивных:** {sentiment_counts.get('Позитивная', 0)}\n"
            f"📉 **Негативных:** {sentiment_counts.get('Негативная', 0)}\n"
            f"➖ **Нейтральных:** {sentiment_counts.get('Нейтральная', 0)}\n\n"
            f"🏷️ **Топ-10 хештегов:**\n"
            f"{hashtags_str}"
        )
        await message.answer(response, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await message.answer("❌ Ошибка при получении статистики.")


@dp.message(Command("chat"))
async def cmd_chat(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Напишите что-нибудь после команды /chat")
        return
    text = command.args
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    response = await llm_analyzer.get_chat_response(text)
    await message.answer(response)


@dp.message(Command("analyze"))
async def cmd_analyze(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Укажите текст: /analyze <текст>")
        return
    text_to_analyze = command.args
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer("🔍 Анализирую...")
    analysis = await llm_analyzer.analyze_message(text_to_analyze)
    if analysis and analysis.summary:
        hashtags_str = (
            f"`{'`, `'.join(analysis.hashtags)}`" if analysis.hashtags else "нет"
        )
        response = (
            f"📊 **Результаты анализа:**\n\n"
            f"**Содержание:**\n{analysis.summary}\n\n"
            f"**Тональность:** {analysis.sentiment}\n\n"
            f"**Хештеги:**\n{hashtags_str}"
        )
        await progress.edit_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await progress.edit_text("❌ Не удалось проанализировать текст.")


@dp.message(Command("web"))
async def cmd_web(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Укажите запрос: /web <запрос>")
        return
    query = command.args
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress = await message.answer(f'🔍 Ищу информацию по запросу: "{query}"...')
    search_results = await tavily_search.search(query)
    if search_results is None:
        await progress.edit_text("❌ Ошибка поиска.")
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
    if message.text and not message.text.startswith("/"):
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await llm_analyzer.get_chat_response(message.text)
        await message.answer(response)
