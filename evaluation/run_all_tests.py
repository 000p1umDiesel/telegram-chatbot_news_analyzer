#!/usr/bin/env python3
"""
Мастер-скрипт для запуска всех тестов системы анализа новостей.
Поддерживает различные режимы тестирования и генерацию отчетов.
"""

import argparse
import subprocess
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor


class TestRunner:
    """Запускает и координирует все тесты системы."""

    def __init__(self, db_path: Path = Path("data/storage.db")):
        self.db_path = db_path
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite_results": {},
            "execution_summary": {},
            "recommendations": [],
        }

        # Определяем доступные тесты
        self.available_tests = {
            "comprehensive": {
                "script": "evaluation/comprehensive_test.py",
                "description": "Комплексное тестирование всех компонентов (включая улучшенную детекцию галлюцинаций)",
                "default_args": ["--samples", "50"],
            },
            "rouge": {
                "script": "evaluation/rouge_metrics_test.py",
                "description": "ROUGE метрики качества суммаризации",
                "default_args": ["--samples", "100"],
            },
            "performance": {
                "script": "evaluation/performance_test.py",
                "description": "Тестирование производительности",
                "default_args": ["--samples", "20"],
            },
            "ab_prompt": {
                "script": "evaluation/ab_prompt_test.py",
                "description": "A/B тестирование промптов",
                "default_args": ["--sample-size", "15"],
            },
        }

    def check_dependencies(self) -> Dict[str, bool]:
        """Проверяет доступность необходимых зависимостей."""
        print("🔍 Проверка зависимостей...")

        dependencies = {
            "rouge-score": False,
            "nltk": False,
            "psutil": False,
            "numpy": False,
            "database": False,
        }

        # Проверяем Python пакеты
        try:
            import rouge_score

            dependencies["rouge-score"] = True
        except ImportError:
            pass

        try:
            import nltk

            dependencies["nltk"] = True
        except ImportError:
            pass

        try:
            import psutil

            dependencies["psutil"] = True
        except ImportError:
            pass

        try:
            import numpy

            dependencies["numpy"] = True
        except ImportError:
            pass

        # Проверяем базу данных
        dependencies["database"] = self.db_path.exists()

        # Выводим результаты
        for dep, available in dependencies.items():
            status = "✅" if available else "❌"
            print(f"  {status} {dep}")

        return dependencies

    def install_missing_dependencies(self, dependencies: Dict[str, bool]):
        """Предлагает установить недостающие зависимости."""
        missing = [
            dep
            for dep, available in dependencies.items()
            if not available and dep != "database"
        ]

        if missing:
            print(f"\n⚠️ Отсутствующие зависимости: {', '.join(missing)}")

            install_commands = {
                "rouge-score": "pip install rouge-score",
                "nltk": "pip install nltk",
                "psutil": "pip install psutil",
                "numpy": "pip install numpy",
            }

            print("📦 Команды для установки:")
            for dep in missing:
                if dep in install_commands:
                    print(f"  {install_commands[dep]}")

    def run_single_test(
        self, test_name: str, custom_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Запускает отдельный тест."""
        if test_name not in self.available_tests:
            return {
                "status": "failed",
                "error": f"Unknown test: {test_name}",
                "execution_time": 0,
            }

        test_config = self.available_tests[test_name]
        script_path = test_config["script"]

        if not Path(script_path).exists():
            return {
                "status": "failed",
                "error": f"Test script not found: {script_path}",
                "execution_time": 0,
            }

        print(f"\n🚀 Запуск теста: {test_name}")
        print(f"📝 Описание: {test_config['description']}")

        # Формируем аргументы командной строки
        args = ["python", script_path]

        # Добавляем пользовательские аргументы или стандартные
        if custom_args:
            args.extend(custom_args)
        else:
            args.extend(test_config["default_args"])

        # Добавляем путь к базе данных
        args.extend(["--db", str(self.db_path)])

        # Добавляем путь для вывода результатов (кроме comprehensive теста)
        output_file = Path(f"evaluation/{test_name}_results.json")
        if test_name != "comprehensive":
            args.extend(["--output", str(output_file)])

        start_time = time.time()

        try:
            # Запускаем тест
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=600,  # 10 минут максимум на тест
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                # Пытаемся загрузить результаты
                test_results = None
                if output_file.exists():
                    try:
                        with open(output_file, "r", encoding="utf-8") as f:
                            test_results = json.load(f)
                    except Exception as e:
                        print(f"⚠️ Не удалось загрузить результаты: {e}")

                return {
                    "status": "passed",
                    "execution_time": execution_time,
                    "stdout": result.stdout,
                    "results": test_results,
                }
            else:
                return {
                    "status": "failed",
                    "execution_time": execution_time,
                    "error": result.stderr,
                    "stdout": result.stdout,
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "execution_time": time.time() - start_time,
                "error": "Test execution timeout (10 minutes)",
            }
        except Exception as e:
            return {
                "status": "error",
                "execution_time": time.time() - start_time,
                "error": str(e),
            }

    def run_tests_parallel(
        self, test_names: List[str], max_workers: int = 2
    ) -> Dict[str, Any]:
        """Запускает тесты параллельно."""
        print(f"\n🔄 Параллельный запуск тестов (макс. {max_workers} потоков)")

        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Запускаем тесты
            future_to_test = {
                executor.submit(self.run_single_test, test_name): test_name
                for test_name in test_names
            }

            # Собираем результаты
            for future in concurrent.futures.as_completed(future_to_test):
                test_name = future_to_test[future]
                try:
                    result = future.result()
                    results[test_name] = result

                    status_icon = "✅" if result["status"] == "passed" else "❌"
                    print(
                        f"  {status_icon} {test_name}: {result['status']} ({result['execution_time']:.1f}s)"
                    )

                except Exception as e:
                    results[test_name] = {
                        "status": "error",
                        "error": str(e),
                        "execution_time": 0,
                    }
                    print(f"  ❌ {test_name}: error - {e}")

        return results

    def run_tests_sequential(self, test_names: List[str]) -> Dict[str, Any]:
        """Запускает тесты последовательно."""
        print(f"\n🔄 Последовательный запуск тестов")

        results = {}

        for test_name in test_names:
            result = self.run_single_test(test_name)
            results[test_name] = result

            status_icon = "✅" if result["status"] == "passed" else "❌"
            print(
                f"  {status_icon} {test_name}: {result['status']} ({result['execution_time']:.1f}s)"
            )

        return results

    def analyze_results(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Анализирует результаты всех тестов."""
        print(f"\n📊 Анализ результатов тестирования")

        total_tests = len(test_results)
        passed_tests = sum(1 for r in test_results.values() if r["status"] == "passed")
        failed_tests = sum(1 for r in test_results.values() if r["status"] == "failed")
        error_tests = sum(
            1 for r in test_results.values() if r["status"] in ["error", "timeout"]
        )

        total_time = sum(r["execution_time"] for r in test_results.values())

        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "error_tests": error_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "total_execution_time": total_time,
        }

        print(f"  📈 Всего тестов: {total_tests}")
        print(f"  ✅ Пройдено: {passed_tests}")
        print(f"  ❌ Провалено: {failed_tests}")
        print(f"  🚫 Ошибки: {error_tests}")
        print(f"  📊 Успешность: {summary['success_rate']:.1%}")
        print(f"  ⏱️ Общее время: {total_time:.1f}с")

        return summary

    def generate_recommendations(self, test_results: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации на основе результатов тестов."""
        recommendations = []

        # Анализируем результаты каждого теста
        for test_name, result in test_results.items():
            if result["status"] != "passed":
                if result["status"] == "timeout":
                    recommendations.append(
                        f"⏱️ Тест {test_name} превысил лимит времени. "
                        "Рассмотрите оптимизацию производительности системы."
                    )
                elif "results" not in result:
                    recommendations.append(
                        f"🔧 Тест {test_name} завершился с ошибкой. "
                        "Проверьте настройки и зависимости."
                    )
            else:
                # Анализируем результаты успешных тестов
                if test_name == "comprehensive" and result.get("results"):
                    comp_results = result["results"]

                    # Проверяем качество галлюцинаций
                    if "hallucination_detection" in comp_results:
                        halluc_rate = comp_results["hallucination_detection"].get(
                            "hallucination_rate", 0
                        )
                        if halluc_rate > 0.2:  # Более 20% галлюцинаций
                            recommendations.append(
                                f"🧠 Высокий уровень галлюцинаций ({halluc_rate:.1%}). "
                                "Рассмотрите настройку температуры модели или улучшение промптов."
                            )

                    # Проверяем консистентность sentiment analysis
                    if "sentiment_consistency" in comp_results:
                        consistency = comp_results["sentiment_consistency"].get(
                            "consistency_score", 0
                        )
                        if consistency < 0.8:  # Менее 80% консистентности
                            recommendations.append(
                                f"😐 Низкая консистентность анализа тональности ({consistency:.1%}). "
                                "Рекомендуется улучшить промпты для определения тональности."
                            )

                elif test_name == "rouge" and result.get("results"):
                    rouge_results = result["results"]

                    if "rouge_evaluation" in rouge_results:
                        rouge_scores = rouge_results["rouge_evaluation"].get(
                            "aggregated_scores", {}
                        )
                        rouge1_f1 = rouge_scores.get("rouge1", {}).get("fmeasure", 0)

                        if rouge1_f1 < 0.3:  # Низкие ROUGE scores
                            recommendations.append(
                                f"📝 Низкие ROUGE-1 F1 scores ({rouge1_f1:.3f}). "
                                "Качество суммаризации требует улучшения."
                            )

                elif test_name == "performance" and result.get("results"):
                    perf_results = result["results"]

                    if (
                        "tests" in perf_results
                        and "llm_performance" in perf_results["tests"]
                    ):
                        llm_perf = perf_results["tests"]["llm_performance"]
                        throughput = llm_perf.get("throughput_per_minute", 0)

                        if throughput < 5:  # Менее 5 анализов в минуту
                            recommendations.append(
                                f"🐌 Низкая производительность LLM ({throughput:.1f} анализов/мин). "
                                "Рассмотрите оптимизацию или использование более быстрой модели."
                            )

        # Общие рекомендации
        failed_count = sum(1 for r in test_results.values() if r["status"] != "passed")
        if failed_count > 0:
            recommendations.append(
                f"🔧 {failed_count} тестов завершились неуспешно. "
                "Проверьте логи и устраните проблемы перед продакшеном."
            )

        if not recommendations:
            recommendations.append(
                "🎉 Все тесты прошли успешно! Система готова к использованию."
            )

        return recommendations

    def generate_report(self, test_results: Dict[str, Any], output_path: Path):
        """Генерирует итоговый отчет о тестировании."""
        summary = self.analyze_results(test_results)
        recommendations = self.generate_recommendations(test_results)

        self.results["test_suite_results"] = test_results
        self.results["execution_summary"] = summary
        self.results["recommendations"] = recommendations

        # Сохраняем отчет
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Итоговый отчет сохранен: {output_path}")

        # Выводим рекомендации
        print(f"\n📋 РЕКОМЕНДАЦИИ:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

    def run_test_suite(
        self, test_names: List[str], parallel: bool = False, max_workers: int = 2
    ) -> Dict[str, Any]:
        """Запускает набор тестов."""
        print(f"🚀 Запуск набора тестов: {', '.join(test_names)}")
        print(f"📊 Режим: {'параллельный' if parallel else 'последовательный'}")
        print("=" * 60)

        start_time = time.time()

        # Проверяем зависимости
        dependencies = self.check_dependencies()
        self.install_missing_dependencies(dependencies)

        # Запускаем тесты
        if parallel and len(test_names) > 1:
            test_results = self.run_tests_parallel(test_names, max_workers)
        else:
            test_results = self.run_tests_sequential(test_names)

        total_time = time.time() - start_time

        print(f"\n⏱️ Общее время выполнения: {total_time:.1f}с")

        return test_results


def main():
    parser = argparse.ArgumentParser(
        description="Мастер-скрипт для запуска всех тестов системы анализа новостей"
    )

    parser.add_argument(
        "--tests",
        nargs="+",
        choices=[
            "comprehensive",
            "rouge",
            "performance",
            "ab_prompt",
            "all",
        ],
        default=["all"],
        help="Тесты для запуска (по умолчанию: all)",
    )

    parser.add_argument(
        "--parallel", action="store_true", help="Запускать тесты параллельно"
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Максимальное количество параллельных процессов (по умолчанию: 2)",
    )

    parser.add_argument(
        "--db", type=Path, default=Path("data/storage.db"), help="Путь к базе данных"
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=Path("evaluation/test_suite_report.json"),
        help="Путь для сохранения итогового отчета",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Быстрый режим с уменьшенными размерами выборок",
    )

    args = parser.parse_args()

    # Определяем список тестов
    runner = TestRunner(args.db)

    if "all" in args.tests:
        test_names = list(runner.available_tests.keys())
    else:
        test_names = args.tests

    # В быстром режиме уменьшаем размеры выборок
    if args.quick:
        print("⚡ Быстрый режим: уменьшенные размеры выборок")
        # Уменьшаем размеры выборок в 2 раза
        for test_name, test_config in runner.available_tests.items():
            new_args = []
            i = 0
            while i < len(test_config["default_args"]):
                arg = test_config["default_args"][i]
                if arg in ["--samples", "--sample-size"] and i + 1 < len(
                    test_config["default_args"]
                ):
                    # Добавляем флаг и уменьшенное значение
                    new_args.append(arg)
                    original_value = int(test_config["default_args"][i + 1])
                    new_args.append(str(max(1, original_value // 2)))
                    i += 2  # Пропускаем следующий аргумент
                else:
                    new_args.append(arg)
                    i += 1
            test_config["default_args"] = new_args

    # Запускаем тесты
    test_results = runner.run_test_suite(
        test_names, parallel=args.parallel, max_workers=args.max_workers
    )

    # Генерируем отчет
    runner.generate_report(test_results, args.report)

    print(f"\n🎉 Тестирование завершено!")


if __name__ == "__main__":
    main()
