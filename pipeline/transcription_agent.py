# pipeline/transcription_agent.py

import logging
from openai import OpenAI
from pathlib import Path
from typing import List, Dict, Optional, Any
import openai
import time
import subprocess
import tempfile
import uuid
import random
import asyncio
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydub import AudioSegment
from .config import ConfigurationManager
from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin
from .retry_mixin import RetryMixin
from .rate_limit_mixin import RateLimitMixin
from .constants import (
    SUPPORTED_TRANSCRIPTION_MODELS,
    DEFAULT_MAX_CONCURRENT_CHUNKS,
    DEFAULT_CHUNK_TIMEOUT_MINUTES
)

class TranscriptionAgent(BaseAgent, ValidationMixin, RetryMixin, RateLimitMixin):
    """
    Агент для взаимодействия с OpenAI Speech-to-Text моделями.
    Поддерживает whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe.
    Возвращает список сегментов с полями:
    id, start, end, text, tokens, avg_logprob, no_speech_prob, temperature, compression_ratio.
    """

    # Поддерживаемые модели и их характеристики (из констант)
    SUPPORTED_MODELS = SUPPORTED_TRANSCRIPTION_MODELS

    def __init__(self, api_key: str, model: str = "whisper-1", language: Optional[str] = None, response_format: str = "auto"):
        """
        Инициализация агента транскрипции.

        Args:
            api_key: OpenAI API ключ
            model: Модель для транскрипции (whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe)
            language: Код языка (например, 'en', 'ru', 'de') для улучшения точности
            response_format: Формат ответа (auto, json, verbose_json, text, srt, vtt)
        """
        # Инициализация базовых классов
        BaseAgent.__init__(self, name="TranscriptionAgent")
        ValidationMixin.__init__(self)
        RetryMixin.__init__(self)
        RateLimitMixin.__init__(self, api_name="openai")

        self.client = OpenAI(api_key=api_key)
        self.model = self._validate_model(model)
        self.language = self.validate_language_code(language)  # Используем ValidationMixin
        self.response_format = self._determine_response_format(response_format)

        # Конфигурация параллельной обработки
        self.max_concurrent_chunks = DEFAULT_MAX_CONCURRENT_CHUNKS  # Максимум 3 части одновременно
        self.chunk_timeout = DEFAULT_CHUNK_TIMEOUT_MINUTES * 60  # 30 минут на часть

        # Статистика параллельной обработки
        self.parallel_stats = {
            "total_chunks_processed": 0,
            "concurrent_chunks_peak": 0,
            "total_parallel_time": 0.0,
            "chunks_failed": 0,
            "chunks_retried": 0
        }

        # Логируем выбранную модель
        model_info = self.SUPPORTED_MODELS[self.model]
        self.log_with_emoji("info", "🎯", f"Модель: {model_info['name']} ({model_info['description']})")

    # Удален _get_adaptive_timeout - используем RetryMixin.get_adaptive_timeout

    # Удалены _intelligent_wait_strategy и _log_retry_statistics - используем RetryMixin

    def _log_parallel_statistics(self):
        """Логирует статистику параллельной обработки для мониторинга производительности."""
        if self.parallel_stats["total_chunks_processed"] > 0:
            self.log_with_emoji("info", "📊",
                f"Параллельная обработка: "
                f"частей={self.parallel_stats['total_chunks_processed']}, "
                f"пик одновременных={self.parallel_stats['concurrent_chunks_peak']}, "
                f"время={self.parallel_stats['total_parallel_time']:.1f}с, "
                f"неудачных={self.parallel_stats['chunks_failed']}"
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

        self.start_operation("транскрипция")

        try:
            # Валидация файла через ValidationMixin
            max_size = self.SUPPORTED_MODELS[self.model]["max_file_size_mb"]
            self.validate_audio_file(wav_local, max_size_mb=max_size)

            file_size_mb = wav_local.stat().st_size / (1024 * 1024)  # MB
            model_info = self.SUPPORTED_MODELS[self.model]

            self.log_with_emoji("info", "🎵", f"Начинаю транскрипцию с {model_info['name']}: {wav_local.name} ({file_size_mb:.1f}MB)")

            # Проверяем, нужно ли разбивать файл
            if file_size_mb > max_size:
                result = self._transcribe_large_file(wav_local, prompt)
            else:
                result = self._transcribe_single_file(wav_local, prompt)

            self.end_operation("транскрипция", success=True)
            return result

        except Exception as e:
            self.end_operation("транскрипция", success=False)
            self.handle_error(e, "транскрипция", reraise=True)

    # Удален _validate_audio_file - используем ValidationMixin.validate_audio_file

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
            self.log_with_emoji("info", "✂️", f"Разбиваю файл {wav_local.name} на части по {chunk_duration_minutes} минут...")

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
                self.log_with_emoji("debug", "📄", f"Создана часть {i+1}: {chunk_path.name} ({chunk_size_mb:.1f}MB)")

            self.log_with_emoji("info", "✅", f"Файл разбит на {len(chunks)} частей")
            return chunks

        except Exception as e:
            self.handle_error(e, "разбиение файла", reraise=True)

    def _transcribe_single_file(self, wav_local: Path, prompt: str = "") -> List[Dict]:
        """Транскрибирует один файл с улучшенной retry логикой."""
        file_size_mb = wav_local.stat().st_size / (1024 * 1024)

        # Получаем адаптивный таймаут через RetryMixin
        adaptive_timeout = self.get_adaptive_timeout(file_size_mb)

        # Подготовка параметров запроса
        transcription_params = self._prepare_transcription_params(prompt)

        # Создаем функцию для retry
        def transcribe_func():
            return self._transcribe_with_rate_limit(wav_local, transcription_params, adaptive_timeout)

        # Выполняем с retry логикой через RetryMixin
        result = self.retry_with_backoff(
            transcribe_func,
            max_attempts=8,
            base_delay=1.0,
            max_delay=120.0
        )

        self.log_with_emoji("info", "✅", f"Транскрипция завершена (файл: {file_size_mb:.1f}MB)")
        return result

    def _transcribe_with_rate_limit(self, wav_local: Path, transcription_params: Dict, timeout: float) -> List[Dict]:
        """Выполняет транскрипцию с rate limiting и обработкой ошибок."""

        def api_call():
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

        # Выполняем API вызов с rate limiting
        try:
            return self.with_rate_limit(api_call, operation_key="transcription", timeout=timeout)
        except openai.APIStatusError as e:
            if e.status_code == 429:  # Rate limit
                raise openai.RateLimitError(f"Rate limit: {e}") from e
            else:
                raise RuntimeError(f"Ошибка OpenAI API: {e}") from e

    def _process_chunk_parallel(self, chunk_info: Dict) -> Dict:
        """
        Обрабатывает одну часть файла в параллельном режиме.

        Args:
            chunk_info: Словарь с информацией о части файла:
                - path: Path к файлу части
                - index: Индекс части
                - offset: Временное смещение в секундах
                - prompt: Контекстная подсказка

        Returns:
            Словарь с результатами обработки:
                - index: Индекс части
                - segments: Список сегментов транскрипции
                - offset: Временное смещение
                - success: Флаг успешности
                - error: Описание ошибки (если есть)
                - processing_time: Время обработки
        """
        chunk_path = chunk_info["path"]
        chunk_index = chunk_info["index"]
        chunk_offset = chunk_info["offset"]
        prompt = chunk_info["prompt"]

        start_time = time.time()

        try:
            self.log_with_emoji("info", "🔄", f"Начинаю обработку части {chunk_index + 1}: {chunk_path.name}")

            # Транскрибируем часть
            chunk_segments = self._transcribe_single_file(chunk_path, prompt)

            # Корректируем временные метки с учетом смещения
            for segment in chunk_segments:
                segment['start'] += chunk_offset
                segment['end'] += chunk_offset
                # ID будет перенумерован позже при объединении

            processing_time = time.time() - start_time

            self.log_with_emoji("info", "✅", f"Часть {chunk_index + 1} обработана: {len(chunk_segments)} сегментов за {processing_time:.2f}с")

            return {
                "index": chunk_index,
                "segments": chunk_segments,
                "offset": chunk_offset,
                "success": True,
                "error": None,
                "processing_time": processing_time
            }

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Ошибка обработки части {chunk_index + 1}: {e}"

            self.log_with_emoji("error", "❌", error_msg)
            self.parallel_stats["chunks_failed"] += 1

            return {
                "index": chunk_index,
                "segments": [],
                "offset": chunk_offset,
                "success": False,
                "error": error_msg,
                "processing_time": processing_time
            }

    def _transcribe_large_file(self, wav_local: Path, prompt: str = "") -> List[Dict]:
        """Транскрибирует большой файл с параллельной обработкой частей."""
        self.log_with_emoji("info", "🚀", f"Обрабатываю большой файл с параллельной обработкой (макс {self.max_concurrent_chunks} одновременно)...")

        start_time = time.time()

        # Разбиваем файл на части
        chunks = self._split_audio_file(wav_local, chunk_duration_minutes=10)

        # Подготавливаем информацию о частях для параллельной обработки
        chunk_infos = []
        for i, chunk_path in enumerate(chunks):
            chunk_info = {
                "path": chunk_path,
                "index": i,
                "offset": i * 10 * 60,  # 10 минут = 600 секунд
                "prompt": prompt
            }
            chunk_infos.append(chunk_info)

        # Обрабатываем части параллельно
        results = self._process_chunks_parallel(chunk_infos)

        # Собираем результаты в правильном порядке
        all_segments = []
        total_processing_time = 0.0
        successful_chunks = 0

        # Сортируем результаты по индексу части
        results.sort(key=lambda x: x["index"])

        for result in results:
            if result["success"]:
                # Перенумеровываем ID сегментов
                for segment in result["segments"]:
                    segment['id'] = len(all_segments)
                    all_segments.append(segment)

                successful_chunks += 1
                total_processing_time += result["processing_time"]
                self.parallel_stats["total_chunks_processed"] += 1
            else:
                self.log_with_emoji("error", "❌", f"Часть {result['index'] + 1} не обработана: {result['error']}")

        # Удаляем временные файлы
        self._cleanup_chunk_files(chunks)

        # Обновляем статистику
        parallel_duration = time.time() - start_time
        self.parallel_stats["total_parallel_time"] += parallel_duration

        # Логируем результаты
        speedup_ratio = total_processing_time / parallel_duration if parallel_duration > 0 else 1.0

        self.log_with_emoji("info", "✅",
            f"Большой файл обработан: {len(all_segments)} сегментов из {successful_chunks}/{len(chunks)} частей"
        )
        self.log_with_emoji("info", "⚡",
            f"Параллельная обработка: {parallel_duration:.2f}с (ускорение в {speedup_ratio:.1f}x)"
        )

        self._log_parallel_statistics()

        if successful_chunks < len(chunks):
            failed_count = len(chunks) - successful_chunks
            self.log_with_emoji("warning", "⚠️", f"{failed_count} частей не удалось обработать")

        return all_segments

    def _process_chunks_parallel(self, chunk_infos: List[Dict]) -> List[Dict]:
        """
        Обрабатывает части файлов параллельно с контролем нагрузки.

        Args:
            chunk_infos: Список информации о частях файлов

        Returns:
            Список результатов обработки
        """
        results = []
        active_futures = 0

        self.log_with_emoji("info", "🔄", f"Запускаю параллельную обработку {len(chunk_infos)} частей (макс {self.max_concurrent_chunks} одновременно)")

        with ThreadPoolExecutor(max_workers=self.max_concurrent_chunks) as executor:
            # Отправляем задачи на выполнение
            future_to_chunk = {}

            for chunk_info in chunk_infos:
                future = executor.submit(self._process_chunk_parallel, chunk_info)
                future_to_chunk[future] = chunk_info
                active_futures += 1

                # Обновляем пик одновременных задач
                if active_futures > self.parallel_stats["concurrent_chunks_peak"]:
                    self.parallel_stats["concurrent_chunks_peak"] = active_futures

            # Собираем результаты по мере завершения
            try:
                for future in as_completed(future_to_chunk, timeout=self.chunk_timeout):
                    chunk_info = future_to_chunk[future]
                    active_futures -= 1

                    try:
                        result = future.result()
                        results.append(result)

                        if result["success"]:
                            self.log_with_emoji("debug", "✅", f"Часть {result['index'] + 1} завершена успешно")
                        else:
                            self.log_with_emoji("warning", "❌", f"Часть {result['index'] + 1} завершена с ошибкой")

                    except concurrent.futures.TimeoutError:
                        error_msg = f"Таймаут обработки части {chunk_info['index'] + 1}"
                        self.log_with_emoji("error", "⏰", error_msg)
                        self.parallel_stats["chunks_failed"] += 1

                        results.append({
                            "index": chunk_info["index"],
                            "segments": [],
                            "offset": chunk_info["offset"],
                            "success": False,
                            "error": error_msg,
                            "processing_time": self.chunk_timeout
                        })

                    except Exception as e:
                        error_msg = f"Исключение при обработке части {chunk_info['index'] + 1}: {e}"
                        self.log_with_emoji("error", "❌", error_msg)
                        self.parallel_stats["chunks_failed"] += 1

                        results.append({
                            "index": chunk_info["index"],
                            "segments": [],
                            "offset": chunk_info["offset"],
                            "success": False,
                            "error": error_msg,
                            "processing_time": 0.0
                        })

            except concurrent.futures.TimeoutError:
                # Глобальный таймаут as_completed - обрабатываем незавершенные задачи
                self.log_with_emoji("error", "⏰", f"Глобальный таймаут параллельной обработки ({self.chunk_timeout}с)")

                # Добавляем результаты для незавершенных задач
                for future, chunk_info in future_to_chunk.items():
                    if not future.done():
                        error_msg = f"Глобальный таймаут обработки части {chunk_info['index'] + 1}"
                        self.parallel_stats["chunks_failed"] += 1

                        results.append({
                            "index": chunk_info["index"],
                            "segments": [],
                            "offset": chunk_info["offset"],
                            "success": False,
                            "error": error_msg,
                            "processing_time": self.chunk_timeout
                        })

        self.log_with_emoji("info", "🏁", f"Параллельная обработка завершена: {len(results)} результатов")
        return results

    def _cleanup_chunk_files(self, chunk_paths: List[Path]) -> None:
        """Удаляет временные файлы частей."""
        for chunk_path in chunk_paths:
            try:
                if chunk_path.exists():
                    chunk_path.unlink()
                    self.log_with_emoji("debug", "🗑️", f"Удален временный файл: {chunk_path.name}")
            except Exception as e:
                self.log_with_emoji("warning", "⚠️", f"Не удалось удалить временный файл {chunk_path}: {e}")

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
                self.log_with_emoji("warning", "⚠️", f"Модель {self.model} не вернула сегментов в verbose_json")
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
            self.log_with_emoji("info", "📊", f"{model_info['name']}: обработано {len(processed_segments)} сегментов (verbose_json)")
            return processed_segments

        elif self.response_format == "json":
            # json возвращает только текст
            text = getattr(transcript, 'text', '')
            if not text:
                self.log_with_emoji("warning", "⚠️", f"Модель {self.model} не вернула текст в json")
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
            self.log_with_emoji("info", "📊", f"{model_info['name']}: создан сегмент из {len(text)} символов (json)")
            return [segment]

        else:
            # Для text, srt, vtt форматов возвращаем как есть
            # Эти форматы обычно используются для прямого вывода, а не для обработки
            text_content = str(transcript) if transcript else ""
            if not text_content:
                self.log_with_emoji("warning", "⚠️", f"Модель {self.model} не вернула контент в формате {self.response_format}")
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
            self.log_with_emoji("info", "📊", f"{model_info['name']}: обработан контент в формате {self.response_format}")
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
            self.log_with_emoji("info", "🌐", f"Установлен язык транскрипции: {language}")
        else:
            self.log_with_emoji("info", "🌐", "Язык транскрипции сброшен (автоопределение)")

    def estimate_cost(self, file_size_mb: float) -> str:
        """Оценивает примерную стоимость транскрипции."""
        cost_tier = self.SUPPORTED_MODELS[self.model]["cost_tier"]

        cost_estimates = {
            "low": f"~${file_size_mb * 0.006:.3f}",  # whisper-1: $0.006/min
            "medium": f"~${file_size_mb * 0.012:.3f}",  # gpt-4o-mini-transcribe: примерно в 2 раза дороже
            "high": f"~${file_size_mb * 0.024:.3f}"  # gpt-4o-transcribe: примерно в 4 раза дороже
        }

        return cost_estimates.get(cost_tier, "Неизвестно")
