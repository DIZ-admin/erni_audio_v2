# tests/test_refactored_transcription_agent.py

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import openai

from pipeline.transcription_agent import TranscriptionAgent


class TestRefactoredTranscriptionAgent:
    """Тесты для рефакторированного TranscriptionAgent."""

    @pytest.fixture
    def agent(self):
        """Создает экземпляр TranscriptionAgent для тестов."""
        return TranscriptionAgent(api_key="test-key", model="whisper-1")

    @pytest.fixture
    def mock_audio_file(self):
        """Создает временный аудиофайл для тестов."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Записываем минимальные данные WAV файла
            f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
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
        assert hasattr(agent, 'retry_with_backoff')  # RetryMixin
        assert hasattr(agent, 'with_rate_limit')  # RateLimitMixin
        
        # Проверяем инициализацию
        assert agent.name == "TranscriptionAgent"
        assert agent.model == "whisper-1"
        assert agent.api_name == "openai"

    def test_language_validation(self):
        """Тест валидации языка через ValidationMixin."""
        # Валидный язык
        agent = TranscriptionAgent(api_key="test-key", language="ru")
        assert agent.language == "ru"
        
        # Невалидный язык
        with pytest.raises(ValueError, match="Код языка должен быть двухбуквенным"):
            TranscriptionAgent(api_key="test-key", language="rus")

    def test_model_validation(self):
        """Тест валидации модели."""
        # Валидная модель
        agent = TranscriptionAgent(api_key="test-key", model="gpt-4o-transcribe")
        assert agent.model == "gpt-4o-transcribe"
        
        # Невалидная модель
        with pytest.raises(ValueError, match="Неподдерживаемая модель"):
            TranscriptionAgent(api_key="test-key", model="invalid-model")

    @patch('pipeline.transcription_agent.OpenAI')
    def test_transcribe_single_file_with_retry_mixin(self, mock_openai_class, agent, mock_audio_file):
        """Тест транскрипции одного файла с использованием RetryMixin."""
        # Настройка мока
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        mock_transcript = Mock()
        mock_transcript.segments = [
            Mock(model_dump=lambda: {
                'id': 0, 'start': 0.0, 'end': 5.0, 'text': 'Test transcription',
                'tokens': [], 'avg_logprob': -0.5, 'no_speech_prob': 0.1,
                'temperature': 0.0, 'compression_ratio': 1.0
            })
        ]
        
        mock_client.with_options.return_value.audio.transcriptions.create.return_value = mock_transcript
        agent.client = mock_client
        
        # Выполняем транскрипцию
        result = agent._transcribe_single_file(mock_audio_file, "test prompt")
        
        # Проверяем результат
        assert len(result) == 1
        assert result[0]['text'] == 'Test transcription'
        assert result[0]['start'] == 0.0
        assert result[0]['end'] == 5.0

    @patch('pipeline.transcription_agent.OpenAI')
    def test_rate_limiting_integration(self, mock_openai_class, agent, mock_audio_file):
        """Тест интеграции rate limiting."""
        # Настройка мока
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        agent.client = mock_client
        
        # Мокаем rate limiter
        agent._rate_limiter = Mock()
        agent._rate_limiter.wait_if_needed.return_value = 0.1  # Небольшая задержка
        
        mock_transcript = Mock()
        mock_transcript.text = "Test transcription"
        mock_client.with_options.return_value.audio.transcriptions.create.return_value = mock_transcript
        
        # Выполняем транскрипцию
        result = agent._transcribe_with_rate_limit(mock_audio_file, {}, 30.0)
        
        # Проверяем, что rate limiter был вызван
        agent._rate_limiter.wait_if_needed.assert_called_once_with("transcription")

    def test_performance_metrics_tracking(self, agent):
        """Тест отслеживания метрик производительности."""
        # Начинаем операцию
        agent.start_operation("test_operation")
        
        # Завершаем операцию
        duration = agent.end_operation("test_operation", success=True)
        
        # Проверяем метрики
        assert duration >= 0
        assert agent._operation_count == 1
        assert agent._error_count == 0
        
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] == 1
        assert metrics['success_rate'] == 100.0

    def test_error_handling_with_base_agent(self, agent):
        """Тест обработки ошибок через BaseAgent."""
        test_error = ValueError("Test error")
        
        # Тестируем обработку ошибки без reraise
        agent.handle_error(test_error, "test_operation", reraise=False)
        
        assert agent._error_count == 1
        assert agent._last_error == test_error

    def test_retry_statistics_integration(self, agent):
        """Тест интеграции статистики retry."""
        # Проверяем, что статистика retry инициализирована
        assert hasattr(agent, 'retry_stats')
        assert 'total_attempts' in agent.retry_stats
        assert 'rate_limit_retries' in agent.retry_stats
        
        # Тестируем логирование статистики
        stats = agent.log_retry_statistics()
        assert isinstance(stats, dict)

    def test_adaptive_timeout_calculation(self, agent):
        """Тест расчета адаптивного таймаута."""
        # Тестируем расчет таймаута для разных размеров файлов
        timeout_small = agent.get_adaptive_timeout(1.0)  # 1MB
        timeout_large = agent.get_adaptive_timeout(10.0)  # 10MB
        
        assert timeout_large > timeout_small
        assert timeout_small >= 30.0  # Минимальный базовый таймаут

    @patch('pipeline.transcription_agent.OpenAI')
    def test_openai_api_error_handling(self, mock_openai_class, agent, mock_audio_file):
        """Тест обработки ошибок OpenAI API."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        agent.client = mock_client
        
        # Мокаем ошибку rate limit
        mock_client.with_options.return_value.audio.transcriptions.create.side_effect = \
            openai.RateLimitError("Rate limit exceeded", response=None, body=None)
        
        # Проверяем, что ошибка правильно обрабатывается
        with pytest.raises(openai.RateLimitError):
            agent._transcribe_with_rate_limit(mock_audio_file, {}, 30.0)

    def test_parallel_processing_statistics(self, agent):
        """Тест статистики параллельной обработки."""
        # Проверяем инициализацию статистики
        assert hasattr(agent, 'parallel_stats')
        assert 'total_chunks_processed' in agent.parallel_stats
        assert 'concurrent_chunks_peak' in agent.parallel_stats
        
        # Тестируем логирование статистики
        agent.parallel_stats['total_chunks_processed'] = 5
        agent._log_parallel_statistics()  # Не должно вызывать ошибок

    def test_model_info_methods(self, agent):
        """Тест методов получения информации о модели."""
        # Тестируем get_model_info
        model_info = agent.get_model_info()
        assert 'model' in model_info
        assert 'name' in model_info
        assert model_info['model'] == 'whisper-1'
        
        # Тестируем get_available_models
        available_models = agent.get_available_models()
        assert 'whisper-1' in available_models
        assert 'gpt-4o-transcribe' in available_models

    def test_cost_estimation(self, agent):
        """Тест оценки стоимости."""
        cost = agent.estimate_cost(10.0)  # 10MB файл
        assert isinstance(cost, str)
        assert '$' in cost

    @patch('pipeline.transcription_agent.AudioSegment')
    def test_file_splitting_with_logging(self, mock_audio_segment, agent, mock_audio_file):
        """Тест разбиения файла с унифицированным логированием."""
        # Настройка мока
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=600000)  # 10 минут в миллисекундах
        mock_audio.__getitem__ = Mock(return_value=mock_audio)
        mock_audio.export = Mock()
        mock_audio_segment.from_wav.return_value = mock_audio
        
        # Выполняем разбиение
        chunks = agent._split_audio_file(mock_audio_file, chunk_duration_minutes=5)
        
        # Проверяем результат
        assert len(chunks) == 2  # 10 минут / 5 минут = 2 части

    def test_unified_logging_usage(self, agent):
        """Тест использования унифицированного логирования."""
        # Проверяем, что метод log_with_emoji доступен
        assert hasattr(agent, 'log_with_emoji')
        
        # Тестируем вызов (не должен вызывать ошибок)
        agent.log_with_emoji("info", "🎯", "Test message")

    def test_validation_mixin_integration(self, agent, mock_audio_file):
        """Тест интеграции ValidationMixin."""
        # Тестируем валидацию аудиофайла
        agent.validate_audio_file(mock_audio_file, max_size_mb=100)
        
        # Тестируем валидацию несуществующего файла
        with pytest.raises(FileNotFoundError):
            agent.validate_audio_file(Path("nonexistent.wav"))

    def test_run_method_integration(self, agent, mock_audio_file):
        """Тест интеграции метода run с базовыми классами."""
        with patch.object(agent, '_transcribe_single_file') as mock_transcribe:
            mock_transcribe.return_value = [{'id': 0, 'text': 'test', 'start': 0, 'end': 1}]
            
            # Выполняем run
            result = agent.run(mock_audio_file, "test prompt")
            
            # Проверяем результат
            assert len(result) == 1
            assert result[0]['text'] == 'test'
            
            # Проверяем, что метрики были обновлены
            assert agent._operation_count > 0
