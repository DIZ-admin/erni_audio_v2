#!/usr/bin/env python3
"""
CLI скрипт для комплексного тестирования качества транскрипции
Запускает тестирование всех доступных моделей и генерирует отчет с WER/CER метриками
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.transcription_quality_tester import TranscriptionQualityTester, TestScenario


def setup_logging(verbose: bool = False) -> None:
    """Настройка логирования"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/transcription_quality_test.log', encoding='utf-8')
        ]
    )
    
    # Создаем директорию для логов
    Path('logs').mkdir(exist_ok=True)


def load_api_keys() -> tuple:
    """Загружает API ключи из переменных окружения"""
    openai_key = os.getenv('OPENAI_API_KEY')
    replicate_key = os.getenv('REPLICATE_API_TOKEN')
    
    if not openai_key:
        print("❌ Ошибка: OPENAI_API_KEY не найден в переменных окружения")
        print("Установите ключ: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    if not replicate_key:
        print("⚠️ Предупреждение: REPLICATE_API_TOKEN не найден")
        print("Replicate модель будет пропущена")
        print("Для включения Replicate установите: export REPLICATE_API_TOKEN='your-token-here'")
    
    return openai_key, replicate_key


def create_custom_scenarios(audio_files: list, reference_texts: list) -> list:
    """Создает пользовательские тестовые сценарии"""
    scenarios = []
    
    for i, audio_file in enumerate(audio_files):
        audio_path = Path(audio_file)
        if not audio_path.exists():
            print(f"❌ Аудиофайл не найден: {audio_file}")
            continue
        
        # Используем предоставленный эталонный текст или создаем базовый
        if i < len(reference_texts):
            reference_text = reference_texts[i]
        else:
            reference_text = f"Эталонный текст для {audio_path.name} не предоставлен"
        
        scenario = TestScenario(
            name=audio_path.stem,
            audio_file=audio_path,
            reference_text=reference_text,
            description=f"Пользовательский тест для {audio_path.name}",
            language=None,  # Автоопределение
            expected_speakers=None  # Автоопределение
        )
        scenarios.append(scenario)
        print(f"✅ Добавлен сценарий: {scenario.name}")
    
    return scenarios


def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Комплексное тестирование качества транскрипции",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

1. Автоматическое тестирование с доступными файлами:
   python transcription_quality_test.py

2. Тестирование конкретных файлов:
   python transcription_quality_test.py --audio-files audio1.wav audio2.mp3

3. Тестирование с эталонными текстами:
   python transcription_quality_test.py --audio-files audio.wav --reference-texts "Привет мир"

4. Подробный вывод:
   python transcription_quality_test.py --verbose

5. Сохранение в конкретную директорию:
   python transcription_quality_test.py --output-dir results/

Переменные окружения:
- OPENAI_API_KEY: Обязательный ключ OpenAI API
- REPLICATE_API_TOKEN: Опциональный токен Replicate API
        """
    )
    
    parser.add_argument(
        '--audio-files',
        nargs='+',
        help='Список аудиофайлов для тестирования'
    )
    
    parser.add_argument(
        '--reference-texts',
        nargs='+',
        help='Эталонные тексты для аудиофайлов (в том же порядке)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('data/interim'),
        help='Директория для сохранения результатов (по умолчанию: data/interim)'
    )
    
    parser.add_argument(
        '--models',
        nargs='+',
        choices=['whisper-1', 'gpt-4o-mini-transcribe', 'gpt-4o-transcribe', 'replicate'],
        help='Конкретные модели для тестирования (по умолчанию: все доступные)'
    )
    
    parser.add_argument(
        '--language',
        help='Код языка для транскрипции (например: en, ru, de)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробный вывод логов'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать план тестирования без выполнения'
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    print("🧪 Комплексное тестирование качества транскрипции")
    print("=" * 60)
    
    # Загружаем API ключи
    openai_key, replicate_key = load_api_keys()
    
    # Создаем тестер
    tester = TranscriptionQualityTester(
        openai_api_key=openai_key,
        replicate_api_key=replicate_key
    )
    
    # Создаем тестовые сценарии
    if args.audio_files:
        scenarios = create_custom_scenarios(args.audio_files, args.reference_texts or [])
        if not scenarios:
            print("❌ Не удалось создать тестовые сценарии")
            sys.exit(1)
    else:
        print("📋 Создаю автоматические тестовые сценарии...")
        scenarios = tester.create_test_scenarios()
        if not scenarios:
            print("❌ Не найдено доступных аудиофайлов для тестирования")
            print("Используйте --audio-files для указания конкретных файлов")
            sys.exit(1)
    
    # Показываем план тестирования
    print(f"\n📋 План тестирования:")
    print(f"Сценариев: {len(scenarios)}")
    for scenario in scenarios:
        print(f"  - {scenario.name}: {scenario.description}")
    
    available_models = tester.openai_models.copy()
    if tester.replicate_available:
        available_models.append("replicate-whisper-diarization")
    
    if args.models:
        # Фильтруем модели
        filtered_models = []
        for model in args.models:
            if model == "replicate":
                if tester.replicate_available:
                    filtered_models.append("replicate-whisper-diarization")
            elif model in tester.openai_models:
                filtered_models.append(model)
        available_models = filtered_models
    
    print(f"Модели: {', '.join(available_models)}")
    print(f"Выходная директория: {args.output_dir}")
    
    if args.dry_run:
        print("\n🔍 Режим dry-run: план показан, тестирование не выполняется")
        return
    
    # Запускаем тестирование
    print(f"\n🚀 Начинаю тестирование...")
    try:
        results = tester.run_comprehensive_test(scenarios)
        
        # Генерируем отчет
        print(f"\n📊 Генерирую отчет...")
        report_path = tester.generate_report(results, args.output_dir)
        
        # Показываем краткую сводку
        print(f"\n✅ Тестирование завершено!")
        print(f"📄 Отчет сохранен: {report_path}")
        print(f"📊 JSON результаты: {args.output_dir / 'wer_evaluation_results.json'}")
        
        # Показываем топ-3 модели по точности
        comparison = results["model_comparison"]
        if comparison:
            print(f"\n🏆 Топ-3 модели по точности слов:")
            sorted_models = sorted(comparison.items(), key=lambda x: x[1]["word_accuracy"], reverse=True)
            for i, (model_name, stats) in enumerate(sorted_models[:3], 1):
                print(f"  {i}. {model_name}: {stats['word_accuracy']:.3f} (WER: {stats['average_wer']:.3f})")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}")
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
