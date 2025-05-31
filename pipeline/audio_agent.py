# pipeline/audio_agent.py

import logging
import subprocess
import tempfile
import uuid
import os
from pathlib import Path
from typing import Tuple, Union, Optional

from .pyannote_media_agent import PyannoteMediaAgent

TARGET_SR = 16_000  # 16 kHz for Whisper & Pyannote

class AudioLoaderAgent:
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
        self.remote_wav_url = remote_wav_url
        self.logger = logging.getLogger(__name__)

        # Инициализируем pyannote.ai Media агент
        api_key = pyannote_api_key or os.getenv("PYANNOTEAI_API_TOKEN") or os.getenv("PYANNOTE_API_KEY")
        if not api_key:
            raise ValueError("Требуется API ключ pyannote.ai. Установите PYANNOTEAI_API_TOKEN или передайте pyannote_api_key")

        try:
            self.pyannote_media_agent = PyannoteMediaAgent(api_key)
            if not self.pyannote_media_agent.validate_api_key():
                raise ValueError("Неверный API ключ pyannote.ai")
            self.logger.info("✅ Pyannote.ai Media агент инициализирован")
        except Exception as e:
            self.logger.error(f"❌ Не удалось инициализировать pyannote.ai Media: {e}")
            raise RuntimeError(f"Не удалось инициализировать pyannote.ai Media API: {e}") from e

    def to_wav16k_mono(self, src: Union[str, Path]) -> Path:
        src = Path(src)
        tmp = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", src.as_posix(),
            "-ac", "1",
            "-ar", str(TARGET_SR),
            "-vn", tmp.as_posix(),
        ]
        try:
            self.logger.debug(f"Конвертирую {src} → {tmp}")
            subprocess.run(cmd, capture_output=True, check=True, text=True)
            self.logger.debug(f"FFmpeg завершён успешно")
            return tmp
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Ошибка конвертации {src}: {e}")
            if e.stderr:
                self.logger.error(f"FFmpeg stderr: {e.stderr}")
            raise RuntimeError(f"Не удалось сконвертировать {src}") from e



    def upload_file(self, wav_path: Path) -> str:
        """
        Загружает файл в pyannote.ai Media API.
        """
        try:
            self.logger.info(f"📤 Загружаю {wav_path.name} в pyannote.ai...")

            # Загружаем файл и получаем виртуальный путь
            virtual_path = self.pyannote_media_agent.upload_file(wav_path)

            self.logger.info(f"✅ Файл загружен в pyannote.ai: {virtual_path}")
            return virtual_path

        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки в pyannote.ai: {e}")
            raise RuntimeError(f"Не удалось загрузить файл в pyannote.ai: {e}") from e

    def run(self, input_src: str) -> Tuple[Path, str]:
        """
        1) Если файл существует локально → to_wav16k_mono → получить wav_local.
           – Если задан --remote-wav-url, взять его (wav_url) и вернуть вместе с wav_local.
           – Иначе upload wav_local → wav_url.
        2) Если input_src — это URL, считаем, что это уже WAV (или любой URL → ffmpeg «читать» URL).
           – Сначала скачиваем в tmp WAV → to_wav16k_mono
           – получаем wav_url:
             • Если --remote-wav-url задан, ignore (реально в нашем случае
               input_src == remote_wav_url), но всё равно отдадим его.
             • Иначе снова upload наш tmp WAV на transfer.sh → wav_url.
        Возвращает (wav_local: Path, wav_url: str).
        """
        if Path(input_src).exists():
            wav_local = self.to_wav16k_mono(input_src)
            if self.remote_wav_url:
                wav_url = self.remote_wav_url
            else:
                wav_url = self.upload_file(wav_local)
        else:
            # предполагаем, что input_src – URL на аудио (mp3/wav)
            # ffmpeg умеет читать напрямую из URL:
            wav_local = self.to_wav16k_mono(input_src)
            if self.remote_wav_url:
                wav_url = self.remote_wav_url
            else:
                wav_url = self.upload_file(wav_local)
        return wav_local, wav_url
