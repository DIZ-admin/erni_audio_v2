# tests/test_refactored_merge_agent.py

import pytest
from typing import List, Dict, Any
from unittest.mock import Mock, patch

from pipeline.merge_agent import MergeAgent, MergeMetrics


class TestRefactoredMergeAgent:
    """Тесты для рефакторированного MergeAgent."""

    @pytest.fixture
    def agent(self):
        """Создает экземпляр MergeAgent для тестов."""
        return MergeAgent(merge_strategy="best_overlap")

    @pytest.fixture
    def sample_diar_segments(self):
        """Создает образцы диаризационных сегментов."""
        return [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
            {"start": 4.0, "end": 6.0, "speaker": "SPEAKER_00"}
        ]

    @pytest.fixture
    def sample_asr_segments(self):
        """Создает образцы ASR сегментов."""
        return [
            {"start": 0.5, "end": 1.5, "text": "Привет мир"},
            {"start": 2.5, "end": 3.5, "text": "Как дела"},
            {"start": 4.5, "end": 5.5, "text": "Отлично"}
        ]

    def test_initialization_with_base_classes(self, agent):
        """Тест инициализации с базовыми классами."""
        # Проверяем, что агент наследует от всех базовых классов
        assert hasattr(agent, 'log_with_emoji')  # BaseAgent
        assert hasattr(agent, 'validate_audio_file')  # ValidationMixin
        
        # Проверяем инициализацию
        assert agent.name == "MergeAgent"
        assert agent.merge_strategy == "best_overlap"
        assert agent.min_overlap_threshold == 0.1
        assert agent.confidence_threshold == 0.5

    def test_validate_segment_valid(self, agent):
        """Тест валидации корректного сегмента."""
        valid_segment = {
            "start": 0.0,
            "end": 2.0,
            "speaker": "SPEAKER_00",
            "text": "Test text"
        }
        
        issues = agent.validate_segment(valid_segment, 0)
        assert len(issues) == 0

    def test_validate_segment_missing_fields(self, agent):
        """Тест валидации сегмента с отсутствующими полями."""
        invalid_segment = {
            "text": "Test text"
            # Отсутствуют start и end
        }
        
        issues = agent.validate_segment(invalid_segment, 0)
        assert len(issues) >= 2  # Должны быть ошибки для start и end
        assert any("отсутствует поле 'start'" in issue for issue in issues)
        assert any("отсутствует поле 'end'" in issue for issue in issues)

    def test_validate_segment_invalid_timestamps(self, agent):
        """Тест валидации сегмента с некорректными временными метками."""
        invalid_segment = {
            "start": 2.0,
            "end": 1.0,  # end < start
            "speaker": "SPEAKER_00"
        }
        
        issues = agent.validate_segment(invalid_segment, 0)
        assert len(issues) >= 1
        assert any("некорректные временные метки" in issue for issue in issues)

    def test_validate_segment_negative_timestamps(self, agent):
        """Тест валидации сегмента с отрицательными временными метками."""
        invalid_segment = {
            "start": -1.0,
            "end": 1.0,
            "speaker": "SPEAKER_00"
        }
        
        issues = agent.validate_segment(invalid_segment, 0)
        assert len(issues) >= 1
        assert any("отрицательное время начала" in issue for issue in issues)

    def test_validate_segment_wrong_types(self, agent):
        """Тест валидации сегмента с неправильными типами данных."""
        invalid_segment = {
            "start": "0.0",  # Строка вместо числа
            "end": "2.0",    # Строка вместо числа
            "speaker": 123   # Число вместо строки
        }
        
        issues = agent.validate_segment(invalid_segment, 0)
        assert len(issues) >= 3
        assert any("'start' должно быть числом" in issue for issue in issues)
        assert any("'end' должно быть числом" in issue for issue in issues)
        assert any("'speaker' должно быть строкой" in issue for issue in issues)

    def test_validate_segments_overlap(self, agent):
        """Тест проверки пересечений между сегментами."""
        overlapping_segments = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 1.5, "end": 3.0, "speaker": "SPEAKER_01"}  # Пересекается с предыдущим
        ]
        
        issues = agent.validate_segments_overlap(overlapping_segments)
        assert len(issues) >= 1
        assert any("пересечение" in issue for issue in issues)

    def test_validate_segments_comprehensive(self, agent, sample_diar_segments, sample_asr_segments):
        """Тест комплексной валидации сегментов."""
        # Валидные сегменты
        diar_issues = agent.validate_segments(sample_diar_segments)
        asr_issues = agent.validate_segments(sample_asr_segments)
        
        assert len(diar_issues) == 0
        assert len(asr_issues) == 0

    def test_run_with_performance_metrics(self, agent, sample_diar_segments, sample_asr_segments):
        """Тест выполнения с отслеживанием метрик производительности."""
        # Выполняем слияние
        result = agent.run(sample_diar_segments, sample_asr_segments)
        
        # Проверяем результат
        assert len(result) == len(sample_asr_segments)
        assert all("speaker" in seg for seg in result)
        assert all("confidence" in seg for seg in result)
        
        # Проверяем, что метрики были обновлены
        assert agent._operation_count > 0
        assert agent._error_count == 0
        
        # Проверяем метрики производительности
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] >= 1
        assert metrics['success_rate'] == 100.0

    def test_run_with_error_handling(self, agent):
        """Тест обработки ошибок через BaseAgent."""
        # Передаем некорректные данные
        invalid_diar = [{"invalid": "data"}]
        invalid_asr = [{"invalid": "data"}]
        
        # Должно обработать ошибки gracefully
        with pytest.raises(Exception):
            agent.run(invalid_diar, invalid_asr)
        
        # Проверяем, что ошибка была зарегистрирована
        assert agent._error_count > 0

    def test_run_empty_inputs(self, agent):
        """Тест выполнения с пустыми входными данными."""
        # Пустые ASR сегменты
        result = agent.run([], [])
        assert result == []
        
        # Пустые диаризационные сегменты
        asr_segments = [{"start": 0.0, "end": 1.0, "text": "test"}]
        result = agent.run([], asr_segments)
        assert len(result) == 1
        assert result[0]["speaker"] == "UNK"

    def test_unified_logging_usage(self, agent):
        """Тест использования унифицированного логирования."""
        # Проверяем, что метод log_with_emoji доступен
        assert hasattr(agent, 'log_with_emoji')
        
        # Тестируем вызов (не должен вызывать ошибок)
        agent.log_with_emoji("info", "🎯", "Test message")

    def test_merge_strategies(self, agent):
        """Тест различных стратегий слияния."""
        strategies = agent.get_merge_strategies()
        assert "best_overlap" in strategies
        assert "weighted" in strategies
        assert "majority_vote" in strategies
        
        # Тестируем смену стратегии
        agent.set_merge_strategy("weighted")
        assert agent.merge_strategy == "weighted"
        
        # Тестируем невалидную стратегию
        with pytest.raises(ValueError):
            agent.set_merge_strategy("invalid_strategy")

    def test_calculate_overlap(self, agent):
        """Тест расчета пересечений."""
        seg1 = {"start": 0.0, "end": 2.0}
        seg2 = {"start": 1.0, "end": 3.0}
        
        overlap_duration, overlap_ratio = agent.calculate_overlap(seg1, seg2)
        
        assert overlap_duration == 1.0  # Пересечение 1 секунда
        assert overlap_ratio == 0.5     # 50% от длительности seg1

    def test_merge_segments_best_overlap(self, agent, sample_diar_segments):
        """Тест слияния сегментов с стратегией best_overlap."""
        asr_seg = {"start": 0.5, "end": 1.5, "text": "Test text"}
        
        merged = agent.merge_segments(asr_seg, sample_diar_segments)
        
        assert merged["speaker"] == "SPEAKER_00"  # Должен выбрать первого спикера
        assert merged["text"] == "Test text"
        assert "confidence" in merged

    def test_post_processing(self, agent):
        """Тест постобработки сегментов."""
        segments = [
            {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "Hello", "confidence": 0.8},
            {"start": 1.1, "end": 2.0, "speaker": "SPEAKER_00", "text": "world", "confidence": 0.9},  # Близкий сегмент того же спикера
            {"start": 3.0, "end": 4.0, "speaker": "SPEAKER_01", "text": "Different speaker", "confidence": 0.7}
        ]
        
        processed = agent.post_process_segments(segments)
        
        # Первые два сегмента должны быть объединены
        assert len(processed) == 2
        assert processed[0]["text"] == "Hello world"
        assert processed[0]["speaker"] == "SPEAKER_00"

    def test_calculate_merge_metrics(self, agent, sample_diar_segments, sample_asr_segments):
        """Тест расчета метрик слияния."""
        merged_segments = agent.run(sample_diar_segments, sample_asr_segments, save_metrics=False)
        
        metrics = agent.calculate_merge_metrics(sample_diar_segments, sample_asr_segments, merged_segments)
        
        assert isinstance(metrics, MergeMetrics)
        assert metrics.total_asr_segments == len(sample_asr_segments)
        assert metrics.total_diar_segments == len(sample_diar_segments)
        assert metrics.merged_segments == len(merged_segments)
        assert isinstance(metrics.speaker_distribution, dict)
        assert 0.0 <= metrics.confidence_score <= 1.0

    def test_save_metrics_integration(self, agent, sample_diar_segments, sample_asr_segments):
        """Тест интеграции сохранения метрик."""
        with patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('builtins.open', create=True) as mock_open:
            
            # Выполняем слияние с сохранением метрик
            result = agent.run(sample_diar_segments, sample_asr_segments, save_metrics=True)
            
            # Проверяем, что метрики были сохранены
            mock_mkdir.assert_called_once()
            mock_open.assert_called_once()

    def test_validation_mixin_integration(self, agent):
        """Тест интеграции ValidationMixin."""
        # Проверяем доступность методов ValidationMixin
        assert hasattr(agent, 'validate_language_code')
        assert hasattr(agent, 'validate_voiceprint_ids')
        
        # Тестируем валидацию языкового кода
        valid_lang = agent.validate_language_code("en")
        assert valid_lang == "en"
        
        # Тестируем валидацию voiceprint IDs
        valid_ids = ["id1", "id2", "id3"]
        agent.validate_voiceprint_ids(valid_ids)  # Не должно вызывать ошибок

    def test_error_handling_comprehensive(self, agent):
        """Тест комплексной обработки ошибок."""
        # Тестируем обработку ошибки без reraise
        test_error = ValueError("Test error")
        agent.handle_error(test_error, "test_operation", reraise=False)
        
        assert agent._error_count == 1
        assert agent._last_error == test_error

    def test_performance_tracking(self, agent, sample_diar_segments, sample_asr_segments):
        """Тест отслеживания производительности."""
        # Выполняем несколько операций
        for _ in range(3):
            agent.run(sample_diar_segments, sample_asr_segments)
        
        # Проверяем метрики
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] == 3
        assert metrics['total_processing_time'] > 0
        assert metrics['success_rate'] == 100.0
