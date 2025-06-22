#!/usr/bin/env python3
"""
Демонстрационный скрипт для показа возможностей системы тестирования.
Запускает упрощенные версии тестов с синтетическими данными.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import random


class DemoTester:
    """Демонстрационное тестирование с синтетическими данными."""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "demo_mode": True,
            "tests": {},
        }

    def generate_synthetic_news(self, count: int = 10) -> List[Dict[str, Any]]:
        """Генерирует синтетические новости для демонстрации."""
        templates = [
            "Центральный банк России повысил ключевую ставку до {rate}% для борьбы с инфляцией. Решение вызвало {reaction} реакцию экспертов и участников рынка.",
            "В {city} открылся новый {facility}, который станет крупнейшим в регионе. Проект обошелся в {cost} миллиардов рублей.",
            "Российские ученые разработали новую технологию {tech}, которая может {benefit}. Разработка заняла {years} лет.",
            "Погодные условия в {region} ухудшились из-за {weather}. Метеорологи предупреждают о {warning}.",
            "Крупная IT-компания {company} объявила о запуске нового сервиса {service}. Ожидается, что он привлечет {users} пользователей.",
        ]

        variables = {
            "rate": ["15", "16", "17", "18"],
            "reaction": ["смешанную", "позитивную", "негативную", "осторожную"],
            "city": ["Москве", "Санкт-Петербурге", "Екатеринбурге", "Новосибирске"],
            "facility": [
                "торговый центр",
                "спортивный комплекс",
                "медицинский центр",
                "образовательный кампус",
            ],
            "cost": ["5", "10", "15", "20"],
            "tech": [
                "искусственного интеллекта",
                "квантовых вычислений",
                "биотехнологий",
                "нанотехнологий",
            ],
            "benefit": [
                "революционизировать медицину",
                "улучшить экологию",
                "повысить эффективность производства",
            ],
            "years": ["3", "5", "7", "10"],
            "region": ["Центральной России", "Сибири", "Дальнего Востока", "Урала"],
            "weather": ["циклона", "антициклона", "атмосферного фронта"],
            "warning": [
                "сильном ветре",
                "гололеде",
                "снегопадах",
                "резком похолодании",
            ],
            "company": ["Яндекс", "Сбер", "МТС", "Ростелеком"],
            "service": [
                "для малого бизнеса",
                "в сфере образования",
                "для государственных услуг",
            ],
            "users": ["миллион", "два миллиона", "пять миллионов"],
        }

        news = []
        for i in range(count):
            template = random.choice(templates)

            # Заполняем переменные
            text = template
            for var, options in variables.items():
                if f"{{{var}}}" in text:
                    text = text.replace(f"{{{var}}}", random.choice(options))

            news.append({"id": f"demo_{i}", "text": text, "channel": "demo_channel"})

        return news

    def simulate_llm_analysis(self, text: str) -> Dict[str, Any]:
        """Симулирует анализ LLM для демонстрации."""
        # Определяем тональность на основе ключевых слов
        positive_words = ["новый", "улучшить", "развитие", "успех", "рост"]
        negative_words = ["ухудшились", "проблема", "кризис", "падение", "риск"]

        pos_count = sum(1 for word in positive_words if word in text.lower())
        neg_count = sum(1 for word in negative_words if word in text.lower())

        if pos_count > neg_count:
            sentiment = "позитивная"
        elif neg_count > pos_count:
            sentiment = "негативная"
        else:
            sentiment = "нейтральная"

        # Генерируем краткое резюме (первые 2 предложения)
        sentences = text.split(".")
        summary = ". ".join(sentences[:2]).strip() + "."

        # Извлекаем ключевые слова
        words = text.lower().split()
        important_words = [w for w in words if len(w) > 4 and w.isalpha()]
        keywords = random.sample(important_words, min(5, len(important_words)))

        # Генерируем темы
        topic_mapping = {
            "банк": "экономика",
            "ставка": "финансы",
            "технология": "инновации",
            "ученые": "наука",
            "погода": "климат",
            "компания": "бизнес",
        }

        topics = []
        for word, topic in topic_mapping.items():
            if word in text.lower():
                topics.append(topic)

        if not topics:
            topics = ["общество"]

        # Генерируем хештеги
        hashtags = [f"#{topic}" for topic in topics[:3]]

        return {
            "summary": summary,
            "sentiment": sentiment,
            "topics": topics,
            "keywords": keywords,
            "hashtags": hashtags,
        }

    def demo_comprehensive_test(self) -> Dict[str, Any]:
        """Демонстрирует комплексное тестирование."""
        print("\n🔍 Демо: Комплексное тестирование")

        # Генерируем тестовые данные
        news_items = self.generate_synthetic_news(20)

        # Симулируем анализ
        analyses = []
        for item in news_items:
            analysis = self.simulate_llm_analysis(item["text"])
            analyses.append({"original": item, "analysis": analysis})

        # Оценка качества
        quality_scores = []
        hallucination_count = 0
        sentiment_consistency = 0

        for analysis in analyses:
            # Симулируем оценки
            completeness = random.uniform(0.7, 1.0)
            relevance = random.uniform(0.6, 0.95)

            # Симулируем детекцию галлюцинаций (10% случаев)
            has_hallucination = random.random() < 0.1
            if has_hallucination:
                hallucination_count += 1

            # Проверяем консистентность sentiment
            if analysis["analysis"]["sentiment"] in [
                "позитивная",
                "негативная",
                "нейтральная",
            ]:
                sentiment_consistency += 1

            quality_scores.append(
                {
                    "completeness": completeness,
                    "relevance": relevance,
                    "has_hallucination": has_hallucination,
                }
            )

        # Агрегируем результаты
        avg_completeness = sum(s["completeness"] for s in quality_scores) / len(
            quality_scores
        )
        avg_relevance = sum(s["relevance"] for s in quality_scores) / len(
            quality_scores
        )
        hallucination_rate = hallucination_count / len(analyses)
        sentiment_consistency_rate = sentiment_consistency / len(analyses)

        overall_score = (
            avg_completeness
            + avg_relevance
            + (1 - hallucination_rate)
            + sentiment_consistency_rate
        ) / 4

        results = {
            "status": "passed",
            "samples_tested": len(analyses),
            "metrics": {
                "avg_completeness": avg_completeness,
                "avg_relevance": avg_relevance,
                "hallucination_rate": hallucination_rate,
                "sentiment_consistency": sentiment_consistency_rate,
                "overall_score": overall_score,
            },
            "sample_analyses": analyses[:3],  # Первые 3 для примера
        }

        print(f"  📊 Образцов протестировано: {len(analyses)}")
        print(f"  ✅ Полнота анализа: {avg_completeness:.3f}")
        print(f"  🎯 Релевантность: {avg_relevance:.3f}")
        print(f"  🧠 Уровень галлюцинаций: {hallucination_rate:.1%}")
        print(f"  😊 Консистентность sentiment: {sentiment_consistency_rate:.1%}")
        print(f"  🏆 Общая оценка: {overall_score:.3f}")

        return results

    def demo_performance_test(self) -> Dict[str, Any]:
        """Демонстрирует тестирование производительности."""
        print("\n⚡ Демо: Тестирование производительности")

        # Симулируем различные операции
        operations = [
            ("Загрузка данных", 0.1, 0.3),
            ("LLM анализ", 2.0, 5.0),
            ("Сохранение результатов", 0.05, 0.15),
            ("Индексация", 0.2, 0.8),
        ]

        performance_results = {}
        total_time = 0

        for op_name, min_time, max_time in operations:
            # Симулируем выполнение операции
            op_time = random.uniform(min_time, max_time)
            time.sleep(0.1)  # Небольшая задержка для реализма

            performance_results[op_name] = {
                "avg_time": op_time,
                "operations_per_minute": 60 / op_time if op_time > 0 else 0,
            }
            total_time += op_time

            print(f"  🔄 {op_name}: {op_time:.2f}с ({60/op_time:.1f} оп/мин)")

        # Общая производительность
        throughput = 60 / total_time if total_time > 0 else 0

        results = {
            "status": "passed",
            "total_time": total_time,
            "throughput_per_minute": throughput,
            "operations": performance_results,
        }

        print(f"  🏁 Общее время цикла: {total_time:.2f}с")
        print(f"  🚀 Пропускная способность: {throughput:.1f} циклов/мин")

        return results

    def demo_rouge_metrics(self) -> Dict[str, Any]:
        """Демонстрирует ROUGE метрики."""
        print("\n📊 Демо: ROUGE метрики")

        # Симулируем ROUGE scores для разных текстов
        rouge_scores = []

        for i in range(10):
            # Генерируем случайные, но реалистичные ROUGE scores
            rouge1_f1 = random.uniform(0.2, 0.6)
            rouge2_f1 = random.uniform(
                0.1, rouge1_f1 * 0.8
            )  # ROUGE-2 обычно ниже ROUGE-1
            rougeL_f1 = random.uniform(rouge2_f1, rouge1_f1)  # ROUGE-L между ними

            rouge_scores.append(
                {"rouge1_f1": rouge1_f1, "rouge2_f1": rouge2_f1, "rougeL_f1": rougeL_f1}
            )

        # Агрегируем результаты
        avg_rouge1 = sum(s["rouge1_f1"] for s in rouge_scores) / len(rouge_scores)
        avg_rouge2 = sum(s["rouge2_f1"] for s in rouge_scores) / len(rouge_scores)
        avg_rougeL = sum(s["rougeL_f1"] for s in rouge_scores) / len(rouge_scores)

        results = {
            "status": "passed",
            "samples_evaluated": len(rouge_scores),
            "metrics": {
                "rouge1_f1": avg_rouge1,
                "rouge2_f1": avg_rouge2,
                "rougeL_f1": avg_rougeL,
            },
        }

        print(f"  📝 Образцов оценено: {len(rouge_scores)}")
        print(f"  📊 ROUGE-1 F1: {avg_rouge1:.3f}")
        print(f"  📊 ROUGE-2 F1: {avg_rouge2:.3f}")
        print(f"  📊 ROUGE-L F1: {avg_rougeL:.3f}")

        return results

    def demo_ab_testing(self) -> Dict[str, Any]:
        """Демонстрирует A/B тестирование промптов."""
        print("\n🧪 Демо: A/B тестирование промптов")

        variants = [
            {"name": "original", "description": "Базовый промпт"},
            {"name": "structured", "description": "Структурированный промпт"},
            {"name": "quality_focused", "description": "Промпт с акцентом на качество"},
        ]

        variant_results = {}

        for variant in variants:
            # Симулируем результаты для каждого варианта
            # Structured и quality_focused показывают лучшие результаты
            base_score = 0.7
            if variant["name"] == "structured":
                base_score = 0.75
            elif variant["name"] == "quality_focused":
                base_score = 0.8

            scores = {
                "completeness": random.uniform(base_score - 0.1, base_score + 0.1),
                "relevance": random.uniform(base_score - 0.05, base_score + 0.15),
                "specificity": random.uniform(base_score - 0.15, base_score + 0.05),
                "overall": 0,
            }
            scores["overall"] = (
                scores["completeness"] + scores["relevance"] + scores["specificity"]
            ) / 3

            variant_results[variant["name"]] = {
                "description": variant["description"],
                "scores": scores,
                "sample_size": 15,
            }

            print(
                f"  🔬 {variant['name']}: {scores['overall']:.3f} ({variant['description']})"
            )

        # Определяем лучший вариант
        best_variant = max(
            variant_results.items(), key=lambda x: x[1]["scores"]["overall"]
        )

        results = {
            "status": "passed",
            "variants_tested": len(variants),
            "best_variant": best_variant[0],
            "best_score": best_variant[1]["scores"]["overall"],
            "variant_results": variant_results,
        }

        print(
            f"  🏆 Лучший вариант: {best_variant[0]} ({best_variant[1]['scores']['overall']:.3f})"
        )

        return results

    def run_demo_suite(self) -> Dict[str, Any]:
        """Запускает полную демонстрацию системы тестирования."""
        print("🎭 ДЕМОНСТРАЦИЯ СИСТЕМЫ ТЕСТИРОВАНИЯ")
        print("=" * 50)
        print("📝 Используются синтетические данные для демонстрации")
        print("🔧 В реальном проекте тесты работают с вашими данными")
        print("=" * 50)

        start_time = time.time()

        # Запускаем все демо-тесты
        self.results["tests"]["comprehensive"] = self.demo_comprehensive_test()
        self.results["tests"]["performance"] = self.demo_performance_test()
        self.results["tests"]["rouge_metrics"] = self.demo_rouge_metrics()
        self.results["tests"]["ab_testing"] = self.demo_ab_testing()

        # Итоговая статистика
        total_time = time.time() - start_time
        passed_tests = sum(
            1
            for test in self.results["tests"].values()
            if test.get("status") == "passed"
        )

        self.results["summary"] = {
            "total_tests": len(self.results["tests"]),
            "passed_tests": passed_tests,
            "execution_time": total_time,
            "success_rate": passed_tests / len(self.results["tests"]),
        }

        print("\n" + "=" * 50)
        print("📋 ИТОГИ ДЕМОНСТРАЦИИ:")
        print(f"✅ Тестов выполнено: {passed_tests}/{len(self.results['tests'])}")
        print(f"⏱️ Время выполнения: {total_time:.1f}с")
        print(f"📊 Успешность: {self.results['summary']['success_rate']:.1%}")

        print(f"\n🎯 КЛЮЧЕВЫЕ ВОЗМОЖНОСТИ:")
        print(f"• Комплексная оценка качества анализа")
        print(f"• Детекция галлюцинаций в LLM")
        print(f"• ROUGE метрики для суммаризации")
        print(f"• Тестирование производительности")
        print(f"• A/B тестирование промптов")
        print(f"• Автоматическая генерация отчетов")

        return self.results

    def save_demo_results(self, output_path: Path):
        """Сохраняет результаты демонстрации."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Результаты демонстрации сохранены: {output_path}")


def main():
    print("🎭 Запуск демонстрации системы тестирования...")

    # Создаем демо-тестер
    demo = DemoTester()

    # Запускаем демонстрацию
    results = demo.run_demo_suite()

    # Сохраняем результаты
    output_path = Path("evaluation/demo_results.json")
    demo.save_demo_results(output_path)

    print(f"\n🎉 Демонстрация завершена!")
    print(f"\n📖 Для изучения реальных тестов:")
    print(f"• Посмотрите evaluation/README.md")
    print(f"• Запустите: python evaluation/run_all_tests.py --quick")
    print(f"• Изучите отдельные тесты в папке evaluation/")


if __name__ == "__main__":
    main()
