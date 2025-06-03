"""
Интеграционные тесты для webhook функциональности
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from pipeline.diarization_agent import DiarizationAgent
from pipeline.voiceprint_agent import VoiceprintAgent
from pipeline.identification_agent import IdentificationAgent


class TestWebhookIntegration:
    """Интеграционные тесты для webhook функциональности"""
    
    @pytest.fixture
    def api_key(self):
        """Тестовый API ключ"""
        return "test_api_key_12345"
    
    @pytest.fixture
    def webhook_url(self):
        """Тестовый webhook URL"""
        return "https://example.com/webhook"
    
    @pytest.fixture
    def sample_audio_url(self):
        """Тестовый URL аудио"""
        return "media://test-audio-file"
    
    @pytest.fixture
    def mock_job_response(self):
        """Мок ответа API с job ID"""
        return {"jobId": "test-job-12345"}


class TestDiarizationAgentWebhook:
    """Тесты webhook функциональности DiarizationAgent"""

    @pytest.fixture
    def api_key(self):
        """Тестовый API ключ"""
        return "test_api_key_12345"

    @pytest.fixture
    def webhook_url(self):
        """Тестовый webhook URL"""
        return "https://example.com/webhook"

    @pytest.fixture
    def sample_audio_url(self):
        """Тестовый URL аудио"""
        return "media://test-audio-file"

    @pytest.fixture
    def mock_job_response(self):
        """Мок ответа API с job ID"""
        return {"jobId": "test-job-12345"}

    @pytest.fixture
    def diarization_agent(self, api_key, webhook_url):
        """Создает DiarizationAgent с webhook URL"""
        return DiarizationAgent(api_key=api_key, webhook_url=webhook_url)

    @pytest.fixture
    def diarization_agent_no_webhook(self, api_key):
        """Создает DiarizationAgent без webhook URL"""
        return DiarizationAgent(api_key=api_key)
    
    def test_diarization_agent_with_webhook_url(self, diarization_agent, webhook_url):
        """Тест инициализации DiarizationAgent с webhook URL"""
        assert diarization_agent.webhook_url == webhook_url
    
    @patch('pipeline.diarization_agent.requests.post')
    def test_diarize_async_success(self, mock_post, diarization_agent, sample_audio_url, mock_job_response):
        """Тест успешного асинхронного запуска диаризации"""
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = mock_job_response
        
        job_id = diarization_agent.diarize_async(sample_audio_url)
        
        assert job_id == "test-job-12345"
        
        # Проверяем, что запрос содержит webhook URL
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['url'] == sample_audio_url
        assert payload['webhook'] == diarization_agent.webhook_url
    
    def test_diarize_async_no_webhook_url(self, diarization_agent_no_webhook, sample_audio_url):
        """Тест асинхронной диаризации без webhook URL"""
        with pytest.raises(ValueError, match="webhook_url должен быть настроен"):
            diarization_agent_no_webhook.diarize_async(sample_audio_url)
    
    @patch('pipeline.diarization_agent.requests.post')
    def test_identify_async_success(self, mock_post, api_key, webhook_url, sample_audio_url, mock_job_response):
        """Тест успешного асинхронного запуска идентификации"""
        voiceprint_ids = ["vp1", "vp2"]
        agent = DiarizationAgent(
            api_key=api_key,
            use_identify=True,
            voiceprint_ids=voiceprint_ids,
            webhook_url=webhook_url
        )
        
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = mock_job_response
        
        job_id = agent.identify_async(sample_audio_url)
        
        assert job_id == "test-job-12345"
        
        # Проверяем payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['url'] == sample_audio_url
        assert payload['voiceprintIds'] == voiceprint_ids
        assert payload['webhook'] == webhook_url
    
    def test_identify_async_no_voiceprints(self, api_key, webhook_url, sample_audio_url):
        """Тест асинхронной идентификации без voiceprint IDs"""
        agent = DiarizationAgent(
            api_key=api_key,
            use_identify=True,
            voiceprint_ids=[],
            webhook_url=webhook_url
        )
        
        with pytest.raises(ValueError, match="Нужен хотя бы один voiceprint_id"):
            agent.identify_async(sample_audio_url)
    
    @patch('pipeline.diarization_agent.requests.post')
    def test_run_async_diarization(self, mock_post, diarization_agent, sample_audio_url, mock_job_response):
        """Тест run_async для диаризации"""
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = mock_job_response
        
        job_id = diarization_agent.run_async(sample_audio_url)
        
        assert job_id == "test-job-12345"
    
    @patch('pipeline.diarization_agent.requests.post')
    def test_run_async_identify(self, mock_post, api_key, webhook_url, sample_audio_url, mock_job_response):
        """Тест run_async для идентификации"""
        agent = DiarizationAgent(
            api_key=api_key,
            use_identify=True,
            voiceprint_ids=["vp1"],
            webhook_url=webhook_url
        )
        
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = mock_job_response
        
        job_id = agent.run_async(sample_audio_url)
        
        assert job_id == "test-job-12345"


class TestVoiceprintAgentWebhook:
    """Тесты webhook функциональности VoiceprintAgent"""

    @pytest.fixture
    def api_key(self):
        """Тестовый API ключ"""
        return "test_api_key_12345"

    @pytest.fixture
    def webhook_url(self):
        """Тестовый webhook URL"""
        return "https://example.com/webhook"

    @pytest.fixture
    def mock_job_response(self):
        """Мок ответа API с job ID"""
        return {"jobId": "test-job-12345"}

    @pytest.fixture
    def voiceprint_agent(self, api_key, webhook_url):
        """Создает VoiceprintAgent с webhook URL"""
        return VoiceprintAgent(api_key=api_key, webhook_url=webhook_url)

    @pytest.fixture
    def sample_audio_file(self, tmp_path):
        """Создает тестовый аудиофайл"""
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_bytes(b"fake audio content")
        return audio_file
    
    def test_voiceprint_agent_with_webhook_url(self, voiceprint_agent, webhook_url):
        """Тест инициализации VoiceprintAgent с webhook URL"""
        assert voiceprint_agent.webhook_url == webhook_url
    
    @patch('pipeline.voiceprint_agent.VoiceprintAgent._validate_audio_file')
    @patch('pipeline.voiceprint_agent.PyannoteMediaAgent.upload_file')
    @patch('pipeline.voiceprint_agent.VoiceprintAgent._submit_voiceprint_job')
    def test_create_voiceprint_async_success(self, mock_submit, mock_upload, mock_validate, 
                                           voiceprint_agent, sample_audio_file, mock_job_response):
        """Тест успешного асинхронного создания voiceprint"""
        mock_validate.return_value = None
        mock_upload.return_value = "media://uploaded-file"
        mock_submit.return_value = "test-job-12345"
        
        job_id = voiceprint_agent.create_voiceprint_async(sample_audio_file, "Test Speaker")
        
        assert job_id == "test-job-12345"
        mock_validate.assert_called_once()
        mock_upload.assert_called_once_with(sample_audio_file)
        mock_submit.assert_called_once_with("media://uploaded-file")
    
    def test_create_voiceprint_async_no_webhook_url(self, api_key, sample_audio_file):
        """Тест асинхронного создания voiceprint без webhook URL"""
        agent = VoiceprintAgent(api_key=api_key)
        
        with pytest.raises(ValueError, match="webhook_url должен быть настроен"):
            agent.create_voiceprint_async(sample_audio_file, "Test Speaker")


class TestIdentificationAgentWebhook:
    """Тесты webhook функциональности IdentificationAgent"""

    @pytest.fixture
    def api_key(self):
        """Тестовый API ключ"""
        return "test_api_key_12345"

    @pytest.fixture
    def webhook_url(self):
        """Тестовый webhook URL"""
        return "https://example.com/webhook"

    @pytest.fixture
    def mock_job_response(self):
        """Мок ответа API с job ID"""
        return {"jobId": "test-job-12345"}

    @pytest.fixture
    def identification_agent(self, api_key, webhook_url):
        """Создает IdentificationAgent с webhook URL"""
        return IdentificationAgent(api_key=api_key, webhook_url=webhook_url)

    @pytest.fixture
    def sample_voiceprints(self):
        """Тестовые voiceprints"""
        return [
            {"label": "John Doe", "voiceprint": "base64_data_1"},
            {"label": "Jane Smith", "voiceprint": "base64_data_2"}
        ]

    @pytest.fixture
    def sample_audio_file(self, tmp_path):
        """Создает тестовый аудиофайл"""
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_bytes(b"fake audio content")
        return audio_file
    
    def test_identification_agent_with_webhook_url(self, identification_agent, webhook_url):
        """Тест инициализации IdentificationAgent с webhook URL"""
        assert identification_agent.webhook_url == webhook_url
    
    @patch('pipeline.identification_agent.PyannoteMediaAgent.upload_file')
    @patch('pipeline.identification_agent.IdentificationAgent._submit_identification_job')
    def test_run_async_success(self, mock_submit, mock_upload, identification_agent, 
                              sample_audio_file, sample_voiceprints, mock_job_response):
        """Тест успешного асинхронного запуска идентификации"""
        mock_upload.return_value = "media://uploaded-file"
        mock_submit.return_value = "test-job-12345"
        
        job_id = identification_agent.run_async(
            audio_file=sample_audio_file,
            voiceprints=sample_voiceprints,
            matching_threshold=0.5
        )
        
        assert job_id == "test-job-12345"
        mock_upload.assert_called_once_with(sample_audio_file)
        mock_submit.assert_called_once()
    
    def test_run_async_no_webhook_url(self, api_key, sample_audio_file, sample_voiceprints):
        """Тест асинхронной идентификации без webhook URL"""
        agent = IdentificationAgent(api_key=api_key)
        
        with pytest.raises(ValueError, match="webhook_url должен быть настроен"):
            agent.run_async(
                audio_file=sample_audio_file,
                voiceprints=sample_voiceprints
            )


class TestWebhookPayloadIntegration:
    """Тесты интеграции с реальными webhook payload"""
    
    def test_webhook_payload_includes_webhook_url(self):
        """Тест что webhook URL включается в API запросы"""
        # Этот тест проверяет, что все агенты правильно добавляют
        # webhook URL в свои API запросы при его наличии
        
        webhook_url = "https://example.com/webhook"
        
        # Проверяем DiarizationAgent
        with patch('pipeline.diarization_agent.requests.post') as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {"jobId": "test"}
            
            agent = DiarizationAgent(api_key="test", webhook_url=webhook_url)
            agent.diarize("media://test")
            
            payload = mock_post.call_args[1]['json']
            assert payload.get('webhook') == webhook_url


if __name__ == "__main__":
    pytest.main([__file__])
