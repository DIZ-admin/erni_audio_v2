"""
Replicate Agent для транскрипции и диаризации через thomasmol/whisper-diarization
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Optional
try:
    import replicate
    from replicate.exceptions import ReplicateError
except ImportError:
    replicate = None
    ReplicateError = Exception

from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin
from .constants import REPLICATE_MODEL_NAME, REPLICATE_SUPPORTED_LANGUAGES


class ReplicateAgent(BaseAgent, ValidationMixin):
    """
    Агент для выполнения транскрипции и диаризации через Replicate API
    с использованием модели thomasmol/whisper-diarization.
    """

    # Модель для использования (из констант)
    MODEL_NAME = REPLICATE_MODEL_NAME

    # Поддерживаемые языки (из констант)
    SUPPORTED_LANGUAGES = REPLICATE_SUPPORTED_LANGUAGES

    def __init__(self, api_token: str):
        """
        Инициализация Replicate агента.

        Args:
            api_token: Replicate API токен
        """
        # Инициализация базовых классов
        BaseAgent.__init__(self, name="ReplicateAgent")
        ValidationMixin.__init__(self)

        if replicate is None:
            raise ImportError("Библиотека replicate не установлена. Установите: pip install replicate")

        # Валидация API токена
        self.validate_replicate_token(api_token)

        self.client = replicate.Client(api_token=api_token)
        self.api_token = api_token

        self.log_with_emoji("info", "✅", "ReplicateAgent инициализирован")

    def validate_replicate_token(self, api_token: str) -> None:
        """
        Валидация API токена Replicate.

        Args:
            api_token: API токен для валидации

        Raises:
            ValueError: Если API токен невалиден
        """
        if not isinstance(api_token, str):
            raise ValueError(f"API токен должен быть строкой, получен {type(api_token)}")

        if not api_token or not api_token.strip():
            raise ValueError("Replicate API токен не может быть пустым")

        # Проверяем базовый формат (должен быть достаточно длинным)
        if len(api_token.strip()) < 10:
            raise ValueError("API токен слишком короткий")

    def validate_replicate_params(self,
                                audio_file: Path,
                                num_speakers: Optional[int] = None,
                                language: Optional[str] = None,
                                prompt: Optional[str] = None) -> List[str]:
        """
        Валидация параметров для Replicate модели.

        Args:
            audio_file: Путь к аудиофайлу
            num_speakers: Количество спикеров
            language: Код языка
            prompt: Подсказка для модели

        Returns:
            Список найденных проблем
        """
        issues = []

        # Валидация файла
        try:
            self.validate_audio_file(audio_file)
        except ValueError as e:
            issues.append(f"Проблема с аудиофайлом: {e}")

        # Валидация num_speakers
        if num_speakers is not None:
            if not isinstance(num_speakers, int):
                issues.append("num_speakers должно быть целым числом")
            elif num_speakers < 1:
                issues.append("num_speakers должно быть больше 0")
            elif num_speakers > 50:
                issues.append("num_speakers слишком большое (максимум 50)")

        # Валидация языка
        if language is not None:
            if not isinstance(language, str):
                issues.append("language должно быть строкой")
            elif language not in self.SUPPORTED_LANGUAGES:
                issues.append(f"Неподдерживаемый язык: {language}. Доступные: {list(self.SUPPORTED_LANGUAGES.keys())}")

        # Валидация prompt
        if prompt is not None:
            if not isinstance(prompt, str):
                issues.append("prompt должно быть строкой")
            elif len(prompt) > 1000:
                issues.append("prompt слишком длинный (максимум 1000 символов)")

        return issues

    def validate_replicate_audio_file(self, audio_file: Path) -> List[str]:
        """
        Специальная валидация аудиофайла для Replicate.

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

        # Проверка размера файла (≤500MB для Replicate)
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        if file_size_mb > 500:
            issues.append(f"Файл слишком большой: {file_size_mb:.1f}MB (максимум 500MB)")
        elif file_size_mb > 100:
            issues.append(f"Большой файл: {file_size_mb:.1f}MB, обработка может занять много времени")

        return issues

    def run(self,
            audio_file: Path,
            num_speakers: Optional[int] = None,
            language: Optional[str] = None,
            prompt: Optional[str] = None) -> List[Dict]:
        """
        Выполняет транскрипцию и диаризацию аудиофайла.

        Args:
            audio_file: Путь к аудиофайлу
            num_speakers: Количество спикеров (None для автоопределения)
            language: Код языка ('en', 'de', 'ru' и т.д., None для автоопределения)
            prompt: Подсказка с именами, акронимами и специальными терминами

        Returns:
            Список сегментов с транскрипцией и диаризацией
        """
        self.start_operation("обработка через Replicate")

        try:
            # Валидация параметров
            param_issues = self.validate_replicate_params(audio_file, num_speakers, language, prompt)
            if param_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с параметрами: {len(param_issues)}")
                for issue in param_issues[:3]:  # Показываем первые 3
                    self.log_with_emoji("warning", "   ", issue)

                # Если есть критические проблемы, прерываем
                if any("не найден" in issue or "слишком большой" in issue for issue in param_issues):
                    raise ValueError(f"Критические проблемы с параметрами: {param_issues[0]}")

            # Валидация аудиофайла для Replicate
            audio_issues = self.validate_replicate_audio_file(audio_file)
            if audio_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы с аудиофайлом: {len(audio_issues)}")
                for issue in audio_issues[:3]:
                    self.log_with_emoji("warning", "   ", issue)

            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.log_with_emoji("info", "🎵", f"Начинаю обработку через Replicate: {audio_file.name} ({file_size_mb:.1f}MB)")

            # Подготовка параметров
            input_params = self._prepare_input_params(
                audio_file, num_speakers, language, prompt
            )

            # Запуск модели
            self.log_with_emoji("info", "🚀", f"Запускаю модель {self.MODEL_NAME}...")
            output = self.client.run(self.MODEL_NAME, input=input_params)

            # Обработка результата
            segments = self._process_output(output)

            # Логирование результатов
            self.log_with_emoji("info", "✅", f"Replicate обработка завершена: {len(segments)} сегментов")

            self.end_operation("обработка через Replicate", success=True)
            return segments

        except ReplicateError as e:
            self.end_operation("обработка через Replicate", success=False)
            self.handle_error(e, "Replicate API", reraise=True)
        except Exception as e:
            self.end_operation("обработка через Replicate", success=False)
            self.handle_error(e, "обработка через Replicate", reraise=True)
    
    # Метод _validate_audio_file удален - используется validate_replicate_audio_file
    
    def _prepare_input_params(self,
                            audio_file: Path,
                            num_speakers: Optional[int],
                            language: Optional[str],
                            prompt: Optional[str]) -> Dict:
        """Подготовка параметров для Replicate API."""

        # Основные параметры - используем file handle для локального файла
        params = {
            "file": open(audio_file, "rb"),
            "file_url": "",  # Пустой, так как используем локальный файл
        }

        # Добавляем опциональные параметры
        if num_speakers is not None:
            if 1 <= num_speakers <= 50:
                params["num_speakers"] = num_speakers
                self.log_with_emoji("info", "👥", f"Установлено количество спикеров: {num_speakers}")
            else:
                self.log_with_emoji("warning", "⚠️", f"Некорректное количество спикеров: {num_speakers}, игнорируем")

        if language and language != "auto":
            if language in self.SUPPORTED_LANGUAGES:
                params["language"] = language
                self.log_with_emoji("info", "🌍", f"Установлен язык: {self.SUPPORTED_LANGUAGES[language]} ({language})")
            else:
                self.log_with_emoji("warning", "⚠️", f"Неподдерживаемый язык: {language}, используем автоопределение")

        if prompt:
            params["prompt"] = prompt
            self.log_with_emoji("info", "💡", f"Добавлена подсказка: {prompt[:50]}...")

        return params
    
    def _process_output(self, output) -> List[Dict]:
        """Обработка вывода Replicate API."""

        # Replicate может возвращать разные форматы
        if isinstance(output, dict):
            segments = output.get('segments', [])
        elif hasattr(output, 'segments'):
            segments = output.segments
        elif isinstance(output, list):
            segments = output
        else:
            self.log_with_emoji("error", "❌", f"Неожиданный формат ответа: {type(output)}")
            raise ValueError("Некорректный ответ от Replicate API")

        if not segments:
            self.log_with_emoji("warning", "⚠️", "Replicate не вернул сегментов")
            return []
        
        # Конвертируем в наш стандартный формат
        processed_segments = []
        
        for segment in segments:
            # Replicate возвращает сегменты в формате:
            # {
            #   "start": float,
            #   "end": float, 
            #   "text": str,
            #   "speaker": str,
            #   "words": [...],
            #   "avg_logprob": float
            # }
            
            processed_segment = {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": segment.get("text", "").strip(),
                "speaker": segment.get("speaker", "UNKNOWN"),
                "avg_logprob": segment.get("avg_logprob", 0.0),
                "words": segment.get("words", [])
            }
            
            processed_segments.append(processed_segment)
        
        self.log_with_emoji("info", "📊", f"Обработано {len(processed_segments)} сегментов")

        # Логируем статистику спикеров
        speakers = set(seg["speaker"] for seg in processed_segments)
        self.log_with_emoji("info", "👥", f"Обнаружено спикеров: {len(speakers)} ({', '.join(sorted(speakers))})")
        
        return processed_segments
    
    def estimate_cost(self, audio_file: Path) -> Dict[str, any]:
        """
        Оценка стоимости обработки файла.

        Args:
            audio_file: Путь к аудиофайлу

        Returns:
            Словарь с оценкой стоимости
        """
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Базовая стоимость Replicate: ~$0.0077 за запуск
        # Но может зависеть от размера файла и времени обработки
        base_cost = 0.0077
        
        # Примерная оценка на основе размера файла
        # (это приблизительно, реальная стоимость может отличаться)
        if file_size_mb <= 25:
            estimated_cost = base_cost
        else:
            # Для больших файлов стоимость может расти
            estimated_cost = base_cost * (file_size_mb / 25)
        
        return {
            "estimated_cost_usd": round(estimated_cost, 4),
            "base_cost_usd": base_cost,
            "file_size_mb": round(file_size_mb, 1),
            "note": "Приблизительная оценка, реальная стоимость может отличаться"
        }
