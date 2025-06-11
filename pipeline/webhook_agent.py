"""
WebhookAgent для обработки веб-хуков pyannote.ai

Этот агент обрабатывает HTTP POST запросы от pyannote.ai с результатами
выполненных задач (diarization, identify, voiceprint).
"""

import hmac
import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import asyncio
from dataclasses import dataclass

from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin
from .retry_mixin import RetryMixin
from .rate_limit_mixin import RateLimitMixin
from .utils import save_json


@dataclass
class WebhookEvent:
    """Структура события веб-хука"""
    job_id: str
    status: str
    job_type: str  # 'diarization', 'identify', 'voiceprint'
    output: Optional[Dict] = None
    timestamp: datetime = None
    retry_num: Optional[int] = None
    retry_reason: Optional[str] = None


class WebhookVerificationError(Exception):
    """Ошибка верификации подписи веб-хука"""
    pass


class WebhookAgent(BaseAgent, ValidationMixin, RetryMixin, RateLimitMixin):
    """
    Агент для обработки веб-хуков pyannote.ai.

    Функции:
    - Верификация подписи веб-хука согласно документации pyannote.ai
    - Парсинг и валидация payload
    - Сохранение результатов в data/interim/
    - Уведомления о завершении задач
    - Обработка повторных попыток
    """

    def __init__(self, webhook_secret: str, data_dir: Path = None):
        """
        Инициализация WebhookAgent.

        Args:
            webhook_secret: Секрет для верификации подписи веб-хука
            data_dir: Директория для сохранения результатов (по умолчанию data/interim)
        """
        # Инициализация базовых классов
        BaseAgent.__init__(self, name="WebhookAgent")
        ValidationMixin.__init__(self)
        RetryMixin.__init__(self)
        RateLimitMixin.__init__(self, api_name="webhook")

        # Валидация webhook secret
        if not webhook_secret or len(webhook_secret) < 10:
            raise ValueError("webhook_secret должен содержать минимум 10 символов")

        self.webhook_secret = webhook_secret
        self.data_dir = data_dir or Path("data/interim")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.event_handlers: Dict[str, Callable] = {}

        # Метрики
        self.processed_webhooks = 0
        self.failed_verifications = 0
        self.successful_events = 0

        self.log_with_emoji("info", "✅", "WebhookAgent инициализирован")
    
    def verify_signature(self, timestamp: str, body: str, received_signature: str) -> bool:
        """
        Верифицирует подпись веб-хука согласно документации pyannote.ai.
        
        Args:
            timestamp: Временная метка из заголовка X-Request-Timestamp
            body: Сырое тело запроса
            received_signature: Подпись из заголовка X-Signature
            
        Returns:
            True если подпись валидна, False иначе
            
        Raises:
            WebhookVerificationError: При ошибке верификации
        """
        try:
            # 1. Создаем подписанный контент: v0:timestamp:body
            signed_content = f"v0:{timestamp}:{body}"
            
            # 2. Вычисляем HMAC-SHA256 хеш
            calculated_signature = hmac.new(
                key=self.webhook_secret.encode('utf-8'),
                msg=signed_content.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # 3. Сравниваем подписи (защищенное сравнение)
            is_valid = hmac.compare_digest(calculated_signature, received_signature)
            
            if is_valid:
                self.logger.debug(f"✅ Подпись веб-хука валидна для job timestamp {timestamp}")
            else:
                self.logger.warning(f"❌ Неверная подпись веб-хука для timestamp {timestamp}")
                self.failed_verifications += 1
                
            return is_valid
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка верификации подписи: {e}")
            raise WebhookVerificationError(f"Ошибка верификации: {e}")
    
    def parse_webhook_payload(self, payload: Dict[str, Any], headers: Dict[str, str]) -> WebhookEvent:
        """
        Парсит payload веб-хука в структурированное событие.
        
        Args:
            payload: JSON payload веб-хука
            headers: HTTP заголовки запроса
            
        Returns:
            WebhookEvent с распарсенными данными
        """
        # Извлекаем основные поля
        job_id = payload.get("jobId")
        status = payload.get("status")
        output = payload.get("output")
        
        if not job_id or not status:
            raise ValueError("Отсутствуют обязательные поля jobId или status")
        
        # Определяем тип задачи по структуре output
        job_type = self._detect_job_type(output)
        
        # Извлекаем информацию о повторах из заголовков
        retry_num = headers.get("x-retry-num")
        retry_reason = headers.get("x-retry-reason")
        
        if retry_num:
            retry_num = int(retry_num)
            self.logger.info(f"🔄 Повторная попытка #{retry_num} для job {job_id}, причина: {retry_reason}")
        
        return WebhookEvent(
            job_id=job_id,
            status=status,
            job_type=job_type,
            output=output,
            timestamp=datetime.now(),
            retry_num=retry_num,
            retry_reason=retry_reason
        )
    
    def _detect_job_type(self, output: Optional[Dict]) -> str:
        """
        Определяет тип задачи по структуре output.
        
        Args:
            output: Выходные данные задачи
            
        Returns:
            Тип задачи: 'diarization', 'identify', 'voiceprint'
        """
        if not output:
            return "unknown"
        
        if "diarization" in output:
            return "diarization"
        elif "identification" in output:
            return "identify"
        elif "voiceprint" in output:
            return "voiceprint"
        else:
            return "unknown"
    
    def process_webhook_event(self, event: WebhookEvent) -> bool:
        """
        Обрабатывает событие веб-хука с rate limiting.

        Args:
            event: Событие веб-хука для обработки

        Returns:
            True если событие успешно обработано
        """
        operation_name = f"process_webhook_{event.job_type}"
        self.start_operation(operation_name)

        try:
            # Применяем rate limiting для webhook обработки
            self.wait_for_rate_limit("webhook_processing")

            self.log_with_emoji("info", "🎯", f"Обрабатываю {event.job_type} webhook: {event.job_id} (статус: {event.status})")

            # Сохраняем результат в файл
            if event.status == "succeeded" and event.output:
                self._save_webhook_result(event)
                self.successful_events += 1
            elif event.status == "canceled":
                self.log_with_emoji("warning", "⚠️", f"Задача {event.job_id} была отменена")
            else:
                self.log_with_emoji("error", "❌", f"Неизвестный статус задачи: {event.status}")

            # Вызываем пользовательские обработчики с retry логикой
            if event.job_type in self.event_handlers:
                def handler_operation():
                    return self.event_handlers[event.job_type](event)

                self.retry_operation(
                    operation=handler_operation,
                    operation_name=f"webhook_handler_{event.job_type}",
                    max_retries=3
                )

            self.processed_webhooks += 1
            self.end_operation(operation_name)
            return True

        except Exception as e:
            self.handle_error(e, f"Ошибка обработки webhook события {event.job_id}")
            self.end_operation(operation_name)
            return False
    
    def _save_webhook_result(self, event: WebhookEvent) -> Path:
        """
        Сохраняет результат веб-хука в файл.
        
        Args:
            event: Событие веб-хука с результатами
            
        Returns:
            Путь к сохраненному файлу
        """
        # Формируем имя файла
        timestamp = event.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{event.job_id}_{event.job_type}_{timestamp}.json"
        output_path = self.data_dir / filename
        
        # Подготавливаем данные для сохранения
        result_data = {
            "job_id": event.job_id,
            "job_type": event.job_type,
            "status": event.status,
            "timestamp": event.timestamp.isoformat(),
            "output": event.output,
            "retry_info": {
                "retry_num": event.retry_num,
                "retry_reason": event.retry_reason
            } if event.retry_num else None
        }
        
        # Сохраняем в JSON
        save_json(result_data, output_path)
        
        self.logger.info(f"💾 Результат сохранен: {output_path}")
        return output_path
    
    def register_event_handler(self, job_type: str, handler: Callable[[WebhookEvent], None]):
        """
        Регистрирует обработчик для определенного типа задач.
        
        Args:
            job_type: Тип задачи ('diarization', 'identify', 'voiceprint')
            handler: Функция-обработчик
        """
        self.event_handlers[job_type] = handler
        self.logger.info(f"📝 Зарегистрирован обработчик для {job_type}")
    
    def run(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """
        Основной метод выполнения WebhookAgent.

        Args:
            payload: JSON payload веб-хука
            headers: HTTP заголовки запроса

        Returns:
            True если webhook успешно обработан
        """
        try:
            # Верификация подписи
            timestamp = headers.get("x-request-timestamp", "")
            signature = headers.get("x-signature", "")
            body = json.dumps(payload, separators=(',', ':'))

            if not self.verify_signature(timestamp, body, signature):
                raise WebhookVerificationError("Неверная подпись webhook")

            # Парсинг события
            event = self.parse_webhook_payload(payload, headers)

            # Обработка события
            return self.process_webhook_event(event)

        except Exception as e:
            self.handle_error(e, "Ошибка обработки webhook")
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """
        Возвращает метрики работы агента.

        Returns:
            Словарь с метриками
        """
        return {
            "processed_webhooks": self.processed_webhooks,
            "failed_verifications": self.failed_verifications,
            "successful_events": self.successful_events,
            "verification_success_rate": (
                (self.processed_webhooks - self.failed_verifications) / max(self.processed_webhooks, 1)
            ) * 100
        }
