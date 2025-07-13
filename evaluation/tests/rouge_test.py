#!/usr/bin/env python3
"""
Тест ROUGE метрик для оценки качества суммаризации.
"""

from typing import List, Dict, Any
import numpy as np
from rouge_score import rouge_scorer
from .base_evaluator import BaseEvaluator


class ROUGETest(BaseEvaluator):
    """Тест ROUGE метрик для суммаризации."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        self.rouge_scorer = rouge_scorer.RougeScorer(
            ["rouge1", "rouge2", "rougeL"], use_stemmer=True
        )

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск ROUGE тестов."""
        print("🔍 Запуск ROUGE метрик...")

        # Извлекаем тексты и саммари
        texts = [item["text"] for item in data]
        summaries = [item["summary"] for item in data]

        # Вычисляем ROUGE метрики
        rouge_results = self._compute_rouge_scores(texts, summaries)

        self.results["metrics"] = rouge_results
        self.results["details"] = {
            "samples_processed": len(data),
            "average_text_length": np.mean([len(text) for text in texts]),
            "average_summary_length": np.mean([len(summary) for summary in summaries]),
        }

        return self.results

    def _compute_rouge_scores(
        self, texts: List[str], summaries: List[str]
    ) -> Dict[str, float]:
        """Вычисление ROUGE метрик."""
        rouge_1_scores = []
        rouge_2_scores = []
        rouge_l_scores = []

        for text, summary in zip(texts, summaries):
            # Используем первые предложения текста как эталон
            sentences = text.split(".")[:3]  # Первые 3 предложения
            reference = ". ".join(sentences).strip()

            if reference and summary:
                scores = self.rouge_scorer.score(reference, summary)
                rouge_1_scores.append(scores["rouge1"].fmeasure)
                rouge_2_scores.append(scores["rouge2"].fmeasure)
                rouge_l_scores.append(scores["rougeL"].fmeasure)

        return {
            "rouge_1_mean": np.mean(rouge_1_scores) if rouge_1_scores else 0.0,
            "rouge_1_std": np.std(rouge_1_scores) if rouge_1_scores else 0.0,
            "rouge_2_mean": np.mean(rouge_2_scores) if rouge_2_scores else 0.0,
            "rouge_2_std": np.std(rouge_2_scores) if rouge_2_scores else 0.0,
            "rouge_l_mean": np.mean(rouge_l_scores) if rouge_l_scores else 0.0,
            "rouge_l_std": np.std(rouge_l_scores) if rouge_l_scores else 0.0,
            "samples_count": len(rouge_1_scores),
        }

    def _generate_summary(self) -> str:
        """Генерация краткого резюме ROUGE теста."""
        metrics = self.results["metrics"]
        rouge_1 = metrics.get("rouge_1_mean", 0)
        rouge_2 = metrics.get("rouge_2_mean", 0)
        rouge_l = metrics.get("rouge_l_mean", 0)

        return f"ROUGE-1: {rouge_1:.3f}, ROUGE-2: {rouge_2:.3f}, ROUGE-L: {rouge_l:.3f}"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе ROUGE метрик."""
        metrics = self.results["metrics"]
        recommendations = []

        rouge_1 = metrics.get("rouge_1_mean", 0)
        rouge_2 = metrics.get("rouge_2_mean", 0)
        rouge_l = metrics.get("rouge_l_mean", 0)

        if rouge_1 < 0.3:
            recommendations.append(
                "ROUGE-1 низкий - улучшите точность лексических совпадений"
            )

        if rouge_2 < 0.2:
            recommendations.append(
                "ROUGE-2 низкий - работайте над качеством биграмм в суммаризации"
            )

        if rouge_l < 0.25:
            recommendations.append(
                "ROUGE-L низкий - улучшите структурное сходство суммари с оригиналом"
            )

        if all(score > 0.4 for score in [rouge_1, rouge_2, rouge_l]):
            recommendations.append(
                "Отличные ROUGE метрики! Модель хорошо справляется с суммаризацией"
            )

        return recommendations
