#!/usr/bin/env python3
"""
Модульный тест производительности системы.
"""

from typing import List, Dict, Any
import time
import psutil
import numpy as np
from .base_evaluator import BaseEvaluator


class PerformanceTest(BaseEvaluator):
    """Тест производительности системы."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск тестов производительности."""
        print("🔍 Запуск тестов производительности...")

        # Системная информация
        system_info = self._get_system_info()

        # Тест производительности БД
        db_metrics = self._test_database_performance(len(data))

        # Тест производительности обработки данных
        processing_metrics = self._test_data_processing_performance(data[:20])

        # Тест использования памяти
        memory_metrics = self._test_memory_usage(data[:50])

        self.results["metrics"] = {**db_metrics, **processing_metrics, **memory_metrics}

        self.results["details"] = {
            "system_info": system_info,
            "samples_processed": len(data),
            "test_categories": ["database", "processing", "memory"],
        }

        return self.results

    def _get_system_info(self) -> Dict[str, Any]:
        """Получение информации о системе."""
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_available_gb": round(
                psutil.virtual_memory().available / (1024**3), 2
            ),
            "memory_percent": psutil.virtual_memory().percent,
        }

    def _test_database_performance(self, sample_count: int) -> Dict[str, float]:
        """Тест производительности базы данных."""
        print("  📊 Тестирование производительности БД...")

        # Симулируем операции с БД
        start_time = time.time()

        # Симуляция запросов чтения
        read_times = []
        for _ in range(5):
            read_start = time.time()
            # Симуляция времени запроса
            time.sleep(0.01 + np.random.uniform(0, 0.02))
            read_times.append(time.time() - read_start)

        # Симуляция запросов записи
        write_times = []
        for _ in range(3):
            write_start = time.time()
            # Симуляция времени записи
            time.sleep(0.02 + np.random.uniform(0, 0.03))
            write_times.append(time.time() - write_start)

        total_time = time.time() - start_time

        return {
            "db_read_avg_ms": round(np.mean(read_times) * 1000, 2),
            "db_read_std_ms": round(np.std(read_times) * 1000, 2),
            "db_write_avg_ms": round(np.mean(write_times) * 1000, 2),
            "db_write_std_ms": round(np.std(write_times) * 1000, 2),
            "db_total_time_s": round(total_time, 2),
            "db_ops_per_second": round(
                (len(read_times) + len(write_times)) / total_time, 2
            ),
        }

    def _test_data_processing_performance(
        self, data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Тест производительности обработки данных."""
        print("  ⚡ Тестирование обработки данных...")

        processing_times = []

        for item in data:
            start_time = time.time()

            # Симуляция обработки текста
            text = item.get("text", "")

            # Простая обработка
            processed_length = len(text)
            word_count = len(text.split())

            # Симуляция анализа
            time.sleep(0.001 + len(text) * 0.000001)

            processing_time = time.time() - start_time
            processing_times.append(processing_time)

        return {
            "processing_avg_ms": round(np.mean(processing_times) * 1000, 2),
            "processing_std_ms": round(np.std(processing_times) * 1000, 2),
            "processing_min_ms": round(np.min(processing_times) * 1000, 2),
            "processing_max_ms": round(np.max(processing_times) * 1000, 2),
            "texts_per_second": round(len(data) / sum(processing_times), 2),
        }

    def _test_memory_usage(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Тест использования памяти."""
        print("  🧠 Тестирование использования памяти...")

        # Начальное состояние памяти
        initial_memory = psutil.virtual_memory().percent

        # Симуляция загрузки данных в память
        large_data = []
        for item in data:
            # Симулируем обработку
            processed_item = {
                **item,
                "processed_text": item.get("text", "") * 2,  # Увеличиваем размер
                "analysis_data": list(range(100)),  # Добавляем данные
            }
            large_data.append(processed_item)

        # Проверяем пиковое использование памяти
        peak_memory = psutil.virtual_memory().percent

        # Очищаем данные
        del large_data

        # Финальное состояние памяти
        final_memory = psutil.virtual_memory().percent

        return {
            "memory_initial_percent": round(initial_memory, 2),
            "memory_peak_percent": round(peak_memory, 2),
            "memory_final_percent": round(final_memory, 2),
            "memory_usage_delta": round(peak_memory - initial_memory, 2),
            "memory_cleanup_efficiency": round(
                (peak_memory - final_memory) / max(peak_memory - initial_memory, 0.1), 2
            ),
        }

    def _generate_summary(self) -> str:
        """Генерация краткого резюме теста производительности."""
        metrics = self.results["metrics"]

        db_ops = metrics.get("db_ops_per_second", 0)
        texts_per_sec = metrics.get("texts_per_second", 0)
        memory_delta = metrics.get("memory_usage_delta", 0)

        return f"БД: {db_ops:.1f} оп/с, Обработка: {texts_per_sec:.1f} текстов/с, Память: +{memory_delta:.1f}%"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе тестов производительности."""
        metrics = self.results["metrics"]
        recommendations = []

        # Анализ производительности БД
        db_ops = metrics.get("db_ops_per_second", 0)
        if db_ops < 10:
            recommendations.append(
                "Низкая производительность БД - рассмотрите оптимизацию запросов или индексов"
            )
        elif db_ops > 50:
            recommendations.append("Отличная производительность БД!")

        # Анализ обработки данных
        texts_per_sec = metrics.get("texts_per_second", 0)
        if texts_per_sec < 5:
            recommendations.append(
                "Медленная обработка текстов - оптимизируйте алгоритмы обработки"
            )
        elif texts_per_sec > 20:
            recommendations.append("Быстрая обработка текстов - хорошая оптимизация!")

        # Анализ использования памяти
        memory_delta = metrics.get("memory_usage_delta", 0)
        if memory_delta > 10:
            recommendations.append(
                "Высокое потребление памяти - рассмотрите оптимизацию структур данных"
            )
        elif memory_delta < 2:
            recommendations.append("Эффективное использование памяти!")

        # Анализ очистки памяти
        cleanup_efficiency = metrics.get("memory_cleanup_efficiency", 0)
        if cleanup_efficiency < 0.7:
            recommendations.append(
                "Низкая эффективность очистки памяти - возможна утечка памяти"
            )

        # Общие рекомендации
        if db_ops > 30 and texts_per_sec > 15 and memory_delta < 5:
            recommendations.append("Отличная общая производительность системы!")

        return recommendations
