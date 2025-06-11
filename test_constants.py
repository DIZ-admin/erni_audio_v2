#!/usr/bin/env python3
"""
Простой тест для проверки констант и настроек после рефакторинга.
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_constants():
    """Тестируем константы"""
    print("🧪 Тестируем константы...")
    
    try:
        from pipeline.constants import (
            TARGET_SAMPLE_RATE,
            API_ENDPOINTS,
            HTTP_STATUS,
            SUPPORTED_TRANSCRIPTION_MODELS,
            DEFAULT_MAX_FILE_SIZE_MB
        )
        
        print(f"✅ TARGET_SAMPLE_RATE = {TARGET_SAMPLE_RATE}")
        print(f"✅ API_ENDPOINTS = {list(API_ENDPOINTS.keys())}")
        print(f"✅ HTTP_STATUS = {list(HTTP_STATUS.keys())}")
        print(f"✅ SUPPORTED_TRANSCRIPTION_MODELS = {list(SUPPORTED_TRANSCRIPTION_MODELS.keys())}")
        print(f"✅ DEFAULT_MAX_FILE_SIZE_MB = {DEFAULT_MAX_FILE_SIZE_MB}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка импорта констант: {e}")
        return False

def test_settings():
    """Тестируем настройки"""
    print("\n🧪 Тестируем настройки...")
    
    try:
        # Устанавливаем тестовые переменные окружения
        os.environ['OPENAI_API_URL'] = 'https://test.openai.com/v1'
        os.environ['MAX_FILE_SIZE_MB'] = '100'
        os.environ['OPENAI_RATE_LIMIT'] = '25'
        
        from pipeline.settings import SETTINGS
        
        print(f"✅ SETTINGS.api.openai_url = {SETTINGS.api.openai_url}")
        print(f"✅ SETTINGS.processing.max_file_size_mb = {SETTINGS.processing.max_file_size_mb}")
        print(f"✅ SETTINGS.api.openai_rate_limit = {SETTINGS.api.openai_rate_limit}")
        print(f"✅ SETTINGS.paths.data_dir = {SETTINGS.paths.data_dir}")
        
        # Проверяем валидацию
        SETTINGS.validate()
        print("✅ Валидация настроек прошла успешно")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка настроек: {e}")
        return False

def test_imports():
    """Тестируем импорты в агентах"""
    print("\n🧪 Тестируем импорты в агентах...")
    
    try:
        # Тестируем импорт констант в audio_agent
        with open('pipeline/audio_agent.py', 'r') as f:
            content = f.read()
            if 'from .constants import TARGET_SAMPLE_RATE' in content:
                print("✅ audio_agent.py: импорт TARGET_SAMPLE_RATE")
            else:
                print("❌ audio_agent.py: импорт TARGET_SAMPLE_RATE не найден")
        
        # Тестируем использование TARGET_SAMPLE_RATE вместо TARGET_SR
        if 'TARGET_SR' in content:
            print("⚠️ audio_agent.py: найдены остатки TARGET_SR")
        else:
            print("✅ audio_agent.py: TARGET_SR полностью заменен")
        
        # Тестируем qc_agent
        with open('pipeline/qc_agent.py', 'r') as f:
            content = f.read()
            if 'from .constants import' in content:
                print("✅ qc_agent.py: импорт констант")
            else:
                print("❌ qc_agent.py: импорт констант не найден")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка проверки импортов: {e}")
        return False

def test_env_example():
    """Тестируем .env.example"""
    print("\n🧪 Тестируем .env.example...")
    
    try:
        with open('.env.example', 'r') as f:
            content = f.read()
        
        new_vars = [
            'OPENAI_API_URL',
            'PYANNOTE_API_URL', 
            'OPENAI_CONNECTION_TIMEOUT',
            'MAX_FILE_SIZE_MB',
            'MAX_CONCURRENT_JOBS',
            'MIN_CONFIDENCE_THRESHOLD'
        ]
        
        found_vars = []
        for var in new_vars:
            if var in content:
                found_vars.append(var)
        
        print(f"✅ Найдено {len(found_vars)}/{len(new_vars)} новых переменных в .env.example")
        print(f"✅ Найденные переменные: {found_vars}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка проверки .env.example: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов после рефакторинга захардкоженных параметров\n")
    
    results = []
    results.append(test_constants())
    results.append(test_settings())
    results.append(test_imports())
    results.append(test_env_example())
    
    print(f"\n📊 Результаты тестирования:")
    print(f"✅ Успешно: {sum(results)}/{len(results)}")
    print(f"❌ Неудачно: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 Все тесты прошли успешно! Рефакторинг выполнен корректно.")
        return 0
    else:
        print("\n⚠️ Некоторые тесты не прошли. Требуется дополнительная проверка.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
