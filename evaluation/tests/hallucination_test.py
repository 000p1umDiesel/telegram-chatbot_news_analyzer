#!/usr/bin/env python3
"""
Тест детекции галлюцинаций в суммаризации.
"""

from typing import List, Dict, Any
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from .base_evaluator import BaseEvaluator


class HallucinationTest(BaseEvaluator):
    """Тест детекции галлюцинаций."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        self.hallucination_thresholds = [0.3, 0.5, 0.7]
        self._load_nli_model()

    def _load_nli_model(self):
        """Загрузка модели NLI для детекции галлюцинаций."""
        try:
            print("🔄 Загрузка NLI модели для детекции галлюцинаций...")
            model_name = "cointegrated/rubert-base-cased-nli-threeway"

            self.nli_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.nli_model = AutoModelForSequenceClassification.from_pretrained(
                model_name
            )

            # Создаем pipeline для удобства
            self.nli_pipeline = pipeline(
                "text-classification",
                model=self.nli_model,
                tokenizer=self.nli_tokenizer,
                device=0 if torch.cuda.is_available() else -1,
            )

            print("✅ NLI модель загружена")
        except Exception as e:
            print(f"❌ Ошибка загрузки NLI модели: {e}")
            self.nli_model = None
            self.nli_pipeline = None

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск тестов детекции галлюцинаций."""
        print("🔍 Запуск детекции галлюцинаций...")

        if not self.nli_pipeline:
            print("❌ NLI модель недоступна")
            return self.results

        # Извлекаем тексты и саммари
        texts = [item["text"] for item in data]
        summaries = [item["summary"] for item in data]

        # Анализируем галлюцинации
        hallucination_results = self._analyze_hallucinations(texts, summaries)

        self.results["metrics"] = hallucination_results
        self.results["details"] = {
            "samples_processed": len(data),
            "thresholds_used": self.hallucination_thresholds,
        }

        return self.results

    def _analyze_hallucinations(
        self, texts: List[str], summaries: List[str]
    ) -> Dict[str, Any]:
        """Анализ галлюцинаций в суммаризации."""
        entailment_scores = []
        hallucination_counts = {
            threshold: 0 for threshold in self.hallucination_thresholds
        }

        for text, summary in zip(texts, summaries):
            if not text or not summary:
                continue

            # Получаем оценку entailment
            entailment_score = self._get_entailment_score(text, summary)
            entailment_scores.append(entailment_score)

            # Проверяем по разным порогам
            for threshold in self.hallucination_thresholds:
                if entailment_score < threshold:
                    hallucination_counts[threshold] += 1

        total_samples = len(entailment_scores)

        results = {
            "entailment_score_mean": (
                np.mean(entailment_scores) if entailment_scores else 0.0
            ),
            "entailment_score_std": (
                np.std(entailment_scores) if entailment_scores else 0.0
            ),
            "entailment_score_min": (
                np.min(entailment_scores) if entailment_scores else 0.0
            ),
            "entailment_score_max": (
                np.max(entailment_scores) if entailment_scores else 0.0
            ),
        }

        # Добавляем показатели галлюцинаций по порогам
        for threshold in self.hallucination_thresholds:
            hallucination_rate = (
                hallucination_counts[threshold] / total_samples
                if total_samples > 0
                else 0
            )
            results[f"hallucination_rate_threshold_{threshold}"] = hallucination_rate

        return results

    def _get_entailment_score(self, premise: str, hypothesis: str) -> float:
        """Получение оценки entailment между текстом и суммари."""
        try:
            # Обрезаем тексты до разумной длины
            premise = premise[:512]
            hypothesis = hypothesis[:256]

            # Форматируем для NLI модели
            input_text = f"{premise} [SEP] {hypothesis}"

            # Получаем предсказание
            result = self.nli_pipeline(input_text)

            # Ищем класс entailment
            entailment_score = 0.0
            for prediction in result:
                if "entailment" in prediction["label"].lower():
                    entailment_score = prediction["score"]
                    break

            return float(entailment_score)

        except Exception as e:
            print(f"❌ Ошибка в _get_entailment_score: {e}")
            return 0.0

    def _generate_summary(self) -> str:
        """Генерация краткого резюме теста галлюцинаций."""
        metrics = self.results["metrics"]

        entailment_mean = metrics.get("entailment_score_mean", 0)
        hallucination_rate_05 = metrics.get("hallucination_rate_threshold_0.5", 0)

        return f"Entailment: {entailment_mean:.3f}, Hallucination Rate (0.5): {hallucination_rate_05:.3f}"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе анализа галлюцинаций."""
        metrics = self.results["metrics"]
        recommendations = []

        entailment_mean = metrics.get("entailment_score_mean", 0)
        hallucination_rate_05 = metrics.get("hallucination_rate_threshold_0.5", 0)

        if entailment_mean < 0.6:
            recommendations.append(
                "Низкий entailment score - модель часто создает суммари не соответствующие тексту"
            )

        if hallucination_rate_05 > 0.3:
            recommendations.append(
                "Высокий уровень галлюцинаций - необходимо улучшить контроль фактической точности"
            )

        if hallucination_rate_05 < 0.1:
            recommendations.append("Отличный контроль галлюцинаций!")

        if entailment_mean > 0.8:
            recommendations.append(
                "Превосходная логическая связность между текстом и суммари"
            )

        return recommendations
