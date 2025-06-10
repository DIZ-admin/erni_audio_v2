# tests/test_refactored_voiceprint_agent.py

import pytest
import tempfile
from pathlib import Path
from typing import Dict
from unittest.mock import Mock, patch, MagicMock

from pipeline.voiceprint_agent import VoiceprintAgent


class TestRefactoredVoiceprintAgent:
    """Тесты для рефакторированного VoiceprintAgent."""

    @pytest.fixture
    def api_key(self):
        """Создает тестовый API ключ."""
        return "test_api_key_12345"

    @pytest.fixture
    def agent(self, api_key):
        """Создает экземпляр VoiceprintAgent для тестов."""
        with patch('pipeline.voiceprint_agent.PyannoteMediaAgent'):
            return VoiceprintAgent(api_key=api_key)

    @pytest.fixture
    def sample_audio_file(self):
        """Создает временный аудиофайл для тестов."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Создаем небольшой файл (имитация аудио)
            f.write(b"fake audio data" * 1000)  # ~14KB
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
        assert agent.name == "VoiceprintAgent"
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
        
        # Только пробелы
        with pytest.raises(ValueError, match="API ключ не может быть пустым"):
            agent.validate_api_key("   ")
        
        # Слишком короткий
        with pytest.raises(ValueError, match="API ключ слишком короткий"):
            agent.validate_api_key("short")
        
        # Неправильный тип
        with pytest.raises(ValueError, match="API ключ должен быть строкой"):
            agent.validate_api_key(123)

    def test_validate_voiceprint_params_valid(self, agent, sample_audio_file):
        """Тест валидации корректных параметров voiceprint."""
        issues = agent.validate_voiceprint_params(sample_audio_file, "Test Speaker")
        assert len(issues) == 0

    def test_validate_voiceprint_params_invalid_label(self, agent, sample_audio_file):
        """Тест валидации некорректной метки."""
        # Пустая метка
        issues = agent.validate_voiceprint_params(sample_audio_file, "")
        assert len(issues) >= 1
        assert any("Метка не может быть пустой" in issue for issue in issues)
        
        # Слишком длинная метка
        long_label = "x" * 101
        issues = agent.validate_voiceprint_params(sample_audio_file, long_label)
        assert len(issues) >= 1
        assert any("Метка слишком длинная" in issue for issue in issues)
        
        # Неправильный тип
        issues = agent.validate_voiceprint_params(sample_audio_file, 123)
        assert len(issues) >= 1
        assert any("Метка должна быть строкой" in issue for issue in issues)

    def test_validate_voiceprint_audio_file_valid(self, agent, sample_audio_file):
        """Тест валидации корректного аудиофайла."""
        issues = agent.validate_voiceprint_audio_file(sample_audio_file, max_duration_check=False)
        assert len(issues) == 0

    def test_validate_voiceprint_audio_file_too_large(self, agent):
        """Тест валидации слишком большого файла."""
        # Создаем большой файл (>100MB)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Создаем файл размером ~101MB
            chunk = b"x" * (1024 * 1024)  # 1MB
            for _ in range(101):
                f.write(chunk)
            large_file = Path(f.name)
        
        try:
            issues = agent.validate_voiceprint_audio_file(large_file, max_duration_check=False)
            assert len(issues) >= 1
            assert any("слишком большой" in issue for issue in issues)
        finally:
            if large_file.exists():
                large_file.unlink()

    def test_validate_voiceprint_audio_file_nonexistent(self, agent):
        """Тест валидации несуществующего файла."""
        nonexistent_file = Path("/nonexistent/file.wav")
        issues = agent.validate_voiceprint_audio_file(nonexistent_file)
        assert len(issues) >= 1
        assert any("не найден" in issue or "не существует" in issue for issue in issues)

    @patch('requests.post')
    @patch('requests.get')
    def test_create_voiceprint_with_performance_metrics(self, mock_get, mock_post, agent, sample_audio_file):
        """Тест создания voiceprint с отслеживанием метрик производительности."""
        # Мокаем ответы API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "test_job_123"}
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {"voiceprint": "base64_encoded_voiceprint_data"}
        }
        
        # Мокаем media_agent
        agent.media_agent.upload_file = Mock(return_value="media://test/file.wav")
        
        # Выполняем создание voiceprint
        result = agent.create_voiceprint(sample_audio_file, "Test Speaker")
        
        # Проверяем результат
        assert isinstance(result, dict)
        assert result["label"] == "Test Speaker"
        assert result["voiceprint"] == "base64_encoded_voiceprint_data"
        assert "created_at" in result
        assert "source_file" in result
        
        # Проверяем, что метрики были обновлены
        assert agent._operation_count > 0
        assert agent._error_count == 0
        
        # Проверяем метрики производительности
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] >= 1
        assert metrics['success_rate'] == 100.0

    def test_create_voiceprint_with_error_handling(self, agent):
        """Тест обработки ошибок через BaseAgent."""
        # Передаем некорректные данные
        nonexistent_file = Path("/nonexistent/file.wav")
        
        # Должно обработать ошибки gracefully
        with pytest.raises(Exception):
            agent.create_voiceprint(nonexistent_file, "Test")
        
        # Проверяем, что ошибка была зарегистрирована
        assert agent._error_count > 0

    def test_unified_logging_usage(self, agent):
        """Тест использования унифицированного логирования."""
        # Проверяем, что метод log_with_emoji доступен
        assert hasattr(agent, 'log_with_emoji')
        
        # Тестируем вызов (не должен вызывать ошибок)
        agent.log_with_emoji("info", "🎯", "Test message")

    @patch('requests.post')
    def test_create_voiceprint_async_with_webhook(self, mock_post, agent, sample_audio_file):
        """Тест асинхронного создания voiceprint с webhook."""
        # Настраиваем webhook
        agent.webhook_url = "https://example.com/webhook"
        
        # Мокаем ответ API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "async_job_123"}
        
        # Мокаем media_agent
        agent.media_agent.upload_file = Mock(return_value="media://test/file.wav")
        
        # Выполняем асинхронное создание
        job_id = agent.create_voiceprint_async(sample_audio_file, "Test Speaker")
        
        # Проверяем результат
        assert job_id == "async_job_123"
        
        # Проверяем, что метрики были обновлены
        assert agent._operation_count > 0

    def test_create_voiceprint_async_without_webhook(self, agent, sample_audio_file):
        """Тест асинхронного создания без webhook."""
        # Webhook не настроен
        agent.webhook_url = None
        
        # Должно вызвать ошибку
        with pytest.raises(ValueError, match="webhook_url должен быть настроен"):
            agent.create_voiceprint_async(sample_audio_file, "Test Speaker")

    def test_estimate_cost(self, agent, sample_audio_file):
        """Тест оценки стоимости."""
        cost_info = agent.estimate_cost(sample_audio_file)
        
        assert isinstance(cost_info, dict)
        assert "estimated_cost_usd" in cost_info
        assert "file_size_mb" in cost_info
        assert "note" in cost_info
        assert cost_info["estimated_cost_usd"] == 0.01

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
    def test_performance_tracking(self, mock_get, mock_post, agent, sample_audio_file):
        """Тест отслеживания производительности."""
        # Мокаем ответы API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "test_job"}
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {"voiceprint": "test_data"}
        }
        
        agent.media_agent.upload_file = Mock(return_value="media://test/file.wav")
        
        # Выполняем несколько операций
        for i in range(3):
            agent.create_voiceprint(sample_audio_file, f"Speaker_{i}")
        
        # Проверяем метрики
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] == 3
        assert metrics['total_processing_time'] > 0
        assert metrics['success_rate'] == 100.0

    def test_submit_voiceprint_job_with_webhook(self, agent):
        """Тест отправки job с webhook."""
        agent.webhook_url = "https://example.com/webhook"
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"jobId": "test_job_123"}
            
            job_id = agent._submit_voiceprint_job("media://test/file.wav")
            
            assert job_id == "test_job_123"
            
            # Проверяем, что webhook был добавлен в запрос
            call_args = mock_post.call_args
            request_data = call_args[1]['json']
            assert request_data['webhook'] == "https://example.com/webhook"

    @patch('requests.get')
    def test_wait_for_completion_success(self, mock_get, agent):
        """Тест успешного ожидания завершения job."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {"voiceprint": "test_voiceprint_data"}
        }
        
        result = agent._wait_for_completion("test_job_123")
        assert result == "test_voiceprint_data"

    @patch('requests.get')
    def test_wait_for_completion_failed(self, mock_get, agent):
        """Тест обработки неудачного завершения job."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "failed",
            "output": {"error": "Processing failed"}
        }
        
        with pytest.raises(RuntimeError, match="Voiceprint job failed"):
            agent._wait_for_completion("test_job_123")

    @patch('requests.get')
    def test_wait_for_completion_timeout(self, mock_get, agent):
        """Тест таймаута при ожидании завершения job."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "processing"
        }
        
        with pytest.raises(RuntimeError, match="Превышено время ожидания"):
            agent._wait_for_completion("test_job_123", max_wait_seconds=1)
