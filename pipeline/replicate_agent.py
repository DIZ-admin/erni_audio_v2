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


class ReplicateAgent:
    """
    Агент для выполнения транскрипции и диаризации через Replicate API
    с использованием модели thomasmol/whisper-diarization.
    """
    
    # Модель для использования (с конкретной версией)
    MODEL_NAME = "thomasmol/whisper-diarization:1495a9cddc83b2203b0d8d3516e38b80fd1572ebc4bc5700ac1da56a9b3ed886"
    
    # Поддерживаемые языки (основные)
    SUPPORTED_LANGUAGES = {
        "auto": "Автоопределение",
        "en": "English",
        "de": "Deutsch", 
        "fr": "Français",
        "es": "Español",
        "it": "Italiano",
        "pt": "Português",
        "ru": "Русский",
        "zh": "中文",
        "ja": "日本語",
        "ko": "한국어"
    }
    
    def __init__(self, api_token: str):
        """
        Инициализация Replicate агента.

        Args:
            api_token: Replicate API токен
        """
        if replicate is None:
            raise ImportError("Библиотека replicate не установлена. Установите: pip install replicate")

        if not api_token:
            raise ValueError("Replicate API токен обязателен")

        self.client = replicate.Client(api_token=api_token)
        self.logger = logging.getLogger(__name__)

        self.logger.info("✅ ReplicateAgent инициализирован")
    
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
        start_time = time.time()
        
        try:
            # Валидация файла
            self._validate_audio_file(audio_file)
            
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            self.logger.info(f"🎵 Начинаю обработку через Replicate: {audio_file.name} ({file_size_mb:.1f}MB)")
            
            # Подготовка параметров
            input_params = self._prepare_input_params(
                audio_file, num_speakers, language, prompt
            )
            
            # Запуск модели
            self.logger.info(f"🚀 Запускаю модель {self.MODEL_NAME}...")
            output = self.client.run(self.MODEL_NAME, input=input_params)
            
            # Обработка результата
            segments = self._process_output(output)
            
            # Логирование результатов
            duration = time.time() - start_time
            self.logger.info(f"✅ Replicate обработка завершена: {len(segments)} сегментов за {duration:.2f}с")
            
            return segments
            
        except ReplicateError as e:
            self.logger.error(f"❌ Ошибка Replicate API: {e}")
            raise RuntimeError(f"Ошибка Replicate API: {e}") from e
        except Exception as e:
            self.logger.error(f"❌ Неожиданная ошибка: {e}")
            raise RuntimeError(f"Ошибка обработки: {e}") from e
    
    def _validate_audio_file(self, audio_file: Path) -> None:
        """Валидация аудиофайла."""
        if not audio_file.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_file}")
        
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Replicate может иметь свои лимиты, но пока проверим разумный размер
        if file_size_mb > 500:  # 500MB лимит для безопасности
            self.logger.warning(f"⚠️ Большой файл: {file_size_mb:.1f}MB")
    
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
                self.logger.info(f"👥 Установлено количество спикеров: {num_speakers}")
            else:
                self.logger.warning(f"⚠️ Некорректное количество спикеров: {num_speakers}, игнорируем")

        if language and language != "auto":
            if language in self.SUPPORTED_LANGUAGES:
                params["language"] = language
                self.logger.info(f"🌍 Установлен язык: {self.SUPPORTED_LANGUAGES[language]} ({language})")
            else:
                self.logger.warning(f"⚠️ Неподдерживаемый язык: {language}, используем автоопределение")

        if prompt:
            params["prompt"] = prompt
            self.logger.info(f"💡 Добавлена подсказка: {prompt[:50]}...")

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
            self.logger.error(f"Неожиданный формат ответа: {type(output)}")
            raise ValueError("Некорректный ответ от Replicate API")

        if not segments:
            self.logger.warning("⚠️ Replicate не вернул сегментов")
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
        
        self.logger.info(f"📊 Обработано {len(processed_segments)} сегментов")
        
        # Логируем статистику спикеров
        speakers = set(seg["speaker"] for seg in processed_segments)
        self.logger.info(f"👥 Обнаружено спикеров: {len(speakers)} ({', '.join(sorted(speakers))})")
        
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
