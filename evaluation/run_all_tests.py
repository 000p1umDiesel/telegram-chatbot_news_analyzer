#!/usr/bin/env python3
"""
Unified Test Runner for News Analysis Evaluation System

Запуск всех тестов:
    python evaluation/run_all_tests.py --all --samples 100

Запуск отдельных тестов:
    python evaluation/run_all_tests.py --tests rouge semantic hashtag --samples 50

Запуск с конкретной конфигурацией БД:
    python evaluation/run_all_tests.py --tests performance --db-config custom_db.json
"""

import asyncio
import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

# Импорты тестов
from evaluation.tests.rouge_test import ROUGETest
from evaluation.tests.semantic_test import SemanticTest
from evaluation.tests.hallucination_test import HallucinationTest
from evaluation.tests.hashtag_test import HashtagTest
from evaluation.tests.sentiment_test import SentimentTest
from evaluation.tests.ab_prompt_test import ABPromptTest
from evaluation.tests.performance_test import PerformanceTest

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UnifiedTestRunner:
    """Унифицированный раннер для всех тестов оценки"""

    def __init__(self, db_config_path: str = "db_config.json"):
        self.db_config_path = db_config_path
        self.test_registry = {
            "rouge": ROUGETest,
            "semantic": SemanticTest,
            "hallucination": HallucinationTest,
            "hashtag": HashtagTest,
            "sentiment": SentimentTest,
            "ab_prompt": ABPromptTest,
            "performance": PerformanceTest,
        }

    def load_db_config(self) -> Optional[Dict[str, Any]]:
        """Загрузка конфигурации базы данных"""
        try:
            if Path(self.db_config_path).exists():
                with open(self.db_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                logger.info(f"Загружена конфигурация БД из {self.db_config_path}")
                return config
            else:
                logger.warning(
                    f"Файл {self.db_config_path} не найден. Используется конфигурация по умолчанию."
                )
                return {
                    "host": "localhost",
                    "port": 5432,
                    "database": "news_analyzer",
                    "user": "postgres",
                    "password": "postgres",
                }
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации БД: {e}")
            return None

    async def run_test(
        self, test_name: str, samples: int = 100
    ) -> Optional[Dict[str, Any]]:
        """Запуск отдельного теста"""
        if test_name not in self.test_registry:
            logger.error(f"Неизвестный тест: {test_name}")
            return None

        logger.info(f"🚀 Запуск теста: {test_name} ({samples} samples)")

        try:
            # Создаем экземпляр тестера
            test_class = self.test_registry[test_name]

            # Всегда используем db_config
            db_config = self.load_db_config()
            if db_config is None:
                logger.error(
                    f"Не удалось загрузить конфигурацию БД для теста {test_name}"
                )
                return None
            evaluator = test_class(db_config)

            # Запуск теста
            start_time = time.time()

            # Получаем данные для теста
            test_data = await evaluator.fetch_test_data(samples)

            # Все тесты используют метод run_test
            results = evaluator.run_test(test_data)

            execution_time = time.time() - start_time

            logger.info(f"✅ Тест {test_name} завершен за {execution_time:.2f}s")

            return {
                "test_name": test_name,
                "execution_time": execution_time,
                "samples": samples,
                "results": results,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка в тесте {test_name}: {e}")
            return None

    async def run_multiple_tests(
        self, test_names: List[str], samples: int = 100
    ) -> Dict[str, Any]:
        """Запуск нескольких тестов"""
        logger.info(f"📊 Запуск {len(test_names)} тестов: {', '.join(test_names)}")

        all_results = {}
        total_start_time = time.time()

        for test_name in test_names:
            result = await self.run_test(test_name, samples)
            if result:
                all_results[test_name] = result
            else:
                logger.warning(f"⚠️ Тест {test_name} не выполнен")

        total_execution_time = time.time() - total_start_time

        # Формируем итоговый отчет
        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(test_names),
            "successful_tests": len(all_results),
            "failed_tests": len(test_names) - len(all_results),
            "total_execution_time": total_execution_time,
            "samples_per_test": samples,
            "results": all_results,
        }

        return summary

    def save_results(self, results: Dict[str, Any], output_file: Optional[str] = None):
        """Сохранение результатов в файл"""
        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"evaluation/test_results_{timestamp}.json"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"📄 Результаты сохранены в {output_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения результатов: {e}")

    def print_summary(self, results: Dict[str, Any]):
        """Вывод краткого отчета"""
        print("\n" + "=" * 80)
        print("🎯 ИТОГОВЫЙ ОТЧЕТ ПО ТЕСТИРОВАНИЮ")
        print("=" * 80)

        print(f"⏰ Время выполнения: {results['timestamp']}")
        print(f"📊 Всего тестов: {results['total_tests']}")
        print(f"✅ Успешных: {results['successful_tests']}")
        print(f"❌ Неудачных: {results['failed_tests']}")
        print(f"⏱️ Общее время: {results['total_execution_time']:.2f}s")
        print(f"🔢 Образцов на тест: {results['samples_per_test']}")

        print("\n📈 РЕЗУЛЬТАТЫ ПО ТЕСТАМ:")
        print("-" * 50)

        for test_name, test_data in results["results"].items():
            print(f"\n🧪 {test_name.upper()}:")
            print(f"   ⏱️ Время: {test_data['execution_time']:.2f}s")

            if "results" in test_data and test_data["results"]:
                test_results = test_data["results"]

                # Разные форматы для разных тестов
                if test_name == "rouge":
                    avg_rouge = test_results.get("average_rouge_scores", {})
                    print(f"   📊 ROUGE-1: {avg_rouge.get('rouge1_f', 0):.3f}")
                    print(f"   📊 ROUGE-2: {avg_rouge.get('rouge2_f', 0):.3f}")
                    print(f"   📊 ROUGE-L: {avg_rouge.get('rougeL_f', 0):.3f}")

                elif test_name == "semantic":
                    print(
                        f"   📊 BERTScore F1: {test_results.get('average_bertscore_f1', 0):.3f}"
                    )
                    print(
                        f"   📊 Semantic Similarity: {test_results.get('average_semantic_similarity', 0):.3f}"
                    )

                elif test_name == "hallucination":
                    print(
                        f"   📊 Hallucination Rate: {test_results.get('hallucination_rate', 0):.3f}"
                    )
                    print(
                        f"   📊 Confidence: {test_results.get('average_confidence', 0):.3f}"
                    )

                elif test_name == "hashtag":
                    print(f"   📊 Accuracy: {test_results.get('accuracy', 0):.3f}")
                    print(f"   📊 Precision: {test_results.get('precision', 0):.3f}")
                    print(f"   📊 Recall: {test_results.get('recall', 0):.3f}")

                elif test_name == "sentiment":
                    print(f"   📊 Accuracy: {test_results.get('accuracy', 0):.3f}")
                    print(f"   📊 F1-Score: {test_results.get('f1_score', 0):.3f}")

                elif test_name == "ab_prompt":
                    for strategy, metrics in test_results.items():
                        if isinstance(metrics, dict):
                            print(
                                f"   📊 {strategy}: Quality={metrics.get('quality', 0):.3f}"
                            )

                elif test_name == "performance":
                    print(
                        f"   📊 Avg Response Time: {test_results.get('average_response_time', 0):.3f}s"
                    )
                    print(
                        f"   📊 Memory Usage: {test_results.get('peak_memory_mb', 0):.1f}MB"
                    )

        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Unified Test Runner for News Analysis"
    )

    parser.add_argument(
        "--tests",
        nargs="+",
        choices=[
            "rouge",
            "semantic",
            "hallucination",
            "hashtag",
            "sentiment",
            "ab_prompt",
            "performance",
        ],
        help="Specific tests to run",
    )

    parser.add_argument("--all", action="store_true", help="Run all available tests")

    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Number of samples per test (default: 100)",
    )

    parser.add_argument(
        "--db-config",
        type=str,
        default="db_config.json",
        help="Database configuration file (default: db_config.json)",
    )

    parser.add_argument(
        "--output", type=str, help="Output file for results (default: auto-generated)"
    )

    parser.add_argument(
        "--no-save", action="store_true", help="Do not save results to file"
    )

    args = parser.parse_args()

    # Определяем какие тесты запускать
    if args.all:
        test_names = list(
            [
                "rouge",
                "semantic",
                "hallucination",
                "hashtag",
                "sentiment",
                "ab_prompt",
                "performance",
            ]
        )
    elif args.tests:
        test_names = args.tests
    else:
        print("❌ Укажите --all или --tests с конкретными тестами")
        parser.print_help()
        return

    # Создаем и запускаем тестер
    runner = UnifiedTestRunner(args.db_config)

    async def run_tests():
        results = await runner.run_multiple_tests(test_names, args.samples)

        # Выводим отчет
        runner.print_summary(results)

        # Сохраняем результаты
        if not args.no_save:
            runner.save_results(results, args.output)

        return results

    # Запуск
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        logger.info("🛑 Тестирование прервано пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
