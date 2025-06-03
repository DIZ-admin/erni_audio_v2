#!/usr/bin/env python3
"""
Unit тесты для WER Evaluator
Тестирует функции расчета WER и CER
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock

from pipeline.wer_evaluator import (
    WERCalculator, 
    WERTranscriptionEvaluator, 
    TranscriptionResult, 
    QualityMetrics
)


class TestWERCalculator:
    """Тесты для WER калькулятора"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.calculator = WERCalculator()
    
    def test_normalize_text(self):
        """Тест нормализации текста"""
        # Базовая нормализация
        assert self.calculator.normalize_text("Привет, мир!") == "привет мир"
        
        # Удаление знаков препинания
        assert self.calculator.normalize_text("Это - тест... с пунктуацией?!") == "это тест с пунктуацией"
        
        # Множественные пробелы
        assert self.calculator.normalize_text("Много    пробелов   здесь") == "много пробелов здесь"
        
        # Пустая строка
        assert self.calculator.normalize_text("") == ""
        
        # Только знаки препинания
        assert self.calculator.normalize_text("!@#$%^&*()") == ""
    
    def test_calculate_edit_distance(self):
        """Тест расчета расстояния редактирования"""
        # Идентичные последовательности
        distance, _ = self.calculator.calculate_edit_distance(["a", "b", "c"], ["a", "b", "c"])
        assert distance == 0
        
        # Одна замена
        distance, _ = self.calculator.calculate_edit_distance(["a", "b", "c"], ["a", "x", "c"])
        assert distance == 1
        
        # Одна вставка
        distance, _ = self.calculator.calculate_edit_distance(["a", "b"], ["a", "x", "b"])
        assert distance == 1
        
        # Одно удаление
        distance, _ = self.calculator.calculate_edit_distance(["a", "b", "c"], ["a", "c"])
        assert distance == 1
        
        # Пустые последовательности
        distance, _ = self.calculator.calculate_edit_distance([], [])
        assert distance == 0
        
        # Одна пустая
        distance, _ = self.calculator.calculate_edit_distance(["a"], [])
        assert distance == 1
        
        distance, _ = self.calculator.calculate_edit_distance([], ["a"])
        assert distance == 1
    
    def test_calculate_wer_perfect_match(self):
        """Тест WER для идентичных текстов"""
        reference = "Привет мир как дела"
        hypothesis = "Привет мир как дела"
        
        wer = self.calculator.calculate_wer(reference, hypothesis)
        assert wer == 0.0
    
    def test_calculate_wer_complete_mismatch(self):
        """Тест WER для полностью разных текстов"""
        reference = "Привет мир"
        hypothesis = "Совсем другой текст"
        
        wer = self.calculator.calculate_wer(reference, hypothesis)
        assert wer == 1.0  # Максимальная ошибка
    
    def test_calculate_wer_partial_match(self):
        """Тест WER для частично совпадающих текстов"""
        reference = "Привет мир как дела"  # 4 слова
        hypothesis = "Привет мир хорошо"   # 3 слова, 2 совпадения
        
        wer = self.calculator.calculate_wer(reference, hypothesis)
        # Ожидаем 2 ошибки из 4 слов = 0.5
        assert 0.4 <= wer <= 0.6
    
    def test_calculate_wer_empty_reference(self):
        """Тест WER для пустого эталона"""
        wer = self.calculator.calculate_wer("", "некий текст")
        assert wer == 1.0
        
        wer = self.calculator.calculate_wer("", "")
        assert wer == 0.0
    
    def test_calculate_cer_perfect_match(self):
        """Тест CER для идентичных текстов"""
        reference = "Привет мир"
        hypothesis = "Привет мир"
        
        cer = self.calculator.calculate_cer(reference, hypothesis)
        assert cer == 0.0
    
    def test_calculate_cer_single_char_error(self):
        """Тест CER для одной ошибки символа"""
        reference = "Привет"  # 6 символов
        hypothesis = "Превет"  # 1 ошибка
        
        cer = self.calculator.calculate_cer(reference, hypothesis)
        # Ожидаем 1 ошибку из 6 символов ≈ 0.167
        assert 0.1 <= cer <= 0.2
    
    def test_calculate_metrics_comprehensive(self):
        """Комплексный тест расчета всех метрик"""
        reference = "Привет мир как дела"
        hypothesis = "Привет мир хорошо"
        
        metrics = self.calculator.calculate_metrics(reference, hypothesis)
        
        # Проверяем типы и диапазоны
        assert isinstance(metrics, QualityMetrics)
        assert 0.0 <= metrics.wer <= 1.0
        assert 0.0 <= metrics.cer <= 1.0
        assert 0.0 <= metrics.word_accuracy <= 1.0
        assert 0.0 <= metrics.char_accuracy <= 1.0
        
        # Проверяем соотношения
        assert metrics.word_accuracy == 1.0 - metrics.wer
        assert metrics.char_accuracy == 1.0 - metrics.cer
        
        # Проверяем подсчет слов и символов
        assert metrics.reference_words == 4
        assert metrics.hypothesis_words == 3
        assert metrics.reference_chars > 0
        assert metrics.hypothesis_chars > 0
    
    def test_metrics_to_dict(self):
        """Тест сериализации метрик в словарь"""
        metrics = QualityMetrics(
            wer=0.25,
            cer=0.15,
            word_accuracy=0.75,
            char_accuracy=0.85,
            reference_words=4,
            hypothesis_words=3,
            reference_chars=20,
            hypothesis_chars=18
        )
        
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert result["wer"] == 0.25
        assert result["cer"] == 0.15
        assert result["word_accuracy"] == 0.75
        assert result["char_accuracy"] == 0.85
        assert result["reference_words"] == 4
        assert result["hypothesis_words"] == 3


class TestTranscriptionResult:
    """Тесты для TranscriptionResult"""
    
    def test_full_text_property(self):
        """Тест свойства full_text"""
        segments = [
            {"text": "Привет"},
            {"text": "мир"},
            {"text": "как дела"}
        ]
        
        result = TranscriptionResult(
            model_name="test-model",
            segments=segments,
            processing_time=1.0,
            estimated_cost="$0.01",
            success=True
        )
        
        assert result.full_text == "Привет мир как дела"
    
    def test_full_text_empty_segments(self):
        """Тест full_text для пустых сегментов"""
        result = TranscriptionResult(
            model_name="test-model",
            segments=[],
            processing_time=1.0,
            estimated_cost="$0.01",
            success=False
        )
        
        assert result.full_text == ""
    
    def test_full_text_missing_text_fields(self):
        """Тест full_text для сегментов без поля text"""
        segments = [
            {"start": 0.0, "end": 1.0},  # Нет поля text
            {"text": "мир"},
            {"text": ""}  # Пустой text
        ]
        
        result = TranscriptionResult(
            model_name="test-model",
            segments=segments,
            processing_time=1.0,
            estimated_cost="$0.01",
            success=True
        )
        
        assert result.full_text == "мир"


class TestWERTranscriptionEvaluator:
    """Тесты для основного оценщика транскрипции"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.evaluator = WERTranscriptionEvaluator()
    
    def test_evaluate_successful_transcription(self):
        """Тест оценки успешной транскрипции"""
        reference_text = "Привет мир как дела"
        
        transcription_result = TranscriptionResult(
            model_name="test-model",
            segments=[
                {"text": "Привет мир"},
                {"text": "хорошо"}
            ],
            processing_time=2.5,
            estimated_cost="$0.05",
            success=True
        )
        
        evaluation = self.evaluator.evaluate_transcription(reference_text, transcription_result)
        
        assert evaluation["model"] == "test-model"
        assert evaluation["success"] is True
        assert evaluation["processing_time"] == 2.5
        assert evaluation["estimated_cost"] == "$0.05"
        assert evaluation["segments_count"] == 2
        assert "quality_metrics" in evaluation
        assert "transcribed_text" in evaluation
        
        # Проверяем метрики качества
        metrics = evaluation["quality_metrics"]
        assert "wer" in metrics
        assert "cer" in metrics
        assert "word_accuracy" in metrics
        assert "char_accuracy" in metrics
    
    def test_evaluate_failed_transcription(self):
        """Тест оценки неудачной транскрипции"""
        reference_text = "Привет мир"
        
        transcription_result = TranscriptionResult(
            model_name="test-model",
            segments=[],
            processing_time=1.0,
            estimated_cost="N/A",
            success=False,
            error="API Error"
        )
        
        evaluation = self.evaluator.evaluate_transcription(reference_text, transcription_result)
        
        assert evaluation["model"] == "test-model"
        assert evaluation["success"] is False
        assert evaluation["error"] == "API Error"
        assert evaluation["processing_time"] == 1.0
        assert "quality_metrics" not in evaluation
    
    def test_save_results(self):
        """Тест сохранения результатов"""
        results = {
            "test_data": "example",
            "model_results": {
                "model1": {"wer": 0.1},
                "model2": {"wer": 0.2}
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_results.json"
            
            self.evaluator.save_results(results, output_path)
            
            # Проверяем, что файл создан
            assert output_path.exists()
            
            # Проверяем содержимое
            with open(output_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            assert "evaluation_metadata" in saved_data
            assert "timestamp" in saved_data["evaluation_metadata"]
            assert "evaluator_version" in saved_data["evaluation_metadata"]
            assert saved_data["test_data"] == "example"


class TestIntegrationWER:
    """Интеграционные тесты для WER оценки"""
    
    def test_real_world_example_russian(self):
        """Тест с реальным примером на русском языке"""
        calculator = WERCalculator()
        
        reference = "Добро пожаловать на встречу по обсуждению проекта"
        hypothesis = "Добро пожаловать на встречу по обсуждению проектов"  # 1 ошибка
        
        wer = calculator.calculate_wer(reference, hypothesis)
        
        # Ожидаем 1 ошибку из 7 слов ≈ 0.143
        assert 0.1 <= wer <= 0.2
    
    def test_real_world_example_german(self):
        """Тест с реальным примером на немецком языке"""
        calculator = WERCalculator()
        
        reference = "Guten Tag willkommen zur Sitzung"
        hypothesis = "Guten Tag willkommen zu Sitzung"  # пропущен артикль "zur" -> "zu"
        
        wer = calculator.calculate_wer(reference, hypothesis)
        
        # Ожидаем 1 ошибку из 5 слов = 0.2
        assert 0.15 <= wer <= 0.25
    
    def test_punctuation_handling(self):
        """Тест обработки знаков препинания"""
        calculator = WERCalculator()
        
        reference = "Привет, мир! Как дела?"
        hypothesis = "Привет мир как дела"  # Без знаков препинания
        
        wer = calculator.calculate_wer(reference, hypothesis)
        
        # Должно быть 0, так как знаки препинания игнорируются
        assert wer == 0.0
    
    def test_case_insensitive(self):
        """Тест нечувствительности к регистру"""
        calculator = WERCalculator()
        
        reference = "ПРИВЕТ МИР"
        hypothesis = "привет мир"
        
        wer = calculator.calculate_wer(reference, hypothesis)
        assert wer == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
