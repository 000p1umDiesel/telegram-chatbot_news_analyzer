# llm_analyzer.py
import json
import re
import hashlib
import asyncio
from typing import Optional, List, Dict, Any
from langchain_community.llms import Ollama
from pydantic import BaseModel, Field
from logger import get_logger
import config


class NewsAnalysis(BaseModel):
    summary: str = Field(description="Краткое содержание новости на русском языке.")
    sentiment: str = Field(
        description="Тональность: 'Позитивная', 'Негативная' или 'Нейтральная'."
    )
    hashtags: List[str] = Field(
        description="Список из 3-5 уникальных и обобщенных хештегов."
    )

    def format_hashtags(self) -> str:
        if not self.hashtags:
            return "Хештеги не сгенерированы."
        return " ".join(f"#{tag}" for tag in self.hashtags)


logger = get_logger()


class OllamaAnalyzer:
    def __init__(
        self,
        model: str = config.OLLAMA_MODEL,
        base_url: str = config.OLLAMA_BASE_URL,
        max_concurrent_requests: int = 2,
        cache_size: int = 1000,
    ):
        self.logger = get_logger()
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Простой кэш для результатов анализа
        self.analysis_cache: Dict[str, NewsAnalysis] = {}
        self.cache_size = cache_size

        try:
            # C июня-2025 `pull` убрали из LangChain-обёртки.
            # Гарантируем наличие модели отдельным вызовом python-клиента.
            try:
                import ollama as _ollama

                _ollama.pull(model, base_url=base_url)  # загрузка, если нужно
            except Exception as pull_err:
                self.logger.warning("Не удалось выполнить ollama pull: %s", pull_err)

            self.llm = Ollama(
                model=model,
                base_url=base_url,
                # Оптимизированные параметры для стабильности
                temperature=0.1,  # Низкая температура для более стабильных результатов
                top_p=0.9,
                repeat_penalty=1.1,
            )

            # Быстрая проверка соединения с моделью
            self.llm.invoke("Hi", temperature=0.0)
            self.logger.info("OllamaAnalyzer инициализирован с моделью %s", model)
        except Exception as e:
            self.logger.error(f"Не удалось инициализировать Ollama: {e}")
            raise

    def _get_cache_key(self, text: str) -> str:
        """Генерирует ключ кэша для текста."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _manage_cache_size(self):
        """Управляет размером кэша, удаляя старые записи."""
        if len(self.analysis_cache) >= self.cache_size:
            # Удаляем 20% старых записей (простая стратегия FIFO)
            keys_to_remove = list(self.analysis_cache.keys())[: self.cache_size // 5]
            for key in keys_to_remove:
                del self.analysis_cache[key]

    def _clean_and_validate_hashtags(self, hashtags: List[Any]) -> List[str]:
        cleaned = []
        if not isinstance(hashtags, list):
            return []
        for tag in hashtags:
            if not isinstance(tag, str):
                continue
            cleaned_tag = re.sub(r"[^\w\s]", "", tag).strip().replace(" ", "_")
            if cleaned_tag:
                cleaned.append(cleaned_tag.lower())
        return list(dict.fromkeys(cleaned))

    def _get_optimized_prompt(self, message_text: str) -> str:
        """Возвращает оптимизированный промпт для анализа."""
        # Обрезаем слишком длинные тексты для экономии токенов
        max_text_length = 2000
        if len(message_text) > max_text_length:
            message_text = message_text[:max_text_length] + "..."

        return f"""
Проанализируй новость и предоставь СТРОГО JSON-ответ.

Формат ответа:
{{"summary": "краткое содержание", "sentiment": "тональность", "hashtags": ["тег1", "тег2"]}}

Правила:
1. summary: Краткое содержание (максимум 200 символов)
2. sentiment: ТОЛЬКО одно из: "Позитивная", "Негативная", "Нейтральная"
3. hashtags: 3-5 тегов из категорий: политика, экономика, происшествия, спорт, наука_и_технологии, культура, общество, другие_страны

Текст: {message_text}

JSON:"""

    async def analyze_message(self, message_text: str) -> Optional[NewsAnalysis]:
        # Проверяем кэш
        cache_key = self._get_cache_key(message_text)
        if cache_key in self.analysis_cache:
            self.logger.debug("Результат анализа взят из кэша")
            return self.analysis_cache[cache_key]

        async with self.semaphore:  # Ограничиваем количество одновременных запросов
            prompt = self._get_optimized_prompt(message_text)

            try:
                response = await self.llm.ainvoke(prompt)

                # Ищем JSON в ответе
                match = re.search(r'\{[^}]*"summary"[^}]*\}', response, re.DOTALL)
                if not match:
                    # Пробуем найти любой JSON
                    match = re.search(r"\{.*\}", response, re.DOTALL)

                if not match:
                    self.logger.warning(f"Не найден JSON в ответе: {response[:200]}...")
                    return None

                data = json.loads(match.group(0))
                data["hashtags"] = self._clean_and_validate_hashtags(
                    data.get("hashtags", [])
                )

                analysis = NewsAnalysis(**data)

                # Сохраняем в кэш
                self._manage_cache_size()
                self.analysis_cache[cache_key] = analysis

                return analysis

            except json.JSONDecodeError as e:
                self.logger.error(f"Ошибка парсинга JSON: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Ошибка анализа: {e}")
                return None

    async def get_chat_response(self, text: str) -> str:
        async with self.semaphore:
            prompt = f"""Ты — дружелюбный ассистент. Отвечай кратко и по существу на русском языке.

Вопрос: {text}

Ответ:"""
            try:
                response = await self.llm.ainvoke(prompt)
                return response.strip()
            except Exception as e:
                self.logger.error(f"Ошибка LLM-ответа: {e}")
                return "Извините, произошла ошибка при обработке запроса."

    def get_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэша."""
        return {
            "cache_size": len(self.analysis_cache),
            "max_cache_size": self.cache_size,
            "cache_usage_percent": (len(self.analysis_cache) / self.cache_size) * 100,
        }

    def clear_cache(self):
        """Очищает кэш."""
        self.analysis_cache.clear()
        self.logger.info("Кэш анализа очищен")
