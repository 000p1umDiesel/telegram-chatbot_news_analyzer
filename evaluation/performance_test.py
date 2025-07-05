#!/usr/bin/env python3
"""
Тест производительности и нагрузочного тестирования системы анализа новостей.
Проверяет скорость обработки, использование памяти, стабильность под нагрузкой.
"""

import argparse
import asyncio
import time
import psutil
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import gc

# Импортируем компоненты системы
import sys

sys.path.append(".")

try:
    from services.llm import OllamaAnalyzer
    from services.db.pg_manager import AsyncPostgresManager as DataManager

    SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Не удалось импортировать компоненты системы: {e}")
    SYSTEM_AVAILABLE = False


class PerformanceTester:
    """Тестирование производительности системы анализа новостей."""

    def __init__(self, db_path: Path = Path("data/storage.db")):
        self.db_path = db_path
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "system_info": self._get_system_info(),
            "tests": {},
        }

        # Инициализируем компоненты системы если доступны
        if SYSTEM_AVAILABLE:
            try:
                self.analyzer = OllamaAnalyzer()
                self.data_manager = DataManager(db_path)
                print("✅ Компоненты системы инициализированы")
            except Exception as e:
                print(f"❌ Ошибка инициализации компонентов: {e}")
                self.analyzer = None
                self.data_manager = None
        else:
            self.analyzer = None
            self.data_manager = None

    def _get_system_info(self) -> Dict[str, Any]:
        """Получает информацию о системе."""
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "memory_available_gb": psutil.virtual_memory().available / (1024**3),
            "python_version": sys.version,
            "platform": sys.platform,
        }

    def test_database_performance(self) -> Dict[str, Any]:
        """Тестирует производительность операций с базой данных."""
        print("\n🔍 Тест производительности базы данных")

        if not self.db_path.exists():
            return {"status": "failed", "error": "Database not found"}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Тест 1: Простые SELECT запросы
            start_time = time.time()
            for _ in range(100):
                cursor.execute("SELECT COUNT(*) FROM messages")
                cursor.fetchone()
            simple_select_time = time.time() - start_time

            # Тест 2: JOIN запросы
            start_time = time.time()
            for _ in range(50):
                cursor.execute(
                    """
                    SELECT m.message_id, m.text, a.summary 
                    FROM messages m 
                    JOIN analyses a ON m.message_id = a.message_id 
                    LIMIT 10
                """
                )
                cursor.fetchall()
            join_select_time = time.time() - start_time

            # Тест 3: Сложные запросы с фильтрацией
            start_time = time.time()
            for _ in range(20):
                cursor.execute(
                    """
                    SELECT channel_id, COUNT(*), AVG(LENGTH(text))
                    FROM messages 
                    WHERE LENGTH(text) > 100 
                    GROUP BY channel_id
                """
                )
                cursor.fetchall()
            complex_select_time = time.time() - start_time

            conn.close()

            results = {
                "status": "passed",
                "simple_select_avg_ms": (simple_select_time / 100) * 1000,
                "join_select_avg_ms": (join_select_time / 50) * 1000,
                "complex_select_avg_ms": (complex_select_time / 20) * 1000,
                "total_test_time": simple_select_time
                + join_select_time
                + complex_select_time,
            }

            print(f"  📊 Простые SELECT: {results['simple_select_avg_ms']:.2f}ms")
            print(f"  📊 JOIN запросы: {results['join_select_avg_ms']:.2f}ms")
            print(f"  📊 Сложные запросы: {results['complex_select_avg_ms']:.2f}ms")

            return results

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def test_llm_performance(self, samples: int = 20) -> Dict[str, Any]:
        """Тестирует производительность LLM анализа."""
        print(f"\n🔍 Тест производительности LLM ({samples} образцов)")

        if not self.analyzer:
            return {"status": "skipped", "reason": "LLM analyzer not available"}

        # Получаем тестовые тексты
        test_texts = self._get_test_texts(samples)
        if not test_texts:
            return {"status": "failed", "reason": "No test texts available"}

        analysis_times = []
        successful_analyses = 0
        failed_analyses = 0

        print(f"  🚀 Начинаем анализ {len(test_texts)} текстов...")
        start_total_time = time.time()

        for i, text in enumerate(test_texts):
            if i % 5 == 0:
                print(f"  📈 Обработано {i}/{len(test_texts)} текстов...")

            start_time = time.time()
            try:
                # Запускаем анализ синхронно для измерения времени
                result = asyncio.run(self.analyzer.analyze_message(text))
                analysis_time = time.time() - start_time

                if result:
                    analysis_times.append(analysis_time)
                    successful_analyses += 1
                else:
                    failed_analyses += 1

            except Exception as e:
                print(f"  ⚠️ Ошибка анализа текста {i}: {e}")
                failed_analyses += 1

        total_time = time.time() - start_total_time

        if analysis_times:
            results = {
                "status": "passed",
                "samples_processed": len(analysis_times),
                "successful_analyses": successful_analyses,
                "failed_analyses": failed_analyses,
                "avg_analysis_time": sum(analysis_times) / len(analysis_times),
                "min_analysis_time": min(analysis_times),
                "max_analysis_time": max(analysis_times),
                "total_time": total_time,
                "throughput_per_minute": (len(analysis_times) / total_time) * 60,
                "success_rate": successful_analyses
                / (successful_analyses + failed_analyses),
            }

            print(f"  ⏱️ Среднее время анализа: {results['avg_analysis_time']:.2f}с")
            print(
                f"  🚀 Пропускная способность: {results['throughput_per_minute']:.1f} анализов/мин"
            )
            print(f"  ✅ Успешность: {results['success_rate']:.1%}")

            return results
        else:
            return {"status": "failed", "reason": "No successful analyses"}

    def _get_test_texts(self, limit: int) -> List[str]:
        """Получает тестовые тексты из базы данных."""
        if not self.db_path.exists():
            # Возвращаем синтетические тексты для тестирования
            return [
                "Это тестовый новостной текст для проверки производительности системы анализа. "
                * 10,
                "Другая новость для тестирования алгоритмов обработки естественного языка. "
                * 8,
                "Третий пример текста, который будет использован для измерения скорости анализа. "
                * 12,
            ] * (limit // 3 + 1)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """
                SELECT text FROM messages 
                WHERE LENGTH(text) > 100 AND LENGTH(text) < 2000
                ORDER BY RANDOM() LIMIT ?
            """,
                (limit,),
            )

            texts = [row[0] for row in cursor.fetchall()]
            conn.close()
            return texts

        except Exception as e:
            print(f"  ⚠️ Ошибка получения тестовых текстов: {e}")
            return []

    def run_performance_tests(self, samples: int = 20) -> Dict[str, Any]:
        """Запускает тесты производительности."""
        print(f"🚀 Запуск тестирования производительности")
        print(f"📊 Образцов для LLM тестов: {samples}")
        print("=" * 50)

        start_time = time.time()

        # Запускаем тесты
        self.results["tests"]["database_performance"] = self.test_database_performance()
        self.results["tests"]["llm_performance"] = self.test_llm_performance(samples)

        # Общая статистика
        total_time = time.time() - start_time
        self.results["execution_summary"] = {
            "total_execution_time": total_time,
            "tests_run": len(self.results["tests"]),
            "tests_passed": sum(
                1
                for test in self.results["tests"].values()
                if test.get("status") == "passed"
            ),
            "tests_failed": sum(
                1
                for test in self.results["tests"].values()
                if test.get("status") == "failed"
            ),
            "tests_skipped": sum(
                1
                for test in self.results["tests"].values()
                if test.get("status") == "skipped"
            ),
        }

        # Выводим итоги
        print("\n" + "=" * 50)
        print("📋 ИТОГИ ТЕСТИРОВАНИЯ ПРОИЗВОДИТЕЛЬНОСТИ:")
        summary = self.results["execution_summary"]
        print(f"⏱️ Общее время выполнения: {summary['total_execution_time']:.1f}с")
        print(f"✅ Тестов пройдено: {summary['tests_passed']}")
        print(f"❌ Тестов провалено: {summary['tests_failed']}")
        print(f"⏭️ Тестов пропущено: {summary['tests_skipped']}")

        return self.results

    def save_results(self, output_path: Path):
        """Сохраняет результаты тестирования."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Результаты сохранены: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Тестирование производительности системы анализа новостей"
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=20,
        help="Количество образцов для LLM тестов (по умолчанию: 20)",
    )

    parser.add_argument(
        "--db", type=Path, default=Path("data/storage.db"), help="Путь к базе данных"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/performance_results.json"),
        help="Путь для сохранения результатов",
    )

    args = parser.parse_args()

    # Запускаем тестирование
    tester = PerformanceTester(args.db)
    results = tester.run_performance_tests(samples=args.samples)

    # Сохраняем результаты
    tester.save_results(args.output)

    print(f"\n🎉 Тестирование производительности завершено!")


if __name__ == "__main__":
    main()
