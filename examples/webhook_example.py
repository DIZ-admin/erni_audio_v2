#!/usr/bin/env python3
"""
Пример использования веб-хуков pyannote.ai для асинхронной обработки аудио

Этот пример демонстрирует:
1. Запуск webhook сервера
2. Асинхронную диаризацию с веб-хуками
3. Асинхронное создание voiceprints
4. Асинхронную идентификацию спикеров
"""

import os
import sys
import time
import asyncio
import logging
from pathlib import Path
from threading import Thread

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.webhook_server import WebhookServer
from pipeline.diarization_agent import DiarizationAgent
from pipeline.voiceprint_agent import VoiceprintAgent
from pipeline.identification_agent import IdentificationAgent


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def start_webhook_server_background():
    """Запускает webhook сервер в фоновом режиме"""
    try:
        # Настройка переменных окружения для примера
        os.environ["PYANNOTEAI_WEBHOOK_SECRET"] = "whs_example_secret_12345"
        os.environ["WEBHOOK_SERVER_PORT"] = "8000"
        
        logger.info("🚀 Запуск webhook сервера в фоновом режиме...")
        
        server = WebhookServer()
        
        # Регистрируем обработчики событий
        def handle_diarization(event):
            logger.info(f"🎤 Диаризация завершена: {event.job_id}")
            if event.status == "succeeded":
                segments = event.output.get("diarization", [])
                logger.info(f"✅ Найдено {len(segments)} сегментов диаризации")
                
                # Здесь можно добавить дополнительную обработку результатов
                for i, segment in enumerate(segments):
                    logger.info(f"  Сегмент {i+1}: {segment['start']:.1f}s - {segment['end']:.1f}s, спикер: {segment['speaker']}")
        
        def handle_voiceprint(event):
            logger.info(f"👤 Voiceprint создан: {event.job_id}")
            if event.status == "succeeded":
                voiceprint = event.output.get("voiceprint")
                if voiceprint:
                    logger.info(f"✅ Voiceprint готов (размер: {len(voiceprint)} символов)")
        
        def handle_identify(event):
            logger.info(f"🔍 Идентификация завершена: {event.job_id}")
            if event.status == "succeeded":
                identification = event.output.get("identification", [])
                logger.info(f"✅ Найдено {len(identification)} сегментов идентификации")
                
                # Показываем результаты идентификации
                for i, segment in enumerate(identification):
                    speaker = segment.get('speaker', 'Unknown')
                    confidence = segment.get('confidence', 0)
                    logger.info(f"  Сегмент {i+1}: {segment['start']:.1f}s - {segment['end']:.1f}s, спикер: {speaker} (уверенность: {confidence:.2f})")
        
        # Регистрируем обработчики
        server.register_event_handler("diarization", handle_diarization)
        server.register_event_handler("voiceprint", handle_voiceprint)
        server.register_event_handler("identify", handle_identify)
        
        # Запускаем сервер
        server.run(debug=False)
        
    except Exception as e:
        logger.error(f"❌ Ошибка webhook сервера: {e}")


async def example_async_diarization():
    """Пример асинхронной диаризации"""
    logger.info("=" * 60)
    logger.info("🎯 ПРИМЕР АСИНХРОННОЙ ДИАРИЗАЦИИ")
    logger.info("=" * 60)
    
    # Инициализируем агент с webhook URL
    agent = DiarizationAgent(
        api_key="your_pyannote_api_key",  # Замените на реальный ключ
        webhook_url="http://localhost:8000/webhook"
    )
    
    # Пример URL аудиофайла (замените на реальный)
    audio_url = "media://example-audio-file"
    
    try:
        # Запускаем асинхронную диаризацию
        job_id = agent.diarize_async(audio_url)
        logger.info(f"✅ Диаризация запущена асинхронно: {job_id}")
        logger.info("📡 Результат будет отправлен на webhook URL")
        
        return job_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска диаризации: {e}")
        return None


async def example_async_voiceprint():
    """Пример асинхронного создания voiceprint"""
    logger.info("=" * 60)
    logger.info("👤 ПРИМЕР АСИНХРОННОГО СОЗДАНИЯ VOICEPRINT")
    logger.info("=" * 60)
    
    # Инициализируем агент с webhook URL
    agent = VoiceprintAgent(
        api_key="your_pyannote_api_key",  # Замените на реальный ключ
        webhook_url="http://localhost:8000/webhook"
    )
    
    # Пример аудиофайла для voiceprint (замените на реальный)
    audio_file = Path("examples/speaker_sample.wav")
    
    try:
        if not audio_file.exists():
            logger.warning(f"⚠️ Файл {audio_file} не найден, создаем фиктивный файл для примера")
            audio_file.parent.mkdir(exist_ok=True)
            audio_file.write_bytes(b"fake audio content for example")
        
        # Запускаем асинхронное создание voiceprint
        job_id = agent.create_voiceprint_async(audio_file, "John Doe")
        logger.info(f"✅ Создание voiceprint запущено асинхронно: {job_id}")
        logger.info("📡 Результат будет отправлен на webhook URL")
        
        return job_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска создания voiceprint: {e}")
        return None


async def example_async_identification():
    """Пример асинхронной идентификации"""
    logger.info("=" * 60)
    logger.info("🔍 ПРИМЕР АСИНХРОННОЙ ИДЕНТИФИКАЦИИ")
    logger.info("=" * 60)
    
    # Инициализируем агент с webhook URL
    agent = IdentificationAgent(
        api_key="your_pyannote_api_key",  # Замените на реальный ключ
        webhook_url="http://localhost:8000/webhook"
    )
    
    # Пример voiceprints (замените на реальные)
    voiceprints = [
        {"label": "John Doe", "voiceprint": "base64_encoded_voiceprint_data_1"},
        {"label": "Jane Smith", "voiceprint": "base64_encoded_voiceprint_data_2"}
    ]
    
    # Пример аудиофайла (замените на реальный)
    audio_file = Path("examples/meeting.wav")
    
    try:
        if not audio_file.exists():
            logger.warning(f"⚠️ Файл {audio_file} не найден, создаем фиктивный файл для примера")
            audio_file.parent.mkdir(exist_ok=True)
            audio_file.write_bytes(b"fake meeting audio content for example")
        
        # Запускаем асинхронную идентификацию
        job_id = agent.run_async(
            audio_file=audio_file,
            voiceprints=voiceprints,
            matching_threshold=0.5
        )
        logger.info(f"✅ Идентификация запущена асинхронно: {job_id}")
        logger.info("📡 Результат будет отправлен на webhook URL")
        
        return job_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска идентификации: {e}")
        return None


async def main():
    """Основная функция примера"""
    logger.info("🌟 ПРИМЕР ИСПОЛЬЗОВАНИЯ ВЕБ-ХУКОВ PYANNOTE.AI")
    logger.info("=" * 60)
    
    # Запускаем webhook сервер в отдельном потоке
    webhook_thread = Thread(target=start_webhook_server_background, daemon=True)
    webhook_thread.start()
    
    # Ждем запуска сервера
    logger.info("⏳ Ожидание запуска webhook сервера...")
    await asyncio.sleep(3)
    
    # Проверяем, что сервер запущен
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Webhook сервер запущен и готов к работе")
        else:
            logger.error("❌ Webhook сервер не отвечает")
            return
    except Exception as e:
        logger.error(f"❌ Не удалось подключиться к webhook серверу: {e}")
        logger.info("💡 Убедитесь, что переменная PYANNOTEAI_WEBHOOK_SECRET настроена")
        return
    
    # Запускаем примеры асинхронной обработки
    job_ids = []
    
    # Пример 1: Асинхронная диаризация
    diarization_job = await example_async_diarization()
    if diarization_job:
        job_ids.append(("diarization", diarization_job))
    
    await asyncio.sleep(1)
    
    # Пример 2: Асинхронное создание voiceprint
    voiceprint_job = await example_async_voiceprint()
    if voiceprint_job:
        job_ids.append(("voiceprint", voiceprint_job))
    
    await asyncio.sleep(1)
    
    # Пример 3: Асинхронная идентификация
    identification_job = await example_async_identification()
    if identification_job:
        job_ids.append(("identification", identification_job))
    
    # Показываем запущенные задачи
    logger.info("=" * 60)
    logger.info("📋 ЗАПУЩЕННЫЕ АСИНХРОННЫЕ ЗАДАЧИ")
    logger.info("=" * 60)
    
    for job_type, job_id in job_ids:
        logger.info(f"🔄 {job_type.capitalize()}: {job_id}")
    
    logger.info("=" * 60)
    logger.info("⏳ Ожидание результатов...")
    logger.info("📡 Результаты будут обработаны webhook сервером автоматически")
    logger.info("💾 Результаты сохраняются в data/interim/")
    logger.info("🔧 Для остановки нажмите Ctrl+C")
    logger.info("=" * 60)
    
    # Ждем результатов (в реальном приложении здесь может быть другая логика)
    try:
        while True:
            await asyncio.sleep(10)
            logger.info("⏳ Ожидание webhook событий...")
    except KeyboardInterrupt:
        logger.info("\n👋 Пример завершен пользователем")


if __name__ == "__main__":
    # Создаем необходимые директории
    Path("data/interim").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    Path("examples").mkdir(exist_ok=True)
    
    # Запускаем пример
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Пример остановлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
