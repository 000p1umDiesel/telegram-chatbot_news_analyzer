#!/usr/bin/env python3
"""
Комплексный скрипт для тестирования системы анализа новостей.
Включает оценку галлюцинаций, качества суммаризации, sentiment analysis и другие тесты.

Использование:
    python evaluation/comprehensive_test.py --samples 50
    python evaluation/comprehensive_test.py --samples 100 --save-report
    python evaluation/comprehensive_test.py --channel durov --samples 30
"""

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict, Counter
from dataclasses import dataclass
import numpy as np

import nltk
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

try:
    from transformers.pipelines import pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Скачиваем необходимые данные NLTK
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    print("Скачиваем NLTK punkt tokenizer...")
    nltk.download("punkt", quiet=True)

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    print("Скачиваем NLTK stopwords...")
    nltk.download("stopwords", quiet=True)

# Константы
DEFAULT_NLI_MODEL = "cointegrated/rubert-base-cased-nli-threeway"
HALLUCINATION_THRESHOLDS = [0.3, 0.5, 0.7]


@dataclass
class HallucinationExample:
    """Пример галлюцинации для детального анализа"""

    message_id: int
    channel: str
    original_text: str
    summary: str
    entailment_score: float
    is_hallucination: bool
    threshold: float
    analysis_type: str  # 'sentence' или 'full_text'

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "channel": self.channel,
            "original_text": (
                self.original_text[:200] + "..."
                if len(self.original_text) > 200
                else self.original_text
            ),
            "summary": self.summary,
            "entailment_score": float(self.entailment_score),
            "is_hallucination": self.is_hallucination,
            "threshold": self.threshold,
            "analysis_type": self.analysis_type,
        }


class NewsAnalysisEvaluator:
    """Комплексная система оценки качества анализа новостей."""

    def __init__(self, db_path: Path = Path("data/storage.db")):
        self.db_path = db_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        print(f"🔧 Инициализация evaluator...")
        print(f"📱 Устройство: {self.device}")
        print(f"🗄️ База данных: {self.db_path}")

        # Загружаем модель NLI для проверки галлюцинаций
        self.nli_tokenizer = None
        self.nli_model = None
        self._load_nli_model()

        # Результаты тестов
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "device": str(self.device),
            "database_path": str(self.db_path),
            "tests": {},
        }

    def _load_nli_model(self):
        """Загружает NLI модель для проверки галлюцинаций."""
        try:
            print(f"🤖 Загружаем NLI модель: {DEFAULT_NLI_MODEL}")
            self.nli_tokenizer = AutoTokenizer.from_pretrained(DEFAULT_NLI_MODEL)
            self.nli_model = AutoModelForSequenceClassification.from_pretrained(
                DEFAULT_NLI_MODEL
            )
            self.nli_model.to(self.device)
            self.nli_model.eval()
            print("✅ NLI модель загружена успешно")
        except Exception as e:
            print(f"❌ Ошибка загрузки NLI модели: {e}")
            print("⚠️ Тесты галлюцинаций будут пропущены")

    def fetch_test_data(
        self, limit: int = 100, channel_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получает данные для тестирования из базы данных."""
        if not self.db_path.exists():
            print(f"❌ База данных не найдена: {self.db_path}")
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            query = """
            SELECT 
                m.message_id,
                m.text,
                m.channel_id,
                m.channel_title,
                m.channel_username,
                m.date,
                a.summary,
                a.sentiment,
                a.hashtags
            FROM messages m
            JOIN analyses a ON m.message_id = a.message_id
            WHERE m.text IS NOT NULL 
            AND a.summary IS NOT NULL
            AND LENGTH(m.text) > 50
            AND LENGTH(a.summary) > 10
            """

            params = []
            if channel_filter:
                query += " AND m.channel_id = ?"
                params.append(channel_filter)

            query += " ORDER BY RANDOM() LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            data = [dict(row) for row in rows]
            print(f"📊 Загружено {len(data)} образцов для тестирования")
            return data

        except Exception as e:
            print(f"❌ Ошибка при загрузке данных: {e}")
            return []

    def test_database_integrity(self) -> Dict[str, Any]:
        """Тест целостности базы данных."""
        print("\n🔍 Тест 1: Проверка целостности базы данных")

        if not self.db_path.exists():
            return {"status": "failed", "error": "Database file not found"}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Проверяем структуру таблиц
            tables_info = {}
            for table in ["messages", "analyses", "subscribers", "channels"]:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                tables_info[table] = count
                print(f"  📋 {table}: {count} записей")

            # Проверяем связность данных
            cursor.execute(
                """
                SELECT COUNT(*) FROM messages m 
                JOIN analyses a ON m.message_id = a.message_id
            """
            )
            linked_count = cursor.fetchone()[0]

            # Проверяем качество данных
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN LENGTH(text) < 10 THEN 1 ELSE 0 END) as short_texts,
                    SUM(CASE WHEN LENGTH(summary) < 5 THEN 1 ELSE 0 END) as short_summaries,
                    SUM(CASE WHEN sentiment IS NULL THEN 1 ELSE 0 END) as missing_sentiment
                FROM messages m 
                JOIN analyses a ON m.message_id = a.message_id
            """
            )
            quality_stats = cursor.fetchone()

            conn.close()

            result = {
                "status": "passed",
                "tables_info": tables_info,
                "linked_records": linked_count,
                "data_quality": {
                    "total_records": quality_stats[0],
                    "short_texts": quality_stats[1],
                    "short_summaries": quality_stats[2],
                    "missing_sentiment": quality_stats[3],
                },
            }

            print(f"  ✅ Связанных записей: {linked_count}")
            print(
                f"  📊 Качество данных: {quality_stats[1]} коротких текстов, {quality_stats[2]} коротких саммари"
            )

            return result

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def test_hallucination_detection(
        self, data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Улучшенный тест обнаружения галлюцинаций с двумя подходами."""
        print(f"\n🔍 Тест 2: Обнаружение галлюцинаций ({len(data)} образцов)")

        if not self.nli_model:
            return {"status": "skipped", "reason": "NLI model not available"}

        start_time = time.time()

        # Результаты для двух типов анализа
        sentence_results = []
        fulltext_results = []
        hallucination_examples = []

        for i, item in enumerate(data):
            if i % 20 == 0 and i > 0:
                print(f"  📈 Обработано {i}/{len(data)} образцов...")

            premise = item["text"]
            summary = item["summary"]
            message_id = item["message_id"]
            channel = item["channel_id"]

            # 1. SENTENCE-LEVEL АНАЛИЗ (как было раньше)
            sentences = self._split_sentences(summary)
            sentence_scores = []

            for sentence in sentences:
                if len(sentence.strip()) > 5:
                    score = self._get_entailment_score(premise, sentence.strip())
                    sentence_scores.append(score)

            if sentence_scores:
                sentence_result = {
                    "message_id": message_id,
                    "channel": channel,
                    "text_length": len(premise.split()),
                    "summary_length": len(summary.split()),
                    "sentences_count": len(sentence_scores),
                    "avg_entailment": np.mean(sentence_scores),
                    "min_entailment": np.min(sentence_scores),
                    "max_entailment": np.max(sentence_scores),
                }

                # Вычисляем hallucination rates для разных порогов (sentence-level)
                for threshold in HALLUCINATION_THRESHOLDS:
                    hallucinated = sum(
                        1 for score in sentence_scores if score < threshold
                    )
                    sentence_result[f"hallucination_rate_{threshold}"] = (
                        hallucinated / len(sentence_scores)
                    )

                sentence_results.append(sentence_result)

            # 2. FULL-TEXT АНАЛИЗ (новый подход)
            fulltext_score = self._get_entailment_score(premise[:512], summary[:256])

            fulltext_result = {
                "message_id": message_id,
                "channel": channel,
                "text_length": len(premise.split()),
                "summary_length": len(summary.split()),
                "entailment_score": fulltext_score,
            }

            # Определяем галлюцинации для каждого порога (full-text)
            for threshold in HALLUCINATION_THRESHOLDS:
                is_hallucination = fulltext_score < threshold
                fulltext_result[f"is_hallucination_{threshold}"] = is_hallucination

                # Собираем примеры галлюцинаций для детального анализа
                if (
                    is_hallucination and len(hallucination_examples) < 15
                ):  # Ограничиваем количество примеров
                    example = HallucinationExample(
                        message_id=message_id,
                        channel=channel,
                        original_text=premise,
                        summary=summary,
                        entailment_score=fulltext_score,
                        is_hallucination=is_hallucination,
                        threshold=threshold,
                        analysis_type="full_text",
                    )
                    hallucination_examples.append(example)

            fulltext_results.append(fulltext_result)

        # Агрегированная статистика для sentence-level
        sentence_stats = {}
        if sentence_results:
            sentence_stats = self._compute_hallucination_stats(sentence_results)
            sentence_stats["analysis_type"] = "sentence_level"

        # Агрегированная статистика для full-text
        fulltext_stats = {}
        if fulltext_results:
            fulltext_stats = {
                "analysis_type": "full_text",
                "samples_count": len(fulltext_results),
                "avg_entailment": np.mean(
                    [r["entailment_score"] for r in fulltext_results]
                ),
                "std_entailment": np.std(
                    [r["entailment_score"] for r in fulltext_results]
                ),
                "min_entailment": np.min(
                    [r["entailment_score"] for r in fulltext_results]
                ),
                "max_entailment": np.max(
                    [r["entailment_score"] for r in fulltext_results]
                ),
            }

            # Статистика по порогам для full-text
            for threshold in HALLUCINATION_THRESHOLDS:
                hallucinations = [
                    r for r in fulltext_results if r[f"is_hallucination_{threshold}"]
                ]
                fulltext_stats[f"hallucination_count_{threshold}"] = len(hallucinations)
                fulltext_stats[f"hallucination_rate_{threshold}"] = len(
                    hallucinations
                ) / len(fulltext_results)

        execution_time = time.time() - start_time

        # Вывод результатов
        print(f"  ⏱️ Время выполнения: {execution_time:.1f}с")

        if sentence_stats:
            print(f"  📝 SENTENCE-LEVEL анализ:")
            print(
                f"    🎯 Средний entailment score: {sentence_stats['avg_entailment']:.3f}"
            )
            for threshold in HALLUCINATION_THRESHOLDS:
                rate = sentence_stats[f"avg_hallucination_rate_{threshold}"]
                print(f"    🚨 Галлюцинации (порог {threshold}): {rate:.1%}")

        if fulltext_stats:
            print(f"  📄 FULL-TEXT анализ:")
            print(
                f"    🎯 Средний entailment score: {fulltext_stats['avg_entailment']:.3f}"
            )
            for threshold in HALLUCINATION_THRESHOLDS:
                rate = fulltext_stats[f"hallucination_rate_{threshold}"]
                print(f"    🚨 Галлюцинации (порог {threshold}): {rate:.1%}")

        if hallucination_examples:
            print(f"  📋 Найдено {len(hallucination_examples)} примеров галлюцинаций")

        return {
            "status": "passed",
            "execution_time": execution_time,
            "samples_processed": len(data),
            "sentence_level_analysis": {
                "statistics": sentence_stats,
                "detailed_results": sentence_results[:5],  # Первые 5 для экономии места
            },
            "full_text_analysis": {
                "statistics": fulltext_stats,
                "detailed_results": fulltext_results[:5],  # Первые 5 для экономии места
            },
            "hallucination_examples": [
                ex.to_dict() for ex in hallucination_examples[:10]
            ],  # Топ-10 примеров
        }

    def test_sentiment_consistency(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Тест консистентности sentiment analysis."""
        print(f"\n🔍 Тест 3: Консистентность sentiment analysis ({len(data)} образцов)")

        sentiment_distribution = Counter()
        sentiment_by_channel = defaultdict(Counter)
        text_length_by_sentiment = defaultdict(list)

        for item in data:
            sentiment = item.get("sentiment", "Unknown")
            channel = item.get("channel_id", "Unknown")
            text_length = len(item.get("text", "").split())

            sentiment_distribution[sentiment] += 1
            sentiment_by_channel[channel][sentiment] += 1
            text_length_by_sentiment[sentiment].append(text_length)

        # Анализ распределения
        total_samples = len(data)
        sentiment_stats = {}

        for sentiment, count in sentiment_distribution.items():
            percentage = (count / total_samples) * 100
            avg_text_length = (
                np.mean(text_length_by_sentiment[sentiment])
                if text_length_by_sentiment[sentiment]
                else 0
            )

            sentiment_stats[sentiment] = {
                "count": count,
                "percentage": percentage,
                "avg_text_length": avg_text_length,
            }

            print(
                f"  📊 {sentiment}: {count} ({percentage:.1f}%), средняя длина: {avg_text_length:.0f} слов"
            )

        # Проверка на аномалии
        anomalies = []

        # Проверяем, нет ли каналов с очень странным распределением тональности
        for channel, channel_sentiments in sentiment_by_channel.items():
            if sum(channel_sentiments.values()) >= 5:  # Минимум 5 образцов для анализа
                positive_ratio = channel_sentiments.get("Позитивная", 0) / sum(
                    channel_sentiments.values()
                )
                negative_ratio = channel_sentiments.get("Негативная", 0) / sum(
                    channel_sentiments.values()
                )

                if positive_ratio > 0.8:
                    anomalies.append(
                        f"Канал {channel}: слишком много позитивных новостей ({positive_ratio:.1%})"
                    )
                elif negative_ratio > 0.8:
                    anomalies.append(
                        f"Канал {channel}: слишком много негативных новостей ({negative_ratio:.1%})"
                    )

        result = {
            "status": "passed",
            "total_samples": total_samples,
            "sentiment_distribution": dict(sentiment_distribution),
            "sentiment_statistics": sentiment_stats,
            "channels_analyzed": len(sentiment_by_channel),
            "anomalies": anomalies,
        }

        if anomalies:
            print(f"  ⚠️ Обнаружено аномалий: {len(anomalies)}")
            for anomaly in anomalies[:3]:  # Показываем первые 3
                print(f"    • {anomaly}")
        else:
            print("  ✅ Аномалий в распределении тональности не обнаружено")

        return result

    def test_summarization_quality(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Тест качества суммаризации."""
        print(f"\n🔍 Тест 4: Качество суммаризации ({len(data)} образцов)")

        compression_ratios = []
        word_overlaps = []
        summary_lengths = []

        for item in data:
            original_text = item["text"]
            summary = item["summary"]

            # Анализ длины
            orig_words = len(original_text.split())
            summ_words = len(summary.split())

            if orig_words > 0:
                compression_ratio = 1 - (summ_words / orig_words)
                compression_ratios.append(compression_ratio)
                summary_lengths.append(summ_words)

                # Анализ пересечения слов (extractiveness)
                orig_words_set = set(original_text.lower().split())
                summ_words_set = set(summary.lower().split())

                if summ_words_set:
                    word_overlap = len(orig_words_set & summ_words_set) / len(
                        summ_words_set
                    )
                    word_overlaps.append(word_overlap)

        # Статистика
        stats = {
            "avg_compression_ratio": (
                np.mean(compression_ratios) if compression_ratios else 0
            ),
            "std_compression_ratio": (
                np.std(compression_ratios) if compression_ratios else 0
            ),
            "avg_summary_length": np.mean(summary_lengths) if summary_lengths else 0,
            "avg_word_overlap": np.mean(word_overlaps) if word_overlaps else 0,
            "samples_analyzed": len(compression_ratios),
        }

        print(f"  📏 Средний коэффициент сжатия: {stats['avg_compression_ratio']:.1%}")
        print(f"  📝 Средняя длина саммари: {stats['avg_summary_length']:.0f} слов")
        print(f"  🔗 Среднее пересечение слов: {stats['avg_word_overlap']:.1%}")

        # Оценка качества
        quality_issues = []

        if stats["avg_compression_ratio"] < 0.3:
            quality_issues.append("Низкий коэффициент сжатия - саммари слишком длинные")
        elif stats["avg_compression_ratio"] > 0.9:
            quality_issues.append(
                "Слишком высокий коэффициент сжатия - саммари могут быть слишком короткими"
            )

        if stats["avg_word_overlap"] < 0.3:
            quality_issues.append(
                "Низкое пересечение слов - возможно много галлюцинаций"
            )
        elif stats["avg_word_overlap"] > 0.8:
            quality_issues.append(
                "Высокое пересечение слов - саммари слишком extractive"
            )

        result = {
            "status": "passed",
            "statistics": stats,
            "quality_issues": quality_issues,
        }

        if quality_issues:
            print(f"  ⚠️ Обнаружено проблем качества: {len(quality_issues)}")
            for issue in quality_issues:
                print(f"    • {issue}")
        else:
            print("  ✅ Серьезных проблем с качеством суммаризации не обнаружено")

        return result

    def test_hashtag_relevance(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Тест релевантности хештегов."""
        print(f"\n🔍 Тест 5: Релевантность хештегов ({len(data)} образцов)")

        hashtag_counter = Counter()
        hashtags_per_message = []

        for item in data:
            hashtags_str = item.get("hashtags", "")
            if hashtags_str:
                try:
                    # Парсим JSON или разделяем по запятым
                    if hashtags_str.startswith("["):
                        hashtags = json.loads(hashtags_str)
                    else:
                        hashtags = [tag.strip() for tag in hashtags_str.split(",")]

                    hashtags_per_message.append(len(hashtags))
                    for tag in hashtags:
                        if tag:
                            hashtag_counter[tag.lower().replace("#", "")] += 1
                except:
                    hashtags_per_message.append(0)
            else:
                hashtags_per_message.append(0)

        # Статистика
        most_common_hashtags = hashtag_counter.most_common(10)
        avg_hashtags_per_message = (
            np.mean(hashtags_per_message) if hashtags_per_message else 0
        )

        print(
            f"  🏷️ Среднее количество хештегов на сообщение: {avg_hashtags_per_message:.1f}"
        )
        print(f"  📊 Топ-5 хештегов:")

        for i, (tag, count) in enumerate(most_common_hashtags[:5], 1):
            percentage = (count / len(data)) * 100
            print(f"    {i}. #{tag}: {count} ({percentage:.1f}%)")

        # Проверка качества
        quality_issues = []

        if avg_hashtags_per_message < 1:
            quality_issues.append("Слишком мало хештегов на сообщение")
        elif avg_hashtags_per_message > 7:
            quality_issues.append("Слишком много хештегов на сообщение")

        # Проверяем разнообразие
        unique_hashtags = len(hashtag_counter)
        if unique_hashtags < 10:
            quality_issues.append("Слишком мало уникальных хештегов")

        result = {
            "status": "passed",
            "avg_hashtags_per_message": avg_hashtags_per_message,
            "unique_hashtags_count": unique_hashtags,
            "most_common_hashtags": most_common_hashtags,
            "quality_issues": quality_issues,
        }

        if quality_issues:
            print(f"  ⚠️ Проблемы с хештегами: {len(quality_issues)}")
            for issue in quality_issues:
                print(f"    • {issue}")
        else:
            print("  ✅ Качество хештегов в норме")

        return result

    def _split_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения."""
        try:
            sentences = nltk.sent_tokenize(text, language="russian")
        except:
            import re

            sentences = re.split(r"[.!?]+\s+", text)
            sentences = [s.strip() for s in sentences if s.strip()]

        return [s for s in sentences if len(s.split()) >= 3]

    def _get_entailment_score(self, premise: str, hypothesis: str) -> float:
        """Получение entailment score с помощью NLI модели."""
        if not self.nli_tokenizer or not self.nli_model:
            return 0.0

        try:
            # Ограничиваем длину текста
            premise = premise[:512]
            hypothesis = hypothesis[:256]

            # Токенизация
            inputs = self.nli_tokenizer.encode_plus(
                premise,
                hypothesis,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=512,
            )

            # Предсказание
            with torch.no_grad():
                outputs = self.nli_model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

                # Индекс для entailment (обычно 0 для этой модели)
                entailment_score = predictions[0][0].item()

            return entailment_score

        except Exception as e:
            print(f"⚠️ Ошибка получения entailment score: {e}")
            return 0.0

    def _compute_hallucination_stats(self, results: List[Dict]) -> Dict[str, Any]:
        """Вычисляет статистику по галлюцинациям."""
        stats = {
            "samples_count": len(results),
            "avg_entailment": np.mean([r["avg_entailment"] for r in results]),
            "std_entailment": np.std([r["avg_entailment"] for r in results]),
            "avg_text_length": np.mean([r["text_length"] for r in results]),
            "avg_summary_length": np.mean([r["summary_length"] for r in results]),
        }

        # Статистика по порогам
        for threshold in HALLUCINATION_THRESHOLDS:
            rates = [r[f"hallucination_rate_{threshold}"] for r in results]
            stats[f"avg_hallucination_rate_{threshold}"] = np.mean(rates)
            stats[f"median_hallucination_rate_{threshold}"] = np.median(rates)
            stats[f"std_hallucination_rate_{threshold}"] = np.std(rates)

        return stats

    def run_all_tests(
        self, samples: int = 100, channel_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Запускает все тесты."""
        print(f"🚀 Запуск комплексного тестирования системы анализа новостей")
        print(f"📊 Количество образцов: {samples}")
        if channel_filter:
            print(f"📺 Фильтр по каналу: {channel_filter}")
        print("=" * 60)

        start_time = time.time()

        # Тест 1: Целостность базы данных
        self.test_results["tests"][
            "database_integrity"
        ] = self.test_database_integrity()

        # Загружаем данные для остальных тестов
        test_data = self.fetch_test_data(samples, channel_filter)

        if not test_data:
            print("❌ Не удалось загрузить данные для тестирования")
            return self.test_results

        # Тест 2: Обнаружение галлюцинаций
        self.test_results["tests"]["hallucination_detection"] = (
            self.test_hallucination_detection(test_data)
        )

        # Тест 3: Консистентность sentiment analysis
        self.test_results["tests"]["sentiment_consistency"] = (
            self.test_sentiment_consistency(test_data)
        )

        # Тест 4: Качество суммаризации
        self.test_results["tests"]["summarization_quality"] = (
            self.test_summarization_quality(test_data)
        )

        # Тест 5: Релевантность хештегов
        self.test_results["tests"]["hashtag_relevance"] = self.test_hashtag_relevance(
            test_data
        )

        # Общая статистика
        total_time = time.time() - start_time
        self.test_results["execution_summary"] = {
            "total_execution_time": total_time,
            "samples_tested": len(test_data),
            "tests_run": len(self.test_results["tests"]),
            "tests_passed": sum(
                1
                for test in self.test_results["tests"].values()
                if test.get("status") == "passed"
            ),
            "tests_failed": sum(
                1
                for test in self.test_results["tests"].values()
                if test.get("status") == "failed"
            ),
            "tests_skipped": sum(
                1
                for test in self.test_results["tests"].values()
                if test.get("status") == "skipped"
            ),
        }

        # Выводим итоги
        print("\n" + "=" * 60)
        print("📋 ИТОГИ ТЕСТИРОВАНИЯ:")
        summary = self.test_results["execution_summary"]
        print(f"⏱️ Общее время выполнения: {summary['total_execution_time']:.1f}с")
        print(f"📊 Образцов протестировано: {summary['samples_tested']}")
        print(f"✅ Тестов пройдено: {summary['tests_passed']}")
        print(f"❌ Тестов провалено: {summary['tests_failed']}")
        print(f"⏭️ Тестов пропущено: {summary['tests_skipped']}")

        return self.test_results

    def save_report(self, output_path: Path):
        """Сохраняет детальный отчет о тестировании."""
        # JSON отчет
        json_path = output_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)

        # Текстовый отчет
        txt_path = output_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            self._write_text_report(f)

        print(f"\n💾 Отчеты сохранены:")
        print(f"  📄 JSON: {json_path}")
        print(f"  📝 TXT: {txt_path}")

    def _write_text_report(self, f):
        """Записывает текстовый отчет."""
        f.write("🔍 КОМПЛЕКСНЫЙ ОТЧЕТ ПО ТЕСТИРОВАНИЮ СИСТЕМЫ АНАЛИЗА НОВОСТЕЙ\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"📅 Дата тестирования: {self.test_results['timestamp']}\n")
        f.write(f"💻 Устройство: {self.test_results['device']}\n")
        f.write(f"🗄️ База данных: {self.test_results['database_path']}\n\n")

        # Итоги
        if "execution_summary" in self.test_results:
            summary = self.test_results["execution_summary"]
            f.write("📊 ИТОГИ ТЕСТИРОВАНИЯ:\n")
            f.write("-" * 30 + "\n")
            f.write(f"⏱️ Время выполнения: {summary['total_execution_time']:.1f}с\n")
            f.write(f"📝 Образцов протестировано: {summary['samples_tested']}\n")
            f.write(f"✅ Тестов пройдено: {summary['tests_passed']}\n")
            f.write(f"❌ Тестов провалено: {summary['tests_failed']}\n")
            f.write(f"⏭️ Тестов пропущено: {summary['tests_skipped']}\n\n")

        # Детали по каждому тесту
        for test_name, test_result in self.test_results.get("tests", {}).items():
            f.write(f"🔍 ТЕСТ: {test_name.upper()}\n")
            f.write("-" * 40 + "\n")
            f.write(f"Статус: {test_result.get('status', 'unknown')}\n")

            if test_result.get("status") == "failed":
                f.write(f"Ошибка: {test_result.get('error', 'Unknown error')}\n")
            elif test_result.get("status") == "skipped":
                f.write(
                    f"Причина пропуска: {test_result.get('reason', 'Unknown reason')}\n"
                )

            # Специальная обработка для теста галлюцинаций
            if (
                test_name == "hallucination_detection"
                and test_result.get("status") == "passed"
            ):
                f.write("📝 SENTENCE-LEVEL АНАЛИЗ:\n")
                if (
                    "sentence_level_analysis" in test_result
                    and "statistics" in test_result["sentence_level_analysis"]
                ):
                    stats = test_result["sentence_level_analysis"]["statistics"]
                    f.write(
                        f"  Средний entailment score: {stats.get('avg_entailment', 0):.3f}\n"
                    )
                    for threshold in HALLUCINATION_THRESHOLDS:
                        rate = stats.get(f"avg_hallucination_rate_{threshold}", 0)
                        f.write(f"  Галлюцинации (порог {threshold}): {rate:.1%}\n")

                f.write("\n📄 FULL-TEXT АНАЛИЗ:\n")
                if (
                    "full_text_analysis" in test_result
                    and "statistics" in test_result["full_text_analysis"]
                ):
                    stats = test_result["full_text_analysis"]["statistics"]
                    f.write(
                        f"  Средний entailment score: {stats.get('avg_entailment', 0):.3f}\n"
                    )
                    f.write(
                        f"  Стандартное отклонение: {stats.get('std_entailment', 0):.3f}\n"
                    )
                    for threshold in HALLUCINATION_THRESHOLDS:
                        rate = stats.get(f"hallucination_rate_{threshold}", 0)
                        count = stats.get(f"hallucination_count_{threshold}", 0)
                        f.write(
                            f"  Галлюцинации (порог {threshold}): {rate:.1%} ({count} из {stats.get('samples_count', 0)})\n"
                        )

                # Примеры галлюцинаций
                if (
                    "hallucination_examples" in test_result
                    and test_result["hallucination_examples"]
                ):
                    f.write(
                        f"\n📋 ПРИМЕРЫ ГАЛЛЮЦИНАЦИЙ ({len(test_result['hallucination_examples'])}):\n"
                    )
                    for i, example in enumerate(
                        test_result["hallucination_examples"][:3], 1
                    ):
                        f.write(f"  Пример {i}:\n")
                        f.write(
                            f"    ID: {example['message_id']}, Канал: {example['channel']}\n"
                        )
                        f.write(
                            f"    Entailment score: {example['entailment_score']:.3f}\n"
                        )
                        f.write(f"    Порог: {example['threshold']}\n")
                        f.write(f"    Оригинал: {example['original_text'][:100]}...\n")
                        f.write(f"    Саммари: {example['summary']}\n\n")

            # Обычная обработка статистики для других тестов
            elif "statistics" in test_result:
                f.write("Статистика:\n")
                for key, value in test_result["statistics"].items():
                    if isinstance(value, float):
                        f.write(f"  {key}: {value:.3f}\n")
                    else:
                        f.write(f"  {key}: {value}\n")

            f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Комплексное тестирование системы анализа новостей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python evaluation/comprehensive_test.py --samples 50
  python evaluation/comprehensive_test.py --samples 100 --save-report
  python evaluation/comprehensive_test.py --channel durov --samples 30 --save-report
        """,
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=50,
        help="Количество образцов для тестирования (по умолчанию: 50)",
    )

    parser.add_argument(
        "--channel", type=str, default=None, help="Фильтр по конкретному каналу"
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/storage.db"),
        help="Путь к базе данных (по умолчанию: data/storage.db)",
    )

    parser.add_argument(
        "--save-report", action="store_true", help="Сохранить детальный отчет в файлы"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/test_report"),
        help="Путь для сохранения отчета (без расширения)",
    )

    args = parser.parse_args()

    # Создаем evaluator и запускаем тесты
    evaluator = NewsAnalysisEvaluator(args.db)
    results = evaluator.run_all_tests(samples=args.samples, channel_filter=args.channel)

    # Сохраняем отчет если нужно
    if args.save_report:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        evaluator.save_report(args.output)

    print(f"\n🎉 Тестирование завершено!")


if __name__ == "__main__":
    main()
