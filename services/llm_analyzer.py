# llm_analyzer.py
import json
import re
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
        self, model: str = config.OLLAMA_MODEL, base_url: str = config.OLLAMA_BASE_URL
    ):
        self.logger = get_logger()
        try:
            # C июня-2025 `pull` убрали из LangChain-обёртки.
            # Гарантируем наличие модели отдельным вызовом python-клиента.
            try:
                import ollama as _ollama

                _ollama.pull(model, base_url=base_url)  # загрузка, если нужно
            except Exception as pull_err:
                self.logger.warning("Не удалось выполнить ollama pull: %s", pull_err)

            self.llm = Ollama(model=model, base_url=base_url)

            # Быстрая проверка соединения с моделью
            self.llm.invoke("Hi", temperature=0.0)
            self.logger.info("OllamaAnalyzer инициализирован с моделью %s", model)
        except Exception as e:
            self.logger.error(f"Не удалось инициализировать Ollama: {e}")
            raise

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

    async def analyze_message(self, message_text: str) -> Optional[NewsAnalysis]:
        prompt = f"""
Проанализируй новость и предоставь СТРОГО JSON-ответ со следующими ключами: "summary", "sentiment", "hashtags".

**Правила анализа:**
1.  **summary**: Сделай краткое, но емкое содержание новости на русском языке.
2.  **sentiment**: Определи тональность. Ответ должен быть ОДНИМ из этих слов: 'Позитивная', 'Негативная', 'Нейтральная'.
3.  **hashtags**: Создай список из 3-5 УНИКАЛЬНЫХ и ОЧЕНЬ ОБЩИХ хештегов.
    - Хештеги должны быть на русском языке и отражать одну из следующих категорий:
      'политика', 'экономика', 'происшествия', 'спорт', 'наука_и_технологии', 'культура', 'общество', 'другие_страны'.
    - Используй ТОЛЬКО предложенные категории. Не придумывай свои.
    - Хештеги НЕ должны дублироваться.
    - Выбери наиболее подходящие категории для данной новости.

**Текст новости для анализа:**
{message_text}
"""
        try:
            response = await self.llm.ainvoke(prompt)
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if not match:
                self.logger.warning(f"Не найден JSON в ответе: {response}")
                return None
            data = json.loads(match.group(0))
            data["hashtags"] = self._clean_and_validate_hashtags(
                data.get("hashtags", [])
            )
            return NewsAnalysis(**data)
        except Exception as e:
            self.logger.error(f"Ошибка анализа: {e}")
            return None

    async def get_chat_response(self, text: str) -> str:
        prompt = f"Ты — дружелюбный ассистент. Ответь кратко и по существу.\nСообщение: {text}"
        try:
            return (await self.llm.ainvoke(prompt)).strip()
        except Exception as e:
            self.logger.error(f"Ошибка LLM-ответа: {e}")
            return "Извините, произошла ошибка при обработке запроса."
