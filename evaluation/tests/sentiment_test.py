#!/usr/bin/env python3
"""
Тест качества sentiment анализа: точность и консистентность.
"""

from typing import List, Dict, Any
import numpy as np
from collections import Counter
from .base_evaluator import BaseEvaluator


class SentimentTest(BaseEvaluator):
    """Тест качества sentiment анализа."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        # Ключевые слова для эвристической оценки sentiment
        self.positive_keywords = {
            "хорошо",
            "отлично",
            "прекрасно",
            "замечательно",
            "успех",
            "победа",
            "рост",
            "улучшение",
            "развитие",
            "достижение",
            "позитивно",
        }
        self.negative_keywords = {
            "плохо",
            "ужасно",
            "проблема",
            "кризис",
            "снижение",
            "падение",
            "ухудшение",
            "негативно",
            "упадок",
            "неудача",
            "провал",
        }

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск тестов sentiment анализа."""
        print("🔍 Запуск анализа качества sentiment...")

        # Извлекаем тексты и sentiment
        texts = [item["text"] for item in data]
        sentiments = [item["sentiment"] for item in data]

        # Анализируем качество sentiment
        sentiment_metrics = self._analyze_sentiment_quality(texts, sentiments)

        self.results["metrics"] = sentiment_metrics
        self.results["details"] = {
            "samples_processed": len(data),
            "sentiment_distribution": self._get_sentiment_distribution(sentiments),
        }

        return self.results

    def _analyze_sentiment_quality(
        self, texts: List[str], sentiments: List[str]
    ) -> Dict[str, float]:
        """Анализ качества sentiment анализа."""
        accuracy_scores = []
        consistency_scores = []

        for text, sentiment in zip(texts, sentiments):
            if not text or not sentiment:
                continue

            # Точность sentiment (сравнение с эвристической оценкой)
            accuracy = self._compute_sentiment_accuracy(text, sentiment)
            accuracy_scores.append(accuracy)

            # Консистентность sentiment
            consistency = self._compute_sentiment_consistency(text, sentiment)
            consistency_scores.append(consistency)

        return {
            "sentiment_accuracy_mean": (
                np.mean(accuracy_scores) if accuracy_scores else 0.0
            ),
            "sentiment_accuracy_std": (
                np.std(accuracy_scores) if accuracy_scores else 0.0
            ),
            "sentiment_consistency_mean": (
                np.mean(consistency_scores) if consistency_scores else 0.0
            ),
            "sentiment_consistency_std": (
                np.std(consistency_scores) if consistency_scores else 0.0
            ),
            "samples_with_sentiment": len(accuracy_scores),
        }

    def _compute_sentiment_accuracy(self, text: str, predicted_sentiment: str) -> float:
        """Вычисление точности sentiment на основе эвристик."""
        text_lower = text.lower()

        # Подсчитываем позитивные и негативные слова
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)

        # Определяем ожидаемый sentiment
        if positive_count > negative_count:
            expected_sentiment = "positive"
        elif negative_count > positive_count:
            expected_sentiment = "negative"
        else:
            expected_sentiment = "neutral"

        # Нормализуем predicted_sentiment
        predicted_lower = predicted_sentiment.lower()
        if any(
            pos in predicted_lower
            for pos in ["positive", "позитивный", "положительный"]
        ):
            predicted_normalized = "positive"
        elif any(
            neg in predicted_lower
            for neg in ["negative", "негативный", "отрицательный"]
        ):
            predicted_normalized = "negative"
        else:
            predicted_normalized = "neutral"

        # Вычисляем точность
        if expected_sentiment == predicted_normalized:
            return 1.0
        elif expected_sentiment == "neutral":
            return 0.5  # Частичная точность для нейтрального
        else:
            return 0.0

    def _compute_sentiment_consistency(self, text: str, sentiment: str) -> float:
        """Вычисление консистентности sentiment."""
        text_lower = text.lower()
        sentiment_lower = sentiment.lower()

        # Подсчитываем эмоциональные индикаторы в тексте
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)

        total_emotional_words = positive_count + negative_count

        if total_emotional_words == 0:
            # Нет явных эмоциональных слов - neutral должен быть консистентен
            if "neutral" in sentiment_lower or "нейтральный" in sentiment_lower:
                return 1.0
            else:
                return 0.5

        # Вычисляем эмоциональный вес
        emotional_balance = (positive_count - negative_count) / total_emotional_words

        # Проверяем консистентность с предсказанным sentiment
        if emotional_balance > 0.3 and any(
            pos in sentiment_lower for pos in ["positive", "позитивный"]
        ):
            return 1.0
        elif emotional_balance < -0.3 and any(
            neg in sentiment_lower for neg in ["negative", "негативный"]
        ):
            return 1.0
        elif abs(emotional_balance) <= 0.3 and "neutral" in sentiment_lower:
            return 1.0
        else:
            # Частичная консистентность
            return max(0.0, 1.0 - abs(emotional_balance))

    def _get_sentiment_distribution(self, sentiments: List[str]) -> Dict[str, int]:
        """Получение распределения sentiment."""
        sentiment_counts = Counter()

        for sentiment in sentiments:
            if sentiment:
                sentiment_lower = sentiment.lower()
                if any(
                    pos in sentiment_lower
                    for pos in ["positive", "позитивный", "положительный"]
                ):
                    sentiment_counts["positive"] += 1
                elif any(
                    neg in sentiment_lower
                    for neg in ["negative", "негативный", "отрицательный"]
                ):
                    sentiment_counts["negative"] += 1
                else:
                    sentiment_counts["neutral"] += 1

        return dict(sentiment_counts)

    def _generate_summary(self) -> str:
        """Генерация краткого резюме sentiment теста."""
        metrics = self.results["metrics"]

        accuracy = metrics.get("sentiment_accuracy_mean", 0)
        consistency = metrics.get("sentiment_consistency_mean", 0)

        return f"Accuracy: {accuracy:.3f}, Consistency: {consistency:.3f}"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе анализа sentiment."""
        metrics = self.results["metrics"]
        details = self.results["details"]
        recommendations = []

        accuracy = metrics.get("sentiment_accuracy_mean", 0)
        consistency = metrics.get("sentiment_consistency_mean", 0)

        if accuracy < 0.6:
            recommendations.append(
                "Низкая точность sentiment анализа - улучшите алгоритм определения эмоциональной окраски"
            )

        if consistency < 0.7:
            recommendations.append(
                "Низкая консистентность sentiment - работайте над стабильностью анализа"
            )

        # Анализ распределения
        distribution = details.get("sentiment_distribution", {})
        total_samples = sum(distribution.values())

        if total_samples > 0:
            neutral_ratio = distribution.get("neutral", 0) / total_samples
            if neutral_ratio > 0.8:
                recommendations.append(
                    "Слишком много нейтральных sentiment - возможно, модель слишком консервативна"
                )
            elif neutral_ratio < 0.1:
                recommendations.append(
                    "Слишком мало нейтральных sentiment - возможно, модель слишком категорична"
                )

        if accuracy > 0.8 and consistency > 0.8:
            recommendations.append("Отличное качество sentiment анализа!")

        return recommendations
