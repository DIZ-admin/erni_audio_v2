# tests/test_transcription_retry_improvements.py

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import openai

from pipeline.transcription_agent import TranscriptionAgent


class TestTranscriptionRetryImprovements:
    """Тесты для улучшенной retry логики TranscriptionAgent."""

    @pytest.fixture
    def agent(self):
        """Создает экземпляр TranscriptionAgent для тестов."""
        # Мокаем переменные окружения для тестов
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-openai-key',
            'PYANNOTE_API_KEY': 'test-pyannote-key'
        }):
            return TranscriptionAgent(api_key="test-key", model="whisper-1")

    @pytest.fixture
    def mock_audio_file(self, tmp_path):
        """Создает временный аудиофайл для тестов."""
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_bytes(b"fake audio data" * 1000)  # ~15KB
        return audio_file

    def test_adaptive_timeout_calculation(self, agent):
        """Тест адаптивного расчета таймаута."""
        # Маленький файл
        timeout_small = agent._get_adaptive_timeout(1.0)  # 1MB
        assert timeout_small == 70.0  # 60 + 10*1

        # Большой файл
        timeout_large = agent._get_adaptive_timeout(50.0)  # 50MB
        assert timeout_large == 560.0  # 60 + 10*50

        # Очень большой файл (должен быть ограничен)
        timeout_huge = agent._get_adaptive_timeout(100.0)  # 100MB
        assert timeout_huge == 600.0  # Максимум 10 минут

    def test_retry_statistics_initialization(self, agent):
        """Тест инициализации статистики retry."""
        assert agent.retry_stats["total_attempts"] == 0
        assert agent.retry_stats["rate_limit_retries"] == 0
        assert agent.retry_stats["connection_retries"] == 0
        assert agent.retry_stats["other_retries"] == 0
        assert agent.retry_stats["total_retry_time"] == 0.0

    def test_intelligent_wait_strategy_rate_limit(self, agent):
        """Тест стратегии ожидания для rate limit ошибок."""
        # Создаем mock retry_state
        retry_state = Mock()
        retry_state.attempt_number = 2

        # Создаем mock исключения с правильными параметрами
        mock_response = Mock()
        mock_response.status_code = 429
        rate_limit_error = Mock(spec=openai.RateLimitError)
        rate_limit_error.__class__ = openai.RateLimitError

        retry_state.outcome.exception.return_value = rate_limit_error

        delay = agent._intelligent_wait_strategy(retry_state)

        # Для rate limit должен быть экспоненциальный backoff
        assert 2.0 <= delay <= 8.0  # 2^1 * 2 + jitter
        assert agent.retry_stats["total_retry_time"] == delay

    def test_intelligent_wait_strategy_connection_error(self, agent):
        """Тест стратегии ожидания для сетевых ошибок."""
        retry_state = Mock()
        retry_state.attempt_number = 3

        # Создаем mock исключения
        connection_error = Mock(spec=openai.APIConnectionError)
        connection_error.__class__ = openai.APIConnectionError

        retry_state.outcome.exception.return_value = connection_error

        delay = agent._intelligent_wait_strategy(retry_state)

        # Для сетевых ошибок должен быть быстрый retry
        assert delay == 1.5  # 0.5 * 3
        assert agent.retry_stats["total_retry_time"] == delay

    def test_transcribe_with_retry_success(self, agent, mock_audio_file):
        """Тест успешной транскрипции с первой попытки."""
        # Мокаем клиент агента напрямую
        mock_client = Mock()
        agent.client = mock_client

        mock_transcript = Mock()
        mock_transcript.segments = [
            Mock(model_dump=lambda: {"id": 0, "start": 0.0, "end": 5.0, "text": "Test text"})
        ]

        mock_client.with_options.return_value.audio.transcriptions.create.return_value = mock_transcript

        # Выполняем транскрипцию
        result = agent._transcribe_with_intelligent_retry(
            mock_audio_file,
            {"response_format": "verbose_json"},
            60.0
        )

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["text"] == "Test text"

    def test_transcribe_with_retry_rate_limit_recovery(self, agent, mock_audio_file):
        """Тест восстановления после rate limit ошибки."""
        # Мокаем клиент агента напрямую
        mock_client = Mock()
        agent.client = mock_client

        # Первый вызов - rate limit, второй - успех
        mock_transcript = Mock()
        mock_transcript.segments = [
            Mock(model_dump=lambda: {"id": 0, "start": 0.0, "end": 5.0, "text": "Success after retry"})
        ]

        # Создаем настоящее исключение
        class MockRateLimitError(openai.RateLimitError):
            def __init__(self):
                pass  # Не вызываем super().__init__() чтобы избежать проблем с параметрами

        rate_limit_error = MockRateLimitError()

        mock_client.with_options.return_value.audio.transcriptions.create.side_effect = [
            rate_limit_error,
            mock_transcript
        ]

        # Выполняем транскрипцию
        result = agent._transcribe_with_intelligent_retry(
            mock_audio_file,
            {"response_format": "verbose_json"},
            60.0
        )

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["text"] == "Success after retry"
        assert agent.retry_stats["rate_limit_retries"] >= 1

    def test_transcribe_with_retry_max_attempts_exceeded(self, agent, mock_audio_file):
        """Тест превышения максимального количества попыток."""
        # Мокаем клиент агента напрямую
        mock_client = Mock()
        agent.client = mock_client

        # Создаем настоящее исключение
        class MockRateLimitError(openai.RateLimitError):
            def __init__(self):
                pass  # Не вызываем super().__init__() чтобы избежать проблем с параметрами

        rate_limit_error = MockRateLimitError()

        # Все попытки заканчиваются rate limit
        mock_client.with_options.return_value.audio.transcriptions.create.side_effect = rate_limit_error

        # Выполняем транскрипцию и ожидаем исключение
        with pytest.raises(openai.RateLimitError):
            agent._transcribe_with_intelligent_retry(
                mock_audio_file,
                {"response_format": "verbose_json"},
                60.0
            )

        # Проверяем статистику
        assert agent.retry_stats["rate_limit_retries"] >= 8  # Максимум попыток

    def test_log_retry_statistics(self, agent, caplog):
        """Тест логирования статистики retry."""
        import logging

        # Устанавливаем уровень логирования
        caplog.set_level(logging.INFO)

        # Устанавливаем статистику
        agent.retry_stats["total_attempts"] = 5
        agent.retry_stats["rate_limit_retries"] = 3
        agent.retry_stats["connection_retries"] = 1
        agent.retry_stats["other_retries"] = 1
        agent.retry_stats["total_retry_time"] = 25.5

        # Логируем статистику
        agent._log_retry_statistics()

        # Проверяем лог
        assert "📊 Статистика retry" in caplog.text
        assert "всего попыток=5" in caplog.text
        assert "rate_limit=3" in caplog.text
        assert "connection=1" in caplog.text
        assert "other=1" in caplog.text
        assert "общее время retry=25.5с" in caplog.text

    def test_log_retry_statistics_no_attempts(self, agent, caplog):
        """Тест логирования статистики когда не было попыток."""
        # Логируем статистику без попыток
        agent._log_retry_statistics()
        
        # Проверяем, что лог пустой
        assert "📊 Статистика retry" not in caplog.text

    def test_transcribe_single_file_integration(self, agent, mock_audio_file):
        """Интеграционный тест метода _transcribe_single_file."""
        # Мокаем клиент агента напрямую
        mock_client = Mock()
        agent.client = mock_client

        mock_transcript = Mock()
        mock_transcript.segments = [
            Mock(model_dump=lambda: {"id": 0, "start": 0.0, "end": 5.0, "text": "Integration test"})
        ]

        mock_client.with_options.return_value.audio.transcriptions.create.return_value = mock_transcript

        # Выполняем транскрипцию
        result = agent._transcribe_single_file(mock_audio_file, "test prompt")

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["text"] == "Integration test"

        # Проверяем, что был вызван with_options для адаптивного таймаута
        mock_client.with_options.assert_called_once()

        # Проверяем, что таймаут был рассчитан правильно
        call_args = mock_client.with_options.call_args
        timeout_used = call_args[1]['timeout']
        assert timeout_used > 60  # Должен быть больше базового таймаута

    def test_config_integration(self, agent):
        """Тест интеграции с ConfigurationManager."""
        # Проверяем, что конфигурация загружена
        assert hasattr(agent, 'config')
        assert hasattr(agent, 'retry_config')
        assert isinstance(agent.retry_config, dict)
        
        # Проверяем основные параметры конфигурации
        assert 'max_attempts' in agent.retry_config
        assert 'min_wait' in agent.retry_config
        assert 'max_wait' in agent.retry_config
