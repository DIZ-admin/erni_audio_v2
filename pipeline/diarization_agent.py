# pipeline/diarization_agent.py

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import List, Dict, Sequence, Optional

from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin
from .retry_mixin import RetryMixin
from .rate_limit_mixin import RateLimitMixin
from .constants import API_ENDPOINTS
from .settings import SETTINGS

PYANNOTE_API = SETTINGS.api.pyannote_url

class DiarizationAgent(BaseAgent, ValidationMixin, RetryMixin, RateLimitMixin):
    """
    Агент для работы с Pyannote:
      - diarize(wav_url)  → raw_diar: List[{"start", "end", "speaker", "confidence"}]
      - identify(wav_url, voiceprint_ids) → raw_diar_with_ids: List[...]
    """
    def __init__(self, api_key: str, use_identify: bool = False, voiceprint_ids: Optional[Sequence[str]] = None, webhook_url: Optional[str] = None):
        """
        Инициализация агента диаризации.

        Args:
            api_key: API ключ pyannote.ai
            use_identify: Использовать ли идентификацию вместо диаризации
            voiceprint_ids: Список ID голосовых отпечатков для идентификации
            webhook_url: URL для асинхронных уведомлений
        """
        # Инициализируем базовые классы
        BaseAgent.__init__(self, "DiarizationAgent")
        ValidationMixin.__init__(self)
        RetryMixin.__init__(self)
        RateLimitMixin.__init__(self, "pyannote")

        # Настройки агента
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.use_identify = use_identify
        self.voiceprint_ids = list(voiceprint_ids) if voiceprint_ids else []
        self.webhook_url = webhook_url

        # Валидируем voiceprint_ids если они предоставлены
        if self.voiceprint_ids:
            self.validate_voiceprint_ids(self.voiceprint_ids)

        # Валидируем webhook URL если предоставлен
        if self.webhook_url:
            is_valid, message = self.validate_url(self.webhook_url, require_https=True)
            if not is_valid:
                self.handle_error(ValueError(f"Невалидный webhook URL: {message}"), "валидация webhook URL")

        self.log_with_emoji("info", "✅", f"DiarizationAgent инициализирован (identify={use_identify})")

    def _poll(self, job_id: str) -> Dict:
        """
        Опрашивает статус задачи с интеллектуальным retry.

        Args:
            job_id: ID задачи для опроса

        Returns:
            Результат выполнения задачи
        """
        def _poll_request():
            self.log_with_emoji("debug", "🔍", f"Опрашиваю статус задачи: {job_id}")

            r = requests.get(
                f"{PYANNOTE_API}/jobs/{job_id}",
                headers=self.headers,
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            status = data["status"]

            if status in {"created", "running"}:
                self.log_with_emoji("debug", "⏳", f"Задача {job_id} ещё выполняется (статус: {status})")
                raise RuntimeError("not-ready")

            if status == "error":
                error_msg = data.get("error", "Неизвестная ошибка")
                self.log_with_emoji("error", "❌", f"Ошибка в задаче {job_id}: {error_msg}")
                raise RuntimeError(f"Ошибка Pyannote API: {error_msg}")

            self.log_with_emoji("info", "✅", f"Задача {job_id} завершена успешно")
            return data["output"]

        # Используем retry с rate limiting
        try:
            return self.retry_with_backoff(
                lambda: self.with_rate_limit(_poll_request, "poll"),
                max_attempts=40,
                base_delay=2.0,
                max_delay=30.0,
                exceptions=(RuntimeError, requests.RequestException)
            )
        except Exception as e:
            self.handle_error(e, f"опрос задачи {job_id}")

    def diarize(self, wav_url: str) -> List[Dict]:
        """
        Выполняет диаризацию аудио.

        Args:
            wav_url: URL аудиофайла (может быть media:// или внешний URL)

        Returns:
            Список сегментов диаризации
        """
        self.start_operation("диаризация")

        try:
            # Валидируем URL
            if not wav_url.startswith("media://"):
                is_valid, message = self.validate_url(wav_url, require_https=False)
                if not is_valid:
                    raise ValueError(f"Невалидный URL: {message}")

            # Определяем тип URL для логирования
            url_type = "виртуальный путь pyannote.ai" if wav_url.startswith("media://") else "внешний URL"
            self.log_with_emoji("info", "🎤", f"Запускаю диаризацию для: {wav_url} ({url_type})")

            # Подготавливаем payload
            payload = {"url": wav_url}
            if self.webhook_url:
                payload["webhook"] = self.webhook_url
                self.log_with_emoji("info", "🔗", f"Webhook URL добавлен: {self.webhook_url}")

            # Выполняем запрос с rate limiting
            def _start_diarization():
                r = requests.post(
                    f"{PYANNOTE_API}{API_ENDPOINTS['pyannote']['diarize']}",
                    json=payload,
                    headers=self.headers,
                    timeout=SETTINGS.api.pyannote_connection_timeout,
                )
                r.raise_for_status()
                return r.json()

            job_data = self.with_rate_limit(_start_diarization, "diarize")
            job_id = job_data["jobId"]
            self.log_with_emoji("info", "🚀", f"Диаризация запущена, ID задачи: {job_id}")

            # Опрашиваем результат
            output = self._poll(job_id)
            self.log_with_emoji("debug", "📊", f"Полный output диаризации: {output}")

            # Извлекаем результат диаризации
            diarization = self._extract_diarization_result(output)

            self.end_operation("диаризация", success=True)
            self.log_with_emoji("info", "✅", f"Диаризация завершена: {len(diarization)} сегментов")

            return diarization

        except Exception as e:
            self.end_operation("диаризация", success=False)
            self.handle_error(e, "диаризация")

    def _extract_diarization_result(self, output: Dict) -> List[Dict]:
        """
        Извлекает результат диаризации из ответа API.

        Args:
            output: Ответ от API

        Returns:
            Список сегментов диаризации
        """
        if not isinstance(output, dict):
            raise ValueError(f"Output должен быть словарем, получен: {type(output)}")

        # Обработка различных форматов ответа API (обратная совместимость)
        diarization = None

        # Новый формат API: поле "result"
        if "result" in output:
            diarization = output["result"]
            self.log_with_emoji("debug", "📋", "Извлечен массив diarization из поля 'result' (новый формат API)")
        # Старый формат API: поле "diarization"
        elif "diarization" in output:
            diarization = output["diarization"]
            self.log_with_emoji("debug", "📋", "Извлечен массив diarization из поля 'diarization' (старый формат API)")
        else:
            available_keys = list(output.keys())
            error_msg = f"Не найден ключ 'result' или 'diarization' в output. Доступные ключи: {available_keys}"
            self.log_with_emoji("error", "❌", f"Неожиданная структура output: {available_keys}")
            raise KeyError(error_msg)

        # Валидация результата
        if not isinstance(diarization, list):
            raise ValueError(f"Неверный тип данных диаризации: {type(diarization)}, ожидался list")

        return diarization

    def identify(self, wav_url: str) -> List[Dict]:
        """
        Выполняет идентификацию спикеров с использованием voiceprints.

        Args:
            wav_url: URL аудиофайла

        Returns:
            Список сегментов с идентифицированными спикерами
        """
        if not self.voiceprint_ids:
            raise ValueError("Нужен хотя бы один voiceprint_id для identify()")

        self.start_operation("идентификация")

        try:
            # Валидируем URL
            if not wav_url.startswith("media://"):
                is_valid, message = self.validate_url(wav_url, require_https=False)
                if not is_valid:
                    raise ValueError(f"Невалидный URL: {message}")

            # Определяем тип URL для логирования
            url_type = "виртуальный путь pyannote.ai" if wav_url.startswith("media://") else "внешний URL"
            self.log_with_emoji("info", "🔍",
                f"Запускаю идентификацию для: {wav_url} ({url_type}) "
                f"с {len(self.voiceprint_ids)} голосовыми отпечатками"
            )

            # Подготавливаем payload
            payload = {"url": wav_url, "voiceprintIds": self.voiceprint_ids}
            if self.webhook_url:
                payload["webhook"] = self.webhook_url
                self.log_with_emoji("info", "🔗", f"Webhook URL добавлен для identify: {self.webhook_url}")

            # Выполняем запрос с rate limiting
            def _start_identification():
                r = requests.post(
                    f"{PYANNOTE_API}{API_ENDPOINTS['pyannote']['identify']}",
                    json=payload,
                    headers=self.headers,
                    timeout=SETTINGS.api.pyannote_connection_timeout,
                )
                r.raise_for_status()
                return r.json()

            job_data = self.with_rate_limit(_start_identification, "identify")
            job_id = job_data["jobId"]
            self.log_with_emoji("info", "🚀", f"Идентификация запущена, ID задачи: {job_id}")

            # Опрашиваем результат
            output = self._poll(job_id)
            self.log_with_emoji("debug", "📊", f"Полный output идентификации: {output}")

            # Извлекаем результат идентификации
            diarization = self._extract_diarization_result(output)

            self.end_operation("идентификация", success=True)
            self.log_with_emoji("info", "✅", f"Идентификация завершена: {len(diarization)} сегментов")

            return diarization

        except Exception as e:
            self.end_operation("идентификация", success=False)
            self.handle_error(e, "идентификация")

    def run(self, wav_url: str) -> List[Dict]:
        """
        Основной метод выполнения агента.

        Args:
            wav_url: URL аудиофайла

        Returns:
            Список сегментов диаризации или идентификации
        """
        self.start_operation("обработка аудио")

        try:
            if self.use_identify:
                result = self.identify(wav_url)
                operation_type = "идентификация"
            else:
                result = self.diarize(wav_url)
                operation_type = "диаризация"

            self.end_operation("обработка аудио", success=True)
            self.log_with_emoji("info", "🎯", f"{operation_type.capitalize()} завершена успешно")

            return result

        except Exception as e:
            self.end_operation("обработка аудио", success=False)
            self.handle_error(e, "обработка аудио")

    def run_async(self, wav_url: str) -> str:
        """
        Запускает обработку асинхронно с веб-хуком.

        Args:
            wav_url: URL аудиофайла

        Returns:
            job_id для отслеживания статуса
        """
        if self.use_identify:
            return self.identify_async(wav_url)
        else:
            return self.diarize_async(wav_url)

    def diarize_async(self, wav_url: str) -> str:
        """
        Запускает диаризацию асинхронно с веб-хуком.

        Args:
            wav_url: URL аудиофайла

        Returns:
            job_id для отслеживания статуса

        Raises:
            ValueError: Если webhook_url не настроен
        """
        if not self.webhook_url:
            raise ValueError("webhook_url должен быть настроен для асинхронной обработки")

        try:
            url_type = "виртуальный путь pyannote.ai" if wav_url.startswith("media://") else "внешний URL"
            self.logger.info(f"🚀 Запускаю асинхронную диаризацию для: {wav_url} ({url_type})")

            payload = {
                "url": wav_url,
                "webhook": self.webhook_url
            }

            r = requests.post(
                f"{PYANNOTE_API}{API_ENDPOINTS['pyannote']['diarize']}",
                json=payload,
                headers=self.headers,
                timeout=SETTINGS.api.pyannote_connection_timeout,
            )
            r.raise_for_status()

            job_data = r.json()
            job_id = job_data["jobId"]

            self.logger.info(f"✅ Асинхронная диаризация запущена: {job_id}")
            self.logger.info(f"📡 Результат будет отправлен на: {self.webhook_url}")

            return job_id

        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска асинхронной диаризации: {e}")
            raise

    def identify_async(self, wav_url: str) -> str:
        """
        Запускает идентификацию асинхронно с веб-хуком.

        Args:
            wav_url: URL аудиофайла

        Returns:
            job_id для отслеживания статуса

        Raises:
            ValueError: Если webhook_url не настроен или voiceprint_ids пусты
        """
        if not self.webhook_url:
            raise ValueError("webhook_url должен быть настроен для асинхронной обработки")

        if not self.voiceprint_ids:
            raise ValueError("Нужен хотя бы один voiceprint_id для identify()")

        try:
            url_type = "виртуальный путь pyannote.ai" if wav_url.startswith("media://") else "внешний URL"
            self.logger.info(f"🚀 Запускаю асинхронную идентификацию для: {wav_url} ({url_type})")

            payload = {
                "url": wav_url,
                "voiceprintIds": self.voiceprint_ids,
                "webhook": self.webhook_url
            }

            r = requests.post(
                f"{PYANNOTE_API}{API_ENDPOINTS['pyannote']['identify']}",
                json=payload,
                headers=self.headers,
                timeout=SETTINGS.api.pyannote_connection_timeout,
            )
            r.raise_for_status()

            job_data = r.json()
            job_id = job_data["jobId"]

            self.logger.info(f"✅ Асинхронная идентификация запущена: {job_id}")
            self.logger.info(f"📡 Результат будет отправлен на: {self.webhook_url}")

            return job_id

        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска асинхронной идентификации: {e}")
            raise
