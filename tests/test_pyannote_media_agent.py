# tests/test_pyannote_media_agent.py

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import requests

from pipeline.pyannote_media_agent import PyannoteMediaAgent


class TestPyannoteMediaAgent:
    """Тесты для PyannoteMediaAgent"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.api_key = "test_api_key"
        self.agent = PyannoteMediaAgent(self.api_key)

    def test_init(self):
        """Тест инициализации агента"""
        assert self.agent.api_key == self.api_key
        assert self.agent.headers["Authorization"] == f"Bearer {self.api_key}"
        assert self.agent.headers["Content-Type"] == "application/json"
        assert self.agent.base_url == "https://api.pyannote.ai/v1"

    @patch('requests.post')
    def test_create_presigned_url_success(self, mock_post):
        """Тест успешного создания pre-signed URL"""
        # Настройка mock
        mock_response = Mock()
        mock_response.json.return_value = {"url": "https://presigned.url/test"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Выполнение
        virtual_path = "media://temp/test.wav"
        result = self.agent._create_presigned_url(virtual_path)

        # Проверки
        assert result == "https://presigned.url/test"
        mock_post.assert_called_once_with(
            "https://api.pyannote.ai/v1/media/input",
            json={"url": virtual_path},
            headers=self.agent.headers,
            timeout=30
        )

    @patch('requests.post')
    def test_create_presigned_url_auth_error(self, mock_post):
        """Тест ошибки аутентификации при создании pre-signed URL"""
        # Настройка mock
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        # Создаем HTTPError с response
        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_post.return_value.raise_for_status.side_effect = http_error

        # Выполнение и проверка
        with pytest.raises(RuntimeError, match="Неверный API ключ pyannote.ai"):
            self.agent._create_presigned_url("media://temp/test.wav")

    @patch('requests.post')
    def test_create_presigned_url_rate_limit_error(self, mock_post):
        """Тест ошибки превышения лимита при создании pre-signed URL"""
        # Настройка mock
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        # Создаем HTTPError с response
        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_post.return_value.raise_for_status.side_effect = http_error

        # Выполнение и проверка
        with pytest.raises(RuntimeError, match="Превышен лимит запросов pyannote.ai"):
            self.agent._create_presigned_url("media://temp/test.wav")

    @patch('requests.put')
    @patch('builtins.open', new_callable=mock_open, read_data=b"test audio data")
    def test_upload_file_to_presigned_url_success(self, mock_file, mock_put):
        """Тест успешной загрузки файла по pre-signed URL"""
        # Настройка mock
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_put.return_value = mock_response

        # Выполнение
        file_path = Path("test.wav")
        presigned_url = "https://presigned.url/test"
        self.agent._upload_file_to_presigned_url(file_path, presigned_url)

        # Проверки
        mock_put.assert_called_once_with(
            presigned_url,
            data=mock_file.return_value,
            timeout=120
        )

    @patch('requests.put')
    @patch('builtins.open', side_effect=IOError("File not found"))
    def test_upload_file_to_presigned_url_file_error(self, mock_file, mock_put):
        """Тест ошибки чтения файла при загрузке"""
        # Выполнение и проверка
        file_path = Path("nonexistent.wav")
        presigned_url = "https://presigned.url/test"
        
        with pytest.raises(RuntimeError, match="Не удалось прочитать файл"):
            self.agent._upload_file_to_presigned_url(file_path, presigned_url)

    @patch.object(PyannoteMediaAgent, '_upload_file_to_presigned_url')
    @patch.object(PyannoteMediaAgent, '_create_presigned_url')
    def test_upload_file_success(self, mock_create_url, mock_upload):
        """Тест успешной загрузки файла"""
        # Настройка mock
        mock_create_url.return_value = "https://presigned.url/test"
        mock_upload.return_value = None

        # Создание временного файла
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(b"test audio data")
            file_path = Path(tmp_file.name)

        try:
            # Выполнение
            result = self.agent.upload_file(file_path)

            # Проверки - код использует формат media://example/conversation-{id}.wav
            assert result.startswith("media://example/conversation-")
            assert result.endswith(".wav")
            mock_create_url.assert_called_once()
            mock_upload.assert_called_once()

        finally:
            # Очистка
            if file_path.exists():
                file_path.unlink()

    @patch.object(PyannoteMediaAgent, '_upload_file_to_presigned_url')
    @patch.object(PyannoteMediaAgent, '_create_presigned_url')
    def test_upload_file_with_custom_name(self, mock_create_url, mock_upload):
        """Тест загрузки файла с пользовательским именем"""
        # Настройка mock
        mock_create_url.return_value = "https://presigned.url/test"
        mock_upload.return_value = None

        # Создание временного файла
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(b"test audio data")
            file_path = Path(tmp_file.name)

        try:
            # Выполнение
            custom_name = "custom_audio.wav"
            result = self.agent.upload_file(file_path, custom_name)

            # Проверки - код использует формат media://example/{custom_name}
            assert result == f"media://example/{custom_name}"
            mock_create_url.assert_called_once_with(f"media://example/{custom_name}")
            mock_upload.assert_called_once()

        finally:
            # Очистка
            if file_path.exists():
                file_path.unlink()

    @patch('requests.get')
    def test_validate_api_key_success(self, mock_get):
        """Тест успешной валидации API ключа"""
        # Настройка mock
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Выполнение
        result = self.agent.validate_api_key()

        # Проверки
        assert result is True
        mock_get.assert_called_once_with(
            "https://api.pyannote.ai/v1/test",
            headers=self.agent.headers,
            timeout=10
        )

    @patch('requests.get')
    def test_validate_api_key_failure(self, mock_get):
        """Тест неуспешной валидации API ключа"""
        # Настройка mock
        mock_get.side_effect = requests.RequestException("API error")

        # Выполнение
        result = self.agent.validate_api_key()

        # Проверки
        assert result is False

    @patch.object(PyannoteMediaAgent, '_create_presigned_url')
    def test_upload_file_create_url_error(self, mock_create_url):
        """Тест ошибки при создании pre-signed URL"""
        # Настройка mock
        mock_create_url.side_effect = RuntimeError("API error")

        # Создание временного файла
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(b"test audio data")
            file_path = Path(tmp_file.name)

        try:
            # Выполнение и проверка
            with pytest.raises(RuntimeError, match="Не удалось загрузить файл в pyannote.ai"):
                self.agent.upload_file(file_path)

        finally:
            # Очистка
            if file_path.exists():
                file_path.unlink()

    def test_headers_format(self):
        """Тест правильного формата заголовков"""
        expected_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        assert self.agent.headers == expected_headers
