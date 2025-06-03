#!/usr/bin/env python3
"""
CLI для запуска webhook сервера pyannote.ai

Этот скрипт запускает HTTP сервер для приема веб-хуков от pyannote.ai
с автоматической верификацией подписи и обработкой событий.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.webhook_server import WebhookServer


def setup_logging(debug: bool = False):
    """Настройка логирования"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/webhook_server.log')
        ]
    )


def create_event_handlers():
    """Создает обработчики событий для различных типов задач"""
    
    def handle_diarization(event):
        """Обработчик завершения диаризации"""
        logger = logging.getLogger(__name__)
        logger.info(f"🎤 Диаризация завершена: {event.job_id}")
        logger.info(f"📊 Статус: {event.status}")
        
        if event.output and event.status == "succeeded":
            diarization = event.output.get("diarization", [])
            logger.info(f"✅ Найдено {len(diarization)} сегментов диаризации")
    
    def handle_voiceprint(event):
        """Обработчик завершения создания voiceprint"""
        logger = logging.getLogger(__name__)
        logger.info(f"👤 Voiceprint создан: {event.job_id}")
        logger.info(f"📊 Статус: {event.status}")
        
        if event.output and event.status == "succeeded":
            voiceprint = event.output.get("voiceprint")
            if voiceprint:
                logger.info(f"✅ Voiceprint готов (размер: {len(voiceprint)} символов)")
    
    def handle_identify(event):
        """Обработчик завершения идентификации"""
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Идентификация завершена: {event.job_id}")
        logger.info(f"📊 Статус: {event.status}")
        
        if event.output and event.status == "succeeded":
            identification = event.output.get("identification", [])
            logger.info(f"✅ Найдено {len(identification)} сегментов идентификации")
    
    return {
        "diarization": handle_diarization,
        "voiceprint": handle_voiceprint,
        "identify": handle_identify
    }


def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Webhook сервер для pyannote.ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Запуск с настройками по умолчанию
  python webhook_server_cli.py

  # Запуск в режиме отладки
  python webhook_server_cli.py --debug

  # Запуск на определенном порту
  python webhook_server_cli.py --port 9000

  # Запуск с кастомным webhook секретом
  python webhook_server_cli.py --webhook-secret "whs_your_secret_here"

Переменные окружения:
  PYANNOTEAI_WEBHOOK_SECRET - секрет для верификации веб-хуков
  WEBHOOK_SERVER_PORT       - порт сервера (по умолчанию 8000)
  WEBHOOK_SERVER_HOST       - хост сервера (по умолчанию 0.0.0.0)
        """
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="Порт для webhook сервера (по умолчанию из env или 8000)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Хост для webhook сервера (по умолчанию из env или 0.0.0.0)"
    )
    
    parser.add_argument(
        "--webhook-secret",
        type=str,
        default=None,
        help="Секрет для верификации веб-хуков (по умолчанию из env)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/interim"),
        help="Директория для сохранения результатов (по умолчанию data/interim)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Включить режим отладки"
    )
    
    parser.add_argument(
        "--no-handlers",
        action="store_true",
        help="Не регистрировать обработчики событий по умолчанию"
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        # Создаем директории
        args.data_dir.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        # Переопределяем переменные окружения если указаны аргументы
        if args.port:
            os.environ["WEBHOOK_SERVER_PORT"] = str(args.port)
        if args.host:
            os.environ["WEBHOOK_SERVER_HOST"] = args.host
        if args.webhook_secret:
            os.environ["PYANNOTEAI_WEBHOOK_SECRET"] = args.webhook_secret
        
        # Создаем webhook сервер
        logger.info("🚀 Инициализация webhook сервера...")
        server = WebhookServer(
            webhook_secret=args.webhook_secret,
            data_dir=args.data_dir
        )
        
        # Регистрируем обработчики событий
        if not args.no_handlers:
            logger.info("📝 Регистрация обработчиков событий...")
            handlers = create_event_handlers()
            for job_type, handler in handlers.items():
                server.register_event_handler(job_type, handler)
        
        # Выводим информацию о сервере
        host = os.getenv("WEBHOOK_SERVER_HOST", "0.0.0.0")
        port = int(os.getenv("WEBHOOK_SERVER_PORT", "8000"))
        
        logger.info("=" * 60)
        logger.info("🌐 WEBHOOK СЕРВЕР PYANNOTE.AI")
        logger.info("=" * 60)
        logger.info(f"📡 Webhook endpoint: http://{host}:{port}/webhook")
        logger.info(f"🏥 Health check:     http://{host}:{port}/health")
        logger.info(f"📊 Metrics:          http://{host}:{port}/metrics")
        logger.info(f"💾 Результаты:       {args.data_dir.absolute()}")
        logger.info("=" * 60)
        logger.info("🔧 Для остановки нажмите Ctrl+C")
        logger.info("=" * 60)
        
        # Запускаем сервер
        server.run(debug=args.debug)
        
    except KeyboardInterrupt:
        logger.info("\n👋 Webhook сервер остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
