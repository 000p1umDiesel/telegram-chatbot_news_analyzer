#!/usr/bin/env python3
"""
Тест семантических метрик: BERTScore и semantic similarity.
"""

from typing import List, Dict, Any
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from .base_evaluator import BaseEvaluator

# Исправленный импорт и использование bert_score
try:
    import importlib.util

    bert_score_module = importlib.util.find_spec("bert_score")
    if bert_score_module is not None:
        from bert_score import score as bert_score

        BERT_SCORE_AVAILABLE = True
    else:
        bert_score = None
        BERT_SCORE_AVAILABLE = False
except ImportError:
    bert_score = None
    BERT_SCORE_AVAILABLE = False


class SemanticTest(BaseEvaluator):
    """Тест семантических метрик."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        self._load_models()

    def _load_models(self):
        """Загрузка моделей для семантического анализа."""
        try:
            print("🔄 Загрузка модели для семантического анализа...")
            try:
                self.sentence_model = SentenceTransformer(
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                )
            except Exception as e:
                print(
                    f"⚠️ Не удалось загрузить paraphrase-multilingual-MiniLM-L12-v2: {e}"
                )
                print("🔄 Пробую fallback: all-MiniLM-L6-v2...")
                self.sentence_model = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2"
                )
            print("✅ Модель semantic similarity загружена")
        except Exception as e:
            print(f"❌ Ошибка загрузки semantic similarity модели: {e}")
            self.sentence_model = None

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск семантических тестов."""
        print("🔍 Запуск семантических метрик...")

        # Извлекаем тексты и саммари
        texts = [item["text"] for item in data]
        summaries = [item["summary"] for item in data]

        metrics = {}

        # Semantic similarity
        if self.sentence_model is not None:
            semantic_results = self._compute_semantic_similarity(texts, summaries)
            metrics.update(semantic_results)

        # BERTScore
        if BERT_SCORE_AVAILABLE:
            bert_results = self._compute_bert_scores(texts, summaries)
            metrics.update(bert_results)
        else:
            print("⚠️ BERTScore недоступен")

        self.results["metrics"] = metrics
        self.results["details"] = {
            "samples_processed": len(data),
            "bert_score_available": BERT_SCORE_AVAILABLE,
            "semantic_model_available": self.sentence_model is not None,
        }

        return self.results

    def _compute_semantic_similarity(
        self, texts: List[str], summaries: List[str]
    ) -> Dict[str, float]:
        """Вычисление семантического сходства."""
        print("🔄 Вычисление semantic similarity...")

        similarities = []

        if self.sentence_model is not None:
            for text, summary in zip(texts, summaries):
                if text and summary:
                    text_snippet = text[:500]
                    embeddings = self.sentence_model.encode([text_snippet, summary])
                    similarity = float(
                        np.dot(embeddings[0], embeddings[1])
                        / (
                            np.linalg.norm(embeddings[0])
                            * np.linalg.norm(embeddings[1])
                        )
                    )
                    similarities.append(similarity)

        return {
            "semantic_similarity_mean": (
                float(np.mean(similarities)) if similarities else 0.0
            ),
            "semantic_similarity_std": (
                float(np.std(similarities)) if similarities else 0.0
            ),
            "semantic_similarity_min": (
                float(np.min(similarities)) if similarities else 0.0
            ),
            "semantic_similarity_max": (
                float(np.max(similarities)) if similarities else 0.0
            ),
        }

    def _compute_bert_scores(
        self, texts: List[str], summaries: List[str]
    ) -> Dict[str, float]:
        """Вычисление BERTScore метрик."""
        print("🔄 Вычисление BERTScore...")
        if not BERT_SCORE_AVAILABLE or bert_score is None:
            print("⚠️ BERTScore не установлен или не импортирован")
            return {
                "bert_score_precision_mean": 0.0,
                "bert_score_recall_mean": 0.0,
                "bert_score_f1_mean": 0.0,
                "bert_score_precision_std": 0.0,
                "bert_score_recall_std": 0.0,
                "bert_score_f1_std": 0.0,
            }
        references = []
        for text in texts:
            sentences = text.split(".")[:3]
            reference = ". ".join(sentences).strip()
            references.append(reference if reference else text[:200])
        P, R, F1 = bert_score(summaries, references, lang="ru", verbose=False)
        return {
            "bert_score_precision_mean": float(P.mean()),
            "bert_score_recall_mean": float(R.mean()),
            "bert_score_f1_mean": float(F1.mean()),
            "bert_score_precision_std": float(P.std()),
            "bert_score_recall_std": float(R.std()),
            "bert_score_f1_std": float(F1.std()),
        }

    def _generate_summary(self) -> str:
        """Генерация краткого резюме семантического теста."""
        metrics = self.results["metrics"]

        semantic_sim = metrics.get("semantic_similarity_mean", 0)
        bert_f1 = metrics.get("bert_score_f1_mean", 0)

        return f"Semantic Similarity: {semantic_sim:.3f}, BERTScore F1: {bert_f1:.3f}"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе семантических метрик."""
        metrics = self.results["metrics"]
        recommendations = []

        semantic_sim = metrics.get("semantic_similarity_mean", 0)
        bert_f1 = metrics.get("bert_score_f1_mean", 0)

        if semantic_sim < 0.6:
            recommendations.append(
                "Низкое семантическое сходство - улучшите соответствие смысла суммари оригинальному тексту"
            )

        if bert_f1 < 0.7:
            recommendations.append(
                "Низкий BERTScore F1 - работайте над качеством контекстного понимания"
            )

        if semantic_sim > 0.8:
            recommendations.append("Отличное семантическое сходство!")

        if bert_f1 > 0.85:
            recommendations.append(
                "Превосходный BERTScore - модель хорошо понимает контекст"
            )

        return recommendations
