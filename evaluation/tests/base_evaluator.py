#!/usr/bin/env python3
"""
Базовый класс для всех тестов системы анализа новостей.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor


class BaseEvaluator:
    """Базовый класс для всех evaluation тестов."""

    def __init__(self, db_config: dict = None):
        self.db_config = db_config or self._get_default_db_config()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "test_name": self.__class__.__name__,
            "metrics": {},
            "details": {},
        }

    def _get_default_db_config(self) -> dict:
        """Получение дефолтной конфигурации для PostgreSQL."""
        return {
            "host": "localhost",
            "port": 5432,
            "database": "news_analysis",
            "user": "postgres",
            "password": "postgres",
        }

    async def fetch_test_data(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение тестовых данных из PostgreSQL."""
        try:
            conn = await asyncpg.connect(**self.db_config)

            query = """
            SELECT 
                m.channel_id AS channel,
                m.text,
                a.summary,
                a.sentiment,
                a.hashtags,
                m.date AS created_at,
                NULL AS analyzed_at
            FROM messages m
            JOIN analyses a ON m.message_id = a.message_id
            WHERE a.summary IS NOT NULL 
                AND length(a.summary) > 10
                AND a.hashtags IS NOT NULL
            ORDER BY m.date DESC
            LIMIT $1
            """

            rows = await conn.fetch(query, limit)
            await conn.close()

            data = []
            for row in rows:
                hashtags = row["hashtags"] if row["hashtags"] else []
                if isinstance(hashtags, str):
                    import json

                    try:
                        hashtags = json.loads(hashtags)
                    except:
                        hashtags = hashtags.split(",") if hashtags else []

                data.append(
                    {
                        "id": None,  # message_id не возвращаем, если нужно - добавить
                        "channel": row["channel"],
                        "text": row["text"],
                        "summary": row["summary"],
                        "sentiment": row["sentiment"],
                        "hashtags": hashtags,
                        "created_at": row["created_at"],
                        "analyzed_at": row["analyzed_at"],
                    }
                )

            return data

        except Exception as e:
            print(f"❌ Ошибка при получении данных: {e}")
            return []

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Основной метод для запуска теста.
        Должен быть переопределен в наследниках.
        """
        raise NotImplementedError("Метод run_test должен быть реализован в наследнике")

    def generate_report(self) -> Dict[str, Any]:
        """Генерация отчета по результатам теста."""
        return {
            "test_name": self.results["test_name"],
            "timestamp": self.results["timestamp"],
            "metrics": self.results["metrics"],
            "summary": self._generate_summary(),
            "recommendations": self._generate_recommendations(),
        }

    def _generate_summary(self) -> str:
        """Генерация краткого резюме теста."""
        return f"Тест {self.results['test_name']} завершен"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе результатов."""
        return []

    def save_results(self, output_path: str):
        """Сохранение результатов в файл."""
        import json

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.generate_report(), f, ensure_ascii=False, indent=2)

        print(f"✅ Результаты сохранены: {path}")
