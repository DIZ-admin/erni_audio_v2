# pipeline/transcription_agent.py

import logging
from openai import OpenAI
from pathlib import Path
from typing import List, Dict, Optional
import openai
import time
import subprocess
import tempfile
import uuid
import random
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from .config import ConfigurationManager

class TranscriptionAgent:
    """
    Агент для взаимодействия с OpenAI Speech-to-Text моделями.
    Поддерживает whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe.
    Возвращает список сегментов с полями:
    id, start, end, text, tokens, avg_logprob, no_speech_prob, temperature, compression_ratio.
    """

    # Поддерживаемые модели и их характеристики
    SUPPORTED_MODELS = {
        "whisper-1": {
            "name": "Whisper v1",
            "description": "Базовая модель Whisper, быстрая и экономичная",
            "max_file_size_mb": 25,
            "supports_language": True,
            "supports_prompt": True,
            "supports_verbose_json": True,
            "cost_tier": "low"
        },
        "gpt-4o-mini-transcribe": {
            "name": "GPT-4o Mini Transcribe",
            "description": "Улучшенная модель с балансом цены и качества",
            "max_file_size_mb": 25,
            "supports_language": True,
            "supports_prompt": True,
            "supports_verbose_json": False,
            "cost_tier": "medium"
        },
        "gpt-4o-transcribe": {
            "name": "GPT-4o Transcribe",
            "description": "Наиболее точная модель с лучшим качеством распознавания",
            "max_file_size_mb": 25,
            "supports_language": True,
            "supports_prompt": True,
            "supports_verbose_json": False,
            "cost_tier": "high"
        }
    }

    def __init__(self, api_key: str, model: str = "whisper-1", language: Optional[str] = None, response_format: str = "auto"):
        """
        Инициализация агента транскрипции.

        Args:
            api_key: OpenAI API ключ
            model: Модель для транскрипции (whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe)
            language: Код языка (например, 'en', 'ru', 'de') для улучшения точности
            response_format: Формат ответа (auto, json, verbose_json, text, srt, vtt)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = self._validate_model(model)
        self.language = language
        self.response_format = self._determine_response_format(response_format)
        self.logger = logging.getLogger(__name__)

        # Загружаем конфигурацию для retry
        self.config = ConfigurationManager()
        self.retry_config = self.config.get_retry_config("transcription")

        # Статистика retry для мониторинга
        self.retry_stats = {
            "total_attempts": 0,
            "rate_limit_retries": 0,
            "connection_retries": 0,
            "other_retries": 0,
            "total_retry_time": 0.0
        }

        # Логируем выбранную модель
        model_info = self.SUPPORTED_MODELS[self.model]
        self.logger.info(f"Инициализирован TranscriptionAgent с моделью: {model_info['name']} ({model_info['description']})")

    def _get_adaptive_timeout(self, file_size_mb: float) -> float:
        """
        Вычисляет адаптивный таймаут на основе размера файла.

        Args:
            file_size_mb: Размер файла в мегабайтах

        Returns:
            Таймаут в секундах
        """
        # Базовый таймаут 60 секунд + 10 секунд на каждый MB
        base_timeout = 60
        size_factor = max(1.0, file_size_mb * 10)
        adaptive_timeout = min(base_timeout + size_factor, 600)  # Максимум 10 минут

        self.logger.debug(f"Адаптивный таймаут для файла {file_size_mb:.1f}MB: {adaptive_timeout:.1f}с")
        return adaptive_timeout

    def _intelligent_wait_strategy(self, retry_state):
        """
        Интеллектуальная стратегия ожидания с различной логикой для разных типов ошибок.
        """
        exception = retry_state.outcome.exception()
        attempt = retry_state.attempt_number

        if isinstance(exception, openai.RateLimitError):
            # Для rate limit - экспоненциальный backoff с jitter
            base_delay = 2.0
            max_delay = 120.0  # 2 минуты максимум

            # Экспоненциальный backoff с jitter
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = random.uniform(0.1, 0.3) * delay
            final_delay = delay + jitter

            self.logger.warning(
                f"🔄 Rate limit hit (попытка {attempt}), ждем {final_delay:.1f}с "
                f"(base: {delay:.1f}с, jitter: {jitter:.1f}с)"
            )

        elif isinstance(exception, openai.APIConnectionError):
            # Для сетевых ошибок - быстрые повторы
            base_delay = 0.5
            final_delay = min(base_delay * attempt, 10.0)  # Максимум 10 секунд

            self.logger.warning(
                f"🌐 Сетевая ошибка (попытка {attempt}), быстрый повтор через {final_delay:.1f}с"
            )

        else:
            # Для других ошибок - стандартный backoff
            base_delay = 1.0
            final_delay = min(base_delay * (1.5 ** (attempt - 1)), 60.0)

            self.logger.warning(
                f"⚠️ Другая ошибка (попытка {attempt}), повтор через {final_delay:.1f}с: {type(exception).__name__}"
            )

        # Обновляем общее время retry
        self.retry_stats["total_retry_time"] += final_delay

        return final_delay

    def _log_retry_statistics(self):
        """Логирует статистику retry для мониторинга производительности."""
        if self.retry_stats["total_attempts"] > 0:
            self.logger.info(
                f"📊 Статистика retry: всего попыток={self.retry_stats['total_attempts']}, "
                f"rate_limit={self.retry_stats['rate_limit_retries']}, "
                f"connection={self.retry_stats['connection_retries']}, "
                f"other={self.retry_stats['other_retries']}, "
                f"общее время retry={self.retry_stats['total_retry_time']:.1f}с"
            )

    # Поддерживаемые форматы ответа
    SUPPORTED_RESPONSE_FORMATS = {
        "auto": "Автоматический выбор оптимального формата",
        "json": "Минимальный JSON с полем text",
        "verbose_json": "Подробный JSON со сегментами и метаданными",
        "text": "Чистый текст без обёртки",
        "srt": "Субтитры в формате SRT",
        "vtt": "Субтитры в формате WebVTT"
    }

    def _validate_model(self, model: str) -> str:
        """Валидация выбранной модели."""
        if model not in self.SUPPORTED_MODELS:
            available_models = ", ".join(self.SUPPORTED_MODELS.keys())
            raise ValueError(f"Неподдерживаемая модель '{model}'. Доступные модели: {available_models}")
        return model

    def _validate_response_format(self, response_format: str) -> str:
        """Валидация формата ответа."""
        if response_format not in self.SUPPORTED_RESPONSE_FORMATS:
            available_formats = ", ".join(self.SUPPORTED_RESPONSE_FORMATS.keys())
            raise ValueError(f"Неподдерживаемый формат '{response_format}'. Доступные форматы: {available_formats}")
        return response_format

    def _determine_response_format(self, requested_format: str) -> str:
        """Определяет оптимальный формат ответа для модели."""
        # Валидируем запрошенный формат
        self._validate_response_format(requested_format)

        # Если auto, выбираем оптимальный формат
        if requested_format == "auto":
            if self.SUPPORTED_MODELS[self.model]["supports_verbose_json"]:
                return "verbose_json"  # Для whisper-1
            else:
                return "json"  # Для gpt-4o моделей

        # Если запрошен verbose_json, но модель его не поддерживает
        if requested_format == "verbose_json" and not self.SUPPORTED_MODELS[self.model]["supports_verbose_json"]:
            self.logger.warning(f"Модель {self.model} не поддерживает verbose_json, используем json")
            return "json"

        return requested_format

    def run(self, wav_local: Path, prompt: str = "") -> List[Dict]:
        """
        Выполняет транскрипцию аудиофайла.

        Args:
            wav_local: Путь к локальному аудиофайлу
            prompt: Контекстная подсказка для улучшения точности

        Returns:
            Список сегментов транскрипции
        """
        start_time = time.time()

        try:
            # Валидация файла
            self._validate_audio_file(wav_local)

            file_size_mb = wav_local.stat().st_size / (1024 * 1024)  # MB
            max_size = self.SUPPORTED_MODELS[self.model]["max_file_size_mb"]
            model_info = self.SUPPORTED_MODELS[self.model]

            self.logger.info(f"Начинаю транскрипцию с {model_info['name']}: {wav_local} ({file_size_mb:.1f}MB)")

            # Проверяем, нужно ли разбивать файл
            if file_size_mb > max_size:
                return self._transcribe_large_file(wav_local, prompt)
            else:
                return self._transcribe_single_file(wav_local, prompt)

        except openai.APIConnectionError as e:
            self.logger.error(f"Ошибка подключения к OpenAI API: {e}")
            raise RuntimeError(f"Не удалось подключиться к OpenAI API: {e}") from e
        except openai.RateLimitError as e:
            self.logger.error(f"Превышен лимит запросов OpenAI API: {e}")
            raise RuntimeError(f"Превышен лимит запросов OpenAI API: {e}") from e
        except openai.APIStatusError as e:
            self.logger.error(f"Ошибка OpenAI API (статус {e.status_code}): {e}")
            raise RuntimeError(f"Ошибка OpenAI API: {e}") from e
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при транскрипции: {e}")
            raise RuntimeError(f"Ошибка транскрипции: {e}") from e

    def _validate_audio_file(self, wav_local: Path) -> None:
        """Валидация аудиофайла перед транскрипцией."""
        if not wav_local.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {wav_local}")

        # Проверка размера файла - теперь не блокируем, а предупреждаем
        file_size_mb = wav_local.stat().st_size / (1024 * 1024)
        max_size = self.SUPPORTED_MODELS[self.model]["max_file_size_mb"]

        if file_size_mb > max_size:
            self.logger.warning(f"Файл ({file_size_mb:.1f}MB) превышает лимит OpenAI ({max_size}MB). Будет разбит на части.")

    def _split_audio_file(self, wav_local: Path, chunk_duration_minutes: int = 10) -> List[Path]:
        """
        Разбивает большой аудиофайл на части для обработки в OpenAI API.

        Args:
            wav_local: Путь к исходному файлу
            chunk_duration_minutes: Длительность каждой части в минутах

        Returns:
            Список путей к частям файла
        """
        try:
            self.logger.info(f"Разбиваю файл {wav_local.name} на части по {chunk_duration_minutes} минут...")

            # Загружаем аудио
            audio = AudioSegment.from_wav(wav_local)
            chunk_duration_ms = chunk_duration_minutes * 60 * 1000  # в миллисекундах

            chunks = []
            temp_dir = Path(tempfile.gettempdir())

            # Разбиваем на части
            for i, start_ms in enumerate(range(0, len(audio), chunk_duration_ms)):
                end_ms = min(start_ms + chunk_duration_ms, len(audio))
                chunk = audio[start_ms:end_ms]

                # Сохраняем часть
                chunk_path = temp_dir / f"{wav_local.stem}_chunk_{i:03d}.wav"
                chunk.export(chunk_path, format="wav")
                chunks.append(chunk_path)

                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                self.logger.debug(f"Создана часть {i+1}: {chunk_path.name} ({chunk_size_mb:.1f}MB)")

            self.logger.info(f"Файл разбит на {len(chunks)} частей")
            return chunks

        except Exception as e:
            self.logger.error(f"Ошибка разбиения файла: {e}")
            raise RuntimeError(f"Не удалось разбить файл: {e}") from e

    def _transcribe_single_file(self, wav_local: Path, prompt: str = "") -> List[Dict]:
        """Транскрибирует один файл с улучшенной retry логикой."""
        start_time = time.time()
        file_size_mb = wav_local.stat().st_size / (1024 * 1024)

        # Получаем адаптивный таймаут
        adaptive_timeout = self._get_adaptive_timeout(file_size_mb)

        # Подготовка параметров запроса
        transcription_params = self._prepare_transcription_params(prompt)

        # Вызываем метод с retry логикой
        result = self._transcribe_with_intelligent_retry(wav_local, transcription_params, adaptive_timeout)

        # Логируем статистику
        duration = time.time() - start_time
        self.logger.info(f"✅ Транскрипция завершена за {duration:.2f}с (файл: {file_size_mb:.1f}MB)")
        self._log_retry_statistics()

        return result

    @retry(
        stop=stop_after_attempt(8),  # Увеличено с 3 до 8 попыток
        wait=wait_exponential(multiplier=1, min=1, max=120),  # Экспоненциальный backoff 1-120с
        retry=retry_if_exception_type((
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError
        )),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True
    )
    def _transcribe_with_intelligent_retry(self, wav_local: Path, transcription_params: Dict, timeout: float) -> List[Dict]:
        """Выполняет транскрипцию с интеллектуальной retry логикой."""
        try:
            # Устанавливаем адаптивный таймаут для клиента
            client_with_timeout = self.client.with_options(timeout=timeout)

            with open(wav_local, "rb") as audio_file:
                transcript = client_with_timeout.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    **transcription_params
                )

            # Обработка результата
            return self._process_transcript_response(transcript)

        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
            # Логируем ошибку для статистики (стратегия retry обрабатывается tenacity)
            if isinstance(e, openai.RateLimitError):
                self.retry_stats["rate_limit_retries"] += 1
            elif isinstance(e, openai.APIConnectionError):
                self.retry_stats["connection_retries"] += 1
            else:
                self.retry_stats["other_retries"] += 1

            self.retry_stats["total_attempts"] += 1
            raise  # Перебрасываем исключение для tenacity

        except openai.APIStatusError as e:
            self.logger.error(f"Ошибка OpenAI API (статус {e.status_code}): {e}")
            if e.status_code == 429:  # Rate limit
                raise openai.RateLimitError(f"Rate limit: {e}") from e
            else:
                raise RuntimeError(f"Ошибка OpenAI API: {e}") from e

    def _transcribe_large_file(self, wav_local: Path, prompt: str = "") -> List[Dict]:
        """Транскрибирует большой файл, разбивая его на части."""
        self.logger.info(f"Обрабатываю большой файл через разбиение на части...")

        # Разбиваем файл на части
        chunks = self._split_audio_file(wav_local, chunk_duration_minutes=10)

        all_segments = []
        total_offset = 0.0

        try:
            for i, chunk_path in enumerate(chunks):
                self.logger.info(f"Обрабатываю часть {i+1}/{len(chunks)}: {chunk_path.name}")

                # Транскрибируем часть
                chunk_segments = self._transcribe_single_file(chunk_path, prompt)

                # Корректируем временные метки с учетом смещения
                for segment in chunk_segments:
                    segment['start'] += total_offset
                    segment['end'] += total_offset
                    segment['id'] = len(all_segments)  # Перенумеровываем ID

                all_segments.extend(chunk_segments)

                # Обновляем смещение для следующей части (10 минут = 600 секунд)
                total_offset += 10 * 60

                self.logger.info(f"Часть {i+1} обработана: {len(chunk_segments)} сегментов")

        finally:
            # Удаляем временные файлы
            for chunk_path in chunks:
                try:
                    chunk_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Не удалось удалить временный файл {chunk_path}: {e}")

        self.logger.info(f"Большой файл обработан: {len(all_segments)} сегментов из {len(chunks)} частей")
        return all_segments

    def _prepare_transcription_params(self, prompt: str) -> Dict:
        """Подготовка параметров для запроса транскрипции."""
        params = {
            "response_format": self.response_format,
            "temperature": 0,
        }

        # Добавляем prompt если поддерживается и предоставлен
        if prompt and self.SUPPORTED_MODELS[self.model]["supports_prompt"]:
            params["prompt"] = prompt

        # Добавляем язык если поддерживается и указан
        if self.language and self.SUPPORTED_MODELS[self.model]["supports_language"]:
            params["language"] = self.language

        return params

    def _process_transcript_response(self, transcript) -> List[Dict]:
        """Обработка ответа транскрипции в зависимости от формата."""

        # Обработка в зависимости от формата ответа
        if self.response_format == "verbose_json":
            # verbose_json возвращает сегменты
            segments = getattr(transcript, 'segments', [])

            if not segments:
                self.logger.warning(f"Модель {self.model} не вернула сегментов в verbose_json")
                return []

            # Конвертируем сегменты в словари
            processed_segments = []
            for segment in segments:
                if hasattr(segment, 'model_dump'):
                    segment_dict = segment.model_dump()
                elif hasattr(segment, '__dict__'):
                    segment_dict = segment.__dict__
                else:
                    segment_dict = dict(segment)

                processed_segments.append(segment_dict)

            model_info = self.SUPPORTED_MODELS[self.model]
            self.logger.info(f"{model_info['name']}: обработано {len(processed_segments)} сегментов (verbose_json)")
            return processed_segments

        elif self.response_format == "json":
            # json возвращает только текст
            text = getattr(transcript, 'text', '')
            if not text:
                self.logger.warning(f"Модель {self.model} не вернула текст в json")
                return []

            # Создаем искусственный сегмент
            duration = getattr(transcript, 'duration', 0.0)
            segment = {
                "id": 0,
                "start": 0.0,
                "end": duration,
                "text": text.strip(),
                "tokens": [],
                "avg_logprob": 0.0,
                "no_speech_prob": 0.0,
                "temperature": 0.0,
                "compression_ratio": 1.0
            }

            model_info = self.SUPPORTED_MODELS[self.model]
            self.logger.info(f"{model_info['name']}: создан сегмент из {len(text)} символов (json)")
            return [segment]

        else:
            # Для text, srt, vtt форматов возвращаем как есть
            # Эти форматы обычно используются для прямого вывода, а не для обработки
            text_content = str(transcript) if transcript else ""
            if not text_content:
                self.logger.warning(f"Модель {self.model} не вернула контент в формате {self.response_format}")
                return []

            segment = {
                "id": 0,
                "start": 0.0,
                "end": 0.0,
                "text": text_content.strip(),
                "tokens": [],
                "avg_logprob": 0.0,
                "no_speech_prob": 0.0,
                "temperature": 0.0,
                "compression_ratio": 1.0
            }

            model_info = self.SUPPORTED_MODELS[self.model]
            self.logger.info(f"{model_info['name']}: обработан контент в формате {self.response_format}")
            return [segment]

    def get_model_info(self) -> Dict:
        """Возвращает информацию о текущей модели."""
        return {
            "model": self.model,
            "language": self.language,
            **self.SUPPORTED_MODELS[self.model]
        }

    @classmethod
    def get_available_models(cls) -> Dict:
        """Возвращает список доступных моделей."""
        return cls.SUPPORTED_MODELS.copy()

    def set_language(self, language: Optional[str]) -> None:
        """Устанавливает язык для транскрипции."""
        self.language = language
        if language:
            self.logger.info(f"Установлен язык транскрипции: {language}")
        else:
            self.logger.info("Язык транскрипции сброшен (автоопределение)")

    def estimate_cost(self, file_size_mb: float) -> str:
        """Оценивает примерную стоимость транскрипции."""
        cost_tier = self.SUPPORTED_MODELS[self.model]["cost_tier"]

        cost_estimates = {
            "low": f"~${file_size_mb * 0.006:.3f}",  # whisper-1: $0.006/min
            "medium": f"~${file_size_mb * 0.012:.3f}",  # gpt-4o-mini-transcribe: примерно в 2 раза дороже
            "high": f"~${file_size_mb * 0.024:.3f}"  # gpt-4o-transcribe: примерно в 4 раза дороже
        }

        return cost_estimates.get(cost_tier, "Неизвестно")
