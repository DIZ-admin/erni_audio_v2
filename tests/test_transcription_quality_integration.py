#!/usr/bin/env python3
"""
Интеграционные тесты для комплексного тестирования качества транскрипции
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pipeline.transcription_quality_tester import TranscriptionQualityTester, TestScenario
from pipeline.wer_evaluator import TranscriptionResult


class TestTranscriptionQualityTesterIntegration:
    """Интеграционные тесты для TranscriptionQualityTester"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.openai_key = "test-openai-key"
        self.replicate_key = "test-replicate-key"
        
        # Создаем временный аудиофайл для тестирования
        self.temp_audio = Path("tests/assets/test_integration_audio.wav")
        self.temp_audio.parent.mkdir(parents=True, exist_ok=True)
        
        # Создаем минимальный WAV файл
        wav_header = b'RIFF' + (44).to_bytes(4, 'little') + b'WAVE'
        wav_header += b'fmt ' + (16).to_bytes(4, 'little')
        wav_header += (1).to_bytes(2, 'little')  # PCM format
        wav_header += (1).to_bytes(2, 'little')  # Mono
        wav_header += (16000).to_bytes(4, 'little')  # Sample rate
        wav_header += (32000).to_bytes(4, 'little')  # Byte rate
        wav_header += (2).to_bytes(2, 'little')  # Block align
        wav_header += (16).to_bytes(2, 'little')  # Bits per sample
        wav_header += b'data' + (0).to_bytes(4, 'little')
        
        self.temp_audio.write_bytes(wav_header)
    
    def teardown_method(self):
        """Очистка после каждого теста"""
        if self.temp_audio.exists():
            self.temp_audio.unlink()
    
    def test_tester_initialization(self):
        """Тест инициализации тестера"""
        tester = TranscriptionQualityTester(
            openai_api_key=self.openai_key,
            replicate_api_key=self.replicate_key
        )
        
        assert tester.openai_api_key == self.openai_key
        assert tester.replicate_api_key == self.replicate_key
        assert tester.replicate_available is True
        assert len(tester.openai_models) == 3  # whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe
    
    def test_tester_initialization_without_replicate(self):
        """Тест инициализации без Replicate ключа"""
        tester = TranscriptionQualityTester(
            openai_api_key=self.openai_key,
            replicate_api_key=None
        )
        
        assert tester.replicate_available is False
    
    def test_create_test_scenarios_with_real_files(self):
        """Тест создания сценариев с реальными файлами"""
        tester = TranscriptionQualityTester(self.openai_key)
        
        # Создаем тестовые файлы
        test_audio = Path("data/raw/test_audio.mp3")
        test_audio.parent.mkdir(parents=True, exist_ok=True)
        test_audio.write_bytes(b"fake audio data")
        
        test_reference = Path("data/raw/test_audio_reference.txt")
        test_reference.write_text("Тестовый эталонный текст", encoding='utf-8')
        
        try:
            scenarios = tester.create_test_scenarios()
            
            # Проверяем, что сценарии созданы
            assert len(scenarios) > 0
            
            # Проверяем структуру сценария
            scenario = scenarios[0]
            assert isinstance(scenario, TestScenario)
            assert scenario.audio_file.exists()
            assert len(scenario.reference_text) > 0
            
        finally:
            # Очистка
            if test_audio.exists():
                test_audio.unlink()
            if test_reference.exists():
                test_reference.unlink()
    
    def test_create_mock_scenarios(self):
        """Тест создания моковых сценариев"""
        tester = TranscriptionQualityTester(self.openai_key)
        
        # Удаляем реальные файлы, чтобы форсировать создание моков
        scenarios = tester._create_mock_scenarios()
        
        assert len(scenarios) > 0
        scenario = scenarios[0]
        assert scenario.name == "mock_test"
        assert scenario.language == "ru"
        assert len(scenario.reference_text) > 0
    
    @patch('pipeline.transcription_quality_tester.TranscriptionAgent')
    def test_test_openai_model_success(self, mock_agent_class):
        """Тест успешного тестирования OpenAI модели"""
        # Настройка мока
        mock_agent = Mock()
        mock_agent.estimate_cost.return_value = "$0.05"
        mock_agent.run.return_value = [
            {"text": "Тестовая транскрипция"},
            {"text": "второй сегмент"}
        ]
        mock_agent_class.return_value = mock_agent
        
        tester = TranscriptionQualityTester(self.openai_key)
        
        scenario = TestScenario(
            name="test",
            audio_file=self.temp_audio,
            reference_text="Тестовый текст",
            description="Тест"
        )
        
        result = tester.test_openai_model("whisper-1", scenario)
        
        assert isinstance(result, TranscriptionResult)
        assert result.success is True
        assert result.model_name == "whisper-1"
        assert len(result.segments) == 2
        assert result.estimated_cost == "$0.05"
        assert result.processing_time > 0
    
    @patch('pipeline.transcription_quality_tester.TranscriptionAgent')
    def test_test_openai_model_failure(self, mock_agent_class):
        """Тест неудачного тестирования OpenAI модели"""
        # Настройка мока для ошибки
        mock_agent_class.side_effect = Exception("API Error")
        
        tester = TranscriptionQualityTester(self.openai_key)
        
        scenario = TestScenario(
            name="test",
            audio_file=self.temp_audio,
            reference_text="Тестовый текст",
            description="Тест"
        )
        
        result = tester.test_openai_model("whisper-1", scenario)
        
        assert isinstance(result, TranscriptionResult)
        assert result.success is False
        assert result.error == "API Error"
        assert len(result.segments) == 0
    
    @patch('pipeline.transcription_quality_tester.ReplicateAgent')
    def test_test_replicate_model_success(self, mock_agent_class):
        """Тест успешного тестирования Replicate модели"""
        # Настройка мока
        mock_agent = Mock()
        mock_agent.estimate_cost.return_value = {"estimated_cost_usd": 0.01}
        mock_agent.run.return_value = [
            {"text": "Replicate транскрипция", "speaker": "SPEAKER_00"},
            {"text": "второй сегмент", "speaker": "SPEAKER_01"}
        ]
        mock_agent_class.return_value = mock_agent
        
        tester = TranscriptionQualityTester(self.openai_key, self.replicate_key)
        
        scenario = TestScenario(
            name="test",
            audio_file=self.temp_audio,
            reference_text="Тестовый текст",
            description="Тест",
            expected_speakers=2
        )
        
        result = tester.test_replicate_model(scenario)
        
        assert isinstance(result, TranscriptionResult)
        assert result.success is True
        assert result.model_name == "replicate-whisper-diarization"
        assert len(result.segments) == 2
        assert result.estimated_cost == "~$0.01"
    
    def test_test_replicate_model_unavailable(self):
        """Тест Replicate модели когда она недоступна"""
        tester = TranscriptionQualityTester(self.openai_key, replicate_api_key=None)
        
        scenario = TestScenario(
            name="test",
            audio_file=self.temp_audio,
            reference_text="Тестовый текст",
            description="Тест"
        )
        
        result = tester.test_replicate_model(scenario)
        assert result is None
    
    @patch('pipeline.transcription_quality_tester.TranscriptionAgent')
    @patch('pipeline.transcription_quality_tester.ReplicateAgent')
    def test_run_comprehensive_test(self, mock_replicate_class, mock_openai_class):
        """Тест комплексного тестирования"""
        # Настройка моков для OpenAI
        mock_openai_agent = Mock()
        mock_openai_agent.estimate_cost.return_value = "$0.05"
        mock_openai_agent.run.return_value = [{"text": "OpenAI результат"}]
        mock_openai_class.return_value = mock_openai_agent

        # Мокаем SUPPORTED_MODELS для правильного подсчета
        mock_openai_class.SUPPORTED_MODELS = {
            "whisper-1": {},
            "gpt-4o-mini-transcribe": {},
            "gpt-4o-transcribe": {}
        }

        # Настройка моков для Replicate
        mock_replicate_agent = Mock()
        mock_replicate_agent.estimate_cost.return_value = {"estimated_cost_usd": 0.01}
        mock_replicate_agent.run.return_value = [{"text": "Replicate результат", "speaker": "SPEAKER_00"}]
        mock_replicate_class.return_value = mock_replicate_agent

        tester = TranscriptionQualityTester(self.openai_key, self.replicate_key)
        
        # Создаем тестовые сценарии
        scenarios = [
            TestScenario(
                name="test_scenario",
                audio_file=self.temp_audio,
                reference_text="Эталонный текст для тестирования",
                description="Тестовый сценарий"
            )
        ]
        
        results = tester.run_comprehensive_test(scenarios)
        
        # Проверяем структуру результатов
        assert "test_summary" in results
        assert "scenarios" in results
        assert "model_comparison" in results
        
        # Проверяем сводку
        summary = results["test_summary"]
        assert summary["total_scenarios"] == 1
        # 3 OpenAI модели + 1 Replicate = 4 модели
        assert summary["total_models"] == 4
        assert "start_time" in summary
        assert "end_time" in summary
        assert "total_duration" in summary
        
        # Проверяем результаты сценариев
        scenario_results = results["scenarios"]["test_scenario"]
        assert "scenario_info" in scenario_results
        assert "model_results" in scenario_results
        
        # Проверяем, что OpenAI модели протестированы
        model_results = scenario_results["model_results"]
        openai_models = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
        for model in openai_models:
            assert model in model_results
            assert model_results[model]["success"] is True

        # Проверяем Replicate модель если доступна
        if tester.replicate_available:
            assert "replicate-whisper-diarization" in model_results
            assert model_results["replicate-whisper-diarization"]["success"] is True

        # Проверяем сравнение моделей
        comparison = results["model_comparison"]
        for model in openai_models:
            assert model in comparison
            model_stats = comparison[model]
            assert "success_rate" in model_stats
            assert "average_wer" in model_stats
            assert "average_cer" in model_stats
            assert "word_accuracy" in model_stats
            assert "char_accuracy" in model_stats
    
    @patch('pipeline.transcription_quality_tester.TranscriptionAgent')
    def test_generate_report(self, mock_agent_class):
        """Тест генерации отчета"""
        # Настройка мока
        mock_agent = Mock()
        mock_agent.estimate_cost.return_value = "$0.05"
        mock_agent.run.return_value = [{"text": "Тестовая транскрипция"}]
        mock_agent_class.return_value = mock_agent
        
        tester = TranscriptionQualityTester(self.openai_key)
        
        # Создаем простые результаты для тестирования
        results = {
            "test_summary": {
                "total_scenarios": 1,
                "total_models": 1,
                "start_time": 1000.0,
                "end_time": 1010.0,
                "total_duration": 10.0
            },
            "scenarios": {
                "test": {
                    "scenario_info": {
                        "name": "test",
                        "description": "Тест",
                        "reference_text": "Эталон",
                        "language": "ru"
                    },
                    "model_results": {
                        "whisper-1": {
                            "success": True,
                            "quality_metrics": {
                                "wer": 0.1,
                                "cer": 0.05,
                                "word_accuracy": 0.9,
                                "char_accuracy": 0.95
                            },
                            "processing_time": 2.0,
                            "estimated_cost": "$0.05"
                        }
                    }
                }
            },
            "model_comparison": {
                "whisper-1": {
                    "success_rate": 1.0,
                    "average_wer": 0.1,
                    "average_cer": 0.05,
                    "word_accuracy": 0.9,
                    "char_accuracy": 0.95,
                    "average_processing_time": 2.0,
                    "average_cost_usd": 0.05
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            report_path = tester.generate_report(results, output_dir)
            
            # Проверяем, что файлы созданы
            assert report_path.exists()
            assert (output_dir / "wer_evaluation_results.json").exists()
            
            # Проверяем содержимое JSON
            with open(output_dir / "wer_evaluation_results.json", 'r', encoding='utf-8') as f:
                saved_results = json.load(f)
            
            assert "evaluation_metadata" in saved_results
            assert saved_results["test_summary"]["total_scenarios"] == 1
            
            # Проверяем содержимое Markdown отчета
            report_content = report_path.read_text(encoding='utf-8')
            assert "# Отчет о качестве транскрипции" in report_content
            assert "## Сравнение моделей" in report_content
            assert "whisper-1" in report_content
            assert "0.900" in report_content  # word_accuracy


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
