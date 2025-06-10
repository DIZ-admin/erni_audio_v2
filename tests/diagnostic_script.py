#!/usr/bin/env python3
"""
Диагностический скрипт для проверки окружения Erni_audio_v2
"""

import sys
import os
import json
from pathlib import Path

def main():
    print("🔍 Диагностика окружения Erni_audio_v2")
    print("=" * 50)
    
    # 1. Проверка Python
    print(f"🐍 Python version: {sys.version}")
    print(f"📁 Working directory: {os.getcwd()}")
    
    # 2. Проверка структуры проекта
    print("\n📂 Структура проекта:")
    required_dirs = ["pipeline", "data", "voiceprints", "logs"]
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ❌ {dir_name}/ - отсутствует")
    
    # 3. Проверка аудиофайла
    print("\n🎵 Аудиофайл:")
    audio_file = Path("data/raw/Sitzung Erweiterte GL 17.04.2025.m4a")
    if audio_file.exists():
        size_mb = audio_file.stat().st_size / (1024 * 1024)
        print(f"  ✅ {audio_file.name} ({size_mb:.1f} MB)")
    else:
        print(f"  ❌ {audio_file.name} - не найден")
    
    # 4. Проверка API ключей
    print("\n🔑 API ключи:")
    api_keys = {
        "PYANNOTEAI_API_TOKEN": os.getenv("PYANNOTEAI_API_TOKEN"),
        "PYANNOTE_API_KEY": os.getenv("PYANNOTE_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "REPLICATE_API_TOKEN": os.getenv("REPLICATE_API_TOKEN")
    }
    
    for key_name, key_value in api_keys.items():
        if key_value:
            masked_key = key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "***"
            print(f"  ✅ {key_name}: {masked_key}")
        else:
            print(f"  ❌ {key_name}: не установлен")
    
    # 5. Проверка voiceprints
    print("\n👥 Voiceprints:")
    vp_file = Path("voiceprints/voiceprints.json")
    if vp_file.exists():
        try:
            with open(vp_file, 'r', encoding='utf-8') as f:
                voiceprints = json.load(f)
            print(f"  ✅ База данных: {len(voiceprints)} voiceprints")
            for vp_id, vp_data in voiceprints.items():
                print(f"    - {vp_data.get('label', 'Unknown')} (ID: {vp_id[:8]}...)")
        except Exception as e:
            print(f"  ❌ Ошибка чтения базы: {e}")
    else:
        print(f"  ❌ {vp_file} - не найден")
    
    # 6. Проверка зависимостей
    print("\n📦 Зависимости:")
    required_modules = ["requests", "pathlib", "json", "logging"]
    for module_name in required_modules:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}")
        except ImportError:
            print(f"  ❌ {module_name} - не найден")
    
    print("\n" + "=" * 50)
    print("✅ Диагностика завершена")

if __name__ == "__main__":
    main()
