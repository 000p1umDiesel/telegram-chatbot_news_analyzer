#!/usr/bin/env python3
"""
Тест качества хештегов: релевантность и разнообразие.
"""

from typing import List, Dict, Any, Set
import numpy as np
from collections import Counter
from sentence_transformers import SentenceTransformer
from .base_evaluator import BaseEvaluator


class HashtagTest(BaseEvaluator):
    """Тест качества хештегов."""

    def __init__(self, db_config: dict = None):
        super().__init__(db_config)
        self._load_models()

    def _load_models(self):
        """Загрузка моделей для анализа хештегов."""
        try:
            print("🔄 Загрузка модели для анализа хештегов...")
            self.sentence_model = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            print("✅ Модель для анализа хештегов загружена")
        except Exception as e:
            print(f"❌ Ошибка загрузки модели: {e}")
            self.sentence_model = None

    def run_test(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Запуск тестов качества хештегов."""
        print("🔍 Запуск анализа качества хештегов...")

        # Извлекаем тексты и хештеги
        texts = [item["text"] for item in data]
        hashtags_lists = [item["hashtags"] for item in data]

        # Анализируем качество хештегов
        hashtag_metrics = self._analyze_hashtag_quality(texts, hashtags_lists)

        self.results["metrics"] = hashtag_metrics
        self.results["details"] = {
            "samples_processed": len(data),
            "total_unique_hashtags": len(self._get_all_hashtags(hashtags_lists)),
            "average_hashtags_per_text": np.mean(
                [len(tags) for tags in hashtags_lists if tags]
            ),
        }

        return self.results

    def _analyze_hashtag_quality(
        self, texts: List[str], hashtags_lists: List[List[str]]
    ) -> Dict[str, float]:
        """Анализ качества хештегов."""
        relevance_scores = []
        diversity_scores = []
        coverage_scores = []

        for text, hashtags in zip(texts, hashtags_lists):
            if not text or not hashtags:
                continue

            # Релевантность хештегов к тексту
            relevance = self._compute_hashtag_relevance(text, hashtags)
            relevance_scores.append(relevance)

            # Разнообразие хештегов
            diversity = self._compute_hashtag_diversity(hashtags)
            diversity_scores.append(diversity)

            # Покрытие ключевых тем
            coverage = self._compute_topic_coverage(text, hashtags)
            coverage_scores.append(coverage)

        return {
            "hashtag_relevance_mean": (
                np.mean(relevance_scores) if relevance_scores else 0.0
            ),
            "hashtag_relevance_std": (
                np.std(relevance_scores) if relevance_scores else 0.0
            ),
            "hashtag_diversity_mean": (
                np.mean(diversity_scores) if diversity_scores else 0.0
            ),
            "hashtag_diversity_std": (
                np.std(diversity_scores) if diversity_scores else 0.0
            ),
            "topic_coverage_mean": np.mean(coverage_scores) if coverage_scores else 0.0,
            "topic_coverage_std": np.std(coverage_scores) if coverage_scores else 0.0,
            "samples_with_hashtags": len(relevance_scores),
        }

    def _compute_hashtag_relevance(self, text: str, hashtags: List[str]) -> float:
        """Вычисление релевантности хештегов к тексту."""
        if not self.sentence_model or not hashtags:
            return 0.0

        try:
            # Получаем embedding текста
            text_embedding = self.sentence_model.encode([text[:500]])[0]

            # Получаем embeddings хештегов
            hashtag_texts = [f"#{tag}" for tag in hashtags]
            hashtag_embeddings = self.sentence_model.encode(hashtag_texts)

            # Вычисляем среднее косинусное сходство
            similarities = []
            for hashtag_emb in hashtag_embeddings:
                similarity = np.dot(text_embedding, hashtag_emb) / (
                    np.linalg.norm(text_embedding) * np.linalg.norm(hashtag_emb)
                )
                similarities.append(float(similarity))

            return np.mean(similarities) if similarities else 0.0

        except Exception as e:
            print(f"❌ Ошибка в _compute_hashtag_relevance: {e}")
            return 0.0

    def _compute_hashtag_diversity(self, hashtags: List[str]) -> float:
        """Вычисление разнообразия хештегов."""
        if not hashtags:
            return 0.0

        # Уникальность хештегов
        unique_ratio = len(set(hashtags)) / len(hashtags)

        # Разнообразие длин хештегов
        lengths = [len(tag) for tag in hashtags]
        length_std = np.std(lengths) if len(lengths) > 1 else 0

        # Нормализуем std длины (максимальная полезная std ~ 5)
        normalized_length_diversity = min(length_std / 5.0, 1.0)

        # Комбинируем метрики
        diversity_score = (unique_ratio + normalized_length_diversity) / 2

        return float(diversity_score)

    def _compute_topic_coverage(self, text: str, hashtags: List[str]) -> float:
        """Вычисление покрытия ключевых тем в тексте."""
        if not hashtags:
            return 0.0

        # Простая эвристика: проверяем наличие ключевых слов из текста в хештегах
        text_words = set(text.lower().split())
        hashtag_words = set()

        for tag in hashtags:
            hashtag_words.update(tag.lower().split())

        # Находим пересечение
        common_words = text_words.intersection(hashtag_words)

        # Вычисляем покрытие
        if len(text_words) == 0:
            return 0.0

        coverage = len(common_words) / min(
            len(text_words), 20
        )  # Ограничиваем до 20 слов
        return min(coverage, 1.0)

    def _get_all_hashtags(self, hashtags_lists: List[List[str]]) -> Set[str]:
        """Получение всех уникальных хештегов."""
        all_hashtags = set()
        for hashtags in hashtags_lists:
            if hashtags:
                all_hashtags.update(hashtags)
        return all_hashtags

    def _generate_summary(self) -> str:
        """Генерация краткого резюме теста хештегов."""
        metrics = self.results["metrics"]

        relevance = metrics.get("hashtag_relevance_mean", 0)
        diversity = metrics.get("hashtag_diversity_mean", 0)
        coverage = metrics.get("topic_coverage_mean", 0)

        return f"Relevance: {relevance:.3f}, Diversity: {diversity:.3f}, Coverage: {coverage:.3f}"

    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе анализа хештегов."""
        metrics = self.results["metrics"]
        recommendations = []

        relevance = metrics.get("hashtag_relevance_mean", 0)
        diversity = metrics.get("hashtag_diversity_mean", 0)
        coverage = metrics.get("topic_coverage_mean", 0)

        if relevance < 0.5:
            recommendations.append(
                "Низкая релевантность хештегов - улучшите соответствие хештегов содержанию текста"
            )

        if diversity < 0.6:
            recommendations.append(
                "Низкое разнообразие хештегов - добавляйте больше уникальных и разнообразных хештегов"
            )

        if coverage < 0.3:
            recommendations.append(
                "Низкое покрытие тем - хештеги не покрывают ключевые темы из текста"
            )

        if all(score > 0.7 for score in [relevance, diversity, coverage]):
            recommendations.append("Отличное качество хештегов!")

        return recommendations
