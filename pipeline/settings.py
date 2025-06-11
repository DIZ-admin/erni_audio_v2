"""
Настройки для speech pipeline.
Все параметры, которые могут изменяться между окружениями.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
try:
    from .constants import *
except ImportError:
    # Fallback для прямого импорта
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '.'
    sys.path.append(current_dir)
    from constants import *


@dataclass
class APISettings:
    """Настройки API"""
    # URLs (можно переопределить через env)
    openai_url: str = field(default_factory=lambda: os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"))
    pyannote_url: str = field(default_factory=lambda: os.getenv("PYANNOTE_API_URL", "https://api.pyannote.ai/v1"))
    
    # Таймауты (секунды)
    openai_connection_timeout: int = field(default_factory=lambda: int(os.getenv("OPENAI_CONNECTION_TIMEOUT", str(DEFAULT_CONNECTION_TIMEOUT))))
    openai_read_timeout: int = field(default_factory=lambda: int(os.getenv("OPENAI_READ_TIMEOUT", str(DEFAULT_OPENAI_READ_TIMEOUT))))
    openai_total_timeout: int = field(default_factory=lambda: int(os.getenv("OPENAI_TOTAL_TIMEOUT", str(DEFAULT_OPENAI_TOTAL_TIMEOUT))))
    
    pyannote_connection_timeout: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_CONNECTION_TIMEOUT", str(DEFAULT_CONNECTION_TIMEOUT))))
    pyannote_read_timeout: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_READ_TIMEOUT", str(DEFAULT_PYANNOTE_READ_TIMEOUT))))
    pyannote_total_timeout: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_TOTAL_TIMEOUT", str(DEFAULT_PYANNOTE_TOTAL_TIMEOUT))))
    
    # Rate limiting
    openai_rate_limit: int = field(default_factory=lambda: int(os.getenv("OPENAI_RATE_LIMIT", str(DEFAULT_OPENAI_RATE_LIMIT))))
    pyannote_rate_limit: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_RATE_LIMIT", str(DEFAULT_PYANNOTE_RATE_LIMIT))))
    replicate_rate_limit: int = field(default_factory=lambda: int(os.getenv("REPLICATE_RATE_LIMIT", str(DEFAULT_REPLICATE_RATE_LIMIT))))
    rate_limit_window: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW", str(DEFAULT_RATE_LIMIT_WINDOW))))
    
    # Retry параметры
    openai_max_retries: int = field(default_factory=lambda: int(os.getenv("OPENAI_MAX_RETRIES", str(DEFAULT_OPENAI_MAX_RETRIES))))
    openai_retry_min_wait: float = field(default_factory=lambda: float(os.getenv("OPENAI_RETRY_MIN_WAIT", str(DEFAULT_RETRY_MIN_WAIT))))
    openai_retry_max_wait: float = field(default_factory=lambda: float(os.getenv("OPENAI_RETRY_MAX_WAIT", str(DEFAULT_RETRY_MAX_WAIT))))
    
    pyannote_max_retries: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_MAX_RETRIES", str(DEFAULT_PYANNOTE_MAX_RETRIES))))
    pyannote_retry_min_wait: float = field(default_factory=lambda: float(os.getenv("PYANNOTE_RETRY_MIN_WAIT", "2.0")))
    pyannote_retry_max_wait: float = field(default_factory=lambda: float(os.getenv("PYANNOTE_RETRY_MAX_WAIT", str(DEFAULT_RETRY_MAX_WAIT))))


@dataclass
class ProcessingSettings:
    """Настройки обработки"""
    # Лимиты файлов
    max_file_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", str(DEFAULT_MAX_FILE_SIZE_MB))))
    max_audio_duration_hours: int = field(default_factory=lambda: int(os.getenv("MAX_AUDIO_DURATION_HOURS", "4")))
    
    # Параллельная обработка
    max_concurrent_jobs: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_JOBS", str(DEFAULT_MAX_CONCURRENT_JOBS))))
    max_concurrent_chunks: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_CHUNKS", str(DEFAULT_MAX_CONCURRENT_CHUNKS))))
    chunk_timeout_minutes: int = field(default_factory=lambda: int(os.getenv("CHUNK_TIMEOUT_MINUTES", str(DEFAULT_CHUNK_TIMEOUT_MINUTES))))
    
    # Пороги качества
    min_confidence_threshold: float = field(default_factory=lambda: float(os.getenv("MIN_CONFIDENCE_THRESHOLD", str(DEFAULT_MIN_CONFIDENCE_THRESHOLD))))
    min_segment_duration: float = field(default_factory=lambda: float(os.getenv("MIN_SEGMENT_DURATION", str(DEFAULT_MIN_SEGMENT_DURATION))))
    min_overlap_threshold: float = field(default_factory=lambda: float(os.getenv("MIN_OVERLAP_THRESHOLD", str(DEFAULT_MIN_OVERLAP_THRESHOLD))))
    
    # QC параметры
    per_speaker_seconds: int = field(default_factory=lambda: int(os.getenv("PER_SPEAKER_SECONDS", str(DEFAULT_PER_SPEAKER_SECONDS))))
    max_silence_gap: float = field(default_factory=lambda: float(os.getenv("MAX_SILENCE_GAP", str(DEFAULT_MAX_SILENCE_GAP))))


@dataclass
class PathSettings:
    """Настройки путей"""
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("CACHE_DIR", "cache")))
    logs_dir: Path = field(default_factory=lambda: Path(os.getenv("LOGS_DIR", "logs")))
    voiceprints_dir: Path = field(default_factory=lambda: Path(os.getenv("VOICEPRINTS_DIR", "voiceprints")))
    metrics_dir: Path = field(default_factory=lambda: Path(os.getenv("METRICS_DIR", "logs/metrics")))
    interim_dir: Path = field(default_factory=lambda: Path(os.getenv("INTERIM_DIR", "data/interim")))


@dataclass
class LoggingSettings:
    """Настройки логирования"""
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL))
    rotation_mb: int = field(default_factory=lambda: int(os.getenv("LOG_ROTATION_MB", str(DEFAULT_LOG_ROTATION_MB))))
    backup_count: int = field(default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", str(DEFAULT_LOG_BACKUP_COUNT))))
    format_type: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))
    separate_error_log: bool = field(default_factory=lambda: os.getenv("SEPARATE_ERROR_LOG", "true").lower() == "true")


@dataclass
class CacheSettings:
    """Настройки кэширования"""
    enabled: bool = field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true")
    ttl_hours: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_HOURS", str(DEFAULT_CACHE_TTL_HOURS))))
    max_size_mb: int = field(default_factory=lambda: int(os.getenv("CACHE_MAX_SIZE_MB", str(DEFAULT_CACHE_MAX_SIZE_MB))))
    intermediate_retention_hours: int = field(default_factory=lambda: int(os.getenv("INTERMEDIATE_RETENTION_HOURS", str(DEFAULT_INTERMEDIATE_RETENTION_HOURS))))


@dataclass
class MonitoringSettings:
    """Настройки мониторинга"""
    enabled: bool = field(default_factory=lambda: os.getenv("MONITORING_ENABLED", "true").lower() == "true")
    metrics_retention_days: int = field(default_factory=lambda: int(os.getenv("METRICS_RETENTION_DAYS", str(DEFAULT_METRICS_RETENTION_DAYS))))
    
    # Пороги алертов
    cpu_threshold_percent: int = field(default_factory=lambda: int(os.getenv("CPU_THRESHOLD_PERCENT", str(DEFAULT_CPU_THRESHOLD_PERCENT))))
    memory_threshold_percent: int = field(default_factory=lambda: int(os.getenv("MEMORY_THRESHOLD_PERCENT", str(DEFAULT_MEMORY_THRESHOLD_PERCENT))))
    disk_free_threshold_gb: int = field(default_factory=lambda: int(os.getenv("DISK_FREE_THRESHOLD_GB", str(DEFAULT_DISK_FREE_THRESHOLD_GB))))
    processing_time_threshold_multiplier: float = field(default_factory=lambda: float(os.getenv("PROCESSING_TIME_THRESHOLD_MULTIPLIER", str(DEFAULT_PROCESSING_TIME_THRESHOLD_MULTIPLIER))))


@dataclass
class WebhookSettings:
    """Настройки webhook сервера"""
    host: str = field(default_factory=lambda: os.getenv("WEBHOOK_SERVER_HOST", DEFAULT_WEBHOOK_HOST))
    port: int = field(default_factory=lambda: int(os.getenv("WEBHOOK_SERVER_PORT", str(DEFAULT_WEBHOOK_PORT))))
    secret: Optional[str] = field(default_factory=lambda: os.getenv("PYANNOTEAI_WEBHOOK_SECRET"))


@dataclass
class TranscriptionSettings:
    """Настройки транскрипции"""
    default_model: str = field(default_factory=lambda: os.getenv("TRANSCRIPTION_MODEL", DEFAULT_TRANSCRIPTION_MODEL))
    fallback_model: str = field(default_factory=lambda: os.getenv("TRANSCRIPTION_FALLBACK_MODEL", DEFAULT_TRANSCRIPTION_FALLBACK_MODEL))
    temperature: float = field(default_factory=lambda: float(os.getenv("TRANSCRIPTION_TEMPERATURE", str(DEFAULT_TRANSCRIPTION_TEMPERATURE))))
    language: Optional[str] = field(default_factory=lambda: os.getenv("TRANSCRIPTION_LANGUAGE"))
    enable_cost_estimation: bool = field(default_factory=lambda: os.getenv("ENABLE_COST_ESTIMATION", "true").lower() == "true")


# Глобальный объект настроек
class Settings:
    """Центральный класс для всех настроек"""
    
    def __init__(self):
        self.api = APISettings()
        self.processing = ProcessingSettings()
        self.paths = PathSettings()
        self.logging = LoggingSettings()
        self.cache = CacheSettings()
        self.monitoring = MonitoringSettings()
        self.webhook = WebhookSettings()
        self.transcription = TranscriptionSettings()
        
        # Создаём необходимые директории
        self._create_directories()
    
    def _create_directories(self):
        """Создаёт необходимые директории"""
        for path in [self.paths.data_dir, self.paths.cache_dir, 
                    self.paths.logs_dir, self.paths.voiceprints_dir,
                    self.paths.metrics_dir, self.paths.interim_dir]:
            path.mkdir(parents=True, exist_ok=True)
    
    def load_profile(self, profile_name: str):
        """Загружает профиль конфигурации"""
        # TODO: Реализация загрузки профилей из YAML файлов
        pass
    
    def validate(self):
        """Валидирует настройки"""
        errors = []
        
        # Проверяем лимиты
        if self.processing.max_file_size_mb <= 0:
            errors.append("MAX_FILE_SIZE_MB должен быть больше 0")
        
        if self.processing.max_concurrent_jobs <= 0:
            errors.append("MAX_CONCURRENT_JOBS должен быть больше 0")
        
        # Проверяем таймауты
        if self.api.openai_total_timeout <= 0:
            errors.append("OPENAI_TOTAL_TIMEOUT должен быть больше 0")
        
        if self.api.pyannote_total_timeout <= 0:
            errors.append("PYANNOTE_TOTAL_TIMEOUT должен быть больше 0")
        
        # Проверяем пороги
        if not 0 <= self.processing.min_confidence_threshold <= 1:
            errors.append("MIN_CONFIDENCE_THRESHOLD должен быть между 0 и 1")
        
        if self.processing.min_segment_duration <= 0:
            errors.append("MIN_SEGMENT_DURATION должен быть больше 0")
        
        if errors:
            raise ValueError(f"Ошибки конфигурации: {'; '.join(errors)}")


# Глобальный экземпляр настроек
SETTINGS = Settings()
