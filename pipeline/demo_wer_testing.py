#!/usr/bin/env python3
"""
Демонстрационный скрипт для тестирования WER оценки
Показывает работу системы с моковыми данными без реальных API вызовов
"""

import logging
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.transcription_quality_tester import TranscriptionQualityTester, TestScenario
from pipeline.wer_evaluator import TranscriptionResult


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def create_demo_scenarios():
    """Создает демонстрационные сценарии для тестирования"""
    scenarios = []
    
    # Сценарий 1: Русский текст
    scenarios.append(TestScenario(
        name="russian_business_meeting",
        audio_file=Path("demo_audio_ru.wav"),  # Фиктивный файл
        reference_text="Добро пожаловать на встречу по обсуждению проекта. Сегодня мы рассмотрим основные вопросы и примем важные решения.",
        description="Деловая встреча на русском языке",
        language="ru",
        expected_speakers=2
    ))
    
    # Сценарий 2: Немецкий текст
    scenarios.append(TestScenario(
        name="german_conference",
        audio_file=Path("demo_audio_de.wav"),  # Фиктивный файл
        reference_text="Guten Tag und herzlich willkommen zur Konferenz. Heute besprechen wir die wichtigsten Themen unserer Agenda.",
        description="Конференция на немецком языке",
        language="de",
        expected_speakers=3
    ))
    
    # Сценарий 3: Английский текст
    scenarios.append(TestScenario(
        name="english_presentation",
        audio_file=Path("demo_audio_en.wav"),  # Фиктивный файл
        reference_text="Welcome to our quarterly presentation. Today we will review our achievements and discuss future plans.",
        description="Презентация на английском языке",
        language="en",
        expected_speakers=1
    ))
    
    return scenarios


def create_mock_transcription_results(reference_text: str, model_name: str):
    """Создает моковые результаты транскрипции с разным качеством"""
    
    # Симулируем разное качество для разных моделей
    if model_name == "whisper-1":
        # Хорошее качество, но с небольшими ошибками
        if "русском" in reference_text or "Добро" in reference_text:
            hypothesis = "Добро пожаловать на встречу по обсуждению проектов. Сегодня мы рассмотрим основные вопросы и примем важные решение."
        elif "Guten" in reference_text:
            hypothesis = "Guten Tag und herzlich willkommen zur Konferenz. Heute besprechen wir die wichtigsten Themen unsere Agenda."
        else:
            hypothesis = "Welcome to our quarterly presentation. Today we will review our achievements and discuss future plan."
        
        return TranscriptionResult(
            model_name=model_name,
            segments=[{"text": hypothesis}],
            processing_time=2.5,
            estimated_cost="$0.006",
            success=True
        )
    
    elif model_name == "gpt-4o-mini-transcribe":
        # Среднее качество
        if "русском" in reference_text or "Добро" in reference_text:
            hypothesis = "Добро пожаловать на встречу по обсуждению проекта. Сегодня мы рассмотрим основные вопросы и примем важные решения."
        elif "Guten" in reference_text:
            hypothesis = "Guten Tag und herzlich willkommen zur Konferenz. Heute besprechen wir wichtigsten Themen unserer Agenda."
        else:
            hypothesis = "Welcome to our quarterly presentation. Today we will review achievements and discuss future plans."
        
        return TranscriptionResult(
            model_name=model_name,
            segments=[{"text": hypothesis}],
            processing_time=3.2,
            estimated_cost="$0.012",
            success=True
        )
    
    elif model_name == "gpt-4o-transcribe":
        # Лучшее качество
        if "русском" in reference_text or "Добро" in reference_text:
            hypothesis = "Добро пожаловать на встречу по обсуждению проекта. Сегодня мы рассмотрим основные вопросы и примем важные решения."
        elif "Guten" in reference_text:
            hypothesis = "Guten Tag und herzlich willkommen zur Konferenz. Heute besprechen wir die wichtigsten Themen unserer Agenda."
        else:
            hypothesis = "Welcome to our quarterly presentation. Today we will review our achievements and discuss future plans."
        
        return TranscriptionResult(
            model_name=model_name,
            segments=[{"text": hypothesis}],
            processing_time=4.1,
            estimated_cost="$0.024",
            success=True
        )
    
    elif model_name == "replicate-whisper-diarization":
        # Хорошее качество с диаризацией
        if "русском" in reference_text or "Добро" in reference_text:
            hypothesis = "Добро пожаловать на встречу по обсуждению проекта. Сегодня мы рассмотрим основные вопросы и примем важные решения."
        elif "Guten" in reference_text:
            hypothesis = "Guten Tag und herzlich willkommen zur Konferenz. Heute besprechen wir die wichtigsten Themen unserer Agenda."
        else:
            hypothesis = "Welcome to our quarterly presentation. Today we will review our achievements and discuss future plans."
        
        return TranscriptionResult(
            model_name=model_name,
            segments=[
                {"text": hypothesis, "speaker": "SPEAKER_00"}
            ],
            processing_time=1.8,
            estimated_cost="$0.008",
            success=True
        )
    
    # Ошибка для неизвестной модели
    return TranscriptionResult(
        model_name=model_name,
        segments=[],
        processing_time=0.0,
        estimated_cost="N/A",
        success=False,
        error="Unknown model"
    )


def mock_test_methods(tester, scenarios):
    """Мокает методы тестирования для демонстрации"""
    
    def mock_test_openai_model(model, scenario):
        return create_mock_transcription_results(scenario.reference_text, model)
    
    def mock_test_replicate_model(scenario):
        return create_mock_transcription_results(scenario.reference_text, "replicate-whisper-diarization")
    
    # Заменяем методы на моковые
    tester.test_openai_model = mock_test_openai_model
    tester.test_replicate_model = mock_test_replicate_model
    
    return tester


def main():
    """Основная функция демонстрации"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🧪 Демонстрация комплексного тестирования качества транскрипции")
    print("=" * 70)
    print("📝 Этот скрипт демонстрирует работу системы WER оценки с моковыми данными")
    print("🔧 Реальные API вызовы заменены на симулированные результаты")
    print()
    
    # Создаем тестер
    tester = TranscriptionQualityTester(
        openai_api_key="demo-key",
        replicate_api_key="demo-replicate-key"
    )
    
    # Создаем демонстрационные сценарии
    scenarios = create_demo_scenarios()
    
    print(f"📋 Создано {len(scenarios)} тестовых сценариев:")
    for scenario in scenarios:
        print(f"  - {scenario.name}: {scenario.description}")
    print()
    
    # Мокаем методы тестирования
    tester = mock_test_methods(tester, scenarios)
    
    print("🚀 Запускаю тестирование...")
    
    try:
        # Запускаем комплексное тестирование
        results = tester.run_comprehensive_test(scenarios)
        
        print("✅ Тестирование завершено!")
        print()
        
        # Показываем краткие результаты
        print("📊 Краткие результаты:")
        comparison = results["model_comparison"]
        
        print(f"{'Модель':<30} {'Точность слов':<15} {'WER':<8} {'Время (с)':<10} {'Стоимость':<12}")
        print("-" * 80)
        
        for model_name, stats in sorted(comparison.items(), key=lambda x: x[1]["word_accuracy"], reverse=True):
            print(f"{model_name:<30} {stats['word_accuracy']:.3f}           {stats['average_wer']:.3f}    "
                  f"{stats['average_processing_time']:.1f}        ${stats['average_cost_usd']:.4f}")
        
        print()
        
        # Показываем рекомендации
        best_accuracy = max(comparison.values(), key=lambda x: x["word_accuracy"])
        fastest = min([v for v in comparison.values() if v["success_rate"] > 0], key=lambda x: x["average_processing_time"])
        cheapest = min([v for v in comparison.values() if v["success_rate"] > 0], key=lambda x: x["average_cost_usd"])
        
        best_model = [k for k, v in comparison.items() if v == best_accuracy][0]
        fastest_model = [k for k, v in comparison.items() if v == fastest][0]
        cheapest_model = [k for k, v in comparison.items() if v == cheapest][0]
        
        print("🏆 Рекомендации:")
        print(f"  🎯 Лучшая точность: {best_model} (точность слов: {best_accuracy['word_accuracy']:.3f})")
        print(f"  ⚡ Самая быстрая: {fastest_model} (время: {fastest['average_processing_time']:.1f}с)")
        print(f"  💰 Самая экономичная: {cheapest_model} (стоимость: ${cheapest['average_cost_usd']:.4f})")
        print()
        
        # Генерируем отчет
        output_dir = Path("data/interim")
        report_path = tester.generate_report(results, output_dir)
        
        print(f"📄 Подробный отчет сохранен: {report_path}")
        print(f"📊 JSON результаты: {output_dir / 'wer_evaluation_results.json'}")
        print()
        
        # Показываем пример детального анализа
        print("🔍 Пример детального анализа для первого сценария:")
        first_scenario = list(results["scenarios"].keys())[0]
        scenario_data = results["scenarios"][first_scenario]
        
        print(f"Сценарий: {scenario_data['scenario_info']['name']}")
        print(f"Эталонный текст: {scenario_data['scenario_info']['reference_text'][:60]}...")
        print()
        
        for model_name, result in scenario_data["model_results"].items():
            if result.get("success", False):
                metrics = result["quality_metrics"]
                print(f"  {model_name}:")
                print(f"    WER: {metrics['wer']:.3f} | CER: {metrics['cer']:.3f}")
                print(f"    Время: {result['processing_time']:.1f}с | Стоимость: {result['estimated_cost']}")
                print()
        
        print("✨ Демонстрация завершена успешно!")
        
    except Exception as e:
        logger.error(f"Ошибка при демонстрации: {e}")
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
