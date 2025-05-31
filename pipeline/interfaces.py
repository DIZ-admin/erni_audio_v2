"""
Интерфейсы и абстракции для агентов пайплайна.
Следование принципам SOLID и чистой архитектуры.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ProcessingStatus(Enum):
    """Статусы обработки"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingMetrics:
    """Метрики производительности"""
    start_time: float
    end_time: Optional[float] = None
    processing_time: Optional[float] = None
    input_size_mb: Optional[float] = None
    output_segments: Optional[int] = None
    processing_ratio: Optional[float] = None  # время_обработки / длительность_аудио
    
    def finalize(self, end_time: float):
        """Завершает сбор метрик"""
        self.end_time = end_time
        self.processing_time = end_time - self.start_time


@dataclass
class AudioSegment:
    """Сегмент аудио с метаданными"""
    start: float
    end: float
    text: Optional[str] = None
    speaker: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class AudioLoaderInterface(ABC):
    """Интерфейс для загрузки и конвертации аудио"""
    
    @abstractmethod
    def load_and_convert(self, input_path: str) -> tuple[Path, str]:
        """
        Загружает и конвертирует аудио файл.
        
        Args:
            input_path: Путь к файлу или URL
            
        Returns:
            Tuple[локальный_путь, удаленный_url]
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_path: str) -> bool:
        """Валидирует входной файл"""
        pass


class DiarizationInterface(ABC):
    """Интерфейс для диаризации"""
    
    @abstractmethod
    def diarize(self, audio_url: str) -> List[AudioSegment]:
        """
        Выполняет диаризацию аудио.
        
        Args:
            audio_url: URL аудио файла
            
        Returns:
            Список сегментов с информацией о говорящих
        """
        pass
    
    @abstractmethod
    def identify_speakers(self, audio_url: str, voiceprint_ids: List[str]) -> List[AudioSegment]:
        """
        Идентифицирует говорящих по голосовым отпечаткам.
        
        Args:
            audio_url: URL аудио файла
            voiceprint_ids: Список ID голосовых отпечатков
            
        Returns:
            Список сегментов с идентифицированными говорящими
        """
        pass


class TranscriptionInterface(ABC):
    """Интерфейс для транскрипции"""
    
    @abstractmethod
    def transcribe(self, audio_file: Path, prompt: str = "") -> List[AudioSegment]:
        """
        Выполняет транскрипцию аудио.
        
        Args:
            audio_file: Локальный аудио файл
            prompt: Опциональный промпт для улучшения качества
            
        Returns:
            Список сегментов с транскрипцией
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Возвращает список поддерживаемых языков"""
        pass


class MergeInterface(ABC):
    """Интерфейс для объединения результатов"""
    
    @abstractmethod
    def merge_segments(self, 
                      diarization: List[AudioSegment], 
                      transcription: List[AudioSegment]) -> List[AudioSegment]:
        """
        Объединяет результаты диаризации и транскрипции.
        
        Args:
            diarization: Сегменты с информацией о говорящих
            transcription: Сегменты с транскрипцией
            
        Returns:
            Объединенные сегменты
        """
        pass
    
    @abstractmethod
    def calculate_overlap(self, seg1: AudioSegment, seg2: AudioSegment) -> float:
        """Вычисляет пересечение между сегментами"""
        pass


class ExportInterface(ABC):
    """Интерфейс для экспорта результатов"""
    
    @abstractmethod
    def export(self, segments: List[AudioSegment], output_path: Path) -> None:
        """
        Экспортирует сегменты в файл.
        
        Args:
            segments: Список сегментов для экспорта
            output_path: Путь к выходному файлу
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Возвращает список поддерживаемых форматов"""
        pass


class QualityControlInterface(ABC):
    """Интерфейс для контроля качества"""
    
    @abstractmethod
    def validate_segments(self, segments: List[AudioSegment]) -> bool:
        """Валидирует качество сегментов"""
        pass
    
    @abstractmethod
    def extract_voiceprints(self, 
                           audio_file: Path, 
                           segments: List[AudioSegment],
                           output_dir: Path) -> Dict[str, str]:
        """
        Извлекает голосовые отпечатки.
        
        Returns:
            Словарь {speaker_id: voiceprint_path}
        """
        pass


class MetricsCollectorInterface(ABC):
    """Интерфейс для сбора метрик"""
    
    @abstractmethod
    def start_processing(self, operation: str) -> str:
        """Начинает отслеживание операции, возвращает ID"""
        pass
    
    @abstractmethod
    def end_processing(self, operation_id: str, success: bool = True) -> ProcessingMetrics:
        """Завершает отслеживание операции"""
        pass
    
    @abstractmethod
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Возвращает сводку метрик"""
        pass


class ConfigurationInterface(ABC):
    """Интерфейс для конфигурации"""
    
    @abstractmethod
    def get_api_key(self, provider: str) -> str:
        """Получает API ключ для провайдера"""
        pass
    
    @abstractmethod
    def get_timeout(self, operation: str) -> int:
        """Получает таймаут для операции"""
        pass
    
    @abstractmethod
    def get_retry_config(self, operation: str) -> Dict[str, Any]:
        """Получает конфигурацию повторов"""
        pass


class CacheInterface(ABC):
    """Интерфейс для кэширования"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохраняет значение в кэш"""
        pass
    
    @abstractmethod
    def invalidate(self, pattern: str) -> None:
        """Инвалидирует кэш по паттерну"""
        pass


class PipelineInterface(ABC):
    """Основной интерфейс пайплайна"""
    
    @abstractmethod
    def process(self, 
               input_path: str,
               output_format: str = "srt",
               use_identification: bool = False,
               voiceprint_mapping: Optional[Dict[str, str]] = None) -> Path:
        """
        Выполняет полную обработку аудио.
        
        Args:
            input_path: Путь к входному файлу
            output_format: Формат вывода (srt, json, ass)
            use_identification: Использовать идентификацию говорящих
            voiceprint_mapping: Маппинг голосовых отпечатков
            
        Returns:
            Путь к результирующему файлу
        """
        pass
    
    @abstractmethod
    def get_processing_status(self, job_id: str) -> ProcessingStatus:
        """Получает статус обработки"""
        pass
    
    @abstractmethod
    def cancel_processing(self, job_id: str) -> bool:
        """Отменяет обработку"""
        pass


# Фабрики для создания провайдеров

class ProviderFactory(ABC):
    """Базовая фабрика провайдеров"""
    
    @abstractmethod
    def create_transcription_provider(self, provider_type: str) -> TranscriptionInterface:
        """Создает провайдера транскрипции"""
        pass
    
    @abstractmethod
    def create_diarization_provider(self, provider_type: str) -> DiarizationInterface:
        """Создает провайдера диаризации"""
        pass


# Исключения

class PipelineError(Exception):
    """Базовое исключение пайплайна"""
    pass


class ValidationError(PipelineError):
    """Ошибка валидации"""
    pass


class ProcessingError(PipelineError):
    """Ошибка обработки"""
    pass


class ConfigurationError(PipelineError):
    """Ошибка конфигурации"""
    pass


class ProviderError(PipelineError):
    """Ошибка провайдера"""
    pass
