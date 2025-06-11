# 🛠️ Примеры реализации исправлений захардкоженных параметров

## 📁 Структура новых файлов

```
pipeline/
├── constants.py          # Новый файл с константами
├── settings.py          # Новый файл с настройками
├── config_profiles/     # Новая директория
│   ├── development.yaml
│   ├── production.yaml
│   └── testing.yaml
└── models/             # Новая директория
    └── supported_models.json
```

---

## 🔧 1. Создание pipeline/constants.py

```python
"""
Константы для speech pipeline.
Все магические числа и неизменяемые значения.
"""

# Аудио параметры
TARGET_SAMPLE_RATE = 16_000  # 16 kHz для Whisper & Pyannote
MIN_AUDIO_DURATION_SECONDS = 5  # Минимум 5 секунд для voiceprint
GOOD_VOICEPRINT_DURATION_SECONDS = 10  # Хорошее качество voiceprint

# API эндпоинты
API_ENDPOINTS = {
    "pyannote": {
        "diarize": "/diarize",
        "identify": "/identify", 
        "voiceprint": "/voiceprint",
        "media_input": "/media/input"
    },
    "openai": {
        "transcriptions": "/audio/transcriptions"
    }
}

# HTTP статус коды
HTTP_STATUS = {
    "OK": 200,
    "BAD_REQUEST": 400,
    "FORBIDDEN": 403,
    "INTERNAL_ERROR": 500
}

# Форматы файлов
SUPPORTED_AUDIO_FORMATS = [".mp3", ".wav", ".mp4", ".avi", ".mov", ".m4a", ".flac"]
SUPPORTED_MIME_TYPES = [
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mp4", "audio/x-m4a", "audio/flac",
    "video/mp4", "video/x-msvideo", "video/quicktime"
]

# Валидация
MIN_API_KEY_LENGTH = 10
VIRTUAL_PATH_PREFIX = "media://example/"

# Форматирование
TIME_FORMAT_PRECISION = 3  # Для логирования времени обработки
```

---

## ⚙️ 2. Создание pipeline/settings.py

```python
"""
Настройки для speech pipeline.
Все параметры, которые могут изменяться между окружениями.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

@dataclass
class APISettings:
    """Настройки API"""
    # URLs (можно переопределить через env)
    openai_url: str = field(default_factory=lambda: os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"))
    pyannote_url: str = field(default_factory=lambda: os.getenv("PYANNOTE_API_URL", "https://api.pyannote.ai/v1"))
    
    # Таймауты (секунды)
    openai_connection_timeout: int = field(default_factory=lambda: int(os.getenv("OPENAI_CONNECTION_TIMEOUT", "30")))
    openai_read_timeout: int = field(default_factory=lambda: int(os.getenv("OPENAI_READ_TIMEOUT", "120")))
    openai_total_timeout: int = field(default_factory=lambda: int(os.getenv("OPENAI_TOTAL_TIMEOUT", "300")))
    
    pyannote_connection_timeout: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_CONNECTION_TIMEOUT", "30")))
    pyannote_read_timeout: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_READ_TIMEOUT", "180")))
    pyannote_total_timeout: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_TOTAL_TIMEOUT", "600")))
    
    # Rate limiting
    openai_rate_limit: int = field(default_factory=lambda: int(os.getenv("OPENAI_RATE_LIMIT", "50")))
    pyannote_rate_limit: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_RATE_LIMIT", "20")))
    replicate_rate_limit: int = field(default_factory=lambda: int(os.getenv("REPLICATE_RATE_LIMIT", "100")))
    
    # Retry параметры
    openai_max_retries: int = field(default_factory=lambda: int(os.getenv("OPENAI_MAX_RETRIES", "3")))
    openai_retry_min_wait: float = field(default_factory=lambda: float(os.getenv("OPENAI_RETRY_MIN_WAIT", "1.0")))
    openai_retry_max_wait: float = field(default_factory=lambda: float(os.getenv("OPENAI_RETRY_MAX_WAIT", "30.0")))
    
    pyannote_max_retries: int = field(default_factory=lambda: int(os.getenv("PYANNOTE_MAX_RETRIES", "40")))
    pyannote_retry_min_wait: float = field(default_factory=lambda: float(os.getenv("PYANNOTE_RETRY_MIN_WAIT", "2.0")))
    pyannote_retry_max_wait: float = field(default_factory=lambda: float(os.getenv("PYANNOTE_RETRY_MAX_WAIT", "30.0")))

@dataclass
class ProcessingSettings:
    """Настройки обработки"""
    # Лимиты файлов
    max_file_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "300")))
    max_audio_duration_hours: int = field(default_factory=lambda: int(os.getenv("MAX_AUDIO_DURATION_HOURS", "4")))
    
    # Параллельная обработка
    max_concurrent_jobs: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_JOBS", "3")))
    max_concurrent_chunks: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_CHUNKS", "3")))
    chunk_timeout_minutes: int = field(default_factory=lambda: int(os.getenv("CHUNK_TIMEOUT_MINUTES", "30")))
    
    # Пороги качества
    min_confidence_threshold: float = field(default_factory=lambda: float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.7")))
    min_segment_duration: float = field(default_factory=lambda: float(os.getenv("MIN_SEGMENT_DURATION", "0.5")))
    min_overlap_threshold: float = field(default_factory=lambda: float(os.getenv("MIN_OVERLAP_THRESHOLD", "0.1")))
    
    # QC параметры
    per_speaker_seconds: int = field(default_factory=lambda: int(os.getenv("PER_SPEAKER_SECONDS", "30")))
    max_silence_gap: float = field(default_factory=lambda: float(os.getenv("MAX_SILENCE_GAP", "5.0")))

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
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    rotation_mb: int = field(default_factory=lambda: int(os.getenv("LOG_ROTATION_MB", "10")))
    backup_count: int = field(default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5")))
    format_type: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))
    separate_error_log: bool = field(default_factory=lambda: os.getenv("SEPARATE_ERROR_LOG", "true").lower() == "true")

@dataclass
class CacheSettings:
    """Настройки кэширования"""
    enabled: bool = field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true")
    ttl_hours: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_HOURS", "24")))
    max_size_mb: int = field(default_factory=lambda: int(os.getenv("CACHE_MAX_SIZE_MB", "1000")))
    intermediate_retention_hours: int = field(default_factory=lambda: int(os.getenv("INTERMEDIATE_RETENTION_HOURS", "24")))

@dataclass
class MonitoringSettings:
    """Настройки мониторинга"""
    enabled: bool = field(default_factory=lambda: os.getenv("MONITORING_ENABLED", "true").lower() == "true")
    metrics_retention_days: int = field(default_factory=lambda: int(os.getenv("METRICS_RETENTION_DAYS", "30")))
    
    # Пороги алертов
    cpu_threshold_percent: int = field(default_factory=lambda: int(os.getenv("CPU_THRESHOLD_PERCENT", "80")))
    memory_threshold_percent: int = field(default_factory=lambda: int(os.getenv("MEMORY_THRESHOLD_PERCENT", "80")))
    disk_free_threshold_gb: int = field(default_factory=lambda: int(os.getenv("DISK_FREE_THRESHOLD_GB", "1")))
    processing_time_threshold_multiplier: float = field(default_factory=lambda: float(os.getenv("PROCESSING_TIME_THRESHOLD_MULTIPLIER", "2.0")))

@dataclass
class WebhookSettings:
    """Настройки webhook сервера"""
    host: str = field(default_factory=lambda: os.getenv("WEBHOOK_SERVER_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("WEBHOOK_SERVER_PORT", "8000")))
    secret: Optional[str] = field(default_factory=lambda: os.getenv("PYANNOTEAI_WEBHOOK_SECRET"))

@dataclass
class TranscriptionSettings:
    """Настройки транскрипции"""
    default_model: str = field(default_factory=lambda: os.getenv("TRANSCRIPTION_MODEL", "whisper-1"))
    fallback_model: str = field(default_factory=lambda: os.getenv("TRANSCRIPTION_FALLBACK_MODEL", "whisper-1"))
    temperature: float = field(default_factory=lambda: float(os.getenv("TRANSCRIPTION_TEMPERATURE", "0.0")))
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
        # Реализация загрузки профилей из YAML файлов
        pass

# Глобальный экземпляр настроек
SETTINGS = Settings()
```

---

## 📝 3. Обновление .env.example

```bash
# =============================================================================
# API URLS (ОПЦИОНАЛЬНО - для кастомизации)
# =============================================================================

# OpenAI API URL (по умолчанию: https://api.openai.com/v1)
# OPENAI_API_URL=https://api.openai.com/v1

# Pyannote.ai API URL (по умолчанию: https://api.pyannote.ai/v1)  
# PYANNOTE_API_URL=https://api.pyannote.ai/v1

# =============================================================================
# ТАЙМАУТЫ И ЛИМИТЫ (ОПЦИОНАЛЬНО)
# =============================================================================

# OpenAI API таймауты (секунды)
# OPENAI_CONNECTION_TIMEOUT=30
# OPENAI_READ_TIMEOUT=120
# OPENAI_TOTAL_TIMEOUT=300

# Pyannote.ai API таймауты (секунды)
# PYANNOTE_CONNECTION_TIMEOUT=30
# PYANNOTE_READ_TIMEOUT=180
# PYANNOTE_TOTAL_TIMEOUT=600

# Rate limiting (запросов в минуту)
# OPENAI_RATE_LIMIT=50
# PYANNOTE_RATE_LIMIT=20
# REPLICATE_RATE_LIMIT=100

# =============================================================================
# ОБРАБОТКА ФАЙЛОВ (ОПЦИОНАЛЬНО)
# =============================================================================

# Максимальный размер файла (MB)
# MAX_FILE_SIZE_MB=300

# Максимальная длительность аудио (часы)
# MAX_AUDIO_DURATION_HOURS=4

# Параллельная обработка
# MAX_CONCURRENT_JOBS=3
# MAX_CONCURRENT_CHUNKS=3
# CHUNK_TIMEOUT_MINUTES=30

# =============================================================================
# ПУТИ К ДИРЕКТОРИЯМ (ОПЦИОНАЛЬНО)
# =============================================================================

# Базовые директории
# DATA_DIR=data
# CACHE_DIR=cache
# LOGS_DIR=logs
# VOICEPRINTS_DIR=voiceprints
# METRICS_DIR=logs/metrics
# INTERIM_DIR=data/interim

# =============================================================================
# КАЧЕСТВО И ПОРОГИ (ОПЦИОНАЛЬНО)
# =============================================================================

# Пороги уверенности и качества
# MIN_CONFIDENCE_THRESHOLD=0.7
# MIN_SEGMENT_DURATION=0.5
# MIN_OVERLAP_THRESHOLD=0.1

# QC параметры
# PER_SPEAKER_SECONDS=30
# MAX_SILENCE_GAP=5.0

# =============================================================================
# ЛОГИРОВАНИЕ (ОПЦИОНАЛЬНО)
# =============================================================================

# Уровень логирования (DEBUG, INFO, WARNING, ERROR)
# LOG_LEVEL=INFO

# Ротация логов
# LOG_ROTATION_MB=10
# LOG_BACKUP_COUNT=5
# LOG_FORMAT=json
# SEPARATE_ERROR_LOG=true

# =============================================================================
# КЭШИРОВАНИЕ (ОПЦИОНАЛЬНО)
# =============================================================================

# Настройки кэша
# CACHE_ENABLED=true
# CACHE_TTL_HOURS=24
# CACHE_MAX_SIZE_MB=1000
# INTERMEDIATE_RETENTION_HOURS=24

# =============================================================================
# МОНИТОРИНГ (ОПЦИОНАЛЬНО)
# =============================================================================

# Включение мониторинга
# MONITORING_ENABLED=true
# METRICS_RETENTION_DAYS=30

# Пороги алертов
# CPU_THRESHOLD_PERCENT=80
# MEMORY_THRESHOLD_PERCENT=80
# DISK_FREE_THRESHOLD_GB=1
# PROCESSING_TIME_THRESHOLD_MULTIPLIER=2.0

# =============================================================================
# ТРАНСКРИПЦИЯ (ОПЦИОНАЛЬНО)
# =============================================================================

# Модели транскрипции
# TRANSCRIPTION_MODEL=whisper-1
# TRANSCRIPTION_FALLBACK_MODEL=whisper-1
# TRANSCRIPTION_TEMPERATURE=0.0
# TRANSCRIPTION_LANGUAGE=auto
# ENABLE_COST_ESTIMATION=true
```

---

## 🔄 4. Пример обновления агента

```python
# pipeline/audio_agent.py (ПОСЛЕ исправления)

from .constants import TARGET_SAMPLE_RATE, VIRTUAL_PATH_PREFIX
from .settings import SETTINGS

class AudioLoaderAgent(BaseAgent, ValidationMixin, RateLimitMixin):
    """Агент для загрузки и конвертации аудио"""
    
    def __init__(self, remote_wav_url: Optional[str] = None, pyannote_api_key: Optional[str] = None):
        # Инициализация базовых классов
        BaseAgent.__init__(self, "AudioLoaderAgent")
        ValidationMixin.__init__(self)
        RateLimitMixin.__init__(self, "pyannote")
        
        self.remote_wav_url = remote_wav_url
        
        # Используем настройки вместо захардкоженных значений
        self.target_sample_rate = TARGET_SAMPLE_RATE
        self.upload_timeout = SETTINGS.api.pyannote_total_timeout
        
        # API ключ через базовый метод
        try:
            api_key = pyannote_api_key or self.get_api_key(
                "pyannote.ai",
                ["PYANNOTEAI_API_TOKEN", "PYANNOTE_API_KEY"]
            )
        except ValueError as e:
            self.handle_error(e, "инициализация API ключа")
        
        # Инициализируем медиа агент
        self.media_agent = PyannoteMediaAgent(api_key)
    
    def _convert_to_wav(self, input_path: Path) -> Path:
        """Конвертирует аудио в WAV формат"""
        # Используем константу вместо захардкоженного значения
        target_sr = self.target_sample_rate  # Вместо 16_000
        
        # Остальная логика без изменений...
```

---

## 📊 5. Профили конфигурации

### config_profiles/development.yaml
```yaml
# Профиль для разработки
api:
  timeouts:
    openai_total: 60      # Короткие таймауты для быстрой отладки
    pyannote_total: 120
  rate_limits:
    openai: 10           # Низкие лимиты для экономии API
    pyannote: 5

processing:
  max_file_size_mb: 50   # Маленькие файлы для тестирования
  max_concurrent_jobs: 1 # Последовательная обработка
  
logging:
  level: DEBUG           # Подробное логирование
  
cache:
  enabled: false         # Отключаем кэш для чистого тестирования
```

### config_profiles/production.yaml
```yaml
# Профиль для production
api:
  timeouts:
    openai_total: 300    # Длинные таймауты для стабильности
    pyannote_total: 600
  rate_limits:
    openai: 50           # Полные лимиты
    pyannote: 20

processing:
  max_file_size_mb: 300  # Полные лимиты
  max_concurrent_jobs: 3 # Параллельная обработка
  
logging:
  level: INFO            # Умеренное логирование
  
cache:
  enabled: true          # Включаем кэш для производительности
  ttl_hours: 24
```

---

*Примеры реализации созданы: 2025-01-15*
