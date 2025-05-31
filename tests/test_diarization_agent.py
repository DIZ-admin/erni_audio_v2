import pytest
from unittest.mock import patch, MagicMock
from pipeline.diarization_agent import DiarizationAgent

def test_init():
    agent = DiarizationAgent(api_key="test_key", use_identify=True, voiceprint_ids=["id1", "id2"])
    assert agent.headers["Authorization"] == "Bearer test_key"
    assert agent.use_identify is True
    assert agent.voiceprint_ids == ["id1", "id2"]

def test_poll():
    agent = DiarizationAgent(api_key="test_key")
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "completed",
            "result": {"diarization": [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        result = agent._poll("job123")
        assert result == {"diarization": [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]}
        mock_get.assert_called_once()

def test_diarize():
    agent = DiarizationAgent(api_key="test_key")
    with patch('requests.post') as mock_post, patch.object(agent, '_poll') as mock_poll:
        mock_response = MagicMock()
        mock_response.json.return_value = {"jobId": "job123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        mock_poll.return_value = {"diarization": [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]}
        
        result = agent.diarize("https://example.com/audio.wav")
        assert result == [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]
        mock_post.assert_called_once()
        mock_poll.assert_called_once_with("job123")

def test_identify():
    agent = DiarizationAgent(api_key="test_key", use_identify=True, voiceprint_ids=["id1", "id2"])
    with patch('requests.post') as mock_post, patch.object(agent, '_poll') as mock_poll:
        mock_response = MagicMock()
        mock_response.json.return_value = {"jobId": "job123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        mock_poll.return_value = {"diarization": [{"start": 0, "end": 1, "speaker": "id1"}]}
        
        result = agent.identify("https://example.com/audio.wav")
        assert result == [{"start": 0, "end": 1, "speaker": "id1"}]
        mock_post.assert_called_once()
        mock_poll.assert_called_once_with("job123")

def test_run_diarize():
    agent = DiarizationAgent(api_key="test_key", use_identify=False)
    with patch.object(agent, 'diarize') as mock_diarize:
        mock_diarize.return_value = [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]
        
        result = agent.run("https://example.com/audio.wav")
        assert result == [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}]
        mock_diarize.assert_called_once_with("https://example.com/audio.wav")

def test_run_identify():
    agent = DiarizationAgent(api_key="test_key", use_identify=True, voiceprint_ids=["id1"])
    with patch.object(agent, 'identify') as mock_identify:
        mock_identify.return_value = [{"start": 0, "end": 1, "speaker": "id1"}]
        
        result = agent.run("https://example.com/audio.wav")
        assert result == [{"start": 0, "end": 1, "speaker": "id1"}]
        mock_identify.assert_called_once_with("https://example.com/audio.wav")
