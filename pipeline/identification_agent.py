"""
IdentificationAgent для диаризации с идентификацией спикеров через pyannote.ai API
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from .pyannote_media_agent import PyannoteMediaAgent
from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin


class IdentificationAgent(BaseAgent, ValidationMixin):
    """
    Агент для диаризации с идентификацией спикеров через pyannote.ai Identification API.

    Выполняет диаризацию аудио и сопоставляет найденных спикеров с предоставленными
    голосовыми отпечатками (voiceprints).
    """

    def __init__(self, api_key: str, webhook_url: Optional[str] = None):
        """
        Инициализация IdentificationAgent.

        Args:
            api_key: API ключ pyannote.ai
            webhook_url: URL для получения веб-хуков (опционально)
        """
        # Инициализация базовых классов
        BaseAgent.__init__(self, name="IdentificationAgent")
        ValidationMixin.__init__(self)

        # Валидация API ключа
        self.validate_api_key(api_key)

        self.api_key = api_key
        self.webhook_url = webhook_url
        self.base_url = "https://api.pyannote.ai/v1"

        # Инициализируем медиа агент для загрузки файлов
        self.media_agent = PyannoteMediaAgent(api_key)

        self.log_with_emoji("info", "✅", "IdentificationAgent инициализирован")

    def validate_api_key(self, api_key: str) -> None:
        """
        Валидация API ключа pyannote.ai.

        Args:
            api_key: API ключ для валидации

        Raises:
            ValueError: Если API ключ невалиден
        """
        if not isinstance(api_key, str):
            raise ValueError(f"API ключ должен быть строкой, получен {type(api_key)}")

        if not api_key or not api_key.strip():
            raise ValueError("API ключ не может быть пустым")

        # Проверяем базовый формат (должен быть достаточно длинным)
        if len(api_key.strip()) < 10:
            raise ValueError("API ключ слишком короткий")

    def validate_voiceprints(self, voiceprints: List[Dict]) -> List[str]:
        """
        Валидация списка voiceprints для identification.

        Args:
            voiceprints: Список voiceprints для валидации

        Returns:
            Список найденных проблем
        """
        issues = []

        if not isinstance(voiceprints, list):
            issues.append("Voiceprints должны быть списком")
            return issues

        if not voiceprints:
            issues.append("Список voiceprints не может быть пустым")
            return issues

        for i, vp in enumerate(voiceprints):
            if not isinstance(vp, dict):
                issues.append(f"Voiceprint {i}: должен быть словарем")
                continue

            # Проверяем обязательные поля
            if "label" not in vp:
                issues.append(f"Voiceprint {i}: отсутствует поле 'label'")
            elif not isinstance(vp["label"], str) or not vp["label"].strip():
                issues.append(f"Voiceprint {i}: 'label' должно быть непустой строкой")

            if "voiceprint" not in vp:
                issues.append(f"Voiceprint {i}: отсутствует поле 'voiceprint'")
            elif not isinstance(vp["voiceprint"], str) or not vp["voiceprint"].strip():
                issues.append(f"Voiceprint {i}: 'voiceprint' должно быть непустой строкой")

        return issues

    def validate_identification_params(self,
                                     audio_file: Path,
                                     voiceprints: List[Dict],
                                     num_speakers: Optional[int] = None,
                                     matching_threshold: float = 0.0) -> List[str]:
        """
        Валидация параметров для identification.

        Args:
            audio_file: Путь к аудиофайлу
            voiceprints: Список voiceprints
            num_speakers: Количество спикеров
            matching_threshold: Порог сходства

        Returns:
            Список найденных проблем
        """
        issues = []

        # Валидация файла
        try:
            self.validate_audio_file(audio_file)
        except ValueError as e:
            issues.append(f"Проблема с аудиофайлом: {e}")

        # Валидация voiceprints
        vp_issues = self.validate_voiceprints(voiceprints)
        issues.extend(vp_issues)

        # Валидация num_speakers
        if num_speakers is not None:
            if not isinstance(num_speakers, int):
                issues.append("num_speakers должно быть целым числом")
            elif num_speakers < 1:
                issues.append("num_speakers должно быть больше 0")
            elif num_speakers > 50:
                issues.append("num_speakers слишком большое (максимум 50)")

        # Валидация matching_threshold
        if not isinstance(matching_threshold, (int, float)):
            issues.append("matching_threshold должно быть числом")
        elif not (0.0 <= matching_threshold <= 1.0):
            issues.append("matching_threshold должно быть в диапазоне 0.0-1.0")

        return issues

    def validate_identification_audio_file(self, audio_file: Path) -> List[str]:
        """
        Специальная валидация аудиофайла для identification.

        Args:
            audio_file: Путь к аудиофайлу

        Returns:
            Список найденных проблем
        """
        issues = []

        # Базовая валидация файла
        try:
            self.validate_audio_file(audio_file)
        except ValueError as e:
            issues.append(str(e))
            return issues  # Если базовая валидация не прошла, дальше не проверяем

        # Проверка размера файла (≤1GB для identification)
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        if file_size_mb > 1024:
            issues.append(f"Файл слишком большой: {file_size_mb:.1f}MB (максимум 1GB)")
        elif file_size_mb > 100:
            issues.append(f"Большой файл: {file_size_mb:.1f}MB, обработка может занять много времени")

        return issues

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
        self.start_operation("идентификация спикеров")

        try:
            # Валидация параметров
            param_issues = self.validate_identification_params(
                audio_file, voiceprints, num_speakers, matching_threshold
            )
            if param_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с параметрами: {len(param_issues)}")
                for issue in param_issues[:3]:  # Показываем первые 3
                    self.log_with_emoji("warning", "   ", issue)

                # Если есть критические проблемы, прерываем
                if any("не может быть пустым" in issue or "не найден" in issue for issue in param_issues):
                    raise ValueError(f"Критические проблемы с параметрами: {param_issues[0]}")

            # Валидация аудиофайла для identification
            audio_issues = self.validate_identification_audio_file(audio_file)
            if audio_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с аудиофайлом: {len(audio_issues)}")
                for issue in audio_issues[:3]:
                    self.log_with_emoji("warning", "   ", issue)

            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.log_with_emoji("info", "🎵", f"Начинаю идентификацию: {audio_file.name} ({file_size_mb:.1f}MB)")
            self.log_with_emoji("info", "👥", f"Voiceprints: {len(voiceprints)} ({', '.join([vp['label'] for vp in voiceprints])})")

            # Загружаем файл в pyannote.ai временное хранилище
            self.log_with_emoji("info", "📤", "Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.log_with_emoji("info", "✅", f"Файл загружен: {media_url}")

            # Создаем identification job
            job_id = self._submit_identification_job(
                media_url, voiceprints, num_speakers, confidence,
                matching_threshold, exclusive_matching
            )
            self.log_with_emoji("info", "🚀", f"Identification job запущен: {job_id}")

            # Ждем завершения
            segments = self._wait_for_completion(job_id)

            # Логирование результатов
            speakers = set(seg["speaker"] for seg in segments)
            self.log_with_emoji("info", "✅", f"Идентификация завершена: {len(segments)} сегментов")
            self.log_with_emoji("info", "👥", f"Обнаружено спикеров: {len(speakers)} ({', '.join(sorted(speakers))})")

            self.end_operation("идентификация спикеров", success=True)
            return segments

        except Exception as e:
            self.end_operation("идентификация спикеров", success=False)
            self.handle_error(e, "идентификация спикеров", reraise=True)
    
    # Метод _validate_audio_file удален - используется validate_identification_audio_file
    
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
            self.log_with_emoji("info", "🎯", f"Установлено количество спикеров: {num_speakers}")

        if confidence:
            data["confidence"] = True
            self.log_with_emoji("info", "📊", "Включены confidence scores")

        if self.webhook_url:
            data["webhook"] = self.webhook_url
            self.log_with_emoji("info", "🔗", f"Webhook URL добавлен для identification: {self.webhook_url}")

        self.log_with_emoji("debug", "🔍", f"Отправляемые данные в API: {data}")

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
                    self.log_with_emoji("debug", "🔍", f"Полный ответ API: {output}")

                    # Для identification API основные данные в поле "identification"
                    identification = output.get("identification", [])

                    if identification:
                        self.log_with_emoji("info", "✅", f"Найдена идентификация: {len(identification)} сегментов")
                        return self._process_identification_segments(identification)

                    # Fallback на обычную диаризацию если identification пуст
                    diarization = output.get("diarization", [])
                    if diarization:
                        self.log_with_emoji("warning", "⚠️", "Identification пуст, используем обычную диаризацию")
                        return self._process_segments(diarization)

                    # Fallback на segments
                    segments = output.get("segments", [])
                    if segments:
                        self.log_with_emoji("warning", "⚠️", "Используем segments как fallback")
                        return self._process_segments(segments)

                    self.log_with_emoji("warning", "⚠️", "Identification job завершен, но данные не найдены")
                    self.log_with_emoji("debug", "🔍", f"Доступные поля в output: {list(output.keys())}")
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
                        self.log_with_emoji("debug", "⏳", f"Identification job {job_id} в статусе '{status}', ждем...")
                    elif retry_count % 10 == 0:
                        elapsed = time.time() - start_time
                        self.log_with_emoji("info", "⏳", f"Identification job {job_id} обрабатывается уже {elapsed:.1f}с...")

                    time.sleep(5)
                    continue
                
                else:
                    raise RuntimeError(f"Неизвестный статус identification job: {status}")
                    
            except requests.RequestException as e:
                self.log_with_emoji("warning", "⚠️", f"Ошибка сети при проверке identification job: {e}")
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

        self.log_with_emoji("info", "📊", f"Обработано {len(processed_segments)} identification сегментов")
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

        self.log_with_emoji("info", "📊", f"Обработано {len(processed_segments)} сегментов")
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

    def run_async(self,
                  audio_file: Path,
                  voiceprints: List[Dict],
                  num_speakers: Optional[int] = None,
                  confidence: bool = True,
                  matching_threshold: float = 0.0,
                  exclusive_matching: bool = True) -> str:
        """
        Выполняет идентификацию спикеров асинхронно с веб-хуком.

        Args:
            audio_file: Путь к аудиофайлу или URL
            voiceprints: Список голосовых отпечатков в формате:
                        [{"label": "John Doe", "voiceprint": "base64_data"}, ...]
            num_speakers: Количество спикеров (None для автоопределения)
            confidence: Включить ли confidence scores
            matching_threshold: Порог сходства для сопоставления (0.0-1.0)
            exclusive_matching: Эксклюзивное сопоставление (один voiceprint = один спикер)

        Returns:
            job_id для отслеживания статуса

        Raises:
            ValueError: Если webhook_url не настроен
        """
        self.start_operation("идентификация спикеров (async)")

        try:
            if not self.webhook_url:
                raise ValueError("webhook_url должен быть настроен для асинхронной обработки")

            # Валидация параметров
            param_issues = self.validate_identification_params(
                audio_file, voiceprints, num_speakers, matching_threshold
            )
            if param_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с параметрами: {len(param_issues)}")
                for issue in param_issues[:3]:
                    self.log_with_emoji("warning", "   ", issue)

            self.log_with_emoji("info", "🚀", f"Запускаю асинхронную идентификацию для: {audio_file}")
            self.log_with_emoji("info", "👥", f"Voiceprints: {len(voiceprints)}, порог: {matching_threshold}")

            # Загружаем файл в pyannote.ai временное хранилище
            self.log_with_emoji("info", "📤", "Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.log_with_emoji("info", "✅", f"Файл загружен: {media_url}")

            # Запускаем identification job с webhook
            job_id = self._submit_identification_job(
                media_url=media_url,
                voiceprints=voiceprints,
                num_speakers=num_speakers,
                confidence=confidence,
                matching_threshold=matching_threshold,
                exclusive_matching=exclusive_matching
            )

            self.log_with_emoji("info", "✅", f"Асинхронная идентификация запущена: {job_id}")
            self.log_with_emoji("info", "📡", f"Результат будет отправлен на: {self.webhook_url}")

            self.end_operation("идентификация спикеров (async)", success=True)
            return job_id

        except Exception as e:
            self.end_operation("идентификация спикеров (async)", success=False)
            self.handle_error(e, "запуск асинхронной идентификации", reraise=True)
