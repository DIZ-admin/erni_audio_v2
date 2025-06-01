# pipeline/diarization_agent.py

import logging
import requests
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential, retry_if_exception_type
from typing import List, Dict, Sequence, Optional
from .rate_limiter import PYANNOTE_RATE_LIMITER, rate_limit_decorator

PYANNOTE_API = "https://api.pyannote.ai/v1"

class DiarizationAgent:
    """
    Агент для работы с Pyannote:
      - diarize(wav_url)  → raw_diar: List[{"start", "end", "speaker", "confidence"}]
      - identify(wav_url, voiceprint_ids) → raw_diar_with_ids: List[...]
    """
    def __init__(self, api_key: str, use_identify: bool = False, voiceprint_ids: Optional[Sequence[str]] = None, webhook_url: Optional[str] = None):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.use_identify = use_identify
        self.voiceprint_ids = list(voiceprint_ids) if voiceprint_ids else []
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)

    @retry(
        stop=stop_after_attempt(40),
        wait=wait_exponential(multiplier=1, min=2, max=30),  # Экспоненциальный backoff
        retry=retry_if_exception_type((RuntimeError, requests.RequestException)),
        before_sleep=lambda retry_state: logging.getLogger(__name__).warning(
            f"Повтор {retry_state.attempt_number} для задачи {retry_state.args[1] if len(retry_state.args) > 1 else 'unknown'}"
        )
    )
    def _poll(self, job_id: str) -> Dict:
        try:
            self.logger.debug(f"Опрашиваю статус задачи: {job_id}")
            # Применяем rate limiting
            PYANNOTE_RATE_LIMITER.wait_if_needed("poll")
            r = requests.get(f"{PYANNOTE_API}/jobs/{job_id}", headers=self.headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            status = data["status"]

            if status in {"created", "running"}:
                self.logger.debug(f"Задача {job_id} ещё выполняется (статус: {status})")
                raise RuntimeError("not-ready")
            if status == "error":
                error_msg = data.get("error", "Неизвестная ошибка")
                self.logger.error(f"Ошибка в задаче {job_id}: {error_msg}")
                raise RuntimeError(f"Ошибка Pyannote API: {error_msg}")

            self.logger.info(f"Задача {job_id} завершена успешно")
            # Согласно документации, результат находится в поле "output"
            return data["output"]

        except requests.Timeout as e:
            self.logger.warning(f"Таймаут при опросе задачи {job_id}: {e}")
            raise RuntimeError("timeout") from e
        except requests.ConnectionError as e:
            self.logger.warning(f"Ошибка подключения при опросе задачи {job_id}: {e}")
            raise RuntimeError("connection-error") from e
        except requests.HTTPError as e:
            self.logger.error(f"HTTP ошибка при опросе задачи {job_id}: {e}")
            raise RuntimeError(f"HTTP ошибка: {e}") from e

    def diarize(self, wav_url: str) -> List[Dict]:
        try:
            # Определяем тип URL для логирования
            url_type = "виртуальный путь pyannote.ai" if wav_url.startswith("media://") else "внешний URL"
            self.logger.info(f"Запускаю диаризацию для: {wav_url} ({url_type})")

            # Подготавливаем payload
            payload = {"url": wav_url}
            if self.webhook_url:
                payload["webhook"] = self.webhook_url
                self.logger.info(f"🔗 Webhook URL добавлен: {self.webhook_url}")

            r = requests.post(
                f"{PYANNOTE_API}/diarize",
                json=payload,
                headers=self.headers,
                timeout=30,  # Увеличен таймаут для больших файлов
            )
            r.raise_for_status()

            job_data = r.json()
            job_id = job_data["jobId"]
            self.logger.info(f"Диаризация запущена, ID задачи: {job_id}")

            output = self._poll(job_id)
            self.logger.debug(f"Полный output диаризации: {output}")

            # Обработка различных форматов ответа API (обратная совместимость)
            diarization = None

            if isinstance(output, dict):
                # Новый формат API: поле "result"
                if "result" in output:
                    diarization = output["result"]
                    self.logger.debug("Извлечен массив diarization из поля 'result' (новый формат API)")
                # Старый формат API: поле "diarization"
                elif "diarization" in output:
                    diarization = output["diarization"]
                    self.logger.debug("Извлечен массив diarization из поля 'diarization' (старый формат API)")
                else:
                    available_keys = list(output.keys())
                    self.logger.error(f"Неожиданная структура output: {available_keys}")
                    raise KeyError(f"Не найден ключ 'result' или 'diarization' в output. Доступные ключи: {available_keys}")
            else:
                self.logger.error(f"Output не является словарем: {type(output)}")
                raise KeyError(f"Output должен быть словарем, получен: {type(output)}")

            # Валидация результата
            if not isinstance(diarization, list):
                self.logger.error(f"Diarization должен быть списком, получен: {type(diarization)}")
                raise ValueError(f"Неверный тип данных диаризации: {type(diarization)}")

            self.logger.info(f"Диаризация завершена: {len(diarization)} сегментов")
            return diarization

        except requests.Timeout as e:
            self.logger.error(f"Таймаут при запуске диаризации: {e}")
            raise RuntimeError(f"Таймаут при запуске диаризации: {e}") from e
        except requests.ConnectionError as e:
            self.logger.error(f"Ошибка подключения к Pyannote API: {e}")
            raise RuntimeError(f"Не удалось подключиться к Pyannote API: {e}") from e
        except requests.HTTPError as e:
            self.logger.error(f"HTTP ошибка при диаризации: {e}")
            raise RuntimeError(f"Ошибка Pyannote API: {e}") from e
        except KeyError as e:
            self.logger.error(f"Неожиданный формат ответа API: {e}")
            raise RuntimeError(f"Неожиданный формат ответа Pyannote API: {e}") from e

    def identify(self, wav_url: str) -> List[Dict]:
        if not self.voiceprint_ids:
            raise ValueError("Нужен хотя бы один voiceprint_id для identify()")

        try:
            # Определяем тип URL для логирования
            url_type = "виртуальный путь pyannote.ai" if wav_url.startswith("media://") else "внешний URL"
            self.logger.info(f"Запускаю идентификацию для: {wav_url} ({url_type}) с {len(self.voiceprint_ids)} голосовыми отпечатками")

            payload = {"url": wav_url, "voiceprintIds": self.voiceprint_ids}
            if self.webhook_url:
                payload["webhook"] = self.webhook_url
                self.logger.info(f"🔗 Webhook URL добавлен для identify: {self.webhook_url}")

            r = requests.post(
                f"{PYANNOTE_API}/identify",
                json=payload,
                headers=self.headers,
                timeout=30,  # Увеличен таймаут для больших файлов
            )
            r.raise_for_status()

            job_data = r.json()
            job_id = job_data["jobId"]
            self.logger.info(f"Идентификация запущена, ID задачи: {job_id}")

            output = self._poll(job_id)
            self.logger.debug(f"Полный output идентификации: {output}")

            # Обработка различных форматов ответа API (обратная совместимость)
            diarization = None

            if isinstance(output, dict):
                # Новый формат API: поле "result"
                if "result" in output:
                    diarization = output["result"]
                    self.logger.debug("Извлечен массив diarization из поля 'result' (новый формат API)")
                # Старый формат API: поле "diarization"
                elif "diarization" in output:
                    diarization = output["diarization"]
                    self.logger.debug("Извлечен массив diarization из поля 'diarization' (старый формат API)")
                else:
                    available_keys = list(output.keys())
                    self.logger.error(f"Неожиданная структура output: {available_keys}")
                    raise KeyError(f"Не найден ключ 'result' или 'diarization' в output. Доступные ключи: {available_keys}")
            else:
                self.logger.error(f"Output не является словарем: {type(output)}")
                raise KeyError(f"Output должен быть словарем, получен: {type(output)}")

            # Валидация результата
            if not isinstance(diarization, list):
                self.logger.error(f"Diarization должен быть списком, получен: {type(diarization)}")
                raise ValueError(f"Неверный тип данных диаризации: {type(diarization)}")

            self.logger.info(f"Идентификация завершена: {len(diarization)} сегментов")
            return diarization

        except requests.Timeout as e:
            self.logger.error(f"Таймаут при запуске идентификации: {e}")
            raise RuntimeError(f"Таймаут при запуске идентификации: {e}") from e
        except requests.ConnectionError as e:
            self.logger.error(f"Ошибка подключения к Pyannote API: {e}")
            raise RuntimeError(f"Не удалось подключиться к Pyannote API: {e}") from e
        except requests.HTTPError as e:
            self.logger.error(f"HTTP ошибка при идентификации: {e}")
            raise RuntimeError(f"Ошибка Pyannote API: {e}") from e
        except KeyError as e:
            self.logger.error(f"Неожиданный формат ответа API: {e}")
            raise RuntimeError(f"Неожиданный формат ответа Pyannote API: {e}") from e

    def run(self, wav_url: str) -> List[Dict]:
        """
        Если use_identify = False → вызываем diarize()
        Иначе → identify(wav_url)
        """
        if self.use_identify:
            return self.identify(wav_url)
        else:
            return self.diarize(wav_url)

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
                f"{PYANNOTE_API}/diarize",
                json=payload,
                headers=self.headers,
                timeout=30,
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
                f"{PYANNOTE_API}/identify",
                json=payload,
                headers=self.headers,
                timeout=30,
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
