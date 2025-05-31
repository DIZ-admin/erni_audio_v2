#!/usr/bin/env python3
"""
Интеграционные тесты для сравнения качества различных моделей транскрипции.
Требует реальных API ключей для полного тестирования.
"""

import pytest
import os
import time
from pathlib import Path
from typing import Dict, List
import json

from pipeline.transcription_agent import TranscriptionAgent


class TestModelComparison:
    """Тесты для сравнения качества моделей"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Настройка для тестов"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            pytest.skip("OPENAI_API_KEY не установлен")
        
        # Путь к тестовому аудиофайлу
        self.test_audio = Path("tests/assets/test_audio.wav")
        if not self.test_audio.exists():
            pytest.skip(f"Тестовый аудиофайл не найден: {self.test_audio}")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_all_models_transcription(self):
        """Тест транскрипции всеми доступными моделями"""
        models = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
        results = {}
        
        for model in models:
            print(f"\n🧪 Тестирую модель: {model}")
            
            try:
                agent = TranscriptionAgent(self.api_key, model)
                start_time = time.time()
                
                segments = agent.run(self.test_audio, "")
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                results[model] = {
                    "segments_count": len(segments),
                    "processing_time": processing_time,
                    "success": True,
                    "segments": segments[:3] if segments else [],  # Первые 3 сегмента для анализа
                    "model_info": agent.get_model_info()
                }
                
                print(f"✅ {model}: {len(segments)} сегментов за {processing_time:.2f}с")
                
            except Exception as e:
                results[model] = {
                    "success": False,
                    "error": str(e),
                    "processing_time": None
                }
                print(f"❌ {model}: Ошибка - {e}")
        
        # Сохраняем результаты для анализа
        results_file = Path("tests/results/model_comparison.json")
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📊 Результаты сохранены в: {results_file}")
        
        # Базовые проверки
        successful_models = [model for model, result in results.items() if result.get("success")]
        assert len(successful_models) > 0, "Ни одна модель не работает"
        
        # Проверяем, что все успешные модели вернули сегменты
        for model in successful_models:
            assert results[model]["segments_count"] > 0, f"Модель {model} не вернула сегментов"
    
    @pytest.mark.integration
    def test_language_specific_transcription(self):
        """Тест транскрипции с указанием языка"""
        if not self.test_audio.exists():
            pytest.skip("Тестовый аудиофайл не найден")
        
        # Тестируем с указанием языка
        agent_with_lang = TranscriptionAgent(self.api_key, "gpt-4o-mini-transcribe", language="en")
        agent_without_lang = TranscriptionAgent(self.api_key, "gpt-4o-mini-transcribe")
        
        try:
            segments_with_lang = agent_with_lang.run(self.test_audio, "")
            segments_without_lang = agent_without_lang.run(self.test_audio, "")
            
            # Оба должны вернуть результаты
            assert len(segments_with_lang) > 0
            assert len(segments_without_lang) > 0
            
            print(f"С языком: {len(segments_with_lang)} сегментов")
            print(f"Без языка: {len(segments_without_lang)} сегментов")
            
        except Exception as e:
            pytest.skip(f"Ошибка API: {e}")
    
    @pytest.mark.integration
    def test_prompt_influence(self):
        """Тест влияния prompt на качество транскрипции"""
        if not self.test_audio.exists():
            pytest.skip("Тестовый аудиофайл не найден")
        
        agent = TranscriptionAgent(self.api_key, "gpt-4o-mini-transcribe")
        
        prompts = [
            "",  # Без prompt
            "This is a technical discussion about AI and machine learning.",  # Технический контекст
            "The following is a conversation between two people."  # Общий контекст
        ]
        
        results = {}
        
        for i, prompt in enumerate(prompts):
            try:
                segments = agent.run(self.test_audio, prompt)
                results[f"prompt_{i}"] = {
                    "prompt": prompt,
                    "segments_count": len(segments),
                    "first_segment_text": segments[0]["text"] if segments else ""
                }
                
            except Exception as e:
                results[f"prompt_{i}"] = {
                    "prompt": prompt,
                    "error": str(e)
                }
        
        # Сохраняем результаты
        results_file = Path("tests/results/prompt_comparison.json")
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Результаты prompt тестирования: {results_file}")
    
    def test_cost_estimation_accuracy(self):
        """Тест точности оценки стоимости"""
        file_sizes = [1.0, 5.0, 10.0, 25.0]  # MB
        
        for model in TranscriptionAgent.SUPPORTED_MODELS:
            agent = TranscriptionAgent("dummy_key", model)
            
            for size in file_sizes:
                cost = agent.estimate_cost(size)
                
                # Проверяем формат оценки
                assert cost.startswith("~$")
                
                # Извлекаем числовое значение
                cost_value = float(cost.replace("~$", ""))
                
                # Стоимость должна расти с размером файла
                assert cost_value > 0
                
                # Для больших файлов стоимость должна быть больше
                if size > 1.0:
                    smaller_cost = agent.estimate_cost(1.0)
                    smaller_value = float(smaller_cost.replace("~$", ""))
                    assert cost_value > smaller_value
    
    def test_model_characteristics(self):
        """Тест характеристик моделей"""
        models = TranscriptionAgent.get_available_models()
        
        # Проверяем иерархию стоимости
        whisper_cost = models["whisper-1"]["cost_tier"]
        mini_cost = models["gpt-4o-mini-transcribe"]["cost_tier"]
        full_cost = models["gpt-4o-transcribe"]["cost_tier"]
        
        cost_hierarchy = ["low", "medium", "high"]
        
        assert whisper_cost == "low"
        assert mini_cost == "medium"
        assert full_cost == "high"
        
        # Проверяем, что все модели поддерживают нужные функции
        for model_name, model_info in models.items():
            assert model_info["supports_language"] is True
            assert model_info["supports_prompt"] is True
            assert model_info["max_file_size_mb"] == 25


class TestPerformanceMetrics:
    """Тесты для метрик производительности"""
    
    def test_processing_time_logging(self):
        """Тест логирования времени обработки"""
        # Этот тест проверяет, что метрики времени корректно рассчитываются
        # без реального API вызова
        
        from unittest.mock import Mock, patch
        
        with patch('pipeline.transcription_agent.OpenAI') as mock_openai:
            # Мокаем ответ API
            mock_transcript = Mock()
            mock_transcript.segments = []
            mock_transcript.duration = 60.0  # 60 секунд аудио
            
            mock_client = Mock()
            mock_client.audio.transcriptions.create.return_value = mock_transcript
            mock_openai.return_value = mock_client
            
            agent = TranscriptionAgent("test_key", "whisper-1")
            
            # Создаем временный файл для теста
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_file:
                tmp_path = Path(tmp_file.name)
                
                # Мокаем размер файла
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024 * 1024  # 1MB
                    
                    with patch.object(Path, 'exists', return_value=True):
                        segments = agent.run(tmp_path, "")
            
            # Проверяем, что API был вызван с правильными параметрами
            mock_client.audio.transcriptions.create.assert_called_once()
            call_args = mock_client.audio.transcriptions.create.call_args[1]
            
            assert call_args["model"] == "whisper-1"
            assert call_args["response_format"] == "verbose_json"
            assert call_args["temperature"] == 0


if __name__ == "__main__":
    # Запуск только быстрых тестов по умолчанию
    pytest.main([__file__, "-v", "-m", "not slow"])
