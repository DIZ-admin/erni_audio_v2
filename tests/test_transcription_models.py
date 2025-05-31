#!/usr/bin/env python3
"""
Тесты для поддержки различных моделей транскрипции.
Проверяет функциональность gpt-4o-transcribe и других моделей.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from pipeline.transcription_agent import TranscriptionAgent
from pipeline.config import ConfigurationManager, TranscriptionConfig


class TestTranscriptionModels:
    """Тесты для различных моделей транскрипции"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.api_key = "test_api_key"
        self.test_audio_file = Path("tests/assets/test_audio.wav")
        
    def test_supported_models_list(self):
        """Тест списка поддерживаемых моделей"""
        models = TranscriptionAgent.get_available_models()
        
        # Проверяем, что все ожидаемые модели присутствуют
        expected_models = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
        for model in expected_models:
            assert model in models
            
        # Проверяем структуру информации о модели
        for model_name, model_info in models.items():
            assert "name" in model_info
            assert "description" in model_info
            assert "max_file_size_mb" in model_info
            assert "cost_tier" in model_info
            assert model_info["cost_tier"] in ["low", "medium", "high"]
    
    def test_model_validation(self):
        """Тест валидации моделей"""
        # Валидная модель
        agent = TranscriptionAgent(self.api_key, "whisper-1")
        assert agent.model == "whisper-1"
        
        # Невалидная модель
        with pytest.raises(ValueError, match="Неподдерживаемая модель"):
            TranscriptionAgent(self.api_key, "invalid-model")
    
    def test_model_info(self):
        """Тест получения информации о модели"""
        agent = TranscriptionAgent(self.api_key, "gpt-4o-transcribe", language="en")
        info = agent.get_model_info()
        
        assert info["model"] == "gpt-4o-transcribe"
        assert info["language"] == "en"
        assert info["name"] == "GPT-4o Transcribe"
        assert info["cost_tier"] == "high"
    
    def test_language_setting(self):
        """Тест установки языка"""
        agent = TranscriptionAgent(self.api_key, "whisper-1")
        
        # Изначально язык не установлен
        assert agent.language is None
        
        # Устанавливаем язык
        agent.set_language("ru")
        assert agent.language == "ru"
        
        # Сбрасываем язык
        agent.set_language(None)
        assert agent.language is None
    
    def test_cost_estimation(self):
        """Тест оценки стоимости"""
        agent = TranscriptionAgent(self.api_key, "whisper-1")
        cost = agent.estimate_cost(10.0)  # 10MB файл
        
        assert cost.startswith("~$")
        assert "0.060" in cost  # Примерная стоимость для whisper-1
        
        # Тест для более дорогой модели
        agent_expensive = TranscriptionAgent(self.api_key, "gpt-4o-transcribe")
        cost_expensive = agent_expensive.estimate_cost(10.0)
        
        assert cost_expensive.startswith("~$")
        # Должна быть дороже whisper-1
        cost_value = float(cost.replace("~$", ""))
        cost_expensive_value = float(cost_expensive.replace("~$", ""))
        assert cost_expensive_value > cost_value
    
    @patch('pipeline.transcription_agent.OpenAI')
    def test_transcription_params_preparation(self, mock_openai):
        """Тест подготовки параметров транскрипции"""
        agent = TranscriptionAgent(self.api_key, "gpt-4o-transcribe", language="en")
        
        # Тест с prompt
        params = agent._prepare_transcription_params("test prompt")
        expected_params = {
            "response_format": "verbose_json",
            "temperature": 0,
            "prompt": "test prompt",
            "language": "en"
        }
        assert params == expected_params
        
        # Тест без prompt
        params_no_prompt = agent._prepare_transcription_params("")
        assert "prompt" not in params_no_prompt
        assert params_no_prompt["language"] == "en"
    
    @patch('pipeline.transcription_agent.OpenAI')
    def test_file_validation(self, mock_openai):
        """Тест валидации файлов"""
        agent = TranscriptionAgent(self.api_key, "whisper-1")
        
        # Тест с несуществующим файлом
        with pytest.raises(FileNotFoundError):
            agent._validate_audio_file(Path("nonexistent.wav"))
        
        # Создаем временный файл для тестирования размера
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            # Создаем файл размером больше лимита (25MB)
            tmp_file.write(b"0" * (26 * 1024 * 1024))  # 26MB
            tmp_path = Path(tmp_file.name)
        
        try:
            with pytest.raises(ValueError, match="превышает максимальный"):
                agent._validate_audio_file(tmp_path)
        finally:
            tmp_path.unlink()  # Удаляем временный файл
    
    @patch('pipeline.transcription_agent.OpenAI')
    def test_transcript_response_processing(self, mock_openai):
        """Тест обработки ответа транскрипции"""
        agent = TranscriptionAgent(self.api_key, "gpt-4o-transcribe")
        
        # Мокаем ответ с segments
        mock_segment = Mock()
        mock_segment.model_dump.return_value = {
            "id": 0,
            "start": 0.0,
            "end": 5.0,
            "text": "Test transcription",
            "tokens": [1, 2, 3],
            "avg_logprob": -0.5,
            "no_speech_prob": 0.1
        }
        
        mock_transcript = Mock()
        mock_transcript.segments = [mock_segment]
        
        segments = agent._process_transcript_response(mock_transcript)
        
        assert len(segments) == 1
        assert segments[0]["text"] == "Test transcription"
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 5.0


class TestTranscriptionConfig:
    """Тесты для конфигурации транскрипции"""
    
    def test_default_config(self):
        """Тест конфигурации по умолчанию"""
        config = TranscriptionConfig()
        
        assert config.model == "whisper-1"
        assert config.language is None
        assert config.prompt == ""
        assert config.temperature == 0.0
        assert config.enable_cost_estimation is True
        assert config.fallback_model == "whisper-1"
    
    def test_custom_config(self):
        """Тест кастомной конфигурации"""
        config = TranscriptionConfig(
            model="gpt-4o-transcribe",
            language="ru",
            prompt="Это русский текст",
            temperature=0.1,
            enable_cost_estimation=False,
            fallback_model="gpt-4o-mini-transcribe"
        )
        
        assert config.model == "gpt-4o-transcribe"
        assert config.language == "ru"
        assert config.prompt == "Это русский текст"
        assert config.temperature == 0.1
        assert config.enable_cost_estimation is False
        assert config.fallback_model == "gpt-4o-mini-transcribe"


class TestConfigurationManager:
    """Тесты для менеджера конфигурации с поддержкой транскрипции"""
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test_openai_key',
        'PYANNOTE_API_KEY': 'test_pyannote_key'
    })
    def test_transcription_config_methods(self):
        """Тест методов конфигурации транскрипции"""
        config_manager = ConfigurationManager()
        
        # Тест получения конфигурации транскрипции
        transcription_config = config_manager.get_transcription_config()
        assert isinstance(transcription_config, TranscriptionConfig)
        assert transcription_config.model == "whisper-1"
        
        # Тест установки модели
        config_manager.set_transcription_model("gpt-4o-transcribe")
        assert config_manager.get_transcription_config().model == "gpt-4o-transcribe"
        
        # Тест установки языка
        config_manager.set_transcription_language("en")
        assert config_manager.get_transcription_config().language == "en"
        
        # Тест получения информации о модели
        model_info = config_manager.get_transcription_model_info()
        assert model_info["current_model"] == "gpt-4o-transcribe"
        assert model_info["language"] == "en"
        assert model_info["name"] == "GPT-4o Transcribe"
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test_openai_key',
        'PYANNOTE_API_KEY': 'test_pyannote_key'
    })
    def test_cost_estimation(self):
        """Тест оценки стоимости через конфигурацию"""
        config_manager = ConfigurationManager()
        
        estimates = config_manager.estimate_transcription_cost(10.0)
        
        # Проверяем, что есть оценки для всех моделей
        expected_models = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
        for model in expected_models:
            assert model in estimates
            assert estimates[model].startswith("~$")
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test_openai_key',
        'PYANNOTE_API_KEY': 'test_pyannote_key'
    })
    def test_invalid_model_setting(self):
        """Тест установки невалидной модели"""
        config_manager = ConfigurationManager()
        
        with pytest.raises(Exception, match="Неподдерживаемая модель"):
            config_manager.set_transcription_model("invalid-model")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
