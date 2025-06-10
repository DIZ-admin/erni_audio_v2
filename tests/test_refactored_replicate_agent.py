# tests/test_refactored_replicate_agent.py

import pytest
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock

# Мокаем replicate модуль для тестов
replicate_mock = MagicMock()
replicate_mock.Client = MagicMock
replicate_mock.exceptions.ReplicateError = Exception

with patch.dict('sys.modules', {'replicate': replicate_mock}):
    from pipeline.replicate_agent import ReplicateAgent


class TestRefactoredReplicateAgent:
    """Тесты для рефакторированного ReplicateAgent."""

    @pytest.fixture
    def api_token(self):
        """Создает тестовый API токен."""
        return "test_replicate_token_12345"

    @pytest.fixture
    def agent(self, api_token):
        """Создает экземпляр ReplicateAgent для тестов."""
        with patch('pipeline.replicate_agent.replicate', replicate_mock):
            return ReplicateAgent(api_token=api_token)

    @pytest.fixture
    def sample_audio_file(self):
        """Создает временный аудиофайл для тестов."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Создаем файл среднего размера (имитация аудио)
            f.write(b"fake audio data" * 5000)  # ~70KB
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Очистка
        if temp_path.exists():
            temp_path.unlink()

    def test_initialization_with_base_classes(self, agent):
        """Тест инициализации с базовыми классами."""
        # Проверяем, что агент наследует от всех базовых классов
        assert hasattr(agent, 'log_with_emoji')  # BaseAgent
        assert hasattr(agent, 'validate_audio_file')  # ValidationMixin
        
        # Проверяем инициализацию
        assert agent.name == "ReplicateAgent"
        assert agent.api_token == "test_replicate_token_12345"
        assert agent.MODEL_NAME == "thomasmol/whisper-diarization:1495a9cddc83b2203b0d8d3516e38b80fd1572ebc4bc5700ac1da56a9b3ed886"

    def test_validate_replicate_token_valid(self, agent):
        """Тест валидации корректного API токена."""
        # Валидные токены
        valid_tokens = ["test_token_123", "r8_1234567890abcdef", "replicate_api_token_long_enough"]
        
        for token in valid_tokens:
            agent.validate_replicate_token(token)  # Не должно вызывать ошибок

    def test_validate_replicate_token_invalid(self, agent):
        """Тест валидации некорректного API токена."""
        # Пустой токен
        with pytest.raises(ValueError, match="API токен не может быть пустым"):
            agent.validate_replicate_token("")
        
        # Слишком короткий
        with pytest.raises(ValueError, match="API токен слишком короткий"):
            agent.validate_replicate_token("short")
        
        # Неправильный тип
        with pytest.raises(ValueError, match="API токен должен быть строкой"):
            agent.validate_replicate_token(123)

    def test_validate_replicate_params_valid(self, agent, sample_audio_file):
        """Тест валидации корректных параметров Replicate."""
        issues = agent.validate_replicate_params(
            sample_audio_file, num_speakers=2, language="en", prompt="Test prompt"
        )
        assert len(issues) == 0

    def test_validate_replicate_params_invalid_num_speakers(self, agent, sample_audio_file):
        """Тест валидации некорректного num_speakers."""
        # Отрицательное число
        issues = agent.validate_replicate_params(sample_audio_file, num_speakers=-1)
        assert len(issues) >= 1
        assert any("должно быть больше 0" in issue for issue in issues)
        
        # Слишком большое число
        issues = agent.validate_replicate_params(sample_audio_file, num_speakers=100)
        assert len(issues) >= 1
        assert any("слишком большое" in issue for issue in issues)

    def test_validate_replicate_params_invalid_language(self, agent, sample_audio_file):
        """Тест валидации некорректного языка."""
        # Неподдерживаемый язык
        issues = agent.validate_replicate_params(sample_audio_file, language="invalid_lang")
        assert len(issues) >= 1
        assert any("Неподдерживаемый язык" in issue for issue in issues)

    def test_validate_replicate_params_invalid_prompt(self, agent, sample_audio_file):
        """Тест валидации некорректного prompt."""
        # Слишком длинный prompt
        long_prompt = "x" * 1001
        issues = agent.validate_replicate_params(sample_audio_file, prompt=long_prompt)
        assert len(issues) >= 1
        assert any("слишком длинный" in issue for issue in issues)

    def test_validate_replicate_audio_file_valid(self, agent, sample_audio_file):
        """Тест валидации корректного аудиофайла."""
        issues = agent.validate_replicate_audio_file(sample_audio_file)
        assert len(issues) == 0

    def test_validate_replicate_audio_file_too_large(self, agent):
        """Тест валидации слишком большого файла."""
        # Создаем большой файл (>500MB)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Создаем файл размером ~501MB (имитация)
            chunk = b"x" * (1024 * 1024)  # 1MB
            for _ in range(501):  # 501MB > 500MB
                f.write(chunk)
            large_file = Path(f.name)
        
        try:
            issues = agent.validate_replicate_audio_file(large_file)
            assert len(issues) >= 1
            assert any("слишком большой" in issue for issue in issues)
        finally:
            if large_file.exists():
                large_file.unlink()

    def test_supported_languages(self, agent):
        """Тест поддерживаемых языков."""
        expected_languages = ["auto", "en", "de", "fr", "es", "it", "pt", "ru", "zh", "ja", "ko"]
        
        for lang in expected_languages:
            assert lang in agent.SUPPORTED_LANGUAGES
        
        # Проверяем, что все языки имеют описания
        for lang, description in agent.SUPPORTED_LANGUAGES.items():
            assert isinstance(description, str)
            assert len(description) > 0

    @patch('builtins.open', create=True)
    def test_run_with_performance_metrics(self, mock_open, agent, sample_audio_file):
        """Тест выполнения с отслеживанием метрик производительности."""
        # Мокаем файл
        mock_file = MagicMock()
        mock_open.return_value = mock_file
        
        # Мокаем ответ Replicate
        mock_output = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello world",
                    "speaker": "SPEAKER_00",
                    "avg_logprob": -0.5,
                    "words": []
                }
            ]
        }
        
        agent.client.run = Mock(return_value=mock_output)
        
        # Выполняем обработку
        result = agent.run(sample_audio_file, num_speakers=2, language="en")
        
        # Проверяем результат
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["speaker"] == "SPEAKER_00"
        
        # Проверяем, что метрики были обновлены
        assert agent._operation_count > 0
        assert agent._error_count == 0
        
        # Проверяем метрики производительности
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] >= 1
        assert metrics['success_rate'] == 100.0

    def test_run_with_error_handling(self, agent):
        """Тест обработки ошибок через BaseAgent."""
        # Передаем некорректные данные
        nonexistent_file = Path("/nonexistent/file.wav")
        
        # Должно обработать ошибки gracefully
        with pytest.raises(Exception):
            agent.run(nonexistent_file)
        
        # Проверяем, что ошибка была зарегистрирована
        assert agent._error_count > 0

    def test_unified_logging_usage(self, agent):
        """Тест использования унифицированного логирования."""
        # Проверяем, что метод log_with_emoji доступен
        assert hasattr(agent, 'log_with_emoji')
        
        # Тестируем вызов (не должен вызывать ошибок)
        agent.log_with_emoji("info", "🎯", "Test message")

    @patch('builtins.open', create=True)
    def test_prepare_input_params(self, mock_open, agent, sample_audio_file):
        """Тест подготовки параметров для Replicate."""
        mock_file = MagicMock()
        mock_open.return_value = mock_file
        
        params = agent._prepare_input_params(
            sample_audio_file, num_speakers=3, language="en", prompt="Test prompt"
        )
        
        assert "file" in params
        assert params["file_url"] == ""
        assert params["num_speakers"] == 3
        assert params["language"] == "en"
        assert params["prompt"] == "Test prompt"

    def test_process_output_dict_format(self, agent):
        """Тест обработки вывода в формате словаря."""
        output = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Test text",
                    "speaker": "SPEAKER_00",
                    "avg_logprob": -0.3
                }
            ]
        }
        
        result = agent._process_output(output)
        
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 2.0
        assert result[0]["text"] == "Test text"
        assert result[0]["speaker"] == "SPEAKER_00"

    def test_process_output_list_format(self, agent):
        """Тест обработки вывода в формате списка."""
        output = [
            {
                "start": 1.0,
                "end": 3.0,
                "text": "Another test",
                "speaker": "SPEAKER_01"
            }
        ]
        
        result = agent._process_output(output)
        
        assert len(result) == 1
        assert result[0]["start"] == 1.0
        assert result[0]["text"] == "Another test"

    def test_process_output_empty(self, agent):
        """Тест обработки пустого вывода."""
        output = {"segments": []}
        
        result = agent._process_output(output)
        
        assert result == []

    def test_process_output_invalid_format(self, agent):
        """Тест обработки некорректного формата вывода."""
        output = "invalid format"
        
        with pytest.raises(ValueError, match="Некорректный ответ от Replicate API"):
            agent._process_output(output)

    def test_estimate_cost(self, agent, sample_audio_file):
        """Тест оценки стоимости."""
        cost_info = agent.estimate_cost(sample_audio_file)
        
        assert isinstance(cost_info, dict)
        assert "estimated_cost_usd" in cost_info
        assert "base_cost_usd" in cost_info
        assert "file_size_mb" in cost_info
        assert "note" in cost_info
        
        assert cost_info["base_cost_usd"] == 0.0077
        assert isinstance(cost_info["estimated_cost_usd"], float)
        assert cost_info["estimated_cost_usd"] > 0

    def test_validation_mixin_integration(self, agent):
        """Тест интеграции ValidationMixin."""
        # Проверяем доступность методов ValidationMixin
        assert hasattr(agent, 'validate_language_code')
        assert hasattr(agent, 'validate_voiceprint_ids')
        
        # Тестируем валидацию языкового кода
        valid_lang = agent.validate_language_code("en")
        assert valid_lang == "en"

    def test_error_handling_comprehensive(self, agent):
        """Тест комплексной обработки ошибок."""
        # Тестируем обработку ошибки без reraise
        test_error = ValueError("Test error")
        agent.handle_error(test_error, "test_operation", reraise=False)
        
        assert agent._error_count == 1
        assert agent._last_error == test_error

    @patch('builtins.open', create=True)
    def test_performance_tracking(self, mock_open, agent, sample_audio_file):
        """Тест отслеживания производительности."""
        mock_file = MagicMock()
        mock_open.return_value = mock_file
        
        # Мокаем ответ Replicate
        mock_output = {"segments": [{"start": 0, "end": 1, "text": "test", "speaker": "SPEAKER_00"}]}
        agent.client.run = Mock(return_value=mock_output)
        
        # Выполняем несколько операций
        for i in range(3):
            agent.run(sample_audio_file)
        
        # Проверяем метрики
        metrics = agent.log_performance_metrics()
        assert metrics['operation_count'] == 3
        assert metrics['total_processing_time'] > 0
        assert metrics['success_rate'] == 100.0

    def test_model_name_constant(self, agent):
        """Тест константы имени модели."""
        expected_model = "thomasmol/whisper-diarization:1495a9cddc83b2203b0d8d3516e38b80fd1572ebc4bc5700ac1da56a9b3ed886"
        assert agent.MODEL_NAME == expected_model

    def test_replicate_import_error(self):
        """Тест обработки отсутствия библиотеки replicate."""
        with patch('pipeline.replicate_agent.replicate', None):
            with pytest.raises(ImportError, match="Библиотека replicate не установлена"):
                ReplicateAgent("test_token")
