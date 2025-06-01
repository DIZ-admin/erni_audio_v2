import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from pipeline.export_agent import ExportAgent

def test_init():
    agent = ExportAgent(format="srt")
    assert agent.format == "srt"
    assert agent.create_all_formats == False

    agent = ExportAgent(format="json")
    assert agent.format == "json"
    assert agent.create_all_formats == False

    agent = ExportAgent(format="ass")
    assert agent.format == "ass"
    assert agent.create_all_formats == False

    agent = ExportAgent(format="srt", create_all_formats=True)
    assert agent.format == "srt"
    assert agent.create_all_formats == True

    with pytest.raises(AssertionError):
        ExportAgent(format="invalid")

def test_ts_srt():
    agent = ExportAgent()
    assert agent._ts_srt(3661.5) == "01:01:01,500"
    assert agent._ts_srt(0.123) == "00:00:00,123"

def test_ts_ass():
    agent = ExportAgent()
    assert agent._ts_ass(3661.5) == "1:01:01.50"

def test_ensure_correct_extension():
    agent = ExportAgent()

    # Тест для SRT
    assert agent._ensure_correct_extension(Path("test"), "srt") == Path("test.srt")
    assert agent._ensure_correct_extension(Path("test.srt"), "srt") == Path("test.srt")
    assert agent._ensure_correct_extension(Path("test.txt"), "srt") == Path("test.srt")

    # Тест для JSON
    assert agent._ensure_correct_extension(Path("test"), "json") == Path("test.json")
    assert agent._ensure_correct_extension(Path("test.json"), "json") == Path("test.json")
    assert agent._ensure_correct_extension(Path("test.txt"), "json") == Path("test.json")

    # Тест для ASS
    assert agent._ensure_correct_extension(Path("test"), "ass") == Path("test.ass")
    assert agent._ensure_correct_extension(Path("test.ass"), "ass") == Path("test.ass")
    assert agent._ensure_correct_extension(Path("test.txt"), "ass") == Path("test.ass")
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
        created_files = agent.run(segs, Path("output.ass"))
        mock_write.assert_called_once_with(segs, Path("output.ass"))
        assert len(created_files) == 1

def test_run_create_all_formats():
    agent = ExportAgent(format="srt", create_all_formats=True)
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]

    with patch.object(agent, 'write_srt') as mock_srt, \
         patch.object(agent, 'write_json') as mock_json, \
         patch.object(agent, 'write_ass') as mock_ass:

        created_files = agent.run(segs, Path("output"))

        # Проверяем, что все три метода были вызваны
        mock_srt.assert_called_once_with(segs, Path("output.srt"))
        mock_json.assert_called_once_with(segs, Path("output.json"))
        mock_ass.assert_called_once_with(segs, Path("output.ass"))

        # Проверяем, что возвращены все три файла
        assert len(created_files) == 3
        assert Path("output.srt") in created_files
        assert Path("output.json") in created_files
        assert Path("output.ass") in created_files

def test_run_with_extension_correction():
    agent = ExportAgent(format="srt")
    segs = [{"start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "Hello"}]

    with patch.object(agent, 'write_srt') as mock_write:
        # Передаем файл без расширения
        created_files = agent.run(segs, Path("output"))
        # Должен быть вызван с правильным расширением
        mock_write.assert_called_once_with(segs, Path("output.srt"))
        assert len(created_files) == 1
        assert created_files[0] == Path("output.srt")
