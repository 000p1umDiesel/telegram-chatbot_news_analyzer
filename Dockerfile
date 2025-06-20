# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости, необходимые для некоторых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Обновляем pip
RUN pip install --no-cache-dir --upgrade pip

# Копируем файл с зависимостями и устанавливаем их
# Это кэширует слой с зависимостями, ускоряя последующие сборки
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код проекта
COPY . .

# Создаем пользователя без прав root для безопасности
RUN useradd -ms /bin/bash appuser

# Создаем и назначаем права на директории для данных, логов и сессий
RUN mkdir -p /app/data /app/logs /app/.sessions && \
    chown -R appuser:appuser /app

# Переключаемся на пользователя без прав root
USER appuser

# Запускаем бота через main.py
CMD ["python", "main.py"] 