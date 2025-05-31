import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from pipeline.export_agent import ExportAgent

def test_init():
    agent = ExportAgent(format="srt")
    assert agent.format == "srt"
    
    agent = ExportAgent(format="json")
    assert agent.format == "json"
    
    agent = ExportAgent(format="ass")
    assert agent.format == "ass"
    
    with pytest.raises(AssertionError):
        ExportAgent(format="invalid")

def test_ts_srt():
    agent = ExportAgent()
    assert agent._ts_srt(3661.5) == "01:01:01,500"
    assert agent._ts_srt(0.123) == "00:00:00,123"

def test_ts_ass():
    agent = ExportAgent()
    assert agent._ts_ass(3661.5) == "1:01:01.50"
    assert agent._ts_ass(0.123) == "0:00:00.12"  # 0.123 секунды = 12.3 сантисекунды = 12 cs
    assert agent._ts_ass(0.01) == "0:00:00.01"   # 0.01 секунды = 1 сантисекунда

def test_write_json():
    agent = ExportAgent(format="json")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]
    
    with patch('pathlib.Path.write_text') as mock_write:
        agent.write_json(segs, Path("output.json"))
        mock_write.assert_called_once()

def test_write_srt():
    agent = ExportAgent(format="srt")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]
    
    with patch('builtins.open', mock_open()) as mock_file:
        agent.write_srt(segs, Path("output.srt"))
        mock_file.assert_called_once_with(Path("output.srt"), "w", encoding="utf-8")
        handle = mock_file()
        handle.write.assert_any_call("1\n00:00:00,000 --> 00:00:01,000\n")
        handle.write.assert_any_call("SPEAKER_00: Hello\n\n")

def test_write_ass():
    agent = ExportAgent(format="ass")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]

    with patch('builtins.open', mock_open()) as mock_file:
        agent.write_ass(segs, Path("output.ass"))
        mock_file.assert_called_once_with(Path("output.ass"), "w", encoding="utf-8")
        handle = mock_file()

        # Проверяем, что было два вызова write: заголовок и диалог
        assert handle.write.call_count == 2

        # Проверяем содержимое первого вызова (заголовок)
        first_call = handle.write.call_args_list[0][0][0]
        assert "[Script Info]" in first_call
        assert "Title: speech_pipeline export" in first_call

        # Проверяем содержимое второго вызова (диалог)
        second_call = handle.write.call_args_list[1][0][0]
        assert "Dialogue: 0,0:00:00.00,0:00:01.00,Default,SPEAKER_00,0,0,0,,Hello" in second_call

def test_run_srt():
    agent = ExportAgent(format="srt")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]
    
    with patch.object(agent, 'write_srt') as mock_write:
        agent.run(segs, Path("output.srt"))
        mock_write.assert_called_once_with(segs, Path("output.srt"))

def test_run_json():
    agent = ExportAgent(format="json")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]
    
    with patch.object(agent, 'write_json') as mock_write:
        agent.run(segs, Path("output.json"))
        mock_write.assert_called_once_with(segs, Path("output.json"))

def test_run_ass():
    agent = ExportAgent(format="ass")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]
    
    with patch.object(agent, 'write_ass') as mock_write:
        agent.run(segs, Path("output.ass"))
        mock_write.assert_called_once_with(segs, Path("output.ass"))
