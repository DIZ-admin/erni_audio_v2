"""
Speech Pipeline - мульти-агентная система для обработки аудио.

Этот пакет содержит реализации агентов для:
- Загрузки и конвертации аудио
- Диаризации (определения говорящих)
- Контроля качества и извлечения голосовых отпечатков
- Транскрипции (распознавания речи)
- Объединения результатов диаризации и транскрипции
- Экспорта в различные форматы (SRT, JSON, ASS)
"""

from .audio_agent import AudioLoaderAgent
from .diarization_agent import DiarizationAgent
from .qc_agent import QCAgent
from .transcription_agent import TranscriptionAgent
from .merge_agent import MergeAgent
from .export_agent import ExportAgent
from .utils import load_json
