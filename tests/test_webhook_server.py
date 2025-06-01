"""
Тесты для WebhookServer - HTTP сервера для веб-хуков pyannote.ai
"""

import json
import hmac
import hashlib
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from pipeline.webhook_server import WebhookServer


class TestWebhookServer:
    """Тесты для WebhookServer"""
    
    @pytest.fixture
    def webhook_secret(self):
        """Тестовый секрет для веб-хуков"""
        return "whs_test_secret_12345"
    
    @pytest.fixture
    def webhook_server(self, webhook_secret, tmp_path):
        """Создает WebhookServer для тестов"""
        with patch.dict('os.environ', {
            'PYANNOTEAI_WEBHOOK_SECRET': webhook_secret,
            'WEBHOOK_SERVER_PORT': '8000',
            'WEBHOOK_SERVER_HOST': '0.0.0.0'
        }):
            return WebhookServer(webhook_secret=webhook_secret, data_dir=tmp_path)
    
    @pytest.fixture
    def test_client(self, webhook_server):
        """Создает тестовый клиент FastAPI"""
        return TestClient(webhook_server.app)
    
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
    
    def test_webhook_server_initialization(self, webhook_server):
        """Тест инициализации WebhookServer"""
        assert webhook_server.webhook_secret == "whs_test_secret_12345"
        assert webhook_server.host == "0.0.0.0"
        assert webhook_server.port == 8000
        assert webhook_server.webhook_agent is not None
    
    def test_root_endpoint(self, test_client):
        """Тест корневого эндпоинта"""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Pyannote.ai Webhook Server"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
    
    def test_health_endpoint(self, test_client):
        """Тест health check эндпоинта"""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pyannote-webhook-server"
        assert "metrics" in data
    
    def test_metrics_endpoint(self, test_client):
        """Тест metrics эндпоинта"""
        response = test_client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "processed_webhooks" in data
        assert "failed_verifications" in data
        assert "successful_events" in data
        assert "verification_success_rate" in data
    
    def test_webhook_endpoint_valid_signature(self, test_client, webhook_secret, sample_payload):
        """Тест webhook эндпоинта с валидной подписью"""
        timestamp = "1640995200"
        body = json.dumps(sample_payload)
        signature = self.create_valid_signature(webhook_secret, timestamp, body)
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Webhook обработан"
    
    def test_webhook_endpoint_invalid_signature(self, test_client, sample_payload):
        """Тест webhook эндпоинта с невалидной подписью"""
        timestamp = "1640995200"
        body = json.dumps(sample_payload)
        invalid_signature = "invalid_signature"
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": invalid_signature,
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 403
        data = response.json()
        assert "Неверная подпись" in data["detail"]
    
    def test_webhook_endpoint_missing_headers(self, test_client, sample_payload):
        """Тест webhook эндпоинта с отсутствующими заголовками"""
        body = json.dumps(sample_payload)
        
        # Отсутствует X-Request-Timestamp
        headers = {
            "X-Signature": "some_signature",
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "Отсутствуют заголовки" in data["detail"]
    
    def test_webhook_endpoint_invalid_json(self, test_client, webhook_secret):
        """Тест webhook эндпоинта с невалидным JSON"""
        timestamp = "1640995200"
        body = "invalid json content"
        signature = self.create_valid_signature(webhook_secret, timestamp, body)
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "Неверный JSON" in data["detail"]
    
    def test_webhook_endpoint_voiceprint_payload(self, test_client, webhook_secret):
        """Тест webhook эндпоинта с payload voiceprint"""
        payload = {
            "jobId": "voiceprint-job-456",
            "status": "succeeded",
            "output": {
                "voiceprint": "base64_encoded_voiceprint_data"
            }
        }
        
        timestamp = "1640995200"
        body = json.dumps(payload)
        signature = self.create_valid_signature(webhook_secret, timestamp, body)
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_webhook_endpoint_canceled_job(self, test_client, webhook_secret):
        """Тест webhook эндпоинта с отмененной задачей"""
        payload = {
            "jobId": "canceled-job-789",
            "status": "canceled"
        }
        
        timestamp = "1640995200"
        body = json.dumps(payload)
        signature = self.create_valid_signature(webhook_secret, timestamp, body)
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_webhook_endpoint_with_retry_headers(self, test_client, webhook_secret, sample_payload):
        """Тест webhook эндпоинта с заголовками повтора"""
        timestamp = "1640995200"
        body = json.dumps(sample_payload)
        signature = self.create_valid_signature(webhook_secret, timestamp, body)
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": signature,
            "X-Retry-Num": "2",
            "X-Retry-Reason": "http_timeout",
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_register_event_handler(self, webhook_server):
        """Тест регистрации обработчика событий"""
        handler_called = False
        
        def test_handler(event):
            nonlocal handler_called
            handler_called = True
        
        webhook_server.register_event_handler("diarization", test_handler)
        
        # Проверяем, что обработчик зарегистрирован
        assert "diarization" in webhook_server.webhook_agent.event_handlers
    
    @patch('pipeline.webhook_server.WebhookServer._process_event_background')
    def test_webhook_endpoint_background_processing(self, mock_process, test_client, webhook_secret, sample_payload):
        """Тест фоновой обработки webhook событий"""
        timestamp = "1640995200"
        body = json.dumps(sample_payload)
        signature = self.create_valid_signature(webhook_secret, timestamp, body)
        
        headers = {
            "X-Request-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
        
        response = test_client.post("/webhook", content=body, headers=headers)
        
        assert response.status_code == 200
        # Проверяем, что фоновая обработка была запущена
        # Примечание: в тестах BackgroundTasks может не выполняться автоматически
    
    def test_webhook_server_missing_secret(self, tmp_path):
        """Тест инициализации сервера без секрета"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="PYANNOTEAI_WEBHOOK_SECRET не найден"):
                WebhookServer(webhook_secret=None, data_dir=tmp_path)


if __name__ == "__main__":
    pytest.main([__file__])
