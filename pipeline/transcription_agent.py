# pipeline/transcription_agent.py

import logging
from openai import OpenAI
from pathlib import Path
from typing import List, Dict
import openai

class TranscriptionAgent:
    """
    Агент для взаимодействия с OpenAI Whisper (cloud).
    Возвращает verbose_json["segments"], каждый сегмент — Dict c полями:
    id, start, end, text, tokens, avg_logprob, no_speech_prob, temperature, compression_ratio.
    """
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.logger = logging.getLogger(__name__)

    def run(self, wav_local: Path, prompt: str = "") -> List[Dict]:
        """
        :param wav_local: локальный 16kHz WAV-файл
        :param prompt: опциональный подпорос Whisper
        :return: список сегментов ASR
        """
        import time
        start_time = time.time()

        try:
            file_size = wav_local.stat().st_size / (1024 * 1024)  # MB
            self.logger.debug(f"Начинаю транскрипцию файла: {wav_local} ({file_size:.1f}MB)")

            with open(wav_local, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="verbose_json",
                    prompt=prompt,
                    temperature=0,
                )

            # Новый API возвращает объект с атрибутом segments
            segments = transcript.segments if hasattr(transcript, 'segments') else []

            # Логируем метрики производительности
            duration = time.time() - start_time
            processing_ratio = duration / (transcript.duration if hasattr(transcript, 'duration') else 1)

            self.logger.info(f"Транскрипция завершена: {len(segments)} сегментов", extra={
                'processing_time': f"{duration:.2f}s",
                'file_size_mb': f"{file_size:.1f}MB",
                'processing_ratio': f"{processing_ratio:.2f}x",
                'segments_count': len(segments)
            })

            return [segment.model_dump() if hasattr(segment, 'model_dump') else dict(segment) for segment in segments]

        except openai.APIConnectionError as e:
            self.logger.error(f"Ошибка подключения к OpenAI API: {e}")
            raise RuntimeError(f"Не удалось подключиться к OpenAI API: {e}") from e
        except openai.RateLimitError as e:
            self.logger.error(f"Превышен лимит запросов OpenAI API: {e}")
            raise RuntimeError(f"Превышен лимит запросов OpenAI API: {e}") from e
        except openai.APIStatusError as e:
            self.logger.error(f"Ошибка OpenAI API (статус {e.status_code}): {e}")
            raise RuntimeError(f"Ошибка OpenAI API: {e}") from e
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при транскрипции: {e}")
            raise RuntimeError(f"Ошибка транскрипции: {e}") from e
