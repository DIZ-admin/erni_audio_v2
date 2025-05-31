#!/usr/bin/env python3
# smoke_test.py

"""
Smoke test для проверки основной функциональности Speech Pipeline.

Этот тест проверяет, что система может:
1. Загрузить и сконвертировать аудио файл
2. Выполнить базовую валидацию
3. Инициализировать все агенты
4. Обработать мок данные через весь пайплайн

Использование:
    python smoke_test.py                    # Базовый smoke test
    python smoke_test.py --with-api-keys    # Тест с реальными API ключами
    python smoke_test.py --create-sample    # Создать тестовый аудио файл
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def create_test_audio_file(output_path: Path) -> None:
    """Создает простой тестовый WAV файл"""
    # Простой WAV заголовок для 1 секунды моно аудио 16kHz
    wav_header = (
        b'RIFF'
        b'\x24\x08\x00\x00'  # Размер файла - 8
        b'WAVE'
        b'fmt '
        b'\x10\x00\x00\x00'  # Размер fmt chunk
        b'\x01\x00'          # PCM формат
        b'\x01\x00'          # Моно
        b'\x80\x3e\x00\x00'  # 16000 Hz
        b'\x00\x7d\x00\x00'  # Byte rate
        b'\x02\x00'          # Block align
        b'\x10\x00'          # Bits per sample
        b'data'
        b'\x00\x08\x00\x00'  # Размер данных
    )
    
    # Простые аудио данные (тишина)
    audio_data = b'\x00\x00' * 16000  # 1 секунда тишины
    
    with open(output_path, 'wb') as f:
        f.write(wav_header + audio_data)
    
    print(f"✅ Создан тестовый аудио файл: {output_path}")


def test_basic_imports():
    """Тест базовых импортов"""
    print("🔍 Проверка импортов...")
    
    try:
        from pipeline.audio_agent import AudioLoaderAgent
        from pipeline.diarization_agent import DiarizationAgent
        from pipeline.transcription_agent import TranscriptionAgent
        from pipeline.merge_agent import MergeAgent
        from pipeline.export_agent import ExportAgent
        from pipeline.security_validator import SECURITY_VALIDATOR
        from pipeline.rate_limiter import PYANNOTE_RATE_LIMITER
        from pipeline.monitoring import PERFORMANCE_MONITOR
        print("✅ Все модули импортированы успешно")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False


def test_security_validation():
    """Тест системы валидации безопасности"""
    print("🔒 Проверка валидации безопасности...")
    
    try:
        from pipeline.security_validator import SECURITY_VALIDATOR
        
        # Тест валидации URL
        is_valid, message = SECURITY_VALIDATOR.validate_url("https://example.com/test.wav")
        if not is_valid:
            print(f"❌ URL валидация не работает: {message}")
            return False
        
        # Тест валидации небезопасного URL
        is_valid, message = SECURITY_VALIDATOR.validate_url("http://example.com/test.wav")
        if is_valid:
            print("❌ HTTP URL должен быть отклонен")
            return False
        
        print("✅ Валидация безопасности работает")
        return True
    except Exception as e:
        print(f"❌ Ошибка валидации безопасности: {e}")
        return False


def test_rate_limiting():
    """Тест системы rate limiting"""
    print("⏱️ Проверка rate limiting...")
    
    try:
        from pipeline.rate_limiter import PYANNOTE_RATE_LIMITER, OPENAI_RATE_LIMITER
        
        # Проверяем, что rate limiters инициализированы
        pyannote_remaining = PYANNOTE_RATE_LIMITER.get_remaining_requests("test")
        openai_remaining = OPENAI_RATE_LIMITER.get_remaining_requests("test")
        
        if pyannote_remaining <= 0 or openai_remaining <= 0:
            print("❌ Rate limiters не инициализированы корректно")
            return False
        
        print(f"✅ Rate limiting работает (Pyannote: {pyannote_remaining}, OpenAI: {openai_remaining})")
        return True
    except Exception as e:
        print(f"❌ Ошибка rate limiting: {e}")
        return False


def test_audio_conversion():
    """Тест конвертации аудио"""
    print("🎵 Проверка конвертации аудио...")
    
    try:
        # Создаем временный аудио файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            create_test_audio_file(Path(tmp_file.name))
            
            from pipeline.audio_agent import AudioLoaderAgent
            
            # Мокируем API ключ и валидацию
            with patch('pipeline.pyannote_media_agent.PyannoteMediaAgent.validate_api_key') as mock_validate:
                mock_validate.return_value = True
                
                agent = AudioLoaderAgent(pyannote_api_key="test_key")
                
                # Тестируем конвертацию
                converted_path = agent.to_wav16k_mono(tmp_file.name)
                
                if not converted_path.exists():
                    print("❌ Конвертированный файл не создан")
                    return False
                
                print("✅ Конвертация аудио работает")
                
                # Очистка
                os.unlink(tmp_file.name)
                if converted_path.exists():
                    os.unlink(converted_path)
                
                return True
                
    except Exception as e:
        print(f"❌ Ошибка конвертации аудио: {e}")
        return False


def test_pipeline_integration():
    """Тест интеграции пайплайна с мок данными"""
    print("🔗 Проверка интеграции пайплайна...")
    
    try:
        from pipeline.merge_agent import MergeAgent
        from pipeline.export_agent import ExportAgent
        
        # Мок данные
        mock_diarization = [
            {"start": 0.0, "end": 2.5, "speaker": "SPEAKER_00", "confidence": 0.95},
            {"start": 2.5, "end": 5.0, "speaker": "SPEAKER_01", "confidence": 0.90}
        ]
        
        mock_transcription = [
            {"start": 0.0, "end": 2.5, "text": "Привет, как дела?"},
            {"start": 2.5, "end": 5.0, "text": "Всё хорошо, спасибо!"}
        ]
        
        # Тест объединения
        merge_agent = MergeAgent()
        merged_segments = merge_agent.run(mock_diarization, mock_transcription)
        
        if len(merged_segments) != 2:
            print(f"❌ Неправильное количество сегментов: {len(merged_segments)}")
            return False
        
        # Тест экспорта
        export_agent = ExportAgent("srt")
        
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp_file:
            export_agent.run(merged_segments, Path(tmp_file.name))
            
            if not Path(tmp_file.name).exists():
                print("❌ Экспортированный файл не создан")
                return False
            
            # Проверяем содержимое
            with open(tmp_file.name, 'r', encoding='utf-8') as f:
                content = f.read()
                if "Привет, как дела?" not in content:
                    print("❌ Неправильное содержимое экспорта")
                    return False
            
            print("✅ Интеграция пайплайна работает")
            
            # Очистка
            os.unlink(tmp_file.name)
            return True
            
    except Exception as e:
        print(f"❌ Ошибка интеграции пайплайна: {e}")
        return False


def test_with_api_keys():
    """Тест с реальными API ключами (если доступны)"""
    print("🔑 Проверка API ключей...")
    
    pyannote_key = os.getenv("PYANNOTEAI_API_TOKEN") or os.getenv("PYANNOTE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not pyannote_key:
        print("⚠️ API ключ Pyannote не найден (PYANNOTEAI_API_TOKEN)")
        return False
    
    if not openai_key:
        print("⚠️ API ключ OpenAI не найден (OPENAI_API_KEY)")
        return False
    
    try:
        from pipeline.pyannote_media_agent import PyannoteMediaAgent
        
        # Тест валидации Pyannote ключа
        agent = PyannoteMediaAgent(pyannote_key)
        if not agent.validate_api_key():
            print("❌ Неверный API ключ Pyannote")
            return False
        
        print("✅ API ключи валидны")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки API ключей: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Smoke test для Speech Pipeline")
    parser.add_argument("--with-api-keys", action="store_true", help="Тест с реальными API ключами")
    parser.add_argument("--create-sample", action="store_true", help="Создать тестовый аудио файл")
    
    args = parser.parse_args()
    
    print("🚀 Speech Pipeline Smoke Test")
    print("=" * 50)
    
    if args.create_sample:
        sample_path = Path("samples/smoke_test.wav")
        sample_path.parent.mkdir(exist_ok=True)
        create_test_audio_file(sample_path)
        return
    
    # Список тестов
    tests = [
        ("Импорты", test_basic_imports),
        ("Валидация безопасности", test_security_validation),
        ("Rate limiting", test_rate_limiting),
        ("Конвертация аудио", test_audio_conversion),
        ("Интеграция пайплайна", test_pipeline_integration),
    ]
    
    if args.with_api_keys:
        tests.append(("API ключи", test_with_api_keys))
    
    # Запуск тестов
    passed = 0
    total = len(tests)
    
    start_time = time.time()
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ Тест '{test_name}' провален")
    
    end_time = time.time()
    
    # Результаты
    print("\n" + "=" * 50)
    print(f"📊 Результаты: {passed}/{total} тестов прошли")
    print(f"⏱️ Время выполнения: {end_time - start_time:.2f}s")
    
    if passed == total:
        print("🎉 Все smoke тесты прошли успешно!")
        print("✅ Система готова к базовому использованию")
        sys.exit(0)
    else:
        print("⚠️ Некоторые тесты провалены")
        print("❌ Система требует доработки")
        sys.exit(1)


if __name__ == "__main__":
    main()
