#!/usr/bin/env python3
"""
Модульный тест A/B тестирования промптов.
"""

from typing import List, Dict, Any
import numpy as np
import random
from .base_evaluator import BaseEvaluator


class ABPromptTest(BaseEvaluator):
    """Тест A/B тестирования промптов."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        self.prompt_variants = self._define_prompt_variants()

    def _define_prompt_variants(self) -> List[Dict[str, Any]]:
        """Определение вариантов промптов для тестирования."""
        return [
            {
                "name": "original",
                "description": "Базовый промпт",
                "system_prompt": "Ты аналитик новостей. Анализируй новости и создавай краткое содержание.",
                "temperature": 0.7,
            },
            {
                "name": "structured",
                "description": "Структурированный промпт",
                "system_prompt": """Ты эксперт-аналитик новостей. 
                
Твоя задача:
1. Внимательно прочитай новость
2. Выдели ключевые факты
3. Создай краткое, но информативное содержание
4. Определи тональность (позитивная/негативная/нейтральная)
5. Предложи релевантные хештеги""",
                "temperature": 0.5,
            },
            {
                "name": "quality_focused",
                "description": "Промпт с акцентом на качество",
                "system_prompt": """Ты высококвалифицированный журналист и аналитик.

Принципы работы:
- Точность превыше всего
- Сохраняй объективность
- Избегай домыслов и спекуляций
- Фокусируйся на фактах
- Создавай ценную для читателя информацию""",
                "temperature": 0.3,
            },
        ]

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск A/B тестирования промптов."""
        print("🔍 Запуск A/B тестирования промптов...")

        # Симулируем тестирование разных промптов
        variant_results = {}

        for variant in self.prompt_variants:
            variant_name = variant["name"]
            print(f"  🧪 Тестирование варианта: {variant_name}")

            # Симулируем анализ с данным промптом
            quality_score = self._simulate_prompt_quality(variant, data[:10])

            variant_results[variant_name] = {
                "description": variant["description"],
                "quality_score": quality_score,
                "temperature": variant["temperature"],
                "samples_tested": min(len(data), 10),
            }

        # Определяем лучший вариант
        best_variant = max(
            variant_results.keys(), key=lambda x: variant_results[x]["quality_score"]
        )

        self.results["metrics"] = {
            "variants_tested": len(variant_results),
            "best_variant": best_variant,
            "best_score": variant_results[best_variant]["quality_score"],
            "variant_results": variant_results,
        }

        self.results["details"] = {
            "samples_processed": min(len(data), 10),
            "variants": variant_results,
        }

        return self.results

    def _simulate_prompt_quality(
        self, variant: Dict[str, Any], sample_data: List[Dict[str, Any]]
    ) -> float:
        """Симулирует оценку качества промпта."""
        base_score = 0.6

        # Бонусы за характеристики промпта
        if "структур" in variant["description"].lower():
            base_score += 0.15

        if "качество" in variant["description"].lower():
            base_score += 0.12

        # Влияние temperature
        temp = variant["temperature"]
        if 0.3 <= temp <= 0.5:
            base_score += 0.08
        elif temp > 0.7:
            base_score -= 0.05

        # Добавляем случайную вариацию
        variation = random.uniform(-0.1, 0.1)
        final_score = max(0.0, min(1.0, base_score + variation))

        return round(final_score, 3)

    def _generate_summary(self) -> str:
        """Генерация краткого резюме A/B теста."""
        metrics = self.results["metrics"]
        best_variant = metrics.get("best_variant", "unknown")
        best_score = metrics.get("best_score", 0)

        return f"Лучший промпт: {best_variant} (score: {best_score:.3f})"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе A/B тестирования."""
        metrics = self.results["metrics"]
        recommendations = []

        best_variant = metrics.get("best_variant", "")
        best_score = metrics.get("best_score", 0)
        variant_results = metrics.get("variant_results", {})

        if best_score > 0.8:
            recommendations.append(
                f"Отличный результат! Используйте промпт '{best_variant}'"
            )
        elif best_score > 0.7:
            recommendations.append(
                f"Хорошие результаты с промптом '{best_variant}', но есть место для улучшений"
            )
        else:
            recommendations.append(
                "Все промпты показали низкие результаты - требуется доработка"
            )

        # Анализ различий между вариантами
        scores = [result["quality_score"] for result in variant_results.values()]
        if len(scores) > 1:
            score_std = np.std(scores)
            if score_std < 0.05:
                recommendations.append(
                    "Различия между промптами минимальны - оптимизируйте другие параметры"
                )
            elif score_std > 0.15:
                recommendations.append(
                    "Большие различия между промптами - выбор промпта критичен"
                )

        # Рекомендации по temperature
        for variant_name, result in variant_results.items():
            if result["quality_score"] == best_score:
                temp = result["temperature"]
                if temp <= 0.3:
                    recommendations.append(
                        "Низкая температура дает хорошие результаты - модель стабильна"
                    )
                elif temp >= 0.7:
                    recommendations.append(
                        "Высокая температура работает хорошо - модель креативна"
                    )

        return recommendations
