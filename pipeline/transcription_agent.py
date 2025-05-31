# pipeline/transcription_agent.py

import logging
from openai import OpenAI
from pathlib import Path
from typing import List, Dict, Optional
import openai
import time

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

        # Логируем выбранную модель
        model_info = self.SUPPORTED_MODELS[self.model]
        self.logger.info(f"Инициализирован TranscriptionAgent с моделью: {model_info['name']} ({model_info['description']})")
        self.logger.info(f"Формат ответа: {self.response_format}")

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

            file_size = wav_local.stat().st_size / (1024 * 1024)  # MB
            model_info = self.SUPPORTED_MODELS[self.model]

            self.logger.info(f"Начинаю транскрипцию с {model_info['name']}: {wav_local} ({file_size:.1f}MB)")

            # Подготовка параметров запроса
            transcription_params = self._prepare_transcription_params(prompt)

            with open(wav_local, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    **transcription_params
                )

            # Обработка ответа в зависимости от модели
            segments = self._process_transcript_response(transcript)

            # Логируем метрики производительности
            duration = time.time() - start_time
            audio_duration = getattr(transcript, 'duration', None)
            processing_ratio = duration / audio_duration if audio_duration else None

            self.logger.info(f"Транскрипция завершена: {len(segments)} сегментов", extra={
                'model': self.model,
                'processing_time': f"{duration:.2f}s",
                'file_size_mb': f"{file_size:.1f}MB",
                'processing_ratio': f"{processing_ratio:.2f}x" if processing_ratio else "N/A",
                'segments_count': len(segments),
                'audio_duration': f"{audio_duration:.2f}s" if audio_duration else "N/A"
            })

            return segments

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

        file_size_mb = wav_local.stat().st_size / (1024 * 1024)
        max_size = self.SUPPORTED_MODELS[self.model]["max_file_size_mb"]

        if file_size_mb > max_size:
            raise ValueError(f"Размер файла ({file_size_mb:.1f}MB) превышает максимальный для модели {self.model} ({max_size}MB)")

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
