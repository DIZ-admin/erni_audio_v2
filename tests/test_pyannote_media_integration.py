# tests/test_pyannote_media_integration.py

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import asyncio

from pipeline.audio_agent import AudioLoaderAgent
from pipeline.diarization_agent import DiarizationAgent


class TestPyannoteMediaIntegration:
    """Интеграционные тесты для pyannote.ai Media API"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.test_api_key = "test_pyannote_api_key"

    def create_test_audio_file(self) -> Path:
        """Создает тестовый аудио файл"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            # Простейший WAV заголовок + данные
            wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00'
            wav_data = b'\x00\x00' * 1000  # Простые аудио данные
            tmp_file.write(wav_header + wav_data)
            return Path(tmp_file.name)

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.upload_file')
    def test_audio_agent_with_pyannote_media_success(self, mock_upload, mock_validate):
        """Тест успешной загрузки через pyannote.ai Media API"""
        # Настройка mock
        mock_validate.return_value = True
        mock_upload.return_value = "media://temp/audio_12345678_test.wav"

        # Создание тестового файла
        test_file = self.create_test_audio_file()

        try:
            # Создание агента с pyannote.ai Media API
            agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

            # Выполнение
            with patch.object(agent, 'to_wav16k_mono', return_value=test_file):
                wav_local, wav_url = agent.run(str(test_file))

            # Проверки
            assert wav_local == test_file
            assert wav_url == "media://temp/audio_12345678_test.wav"
            assert wav_url.startswith("media://")
            mock_validate.assert_called_once()
            mock_upload.assert_called_once()

        finally:
            # Очистка
            if test_file.exists():
                test_file.unlink()

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.upload_file')
    def test_audio_agent_upload_error(self, mock_upload, mock_validate):
        """Тест ошибки при загрузке в pyannote.ai Media API"""
        # Настройка mock
        mock_validate.return_value = True
        mock_upload.side_effect = RuntimeError("API error")

        # Создание тестового файла
        test_file = self.create_test_audio_file()

        try:
            # Создание агента
            agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

            # Выполнение и проверка ошибки
            with patch.object(agent, 'to_wav16k_mono', return_value=test_file):
                with pytest.raises(RuntimeError, match="Не удалось загрузить файл в pyannote.ai"):
                    agent.run(str(test_file))

            mock_upload.assert_called_once()

        finally:
            # Очистка
            if test_file.exists():
                test_file.unlink()

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_audio_agent_invalid_api_key(self, mock_validate):
        """Тест обработки неверного API ключа"""
        # Настройка mock
        mock_validate.return_value = False

        # Проверки - должна быть ошибка при инициализации
        with pytest.raises(RuntimeError, match="Не удалось инициализировать pyannote.ai Media API"):
            AudioLoaderAgent(pyannote_api_key="invalid_key")

    def test_audio_agent_no_api_key(self):
        """Тест обработки отсутствующего API ключа"""
        # Создание агента без API ключа
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Требуется API ключ pyannote.ai"):
                AudioLoaderAgent()

    @patch('requests.post')
    def test_diarization_agent_with_media_url(self, mock_post):
        """Тест работы DiarizationAgent с виртуальными путями pyannote.ai"""
        # Настройка mock для создания задачи
        mock_create_response = Mock()
        mock_create_response.json.return_value = {"jobId": "test_job_123"}
        mock_create_response.raise_for_status.return_value = None

        # Настройка mock для опроса статуса
        mock_poll_response = Mock()
        mock_poll_response.json.return_value = {
            "status": "done",
            "output": {
                "diarization": [
                    {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00", "confidence": 0.95}
                ]
            }
        }
        mock_poll_response.raise_for_status.return_value = None

        mock_post.return_value = mock_create_response

        # Создание агента
        agent = DiarizationAgent(api_key=self.test_api_key)

        # Выполнение с виртуальным путем
        media_url = "media://temp/audio_12345678_test.wav"
        
        with patch('requests.get', return_value=mock_poll_response):
            result = agent.diarize(media_url)

        # Проверки
        assert len(result) == 1
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 5.0

        # Проверяем, что был сделан правильный запрос
        mock_post.assert_called_once_with(
            "https://api.pyannote.ai/v1/diarize",
            json={"url": media_url},
            headers=agent.headers,
            timeout=30
        )

    @patch('requests.post')
    def test_diarization_agent_with_regular_url(self, mock_post):
        """Тест работы DiarizationAgent с обычными URL"""
        # Настройка mock
        mock_create_response = Mock()
        mock_create_response.json.return_value = {"jobId": "test_job_456"}
        mock_create_response.raise_for_status.return_value = None

        mock_poll_response = Mock()
        mock_poll_response.json.return_value = {
            "status": "done",
            "output": {
                "diarization": [
                    {"start": 0.0, "end": 3.0, "speaker": "SPEAKER_01", "confidence": 0.88}
                ]
            }
        }
        mock_poll_response.raise_for_status.return_value = None

        mock_post.return_value = mock_create_response

        # Создание агента
        agent = DiarizationAgent(api_key=self.test_api_key)

        # Выполнение с обычным URL
        regular_url = "https://example.com/audio.wav"
        
        with patch('requests.get', return_value=mock_poll_response):
            result = agent.diarize(regular_url)

        # Проверки
        assert len(result) == 1
        assert result[0]["speaker"] == "SPEAKER_01"

        # Проверяем, что был сделан правильный запрос
        mock_post.assert_called_once_with(
            "https://api.pyannote.ai/v1/diarize",
            json={"url": regular_url},
            headers=agent.headers,
            timeout=30
        )

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.upload_file')
    def test_successful_upload_workflow(self, mock_upload, mock_validate):
        """Тест полного рабочего процесса загрузки"""
        # Настройка mock
        mock_validate.return_value = True
        mock_upload.return_value = "media://temp/test_workflow.wav"

        # Создание тестового файла
        test_file = self.create_test_audio_file()

        try:
            # Создание агента
            agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

            # Выполнение
            with patch.object(agent, 'to_wav16k_mono', return_value=test_file):
                wav_local, wav_url = agent.run(str(test_file))

            # Проверки - должен использоваться pyannote.ai Media API
            assert wav_url.startswith("media://")
            assert wav_url == "media://temp/test_workflow.wav"
            mock_upload.assert_called_once()

        finally:
            # Очистка
            if test_file.exists():
                test_file.unlink()
