# analyzer.py

"""Ollama-based news analyzer (moved from services.llm_analyzer)."""

# llm_analyzer.py
import json
import re
import hashlib
import asyncio
from typing import Optional, List, Dict, Any
from langchain_community.llms import Ollama
from pydantic import BaseModel, Field
from logger import get_logger
from core.config import settings as config
from collections import OrderedDict
import time
from jinja2 import Template  # for safe prompt construction
import services  # for global data_manager

from utils.error_handler import retry_with_backoff, RetryConfig, ErrorCategory
from utils.performance import performance_timer
from pipeline.cleaning import truncate_text, clean_and_validate_hashtags


class NewsAnalysis(BaseModel):
    summary: str = Field(description="Краткое содержание новости на русском языке.")
    sentiment: str = Field(
        description="Тональность: 'Позитивная', 'Негативная' или 'Нейтральная'."
    )
    hashtags: List[str] = Field(
        description="Список из 3-5 уникальных и обобщенных хештегов."
    )

    def format_hashtags(self) -> str:  # noqa: D401
        if not self.hashtags:
            return "Хештеги не сгенерированы."
        return " ".join(f"#{tag}" for tag in self.hashtags)


logger = get_logger()


class LRUCacheWithTTL:
    """LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        if time.time() - self.timestamps[key] > self.ttl_seconds:
            self._remove(key)
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            self._remove(oldest_key)
        self.cache[key] = value
        self.timestamps[key] = time.time()

    def _remove(self, key: str):
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)

    def clear(self):  # noqa: D401
        self.cache.clear()
        self.timestamps.clear()

    def size(self) -> int:  # noqa: D401
        return len(self.cache)


class OllamaAnalyzer:
    def __init__(
        self,
        model: str = config.OLLAMA_MODEL,
        base_url: str = config.OLLAMA_BASE_URL,
        max_concurrent_requests: int = config.MAX_CONCURRENT_REQUESTS,
        cache_size: int = config.DEFAULT_CACHE_SIZE,
        cache_ttl: int = config.DEFAULT_CACHE_TTL_SECONDS,
    ):
        self.logger = get_logger()
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.analysis_cache = LRUCacheWithTTL(cache_size, cache_ttl)
        self.cache_size = cache_size

        try:
            self.llm = Ollama(
                model=model,
                base_url=base_url,
                temperature=0.1,
                top_p=0.9,
                repeat_penalty=1.1,
            )

            # Флаг для отслеживания проверки модели
            self._model_checked = False

            self.logger.info("OllamaAnalyzer инициализирован с моделью %s", model)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Не удалось инициализировать Ollama: %s", exc)
            raise

    async def _check_model_availability(self, model: str):
        """Проверяет доступность модели асинхронно."""
        try:
            import ollama as _ollama

            await asyncio.get_event_loop().run_in_executor(None, _ollama.pull, model)

            # Тестовый запрос для проверки работоспособности
            test_response = await self.llm.ainvoke("Test", temperature=0.0)
            self.logger.info("Модель %s успешно загружена и протестирована", model)
        except Exception as e:
            self.logger.warning("Не удалось проверить модель %s: %s", model, e)

    # ----------------------------------------------- internal helpers ----
    def _get_cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _get_optimized_prompt(self, message_text: str) -> str:
        safe_text = truncate_text(message_text, config.MAX_TEXT_LENGTH_FOR_ANALYSIS)
        hashtag_categories = ", ".join(config.HASHTAG_CATEGORIES)

        template = Template(
            """
Проанализируй новость и предоставь СТРОГО JSON-ответ.

Формат ответа:
{"summary": "краткое содержание", "sentiment": "тональность", "hashtags": ["тег1", "тег2"]}

Правила:
1. summary: Краткое содержание (максимум {{ max_summary }} символов)
2. sentiment: ТОЛЬКО одно из: "Позитивная", "Негативная", "Нейтральная"
3. hashtags: 3-5 тегов из категорий: {{ categories }}

ПРИМЕРЫ:
Текст: "Центробанк повысил ключевую ставку до 21%"
{"summary": "ЦБ РФ повысил ключевую ставку до рекордных 21%", "sentiment": "Негативная", "hashtags": ["экономика", "финансы", "центробанк"]}

Текст: "Российские ученые создали новый материал для космоса"
{"summary": "Российские ученые разработали инновационный материал для космической промышленности", "sentiment": "Позитивная", "hashtags": ["наука_и_технологии", "космос", "инновации"]}

Текст: {{ text }}

JSON:
"""
        )
        return template.render(
            max_summary=config.MAX_SUMMARY_LENGTH,
            categories=hashtag_categories,
            text=safe_text,
        )

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Улучшенный парсинг JSON из ответа LLM."""
        try:
            # Ищем JSON блок в ответе
            json_patterns = [
                r'\{[^{}]*"summary"[^{}]*"sentiment"[^{}]*"hashtags"[^{}]*\}',
                r'\{[^{}]*"hashtags"[^{}]*"sentiment"[^{}]*"summary"[^{}]*\}',
                r'\{.*?"summary".*?"sentiment".*?"hashtags".*?\}',
                r"\{.*?\}",
            ]

            for pattern in json_patterns:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(0))
                        # Проверяем, что есть все необходимые поля
                        if all(
                            key in data for key in ["summary", "sentiment", "hashtags"]
                        ):
                            return data
                    except json.JSONDecodeError:
                        continue

            # Если не нашли валидный JSON, логируем ошибку
            self.logger.warning("Не найден валидный JSON в ответе: %s", response[:200])
            return None

        except Exception as e:
            self.logger.error("Ошибка парсинга JSON: %s", e)
            return None

    # ----------------------------------------- public API ---------------
    @retry_with_backoff(
        config=RetryConfig(max_attempts=3, base_delay=1.0),
        exceptions=(Exception,),
        category=ErrorCategory.LLM,
    )
    async def analyze_message(self, message_text: str) -> Optional[NewsAnalysis]:
        async with performance_timer("llm_analysis"):
            # Проверяем модель при первом вызове
            if not self._model_checked:
                await self._check_model_availability(config.OLLAMA_MODEL)
                self._model_checked = True

            cache_key = self._get_cache_key(message_text)
            cached = self.analysis_cache.get(cache_key)
            if cached is not None:
                self.logger.debug("Результат анализа взят из кэша")
                return cached

            async with self.semaphore:
                prompt = self._get_optimized_prompt(message_text)
                start = time.perf_counter()
                try:
                    response = await self.llm.ainvoke(prompt)
                    latency_ms = int((time.perf_counter() - start) * 1000)

                    # Парсим JSON из ответа
                    data = self._parse_json_response(response)
                    if not data:
                        return None

                    # Очищаем и валидируем хештеги
                    data["hashtags"] = clean_and_validate_hashtags(
                        data.get("hashtags", [])
                    )

                    analysis = NewsAnalysis(**data)
                    self.analysis_cache.put(cache_key, analysis)

                    # логируем вызов LLM в БД (fire-and-forget)
                    if services.data_manager and hasattr(
                        services.data_manager, "log_llm_call"
                    ):
                        try:
                            services.data_manager.log_llm_call(
                                prompt_tokens=len(prompt.split()),
                                completion_tokens=len(response.split()),
                                latency_ms=latency_ms,
                                model=config.OLLAMA_MODEL,
                            )
                        except Exception as log_err:
                            self.logger.debug(
                                "Не удалось записать лог LLM: %s", log_err
                            )

                    return analysis

                except Exception as e:
                    self.logger.error("Ошибка анализа сообщения: %s", e)
                    return None

    def get_cache_stats(self) -> Dict[str, Any]:  # noqa: D401
        cache_size = self.analysis_cache.size()
        return {
            "cache_size": cache_size,
            "max_cache_size": self.cache_size,
            "cache_usage_percent": (cache_size / self.cache_size) * 100,
        }

    def clear_cache(self):  # noqa: D401
        self.analysis_cache.clear()
        self.logger.info("Кэш анализатора очищен")

    async def get_chat_response(self, message_text: str) -> str:
        """Получает ответ от LLM для чата с пользователем."""
        try:
            # Проверяем модель при первом вызове
            if not self._model_checked:
                await self._check_model_availability(config.OLLAMA_MODEL)
                self._model_checked = True

            # Простой промпт для чата
            chat_prompt = f"""Ты полезный ИИ-ассистент. Отвечай кратко и по делу на русском языке.

Пользователь: {message_text}

Ассистент:"""

            async with self.semaphore:
                response = await self.llm.ainvoke(chat_prompt)
                return str(response).strip()

        except Exception as e:
            self.logger.error(f"Ошибка получения ответа чата: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса."
