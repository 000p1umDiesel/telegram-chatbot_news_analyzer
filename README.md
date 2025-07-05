# 🤖 Telegram News Analyzer

Система анализа новостей из Telegram каналов с использованием ИИ. Бот автоматически мониторит указанные каналы, анализирует новости с помощью LLM модели и отправляет уведомления подписчикам.

## ✨ Основные возможности

- 📰 **Автоматический мониторинг** Telegram каналов
- 🧠 **ИИ-анализ новостей** с определением тональности и тематики
- 🏷️ **Автоматическая генерация хештегов** по категориям
- 🔔 **Персонализированные уведомления** с фильтрацией
- 💬 **Интерактивный бот** для общения с ИИ
- 🔍 **Веб-поиск** через Tavily API
- 📊 **Статистика и аналитика**
- 🐳 **Docker поддержка** для легкого развертывания

## 🏗️ Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Telegram API   │────│  Channel Monitor │────│   LLM Analyzer  │
│   (Telethon)    │    │                  │    │    (Ollama)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Telegram Bot   │────│   Notification   │────│   PostgreSQL    │
│   (aiogram)     │    │     Manager      │    │    Database     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

<details>
<summary>🖼️ <b>Современная схема (Mermaid)</b> (кликабельно)</summary>

```mermaid
flowchart TD
    subgraph Telegram
        A1["Telegram API"]
        A2["Telegram Channels"]
        A3["Telegram Bot (aiogram)"]
    end
    subgraph Core
        B1["Channel Monitor"]
        B2["LLM Analyzer (Ollama)"]
        B3["Notification Manager"]
        B4["PostgreSQL DB"]
    end
    subgraph External
        C1["Tavily Search API"]
        C2["Ollama Server"]
    end

    A2-->|Мониторинг|B1
    B1-->|Анализ новости|B2
    B2-->|Результаты|B3
    B3-->|Уведомления|A3
    B3-->|Сохранение|B4
    A3-->|/chat, /analyze|B2
    A3-->|/web|C1
    B2-->|LLM запрос|C2
```

</details>

## 🚀 Быстрый старт

### 1. Клонирование и установка

```bash
git clone <repository-url>
cd telegram-chatbot_news_analyzer
```

### 2. Установка зависимостей

```bash
# Все зависимости (production + development)
pip install -r requirements.txt
```

### 3. Настройка окружения

Скопируйте файл примера и заполните реальными данными:

```bash
cp env.example .env
```

Отредактируйте `.env` файл:

```bash
# Telegram API (получить на https://my.telegram.org/apps)
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+7XXXXXXXXX

# Telegram Bot (получить у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Каналы для мониторинга
TELEGRAM_CHANNEL_IDS=channel1,channel2,channel3

# База данных
POSTGRES_DSN=postgresql://username:password@localhost:5432/news_analyzer

# LLM (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=ilyagusev/saiga_llama3

# Поиск (опционально)
TAVILY_API_KEY=your_tavily_api_key_here
```

### 4. Инициализация Telegram сессии

**ВАЖНО**: Перед первым запуском выполните инициализацию:

```bash
python init_session.py
```

Следуйте инструкциям для авторизации в Telegram.

### 5. Запуск с Docker (рекомендуется)

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot
```

### 6. Запуск локально

```bash
# Убедитесь, что PostgreSQL и Ollama запущены
python main.py
```

## 📋 Требования

### Системные требования

- **Python 3.11+**
- **PostgreSQL 13+**
- **Ollama** с моделью `ilyagusev/saiga_llama3`
- **Docker & Docker Compose** (для контейнерного запуска)

### API ключи

1. **Telegram API**: https://my.telegram.org/apps
2. **Telegram Bot**: @BotFather в Telegram
3. **Tavily Search** (опционально): https://app.tavily.com/

## 🔧 Конфигурация

### 🚀 Единая конфигурация

Все настройки системы находятся в файле `core/config.py`. Настройка выполняется двумя способами:

#### 1. Через переменные окружения (.env файл)

```env
# Основные настройки
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+7XXXXXXXXXX

# Каналы для мониторинга
TELEGRAM_CHANNEL_IDS=meduzalive,lentach,rbc_news

# Интервалы (секунды)
CHECK_INTERVAL_SECONDS=60
ERROR_RETRY_SECONDS=300

# LLM настройки
OLLAMA_MODEL=ilyagusev/saiga_llama3
OLLAMA_BASE_URL=http://localhost:11434
```

#### 2. Изменение значений по умолчанию в core/config.py

Откройте файл `core/config.py` и измените значения по умолчанию для нужных параметров. Каждый параметр имеет подробное описание на русском языке.

### 📄 Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| `TELEGRAM_API_ID` | ID приложения Telegram | ✅ |
| `TELEGRAM_API_HASH` | Hash приложения Telegram | ✅ |
| `TELEGRAM_PHONE` | Номер телефона для авторизации | ✅ |
| `TELEGRAM_BOT_TOKEN` | Токен бота | ✅ |
| `TELEGRAM_CHANNEL_IDS` | Каналы для мониторинга | ✅ |
| `POSTGRES_DSN` | Строка подключения к БД | ✅ |
| `OLLAMA_BASE_URL` | URL Ollama сервера | ✅ |
| `OLLAMA_MODEL` | Название LLM модели | ✅ |
| `TAVILY_API_KEY` | Ключ для веб-поиска | ❌ |

### Настройка каналов

Каналы можно указывать в разных форматах:

```bash
# По username
TELEGRAM_CHANNEL_IDS=lentach,meduzalive,rbc_news

# По ID
TELEGRAM_CHANNEL_IDS=-1001234567890,-1001234567891

# Смешанный формат
TELEGRAM_CHANNEL_IDS=lentach,-1001234567890,@meduzalive
```

## 🤖 Команды бота

### Основные команды

- `/start` - Начать работу с ботом
- `/help` - Справка по командам
- `/subscribe` - Управление подпиской на уведомления
- `/stats` - Статистика анализа новостей
- `/status` - Статус системы

### Работа с ИИ

- `/chat <текст>` - Пообщаться с ИИ-ассистентом
- `/analyze <текст>` - Проанализировать текст
- `/web <запрос>` - Поиск в интернете

### Дополнительные команды

- `/trends` - Популярные темы и хештеги
- `/digest` - Дайджест новостей за период
- `/health` - Подробная информация о системе

## 🐳 Docker

### Сервисы

- **bot** - Основное приложение
- **postgres** - База данных PostgreSQL
- **ollama** - LLM сервер

### Управление

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart bot

# Логи
docker-compose logs -f bot

# Статус
docker-compose ps
```

## 🔍 Мониторинг и логи

### Логи

Логи сохраняются в папку `logs/` с ротацией по дням:

```
logs/
├── telelytics_2024-01-15.log
├── telelytics_2024-01-16.log
└── ...
```

### Healthcheck

Система включает встроенные проверки здоровья:

- ✅ Статус подключения к БД
- ✅ Доступность Ollama
- ✅ Статистика обработки сообщений
- ✅ Количество активных подписчиков

## 🛠️ Разработка

### Структура проекта

```
telegram-chatbot_news_analyzer/
├── bot/                    # Telegram бот
│   ├── __init__.py
│   ├── handlers.py         # Обработчики команд
│   └── notifier.py         # Система уведомлений
├── core/                   # Основная конфигурация
│   └── config.py           # Настройки (pydantic)
├── services/               # Бизнес-логика
│   ├── llm/               # LLM анализатор
│   ├── db/                # Работа с БД
│   ├── telegram_monitor.py # Мониторинг каналов
│   └── tavily_search.py   # Веб-поиск
├── utils/                  # Утилиты
│   ├── error_handler.py    # Обработка ошибок
│   └── performance.py      # Мониторинг производительности
├── pipeline/               # Обработка данных
│   └── cleaning.py         # Очистка текста
├── evaluation/             # Тестирование
├── main.py                 # Точка входа
└── init_session.py         # Инициализация Telegram
```

### Запуск тестов

```bash
# Все тесты
python -m pytest evaluation/

# Конкретный тест
python evaluation/performance_test.py
```

### Линтинг

```bash
# Проверка кода
ruff check .
mypy .

# Форматирование
black .
```

## 🔧 Исправленные проблемы

В последней версии исправлены следующие критические проблемы:

### ✅ Критические исправления

1. **Создан `telegram_monitor`** - реализован полноценный мониторинг каналов через Telethon
2. **Унифицирована конфигурация** - удален дублирующий `config.py`, используется только `core/config.py`
3. **Очищен `env.example`** - убраны реальные токены и API ключи
4. **Исправлен healthcheck** - заменен на проверку процесса Python
5. **Исправлена логика `main.py`** - добавлен мониторинг каналов, улучшена обработка ошибок

### ✅ Важные улучшения

1. **Унифицированы константы** - убрано дублирование между файлами
2. **Улучшен парсинг JSON** - более надежное извлечение данных из LLM ответов
3. **Исправлены async/sync проблемы** - корректная работа с асинхронными вызовами
4. **Улучшена обработка ошибок** - добавлена категоризация и retry механизмы
5. **Убраны неиспользуемые импорты** - очищен код

### ✅ Дополнительные исправления

1. **Добавлен `telethon` в зависимости**
2. **Создан скрипт инициализации** - `init_session.py` для настройки Telegram
3. **Улучшена типизация** - добавлены проверки на None
4. **Обновлена документация** - актуальные инструкции по запуску

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи в папке `logs/`
2. Убедитесь, что все зависимости установлены
3. Проверьте правильность настройки `.env`
4. Выполните инициализацию Telegram сессии

## 📄 Лицензия

MIT License

