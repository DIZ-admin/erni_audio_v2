import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.transcription_agent import TranscriptionAgent
import openai

def test_init():
    # Используем существующую модель
    agent = TranscriptionAgent(api_key="test-key", model="gpt-4o-transcribe")  # Используем test-key для тестового окружения
    assert agent.model == "gpt-4o-transcribe"
    assert agent.client is not None

def test_run():
    agent = TranscriptionAgent(api_key="test-key")  # Используем test-key для тестового окружения

    # Создаём мок-объект для сегмента
    mock_segment = MagicMock()
    mock_segment.model_dump.return_value = {
        "id": 0,
        "start": 0,
        "end": 1,
        "text": "Hello world",
        "tokens": [1, 2, 3],
        "avg_logprob": -0.1,
        "no_speech_prob": 0.01,
        "temperature": 0,
        "compression_ratio": 1.0
    }

    # Создаём мок-объект для ответа транскрипции
    mock_transcript = MagicMock()
    mock_transcript.segments = [mock_segment]
    mock_transcript.duration = 1.0  # Добавляем duration как число

    # Мокируем client.with_options для правильной работы с timeout
    with patch.object(agent, 'client') as mock_client:
        # Создаем mock для with_options
        mock_client_with_timeout = MagicMock()
        mock_client.with_options.return_value = mock_client_with_timeout
        mock_client_with_timeout.audio.transcriptions.create.return_value = mock_transcript

        with patch('builtins.open', MagicMock()), \
             patch.object(Path, 'stat') as mock_stat, \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'read_bytes', return_value=b'fake audio data'):
            # Мокируем stat для получения размера файла
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB
            result = agent.run(Path("test.wav"), prompt="Test prompt")

            assert len(result) == 1
            assert result[0]["text"] == "Hello world"
            assert result[0]["start"] == 0
            assert result[0]["end"] == 1

            mock_client_with_timeout.audio.transcriptions.create.assert_called_once()
            # Проверяем, что параметры переданы корректно
            call_kwargs = mock_client_with_timeout.audio.transcriptions.create.call_args.kwargs
            assert call_kwargs["model"] == "whisper-1"  # модель по умолчанию
            assert call_kwargs["prompt"] == "Test prompt"
            assert call_kwargs["temperature"] == 0
            assert call_kwargs["response_format"] == "verbose_json"
