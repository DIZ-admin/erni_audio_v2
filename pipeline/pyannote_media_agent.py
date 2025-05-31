# pipeline/pyannote_media_agent.py

import logging
import os
import requests
import uuid
from pathlib import Path
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class PyannoteMediaAgent:
    """
    Агент для работы с pyannote.ai Media API.
    
    Реализует безопасную загрузку файлов через временное хранилище pyannote.ai:
    - Создает pre-signed URL для загрузки
    - Загружает файл в изолированное хранилище
    - Файлы автоматически удаляются через 24-48 часов
    - Более безопасная альтернатива transfer.sh
    """

    def __init__(self, api_key: str):
        """
        Args:
            api_key: API ключ pyannote.ai
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://api.pyannote.ai/v1"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=lambda retry_state: logging.getLogger(__name__).warning(
            f"Повтор {retry_state.attempt_number} создания pre-signed URL"
        )
    )
    def _create_presigned_url(self, virtual_path: str) -> str:
        """
        Создает pre-signed URL для загрузки файла.
        
        Args:
            virtual_path: Виртуальный путь в формате media://folder/filename.wav
            
        Returns:
            Pre-signed URL для загрузки
        """
        try:
            self.logger.debug(f"Создаю pre-signed URL для: {virtual_path}")

            payload = {"url": virtual_path}

            response = requests.post(
                f"{self.base_url}/media/input",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            presigned_url = data["url"]
            
            self.logger.debug(f"Pre-signed URL создан успешно")
            return presigned_url
            
        except requests.Timeout as e:
            self.logger.error(f"Таймаут при создании pre-signed URL: {e}")
            raise
        except requests.HTTPError as e:
            self.logger.error(f"HTTP ошибка при создании pre-signed URL: {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 401:
                    raise RuntimeError("Неверный API ключ pyannote.ai") from e
                elif e.response.status_code == 429:
                    raise RuntimeError("Превышен лимит запросов pyannote.ai") from e
                else:
                    raise RuntimeError(f"Ошибка pyannote.ai API: {e}") from e
            else:
                raise RuntimeError(f"Ошибка pyannote.ai API: {e}") from e
        except KeyError as e:
            self.logger.error(f"Неожиданный формат ответа API: {e}")
            raise RuntimeError("Неожиданный формат ответа pyannote.ai API") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=lambda retry_state: logging.getLogger(__name__).warning(
            f"Повтор {retry_state.attempt_number} загрузки файла"
        )
    )
    def _upload_file_to_presigned_url(self, file_path: Path, presigned_url: str) -> None:
        """
        Загружает файл по pre-signed URL.
        
        Args:
            file_path: Путь к локальному файлу
            presigned_url: Pre-signed URL для загрузки
        """
        try:
            self.logger.debug(f"Загружаю файл {file_path.name} по pre-signed URL")
            
            with open(file_path, "rb") as file_data:
                response = requests.put(
                    presigned_url,
                    data=file_data,
                    timeout=120  # Увеличенный таймаут для больших файлов
                )
                response.raise_for_status()
            
            self.logger.debug(f"Файл {file_path.name} загружен успешно")
            
        except requests.Timeout as e:
            self.logger.error(f"Таймаут при загрузке файла: {e}")
            raise RuntimeError(f"Таймаут при загрузке файла: {e}") from e
        except requests.HTTPError as e:
            self.logger.error(f"HTTP ошибка при загрузке файла: {e}")
            raise RuntimeError(f"Ошибка загрузки файла: {e}") from e
        except IOError as e:
            self.logger.error(f"Ошибка чтения файла {file_path}: {e}")
            raise RuntimeError(f"Не удалось прочитать файл: {e}") from e

    def upload_file(self, file_path: Path, custom_name: Optional[str] = None) -> str:
        """
        Загружает файл в временное хранилище pyannote.ai.
        
        Args:
            file_path: Путь к локальному файлу
            custom_name: Пользовательское имя файла (опционально)
            
        Returns:
            Виртуальный путь для использования в Jobs API (media://...)
        """
        try:
            # Используем формат из документации: media://example/conversation.wav
            if custom_name:
                filename = custom_name
            else:
                unique_id = uuid.uuid4().hex[:8]
                filename = f"conversation-{unique_id}.wav"

            # Создаем виртуальный путь точно как в документации
            virtual_path = f"media://example/{filename}"
            
            self.logger.info(f"📤 Загружаю {file_path.name} в pyannote.ai временное хранилище...")
            
            # Создаем pre-signed URL
            presigned_url = self._create_presigned_url(virtual_path)
            
            # Загружаем файл
            self._upload_file_to_presigned_url(file_path, presigned_url)
            
            self.logger.info(f"✅ Файл загружен в pyannote.ai: {virtual_path}")
            self.logger.info("ℹ️ Файл будет автоматически удален через 24-48 часов")
            
            return virtual_path
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки в pyannote.ai: {e}")
            raise RuntimeError(f"Не удалось загрузить файл в pyannote.ai: {e}") from e

    def validate_api_key(self) -> bool:
        """
        Проверяет валидность API ключа.
        
        Returns:
            True если ключ валиден, False иначе
        """
        try:
            # Используем тестовый endpoint для проверки ключа
            response = requests.get(
                f"{self.base_url}/test",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return True
            
        except requests.RequestException:
            return False
