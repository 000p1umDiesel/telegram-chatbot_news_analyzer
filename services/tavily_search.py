import aiohttp
from typing import List, Dict, Any, Optional
from logger import get_logger
import config

logger = get_logger()


class TavilySearch:
    def __init__(self):
        self.api_key = config.TAVILY_API_KEY
        if not self.api_key:
            logger.warning("TAVILY_API_KEY не установлен. Поиск будет недоступен.")
            self.api_key = None
            return

        self.base_url = "https://api.tavily.com/search"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def search(
        self, query: str, max_results: int = 3
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Выполняет поиск через Tavily API.
        """
        if not self.api_key:
            logger.warning("Tavily API недоступен - API ключ не установлен")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("results", [])
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Ошибка при поиске: {response.status} - {error_text}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Ошибка при выполнении поиска: {e}")
            return None

    def format_search_results(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        Форматирует результаты поиска в читаемый вид.
        """
        if not results:
            return "По вашему запросу ничего не найдено."

        def escape_markdown(text: str) -> str:
            """Экранирует специальные символы Markdown."""
            # Список символов, которые нужно экранировать в MarkdownV2
            special_chars = [
                "_",
                "*",
                "[",
                "]",
                "(",
                ")",
                "~",
                "`",
                ">",
                "#",
                "+",
                "-",
                "=",
                "|",
                "{",
                "}",
                ".",
                "!",
            ]
            for char in special_chars:
                text = text.replace(char, f"\\{char}")
            return text

        # Экранируем query для безопасности
        safe_query = escape_markdown(query)
        formatted_results = [f"🔍 *Результаты поиска для* '{safe_query}':\n"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Без заголовка")
            url = result.get("url", "")
            content = result.get("content", "Нет описания")

            # Обрезаем контент для краткости
            if len(content) > 200:
                content = content[:197] + "..."

            # Экранируем все текстовые данные
            safe_title = escape_markdown(title)
            safe_content = escape_markdown(content)

            formatted_results.append(f"📌 *{safe_title}*\n🔗 {url}\n📝 {safe_content}")

        return "\n\n".join(formatted_results)

    def format_search_results_simple(
        self, results: List[Dict[str, Any]], query: str
    ) -> str:
        """
        Форматирует результаты поиска в простой текстовый вид без Markdown.
        """
        if not results:
            return "По вашему запросу ничего не найдено."

        formatted_results = [f"🔍 Результаты поиска для '{query}':\n"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Без заголовка")
            url = result.get("url", "")
            content = result.get("content", "Нет описания")

            # Обрезаем контент для краткости
            if len(content) > 200:
                content = content[:197] + "..."

            formatted_results.append(f"📌 {title}\n🔗 {url}\n📝 {content}")

        return "\n\n".join(formatted_results)
