#!/usr/bin/env python3
"""
Создание точных эталонных текстов для WER тестирования
Использует лучшую модель (gpt-4o-transcribe) для создания базовых транскрипций
"""

import argparse
import logging
import sys
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent))

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Если python-dotenv не установлен, пытаемся загрузить вручную
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from pipeline.transcription_agent import TranscriptionAgent


def setup_logging(verbose: bool = False) -> None:
    """Настройка логирования"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Создаем директорию для логов
    Path('logs').mkdir(exist_ok=True)
    
    # Настраиваем форматирование
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Файловый обработчик
    file_handler = logging.FileHandler('logs/create_references.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Отключаем логи библиотек для чистоты вывода
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)


def validate_api_key() -> str:
    """Проверяет наличие OpenAI API ключа"""
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_key:
        print("❌ Ошибка: OPENAI_API_KEY не найден в переменных окружения")
        print("Установите ключ: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    print(f"✅ OpenAI API ключ: {openai_key[:10]}...")
    return openai_key


def find_audio_files() -> List[Tuple[Path, str]]:
    """Находит доступные аудиофайлы для создания эталонов"""
    audio_files = []
    
    # Проверяем доступные аудиофайлы
    test_files = [
        ("data/raw/Testdatei.m4a", "Немецкая тестовая запись"),
        ("data/interim/Sitzung Erweiterte GL 17.04.2025_converted.wav", "Расширенная встреча руководства"),
        ("data/interim/Schongiland 3_converted.wav", "Аудиозапись Schongiland"),
    ]
    
    for file_path, description in test_files:
        audio_path = Path(file_path)
        if audio_path.exists():
            audio_files.append((audio_path, description))
            print(f"✅ Найден файл: {audio_path}")
            print(f"   Описание: {description}")
            print(f"   Размер: {audio_path.stat().st_size / (1024*1024):.2f} MB")
        else:
            print(f"⚠️ Файл не найден: {audio_path}")
    
    return audio_files


def extract_short_segment(audio_path: Path, duration_minutes: float = 2.5) -> Path:
    """Извлекает короткий сегмент из начала аудиофайла для создания эталона"""
    logger = logging.getLogger(__name__)
    
    # Создаем имя для короткого сегмента
    segment_name = f"{audio_path.stem}_segment_{duration_minutes}min{audio_path.suffix}"
    segment_path = audio_path.parent / segment_name
    
    # Если сегмент уже существует, используем его
    if segment_path.exists():
        logger.info(f"📁 Используем существующий сегмент: {segment_path}")
        return segment_path
    
    try:
        logger.info(f"✂️ Извлекаю {duration_minutes} минут из {audio_path.name}...")

        # Конвертируем в WAV и обрезаем
        duration_seconds = int(duration_minutes * 60)
        
        # Используем ffmpeg для извлечения сегмента
        import subprocess
        
        cmd = [
            'ffmpeg', '-i', str(audio_path),
            '-t', str(duration_seconds),
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            str(segment_path),
            '-y'  # Перезаписать если существует
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ Сегмент создан: {segment_path}")
            logger.info(f"   Размер: {segment_path.stat().st_size / (1024*1024):.2f} MB")
            return segment_path
        else:
            logger.error(f"❌ Ошибка ffmpeg: {result.stderr}")
            # Если ffmpeg не работает, используем оригинальный файл
            logger.warning(f"⚠️ Используем оригинальный файл: {audio_path}")
            return audio_path
            
    except Exception as e:
        logger.error(f"❌ Ошибка при извлечении сегмента: {e}")
        logger.warning(f"⚠️ Используем оригинальный файл: {audio_path}")
        return audio_path


def create_reference_transcription(audio_path: Path, openai_key: str) -> str:
    """Создает эталонную транскрипцию с помощью лучшей модели"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"🎯 Создаю эталонную транскрипцию для: {audio_path.name}")
    
    try:
        # Используем лучшую модель для создания эталона
        agent = TranscriptionAgent(
            api_key=openai_key,
            model="gpt-4o-transcribe"
        )
        
        # Транскрибируем файл
        start_time = time.time()
        segments = agent.run(audio_path)
        processing_time = time.time() - start_time

        if segments:
            logger.info(f"✅ Транскрипция завершена за {processing_time:.2f}с")
            logger.info(f"   Сегментов: {len(segments)}")

            # Собираем текст из сегментов
            text = " ".join([segment.get('text', '') for segment in segments])
            logger.info(f"   Символов: {len(text)}")

            return text.strip()
        else:
            logger.error(f"❌ Ошибка транскрипции: пустой результат")
            return ""
            
    except Exception as e:
        logger.error(f"❌ Ошибка при создании эталона: {e}")
        return ""


def save_reference_text(audio_path: Path, reference_text: str) -> Path:
    """Сохраняет эталонный текст в файл"""
    logger = logging.getLogger(__name__)
    
    # Создаем имя файла для эталонного текста
    reference_filename = f"{audio_path.stem}_accurate_reference.txt"
    reference_path = Path("data/raw") / reference_filename
    
    # Создаем директорию если не существует
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(reference_path, 'w', encoding='utf-8') as f:
            f.write(reference_text)
        
        logger.info(f"💾 Эталонный текст сохранен: {reference_path}")
        logger.info(f"   Длина: {len(reference_text)} символов")
        logger.info(f"   Слов: {len(reference_text.split())} слов")
        
        return reference_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении эталона: {e}")
        raise


def create_all_references(duration_minutes: float = 2.5, force_recreate: bool = False) -> Dict[str, Path]:
    """Создает эталонные тексты для всех доступных аудиофайлов"""
    logger = logging.getLogger(__name__)
    
    # Проверяем API ключ
    openai_key = validate_api_key()
    
    # Находим аудиофайлы
    audio_files = find_audio_files()
    if not audio_files:
        logger.error("❌ Не найдено аудиофайлов для создания эталонов")
        return {}
    
    logger.info(f"📋 Будет создано {len(audio_files)} эталонных текстов")
    logger.info(f"⏱️ Длительность сегментов: {duration_minutes} минут")
    
    # Подтверждение от пользователя
    if not force_recreate:
        confirm = input(f"\n❓ Продолжить создание эталонов? Это может стоить ~${len(audio_files) * 0.5:.2f} (y/N): ")
        if confirm.lower() != 'y':
            logger.info("❌ Создание эталонов отменено пользователем")
            return {}
    
    created_references = {}
    total_cost = 0.0
    
    for i, (audio_path, description) in enumerate(audio_files, 1):
        logger.info(f"\n🔄 Обрабатываю файл {i}/{len(audio_files)}: {audio_path.name}")
        
        try:
            # Проверяем, существует ли уже эталонный текст
            reference_filename = f"{audio_path.stem}_accurate_reference.txt"
            reference_path = Path("data/raw") / reference_filename
            
            if reference_path.exists() and not force_recreate:
                logger.info(f"📁 Эталонный текст уже существует: {reference_path}")
                created_references[audio_path.stem] = reference_path
                continue
            
            # Извлекаем короткий сегмент
            segment_path = extract_short_segment(audio_path, duration_minutes)
            
            # Создаем эталонную транскрипцию
            reference_text = create_reference_transcription(segment_path, openai_key)
            
            if reference_text:
                # Сохраняем эталонный текст
                saved_path = save_reference_text(audio_path, reference_text)
                created_references[audio_path.stem] = saved_path
                
                # Оценка стоимости (примерно)
                estimated_cost = len(reference_text) / 1000 * 0.024  # Примерная стоимость gpt-4o-transcribe
                total_cost += estimated_cost
                
                logger.info(f"💰 Примерная стоимость: ${estimated_cost:.3f}")
            else:
                logger.error(f"❌ Не удалось создать эталон для {audio_path.name}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке {audio_path.name}: {e}")
            continue
    
    logger.info(f"\n✅ Создание эталонов завершено!")
    logger.info(f"📊 Создано эталонов: {len(created_references)}")
    logger.info(f"💰 Общая примерная стоимость: ${total_cost:.3f}")
    
    return created_references


def main():
    """Основная функция для создания эталонных текстов"""
    parser = argparse.ArgumentParser(
        description="Создание точных эталонных текстов для WER тестирования",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--duration',
        type=float,
        default=2.5,
        help='Длительность сегментов в минутах (по умолчанию: 2.5)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Пересоздать эталоны даже если они уже существуют'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробный вывод логов'
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    print("🎯 СОЗДАНИЕ ТОЧНЫХ ЭТАЛОННЫХ ТЕКСТОВ")
    print("=" * 50)
    print("⚠️  ВНИМАНИЕ: Используются настоящие API вызовы!")
    print("⚠️  Это может занять время и стоить денег!")
    print("=" * 50)
    
    try:
        # Создаем эталонные тексты
        created_references = create_all_references(
            duration_minutes=args.duration,
            force_recreate=args.force
        )
        
        if created_references:
            print(f"\n🎉 Успешно создано {len(created_references)} эталонных текстов:")
            for name, path in created_references.items():
                print(f"  ✅ {name}: {path}")
            
            print(f"\n📁 Все эталонные тексты сохранены в директории: data/raw/")
            print(f"📝 Теперь можно запустить точное WER тестирование!")
        else:
            print(f"\n❌ Не удалось создать эталонные тексты")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Создание эталонов прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка при создании эталонов: {e}")
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
