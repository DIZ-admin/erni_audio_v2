# pipeline/validation_mixin.py

import mimetypes
import urllib.parse
from pathlib import Path
from typing import Set, Optional, Tuple

# Temporary workaround for Python 3.13 compatibility with pydub
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("⚠️ Warning: pydub not available, audio duration validation disabled")


class ValidationMixin:
    """
    Миксин для валидации файлов и данных.
    
    Предоставляет общие методы валидации:
    - Валидация аудиофайлов
    - Проверка размеров файлов
    - MIME type валидация
    - URL валидация
    """
    
    # Поддерживаемые MIME типы для аудио
    ALLOWED_AUDIO_MIME_TYPES: Set[str] = {
        'audio/mpeg',           # MP3
        'audio/wav',            # WAV
        'audio/x-wav',          # WAV (альтернативный)
        'audio/wave',           # WAV (альтернативный)
        'audio/mp4',            # M4A/MP4 audio
        'audio/x-m4a',          # M4A
        'audio/flac',           # FLAC
        'audio/ogg',            # OGG
        'audio/webm',           # WebM audio
        'video/mp4',            # MP4 video (с аудио)
        'video/avi',            # AVI
        'video/mov',            # MOV
        'video/quicktime',      # QuickTime
    }
    
    # Поддерживаемые расширения файлов
    ALLOWED_AUDIO_EXTENSIONS: Set[str] = {
        '.mp3', '.wav', '.m4a', '.mp4', '.avi', '.mov', 
        '.flac', '.ogg', '.webm', '.aac', '.wma'
    }
    
    def validate_audio_file(self, file_path: Path, max_size_mb: int = 300, 
                           check_duration: bool = False, max_duration_hours: float = 24.0) -> None:
        """
        Комплексная валидация аудиофайла.
        
        Args:
            file_path: Путь к файлу
            max_size_mb: Максимальный размер в МБ
            check_duration: Проверять ли длительность
            max_duration_hours: Максимальная длительность в часах
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если файл не прошел валидацию
        """
        # Проверка существования файла
        if not file_path.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {file_path}")
        
        # Проверка, что это файл, а не директория
        if not file_path.is_file():
            raise ValueError(f"Путь не является файлом: {file_path}")
        
        # Проверка расширения
        if file_path.suffix.lower() not in self.ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"Неподдерживаемое расширение файла: {file_path.suffix}. "
                f"Поддерживаемые: {', '.join(sorted(self.ALLOWED_AUDIO_EXTENSIONS))}"
            )
        
        # Проверка размера файла
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(
                f"Файл слишком большой: {file_size_mb:.1f}MB "
                f"(максимум {max_size_mb}MB)"
            )
        
        # Проверка MIME типа
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type not in self.ALLOWED_AUDIO_MIME_TYPES:
            # Логируем предупреждение, но не блокируем
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"⚠️ Неожиданный MIME тип: {mime_type} для файла {file_path.name}"
                )
        
        # Проверка длительности (опционально)
        if check_duration and PYDUB_AVAILABLE:
            try:
                audio = AudioSegment.from_file(str(file_path))
                duration_hours = len(audio) / (1000 * 60 * 60)  # миллисекунды в часы
                
                if duration_hours > max_duration_hours:
                    raise ValueError(
                        f"Файл слишком длинный: {duration_hours:.1f}ч "
                        f"(максимум {max_duration_hours}ч)"
                    )
                
                if hasattr(self, 'logger'):
                    self.logger.debug(
                        f"📊 Файл {file_path.name}: {file_size_mb:.1f}MB, "
                        f"{duration_hours:.1f}ч"
                    )
                    
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.warning(
                        f"⚠️ Не удалось проверить длительность файла {file_path.name}: {e}"
                    )
        elif check_duration and not PYDUB_AVAILABLE:
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"⚠️ Проверка длительности отключена: pydub недоступен"
                )
        
        # Логируем успешную валидацию
        if hasattr(self, 'logger'):
            self.logger.debug(f"✅ Файл {file_path.name} прошел валидацию ({file_size_mb:.1f}MB)")
    
    def validate_file_size(self, file_path: Path, max_size_mb: int, 
                          operation_name: str = "операция") -> None:
        """
        Валидация размера файла.
        
        Args:
            file_path: Путь к файлу
            max_size_mb: Максимальный размер в МБ
            operation_name: Название операции для сообщений об ошибках
            
        Raises:
            ValueError: Если файл слишком большой
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        
        if file_size_mb > max_size_mb:
            raise ValueError(
                f"Файл слишком большой для {operation_name}: {file_size_mb:.1f}MB "
                f"(максимум {max_size_mb}MB)"
            )
        
        # Предупреждение для больших файлов
        if file_size_mb > max_size_mb * 0.8:  # 80% от лимита
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"⚠️ Большой файл для {operation_name}: {file_size_mb:.1f}MB, "
                    f"обработка может занять много времени"
                )
    
    def validate_url(self, url: str, require_https: bool = True) -> Tuple[bool, str]:
        """
        Валидация URL.
        
        Args:
            url: URL для валидации
            require_https: Требовать ли HTTPS
            
        Returns:
            Tuple[bool, str]: (валиден ли URL, сообщение об ошибке)
        """
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Проверка схемы
            if not parsed.scheme:
                return False, "URL должен содержать схему (http/https)"
            
            if require_https and parsed.scheme != 'https':
                return False, "Требуется HTTPS URL для безопасности"
            
            if parsed.scheme not in ['http', 'https']:
                return False, f"Неподдерживаемая схема: {parsed.scheme}"
            
            # Проверка хоста
            if not parsed.netloc:
                return False, "URL должен содержать хост"
            
            # Проверка на локальные адреса (безопасность)
            if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
                return False, "Локальные адреса не разрешены"
            
            return True, "URL валиден"
            
        except Exception as e:
            return False, f"Ошибка парсинга URL: {e}"
    
    def validate_voiceprint_ids(self, voiceprint_ids: list, min_count: int = 1, 
                               max_count: int = 100) -> None:
        """
        Валидация списка voiceprint ID.
        
        Args:
            voiceprint_ids: Список ID голосовых отпечатков
            min_count: Минимальное количество ID
            max_count: Максимальное количество ID
            
        Raises:
            ValueError: Если список не прошел валидацию
        """
        if not isinstance(voiceprint_ids, list):
            raise ValueError("voiceprint_ids должен быть списком")
        
        if len(voiceprint_ids) < min_count:
            raise ValueError(
                f"Недостаточно voiceprint ID: {len(voiceprint_ids)} "
                f"(минимум {min_count})"
            )
        
        if len(voiceprint_ids) > max_count:
            raise ValueError(
                f"Слишком много voiceprint ID: {len(voiceprint_ids)} "
                f"(максимум {max_count})"
            )
        
        # Проверка на дубликаты
        unique_ids = set(voiceprint_ids)
        if len(unique_ids) != len(voiceprint_ids):
            duplicates = len(voiceprint_ids) - len(unique_ids)
            raise ValueError(f"Найдены дублирующиеся voiceprint ID: {duplicates} дубликатов")
        
        # Проверка формата ID (должны быть строками)
        for i, vp_id in enumerate(voiceprint_ids):
            if not isinstance(vp_id, str):
                raise ValueError(f"Voiceprint ID #{i} должен быть строкой, получен {type(vp_id)}")
            
            if not vp_id.strip():
                raise ValueError(f"Voiceprint ID #{i} не может быть пустым")
    
    def validate_language_code(self, language: Optional[str]) -> Optional[str]:
        """
        Валидация кода языка.
        
        Args:
            language: Код языка (например, 'en', 'ru', 'de')
            
        Returns:
            Валидированный код языка или None
            
        Raises:
            ValueError: Если код языка невалиден
        """
        if language is None:
            return None
        
        if not isinstance(language, str):
            raise ValueError(f"Код языка должен быть строкой, получен {type(language)}")
        
        language = language.strip().lower()
        
        if not language:
            return None
        
        # Проверка длины (ISO 639-1 коды имеют длину 2)
        if len(language) != 2:
            raise ValueError(
                f"Код языка должен быть двухбуквенным (ISO 639-1): '{language}'"
            )
        
        # Проверка на буквы
        if not language.isalpha():
            raise ValueError(f"Код языка должен содержать только буквы: '{language}'")
        
        return language
