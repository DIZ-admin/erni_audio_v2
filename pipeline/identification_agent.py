"""
IdentificationAgent для диаризации с идентификацией спикеров через pyannote.ai API
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from .pyannote_media_agent import PyannoteMediaAgent


class IdentificationAgent:
    """
    Агент для диаризации с идентификацией спикеров через pyannote.ai Identification API.
    
    Выполняет диаризацию аудио и сопоставляет найденных спикеров с предоставленными
    голосовыми отпечатками (voiceprints).
    """
    
    def __init__(self, api_key: str):
        """
        Инициализация IdentificationAgent.
        
        Args:
            api_key: API ключ pyannote.ai
        """
        self.api_key = api_key
        self.base_url = "https://api.pyannote.ai/v1"
        self.logger = logging.getLogger(__name__)
        
        # Инициализируем медиа агент для загрузки файлов
        self.media_agent = PyannoteMediaAgent(api_key)
        
        self.logger.info("✅ IdentificationAgent инициализирован")
    
    def run(self,
            audio_file: Path,
            voiceprints: List[Dict],
            num_speakers: Optional[int] = None,
            confidence: bool = True,
            matching_threshold: float = 0.0,
            exclusive_matching: bool = True) -> List[Dict]:
        """
        Выполняет диаризацию с идентификацией спикеров.
        
        Args:
            audio_file: Путь к аудиофайлу или URL
            voiceprints: Список голосовых отпечатков в формате:
                        [{"label": "John Doe", "voiceprint": "base64_data"}, ...]
            num_speakers: Количество спикеров (None для автоопределения)
            confidence: Включить ли confidence scores
            matching_threshold: Порог сходства для сопоставления (0.0-1.0)
            exclusive_matching: Эксклюзивное сопоставление (один voiceprint = один спикер)
            
        Returns:
            Список сегментов с диаризацией и идентификацией:
            [{"start": float, "end": float, "speaker": str, "confidence": float}, ...]
        """
        start_time = time.time()
        
        try:
            if not voiceprints:
                raise ValueError("Список voiceprints не может быть пустым")
            
            # Валидация файла
            self._validate_audio_file(audio_file)
            
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.logger.info(f"🎵 Начинаю идентификацию: {audio_file.name} ({file_size_mb:.1f}MB)")
            self.logger.info(f"👥 Voiceprints: {len(voiceprints)} ({', '.join([vp['label'] for vp in voiceprints])})")
            
            # Загружаем файл в pyannote.ai временное хранилище
            self.logger.info("📤 Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.logger.info(f"✅ Файл загружен: {media_url}")
            
            # Создаем identification job
            job_id = self._submit_identification_job(
                media_url, voiceprints, num_speakers, confidence, 
                matching_threshold, exclusive_matching
            )
            self.logger.info(f"🚀 Identification job запущен: {job_id}")
            
            # Ждем завершения
            segments = self._wait_for_completion(job_id)
            
            # Логирование результатов
            duration = time.time() - start_time
            speakers = set(seg["speaker"] for seg in segments)
            self.logger.info(f"✅ Идентификация завершена: {len(segments)} сегментов за {duration:.2f}с")
            self.logger.info(f"👥 Обнаружено спикеров: {len(speakers)} ({', '.join(sorted(speakers))})")
            
            return segments
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка идентификации: {e}")
            raise RuntimeError(f"Ошибка идентификации: {e}") from e
    
    def _validate_audio_file(self, audio_file: Path) -> None:
        """Валидация аудиофайла для identification."""
        if not audio_file.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_file}")
        
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Проверяем размер файла (лимит pyannote.ai: 1GB)
        if file_size_mb > 1024:
            raise ValueError(f"Файл слишком большой: {file_size_mb:.1f}MB (максимум 1GB)")
        
        # Предупреждение о длительности (лимит pyannote.ai: 24 часа)
        if file_size_mb > 100:  # Примерно 50 минут для WAV
            self.logger.warning(f"⚠️ Большой файл: {file_size_mb:.1f}MB, обработка может занять много времени")
    
    def _submit_identification_job(self, 
                                  media_url: str,
                                  voiceprints: List[Dict],
                                  num_speakers: Optional[int],
                                  confidence: bool,
                                  matching_threshold: float,
                                  exclusive_matching: bool) -> str:
        """Отправляет задачу на идентификацию."""
        url = f"{self.base_url}/identify"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "url": media_url,
            "voiceprints": voiceprints,
            "matching": {
                "threshold": matching_threshold,
                "exclusive": exclusive_matching
            }
        }
        
        # Добавляем опциональные параметры
        if num_speakers is not None:
            data["numSpeakers"] = num_speakers
            self.logger.info(f"🎯 Установлено количество спикеров: {num_speakers}")
        
        if confidence:
            data["confidence"] = True
            self.logger.info("📊 Включены confidence scores")

        self.logger.debug(f"🔍 Отправляемые данные в API: {data}")

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
    
    def _wait_for_completion(self, job_id: str, max_wait_seconds: int = 1800) -> List[Dict]:
        """Ждет завершения identification job и возвращает сегменты."""
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
                    output = job_data.get("output", {})
                    self.logger.debug(f"🔍 Полный ответ API: {output}")

                    # Для identification API основные данные в поле "identification"
                    identification = output.get("identification", [])

                    if identification:
                        self.logger.info(f"✅ Найдена идентификация: {len(identification)} сегментов")
                        return self._process_identification_segments(identification)

                    # Fallback на обычную диаризацию если identification пуст
                    diarization = output.get("diarization", [])
                    if diarization:
                        self.logger.warning("⚠️ Identification пуст, используем обычную диаризацию")
                        return self._process_segments(diarization)

                    # Fallback на segments
                    segments = output.get("segments", [])
                    if segments:
                        self.logger.warning("⚠️ Используем segments как fallback")
                        return self._process_segments(segments)

                    self.logger.warning("⚠️ Identification job завершен, но данные не найдены")
                    self.logger.debug(f"🔍 Доступные поля в output: {list(output.keys())}")
                    return []
                
                elif status == "failed":
                    error_msg = job_data.get("output", {}).get("error", "Unknown error")
                    raise RuntimeError(f"Identification job failed: {error_msg}")
                
                elif status == "canceled":
                    raise RuntimeError("Identification job был отменен")
                
                elif status in ["created", "processing", "running"]:
                    # Продолжаем ждать
                    retry_count += 1
                    if retry_count <= 5:
                        self.logger.debug(f"Identification job {job_id} в статусе '{status}', ждем...")
                    elif retry_count % 10 == 0:
                        elapsed = time.time() - start_time
                        self.logger.info(f"⏳ Identification job {job_id} обрабатывается уже {elapsed:.1f}с...")

                    time.sleep(5)
                    continue
                
                else:
                    raise RuntimeError(f"Неизвестный статус identification job: {status}")
                    
            except requests.RequestException as e:
                self.logger.warning(f"⚠️ Ошибка сети при проверке identification job: {e}")
                time.sleep(10)
                continue
        
        raise RuntimeError(f"Превышено время ожидания identification job ({max_wait_seconds}с)")
    
    def _process_identification_segments(self, identification: List[Dict]) -> List[Dict]:
        """Обрабатывает identification сегменты из pyannote.ai."""
        processed_segments = []

        for segment in identification:
            # Identification API возвращает сегменты с полем "speaker" (уже идентифицированное имя)
            processed_segment = {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "speaker": segment.get("speaker", "UNKNOWN"),
                "confidence": 1.0,  # Для identification используем 1.0 как базовое значение
                "match": segment.get("match"),  # Сопоставленный voiceprint или None
                "diarization_speaker": segment.get("diarizationSpeaker", "UNKNOWN")  # Исходный спикер из диаризации
            }

            processed_segments.append(processed_segment)

        self.logger.info(f"📊 Обработано {len(processed_segments)} identification сегментов")
        return processed_segments

    def _process_segments(self, segments: List[Dict]) -> List[Dict]:
        """Обрабатывает сегменты из pyannote.ai в наш стандартный формат."""
        processed_segments = []

        for segment in segments:
            processed_segment = {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "speaker": segment.get("speaker", "UNKNOWN"),
                "confidence": segment.get("confidence", 0.0)
            }

            processed_segments.append(processed_segment)

        self.logger.info(f"📊 Обработано {len(processed_segments)} сегментов")
        return processed_segments
    
    def estimate_cost(self, audio_file: Path, num_voiceprints: int) -> Dict[str, any]:
        """
        Оценка стоимости идентификации.
        
        Args:
            audio_file: Путь к аудиофайлу
            num_voiceprints: Количество voiceprints для сопоставления
            
        Returns:
            Словарь с оценкой стоимости
        """
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Стоимость identification в pyannote.ai (примерная)
        # Обычно зависит от длительности аудио и количества voiceprints
        base_cost = 0.05  # Базовая стоимость
        size_cost = file_size_mb * 0.01  # За размер файла
        voiceprint_cost = num_voiceprints * 0.005  # За каждый voiceprint
        
        estimated_cost = base_cost + size_cost + voiceprint_cost
        
        return {
            "estimated_cost_usd": round(estimated_cost, 4),
            "file_size_mb": round(file_size_mb, 1),
            "num_voiceprints": num_voiceprints,
            "note": "Приблизительная оценка, реальная стоимость может отличаться"
        }
