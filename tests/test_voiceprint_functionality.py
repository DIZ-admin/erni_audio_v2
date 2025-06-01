"""
Тесты для voiceprint функционала
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pipeline.voiceprint_manager import VoiceprintManager
from pipeline.voiceprint_agent import VoiceprintAgent
from pipeline.identification_agent import IdentificationAgent
from pipeline.replicate_agent import ReplicateAgent


class TestVoiceprintManager:
    """Тесты для VoiceprintManager"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_voiceprints.json"
        self.manager = VoiceprintManager(self.db_path)
    
    def test_add_voiceprint(self):
        """Тест добавления voiceprint"""
        vp_id = self.manager.add_voiceprint(
            label="Test Speaker",
            voiceprint_data="base64_test_data",
            source_file="test.wav"
        )
        
        assert vp_id is not None
        assert len(vp_id) == 36  # UUID длина
        
        # Проверяем, что voiceprint сохранен
        voiceprint = self.manager.get_voiceprint(vp_id)
        assert voiceprint is not None
        assert voiceprint["label"] == "Test Speaker"
        assert voiceprint["voiceprint"] == "base64_test_data"
    
    def test_get_voiceprint_by_label(self):
        """Тест получения voiceprint по имени"""
        self.manager.add_voiceprint("John Doe", "data1")
        self.manager.add_voiceprint("Jane Smith", "data2")
        
        voiceprint = self.manager.get_voiceprint_by_label("John Doe")
        assert voiceprint is not None
        assert voiceprint["label"] == "John Doe"
        assert voiceprint["voiceprint"] == "data1"
        
        # Тест case-insensitive поиска
        voiceprint = self.manager.get_voiceprint_by_label("john doe")
        assert voiceprint is not None
    
    def test_search_voiceprints(self):
        """Тест поиска voiceprints"""
        self.manager.add_voiceprint("John Doe", "data1")
        self.manager.add_voiceprint("Jane Smith", "data2")
        self.manager.add_voiceprint("Bob Johnson", "data3")
        
        # Поиск по части имени
        results = self.manager.search_voiceprints("John")
        assert len(results) == 2  # John Doe и Bob Johnson
        
        # Поиск по точному имени
        results = self.manager.search_voiceprints("Jane Smith")
        assert len(results) == 1
        assert results[0]["label"] == "Jane Smith"
    
    def test_delete_voiceprint(self):
        """Тест удаления voiceprint"""
        vp_id = self.manager.add_voiceprint("Test Speaker", "data")
        
        # Проверяем, что voiceprint существует
        assert self.manager.get_voiceprint(vp_id) is not None
        
        # Удаляем
        result = self.manager.delete_voiceprint(vp_id)
        assert result is True
        
        # Проверяем, что voiceprint удален
        assert self.manager.get_voiceprint(vp_id) is None
        
        # Попытка удалить несуществующий
        result = self.manager.delete_voiceprint("nonexistent")
        assert result is False
    
    def test_get_voiceprints_for_identification(self):
        """Тест получения voiceprints для идентификации"""
        self.manager.add_voiceprint("John Doe", "data1")
        self.manager.add_voiceprint("Jane Smith", "data2")
        
        voiceprints = self.manager.get_voiceprints_for_identification(["John Doe", "Jane Smith"])
        
        assert len(voiceprints) == 2
        assert voiceprints[0]["label"] == "John Doe"
        assert voiceprints[0]["voiceprint"] == "data1"
        assert voiceprints[1]["label"] == "Jane Smith"
        assert voiceprints[1]["voiceprint"] == "data2"
        
        # Тест с несуществующим voiceprint
        voiceprints = self.manager.get_voiceprints_for_identification(["John Doe", "Nonexistent"])
        assert len(voiceprints) == 1
    
    def test_statistics(self):
        """Тест статистики"""
        # Пустая база
        stats = self.manager.get_statistics()
        assert stats["total"] == 0
        assert stats["labels"] == []
        
        # Добавляем voiceprints
        self.manager.add_voiceprint("John Doe", "data1")
        self.manager.add_voiceprint("Jane Smith", "data2")
        
        stats = self.manager.get_statistics()
        assert stats["total"] == 2
        assert "John Doe" in stats["labels"]
        assert "Jane Smith" in stats["labels"]
        assert stats["database_path"] == str(self.db_path)


class TestVoiceprintAgent:
    """Тесты для VoiceprintAgent"""
    
    @patch('pipeline.voiceprint_agent.PyannoteMediaAgent')
    @patch('requests.post')
    @patch('requests.get')
    def test_create_voiceprint_success(self, mock_get, mock_post, mock_media_agent):
        """Тест успешного создания voiceprint"""
        # Настройка моков
        mock_media_instance = Mock()
        mock_media_instance.upload_file.return_value = "media://example/test.wav"
        mock_media_agent.return_value = mock_media_instance
        
        # Mock POST запроса (создание job)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "test-job-id"}
        
        # Mock GET запроса (проверка статуса)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {"voiceprint": "base64_voiceprint_data"}
        }
        
        # Создаем тестовый файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            test_file = Path(f.name)
            f.write(b"fake audio data")
        
        try:
            agent = VoiceprintAgent("test_api_key")
            result = agent.create_voiceprint(test_file, "Test Speaker")
            
            assert result["label"] == "Test Speaker"
            assert result["voiceprint"] == "base64_voiceprint_data"
            assert "created_at" in result
            assert "duration" in result
            
        finally:
            test_file.unlink()
    
    def test_validate_audio_file(self):
        """Тест валидации аудиофайла"""
        agent = VoiceprintAgent("test_api_key")
        
        # Тест несуществующего файла
        with pytest.raises(FileNotFoundError):
            agent._validate_audio_file(Path("nonexistent.wav"))
    
    def test_estimate_cost(self):
        """Тест оценки стоимости"""
        # Создаем тестовый файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            test_file = Path(f.name)
            f.write(b"fake audio data" * 1000)  # ~13KB
        
        try:
            agent = VoiceprintAgent("test_api_key")
            cost_info = agent.estimate_cost(test_file)
            
            assert "estimated_cost_usd" in cost_info
            assert "file_size_mb" in cost_info
            assert "note" in cost_info
            assert cost_info["estimated_cost_usd"] > 0
            
        finally:
            test_file.unlink()


class TestIdentificationAgent:
    """Тесты для IdentificationAgent"""
    
    @patch('pipeline.identification_agent.PyannoteMediaAgent')
    @patch('requests.post')
    @patch('requests.get')
    def test_identification_success(self, mock_get, mock_post, mock_media_agent):
        """Тест успешной идентификации"""
        # Настройка моков
        mock_media_instance = Mock()
        mock_media_instance.upload_file.return_value = "media://example/test.wav"
        mock_media_agent.return_value = mock_media_instance
        
        # Mock POST запроса (создание job)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"jobId": "test-job-id"}
        
        # Mock GET запроса (проверка статуса)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "succeeded",
            "output": {
                "diarization": [
                    {"start": 0.0, "end": 5.0, "speaker": "John Doe", "confidence": 0.9},
                    {"start": 5.0, "end": 10.0, "speaker": "Jane Smith", "confidence": 0.8}
                ]
            }
        }
        
        # Создаем тестовый файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            test_file = Path(f.name)
            f.write(b"fake audio data")
        
        try:
            agent = IdentificationAgent("test_api_key")
            voiceprints = [
                {"label": "John Doe", "voiceprint": "base64_data1"},
                {"label": "Jane Smith", "voiceprint": "base64_data2"}
            ]
            
            segments = agent.run(test_file, voiceprints)
            
            assert len(segments) == 2
            assert segments[0]["speaker"] == "John Doe"
            assert segments[0]["confidence"] == 0.9
            assert segments[1]["speaker"] == "Jane Smith"
            assert segments[1]["confidence"] == 0.8
            
        finally:
            test_file.unlink()


class TestReplicateAgent:
    """Тесты для ReplicateAgent"""
    
    @patch('pipeline.replicate_agent.replicate')
    def test_replicate_success(self, mock_replicate):
        """Тест успешной обработки через Replicate"""
        # Настройка мока
        mock_client = Mock()
        mock_replicate.Client.return_value = mock_client
        
        mock_output = Mock()
        mock_output.segments = [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Hello world",
                "speaker": "SPEAKER_00",
                "avg_logprob": -0.2,
                "words": []
            }
        ]
        mock_client.run.return_value = mock_output
        
        # Создаем тестовый файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            test_file = Path(f.name)
            f.write(b"fake audio data")
        
        try:
            agent = ReplicateAgent("test_api_token")
            segments = agent.run(test_file)
            
            assert len(segments) == 1
            assert segments[0]["text"] == "Hello world"
            assert segments[0]["speaker"] == "SPEAKER_00"
            assert segments[0]["start"] == 0.0
            assert segments[0]["end"] == 5.0
            
        finally:
            test_file.unlink()
    
    def test_estimate_cost(self):
        """Тест оценки стоимости Replicate"""
        # Создаем тестовый файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            test_file = Path(f.name)
            f.write(b"fake audio data" * 1000)  # ~13KB
        
        try:
            agent = ReplicateAgent("test_api_token")
            cost_info = agent.estimate_cost(test_file)
            
            assert "estimated_cost_usd" in cost_info
            assert "file_size_mb" in cost_info
            assert "note" in cost_info
            assert cost_info["estimated_cost_usd"] > 0
            
        finally:
            test_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__])
