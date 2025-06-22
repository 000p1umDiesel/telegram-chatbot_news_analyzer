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
from functools import lru_cache
from collections import OrderedDict
import time

# Импортируем новые утилиты
from utils.error_handler import retry_with_backoff, RetryConfig, ErrorCategory
from utils.performance import performance_timer
from utils.constants import (
    DEFAULT_CACHE_SIZE,
    DEFAULT_CACHE_TTL_SECONDS,
    MAX_CONCURRENT_REQUESTS,
    MAX_SUMMARY_LENGTH,
    MAX_TEXT_LENGTH_FOR_ANALYSIS,
    HASHTAG_CATEGORIES,
)


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


class LRUCacheWithTTL:
    """LRU кэш с поддержкой TTL (Time To Live)."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self.timestamps = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None

        # Проверяем TTL
        if time.time() - self.timestamps[key] > self.ttl_seconds:
            self._remove(key)
            return None

        # Перемещаем в конец (недавно использованный)
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                # Удаляем самый старый элемент
                oldest_key = next(iter(self.cache))
                self._remove(oldest_key)

        self.cache[key] = value
        self.timestamps[key] = time.time()

    def _remove(self, key: str):
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]

    def clear(self):
        self.cache.clear()
        self.timestamps.clear()

    def size(self) -> int:
        return len(self.cache)


class OllamaAnalyzer:
    def __init__(
        self,
        model: str = config.OLLAMA_MODEL,
        base_url: str = config.OLLAMA_BASE_URL,
        max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
        cache_size: int = DEFAULT_CACHE_SIZE,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
    ):
        self.logger = get_logger()
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Улучшенный кэш с LRU и TTL
        self.analysis_cache = LRUCacheWithTTL(cache_size, cache_ttl)
        self.cache_size = cache_size

        try:
            # C июня-2025 `pull` убрали из LangChain-обёртки.
            # Гарантируем наличие модели отдельным вызовом python-клиента.
            try:
                import ollama as _ollama

                _ollama.pull(model)  # загрузка, если нужно
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
        if len(message_text) > MAX_TEXT_LENGTH_FOR_ANALYSIS:
            message_text = message_text[:MAX_TEXT_LENGTH_FOR_ANALYSIS] + "..."

        # Используем константы для категорий хештегов
        hashtag_categories = ", ".join(HASHTAG_CATEGORIES)

        return f"""
Проанализируй новость и предоставь СТРОГО JSON-ответ.

Формат ответа:
{{"summary": "краткое содержание", "sentiment": "тональность", "hashtags": ["тег1", "тег2"]}}

Правила:
1. summary: Краткое содержание (максимум {MAX_SUMMARY_LENGTH} символов)
2. sentiment: ТОЛЬКО одно из: "Позитивная", "Негативная", "Нейтральная"
3. hashtags: 3-5 тегов из категорий: {hashtag_categories}

ПРИМЕРЫ:
Текст: "Центробанк повысил ключевую ставку до 21%"
{{"summary": "ЦБ РФ повысил ключевую ставку до рекордных 21%", "sentiment": "Негативная", "hashtags": ["экономика", "финансы", "центробанк"]}}

Текст: "Российские ученые создали новый материал для космоса"
{{"summary": "Российские ученые разработали инновационный материал для космической промышленности", "sentiment": "Позитивная", "hashtags": ["наука_и_технологии", "космос", "инновации"]}}

Текст: {message_text}

JSON:"""

    @retry_with_backoff(
        config=RetryConfig(max_attempts=3, base_delay=1.0),
        exceptions=(Exception,),
        category=ErrorCategory.LLM,
    )
    async def analyze_message(self, message_text: str) -> Optional[NewsAnalysis]:
        async with performance_timer("llm_analysis"):
            # Проверяем кэш
            cache_key = self._get_cache_key(message_text)
            cached_result = self.analysis_cache.get(cache_key)
            if cached_result is not None:
                self.logger.debug("Результат анализа взят из кэша")
                return cached_result

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
                        self.logger.warning(
                            f"Не найден JSON в ответе: {response[:200]}..."
                        )
                        return None

                    data = json.loads(match.group(0))
                    data["hashtags"] = self._clean_and_validate_hashtags(
                        data.get("hashtags", [])
                    )

                    analysis = NewsAnalysis(**data)

                    # Сохраняем в кэш
                    self.analysis_cache.put(cache_key, analysis)

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
            "cache_size": self.analysis_cache.size(),
            "max_cache_size": self.cache_size,
            "cache_usage_percent": (self.analysis_cache.size() / self.cache_size) * 100,
        }

    def clear_cache(self):
        """Очищает кэш."""
        self.analysis_cache.clear()
        self.logger.info("Кэш анализа очищен")
