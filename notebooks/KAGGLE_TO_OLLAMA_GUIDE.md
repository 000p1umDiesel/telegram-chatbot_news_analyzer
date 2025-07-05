# 🔄 Интеграция модели из Kaggle в Ollama

Пошаговое руководство по загрузке дообученной в Kaggle модели в Ollama для использования в вашем проекте.

## 📋 Содержание

1. [Подготовка модели в Kaggle](#1-подготовка-модели-в-kaggle)
2. [Скачивание модели](#2-скачивание-модели)
3. [Создание Ollama модели](#3-создание-ollama-модели)
4. [Интеграция в проект](#4-интеграция-в-проект)
5. [Тестирование](#5-тестирование)

---

## 1. 📚 Подготовка модели в Kaggle

### Обучение модели

Используйте созданный `kaggle_finetuning.ipynb` notebook в Kaggle. Он автоматически:

1. **Загружает данные** из вашего dataset
2. **Обучает модель** с LoRA
3. **Объединяет LoRA** с базовой моделью
4. **Создает архив** `saiga_hashtag_model_for_ollama.zip`
5. **Подготавливает Modelfile** для Ollama

После завершения обучения скачайте готовый архив из раздела Output в Kaggle.

---

## 2. 📥 Скачивание модели

### Через Kaggle Output

1. В Kaggle notebook перейдите в раздел **Output**
2. Скачайте файл `saiga_hashtag_model_for_ollama.zip`
3. Распакуйте архив на локальной машине

**Примечание:** Архив уже содержит всё необходимое: модель, токенизатор, Modelfile и инструкции.

---

## 3. 🚀 Создание Ollama модели

### Создание модели в Ollama

Архив уже содержит готовый Modelfile, просто выполните команды:

```bash
# Распакуйте архив и перейдите в папку
unzip saiga_hashtag_model_for_ollama.zip
cd final_model_for_ollama

# Создайте модель в Ollama
ollama create saiga-hashtag-pro -f Modelfile

# Проверьте создание
ollama list
```

---

## 4. 🔧 Интеграция в проект

### Обновление analyzer.py

Обновите файл `services/llm/analyzer.py`:

```python
from ollama import AsyncClient
from core.config import get_settings

settings = get_settings()

class LLMAnalyzer:
    def __init__(self):
        self.ollama_client = AsyncClient(host=settings.OLLAMA_BASE_URL)
        
        # Модели для разных задач
        self.models = {
            'original': settings.OLLAMA_MODEL,  # ilyagusev/saiga_llama3
            'hashtag_enhanced': 'saiga-hashtag-pro'  # Ваша дообученная модель
        }
        
        # Флаг использования улучшенной модели
        self.use_enhanced_hashtag_model = True
    
    async def generate_hashtags(self, text: str) -> str:
        """Генерирует хештеги с выбором модели"""
        
        # Выбираем модель
        model_name = (
            self.models['hashtag_enhanced'] 
            if self.use_enhanced_hashtag_model 
            else self.models['original']
        )
        
        try:
            response = await self.ollama_client.generate(
                model=model_name,
                prompt=f"Сгенерируй хештеги для новости: {text}",
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 50
                }
            )
            
            hashtags = response['response'].strip()
            
            # Очистка и форматирование
            hashtags = self._clean_hashtags(hashtags)
            
            return hashtags
            
        except Exception as e:
            # Fallback на оригинальную модель
            if self.use_enhanced_hashtag_model:
                print(f"⚠️ Ошибка enhanced модели, переключаемся на оригинальную: {e}")
                response = await self.ollama_client.generate(
                    model=self.models['original'],
                    prompt=f"Сгенерируй хештеги для новости: {text}"
                )
                return self._clean_hashtags(response['response'])
            else:
                raise e
    
    def _clean_hashtags(self, hashtags: str) -> str:
        """Очищает и форматирует хештеги"""
        # Убираем лишние символы
        hashtags = hashtags.replace('#', '').strip()
        
        # Разделяем и очищаем
        tags = [tag.strip() for tag in hashtags.split(',')]
        tags = [tag for tag in tags if tag and len(tag) > 2]
        
        # Ограничиваем количество
        tags = tags[:5]
        
        return ', '.join(tags)
    
    async def switch_model(self, use_enhanced: bool = True):
        """Переключает между моделями"""
        self.use_enhanced_hashtag_model = use_enhanced
        model_name = (
            self.models['hashtag_enhanced'] 
            if use_enhanced 
            else self.models['original']
        )
        print(f"🔄 Переключено на модель: {model_name}")
```

### Добавление команды переключения в бота

В `bot/handlers.py` добавьте команду:

```python
@dp.message(Command("switch_model"))
async def switch_model_command(message: types.Message):
    """Переключает между моделями генерации хештегов"""
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply(
            "Использование: /switch_model enhanced|original\n"
            "enhanced - дообученная модель\n"
            "original - оригинальная модель"
        )
        return
    
    model_type = args[1].lower()
    
    if model_type == "enhanced":
        await analyzer.switch_model(use_enhanced=True)
        await message.reply("✅ Переключено на дообученную модель")
    elif model_type == "original":
        await analyzer.switch_model(use_enhanced=False)
        await message.reply("✅ Переключено на оригинальную модель")
    else:
        await message.reply("❌ Неверный тип модели. Используйте: enhanced или original")
```

---

## 5. 🧪 Тестирование

### Команды для тестирования

```bash
# Проверка списка моделей
ollama list

# Тестирование модели напрямую
ollama run saiga-hashtag-pro "Сгенерируй хештеги для новости: Центральный банк повысил ключевую ставку"

# Проверка размера модели
ollama show saiga-hashtag-pro
```

### Тестирование в проекте

Создайте тестовый скрипт `test_enhanced_model.py`:

```python
import asyncio
from services.llm.analyzer import LLMAnalyzer

async def test_models():
    analyzer = LLMAnalyzer()
    
    test_text = "Центральный банк России повысил ключевую ставку до 21% годовых"
    
    print("🧪 Тестирование моделей...")
    print(f"📰 Текст: {test_text}")
    
    # Тест оригинальной модели
    await analyzer.switch_model(use_enhanced=False)
    original_hashtags = await analyzer.generate_hashtags(test_text)
    print(f"🔵 Оригинальная: {original_hashtags}")
    
    # Тест дообученной модели
    await analyzer.switch_model(use_enhanced=True)
    enhanced_hashtags = await analyzer.generate_hashtags(test_text)
    print(f"🟢 Дообученная: {enhanced_hashtags}")

if __name__ == "__main__":
    asyncio.run(test_models())
```

Запустите тест:

```bash
python test_enhanced_model.py
```

---

## 6. 📊 Мониторинг и сравнение

### Добавление логирования

В `analyzer.py` добавьте логирование использования моделей:

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    def __init__(self):
        # ... существующий код ...
        self.model_usage_stats = {
            'original': 0,
            'enhanced': 0
        }
    
    async def generate_hashtags(self, text: str) -> str:
        model_type = 'enhanced' if self.use_enhanced_hashtag_model else 'original'
        self.model_usage_stats[model_type] += 1
        
        start_time = datetime.now()
        
        # ... генерация хештегов ...
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Model: {model_type}, Duration: {duration:.2f}s, Text length: {len(text)}")
        
        return hashtags
    
    def get_usage_stats(self):
        """Возвращает статистику использования моделей"""
        total = sum(self.model_usage_stats.values())
        if total == 0:
            return self.model_usage_stats
        
        return {
            'original': {
                'count': self.model_usage_stats['original'],
                'percentage': self.model_usage_stats['original'] / total * 100
            },
            'enhanced': {
                'count': self.model_usage_stats['enhanced'],
                'percentage': self.model_usage_stats['enhanced'] / total * 100
            },
            'total': total
        }
```

### Команда статистики в боте

```python
@dp.message(Command("model_stats"))
async def model_stats_command(message: types.Message):
    """Показывает статистику использования моделей"""
    
    stats = analyzer.get_usage_stats()
    
    response = "📊 Статистика использования моделей:\n\n"
    response += f"🔵 Оригинальная: {stats['original']['count']} ({stats['original']['percentage']:.1f}%)\n"
    response += f"🟢 Дообученная: {stats['enhanced']['count']} ({stats['enhanced']['percentage']:.1f}%)\n"
    response += f"📈 Всего запросов: {stats['total']}"
    
    await message.reply(response)
```

---

## 7. 🚀 Дополнительные возможности

### A/B тестирование

```python
import random

class LLMAnalyzer:
    def __init__(self):
        # ... существующий код ...
        self.ab_test_enabled = False
        self.ab_test_ratio = 0.5  # 50% на каждую модель
    
    async def generate_hashtags_with_ab_test(self, text: str) -> dict:
        """Генерирует хештеги с A/B тестированием"""
        
        if not self.ab_test_enabled:
            hashtags = await self.generate_hashtags(text)
            return {
                'hashtags': hashtags,
                'model_used': 'enhanced' if self.use_enhanced_hashtag_model else 'original'
            }
        
        # A/B тест
        use_enhanced = random.random() < self.ab_test_ratio
        
        # Временно переключаем модель
        original_setting = self.use_enhanced_hashtag_model
        self.use_enhanced_hashtag_model = use_enhanced
        
        hashtags = await self.generate_hashtags(text)
        
        # Возвращаем исходную настройку
        self.use_enhanced_hashtag_model = original_setting
        
        return {
            'hashtags': hashtags,
            'model_used': 'enhanced' if use_enhanced else 'original',
            'ab_test': True
        }
```

### Автоматическое переключение по качеству

```python
class LLMAnalyzer:
    def __init__(self):
        # ... существующий код ...
        self.quality_threshold = 0.7
        self.auto_switch_enabled = False
    
    async def generate_hashtags_with_quality_check(self, text: str) -> str:
        """Генерирует хештеги с проверкой качества"""
        
        if not self.auto_switch_enabled:
            return await self.generate_hashtags(text)
        
        # Пробуем дообученную модель
        enhanced_hashtags = await self._generate_with_model(text, use_enhanced=True)
        quality_score = self._calculate_quality_score(text, enhanced_hashtags)
        
        if quality_score >= self.quality_threshold:
            return enhanced_hashtags
        else:
            # Fallback на оригинальную
            logger.warning(f"Low quality score: {quality_score}, switching to original model")
            return await self._generate_with_model(text, use_enhanced=False)
    
    def _calculate_quality_score(self, text: str, hashtags: str) -> float:
        """Простая оценка качества хештегов"""
        # Можно улучшить эту логику
        
        tags = hashtags.split(',')
        
        # Базовые проверки
        if len(tags) < 2 or len(tags) > 6:
            return 0.3
        
        # Проверка на релевантность (простая)
        text_lower = text.lower()
        relevant_count = 0
        
        for tag in tags:
            tag_clean = tag.strip().lower()
            if any(word in text_lower for word in tag_clean.split()):
                relevant_count += 1
        
        relevance_score = relevant_count / len(tags)
        
        # Проверка на разнообразие
        unique_words = set()
        for tag in tags:
            unique_words.update(tag.strip().lower().split())
        
        diversity_score = len(unique_words) / (len(tags) * 2)  # Примерная метрика
        
        return (relevance_score + diversity_score) / 2
```

---

## 8. 🎯 Итоговая схема интеграции

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     Kaggle      │────│  Скачивание      │────│   Локальная     │
│   (Обучение)    │    │   модели         │    │    машина       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │     Ollama      │
                                               │ (saiga-hashtag- │
                                               │      pro)       │
                                               └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Ваш проект     │
                                               │  (analyzer.py)  │
                                               └─────────────────┘
```

## 🎉 Результат

После выполнения всех шагов у вас будет:

✅ **Дообученная модель в Ollama** под именем `saiga-hashtag-pro`  
✅ **Интеграция в существующий проект** с возможностью переключения  
✅ **Команды управления** через Telegram бота  
✅ **Мониторинг и статистика** использования моделей  
✅ **A/B тестирование** для сравнения качества  
✅ **Автоматическое переключение** по качеству (опционально)

Теперь ваша система может использовать как оригинальную модель, так и специально дообученную для генерации хештегов! 