"""
Webhook HTTP сервер для приема веб-хуков pyannote.ai

FastAPI сервер для обработки HTTP POST запросов от pyannote.ai
с автоматической верификацией подписи и обработкой событий.
"""

import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any
import uvicorn
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .webhook_agent import WebhookAgent, WebhookVerificationError


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebhookServer:
    """
    HTTP сервер для обработки веб-хуков pyannote.ai.
    
    Функции:
    - Прием POST запросов на /webhook
    - Автоматическая верификация подписи
    - Асинхронная обработка событий
    - Метрики и мониторинг
    - Health checks
    """
    
    def __init__(self, webhook_secret: str = None, data_dir: Path = None):
        """
        Инициализация webhook сервера.
        
        Args:
            webhook_secret: Секрет для верификации (из env если не указан)
            data_dir: Директория для сохранения результатов
        """
        self.webhook_secret = webhook_secret or os.getenv("PYANNOTEAI_WEBHOOK_SECRET")
        if not self.webhook_secret:
            raise ValueError("PYANNOTEAI_WEBHOOK_SECRET не найден в переменных окружения")
        
        self.data_dir = data_dir or Path("data/interim")
        self.host = os.getenv("WEBHOOK_SERVER_HOST", "0.0.0.0")
        self.port = int(os.getenv("WEBHOOK_SERVER_PORT", "8000"))
        
        # Инициализируем webhook агент
        self.webhook_agent = WebhookAgent(self.webhook_secret, self.data_dir)
        
        # Создаем FastAPI приложение
        self.app = FastAPI(
            title="Pyannote.ai Webhook Server",
            description="Сервер для обработки веб-хуков pyannote.ai",
            version="1.0.0"
        )
        
        # Настраиваем middleware
        self._setup_middleware()
        
        # Регистрируем маршруты
        self._setup_routes()
        
        logger.info(f"✅ WebhookServer инициализирован на {self.host}:{self.port}")
    
    def _setup_middleware(self):
        """Настройка middleware для CORS и логирования"""
        
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # В production ограничить до pyannote.ai
            allow_credentials=True,
            allow_methods=["POST", "GET"],
            allow_headers=["*"],
        )
        
        # Middleware для логирования запросов
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            
            # Логируем входящий запрос
            logger.info(f"📥 {request.method} {request.url.path} от {request.client.host}")
            
            response = await call_next(request)
            
            # Логируем время обработки
            process_time = time.time() - start_time
            logger.info(f"⏱️ Обработано за {process_time:.3f}s, статус: {response.status_code}")
            
            return response
    
    def _setup_routes(self):
        """Регистрация маршрутов API"""
        
        @self.app.post("/webhook")
        async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
            """
            Основной эндпоинт для приема веб-хуков pyannote.ai.
            
            Ожидает POST запрос с JSON payload и заголовками:
            - X-Request-Timestamp: временная метка
            - X-Signature: подпись HMAC-SHA256
            """
            try:
                # Получаем заголовки
                headers = dict(request.headers)
                timestamp = headers.get("x-request-timestamp")
                signature = headers.get("x-signature")
                
                if not timestamp or not signature:
                    logger.warning("❌ Отсутствуют обязательные заголовки")
                    raise HTTPException(
                        status_code=400, 
                        detail="Отсутствуют заголовки X-Request-Timestamp или X-Signature"
                    )
                
                # Получаем сырое тело запроса
                body = await request.body()
                body_str = body.decode('utf-8')
                
                # Верифицируем подпись
                if not self.webhook_agent.verify_signature(timestamp, body_str, signature):
                    logger.warning(f"❌ Неверная подпись веб-хука от {request.client.host}")
                    raise HTTPException(status_code=403, detail="Неверная подпись")
                
                # Парсим JSON payload
                try:
                    payload = json.loads(body_str)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON: {e}")
                    raise HTTPException(status_code=400, detail="Неверный JSON")
                
                # Создаем событие веб-хука
                event = self.webhook_agent.parse_webhook_payload(payload, headers)
                
                # Обрабатываем событие в фоне
                background_tasks.add_task(self._process_event_background, event)
                
                logger.info(f"✅ Webhook принят: {event.job_id} ({event.job_type})")
                
                return JSONResponse(
                    status_code=200,
                    content={"status": "success", "message": "Webhook обработан"}
                )
                
            except HTTPException:
                raise
            except WebhookVerificationError as e:
                logger.error(f"❌ Ошибка верификации: {e}")
                raise HTTPException(status_code=403, detail=str(e))
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка: {e}")
                raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
        
        @self.app.get("/health")
        async def health_check():
            """Health check эндпоинт"""
            metrics = self.webhook_agent.get_metrics()
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "service": "pyannote-webhook-server",
                    "metrics": metrics
                }
            )
        
        @self.app.get("/metrics")
        async def get_metrics():
            """Эндпоинт для получения метрик"""
            metrics = self.webhook_agent.get_metrics()
            return JSONResponse(status_code=200, content=metrics)
        
        @self.app.get("/")
        async def root():
            """Корневой эндпоинт"""
            return JSONResponse(
                status_code=200,
                content={
                    "service": "Pyannote.ai Webhook Server",
                    "version": "1.0.0",
                    "endpoints": {
                        "webhook": "/webhook (POST)",
                        "health": "/health (GET)",
                        "metrics": "/metrics (GET)"
                    }
                }
            )
    
    async def _process_event_background(self, event):
        """
        Обрабатывает событие веб-хука в фоновом режиме.
        
        Args:
            event: WebhookEvent для обработки
        """
        try:
            success = self.webhook_agent.process_webhook_event(event)
            if success:
                logger.info(f"✅ Событие {event.job_id} успешно обработано")
            else:
                logger.error(f"❌ Ошибка обработки события {event.job_id}")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка обработки события {event.job_id}: {e}")
    
    def run(self, debug: bool = False):
        """
        Запускает webhook сервер.
        
        Args:
            debug: Режим отладки
        """
        logger.info(f"🚀 Запуск webhook сервера на http://{self.host}:{self.port}")
        logger.info(f"📡 Webhook endpoint: http://{self.host}:{self.port}/webhook")
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if not debug else "debug",
            access_log=True
        )
    
    def register_event_handler(self, job_type: str, handler):
        """
        Регистрирует пользовательский обработчик событий.
        
        Args:
            job_type: Тип задачи ('diarization', 'identify', 'voiceprint')
            handler: Функция-обработчик
        """
        self.webhook_agent.register_event_handler(job_type, handler)


def create_webhook_server() -> WebhookServer:
    """
    Фабричная функция для создания webhook сервера.
    
    Returns:
        Настроенный WebhookServer
    """
    return WebhookServer()


if __name__ == "__main__":
    import time
    import json
    
    # Запуск сервера для разработки
    server = create_webhook_server()
    
    # Пример регистрации обработчиков
    def handle_diarization(event):
        logger.info(f"🎤 Диаризация завершена: {event.job_id}")
    
    def handle_voiceprint(event):
        logger.info(f"👤 Voiceprint создан: {event.job_id}")
    
    server.register_event_handler("diarization", handle_diarization)
    server.register_event_handler("voiceprint", handle_voiceprint)
    
    # Запускаем сервер
    server.run(debug=True)
