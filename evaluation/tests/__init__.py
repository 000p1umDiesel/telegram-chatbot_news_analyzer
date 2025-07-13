"""
Модульные тесты для системы анализа новостей.
Разделенные компоненты для лучшей организации и поддержки.
"""

from .base_evaluator import BaseEvaluator
from .rouge_test import ROUGETest
from .semantic_test import SemanticTest
from .hallucination_test import HallucinationTest
from .hashtag_test import HashtagTest
from .sentiment_test import SentimentTest
from .ab_prompt_test import ABPromptTest
from .performance_test import PerformanceTest

__all__ = [
    "BaseEvaluator",
    "ROUGETest",
    "SemanticTest",
    "HallucinationTest",
    "HashtagTest",
    "SentimentTest",
    "ABPromptTest",
    "PerformanceTest",
]
