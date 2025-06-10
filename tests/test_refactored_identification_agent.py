# tests/test_refactored_identification_agent.py

import pytest
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock

from pipeline.identification_agent import IdentificationAgent


class TestRefactoredIdentificationAgent:
    """Тесты для рефакторированного IdentificationAgent."""

    @pytest.fixture
    def api_key(self):
        """Создает тестовый API ключ."""
        return "test_api_key_12345"

    @pytest.fixture
    def agent(self, api_key):
        """Создает экземпляр IdentificationAgent для тестов."""
        with patch('pipeline.identification_agent.PyannoteMediaAgent'):
            return IdentificationAgent(api_key=api_key)

    @pytest.fixture
    def sample_audio_file(self):
        """Создает временный аудиофайл для тестов."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Создаем файл среднего размера (имитация аудио)
            f.write(b"fake audio data" * 10000)  # ~140KB
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Очистка
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def sample_voiceprints(self):
        """Создает образцы voiceprints для тестов."""
        return [
            {
                "label": "John Doe",
                "voiceprint": "base64_encoded_voiceprint_data_john"
            },
            {
                "label": "Jane Smith",
                "voiceprint": "base64_encoded_voiceprint_data_jane"
            }
        ]

    def test_initialization_with_base_classes(self, agent):
        """Тест инициализации с базовыми классами."""
        # Проверяем, что агент наследует от всех базовых классов
        assert hasattr(agent, 'log_with_emoji')  # BaseAgent
        assert hasattr(agent, 'validate_audio_file')  # ValidationMixin
        
        # Проверяем инициализацию
        assert agent.name == "IdentificationAgent"
        assert agent.api_key == "test_api_key_12345"
        assert agent.base_url == "https://api.pyannote.ai/v1"

    def test_validate_api_key_valid(self, agent):
        """Тест валидации корректного API ключа."""
        # Валидные ключи
        valid_keys = ["test_key_123", "sk-1234567890abcdef", "pyannote_api_key_long_enough"]
        
        for key in valid_keys:
            agent.validate_api_key(key)  # Не должно вызывать ошибок

    def test_validate_api_key_invalid(self, agent):
        """Тест валидации некорректного API ключа."""
        # Пустой ключ
        with pytest.raises(ValueError, match="API ключ не может быть пустым"):
            agent.validate_api_key("")
        
        # Слишком короткий
        with pytest.raises(ValueError, match="API ключ слишком короткий"):
            agent.validate_api_key("short")
        
        # Неправильный тип
        with pytest.raises(ValueError, match="API ключ должен быть строкой"):
            agent.validate_api_key(123)

    def test_validate_voiceprints_valid(self, agent, sample_voiceprints):
        """Тест валидации корректных voiceprints."""
        issues = agent.validate_voiceprints(sample_voiceprints)
        assert len(issues) == 0

    def test_validate_voiceprints_empty(self, agent):
        """Тест валидации пустых voiceprints."""
        issues = agent.validate_voiceprints([])
        assert len(issues) >= 1
        assert any("не может быть пустым" in issue for issue in issues)

    def test_validate_voiceprints_invalid_type(self, agent):
        """Тест валидации voiceprints неправильного типа."""
        issues = agent.validate_voiceprints("not a list")
        assert len(issues) >= 1
        assert any("должны быть списком" in issue for issue in issues)

    def test_validate_voiceprints_missing_fields(self, agent):
        """Тест валидации voiceprints с отсутствующими полями."""
        invalid_voiceprints = [
            {"label": "John Doe"},  # Отсутствует voiceprint
            {"voiceprint": "data"}  # Отсутствует label
        ]
        
        issues = agent.validate_voiceprints(invalid_voiceprints)
        assert len(issues) >= 2
        assert any("отсутствует поле 'voiceprint'" in issue for issue in issues)
        assert any("отсутствует поле 'label'" in issue for issue in issues)

    def test_validate_voiceprints_wrong_types(self, agent):
        """Тест валидации voiceprints с неправильными типами данных."""
        invalid_voiceprints = [
            {
                "label": 123,  # Число вместо строки
                "voiceprint": ""  # Пустая строка
            }
        ]
        
        issues = agent.validate_voiceprints(invalid_voiceprints)
        assert len(issues) >= 2
        assert any("'label' должно быть непустой строкой" in issue for issue in issues)
        assert any("'voiceprint' должно быть непустой строкой" in issue for issue in issues)

    def test_validate_identification_params_valid(self, agent, sample_audio_file, sample_voiceprints):
        """Тест валидации корректных параметров identification."""
        issues = agent.validate_identification_params(
            sample_audio_file, sample_voiceprints, num_speakers=2, matching_threshold=0.5
        )
        assert len(issues) == 0

    def test_validate_identification_params_invalid_num_speakers(self, agent, sample_audio_file, sample_voiceprints):
        """Тест валидации некорректного num_speakers."""
        # Отрицательное число
        issues = agent.validate_identification_params(
            sample_audio_file, sample_voiceprints, num_speakers=-1
        )
        assert len(issues) >= 1
        assert any("должно быть больше 0" in issue for issue in issues)
        
        # Слишком большое число
        issues = agent.validate_identification_params(
            sample_audio_file, sample_voiceprints, num_speakers=100
        )
        assert len(issues) >= 1
        assert any("слишком большое" in issue for issue in issues)

    def test_validate_identification_params_invalid_threshold(self, agent, sample_audio_file, sample_voiceprints):
        """Тест валидации некорректного matching_threshold."""
        # Вне диапазона
        issues = agent.validate_identification_params(
            sample_audio_file, sample_voiceprints, matching_threshold=1.5
        )
        assert len(issues) >= 1
        assert any("должно быть в диапазоне 0.0-1.0" in issue for issue in issues)

    def test_validate_identification_audio_file_valid(self, agent, sample_audio_file):
        """Тест валидации корректного аудиофайла."""
        issues = agent.validate_identification_audio_file(sample_audio_file)
        assert len(issues) == 0

    def test_validate_identification_audio_file_too_large(self, agent):
        """Тест валидации слишком большого файла."""
        # Создаем большой файл (>1GB)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Создаем файл размером ~1.1GB (имитация)
            # Для теста создадим файл поменьше, но проверим логику
            chunk = b"x" * (1024 * 1024)  # 1MB
            for _ in range(1025):  # 1025MB > 1024MB
                f.write(chunk)
            large_file = Path(f.name)
        
        try:
            issues = agent.validate_identification_audio_file(large_file)
            assert len(issues) >= 1
            assert any("слишком большой" in issue for issue in issues)
        finally:
            if large_file.exists():
                large_file.unlink()

    @patch('requests.post')
    @patch('requests.get')
    def test_run_with_performance_metrics(self, mock_get, mock_post, agent, sample_audio_file, sample_voiceprints):
        """Тест выполнения identification с отслеживанием метрик производительности."""
        # Мокаем ответы API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "test_job_123"}
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {
                "identification": [
                    {
                        "start": 0.0,
                        "end": 2.0,
                        "speaker": "John Doe",
                        "match": "john_voiceprint_id",
                        "diarizationSpeaker": "SPEAKER_00"
                    }
                ]
            }
        }
        
        # Мокаем media_agent
        agent.media_agent.upload_file = Mock(return_value="media://test/file.wav")
        
        # Выполняем identification
        result = agent.run(sample_audio_file, sample_voiceprints)
        
        # Проверяем результат
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["speaker"] == "John Doe"
        assert "match" in result[0]
        assert "diarization_speaker" in result[0]
        
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
        nonexistent_file = Path("/nonexistent/file.wav")
        empty_voiceprints = []
        
        # Должно обработать ошибки gracefully
        with pytest.raises(Exception):
            agent.run(nonexistent_file, empty_voiceprints)
        
        # Проверяем, что ошибка была зарегистрирована
        assert agent._error_count > 0

    def test_unified_logging_usage(self, agent):
        """Тест использования унифицированного логирования."""
        # Проверяем, что метод log_with_emoji доступен
        assert hasattr(agent, 'log_with_emoji')
        
        # Тестируем вызов (не должен вызывать ошибок)
        agent.log_with_emoji("info", "🎯", "Test message")

    @patch('requests.post')
    def test_run_async_with_webhook(self, mock_post, agent, sample_audio_file, sample_voiceprints):
        """Тест асинхронного выполнения identification с webhook."""
        # Настраиваем webhook
        agent.webhook_url = "https://example.com/webhook"
        
        # Мокаем ответ API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "async_job_123"}
        
        # Мокаем media_agent
        agent.media_agent.upload_file = Mock(return_value="media://test/file.wav")
        
        # Выполняем асинхронную identification
        job_id = agent.run_async(sample_audio_file, sample_voiceprints)
        
        # Проверяем результат
        assert job_id == "async_job_123"
        
        # Проверяем, что метрики были обновлены
        assert agent._operation_count > 0

    def test_run_async_without_webhook(self, agent, sample_audio_file, sample_voiceprints):
        """Тест асинхронного выполнения без webhook."""
        # Webhook не настроен
        agent.webhook_url = None
        
        # Должно вызвать ошибку
        with pytest.raises(ValueError, match="webhook_url должен быть настроен"):
            agent.run_async(sample_audio_file, sample_voiceprints)

    def test_estimate_cost(self, agent, sample_audio_file):
        """Тест оценки стоимости."""
        cost_info = agent.estimate_cost(sample_audio_file, num_voiceprints=2)
        
        assert isinstance(cost_info, dict)
        assert "estimated_cost_usd" in cost_info
        assert "file_size_mb" in cost_info
        assert "num_voiceprints" in cost_info
        assert "note" in cost_info
        assert cost_info["num_voiceprints"] == 2

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

    @patch('requests.post')
    @patch('requests.get')
    def test_performance_tracking(self, mock_get, mock_post, agent, sample_audio_file, sample_voiceprints):
        """Тест отслеживания производительности."""
        # Мокаем ответы API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "test_job"}
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {"identification": []}
        }
        
        agent.media_agent.upload_file = Mock(return_value="media://test/file.wav")
        
        # Выполняем несколько операций
        for i in range(3):
            agent.run(sample_audio_file, sample_voiceprints)
        
        # Проверяем метрики
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] == 3
        assert metrics['total_processing_time'] > 0
        assert metrics['success_rate'] == 100.0

    def test_process_identification_segments(self, agent):
        """Тест обработки identification сегментов."""
        identification_data = [
            {
                "start": 0.0,
                "end": 2.0,
                "speaker": "John Doe",
                "match": "john_voiceprint_id",
                "diarizationSpeaker": "SPEAKER_00"
            },
            {
                "start": 2.0,
                "end": 4.0,
                "speaker": "Jane Smith",
                "match": "jane_voiceprint_id",
                "diarizationSpeaker": "SPEAKER_01"
            }
        ]
        
        result = agent._process_identification_segments(identification_data)
        
        assert len(result) == 2
        assert result[0]["speaker"] == "John Doe"
        assert result[0]["match"] == "john_voiceprint_id"
        assert result[0]["diarization_speaker"] == "SPEAKER_00"
        assert result[1]["speaker"] == "Jane Smith"

    def test_process_segments_fallback(self, agent):
        """Тест обработки обычных сегментов (fallback)."""
        segments_data = [
            {
                "start": 0.0,
                "end": 2.0,
                "speaker": "SPEAKER_00",
                "confidence": 0.95
            }
        ]
        
        result = agent._process_segments(segments_data)
        
        assert len(result) == 1
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[0]["confidence"] == 0.95
