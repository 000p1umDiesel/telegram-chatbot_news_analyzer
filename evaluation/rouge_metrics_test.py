#!/usr/bin/env python3
"""
Тест качества суммаризации с использованием ROUGE метрик.
Требует установки: pip install rouge-score
"""

import argparse
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
import numpy as np

try:
    from rouge_score import rouge_scorer

    ROUGE_AVAILABLE = True
except ImportError:
    print("⚠️ rouge-score не установлен. Установите: pip install rouge-score")
    ROUGE_AVAILABLE = False

try:
    import nltk
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

    nltk.download("punkt", quiet=True)
    BLEU_AVAILABLE = True
except ImportError:
    print("⚠️ NLTK не установлен для BLEU метрик")
    BLEU_AVAILABLE = False


class ROUGEEvaluator:
    """Оценка качества суммаризации с помощью ROUGE и других метрик."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

        if ROUGE_AVAILABLE:
            # Инициализируем ROUGE scorer
            self.rouge_scorer = rouge_scorer.RougeScorer(
                ["rouge1", "rouge2", "rougeL"], use_stemmer=True
            )

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "metrics_available": {"rouge": ROUGE_AVAILABLE, "bleu": BLEU_AVAILABLE},
        }

    def fetch_data_with_references(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получает данные для оценки ROUGE.
        В идеале нужны reference summaries, но будем использовать первые предложения как псевдо-референсы.
        """
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
                a.summary
            FROM messages m
            JOIN analyses a ON m.message_id = a.message_id
            WHERE m.text IS NOT NULL 
            AND a.summary IS NOT NULL
            AND LENGTH(m.text) > 100
            AND LENGTH(a.summary) > 20
            ORDER BY RANDOM() LIMIT ?
            """

            cursor = conn.execute(query, (limit,))
            rows = cursor.fetchall()
            conn.close()

            data = []
            for row in rows:
                # Создаем псевдо-референс из первых предложений оригинального текста
                text = row["text"]
                sentences = self._split_sentences(text)

                # Берем первые 2-3 предложения как референс
                reference_summary = ". ".join(sentences[: min(3, len(sentences))])

                data.append(
                    {
                        "message_id": row["message_id"],
                        "channel_id": row["channel_id"],
                        "original_text": text,
                        "generated_summary": row["summary"],
                        "reference_summary": reference_summary,
                    }
                )

            print(f"📊 Загружено {len(data)} образцов для ROUGE оценки")
            return data

        except Exception as e:
            print(f"❌ Ошибка при загрузке данных: {e}")
            return []

    def _split_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения."""
        try:
            import nltk

            sentences = nltk.sent_tokenize(text, language="russian")
        except:
            import re

            sentences = re.split(r"[.!?]+\s+", text)
            sentences = [s.strip() for s in sentences if s.strip()]

        return [s for s in sentences if len(s.split()) >= 5]

    def evaluate_rouge_scores(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Вычисляет ROUGE метрики."""
        print(f"\n🔍 Оценка ROUGE метрик ({len(data)} образцов)")

        if not ROUGE_AVAILABLE:
            return {"status": "skipped", "reason": "ROUGE not available"}

        rouge1_scores = {"precision": [], "recall": [], "fmeasure": []}
        rouge2_scores = {"precision": [], "recall": [], "fmeasure": []}
        rougeL_scores = {"precision": [], "recall": [], "fmeasure": []}

        detailed_results = []

        for i, item in enumerate(data):
            if i % 20 == 0 and i > 0:
                print(f"  📈 Обработано {i}/{len(data)} образцов...")

            generated = item["generated_summary"]
            reference = item["reference_summary"]

            try:
                # Вычисляем ROUGE scores
                scores = self.rouge_scorer.score(reference, generated)

                # Сохраняем scores
                rouge1_scores["precision"].append(scores["rouge1"].precision)
                rouge1_scores["recall"].append(scores["rouge1"].recall)
                rouge1_scores["fmeasure"].append(scores["rouge1"].fmeasure)

                rouge2_scores["precision"].append(scores["rouge2"].precision)
                rouge2_scores["recall"].append(scores["rouge2"].recall)
                rouge2_scores["fmeasure"].append(scores["rouge2"].fmeasure)

                rougeL_scores["precision"].append(scores["rougeL"].precision)
                rougeL_scores["recall"].append(scores["rougeL"].recall)
                rougeL_scores["fmeasure"].append(scores["rougeL"].fmeasure)

                detailed_results.append(
                    {
                        "message_id": item["message_id"],
                        "rouge1_f": scores["rouge1"].fmeasure,
                        "rouge2_f": scores["rouge2"].fmeasure,
                        "rougeL_f": scores["rougeL"].fmeasure,
                        "generated_length": len(generated.split()),
                        "reference_length": len(reference.split()),
                    }
                )

            except Exception as e:
                print(f"  ⚠️ Ошибка при вычислении ROUGE для образца {i}: {e}")
                continue

        # Агрегированная статистика
        if detailed_results:
            aggregated_scores = {
                "rouge1": {
                    "precision": np.mean(rouge1_scores["precision"]),
                    "recall": np.mean(rouge1_scores["recall"]),
                    "fmeasure": np.mean(rouge1_scores["fmeasure"]),
                },
                "rouge2": {
                    "precision": np.mean(rouge2_scores["precision"]),
                    "recall": np.mean(rouge2_scores["recall"]),
                    "fmeasure": np.mean(rouge2_scores["fmeasure"]),
                },
                "rougeL": {
                    "precision": np.mean(rougeL_scores["precision"]),
                    "recall": np.mean(rougeL_scores["recall"]),
                    "fmeasure": np.mean(rougeL_scores["fmeasure"]),
                },
            }

            print(f"  📊 ROUGE-1 F1: {aggregated_scores['rouge1']['fmeasure']:.3f}")
            print(f"  📊 ROUGE-2 F1: {aggregated_scores['rouge2']['fmeasure']:.3f}")
            print(f"  📊 ROUGE-L F1: {aggregated_scores['rougeL']['fmeasure']:.3f}")

            return {
                "status": "passed",
                "samples_evaluated": len(detailed_results),
                "aggregated_scores": aggregated_scores,
                "detailed_results": detailed_results[
                    :10
                ],  # Первые 10 для экономии места
            }
        else:
            return {"status": "failed", "reason": "No valid ROUGE scores computed"}

    def evaluate_bleu_scores(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Вычисляет BLEU метрики."""
        print(f"\n🔍 Оценка BLEU метрик ({len(data)} образцов)")

        if not BLEU_AVAILABLE:
            return {"status": "skipped", "reason": "BLEU not available"}

        bleu_scores = []
        smoothing_function = SmoothingFunction().method1

        for i, item in enumerate(data):
            if i % 20 == 0 and i > 0:
                print(f"  📈 Обработано {i}/{len(data)} образцов...")

            generated = item["generated_summary"].lower().split()
            reference = item["reference_summary"].lower().split()

            try:
                # Вычисляем BLEU score
                bleu_score = sentence_bleu(
                    [reference], generated, smoothing_function=smoothing_function
                )
                bleu_scores.append(bleu_score)

            except Exception as e:
                print(f"  ⚠️ Ошибка при вычислении BLEU для образца {i}: {e}")
                continue

        if bleu_scores:
            avg_bleu = np.mean(bleu_scores)
            std_bleu = np.std(bleu_scores)

            print(f"  📊 Средний BLEU: {avg_bleu:.3f} (±{std_bleu:.3f})")

            return {
                "status": "passed",
                "samples_evaluated": len(bleu_scores),
                "average_bleu": avg_bleu,
                "std_bleu": std_bleu,
                "bleu_scores": bleu_scores[:10],  # Первые 10
            }
        else:
            return {"status": "failed", "reason": "No valid BLEU scores computed"}

    def evaluate_length_consistency(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Оценивает консистентность длины саммари."""
        print(f"\n🔍 Анализ консистентности длины ({len(data)} образцов)")

        length_ratios = []
        absolute_lengths = []

        for item in data:
            orig_len = len(item["original_text"].split())
            summ_len = len(item["generated_summary"].split())

            if orig_len > 0:
                ratio = summ_len / orig_len
                length_ratios.append(ratio)
                absolute_lengths.append(summ_len)

        if length_ratios:
            stats = {
                "avg_length_ratio": np.mean(length_ratios),
                "std_length_ratio": np.std(length_ratios),
                "avg_absolute_length": np.mean(absolute_lengths),
                "std_absolute_length": np.std(absolute_lengths),
                "min_length": np.min(absolute_lengths),
                "max_length": np.max(absolute_lengths),
            }

            print(f"  📏 Средний коэффициент длины: {stats['avg_length_ratio']:.3f}")
            print(
                f"  📝 Средняя длина саммари: {stats['avg_absolute_length']:.1f} слов"
            )
            print(
                f"  📊 Диапазон длин: {stats['min_length']}-{stats['max_length']} слов"
            )

            # Анализ аномалий
            anomalies = []
            for i, ratio in enumerate(length_ratios):
                if ratio > 0.8:  # Саммари слишком длинное
                    anomalies.append(
                        f"Образец {i}: слишком длинное саммари (ratio: {ratio:.2f})"
                    )
                elif ratio < 0.05:  # Саммари слишком короткое
                    anomalies.append(
                        f"Образец {i}: слишком короткое саммари (ratio: {ratio:.2f})"
                    )

            if anomalies:
                print(f"  ⚠️ Обнаружено аномалий: {len(anomalies)}")

            return {
                "status": "passed",
                "statistics": stats,
                "anomalies_count": len(anomalies),
                "anomalies": anomalies[:5],  # Первые 5
            }
        else:
            return {"status": "failed", "reason": "No valid length data"}

    def run_comprehensive_rouge_evaluation(self, samples: int = 100) -> Dict[str, Any]:
        """Запускает комплексную оценку с ROUGE метриками."""
        print(f"🚀 Запуск комплексной ROUGE оценки")
        print(f"📊 Количество образцов: {samples}")
        print("=" * 50)

        # Загружаем данные
        data = self.fetch_data_with_references(samples)

        if not data:
            print("❌ Не удалось загрузить данные")
            return self.results

        # Запускаем тесты
        self.results["rouge_evaluation"] = self.evaluate_rouge_scores(data)
        self.results["bleu_evaluation"] = self.evaluate_bleu_scores(data)
        self.results["length_consistency"] = self.evaluate_length_consistency(data)

        # Итоги
        print("\n" + "=" * 50)
        print("📋 ИТОГИ ROUGE ОЦЕНКИ:")

        if self.results["rouge_evaluation"].get("status") == "passed":
            rouge_scores = self.results["rouge_evaluation"]["aggregated_scores"]
            print(f"📊 ROUGE-1 F1: {rouge_scores['rouge1']['fmeasure']:.3f}")
            print(f"📊 ROUGE-2 F1: {rouge_scores['rouge2']['fmeasure']:.3f}")
            print(f"📊 ROUGE-L F1: {rouge_scores['rougeL']['fmeasure']:.3f}")

        if self.results["bleu_evaluation"].get("status") == "passed":
            bleu_score = self.results["bleu_evaluation"]["average_bleu"]
            print(f"📊 BLEU: {bleu_score:.3f}")

        return self.results

    def save_results(self, output_path: Path):
        """Сохраняет результаты в JSON файл."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Конвертируем numpy типы в стандартные Python типы
        def convert_numpy_types(obj):
            if hasattr(obj, "item"):  # numpy scalar
                return obj.item()
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(v) for v in obj]
            else:
                return obj

        converted_results = convert_numpy_types(self.results)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(converted_results, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Результаты сохранены: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Оценка качества суммаризации с помощью ROUGE метрик"
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Количество образцов для оценки (по умолчанию: 100)",
    )

    parser.add_argument(
        "--db", type=Path, default=Path("data/storage.db"), help="Путь к базе данных"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/rouge_results.json"),
        help="Путь для сохранения результатов",
    )

    args = parser.parse_args()

    # Проверяем доступность библиотек
    if not ROUGE_AVAILABLE:
        print("❌ Для работы скрипта установите: pip install rouge-score")
        return

    # Запускаем оценку
    evaluator = ROUGEEvaluator(args.db)
    results = evaluator.run_comprehensive_rouge_evaluation(args.samples)

    # Сохраняем результаты
    evaluator.save_results(args.output)

    print(f"\n🎉 ROUGE оценка завершена!")


if __name__ == "__main__":
    main()
