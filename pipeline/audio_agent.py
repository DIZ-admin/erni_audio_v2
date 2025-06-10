# pipeline/audio_agent.py

import subprocess
import tempfile
import uuid
import os
from pathlib import Path
from typing import Tuple, Union, Optional

from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin
from .rate_limit_mixin import RateLimitMixin
from .pyannote_media_agent import PyannoteMediaAgent

TARGET_SR = 16_000  # 16 kHz for Whisper & Pyannote

class AudioLoaderAgent(BaseAgent, ValidationMixin, RateLimitMixin):
    """
    Агент, который принимает на вход:
      - либо локальный файл (mp3, wav, mp4 …)
      - либо URL на WAV
    и выдаёт:
      (local_wav_path: Path, wav_url: str)
    Если input_path.exists(), конвертируем его в 16kHz-mono WAV.
    Если у нас флаг --remote-wav-url, то пропускаем upload и берём URL.
    Иначе загружаем в pyannote.ai Media API и возвращаем виртуальный путь.
    """

    def __init__(self,
                 remote_wav_url: Optional[str] = None,
                 pyannote_api_key: Optional[str] = None):
        """
        Args:
            remote_wav_url: Готовый URL для использования (пропускает загрузку)
            pyannote_api_key: API ключ для pyannote.ai (если не задан, берется из env)
        """
        # Инициализируем базовые классы
        BaseAgent.__init__(self, "AudioLoaderAgent")
        ValidationMixin.__init__(self)
        RateLimitMixin.__init__(self, "pyannote")

        self.remote_wav_url = remote_wav_url

        # Получаем API ключ через базовый метод
        try:
            api_key = pyannote_api_key or self.get_api_key(
                "pyannote.ai",
                ["PYANNOTEAI_API_TOKEN", "PYANNOTE_API_KEY"]
            )
        except ValueError as e:
            self.handle_error(e, "инициализация API ключа")

        # Инициализируем pyannote.ai Media агент
        try:
            self.pyannote_media_agent = PyannoteMediaAgent(api_key)
            if not self.pyannote_media_agent.validate_api_key():
                raise ValueError("Неверный API ключ pyannote.ai")
            self.log_with_emoji("info", "✅", "Pyannote.ai Media агент инициализирован")
        except Exception as e:
            self.handle_error(e, "инициализация pyannote.ai Media API")

    def to_wav16k_mono(self, src: Union[str, Path]) -> Path:
        """
        Конвертирует аудиофайл в WAV 16kHz mono формат.

        Args:
            src: Путь к исходному файлу или URL

        Returns:
            Путь к сконвертированному WAV файлу
        """
        src = Path(src) if not str(src).startswith(('http://', 'https://')) else src
        tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.wav"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-ac", "1",
            "-ar", str(TARGET_SR),
            "-vn", tmp.as_posix(),
        ]

        try:
            self.log_with_emoji("debug", "🔄", f"Конвертирую {src} → {tmp}")
            subprocess.run(cmd, capture_output=True, check=True, text=True)
            self.log_with_emoji("debug", "✅", "FFmpeg завершён успешно")
            return tmp
        except subprocess.CalledProcessError as e:
            error_msg = f"Ошибка конвертации {src}: {e}"
            if e.stderr:
                error_msg += f"\nFFmpeg stderr: {e.stderr}"
            self.handle_error(RuntimeError(error_msg), "конвертация аудио")



    def upload_file(self, wav_path: Path) -> str:
        """
        Загружает файл в pyannote.ai Media API с rate limiting.

        Args:
            wav_path: Путь к WAV файлу для загрузки

        Returns:
            Виртуальный путь в pyannote.ai Media API
        """
        # Валидируем файл перед загрузкой
        self.validate_audio_file(wav_path, max_size_mb=100)  # pyannote.ai лимит

        def _upload():
            self.log_with_emoji("info", "📤", f"Загружаю {wav_path.name} в pyannote.ai...")
            virtual_path = self.pyannote_media_agent.upload_file(wav_path)
            self.log_with_emoji("info", "✅", f"Файл загружен в pyannote.ai: {virtual_path}")
            return virtual_path

        try:
            # Выполняем загрузку с rate limiting
            return self.with_rate_limit(_upload, "upload", timeout=300.0)  # 5 минут таймаут
        except Exception as e:
            self.handle_error(e, "загрузка в pyannote.ai")

    def run(self, input_src: str) -> Tuple[Path, str]:
        """
        Основной метод обработки аудио.

        Процесс:
        1) Если файл существует локально → конвертация в WAV 16kHz mono
        2) Если input_src — URL → скачивание и конвертация
        3) Загрузка в pyannote.ai Media API (если не задан remote_wav_url)

        Args:
            input_src: Путь к файлу или URL

        Returns:
            Tuple[Path, str]: (локальный WAV файл, URL для API)
        """
        self.start_operation("обработка аудио")

        try:
            # Определяем тип входных данных
            is_local_file = Path(input_src).exists()

            if is_local_file:
                self.log_with_emoji("info", "📁", f"Обрабатываю локальный файл: {input_src}")
                # Валидируем локальный файл
                input_path = Path(input_src)
                self.validate_audio_file(input_path, max_size_mb=300)
                wav_local = self.to_wav16k_mono(input_src)
            else:
                self.log_with_emoji("info", "🌐", f"Обрабатываю URL: {input_src}")
                # Валидируем URL
                is_valid, message = self.validate_url(input_src, require_https=False)
                if not is_valid:
                    raise ValueError(f"Невалидный URL: {message}")
                wav_local = self.to_wav16k_mono(input_src)

            # Определяем URL для API
            if self.remote_wav_url:
                self.log_with_emoji("info", "🔗", f"Используется предоставленный URL: {self.remote_wav_url}")
                wav_url = self.remote_wav_url
            else:
                wav_url = self.upload_file(wav_local)

            self.end_operation("обработка аудио", success=True)
            self.log_with_emoji("info", "✅", f"Аудио готово: {wav_local} → {wav_url}")

            return wav_local, wav_url

        except Exception as e:
            self.end_operation("обработка аудио", success=False)
            self.handle_error(e, "обработка аудио")
