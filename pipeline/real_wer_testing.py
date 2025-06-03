#!/usr/bin/env python3
"""
Реальное тестирование WER с использованием настоящих API вызовов
Отключает все моки и заглушки для получения реальных результатов
"""

import argparse
import logging
import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, List

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

from pipeline.transcription_quality_tester import TranscriptionQualityTester, TestScenario
from pipeline.transcription_agent import TranscriptionAgent
from pipeline.replicate_agent import ReplicateAgent


def setup_logging(verbose: bool = False) -> None:
    """Настройка подробного логирования для реального тестирования"""
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
    file_handler = logging.FileHandler('logs/real_wer_testing.log', encoding='utf-8')
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


def validate_api_keys() -> tuple:
    """Проверяет наличие и валидность API ключей"""
    openai_key = os.getenv('OPENAI_API_KEY')
    replicate_key = os.getenv('REPLICATE_API_TOKEN')
    pyannote_key = os.getenv('PYANNOTE_API_KEY')
    
    if not openai_key:
        print("❌ Ошибка: OPENAI_API_KEY не найден в переменных окружения")
        print("Установите ключ: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    if not replicate_key:
        print("⚠️ Предупреждение: REPLICATE_API_TOKEN не найден")
        print("Replicate модель будет пропущена")
    
    if not pyannote_key:
        print("⚠️ Предупреждение: PYANNOTE_API_KEY не найден")
        print("Может потребоваться для некоторых функций")
    
    print(f"✅ OpenAI API ключ: {openai_key[:10]}...")
    if replicate_key:
        print(f"✅ Replicate API ключ: {replicate_key[:10]}...")
    if pyannote_key:
        print(f"✅ Pyannote API ключ: {pyannote_key[:10]}...")
    
    return openai_key, replicate_key


def create_real_test_scenarios(use_segments: bool = True) -> List[TestScenario]:
    """Создает реальные тестовые сценарии на основе доступных файлов"""
    scenarios = []

    # Проверяем доступные аудиофайлы и их сегменты
    test_files = [
        ("data/raw/Testdatei.m4a", "Немецкая тестовая запись", "de"),
        ("data/interim/Sitzung Erweiterte GL 17.04.2025_converted.wav", "Расширенная встреча руководства", "de"),
        ("data/interim/Schongiland 3_converted.wav", "Аудиозапись Schongiland", "de"),
    ]

    for file_path, description, language in test_files:
        audio_path = Path(file_path)

        # Если используем сегменты, ищем короткие сегменты для экономии
        if use_segments:
            segment_path = audio_path.parent / f"{audio_path.stem}_segment_2.0min{audio_path.suffix}"
            if segment_path.exists():
                audio_path = segment_path
                description += " (2-минутный сегмент)"

        if audio_path.exists():
            # Ищем эталонный текст (передаем оригинальный путь для правильного поиска)
            reference_text = find_reference_text(audio_path, file_path)

            # Проверяем, что у нас есть точный эталонный текст
            accurate_reference_file = Path("data/raw") / f"{Path(file_path).stem}_accurate_reference.txt"
            if not accurate_reference_file.exists():
                print(f"⚠️ Пропускаем {audio_path.name} - нет точного эталонного текста")
                continue

            scenario = TestScenario(
                name=audio_path.stem,
                audio_file=audio_path,
                reference_text=reference_text,
                description=description,
                language=language,
                expected_speakers=2
            )
            scenarios.append(scenario)
            print(f"✅ Создан сценарий: {scenario.name}")
            print(f"   Файл: {audio_path}")
            print(f"   Размер: {audio_path.stat().st_size / (1024*1024):.2f} MB")
            print(f"   Эталонный текст: {len(reference_text)} символов")

    return scenarios


def find_reference_text(audio_path: Path, original_file_path: str = None) -> str:
    """Ищет эталонный текст для аудиофайла"""
    # Если это сегмент, извлекаем имя оригинального файла
    if original_file_path:
        original_stem = Path(original_file_path).stem
    else:
        # Если имя содержит "_segment_", извлекаем оригинальное имя
        if "_segment_" in audio_path.stem:
            original_stem = audio_path.stem.split("_segment_")[0]
        else:
            original_stem = audio_path.stem

    # Сначала проверяем точный эталонный текст с суффиксом _accurate_reference.txt
    accurate_reference_file = Path("data/raw") / f"{original_stem}_accurate_reference.txt"
    if accurate_reference_file.exists():
        return accurate_reference_file.read_text(encoding='utf-8').strip()

    # Проверяем файл с суффиксом _reference.txt
    reference_file = audio_path.parent / f"{original_stem}_reference.txt"
    if reference_file.exists():
        return reference_file.read_text(encoding='utf-8').strip()

    # Если нет готового эталона, создаем базовый
    return ("Guten Tag, das ist eine Testaufnahme für die automatische Spracherkennung. "
           "Wir testen heute verschiedene Modelle zur Transkription von deutschen Audiodateien.")


def run_real_wer_testing(scenarios: List[TestScenario], models: List[str] = None) -> Dict:
    """Запускает реальное тестирование WER"""
    logger = logging.getLogger(__name__)
    
    # Загружаем API ключи
    openai_key, replicate_key = validate_api_keys()
    
    # Создаем тестер
    tester = TranscriptionQualityTester(
        openai_api_key=openai_key,
        replicate_api_key=replicate_key
    )
    
    # Определяем модели для тестирования
    if models is None:
        models = list(TranscriptionAgent.SUPPORTED_MODELS.keys())
        if replicate_key:
            models.append("replicate-whisper-diarization")
    
    logger.info(f"🧪 Начинаю реальное тестирование WER")
    logger.info(f"📋 Сценариев: {len(scenarios)}")
    logger.info(f"🤖 Моделей: {len(models)} - {', '.join(models)}")
    
    # Запускаем тестирование
    start_time = time.time()
    
    try:
        results = tester.run_comprehensive_test(scenarios)
        
        # Добавляем метаданные о реальном тестировании
        results["test_metadata"] = {
            "test_type": "real_api_testing",
            "mocks_disabled": True,
            "total_duration": time.time() - start_time,
            "models_tested": models,
            "scenarios_count": len(scenarios)
        }
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Ошибка при реальном тестировании: {e}")
        raise


def save_real_results(results: Dict, output_dir: Path) -> None:
    """Сохраняет результаты реального тестирования"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем JSON результаты
    json_path = output_dir / "real_wer_evaluation_results.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Создаем отчет
    report_path = output_dir / "real_wer_evaluation_report.md"
    generate_real_report(results, report_path)
    
    print(f"📊 Результаты сохранены:")
    print(f"   JSON: {json_path}")
    print(f"   Отчет: {report_path}")


def generate_real_report(results: Dict, output_path: Path) -> None:
    """Генерирует отчет о реальном тестировании"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Отчет о реальном тестировании WER\n\n")
        
        # Метаданные
        metadata = results.get("test_metadata", {})
        f.write(f"**Тип тестирования:** {metadata.get('test_type', 'Неизвестно')}\n")
        f.write(f"**Моки отключены:** {metadata.get('mocks_disabled', False)}\n")
        f.write(f"**Дата:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Общее время:** {metadata.get('total_duration', 0):.2f} секунд\n")
        f.write(f"**Протестировано моделей:** {len(metadata.get('models_tested', []))}\n")
        f.write(f"**Протестировано сценариев:** {metadata.get('scenarios_count', 0)}\n\n")
        
        # Сравнительная таблица
        f.write("## Результаты реального тестирования\n\n")
        f.write("| Модель | Точность слов | WER | CER | Время (с) | Стоимость ($) | Успешность |\n")
        f.write("|--------|---------------|-----|-----|-----------|---------------|------------|\n")
        
        comparison = results.get("model_comparison", {})
        for model_name, stats in sorted(comparison.items(), key=lambda x: x[1].get("word_accuracy", 0), reverse=True):
            f.write(f"| {model_name} | {stats.get('word_accuracy', 0):.3f} | "
                   f"{stats.get('average_wer', 1):.3f} | {stats.get('average_cer', 1):.3f} | "
                   f"{stats.get('average_processing_time', 0):.2f} | "
                   f"{stats.get('average_cost_usd', 0):.4f} | "
                   f"{stats.get('success_rate', 0):.1%} |\n")
        
        # Детальные результаты
        f.write("\n## Детальные результаты по сценариям\n\n")
        for scenario_name, scenario_data in results.get("scenarios", {}).items():
            f.write(f"### {scenario_name}\n\n")
            f.write(f"**Описание:** {scenario_data['scenario_info']['description']}\n")
            f.write(f"**Язык:** {scenario_data['scenario_info'].get('language', 'Не указан')}\n")
            f.write(f"**Файл:** {scenario_data['scenario_info']['audio_file']}\n\n")
            
            for model_name, result in scenario_data.get("model_results", {}).items():
                if result.get("success", False):
                    metrics = result.get("quality_metrics", {})
                    f.write(f"- **{model_name}:** WER={metrics.get('wer', 1):.3f}, "
                           f"CER={metrics.get('cer', 1):.3f}, "
                           f"время={result.get('processing_time', 0):.2f}с, "
                           f"стоимость={result.get('estimated_cost', 'N/A')}\n")
                else:
                    f.write(f"- **{model_name}:** ❌ Ошибка - {result.get('error', 'Неизвестная ошибка')}\n")
            
            f.write("\n")


def main():
    """Основная функция для реального тестирования WER"""
    parser = argparse.ArgumentParser(
        description="Реальное тестирование WER с настоящими API вызовами",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--models',
        nargs='+',
        choices=['whisper-1', 'gpt-4o-mini-transcribe', 'gpt-4o-transcribe', 'replicate'],
        help='Конкретные модели для тестирования'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('data/interim'),
        help='Директория для сохранения результатов'
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
    
    print("🔥 РЕАЛЬНОЕ ТЕСТИРОВАНИЕ WER")
    print("=" * 50)
    print("⚠️  ВНИМАНИЕ: Используются настоящие API вызовы!")
    print("⚠️  Это может занять время и стоить денег!")
    print("=" * 50)
    
    # Создаем тестовые сценарии (используем короткие сегменты для экономии)
    scenarios = create_real_test_scenarios(use_segments=True)
    if not scenarios:
        print("❌ Не найдено доступных аудиофайлов с точными эталонными текстами")
        print("💡 Запустите сначала: python3 create_accurate_references.py")
        sys.exit(1)
    
    # Подтверждение от пользователя
    print(f"\n📋 Будет протестировано {len(scenarios)} сценариев")
    for scenario in scenarios:
        print(f"  - {scenario.name}: {scenario.description}")
    
    confirm = input("\n❓ Продолжить реальное тестирование? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Тестирование отменено пользователем")
        sys.exit(0)
    
    try:
        # Запускаем реальное тестирование
        print(f"\n🚀 Начинаю реальное тестирование...")
        results = run_real_wer_testing(scenarios, args.models)
        
        # Сохраняем результаты
        save_real_results(results, args.output_dir)
        
        # Показываем краткую сводку
        print(f"\n✅ Реальное тестирование завершено!")
        comparison = results.get("model_comparison", {})
        if comparison:
            print(f"\n🏆 Лучшие результаты по точности слов:")
            sorted_models = sorted(comparison.items(), key=lambda x: x[1].get("word_accuracy", 0), reverse=True)
            for i, (model_name, stats) in enumerate(sorted_models[:3], 1):
                print(f"  {i}. {model_name}: {stats.get('word_accuracy', 0):.3f} (WER: {stats.get('average_wer', 1):.3f})")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка при реальном тестировании: {e}")
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
