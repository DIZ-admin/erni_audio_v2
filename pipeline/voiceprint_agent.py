"""
VoiceprintAgent для создания голосовых отпечатков через pyannote.ai API
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional
import requests
from .pyannote_media_agent import PyannoteMediaAgent


class VoiceprintAgent:
    """
    Агент для создания голосовых отпечатков через pyannote.ai Voiceprint API.
    
    Создает уникальные голосовые отпечатки из аудиофайлов (≤30 секунд),
    которые затем можно использовать для идентификации спикеров.
    """
    
    def __init__(self, api_key: str, webhook_url: Optional[str] = None):
        """
        Инициализация VoiceprintAgent.

        Args:
            api_key: API ключ pyannote.ai
            webhook_url: URL для получения веб-хуков (опционально)
        """
        self.api_key = api_key
        self.webhook_url = webhook_url
        self.base_url = "https://api.pyannote.ai/v1"
        self.logger = logging.getLogger(__name__)

        # Инициализируем медиа агент для загрузки файлов
        self.media_agent = PyannoteMediaAgent(api_key)

        self.logger.info("✅ VoiceprintAgent инициализирован")
    
    def create_voiceprint(self, 
                         audio_file: Path, 
                         label: str,
                         max_duration_check: bool = True) -> Dict:
        """
        Создает голосовой отпечаток из аудиофайла.
        
        Args:
            audio_file: Путь к аудиофайлу (должен содержать только 1 спикера, ≤30с)
            label: Человекочитаемое имя для голосового отпечатка
            max_duration_check: Проверять ли длительность файла (по умолчанию True)
            
        Returns:
            Словарь с информацией о голосовом отпечатке:
            {
                "label": str,
                "voiceprint": str (base64),
                "created_at": str,
                "source_file": str,
                "duration": float
            }
        """
        start_time = time.time()
        
        try:
            # Валидация файла
            self._validate_audio_file(audio_file, max_duration_check)
            
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.logger.info(f"🎵 Создаю voiceprint для '{label}': {audio_file.name} ({file_size_mb:.1f}MB)")
            
            # Загружаем файл в pyannote.ai временное хранилище
            self.logger.info("📤 Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.logger.info(f"✅ Файл загружен: {media_url}")
            
            # Создаем voiceprint job
            job_id = self._submit_voiceprint_job(media_url)
            self.logger.info(f"🚀 Voiceprint job запущен: {job_id}")
            
            # Ждем завершения
            voiceprint_data = self._wait_for_completion(job_id)
            
            # Формируем результат
            result = {
                "label": label,
                "voiceprint": voiceprint_data,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source_file": str(audio_file),
                "duration": time.time() - start_time,
                "file_size_mb": file_size_mb
            }
            
            duration = time.time() - start_time
            self.logger.info(f"✅ Voiceprint создан для '{label}' за {duration:.2f}с")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка создания voiceprint для '{label}': {e}")
            raise RuntimeError(f"Ошибка создания voiceprint: {e}") from e
    
    def _validate_audio_file(self, audio_file: Path, check_duration: bool = True) -> None:
        """Валидация аудиофайла для voiceprint."""
        if not audio_file.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_file}")
        
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Проверяем размер файла (лимит pyannote.ai: 100MB)
        if file_size_mb > 100:
            raise ValueError(f"Файл слишком большой: {file_size_mb:.1f}MB (максимум 100MB)")
        
        # Предупреждение о длительности (лимит pyannote.ai: 30 секунд)
        if check_duration:
            try:
                # Примерная оценка длительности по размеру файла
                # Для WAV 16kHz mono: ~1MB ≈ 30 секунд
                estimated_duration = file_size_mb * 30
                if estimated_duration > 30:
                    self.logger.warning(f"⚠️ Файл может быть длиннее 30 секунд (~{estimated_duration:.1f}с)")
                    self.logger.warning("⚠️ pyannote.ai принимает файлы до 30 секунд для voiceprint")
            except:
                pass  # Игнорируем ошибки оценки длительности
    
    def _submit_voiceprint_job(self, media_url: str) -> str:
        """Отправляет задачу на создание voiceprint."""
        url = f"{self.base_url}/voiceprint"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "url": media_url
        }

        if self.webhook_url:
            data["webhook"] = self.webhook_url
            self.logger.info(f"🔗 Webhook URL добавлен для voiceprint: {self.webhook_url}")
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json().get("detail", "Unknown error")
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text}"
            raise RuntimeError(f"Ошибка pyannote.ai API: {error_msg}")
        
        result = response.json()
        return result["jobId"]
    
    def _wait_for_completion(self, job_id: str, max_wait_seconds: int = 300) -> str:
        """Ждет завершения voiceprint job и возвращает base64 voiceprint."""
        url = f"{self.base_url}/jobs/{job_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        start_time = time.time()
        retry_count = 0
        
        while time.time() - start_time < max_wait_seconds:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    raise RuntimeError(f"Ошибка получения статуса job: HTTP {response.status_code}")
                
                job_data = response.json()
                status = job_data.get("status")
                
                if status == "succeeded":
                    voiceprint = job_data.get("output", {}).get("voiceprint")
                    if not voiceprint:
                        raise RuntimeError("Voiceprint не найден в ответе API")
                    return voiceprint
                
                elif status == "failed":
                    error_msg = job_data.get("output", {}).get("error", "Unknown error")
                    raise RuntimeError(f"Voiceprint job failed: {error_msg}")
                
                elif status == "canceled":
                    raise RuntimeError("Voiceprint job был отменен")
                
                elif status in ["created", "processing", "running"]:
                    # Продолжаем ждать
                    retry_count += 1
                    if retry_count <= 5:
                        self.logger.debug(f"Voiceprint job {job_id} в статусе '{status}', ждем...")
                    elif retry_count % 10 == 0:
                        elapsed = time.time() - start_time
                        self.logger.info(f"⏳ Voiceprint job {job_id} обрабатывается уже {elapsed:.1f}с...")

                    time.sleep(2)
                    continue
                
                else:
                    raise RuntimeError(f"Неизвестный статус voiceprint job: {status}")
                    
            except requests.RequestException as e:
                self.logger.warning(f"⚠️ Ошибка сети при проверке voiceprint job: {e}")
                time.sleep(5)
                continue
        
        raise RuntimeError(f"Превышено время ожидания voiceprint job ({max_wait_seconds}с)")
    
    def estimate_cost(self, audio_file: Path) -> Dict[str, any]:
        """
        Оценка стоимости создания voiceprint.
        
        Args:
            audio_file: Путь к аудиофайлу
            
        Returns:
            Словарь с оценкой стоимости
        """
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Стоимость voiceprint в pyannote.ai (примерная)
        # Обычно это фиксированная стоимость за voiceprint
        estimated_cost = 0.01  # Примерно $0.01 за voiceprint
        
        return {
            "estimated_cost_usd": estimated_cost,
            "file_size_mb": round(file_size_mb, 1),
            "note": "Приблизительная оценка, реальная стоимость может отличаться"
        }

    def create_voiceprint_async(self, audio_file: Path, label: str) -> str:
        """
        Создает голосовой отпечаток асинхронно с веб-хуком.

        Args:
            audio_file: Путь к аудиофайлу (должен содержать только 1 спикера, ≤30с)
            label: Человекочитаемое имя для голосового отпечатка

        Returns:
            job_id для отслеживания статуса

        Raises:
            ValueError: Если webhook_url не настроен
        """
        if not self.webhook_url:
            raise ValueError("webhook_url должен быть настроен для асинхронной обработки")

        try:
            # Валидация файла
            self._validate_audio_file(audio_file, max_duration_check=True)

            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.logger.info(f"🚀 Запускаю асинхронное создание voiceprint для '{label}': {audio_file.name} ({file_size_mb:.1f}MB)")

            # Загружаем файл в pyannote.ai временное хранилище
            self.logger.info("📤 Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.logger.info(f"✅ Файл загружен: {media_url}")

            # Создаем voiceprint job с webhook
            job_id = self._submit_voiceprint_job(media_url)
            self.logger.info(f"✅ Асинхронный voiceprint job запущен: {job_id}")
            self.logger.info(f"📡 Результат будет отправлен на: {self.webhook_url}")

            return job_id

        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска асинхронного создания voiceprint: {e}")
            raise
