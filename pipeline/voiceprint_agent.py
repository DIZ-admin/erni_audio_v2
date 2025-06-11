"""
VoiceprintAgent для создания голосовых отпечатков через pyannote.ai API
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
import requests
from .pyannote_media_agent import PyannoteMediaAgent
from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin
from .retry_mixin import RetryMixin
from .rate_limit_mixin import RateLimitMixin


class VoiceprintAgent(BaseAgent, ValidationMixin, RetryMixin, RateLimitMixin):
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
        # Инициализация базовых классов
        BaseAgent.__init__(self, name="VoiceprintAgent")
        ValidationMixin.__init__(self)
        RetryMixin.__init__(self)
        RateLimitMixin.__init__(self, service_name="pyannote")

        # Валидация API ключа
        self.validate_api_key(api_key)

        self.api_key = api_key
        self.webhook_url = webhook_url
        from .settings import SETTINGS
        self.base_url = SETTINGS.api.pyannote_url

        # Инициализируем медиа агент для загрузки файлов
        self.media_agent = PyannoteMediaAgent(api_key)

        self.log_with_emoji("info", "✅", "VoiceprintAgent инициализирован")

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

    def validate_voiceprint_params(self, audio_file: Path, label: str) -> List[str]:
        """
        Валидация параметров для создания voiceprint.

        Args:
            audio_file: Путь к аудиофайлу
            label: Метка для voiceprint

        Returns:
            Список найденных проблем
        """
        issues = []

        # Валидация файла
        try:
            self.validate_audio_file(audio_file)
        except ValueError as e:
            issues.append(f"Проблема с аудиофайлом: {e}")

        # Валидация метки
        if not isinstance(label, str):
            issues.append(f"Метка должна быть строкой, получена {type(label)}")
        elif not label or not label.strip():
            issues.append("Метка не может быть пустой")
        elif len(label.strip()) > 100:
            issues.append("Метка слишком длинная (максимум 100 символов)")

        return issues

    def validate_voiceprint_audio_file(self, audio_file: Path, max_duration_check: bool = True) -> List[str]:
        """
        Специальная валидация аудиофайла для voiceprint.

        Args:
            audio_file: Путь к аудиофайлу
            max_duration_check: Проверять ли максимальную длительность

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

        # Проверка размера файла (≤100MB для voiceprint)
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        if file_size_mb > 100:
            issues.append(f"Файл слишком большой: {file_size_mb:.1f}MB (максимум 100MB)")

        # Проверка длительности (≤30 секунд для voiceprint)
        if max_duration_check:
            try:
                import librosa
                duration = librosa.get_duration(path=str(audio_file))
                if duration > 30:
                    issues.append(f"Файл слишком длинный: {duration:.1f}с (максимум 30с)")
            except ImportError:
                issues.append("Не удалось проверить длительность: требуется librosa")
            except Exception as e:
                issues.append(f"Ошибка при проверке длительности: {e}")

        return issues

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
        self.start_operation("создание voiceprint")

        try:
            # Валидация параметров
            param_issues = self.validate_voiceprint_params(audio_file, label)
            if param_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с параметрами: {len(param_issues)}")
                for issue in param_issues[:3]:  # Показываем первые 3
                    self.log_with_emoji("warning", "   ", issue)

            # Валидация аудиофайла для voiceprint
            audio_issues = self.validate_voiceprint_audio_file(audio_file, max_duration_check)
            if audio_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с аудиофайлом: {len(audio_issues)}")
                for issue in audio_issues[:3]:  # Показываем первые 3
                    self.log_with_emoji("warning", "   ", issue)

                # Если есть критические проблемы, прерываем
                if any("слишком большой" in issue or "слишком длинный" in issue for issue in audio_issues):
                    raise ValueError(f"Критические проблемы с файлом: {audio_issues[0]}")

            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.log_with_emoji("info", "🎵", f"Создаю voiceprint для '{label}': {audio_file.name} ({file_size_mb:.1f}MB)")

            # Загружаем файл в pyannote.ai временное хранилище
            self.log_with_emoji("info", "📤", "Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.log_with_emoji("info", "✅", f"Файл загружен: {media_url}")

            # Создаем voiceprint job
            job_id = self._submit_voiceprint_job(media_url)
            self.log_with_emoji("info", "🚀", f"Voiceprint job запущен: {job_id}")

            # Ждем завершения
            voiceprint_data = self._wait_for_completion(job_id)
            
            # Формируем результат
            result = {
                "label": label,
                "voiceprint": voiceprint_data,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source_file": str(audio_file),
                "file_size_mb": file_size_mb
            }

            self.log_with_emoji("info", "✅", f"Voiceprint создан для '{label}'")
            self.end_operation("создание voiceprint", success=True)

            return result

        except Exception as e:
            self.end_operation("создание voiceprint", success=False)
            self.handle_error(e, f"создание voiceprint для '{label}'", reraise=True)
    
    # Метод _validate_audio_file удален - используется validate_voiceprint_audio_file
    
    def _submit_voiceprint_job(self, media_url: str) -> str:
        """Отправляет задачу на создание voiceprint с rate limiting."""
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
            self.log_with_emoji("info", "🔗", f"Webhook URL добавлен для voiceprint: {self.webhook_url}")

        def _submit_request():
            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                raise RuntimeError(f"Ошибка pyannote.ai API: {error_msg}")

            return response.json()

        # Выполняем запрос с rate limiting
        result = self.with_rate_limit(_submit_request, "voiceprint")
        return result["jobId"]
    
    def _wait_for_completion(self, job_id: str, max_wait_seconds: int = 300) -> str:
        """Ждет завершения voiceprint job и возвращает base64 voiceprint с retry логикой."""
        url = f"{self.base_url}/jobs/{job_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        def _check_job_status():
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
                raise RuntimeError("not-ready")

            else:
                raise RuntimeError(f"Неизвестный статус voiceprint job: {status}")

        # Используем retry с rate limiting
        try:
            return self.retry_with_backoff(
                lambda: self.with_rate_limit(_check_job_status, "poll"),
                max_attempts=max_wait_seconds // 2,  # Проверяем каждые 2 секунды
                base_delay=2.0,
                max_delay=10.0,
                exceptions=(RuntimeError, requests.RequestException)
            )
        except Exception as e:
            if "not-ready" in str(e):
                raise RuntimeError(f"Превышено время ожидания voiceprint job ({max_wait_seconds}с)")
            raise
    
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
        self.start_operation("создание voiceprint (async)")

        try:
            if not self.webhook_url:
                raise ValueError("webhook_url должен быть настроен для асинхронной обработки")

            # Валидация параметров
            param_issues = self.validate_voiceprint_params(audio_file, label)
            if param_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с параметрами: {len(param_issues)}")
                for issue in param_issues[:3]:
                    self.log_with_emoji("warning", "   ", issue)

            # Валидация аудиофайла
            audio_issues = self.validate_voiceprint_audio_file(audio_file, max_duration_check=True)
            if audio_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с аудиофайлом: {len(audio_issues)}")
                for issue in audio_issues[:3]:
                    self.log_with_emoji("warning", "   ", issue)

            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.log_with_emoji("info", "🚀", f"Запускаю асинхронное создание voiceprint для '{label}': {audio_file.name} ({file_size_mb:.1f}MB)")

            # Загружаем файл в pyannote.ai временное хранилище
            self.log_with_emoji("info", "📤", "Загружаю файл в pyannote.ai...")
            media_url = self.media_agent.upload_file(audio_file)
            self.log_with_emoji("info", "✅", f"Файл загружен: {media_url}")

            # Создаем voiceprint job с webhook
            job_id = self._submit_voiceprint_job(media_url)
            self.log_with_emoji("info", "✅", f"Асинхронный voiceprint job запущен: {job_id}")
            self.log_with_emoji("info", "📡", f"Результат будет отправлен на: {self.webhook_url}")

            self.end_operation("создание voiceprint (async)", success=True)
            return job_id

        except Exception as e:
            self.end_operation("создание voiceprint (async)", success=False)
            self.handle_error(e, "запуск асинхронного создания voiceprint", reraise=True)
