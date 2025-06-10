# tests/test_refactored_agents.py

"""
Тесты для рефакторированных агентов с базовыми классами.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pipeline.audio_agent import AudioLoaderAgent
from pipeline.base_agent import BaseAgent
from pipeline.validation_mixin import ValidationMixin
from pipeline.retry_mixin import RetryMixin
from pipeline.rate_limit_mixin import RateLimitMixin


class TestBaseAgent:
    """Тесты для BaseAgent."""
    
    def test_base_agent_initialization(self):
        """Тест инициализации базового агента."""
        
        class TestAgent(BaseAgent):
            def run(self):
                return "test"
        
        agent = TestAgent("TestAgent")
        
        assert agent.name == "TestAgent"
        assert agent._operation_count == 0
        assert agent._error_count == 0
        assert agent._total_processing_time == 0.0
    
    def test_operation_tracking(self):
        """Тест отслеживания операций."""
        
        class TestAgent(BaseAgent):
            def run(self):
                self.start_operation("test_op")
                # Имитируем работу
                import time
                time.sleep(0.01)
                duration = self.end_operation("test_op", success=True)
                return duration
        
        agent = TestAgent()
        duration = agent.run()
        
        assert duration > 0
        assert agent._operation_count == 1
        assert agent._error_count == 0
        assert agent._total_processing_time > 0
    
    def test_error_handling(self):
        """Тест обработки ошибок."""
        
        class TestAgent(BaseAgent):
            def run(self):
                try:
                    raise ValueError("Test error")
                except Exception as e:
                    self.handle_error(e, "test_operation", reraise=False)
        
        agent = TestAgent()
        agent.run()
        
        assert agent._error_count == 1
        assert isinstance(agent._last_error, ValueError)
    
    def test_api_key_retrieval(self):
        """Тест получения API ключей."""
        
        class TestAgent(BaseAgent):
            def run(self):
                return "test"
        
        agent = TestAgent()
        
        # Тест с существующей переменной окружения
        with patch.dict('os.environ', {'TEST_API_KEY': 'test_key_value'}):
            key = agent.get_api_key("Test API", ["TEST_API_KEY"])
            assert key == "test_key_value"
        
        # Тест с отсутствующей переменной
        with pytest.raises(ValueError):
            agent.get_api_key("Missing API", ["MISSING_KEY"])


class TestValidationMixin:
    """Тесты для ValidationMixin."""
    
    def test_audio_file_validation(self):
        """Тест валидации аудиофайлов."""
        
        class TestValidator(ValidationMixin):
            def __init__(self):
                self.logger = Mock()
        
        validator = TestValidator()
        
        # Тест с несуществующим файлом
        with pytest.raises(FileNotFoundError):
            validator.validate_audio_file(Path("nonexistent.wav"))
    
    def test_url_validation(self):
        """Тест валидации URL."""
        
        validator = ValidationMixin()
        
        # Валидный HTTPS URL
        is_valid, message = validator.validate_url("https://example.com/audio.wav")
        assert is_valid
        
        # Невалидный HTTP URL (требуется HTTPS)
        is_valid, message = validator.validate_url("http://example.com/audio.wav")
        assert not is_valid
        
        # URL без схемы
        is_valid, message = validator.validate_url("example.com/audio.wav")
        assert not is_valid
    
    def test_voiceprint_ids_validation(self):
        """Тест валидации voiceprint ID."""
        
        validator = ValidationMixin()
        
        # Валидный список
        validator.validate_voiceprint_ids(["id1", "id2", "id3"])
        
        # Пустой список
        with pytest.raises(ValueError):
            validator.validate_voiceprint_ids([])
        
        # Дубликаты
        with pytest.raises(ValueError):
            validator.validate_voiceprint_ids(["id1", "id2", "id1"])
        
        # Невалидный тип
        with pytest.raises(ValueError):
            validator.validate_voiceprint_ids(["id1", 123, "id3"])


class TestRetryMixin:
    """Тесты для RetryMixin."""
    
    def test_retry_statistics_initialization(self):
        """Тест инициализации статистики retry."""
        
        class TestRetry(RetryMixin):
            def __init__(self):
                RetryMixin.__init__(self)
                self.logger = Mock()
        
        retry_obj = TestRetry()
        
        assert retry_obj.retry_stats["total_attempts"] == 0
        assert retry_obj.retry_stats["successful_operations"] == 0
        assert retry_obj.retry_stats["failed_operations"] == 0
    
    def test_adaptive_timeout_calculation(self):
        """Тест вычисления адаптивного таймаута."""
        
        class TestRetry(RetryMixin):
            def __init__(self):
                RetryMixin.__init__(self)
                self.logger = Mock()
        
        retry_obj = TestRetry()
        
        # Маленький файл
        timeout = retry_obj.get_adaptive_timeout(1.0)  # 1MB
        assert timeout == 32.0  # 30 + 1*2
        
        # Большой файл
        timeout = retry_obj.get_adaptive_timeout(100.0)  # 100MB
        assert timeout == 230.0  # 30 + 100*2
        
        # Очень большой файл (должен быть ограничен максимумом)
        timeout = retry_obj.get_adaptive_timeout(1000.0, max_timeout=300.0)
        assert timeout == 300.0


class TestRateLimitMixin:
    """Тесты для RateLimitMixin."""
    
    def test_rate_limit_initialization(self):
        """Тест инициализации rate limiting."""
        
        class TestRateLimit(RateLimitMixin):
            def __init__(self):
                RateLimitMixin.__init__(self, "test_api")
                self.logger = Mock()
        
        rate_limit_obj = TestRateLimit()
        
        assert rate_limit_obj.api_name == "test_api"
        # Rate limiter может быть None если не настроен в глобальных настройках
    
    def test_rate_limit_status_check(self):
        """Тест проверки статуса rate limit."""
        
        class TestRateLimit(RateLimitMixin):
            def __init__(self):
                RateLimitMixin.__init__(self, None)  # Без rate limiter
        
        rate_limit_obj = TestRateLimit()
        status = rate_limit_obj.check_rate_limit_status()
        
        assert not status["rate_limit_enabled"]
        assert status["remaining_requests"] == float('inf')


@pytest.mark.integration
class TestRefactoredAudioLoaderAgent:
    """Интеграционные тесты для рефакторированного AudioLoaderAgent."""
    
    @patch('pipeline.audio_agent.PyannoteMediaAgent')
    def test_audio_loader_initialization(self, mock_media_agent):
        """Тест инициализации AudioLoaderAgent."""
        
        # Настраиваем мок
        mock_instance = Mock()
        mock_instance.validate_api_key.return_value = True
        mock_media_agent.return_value = mock_instance
        
        with patch.dict('os.environ', {'PYANNOTEAI_API_TOKEN': 'test_token'}):
            agent = AudioLoaderAgent()
            
            assert agent.name == "AudioLoaderAgent"
            assert agent.api_name == "pyannote"
            assert hasattr(agent, 'pyannote_media_agent')
    
    @patch('pipeline.audio_agent.PyannoteMediaAgent')
    @patch('pipeline.audio_agent.subprocess.run')
    def test_audio_conversion(self, mock_subprocess, mock_media_agent):
        """Тест конвертации аудио."""
        
        # Настраиваем моки
        mock_instance = Mock()
        mock_instance.validate_api_key.return_value = True
        mock_media_agent.return_value = mock_instance
        
        mock_subprocess.return_value = Mock()
        
        with patch.dict('os.environ', {'PYANNOTEAI_API_TOKEN': 'test_token'}):
            agent = AudioLoaderAgent()
            
            # Создаем временный файл для тестирования
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_file.write(b"fake audio data")
                tmp_path = Path(tmp_file.name)
            
            try:
                # Тестируем конвертацию
                result = agent.to_wav16k_mono(tmp_path)
                
                assert isinstance(result, Path)
                assert result.suffix == ".wav"
                mock_subprocess.assert_called_once()
                
            finally:
                # Очищаем временный файл
                tmp_path.unlink(missing_ok=True)
    
    def test_inheritance_structure(self):
        """Тест структуры наследования."""
        
        with patch('pipeline.audio_agent.PyannoteMediaAgent'):
            with patch.dict('os.environ', {'PYANNOTEAI_API_TOKEN': 'test_token'}):
                agent = AudioLoaderAgent()
                
                # Проверяем, что агент наследует от всех нужных классов
                assert isinstance(agent, BaseAgent)
                assert isinstance(agent, ValidationMixin)
                assert isinstance(agent, RateLimitMixin)
                
                # Проверяем доступность методов
                assert hasattr(agent, 'start_operation')
                assert hasattr(agent, 'validate_audio_file')
                assert hasattr(agent, 'with_rate_limit')
                assert hasattr(agent, 'log_with_emoji')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
