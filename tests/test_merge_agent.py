import pytest
import json
from pathlib import Path
from typing import List, Dict
from pipeline.merge_agent import MergeAgent

# Загружаем тестовые данные
def load_test_data():
    test_dir = Path(__file__).parent / "assets"
    with open(test_dir / "fake_diarization.json") as f:
        diar_data = json.load(f)
    with open(test_dir / "fake_whisper.json") as f:
        whisper_data = json.load(f)
    return diar_data, whisper_data

def test_init():
    agent = MergeAgent()
    # Проверяем, что агент создается без ошибок

def test_run_empty_lists():
    agent = MergeAgent()
    diar = []
    asr = []
    
    result = agent.run(diar, asr)
    assert result == []

def test_run_simple_case():
    agent = MergeAgent()
    diar = [
        {"start": 0, "end": 2, "speaker": "SPEAKER_00"},
        {"start": 2, "end": 4, "speaker": "SPEAKER_01"}
    ]
    asr = [
        {"start": 0.5, "end": 1.5, "text": "Hello world"},
        {"start": 2.5, "end": 3.5, "text": "How are you"}
    ]
    
    result = agent.run(diar, asr)
    
    assert len(result) == 2
    assert result[0]["speaker"] == "SPEAKER_00"
    assert result[0]["text"] == "Hello world"
    assert result[1]["speaker"] == "SPEAKER_01"
    assert result[1]["text"] == "How are you"

def test_run_edge_case():
    agent = MergeAgent()
    diar = [
        {"start": 0, "end": 2, "speaker": "SPEAKER_00"}
    ]
    asr = [
        {"start": 0.5, "end": 1.5, "text": "Hello world"},
        {"start": 2.5, "end": 3.5, "text": "How are you"}  # За пределами диаризации
    ]
    
    result = agent.run(diar, asr)
    
    assert len(result) == 2
    assert result[0]["speaker"] == "SPEAKER_00"
    assert result[1]["speaker"] == "UNK"  # Должен быть UNK, так как выходит за пределы диаризации

def test_run_with_test_assets():
    """Тест с использованием реальных тестовых данных"""
    agent = MergeAgent()
    diar_data, whisper_data = load_test_data()

    result = agent.run(diar_data, whisper_data)

    assert len(result) == len(whisper_data)
    assert all("speaker" in seg for seg in result)
    assert all("text" in seg for seg in result)
    assert all("start" in seg for seg in result)
    assert all("end" in seg for seg in result)

    # Проверяем, что первый сегмент правильно назначен
    assert result[0]["speaker"] == "SPEAKER_00"
    assert result[0]["text"] == "Привет, как дела?"
