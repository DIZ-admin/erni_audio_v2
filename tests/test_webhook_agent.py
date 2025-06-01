"""
Тесты для WebhookAgent - обработки веб-хуков pyannote.ai
"""

import json
import hmac
import hashlib
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from pipeline.webhook_agent import WebhookAgent, WebhookEvent, WebhookVerificationError


class TestWebhookAgent:
    """Тесты для WebhookAgent"""
    
    @pytest.fixture
    def webhook_secret(self):
        """Тестовый секрет для веб-хуков"""
        return "whs_test_secret_12345"
    
    @pytest.fixture
    def webhook_agent(self, webhook_secret, tmp_path):
        """Создает WebhookAgent для тестов"""
        return WebhookAgent(webhook_secret, tmp_path)
    
    @pytest.fixture
    def sample_payload(self):
        """Пример payload веб-хука"""
        return {
            "jobId": "test-job-123",
            "status": "succeeded",
            "output": {
                "diarization": [
                    {"start": 0.0, "end": 5.0, "speaker": "speaker_1"},
                    {"start": 5.0, "end": 10.0, "speaker": "speaker_2"}
                ]
            }
        }
    
    def create_valid_signature(self, webhook_secret: str, timestamp: str, body: str) -> str:
        """Создает валидную подпись для тестов"""
        signed_content = f"v0:{timestamp}:{body}"
        signature = hmac.new(
            key=webhook_secret.encode('utf-8'),
            msg=signed_content.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        return signature
    
    def test_webhook_agent_initialization(self, webhook_agent, tmp_path):
        """Тест инициализации WebhookAgent"""
        assert webhook_agent.webhook_secret == "whs_test_secret_12345"
        assert webhook_agent.data_dir == tmp_path
        assert webhook_agent.processed_webhooks == 0
        assert webhook_agent.failed_verifications == 0
        assert webhook_agent.successful_events == 0
    
    def test_verify_signature_valid(self, webhook_agent):
        """Тест верификации валидной подписи"""
        timestamp = "1640995200"
        body = '{"jobId": "test", "status": "succeeded"}'
        signature = self.create_valid_signature(webhook_agent.webhook_secret, timestamp, body)
        
        result = webhook_agent.verify_signature(timestamp, body, signature)
        assert result is True
    
    def test_verify_signature_invalid(self, webhook_agent):
        """Тест верификации невалидной подписи"""
        timestamp = "1640995200"
        body = '{"jobId": "test", "status": "succeeded"}'
        invalid_signature = "invalid_signature"
        
        result = webhook_agent.verify_signature(timestamp, body, invalid_signature)
        assert result is False
        assert webhook_agent.failed_verifications == 1
    
    def test_verify_signature_wrong_secret(self, webhook_agent):
        """Тест верификации с неправильным секретом"""
        timestamp = "1640995200"
        body = '{"jobId": "test", "status": "succeeded"}'
        wrong_signature = self.create_valid_signature("wrong_secret", timestamp, body)
        
        result = webhook_agent.verify_signature(timestamp, body, wrong_signature)
        assert result is False
    
    def test_parse_webhook_payload_diarization(self, webhook_agent, sample_payload):
        """Тест парсинга payload диаризации"""
        headers = {}
        
        event = webhook_agent.parse_webhook_payload(sample_payload, headers)
        
        assert event.job_id == "test-job-123"
        assert event.status == "succeeded"
        assert event.job_type == "diarization"
        assert event.output == sample_payload["output"]
        assert event.retry_num is None
        assert event.retry_reason is None
    
    def test_parse_webhook_payload_voiceprint(self, webhook_agent):
        """Тест парсинга payload voiceprint"""
        payload = {
            "jobId": "voiceprint-job-456",
            "status": "succeeded",
            "output": {
                "voiceprint": "base64_encoded_voiceprint_data"
            }
        }
        headers = {}
        
        event = webhook_agent.parse_webhook_payload(payload, headers)
        
        assert event.job_id == "voiceprint-job-456"
        assert event.status == "succeeded"
        assert event.job_type == "voiceprint"
    
    def test_parse_webhook_payload_identify(self, webhook_agent):
        """Тест парсинга payload идентификации"""
        payload = {
            "jobId": "identify-job-789",
            "status": "succeeded",
            "output": {
                "identification": [
                    {"start": 0.0, "end": 5.0, "speaker": "John Doe"},
                    {"start": 5.0, "end": 10.0, "speaker": "Jane Smith"}
                ]
            }
        }
        headers = {}
        
        event = webhook_agent.parse_webhook_payload(payload, headers)
        
        assert event.job_id == "identify-job-789"
        assert event.status == "succeeded"
        assert event.job_type == "identify"
    
    def test_parse_webhook_payload_with_retry(self, webhook_agent, sample_payload):
        """Тест парсинга payload с информацией о повторе"""
        headers = {
            "x-retry-num": "2",
            "x-retry-reason": "http_timeout"
        }
        
        event = webhook_agent.parse_webhook_payload(sample_payload, headers)
        
        assert event.retry_num == 2
        assert event.retry_reason == "http_timeout"
    
    def test_parse_webhook_payload_missing_fields(self, webhook_agent):
        """Тест парсинга payload с отсутствующими полями"""
        payload = {"status": "succeeded"}  # Отсутствует jobId
        headers = {}
        
        with pytest.raises(ValueError, match="Отсутствуют обязательные поля"):
            webhook_agent.parse_webhook_payload(payload, headers)
    
    def test_process_webhook_event_succeeded(self, webhook_agent, sample_payload, tmp_path):
        """Тест обработки успешного события"""
        event = WebhookEvent(
            job_id="test-job-123",
            status="succeeded",
            job_type="diarization",
            output=sample_payload["output"],
            timestamp=datetime.now()
        )
        
        result = webhook_agent.process_webhook_event(event)
        
        assert result is True
        assert webhook_agent.processed_webhooks == 1
        assert webhook_agent.successful_events == 1
        
        # Проверяем, что файл сохранен
        saved_files = list(tmp_path.glob("*.json"))
        assert len(saved_files) == 1
    
    def test_process_webhook_event_canceled(self, webhook_agent):
        """Тест обработки отмененного события"""
        event = WebhookEvent(
            job_id="canceled-job-456",
            status="canceled",
            job_type="diarization",
            timestamp=datetime.now()
        )
        
        result = webhook_agent.process_webhook_event(event)
        
        assert result is True
        assert webhook_agent.processed_webhooks == 1
        assert webhook_agent.successful_events == 0  # Не считается успешным
    
    def test_register_event_handler(self, webhook_agent):
        """Тест регистрации обработчика событий"""
        handler_called = False
        
        def test_handler(event):
            nonlocal handler_called
            handler_called = True
        
        webhook_agent.register_event_handler("diarization", test_handler)
        
        # Создаем и обрабатываем событие
        event = WebhookEvent(
            job_id="test-job",
            status="succeeded",
            job_type="diarization",
            output={"diarization": []},
            timestamp=datetime.now()
        )
        
        webhook_agent.process_webhook_event(event)
        
        assert handler_called is True
    
    def test_get_metrics(self, webhook_agent):
        """Тест получения метрик"""
        # Симулируем некоторую активность
        webhook_agent.processed_webhooks = 10
        webhook_agent.failed_verifications = 2
        webhook_agent.successful_events = 8
        
        metrics = webhook_agent.get_metrics()
        
        assert metrics["processed_webhooks"] == 10
        assert metrics["failed_verifications"] == 2
        assert metrics["successful_events"] == 8
        assert metrics["verification_success_rate"] == 80.0
    
    def test_save_webhook_result(self, webhook_agent, tmp_path):
        """Тест сохранения результата веб-хука"""
        event = WebhookEvent(
            job_id="save-test-job",
            status="succeeded",
            job_type="diarization",
            output={"diarization": [{"start": 0, "end": 5, "speaker": "test"}]},
            timestamp=datetime.now(),
            retry_num=1,
            retry_reason="http_timeout"
        )
        
        saved_path = webhook_agent._save_webhook_result(event)
        
        assert saved_path.exists()
        assert saved_path.parent == tmp_path
        
        # Проверяем содержимое файла
        with open(saved_path, 'r') as f:
            data = json.load(f)
        
        assert data["job_id"] == "save-test-job"
        assert data["job_type"] == "diarization"
        assert data["status"] == "succeeded"
        assert data["output"]["diarization"][0]["speaker"] == "test"
        assert data["retry_info"]["retry_num"] == 1
        assert data["retry_info"]["retry_reason"] == "http_timeout"
    
    def test_detect_job_type(self, webhook_agent):
        """Тест определения типа задачи"""
        # Тест диаризации
        output = {"diarization": []}
        job_type = webhook_agent._detect_job_type(output)
        assert job_type == "diarization"
        
        # Тест идентификации
        output = {"identification": []}
        job_type = webhook_agent._detect_job_type(output)
        assert job_type == "identify"
        
        # Тест voiceprint
        output = {"voiceprint": "base64_data"}
        job_type = webhook_agent._detect_job_type(output)
        assert job_type == "voiceprint"
        
        # Тест неизвестного типа
        output = {"unknown_field": "data"}
        job_type = webhook_agent._detect_job_type(output)
        assert job_type == "unknown"
        
        # Тест пустого output
        job_type = webhook_agent._detect_job_type(None)
        assert job_type == "unknown"


if __name__ == "__main__":
    pytest.main([__file__])
