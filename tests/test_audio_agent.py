import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from pipeline.audio_agent import AudioLoaderAgent


class TestAudioLoaderAgent:
    """Тесты для AudioLoaderAgent с pyannote.ai Media API"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.test_api_key = "test_pyannote_api_key"

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_init_success(self, mock_validate):
        """Тест успешной инициализации агента"""
        mock_validate.return_value = True

        agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

        assert agent.pyannote_media_agent is not None
        assert agent.remote_wav_url is None
        mock_validate.assert_called_once()

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_init_invalid_api_key(self, mock_validate):
        """Тест инициализации с неверным API ключом"""
        mock_validate.return_value = False

        with pytest.raises(RuntimeError, match="Не удалось инициализировать pyannote.ai Media API"):
            AudioLoaderAgent(pyannote_api_key=self.test_api_key)

    def test_init_no_api_key(self):
        """Тест инициализации без API ключа"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Требуется API ключ pyannote.ai"):
                AudioLoaderAgent()

    @patch.dict(os.environ, {'PYANNOTEAI_API_TOKEN': 'env_api_key'})
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_init_from_env_new_format(self, mock_validate):
        """Тест инициализации с API ключом из переменной окружения (новый формат)"""
        mock_validate.return_value = True

        agent = AudioLoaderAgent()

        assert agent.pyannote_media_agent is not None
        mock_validate.assert_called_once()

    @patch.dict(os.environ, {'PYANNOTE_API_KEY': 'old_env_api_key'})
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_init_from_env_old_format(self, mock_validate):
        """Тест инициализации с API ключом из переменной окружения (старый формат)"""
        mock_validate.return_value = True

        agent = AudioLoaderAgent()

        assert agent.pyannote_media_agent is not None
        mock_validate.assert_called_once()

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_to_wav16k_mono(self, mock_validate):
        """Тест конвертации аудио в WAV 16kHz mono"""
        mock_validate.return_value = True
        agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = agent.to_wav16k_mono("test.mp3")

            assert isinstance(result, Path)
            assert result.suffix == ".wav"
            mock_run.assert_called_once()

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.upload_file')
    def test_upload_file_success(self, mock_upload, mock_validate):
        """Тест успешной загрузки файла"""
        mock_validate.return_value = True
        mock_upload.return_value = "media://temp/audio_12345678_test.wav"

        agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)
        result = agent.upload_file(Path("test.wav"))

        assert result == "media://temp/audio_12345678_test.wav"
        assert result.startswith("media://")
        mock_upload.assert_called_once_with(Path("test.wav"))

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.upload_file')
    def test_upload_file_error(self, mock_upload, mock_validate):
        """Тест ошибки при загрузке файла"""
        mock_validate.return_value = True
        mock_upload.side_effect = RuntimeError("API error")

        agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

        with pytest.raises(RuntimeError, match="Не удалось загрузить файл в pyannote.ai"):
            agent.upload_file(Path("test.wav"))

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_run_local_file(self, mock_validate):
        """Тест обработки локального файла"""
        mock_validate.return_value = True
        agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

        with patch('pathlib.Path.exists', return_value=True), \
             patch.object(agent, 'to_wav16k_mono') as mock_convert, \
             patch.object(agent, 'upload_file') as mock_upload:

            mock_convert.return_value = Path("/tmp/test.wav")
            mock_upload.return_value = "media://temp/audio_12345678_test.wav"

            wav_local, wav_url = agent.run("test.mp3")

            assert wav_local == Path("/tmp/test.wav")
            assert wav_url == "media://temp/audio_12345678_test.wav"
            mock_convert.assert_called_once_with("test.mp3")
            mock_upload.assert_called_once_with(Path("/tmp/test.wav"))

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_run_remote_url(self, mock_validate):
        """Тест обработки с готовым remote URL"""
        mock_validate.return_value = True
        agent = AudioLoaderAgent(
            remote_wav_url="https://example.com/audio.wav",
            pyannote_api_key=self.test_api_key
        )

        with patch('pathlib.Path.exists', return_value=False), \
             patch.object(agent, 'to_wav16k_mono') as mock_convert:

            mock_convert.return_value = Path("/tmp/test.wav")

            wav_local, wav_url = agent.run("https://source.com/audio.mp3")

            assert wav_local == Path("/tmp/test.wav")
            assert wav_url == "https://example.com/audio.wav"
            mock_convert.assert_called_once_with("https://source.com/audio.mp3")

    @patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key')
    def test_run_conversion_error(self, mock_validate):
        """Тест ошибки конвертации"""
        mock_validate.return_value = True
        agent = AudioLoaderAgent(pyannote_api_key=self.test_api_key)

        with patch('pathlib.Path.exists', return_value=True), \
             patch.object(agent, 'to_wav16k_mono') as mock_convert:

            mock_convert.side_effect = RuntimeError("FFmpeg error")

            with pytest.raises(RuntimeError, match="FFmpeg error"):
                agent.run("test.mp3")
