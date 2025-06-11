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

# Размеры и лимиты
DEFAULT_MAX_FILE_SIZE_MB = 300
OPENAI_MAX_FILE_SIZE_MB = 25
DEFAULT_CHUNK_TIMEOUT_MINUTES = 30
DEFAULT_MAX_CONCURRENT_CHUNKS = 3
DEFAULT_MAX_CONCURRENT_JOBS = 3

# Пороги качества
DEFAULT_MIN_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_MIN_SEGMENT_DURATION = 0.5
DEFAULT_MIN_OVERLAP_THRESHOLD = 0.1
DEFAULT_PER_SPEAKER_SECONDS = 30
DEFAULT_MAX_SILENCE_GAP = 5.0

# Retry параметры
DEFAULT_OPENAI_MAX_RETRIES = 3
DEFAULT_PYANNOTE_MAX_RETRIES = 40
DEFAULT_RETRY_MIN_WAIT = 1.0
DEFAULT_RETRY_MAX_WAIT = 30.0

# Таймауты (секунды)
DEFAULT_CONNECTION_TIMEOUT = 30
DEFAULT_OPENAI_READ_TIMEOUT = 120
DEFAULT_OPENAI_TOTAL_TIMEOUT = 300
DEFAULT_PYANNOTE_READ_TIMEOUT = 180
DEFAULT_PYANNOTE_TOTAL_TIMEOUT = 600

# Rate limiting
DEFAULT_OPENAI_RATE_LIMIT = 50
DEFAULT_PYANNOTE_RATE_LIMIT = 20
DEFAULT_REPLICATE_RATE_LIMIT = 100
DEFAULT_RATE_LIMIT_WINDOW = 60

# Логирование
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_ROTATION_MB = 10
DEFAULT_LOG_BACKUP_COUNT = 5

# Кэширование
DEFAULT_CACHE_TTL_HOURS = 24
DEFAULT_CACHE_MAX_SIZE_MB = 1000
DEFAULT_INTERMEDIATE_RETENTION_HOURS = 24

# Мониторинг
DEFAULT_METRICS_RETENTION_DAYS = 30
DEFAULT_CPU_THRESHOLD_PERCENT = 80
DEFAULT_MEMORY_THRESHOLD_PERCENT = 80
DEFAULT_DISK_FREE_THRESHOLD_GB = 1
DEFAULT_PROCESSING_TIME_THRESHOLD_MULTIPLIER = 2.0

# Webhook
DEFAULT_WEBHOOK_HOST = "0.0.0.0"
DEFAULT_WEBHOOK_PORT = 8000

# Docker health check
DEFAULT_HEALTH_CHECK_INTERVAL = 30
DEFAULT_HEALTH_CHECK_TIMEOUT = 10
DEFAULT_HEALTH_CHECK_RETRIES = 3
DEFAULT_HEALTH_CHECK_START_PERIOD = 40

# Транскрипция
DEFAULT_TRANSCRIPTION_MODEL = "whisper-1"
DEFAULT_TRANSCRIPTION_TEMPERATURE = 0.0
DEFAULT_TRANSCRIPTION_FALLBACK_MODEL = "whisper-1"

# Поддерживаемые модели транскрипции
SUPPORTED_TRANSCRIPTION_MODELS = {
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

# Replicate модель
REPLICATE_MODEL_NAME = "thomasmol/whisper-diarization:1495a9cddc83b2203b0d8d3516e38b80fd1572ebc4bc5700ac1da56a9b3ed886"

# Поддерживаемые языки Replicate
REPLICATE_SUPPORTED_LANGUAGES = {
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
