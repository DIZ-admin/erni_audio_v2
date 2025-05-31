import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pipeline.qc_agent import QCAgent

def test_init():
    agent = QCAgent(manifest_dir=Path("/tmp/voiceprints"), per_speaker_sec=20)
    assert agent.manifest_dir == Path("/tmp/voiceprints")
    assert agent.per_speaker_sec == 20

def test_run_without_manifest_dir():
    agent = QCAgent(manifest_dir=None)
    diar = [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]
    
    result = agent.run(Path("test.wav"), diar)
    assert result == diar  # Должен вернуть тот же diar без изменений

def test_run_with_manifest_dir():
    agent = QCAgent(manifest_dir=Path("/tmp/voiceprints"))
    diar = [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]
    
    with patch.object(agent, 'extract_voiceprints') as mock_extract:
        result = agent.run(Path("test.wav"), diar)
        assert result == []  # Должен вернуть пустой список, сигнализируя о завершении пайплайна
        mock_extract.assert_called_once_with(Path("test.wav"), diar)

def test_extract_voiceprints():
    """Тест проверяет основную функциональность extract_voiceprints"""
    agent = QCAgent(manifest_dir=Path("/tmp/voiceprints"))
    diar = [
        {"start": 0, "end": 10, "speaker": "SPEAKER_00"},
        {"start": 10, "end": 20, "speaker": "SPEAKER_01"}
    ]

    with patch('pipeline.qc_agent.AudioSegment') as mock_audio, \
         patch('pathlib.Path.mkdir') as mock_mkdir, \
         patch('pathlib.Path.write_text') as mock_write:

        # Простая настройка мока
        mock_audio_instance = MagicMock()
        mock_audio.from_wav.return_value = mock_audio_instance

        # Мокаем empty() чтобы возвращать объект с нужными методами
        mock_empty = MagicMock()
        mock_empty.__len__.return_value = 10000  # Достаточно длинный
        mock_audio.empty.return_value = mock_empty

        agent.extract_voiceprints(Path("test.wav"), diar)

        # Проверяем основные вызовы
        mock_mkdir.assert_called_once()
        mock_write.assert_called_once()
        mock_audio.from_wav.assert_called_once_with(Path("test.wav"))
