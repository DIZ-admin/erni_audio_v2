# tests/test_refactored_export_agent.py

import pytest
import tempfile
from pathlib import Path
from typing import List, Dict
from unittest.mock import Mock, patch, mock_open

from pipeline.export_agent import ExportAgent, ExportMetrics


class TestRefactoredExportAgent:
    """Тесты для рефакторированного ExportAgent."""

    @pytest.fixture
    def agent(self):
        """Создает экземпляр ExportAgent для тестов."""
        return ExportAgent(format="srt")

    @pytest.fixture
    def sample_segments(self):
        """Создает образцы сегментов для экспорта."""
        return [
            {
                "start": 0.0,
                "end": 2.0,
                "speaker": "SPEAKER_00",
                "text": "Привет мир",
                "confidence": 0.95
            },
            {
                "start": 2.0,
                "end": 4.0,
                "speaker": "SPEAKER_01",
                "text": "Как дела",
                "confidence": 0.87
            },
            {
                "start": 4.0,
                "end": 6.0,
                "speaker": "SPEAKER_00",
                "text": "Отлично",
                "confidence": 0.92
            }
        ]

    @pytest.fixture
    def temp_output_path(self):
        """Создает временный путь для экспорта."""
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Очистка
        if temp_path.exists():
            temp_path.unlink()

    def test_initialization_with_base_classes(self, agent):
        """Тест инициализации с базовыми классами."""
        # Проверяем, что агент наследует от всех базовых классов
        assert hasattr(agent, 'log_with_emoji')  # BaseAgent
        assert hasattr(agent, 'validate_audio_file')  # ValidationMixin
        
        # Проверяем инициализацию
        assert agent.name == "ExportAgent"
        assert agent.format == "srt"
        assert agent.create_all_formats == False

    def test_validate_export_format_valid(self, agent):
        """Тест валидации корректного формата."""
        # Валидные форматы
        for format in ExportAgent.SUPPORTED_FORMATS:
            agent.validate_export_format(format)  # Не должно вызывать ошибок

    def test_validate_export_format_invalid(self, agent):
        """Тест валидации некорректного формата."""
        # Невалидный формат
        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            agent.validate_export_format("invalid_format")
        
        # Пустой формат
        with pytest.raises(ValueError, match="Формат не может быть пустым"):
            agent.validate_export_format("")
        
        # Неправильный тип
        with pytest.raises(ValueError, match="Формат должен быть строкой"):
            agent.validate_export_format(123)

    def test_validate_export_segments_valid(self, agent, sample_segments):
        """Тест валидации корректных сегментов."""
        issues = agent.validate_export_segments(sample_segments)
        assert len(issues) == 0

    def test_validate_export_segments_empty(self, agent):
        """Тест валидации пустых сегментов."""
        issues = agent.validate_export_segments([])
        assert len(issues) >= 1
        assert any("Список сегментов пуст" in issue for issue in issues)

    def test_validate_export_segments_invalid_type(self, agent):
        """Тест валидации сегментов неправильного типа."""
        issues = agent.validate_export_segments("not a list")
        assert len(issues) >= 1
        assert any("Сегменты должны быть списком" in issue for issue in issues)

    def test_validate_export_segments_missing_fields(self, agent):
        """Тест валидации сегментов с отсутствующими полями."""
        invalid_segments = [
            {"start": 0.0, "end": 2.0},  # Отсутствуют speaker и text
            {"speaker": "SPEAKER_00", "text": "Hello"}  # Отсутствуют start и end
        ]
        
        issues = agent.validate_export_segments(invalid_segments)
        assert len(issues) >= 4  # По 2 ошибки на каждый сегмент
        assert any("отсутствует поле 'speaker'" in issue for issue in issues)
        assert any("отсутствует поле 'text'" in issue for issue in issues)
        assert any("отсутствует поле 'start'" in issue for issue in issues)
        assert any("отсутствует поле 'end'" in issue for issue in issues)

    def test_validate_export_segments_wrong_types(self, agent):
        """Тест валидации сегментов с неправильными типами данных."""
        invalid_segments = [
            {
                "start": "0.0",  # Строка вместо числа
                "end": "2.0",    # Строка вместо числа
                "speaker": 123,  # Число вместо строки
                "text": 456      # Число вместо строки
            }
        ]
        
        issues = agent.validate_export_segments(invalid_segments)
        assert len(issues) >= 4
        assert any("'start' должно быть числом" in issue for issue in issues)
        assert any("'end' должно быть числом" in issue for issue in issues)
        assert any("'speaker' должно быть строкой" in issue for issue in issues)
        assert any("'text' должно быть строкой" in issue for issue in issues)

    def test_validate_export_segments_invalid_timestamps(self, agent):
        """Тест валидации сегментов с некорректными временными метками."""
        invalid_segments = [
            {
                "start": -1.0,  # Отрицательное время
                "end": 2.0,
                "speaker": "SPEAKER_00",
                "text": "Test"
            },
            {
                "start": 2.0,
                "end": 1.0,  # end < start
                "speaker": "SPEAKER_00",
                "text": "Test"
            }
        ]
        
        issues = agent.validate_export_segments(invalid_segments)
        assert len(issues) >= 2
        assert any("отрицательное время начала" in issue for issue in issues)
        assert any("некорректные временные метки" in issue for issue in issues)

    def test_validate_output_path_valid(self, agent, temp_output_path):
        """Тест валидации корректного пути вывода."""
        agent.validate_output_path(temp_output_path)  # Не должно вызывать ошибок

    def test_validate_output_path_invalid_type(self, agent):
        """Тест валидации пути неправильного типа."""
        with pytest.raises(ValueError, match="output_path должен быть Path объектом"):
            agent.validate_output_path("not_a_path")

    def test_validate_output_path_directory_creation(self, agent):
        """Тест создания директории при валидации пути."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new_subdir"
            output_path = new_dir / "output.srt"
            
            # Директория не существует
            assert not new_dir.exists()
            
            # Валидация должна создать директорию
            agent.validate_output_path(output_path)
            
            # Директория должна быть создана
            assert new_dir.exists()

    @patch('builtins.open', mock_open())
    def test_run_with_performance_metrics(self, agent, sample_segments, temp_output_path):
        """Тест выполнения с отслеживанием метрик производительности."""
        # Выполняем экспорт
        result = agent.run(sample_segments, temp_output_path)
        
        # Проверяем результат
        assert len(result) >= 1
        assert all(isinstance(path, Path) for path in result)
        
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
        invalid_segments = "not a list"
        invalid_path = Path("/invalid/path/that/cannot/be/created")
        
        # Должно обработать ошибки gracefully
        with pytest.raises(Exception):
            agent.run(invalid_segments, invalid_path)
        
        # Проверяем, что ошибка была зарегистрирована
        assert agent._error_count > 0

    @patch('builtins.open', mock_open())
    def test_run_empty_segments(self, agent, temp_output_path):
        """Тест выполнения с пустыми сегментами."""
        result = agent.run([], temp_output_path)
        assert result == []

    def test_unified_logging_usage(self, agent):
        """Тест использования унифицированного логирования."""
        # Проверяем, что метод log_with_emoji доступен
        assert hasattr(agent, 'log_with_emoji')
        
        # Тестируем вызов (не должен вызывать ошибок)
        agent.log_with_emoji("info", "🎯", "Test message")

    def test_supported_formats(self, agent):
        """Тест поддерживаемых форматов."""
        expected_formats = ["srt", "json", "ass", "vtt", "ttml", "txt", "csv", "docx"]
        assert agent.SUPPORTED_FORMATS == expected_formats

    @patch('builtins.open', mock_open())
    def test_create_all_formats(self, sample_segments, temp_output_path):
        """Тест создания всех форматов."""
        agent = ExportAgent(format="srt", create_all_formats=True)
        
        with patch.object(agent, '_export_single_format') as mock_export:
            result = agent.run(sample_segments, temp_output_path)
            
            # Должен быть вызван для каждого формата
            assert mock_export.call_count == len(agent.SUPPORTED_FORMATS)

    def test_calculate_export_metrics(self, agent, sample_segments):
        """Тест расчета метрик экспорта."""
        # Создаем временные файлы для тестирования
        with tempfile.NamedTemporaryFile(suffix=".srt") as temp_file:
            temp_path = Path(temp_file.name)
            created_files = [temp_path]
            
            metrics = agent.calculate_export_metrics(sample_segments, created_files)
            
            assert isinstance(metrics, ExportMetrics)
            assert metrics.total_segments == len(sample_segments)
            assert metrics.speakers_count == 2  # SPEAKER_00 и SPEAKER_01
            assert metrics.total_words > 0
            assert metrics.total_duration == 6.0  # Последний сегмент заканчивается в 6.0

    def test_calculate_export_metrics_empty(self, agent):
        """Тест расчета метрик для пустых данных."""
        metrics = agent.calculate_export_metrics([], [])
        
        assert metrics.total_segments == 0
        assert metrics.total_duration == 0.0
        assert metrics.speakers_count == 0
        assert metrics.total_words == 0

    def test_validation_mixin_integration(self, agent):
        """Тест интеграции ValidationMixin."""
        # Проверяем доступность методов ValidationMixin
        assert hasattr(agent, 'validate_language_code')
        assert hasattr(agent, 'validate_voiceprint_ids')
        
        # Тестируем валидацию языкового кода
        valid_lang = agent.validate_language_code("en")
        assert valid_lang == "en"

    def test_error_handling_comprehensive(self, agent):
        """Тест комплексной обработки ошибок."""
        # Тестируем обработку ошибки без reraise
        test_error = ValueError("Test error")
        agent.handle_error(test_error, "test_operation", reraise=False)
        
        assert agent._error_count == 1
        assert agent._last_error == test_error

    @patch('builtins.open', mock_open())
    def test_performance_tracking(self, agent, sample_segments, temp_output_path):
        """Тест отслеживания производительности."""
        # Выполняем несколько операций
        for _ in range(3):
            agent.run(sample_segments, temp_output_path)
        
        # Проверяем метрики
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] == 3
        assert metrics['total_processing_time'] > 0
        assert metrics['success_rate'] == 100.0

    def test_speaker_colors(self, agent):
        """Тест функциональности цветов спикеров."""
        # Тестируем получение цвета для известного спикера
        color = agent.get_speaker_color("SPEAKER_00")
        assert color == "#FF6B6B"
        
        # Тестируем получение цвета для неизвестного спикера
        unknown_color = agent.get_speaker_color("UNKNOWN_SPEAKER")
        assert unknown_color == "#CCCCCC"
        
        # Тестируем отключение цветов
        agent.speaker_colors = False
        no_color = agent.get_speaker_color("SPEAKER_00")
        assert no_color == "#FFFFFF"
