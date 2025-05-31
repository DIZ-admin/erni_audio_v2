#!/usr/bin/env python3
"""
Простой тест интеграции gpt-4o-transcribe
"""

import sys
import os
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

def test_transcription_agent_import():
    """Тест импорта TranscriptionAgent"""
    try:
        from pipeline.transcription_agent import TranscriptionAgent
        print("✅ Импорт TranscriptionAgent успешен")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_supported_models():
    """Тест списка поддерживаемых моделей"""
    try:
        from pipeline.transcription_agent import TranscriptionAgent
        
        models = TranscriptionAgent.get_available_models()
        print(f"✅ Найдено {len(models)} моделей:")
        
        for model_name, model_info in models.items():
            print(f"  - {model_name}: {model_info['name']} ({model_info['cost_tier']} cost)")
        
        # Проверяем наличие ожидаемых моделей
        expected_models = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
        for model in expected_models:
            if model in models:
                print(f"✅ Модель {model} найдена")
            else:
                print(f"❌ Модель {model} не найдена")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Ошибка тестирования моделей: {e}")
        return False

def test_agent_creation():
    """Тест создания агентов с разными моделями"""
    try:
        from pipeline.transcription_agent import TranscriptionAgent
        
        models_to_test = ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
        
        for model in models_to_test:
            try:
                agent = TranscriptionAgent("test_api_key", model, language="en")
                model_info = agent.get_model_info()
                print(f"✅ Агент {model} создан: {model_info['name']}")
                
                # Тест оценки стоимости
                cost = agent.estimate_cost(10.0)
                print(f"  💰 Оценка стоимости для 10MB: {cost}")
                
            except Exception as e:
                print(f"❌ Ошибка создания агента {model}: {e}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Ошибка тестирования создания агентов: {e}")
        return False

def test_config_integration():
    """Тест интеграции с конфигурацией"""
    try:
        # Устанавливаем временные переменные окружения
        os.environ['OPENAI_API_KEY'] = 'test_key'
        os.environ['PYANNOTE_API_KEY'] = 'test_key'
        
        from pipeline.config import ConfigurationManager, TranscriptionConfig
        
        config_manager = ConfigurationManager()
        
        # Тест получения конфигурации транскрипции
        transcription_config = config_manager.get_transcription_config()
        print(f"✅ Конфигурация транскрипции получена: модель {transcription_config.model}")
        
        # Тест установки модели
        config_manager.set_transcription_model("gpt-4o-transcribe")
        updated_config = config_manager.get_transcription_config()
        print(f"✅ Модель обновлена на: {updated_config.model}")
        
        # Тест получения информации о модели
        model_info = config_manager.get_transcription_model_info()
        print(f"✅ Информация о модели: {model_info['name']}")
        
        # Тест оценки стоимости
        estimates = config_manager.estimate_transcription_cost(5.0)
        print("✅ Оценки стоимости для всех моделей:")
        for model, cost in estimates.items():
            print(f"  - {model}: {cost}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка тестирования конфигурации: {e}")
        return False

def test_command_line_args():
    """Тест аргументов командной строки"""
    try:
        import argparse
        
        # Имитируем парсер аргументов из speech_pipeline.py
        parser = argparse.ArgumentParser()
        parser.add_argument("input")
        parser.add_argument("--transcription-model", 
                           choices=["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"],
                           default="whisper-1")
        parser.add_argument("--language")
        parser.add_argument("--show-cost-estimate", action="store_true")
        
        # Тест парсинга аргументов
        test_args = ["test.wav", "--transcription-model", "gpt-4o-transcribe", "--language", "en"]
        args = parser.parse_args(test_args)
        
        print(f"✅ Аргументы распарсены:")
        print(f"  - Модель: {args.transcription_model}")
        print(f"  - Язык: {args.language}")
        print(f"  - Показать стоимость: {args.show_cost_estimate}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка тестирования аргументов: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🧪 Тестирование интеграции gpt-4o-transcribe")
    print("=" * 50)
    
    tests = [
        ("Импорт модулей", test_transcription_agent_import),
        ("Поддерживаемые модели", test_supported_models),
        ("Создание агентов", test_agent_creation),
        ("Интеграция с конфигурацией", test_config_integration),
        ("Аргументы командной строки", test_command_line_args),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}:")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - ПРОЙДЕН")
            else:
                print(f"❌ {test_name} - ПРОВАЛЕН")
        except Exception as e:
            print(f"❌ {test_name} - ОШИБКА: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        return 0
    else:
        print("⚠️  Некоторые тесты провалены")
        return 1

if __name__ == "__main__":
    exit(main())
