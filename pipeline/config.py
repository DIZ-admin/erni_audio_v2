"""
Конфигурационный менеджер для speech pipeline.
Централизованное управление настройками, API ключами и параметрами.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

from .interfaces import ConfigurationInterface, ConfigurationError


@dataclass
class RetryConfig:
    """Конфигурация повторов"""
    max_attempts: int = 3
    min_wait: float = 1.0
    max_wait: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class TimeoutConfig:
    """Конфигурация таймаутов"""
    connection: int = 30
    read: int = 60
    total: int = 300


@dataclass
class APIConfig:
    """Конфигурация API"""
    base_url: str
    timeout: TimeoutConfig
    retry: RetryConfig
    rate_limit_per_minute: int = 60


@dataclass
class TranscriptionConfig:
    """Конфигурация транскрипции"""
    model: str = "whisper-1"  # whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe
    language: Optional[str] = None  # Автоопределение языка по умолчанию
    prompt: str = ""  # Контекстная подсказка
    temperature: float = 0.0  # Температура для генерации
    enable_cost_estimation: bool = True  # Показывать оценку стоимости
    fallback_model: str = "whisper-1"  # Резервная модель при ошибках


@dataclass
class PipelineConfig:
    """Основная конфигурация пайплайна"""
    # Пути
    data_dir: Path = Path("data")
    cache_dir: Path = Path("cache")
    logs_dir: Path = Path("logs")
    voiceprints_dir: Path = Path("voiceprints")

    # Лимиты
    max_file_size_mb: int = 100
    max_audio_duration_hours: int = 4
    max_concurrent_jobs: int = 3

    # Качество
    min_confidence_threshold: float = 0.7
    min_segment_duration: float = 0.5

    # Кэширование
    cache_enabled: bool = True
    cache_ttl_hours: int = 24

    # Логирование
    log_level: str = "INFO"
    log_rotation_mb: int = 10
    log_backup_count: int = 5

    # Транскрипция
    transcription: TranscriptionConfig = None

    def __post_init__(self):
        """Инициализация после создания объекта"""
        if self.transcription is None:
            self.transcription = TranscriptionConfig()


class ConfigurationManager(ConfigurationInterface):
    """Менеджер конфигурации"""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file or Path("config/pipeline.json")
        self._config = self._load_config()
        self._api_configs = self._load_api_configs()
        self._validate_config()
    
    def _load_config(self) -> PipelineConfig:
        """Загружает основную конфигурацию"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                return PipelineConfig(**config_data)
            except Exception as e:
                self.logger.warning(f"Ошибка загрузки конфигурации: {e}. Используем значения по умолчанию.")
        
        return PipelineConfig()
    
    def _load_api_configs(self) -> Dict[str, APIConfig]:
        """Загружает конфигурации API"""
        configs = {}
        
        # OpenAI конфигурация
        configs["openai"] = APIConfig(
            base_url="https://api.openai.com/v1",
            timeout=TimeoutConfig(connection=30, read=120, total=300),
            retry=RetryConfig(max_attempts=3, min_wait=1.0, max_wait=30.0),
            rate_limit_per_minute=50
        )
        
        # Pyannote конфигурация
        configs["pyannote"] = APIConfig(
            base_url="https://api.pyannote.ai/v1",
            timeout=TimeoutConfig(connection=30, read=180, total=600),
            retry=RetryConfig(max_attempts=40, min_wait=2.0, max_wait=30.0),
            rate_limit_per_minute=20
        )
        
        return configs
    
    def _validate_config(self) -> None:
        """Валидирует конфигурацию"""
        # Проверяем API ключи
        required_keys = ["OPENAI_API_KEY", "PYANNOTE_API_KEY"]
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        
        if missing_keys:
            raise ConfigurationError(f"Отсутствуют обязательные переменные окружения: {missing_keys}")
        
        # Проверяем директории
        for dir_path in [self._config.data_dir, self._config.cache_dir, 
                        self._config.logs_dir, self._config.voiceprints_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Валидируем лимиты
        if self._config.max_file_size_mb <= 0:
            raise ConfigurationError("max_file_size_mb должен быть положительным")
        
        if self._config.max_audio_duration_hours <= 0:
            raise ConfigurationError("max_audio_duration_hours должен быть положительным")
    
    def get_api_key(self, provider: str) -> str:
        """Получает API ключ для провайдера"""
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "pyannote": "PYANNOTE_API_KEY"
        }
        
        env_var = key_mapping.get(provider.lower())
        if not env_var:
            raise ConfigurationError(f"Неизвестный провайдер: {provider}")
        
        api_key = os.getenv(env_var)
        if not api_key:
            raise ConfigurationError(f"Отсутствует API ключ для {provider}: {env_var}")
        
        # Базовая валидация ключа
        if len(api_key) < 10:
            raise ConfigurationError(f"Некорректный формат API ключа для {provider}")
        
        return api_key
    
    def get_timeout(self, operation: str) -> int:
        """Получает таймаут для операции"""
        timeout_mapping = {
            "transcription": self._api_configs["openai"].timeout.total,
            "diarization": self._api_configs["pyannote"].timeout.total,
            "upload": 120,
            "download": 60
        }
        
        return timeout_mapping.get(operation, 30)
    
    def get_retry_config(self, operation: str) -> Dict[str, Any]:
        """Получает конфигурацию повторов"""
        if operation in ["transcription", "openai"]:
            retry_config = self._api_configs["openai"].retry
        elif operation in ["diarization", "pyannote"]:
            retry_config = self._api_configs["pyannote"].retry
        else:
            retry_config = RetryConfig()
        
        return asdict(retry_config)
    
    def get_api_config(self, provider: str) -> APIConfig:
        """Получает полную конфигурацию API"""
        if provider not in self._api_configs:
            raise ConfigurationError(f"Конфигурация для {provider} не найдена")
        
        return self._api_configs[provider]
    
    def get_pipeline_config(self) -> PipelineConfig:
        """Получает конфигурацию пайплайна"""
        return self._config

    def get_transcription_config(self) -> TranscriptionConfig:
        """Получает конфигурацию транскрипции"""
        return self._config.transcription

    def set_transcription_model(self, model: str) -> None:
        """Устанавливает модель транскрипции"""
        # Список поддерживаемых моделей (избегаем циклического импорта)
        supported_models = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]

        # Валидируем модель
        if model not in supported_models:
            available_models = ", ".join(supported_models)
            raise ConfigurationError(f"Неподдерживаемая модель '{model}'. Доступные: {available_models}")

        self._config.transcription.model = model
        self.logger.info(f"Установлена модель транскрипции: {model}")

    def set_transcription_language(self, language: Optional[str]) -> None:
        """Устанавливает язык транскрипции"""
        self._config.transcription.language = language
        if language:
            self.logger.info(f"Установлен язык транскрипции: {language}")
        else:
            self.logger.info("Язык транскрипции сброшен (автоопределение)")

    def get_transcription_model_info(self) -> Dict[str, Any]:
        """Получает информацию о текущей модели транскрипции"""
        # Информация о моделях (избегаем циклического импорта)
        model_info_map = {
            "whisper-1": {
                "name": "Whisper v1",
                "description": "Базовая модель Whisper, быстрая и экономичная",
                "cost_tier": "low"
            },
            "gpt-4o-mini-transcribe": {
                "name": "GPT-4o Mini Transcribe",
                "description": "Улучшенная модель с балансом цены и качества",
                "cost_tier": "medium"
            },
            "gpt-4o-transcribe": {
                "name": "GPT-4o Transcribe",
                "description": "Наиболее точная модель с лучшим качеством распознавания",
                "cost_tier": "high"
            }
        }

        model = self._config.transcription.model
        if model in model_info_map:
            return {
                "current_model": model,
                "language": self._config.transcription.language,
                **model_info_map[model]
            }
        else:
            return {"current_model": model, "status": "unknown"}

    def estimate_transcription_cost(self, file_size_mb: float) -> Dict[str, str]:
        """Оценивает стоимость транскрипции для всех моделей"""
        # Простая оценка стоимости (избегаем циклического импорта)
        cost_estimates = {
            "low": f"~${file_size_mb * 0.006:.3f}",  # whisper-1: $0.006/min
            "medium": f"~${file_size_mb * 0.012:.3f}",  # gpt-4o-mini-transcribe: примерно в 2 раза дороже
            "high": f"~${file_size_mb * 0.024:.3f}"  # gpt-4o-transcribe: примерно в 4 раза дороже
        }

        estimates = {}
        model_cost_map = {
            "whisper-1": "low",
            "gpt-4o-mini-transcribe": "medium",
            "gpt-4o-transcribe": "high"
        }

        for model_name, cost_tier in model_cost_map.items():
            estimates[model_name] = cost_estimates[cost_tier]

        return estimates
    
    def update_config(self, **kwargs) -> None:
        """Обновляет конфигурацию"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                self.logger.warning(f"Неизвестный параметр конфигурации: {key}")
        
        self._validate_config()
    
    def save_config(self) -> None:
        """Сохраняет конфигурацию в файл"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self._config), f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"Конфигурация сохранена в {self.config_file}")
    
    def get_rate_limit(self, provider: str) -> int:
        """Получает лимит запросов в минуту"""
        if provider in self._api_configs:
            return self._api_configs[provider].rate_limit_per_minute
        return 60  # По умолчанию
    
    def is_cache_enabled(self) -> bool:
        """Проверяет, включено ли кэширование"""
        return self._config.cache_enabled
    
    def get_cache_ttl(self) -> int:
        """Получает TTL кэша в секундах"""
        return self._config.cache_ttl_hours * 3600
    
    def get_max_file_size(self) -> int:
        """Получает максимальный размер файла в байтах"""
        return self._config.max_file_size_mb * 1024 * 1024
    
    def get_max_audio_duration(self) -> int:
        """Получает максимальную длительность аудио в секундах"""
        return self._config.max_audio_duration_hours * 3600
    
    def get_data_paths(self) -> Dict[str, Path]:
        """Получает пути к директориям данных"""
        return {
            "data": self._config.data_dir,
            "cache": self._config.cache_dir,
            "logs": self._config.logs_dir,
            "voiceprints": self._config.voiceprints_dir,
            "raw": self._config.data_dir / "raw",
            "interim": self._config.data_dir / "interim",
            "processed": self._config.data_dir / "processed"
        }
    
    def setup_logging(self) -> None:
        """Настраивает логирование согласно конфигурации"""
        from logging.handlers import RotatingFileHandler
        import json
        import datetime
        
        # Создаём директорию для логов
        self._config.logs_dir.mkdir(exist_ok=True)
        
        # Кастомный форматтер для JSON логов
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                if record.exc_info:
                    log_entry['exception'] = self.formatException(record.exc_info)
                return json.dumps(log_entry, ensure_ascii=False)
        
        # Настраиваем root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self._config.log_level.upper()))
        
        # Очищаем существующие handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler
        file_handler = RotatingFileHandler(
            self._config.logs_dir / 'pipeline.log',
            maxBytes=self._config.log_rotation_mb * 1024 * 1024,
            backupCount=self._config.log_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
        
        # Error handler
        error_handler = RotatingFileHandler(
            self._config.logs_dir / 'errors.log',
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_handler)


# Глобальный экземпляр конфигурации
_config_manager: Optional[ConfigurationManager] = None


def get_config() -> ConfigurationManager:
    """Получает глобальный экземпляр конфигурации"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def init_config(config_file: Optional[Path] = None) -> ConfigurationManager:
    """Инициализирует конфигурацию"""
    global _config_manager
    _config_manager = ConfigurationManager(config_file)
    return _config_manager
