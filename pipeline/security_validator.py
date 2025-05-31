# pipeline/security_validator.py

import os
import hashlib
import mimetypes
from pathlib import Path
from typing import Set, Optional, Tuple
import logging
import magic  # python-magic для определения MIME типов


class SecurityValidator:
    """
    Валидатор безопасности для входных файлов.
    
    Проверяет файлы на соответствие требованиям безопасности:
    - MIME типы
    - Размер файлов
    - Расширения
    - Целостность
    """
    
    # Разрешенные MIME типы для аудио/видео файлов
    ALLOWED_MIME_TYPES: Set[str] = {
        'audio/mpeg',           # MP3
        'audio/wav',            # WAV
        'audio/x-wav',          # WAV (альтернативный)
        'audio/wave',           # WAV (альтернативный)
        'audio/mp4',            # M4A
        'audio/x-m4a',          # M4A (альтернативный)
        'audio/flac',           # FLAC
        'video/mp4',            # MP4
        'video/x-msvideo',      # AVI
        'video/quicktime',      # MOV
    }
    
    # Разрешенные расширения файлов
    ALLOWED_EXTENSIONS: Set[str] = {
        '.mp3', '.wav', '.mp4', '.avi', '.mov', '.m4a', '.flac'
    }
    
    # Максимальный размер файла (300MB)
    MAX_FILE_SIZE: int = 300 * 1024 * 1024
    
    # Минимальный размер файла (1KB)
    MIN_FILE_SIZE: int = 1024
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Проверяем доступность python-magic
        try:
            self.magic_mime = magic.Magic(mime=True)
            self.magic_available = True
        except Exception as e:
            self.logger.warning(f"python-magic недоступен: {e}")
            self.magic_available = False
    
    def validate_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        Комплексная валидация файла.
        
        Args:
            file_path: Путь к файлу для проверки
            
        Returns:
            Tuple[bool, str]: (валиден ли файл, сообщение об ошибке)
        """
        try:
            # 1. Проверка существования файла
            if not file_path.exists():
                return False, f"Файл не найден: {file_path}"
            
            if not file_path.is_file():
                return False, f"Путь не является файлом: {file_path}"
            
            # 2. Проверка размера файла
            file_size = file_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                return False, f"Файл слишком большой: {file_size / 1024 / 1024:.1f}MB (максимум {self.MAX_FILE_SIZE / 1024 / 1024}MB)"
            
            if file_size < self.MIN_FILE_SIZE:
                return False, f"Файл слишком маленький: {file_size} байт (минимум {self.MIN_FILE_SIZE} байт)"
            
            # 3. Проверка расширения файла
            extension = file_path.suffix.lower()
            if extension not in self.ALLOWED_EXTENSIONS:
                return False, f"Неподдерживаемое расширение: {extension}. Разрешены: {', '.join(self.ALLOWED_EXTENSIONS)}"
            
            # 4. Проверка MIME типа
            mime_valid, mime_error = self._validate_mime_type(file_path)
            if not mime_valid:
                return False, mime_error
            
            # 5. Проверка целостности файла
            integrity_valid, integrity_error = self._validate_file_integrity(file_path)
            if not integrity_valid:
                return False, integrity_error
            
            self.logger.info(f"Файл прошел валидацию: {file_path} ({file_size / 1024 / 1024:.1f}MB)")
            return True, "Файл валиден"
            
        except Exception as e:
            self.logger.error(f"Ошибка валидации файла {file_path}: {e}")
            return False, f"Ошибка валидации: {e}"
    
    def _validate_mime_type(self, file_path: Path) -> Tuple[bool, str]:
        """Проверка MIME типа файла."""
        try:
            # Используем python-magic если доступен
            if self.magic_available:
                mime_type = self.magic_mime.from_file(str(file_path))
            else:
                # Fallback на mimetypes
                mime_type, _ = mimetypes.guess_type(str(file_path))
                if mime_type is None:
                    return False, "Не удалось определить MIME тип файла"
            
            if mime_type not in self.ALLOWED_MIME_TYPES:
                return False, f"Неподдерживаемый MIME тип: {mime_type}. Разрешены: {', '.join(sorted(self.ALLOWED_MIME_TYPES))}"
            
            return True, f"MIME тип валиден: {mime_type}"
            
        except Exception as e:
            return False, f"Ошибка проверки MIME типа: {e}"
    
    def _validate_file_integrity(self, file_path: Path) -> Tuple[bool, str]:
        """Базовая проверка целостности файла."""
        try:
            # Проверяем, что файл можно прочитать
            with open(file_path, 'rb') as f:
                # Читаем первые 1KB для проверки доступности
                chunk = f.read(1024)
                if not chunk:
                    return False, "Файл пустой или поврежден"
            
            # Вычисляем хэш файла для проверки целостности
            file_hash = self._calculate_file_hash(file_path)
            if not file_hash:
                return False, "Не удалось вычислить хэш файла"
            
            return True, f"Файл целостен (SHA256: {file_hash[:16]}...)"
            
        except PermissionError:
            return False, "Недостаточно прав для чтения файла"
        except Exception as e:
            return False, f"Ошибка проверки целостности: {e}"
    
    def _calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """Вычисляет SHA256 хэш файла."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Читаем файл по частям для экономии памяти
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Ошибка вычисления хэша: {e}")
            return None
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Валидация URL для удаленных файлов.
        
        Args:
            url: URL для проверки
            
        Returns:
            Tuple[bool, str]: (валиден ли URL, сообщение)
        """
        if not url.startswith(('http://', 'https://')):
            return False, "URL должен начинаться с http:// или https://"
        
        if not url.startswith('https://'):
            return False, "Для безопасности используйте только HTTPS URLs"
        
        # Проверяем, что URL не содержит подозрительных символов
        suspicious_chars = ['<', '>', '"', "'", '&', ';']
        if any(char in url for char in suspicious_chars):
            return False, "URL содержит подозрительные символы"
        
        return True, "URL валиден"


# Глобальный экземпляр валидатора
SECURITY_VALIDATOR = SecurityValidator()
