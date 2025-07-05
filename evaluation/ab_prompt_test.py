#!/usr/bin/env python3
"""
A/B тестирование промптов для оптимизации качества анализа новостей.
Сравнивает различные промпты, температуры и настройки LLM.
"""

import argparse
import asyncio
import sqlite3
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import numpy as np

# Импортируем компоненты системы
import sys

sys.path.append(".")

try:
    from services.llm import OllamaAnalyzer

    SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Не удалось импортировать компоненты системы: {e}")
    SYSTEM_AVAILABLE = False


@dataclass
class PromptVariant:
    """Вариант промпта для тестирования."""

    name: str
    system_prompt: str
    user_prompt_template: str
    temperature: float = 0.7
    max_tokens: int = 1000
    description: str = ""


class ABPromptTester:
    """A/B тестирование промптов для анализа новостей."""

    def __init__(self, db_path: Path = Path("data/storage.db")):
        self.db_path = db_path
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "test_variants": {},
            "comparisons": {},
            "summary": {},
        }

        # Инициализируем анализатор если доступен
        if SYSTEM_AVAILABLE:
            try:
                self.analyzer = OllamaAnalyzer()
                print("✅ LLM анализатор инициализирован")
            except Exception as e:
                print(f"❌ Ошибка инициализации анализатора: {e}")
                self.analyzer = None
        else:
            self.analyzer = None

        # Определяем варианты промптов для тестирования
        self.prompt_variants = self._define_prompt_variants()

    def _define_prompt_variants(self) -> List[PromptVariant]:
        """Определяет различные варианты промптов для тестирования."""

        variants = [
            # Оригинальный промпт (контрольная группа)
            PromptVariant(
                name="original",
                system_prompt="""Ты - эксперт по анализу новостей. Твоя задача - проанализировать новостной текст и предоставить структурированный анализ.""",
                user_prompt_template="""Проанализируй следующий новостной текст:

{text}

Предоставь анализ в следующем формате:
- Краткое резюме (2-3 предложения)
- Тональность (позитивная/негативная/нейтральная)
- Основные темы (до 5 тем)
- Ключевые слова (до 10 слов)
- Хештеги (до 5 хештегов)""",
                temperature=0.7,
                description="Оригинальный промпт системы",
            ),
            # Более структурированный промпт
            PromptVariant(
                name="structured",
                system_prompt="""Ты - профессиональный аналитик новостей с опытом работы в медиа-индустрии. 
Твоя специализация - быстрый и точный анализ новостного контента с выделением ключевых аспектов.""",
                user_prompt_template="""ЗАДАЧА: Проанализировать новостной текст

ТЕКСТ ДЛЯ АНАЛИЗА:
{text}

ТРЕБУЕМЫЙ АНАЛИЗ:

1. РЕЗЮМЕ: Сформулируй суть новости в 2-3 четких предложениях
2. ТОНАЛЬНОСТЬ: Определи эмоциональную окраску (позитивная/негативная/нейтральная)
3. КАТЕГОРИЯ: Определи основную тематическую категорию
4. КЛЮЧЕВЫЕ ТЕМЫ: Выдели 3-5 основных тем
5. ВАЖНЫЕ ТЕРМИНЫ: Найди 5-8 ключевых слов/терминов
6. ХЕШТЕГИ: Предложи 3-5 релевантных хештегов""",
                temperature=0.5,
                description="Более структурированный и детальный промпт",
            ),
            # Промпт с фокусом на качество
            PromptVariant(
                name="quality_focused",
                system_prompt="""Ты - эксперт по анализу новостей с высокими стандартами качества. 
Твоя задача - предоставить максимально точный и полезный анализ, избегая общих фраз и поверхностных выводов.""",
                user_prompt_template="""Проведи глубокий анализ новостного текста:

{text}

Важно:
- Резюме должно быть информативным и точным
- Тональность определяй на основе фактов и контекста
- Темы должны быть конкретными, не общими
- Ключевые слова - только самые важные для понимания
- Хештеги - практичные для социальных сетей

Формат ответа:
Резюме: [2-3 предложения]
Тональность: [позитивная/негативная/нейтральная + обоснование]
Темы: [конкретные темы через запятую]
Ключевые слова: [важные термины через запятую]
Хештеги: [#хештег1 #хештег2 #хештег3]""",
                temperature=0.3,
                description="Промпт с акцентом на качество и точность",
            ),
            # Краткий промпт
            PromptVariant(
                name="concise",
                system_prompt="""Ты - аналитик новостей. Предоставляй краткий, но полный анализ.""",
                user_prompt_template="""Анализ новости:
{text}

Нужно:
Резюме (кратко), Тональность, Темы, Ключевые слова, Хештеги""",
                temperature=0.7,
                description="Максимально краткий промпт",
            ),
            # Промпт с примерами
            PromptVariant(
                name="with_examples",
                system_prompt="""Ты - эксперт по анализу новостей. Используй следующие примеры как образец качественного анализа.""",
                user_prompt_template="""Проанализируй новость по образцу:

ПРИМЕР АНАЛИЗА:
Резюме: Центральный банк повысил ключевую ставку до 15% для борьбы с инфляцией. Решение вызвало смешанную реакцию экспертов.
Тональность: нейтральная (официальное решение с разными мнениями)
Темы: денежно-кредитная политика, инфляция, экономическое регулирование
Ключевые слова: ЦБ, ключевая ставка, инфляция, процентная ставка
Хештеги: #ЦБ #ставка #инфляция #экономика

ТВОЯ ЗАДАЧА - проанализировать этот текст:
{text}

Используй тот же формат и подход.""",
                temperature=0.6,
                description="Промпт с примером качественного анализа",
            ),
        ]

        return variants

    def _get_test_texts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает тестовые тексты из базы данных."""
        if not self.db_path.exists():
            # Возвращаем синтетические тексты
            return [
                {
                    "message_id": f"test_{i}",
                    "text": f"Тестовая новость номер {i} для проверки различных промптов анализа. "
                    * 10,
                    "channel_id": "test_channel",
                }
                for i in range(limit)
            ]

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                """
                SELECT message_id, text, channel_id
                FROM messages 
                WHERE LENGTH(text) > 200 AND LENGTH(text) < 2000
                AND text NOT LIKE '%@%'  -- Исключаем сообщения с упоминаниями
                ORDER BY RANDOM() LIMIT ?
            """,
                (limit,),
            )

            texts = []
            for row in cursor.fetchall():
                texts.append(
                    {
                        "message_id": row["message_id"],
                        "text": row["text"],
                        "channel_id": row["channel_id"],
                    }
                )

            conn.close()
            print(f"📊 Загружено {len(texts)} тестовых текстов")
            return texts

        except Exception as e:
            print(f"❌ Ошибка загрузки тестовых данных: {e}")
            return []

    async def _analyze_with_variant(
        self, text: str, variant: PromptVariant
    ) -> Dict[str, Any]:
        """Анализирует текст с использованием конкретного варианта промпта."""
        if not self.analyzer:
            return {"error": "Analyzer not available"}

        try:
            # Создаем временный анализатор с настройками варианта
            # Здесь нужно будет адаптировать под реальную структуру OllamaAnalyzer

            # Формируем промпт
            user_prompt = variant.user_prompt_template.format(text=text)

            # Запускаем анализ (это упрощенная версия, нужно адаптировать)
            result = await self.analyzer.analyze_message(text)

            if result:
                return {
                    "success": True,
                    "result": result,
                    "variant_name": variant.name,
                    "processing_time": 0,  # Здесь можно добавить измерение времени
                }
            else:
                return {"success": False, "error": "Analysis failed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _evaluate_analysis_quality(
        self, analysis: Dict[str, Any], original_text: str
    ) -> Dict[str, float]:
        """Оценивает качество анализа по различным метрикам."""
        scores = {
            "completeness": 0.0,  # Полнота анализа
            "relevance": 0.0,  # Релевантность
            "specificity": 0.0,  # Конкретность
            "length_appropriateness": 0.0,  # Соответствие длины
            "overall": 0.0,
        }

        if not analysis.get("success") or not analysis.get("result"):
            return scores

        result = analysis["result"]

        # Оценка полноты (есть ли все необходимые поля)
        required_fields = ["summary", "sentiment", "topics", "keywords"]
        present_fields = sum(1 for field in required_fields if result.get(field))
        scores["completeness"] = present_fields / len(required_fields)

        # Оценка длины резюме
        if result.get("summary"):
            summary_len = len(result["summary"].split())
            if 10 <= summary_len <= 50:  # Оптимальная длина резюме
                scores["length_appropriateness"] = 1.0
            elif 5 <= summary_len <= 80:
                scores["length_appropriateness"] = 0.7
            else:
                scores["length_appropriateness"] = 0.3

        # Оценка конкретности (избегание общих фраз)
        if result.get("summary"):
            generic_phrases = [
                "важная новость",
                "интересная информация",
                "актуальная тема",
            ]
            summary_lower = result["summary"].lower()
            generic_count = sum(
                1 for phrase in generic_phrases if phrase in summary_lower
            )
            scores["specificity"] = max(0, 1.0 - (generic_count * 0.3))

        # Оценка релевантности тем
        if result.get("topics") and isinstance(result["topics"], list):
            # Простая проверка - темы не должны быть слишком общими
            generic_topics = ["новости", "информация", "события", "актуальное"]
            specific_topics = [
                t for t in result["topics"] if t.lower() not in generic_topics
            ]
            if result["topics"]:
                scores["relevance"] = len(specific_topics) / len(result["topics"])

        # Общая оценка
        scores["overall"] = np.mean(
            [
                scores["completeness"],
                scores["relevance"],
                scores["specificity"],
                scores["length_appropriateness"],
            ]
        )

        return scores

    async def run_ab_test(self, sample_size: int = 30) -> Dict[str, Any]:
        """Запускает A/B тестирование промптов."""
        print(f"🚀 Запуск A/B тестирования промптов")
        print(f"📊 Размер выборки: {sample_size} текстов на вариант")
        print(f"🔬 Вариантов для тестирования: {len(self.prompt_variants)}")
        print("=" * 60)

        if not self.analyzer:
            print("❌ LLM анализатор недоступен")
            return self.results

        # Получаем тестовые тексты
        test_texts = self._get_test_texts(sample_size * len(self.prompt_variants))
        if not test_texts:
            print("❌ Не удалось получить тестовые тексты")
            return self.results

        # Перемешиваем тексты для случайного распределения
        random.shuffle(test_texts)

        # Разбиваем тексты по вариантам
        texts_per_variant = len(test_texts) // len(self.prompt_variants)

        # Тестируем каждый вариант
        for i, variant in enumerate(self.prompt_variants):
            print(
                f"\n🔍 Тестирование варианта '{variant.name}' ({variant.description})"
            )

            # Выбираем тексты для этого варианта
            start_idx = i * texts_per_variant
            end_idx = start_idx + texts_per_variant
            variant_texts = test_texts[start_idx:end_idx]

            variant_results = []
            successful_analyses = 0

            for j, text_data in enumerate(variant_texts):
                if j % 10 == 0:
                    print(f"  📈 Обработано {j}/{len(variant_texts)} текстов...")

                # Анализируем текст
                analysis = await self._analyze_with_variant(text_data["text"], variant)

                if analysis.get("success"):
                    # Оценка качества
                    quality_scores = self._evaluate_analysis_quality(
                        analysis, text_data["text"]
                    )

                    variant_results.append(
                        {
                            "message_id": text_data["message_id"],
                            "analysis": analysis["result"],
                            "quality_scores": quality_scores,
                        }
                    )
                    successful_analyses += 1

            # Агрегируем результаты для варианта
            if variant_results:
                avg_scores = {}
                for metric in [
                    "completeness",
                    "relevance",
                    "specificity",
                    "length_appropriateness",
                    "overall",
                ]:
                    scores = [r["quality_scores"][metric] for r in variant_results]
                    avg_scores[metric] = {
                        "mean": np.mean(scores),
                        "std": np.std(scores),
                        "min": np.min(scores),
                        "max": np.max(scores),
                    }

                self.results["test_variants"][variant.name] = {
                    "variant_info": {
                        "name": variant.name,
                        "description": variant.description,
                        "temperature": variant.temperature,
                        "max_tokens": variant.max_tokens,
                    },
                    "sample_size": len(variant_results),
                    "success_rate": successful_analyses / len(variant_texts),
                    "quality_metrics": avg_scores,
                    "sample_results": variant_results[:5],  # Первые 5 для примера
                }

                print(
                    f"  ✅ Успешно проанализировано: {successful_analyses}/{len(variant_texts)}"
                )
                print(
                    f"  📊 Общая оценка качества: {avg_scores['overall']['mean']:.3f}"
                )
            else:
                print(
                    f"  ❌ Не удалось получить результаты для варианта {variant.name}"
                )

        # Сравнительный анализ
        self._compare_variants()

        return self.results

    def _compare_variants(self):
        """Сравнивает результаты различных вариантов промптов."""
        print(f"\n📊 Сравнительный анализ вариантов")

        if len(self.results["test_variants"]) < 2:
            print("❌ Недостаточно вариантов для сравнения")
            return

        # Сравниваем по основным метрикам
        comparison_metrics = [
            "completeness",
            "relevance",
            "specificity",
            "length_appropriateness",
            "overall",
        ]

        comparisons = {}

        for metric in comparison_metrics:
            metric_results = {}

            for variant_name, variant_data in self.results["test_variants"].items():
                if (
                    "quality_metrics" in variant_data
                    and metric in variant_data["quality_metrics"]
                ):
                    metric_results[variant_name] = variant_data["quality_metrics"][
                        metric
                    ]["mean"]

            if metric_results:
                # Находим лучший и худший варианты
                best_variant = max(metric_results.items(), key=lambda x: x[1])
                worst_variant = min(metric_results.items(), key=lambda x: x[1])

                comparisons[metric] = {
                    "best": {"variant": best_variant[0], "score": best_variant[1]},
                    "worst": {"variant": worst_variant[0], "score": worst_variant[1]},
                    "all_scores": metric_results,
                }

                print(f"  📈 {metric.upper()}:")
                print(f"    🥇 Лучший: {best_variant[0]} ({best_variant[1]:.3f})")
                print(f"    📉 Худший: {worst_variant[0]} ({worst_variant[1]:.3f})")

        self.results["comparisons"] = comparisons

        # Общий рейтинг вариантов
        overall_scores = {}
        for variant_name, variant_data in self.results["test_variants"].items():
            if (
                "quality_metrics" in variant_data
                and "overall" in variant_data["quality_metrics"]
            ):
                overall_scores[variant_name] = variant_data["quality_metrics"][
                    "overall"
                ]["mean"]

        if overall_scores:
            ranked_variants = sorted(
                overall_scores.items(), key=lambda x: x[1], reverse=True
            )

            print(f"\n🏆 ОБЩИЙ РЕЙТИНГ ВАРИАНТОВ:")
            for i, (variant, score) in enumerate(ranked_variants, 1):
                print(f"  {i}. {variant}: {score:.3f}")

            self.results["summary"] = {
                "best_overall_variant": ranked_variants[0][0],
                "best_overall_score": ranked_variants[0][1],
                "ranking": ranked_variants,
            }

    def save_results(self, output_path: Path):
        """Сохраняет результаты A/B тестирования."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Результаты A/B тестирования сохранены: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="A/B тестирование промптов для анализа новостей"
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Размер выборки для каждого варианта (по умолчанию: 20)",
    )

    parser.add_argument(
        "--db", type=Path, default=Path("data/storage.db"), help="Путь к базе данных"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/ab_test_results.json"),
        help="Путь для сохранения результатов",
    )

    args = parser.parse_args()

    # Проверяем доступность системы
    if not SYSTEM_AVAILABLE:
        print("❌ Компоненты системы недоступны для тестирования")
        return

    # Запускаем A/B тестирование
    tester = ABPromptTester(args.db)
    results = asyncio.run(tester.run_ab_test(args.sample_size))

    # Сохраняем результаты
    tester.save_results(args.output)

    print(f"\n🎉 A/B тестирование промптов завершено!")


if __name__ == "__main__":
    main()
