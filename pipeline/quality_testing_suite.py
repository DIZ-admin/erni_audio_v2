#!/usr/bin/env python3
"""
Quality Testing Suite - Объединенный инструмент для тестирования качества транскрипции
Объединяет функциональность transcription_quality_test.py, transcription_quality_tester.py и real_wer_testing.py
"""

import argparse
import logging
import sys
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

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
from pipeline.replicate_agent import ReplicateAgent
from pipeline.wer_evaluator import WERTranscriptionEvaluator, TranscriptionResult, WERCalculator


@dataclass
class TestScenario:
    """Тестовый сценарий для оценки качества"""
    name: str
    audio_file: Path
    reference_text: str
    description: str
    language: Optional[str] = None
    expected_speakers: Optional[int] = None


class QualityTestingSuite:
    """Объединенный класс для всех видов тестирования качества транскрипции"""
    
    def __init__(self, openai_api_key: str, replicate_api_key: Optional[str] = None):
        """
        Инициализация тестового набора
        
        Args:
            openai_api_key: OpenAI API ключ
            replicate_api_key: Replicate API ключ (опционально)
        """
        self.openai_api_key = openai_api_key
        self.replicate_api_key = replicate_api_key
        self.logger = logging.getLogger(__name__)
        self.evaluator = WERTranscriptionEvaluator()
        
        # Список доступных моделей для тестирования
        self.openai_models = list(TranscriptionAgent.SUPPORTED_MODELS.keys())
        self.replicate_available = replicate_api_key is not None
        
        self.logger.info(f"🧪 Инициализирован QualityTestingSuite")
        self.logger.info(f"📋 OpenAI модели: {', '.join(self.openai_models)}")
        self.logger.info(f"🚀 Replicate доступен: {'Да' if self.replicate_available else 'Нет'}")
    
    def create_test_scenarios(self, audio_files: List[str] = None, reference_texts: List[str] = None, 
                            use_real_files: bool = True) -> List[TestScenario]:
        """
        Создает тестовые сценарии
        
        Args:
            audio_files: Список аудиофайлов для тестирования
            reference_texts: Эталонные тексты для аудиофайлов
            use_real_files: Использовать реальные файлы из проекта
            
        Returns:
            Список тестовых сценариев
        """
        scenarios = []
        
        # Если указаны конкретные файлы
        if audio_files:
            scenarios = self._create_custom_scenarios(audio_files, reference_texts or [])
        
        # Если используем реальные файлы проекта
        elif use_real_files:
            scenarios = self._create_real_scenarios()
        
        # Если ничего не найдено, создаем моковые сценарии
        if not scenarios:
            scenarios = self._create_mock_scenarios()
        
        return scenarios
    
    def _create_custom_scenarios(self, audio_files: List[str], reference_texts: List[str]) -> List[TestScenario]:
        """Создает пользовательские тестовые сценарии"""
        scenarios = []
        
        for i, audio_file in enumerate(audio_files):
            audio_path = Path(audio_file)
            if not audio_path.exists():
                self.logger.warning(f"❌ Аудиофайл не найден: {audio_file}")
                continue
            
            # Используем предоставленный эталонный текст или создаем базовый
            if i < len(reference_texts):
                reference_text = reference_texts[i]
            else:
                reference_text = self._find_reference_text(audio_path)
            
            scenario = TestScenario(
                name=audio_path.stem,
                audio_file=audio_path,
                reference_text=reference_text,
                description=f"Пользовательский тест для {audio_path.name}",
                language=None,  # Автоопределение
                expected_speakers=None  # Автоопределение
            )
            scenarios.append(scenario)
            self.logger.info(f"✅ Добавлен сценарий: {scenario.name}")
        
        return scenarios
    
    def _create_real_scenarios(self) -> List[TestScenario]:
        """Создает реальные тестовые сценарии на основе доступных файлов"""
        scenarios = []
        
        # Проверяем доступные аудиофайлы
        test_files = [
            ("data/raw/Testdatei.m4a", "Немецкая тестовая запись", "de"),
            ("data/raw/Sitzung Erweiterte GL 17.04.2025.m4a", "Расширенная встреча руководства", "de"),
            ("data/interim/Sitzung Erweiterte GL 17.04.2025_converted.wav", "Конвертированная встреча", "de"),
        ]
        
        for file_path, description, language in test_files:
            audio_path = Path(file_path)
            
            # Для экономии API вызовов ищем короткие сегменты
            segment_path = audio_path.parent / f"{audio_path.stem}_segment_2.0min{audio_path.suffix}"
            if segment_path.exists():
                audio_path = segment_path
                description += " (2-минутный сегмент)"
            
            if audio_path.exists():
                reference_text = self._find_reference_text(audio_path, file_path)
                
                # Проверяем наличие точного эталонного текста для реального тестирования
                accurate_reference_file = Path("data/raw") / f"{Path(file_path).stem}_accurate_reference.txt"
                if not accurate_reference_file.exists():
                    self.logger.warning(f"⚠️ Нет точного эталонного текста для {audio_path.name}")
                    # Для демо тестирования используем базовый текст
                    reference_text = self._generate_demo_reference_text(description, language)
                
                scenario = TestScenario(
                    name=audio_path.stem,
                    audio_file=audio_path,
                    reference_text=reference_text,
                    description=description,
                    language=language,
                    expected_speakers=2
                )
                scenarios.append(scenario)
                self.logger.info(f"✅ Создан сценарий: {scenario.name}")
        
        return scenarios
    
    def _create_mock_scenarios(self) -> List[TestScenario]:
        """Создает тестовые сценарии с моковыми данными"""
        mock_scenarios = []
        
        # Создаем временный тестовый файл
        test_audio = Path("tests/assets/test_audio_mock.wav")
        test_audio.parent.mkdir(parents=True, exist_ok=True)
        if not test_audio.exists():
            test_audio.write_bytes(b"RIFF" + b"\x00" * 44)  # Минимальный WAV заголовок
        
        scenario = TestScenario(
            name="mock_test",
            audio_file=test_audio,
            reference_text="Это тестовая транскрипция для проверки качества распознавания речи.",
            description="Тестовый сценарий с моковыми данными",
            language="ru",
            expected_speakers=1
        )
        mock_scenarios.append(scenario)
        
        return mock_scenarios
    
    def _find_reference_text(self, audio_path: Path, original_file_path: str = None) -> str:
        """Ищет эталонный текст для аудиофайла"""
        # Если это сегмент, извлекаем имя оригинального файла
        if original_file_path:
            original_stem = Path(original_file_path).stem
        else:
            if "_segment_" in audio_path.stem:
                original_stem = audio_path.stem.split("_segment_")[0]
            else:
                original_stem = audio_path.stem
        
        # Сначала проверяем точный эталонный текст
        accurate_reference_file = Path("data/raw") / f"{original_stem}_accurate_reference.txt"
        if accurate_reference_file.exists():
            return accurate_reference_file.read_text(encoding='utf-8').strip()
        
        # Проверяем обычный эталонный файл
        reference_file = audio_path.parent / f"{original_stem}_reference.txt"
        if reference_file.exists():
            return reference_file.read_text(encoding='utf-8').strip()
        
        # Если нет готового эталона, создаем базовый
        return self._generate_demo_reference_text("Тестовая запись", "de")
    
    def _generate_demo_reference_text(self, description: str, language: str) -> str:
        """Генерирует демонстрационный эталонный текст"""
        if language == "de":
            return ("Guten Tag, das ist eine Testaufnahme für die automatische Spracherkennung. "
                   "Wir testen heute verschiedene Modelle zur Transkription von deutschen Audiodateien.")
        elif language == "en":
            return ("Good day, this is a test recording for automatic speech recognition. "
                   "Today we are testing various models for transcribing English audio files.")
        else:
            return ("Добро пожаловать на тестовую запись для автоматического распознавания речи. "
                   "Сегодня мы тестируем различные модели для транскрипции аудиофайлов.")
    
    def test_openai_model(self, model: str, scenario: TestScenario) -> TranscriptionResult:
        """Тестирует OpenAI модель на сценарии"""
        start_time = time.time()
        
        try:
            self.logger.info(f"🔄 Тестирую {model} на {scenario.name}...")
            
            agent = TranscriptionAgent(
                api_key=self.openai_api_key,
                model=model,
                language=scenario.language
            )
            
            # Получаем оценку стоимости
            file_size_mb = scenario.audio_file.stat().st_size / (1024 * 1024)
            estimated_cost = agent.estimate_cost(file_size_mb)
            
            # Выполняем транскрипцию
            segments = agent.run(scenario.audio_file, "")
            
            processing_time = time.time() - start_time
            
            return TranscriptionResult(
                model_name=model,
                segments=segments,
                processing_time=processing_time,
                estimated_cost=estimated_cost,
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"❌ Ошибка тестирования {model}: {e}")
            
            return TranscriptionResult(
                model_name=model,
                segments=[],
                processing_time=processing_time,
                estimated_cost="N/A",
                success=False,
                error=str(e)
            )
    
    def test_replicate_model(self, scenario: TestScenario) -> Optional[TranscriptionResult]:
        """Тестирует Replicate модель на сценарии"""
        if not self.replicate_available:
            return None
        
        start_time = time.time()
        
        try:
            self.logger.info(f"🚀 Тестирую Replicate на {scenario.name}...")
            
            agent = ReplicateAgent(api_token=self.replicate_api_key)
            
            # Получаем оценку стоимости
            cost_info = agent.estimate_cost(scenario.audio_file)
            estimated_cost = f"~${cost_info['estimated_cost_usd']}"
            
            # Выполняем транскрипцию
            segments = agent.run(
                audio_file=scenario.audio_file,
                num_speakers=scenario.expected_speakers,
                language=scenario.language
            )
            
            processing_time = time.time() - start_time
            
            return TranscriptionResult(
                model_name="replicate-whisper-diarization",
                segments=segments,
                processing_time=processing_time,
                estimated_cost=estimated_cost,
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"❌ Ошибка тестирования Replicate: {e}")
            
            return TranscriptionResult(
                model_name="replicate-whisper-diarization",
                segments=[],
                processing_time=processing_time,
                estimated_cost="N/A",
                success=False,
                error=str(e)
            )

    def run_comprehensive_test(self, scenarios: Optional[List[TestScenario]] = None,
                             models: List[str] = None, real_api: bool = True) -> Dict:
        """
        Запускает комплексное тестирование всех моделей

        Args:
            scenarios: Список сценариев для тестирования
            models: Конкретные модели для тестирования
            real_api: Использовать реальные API вызовы

        Returns:
            Словарь с результатами тестирования
        """
        if scenarios is None:
            scenarios = self.create_test_scenarios(use_real_files=real_api)

        if not scenarios:
            raise ValueError("Нет доступных тестовых сценариев")

        # Определяем модели для тестирования
        if models is None:
            models = self.openai_models.copy()
            if self.replicate_available:
                models.append("replicate-whisper-diarization")
        else:
            # Фильтруем модели
            filtered_models = []
            for model in models:
                if model == "replicate":
                    if self.replicate_available:
                        filtered_models.append("replicate-whisper-diarization")
                elif model in self.openai_models:
                    filtered_models.append(model)
            models = filtered_models

        self.logger.info(f"🧪 Начинаю комплексное тестирование {len(scenarios)} сценариев...")
        self.logger.info(f"🤖 Модели: {', '.join(models)}")

        all_results = {
            "test_summary": {
                "total_scenarios": len(scenarios),
                "total_models": len(models),
                "start_time": time.time(),
                "test_type": "real_api" if real_api else "demo",
                "models_tested": models
            },
            "scenarios": {},
            "model_comparison": {}
        }

        # Тестируем каждый сценарий
        for scenario in scenarios:
            self.logger.info(f"📋 Тестирую сценарий: {scenario.name}")

            scenario_results = {
                "scenario_info": {
                    "name": scenario.name,
                    "description": scenario.description,
                    "audio_file": str(scenario.audio_file),
                    "language": scenario.language,
                    "reference_text": scenario.reference_text
                },
                "model_results": {}
            }

            # Тестируем OpenAI модели
            for model in [m for m in models if m in self.openai_models]:
                result = self.test_openai_model(model, scenario)
                evaluation = self.evaluator.evaluate_transcription(scenario.reference_text, result)
                scenario_results["model_results"][model] = evaluation

            # Тестируем Replicate модель
            if "replicate-whisper-diarization" in models and self.replicate_available:
                result = self.test_replicate_model(scenario)
                if result:
                    evaluation = self.evaluator.evaluate_transcription(scenario.reference_text, result)
                    scenario_results["model_results"]["replicate-whisper-diarization"] = evaluation

            all_results["scenarios"][scenario.name] = scenario_results

        # Создаем сводку по моделям
        all_results["model_comparison"] = self._create_model_comparison(all_results["scenarios"])
        all_results["test_summary"]["end_time"] = time.time()
        all_results["test_summary"]["total_duration"] = all_results["test_summary"]["end_time"] - all_results["test_summary"]["start_time"]

        return all_results

    def _create_model_comparison(self, scenarios_results: Dict) -> Dict:
        """Создает сравнительную таблицу моделей"""
        model_stats = {}

        # Собираем статистику по каждой модели
        for scenario_name, scenario_data in scenarios_results.items():
            for model_name, model_result in scenario_data["model_results"].items():
                if model_name not in model_stats:
                    model_stats[model_name] = {
                        "total_tests": 0,
                        "successful_tests": 0,
                        "total_wer": 0.0,
                        "total_cer": 0.0,
                        "total_processing_time": 0.0,
                        "costs": []
                    }

                stats = model_stats[model_name]
                stats["total_tests"] += 1

                if model_result.get("success", False):
                    stats["successful_tests"] += 1
                    quality_metrics = model_result.get("quality_metrics", {})
                    stats["total_wer"] += quality_metrics.get("wer", 1.0)
                    stats["total_cer"] += quality_metrics.get("cer", 1.0)
                    stats["total_processing_time"] += model_result.get("processing_time", 0.0)

                    # Парсим стоимость
                    cost_str = model_result.get("estimated_cost", "N/A")
                    if cost_str.startswith("~$"):
                        try:
                            cost_value = float(cost_str.replace("~$", ""))
                            stats["costs"].append(cost_value)
                        except ValueError:
                            pass

        # Вычисляем средние значения
        comparison = {}
        for model_name, stats in model_stats.items():
            successful_tests = stats["successful_tests"]

            if successful_tests > 0:
                avg_wer = stats["total_wer"] / successful_tests
                avg_cer = stats["total_cer"] / successful_tests
                avg_processing_time = stats["total_processing_time"] / successful_tests
                avg_cost = sum(stats["costs"]) / len(stats["costs"]) if stats["costs"] else 0.0

                comparison[model_name] = {
                    "success_rate": successful_tests / stats["total_tests"],
                    "average_wer": round(avg_wer, 4),
                    "average_cer": round(avg_cer, 4),
                    "word_accuracy": round(1.0 - avg_wer, 4),
                    "char_accuracy": round(1.0 - avg_cer, 4),
                    "average_processing_time": round(avg_processing_time, 2),
                    "average_cost_usd": round(avg_cost, 4),
                    "total_tests": stats["total_tests"],
                    "successful_tests": successful_tests
                }
            else:
                comparison[model_name] = {
                    "success_rate": 0.0,
                    "average_wer": 1.0,
                    "average_cer": 1.0,
                    "word_accuracy": 0.0,
                    "char_accuracy": 0.0,
                    "average_processing_time": 0.0,
                    "average_cost_usd": 0.0,
                    "total_tests": stats["total_tests"],
                    "successful_tests": 0,
                    "note": "Все тесты завершились ошибкой"
                }

        return comparison

    def generate_report(self, results: Dict, output_dir: Path = None) -> Path:
        """Генерирует подробный отчет о тестировании"""
        if output_dir is None:
            output_dir = Path("data/interim")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем JSON результаты
        test_type = results["test_summary"].get("test_type", "unknown")
        json_path = output_dir / f"{test_type}_quality_evaluation_results.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Создаем текстовый отчет
        report_path = output_dir / f"{test_type}_quality_evaluation_report.md"
        self._generate_markdown_report(results, report_path)

        self.logger.info(f"📊 Отчет сохранен: {report_path}")
        return report_path

    def _generate_markdown_report(self, results: Dict, output_path: Path) -> None:
        """Генерирует Markdown отчет"""
        with open(output_path, 'w', encoding='utf-8') as f:
            test_type = results["test_summary"].get("test_type", "unknown")
            f.write(f"# Отчет о качестве транскрипции ({test_type})\n\n")

            # Общая информация
            summary = results["test_summary"]
            f.write(f"**Дата тестирования:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Тип тестирования:** {test_type}\n")
            f.write(f"**Количество сценариев:** {summary['total_scenarios']}\n")
            f.write(f"**Количество моделей:** {summary['total_models']}\n")
            f.write(f"**Общее время тестирования:** {summary['total_duration']:.2f} секунд\n")
            f.write(f"**Протестированные модели:** {', '.join(summary.get('models_tested', []))}\n\n")

            # Сравнительная таблица
            f.write("## Сравнение моделей\n\n")
            f.write("| Модель | Точность слов | Точность символов | WER | CER | Время (с) | Стоимость ($) | Успешность |\n")
            f.write("|--------|---------------|-------------------|-----|-----|-----------|---------------|------------|\n")

            comparison = results["model_comparison"]
            for model_name, stats in sorted(comparison.items(), key=lambda x: x[1]["word_accuracy"], reverse=True):
                f.write(f"| {model_name} | {stats['word_accuracy']:.3f} | {stats['char_accuracy']:.3f} | "
                       f"{stats['average_wer']:.3f} | {stats['average_cer']:.3f} | "
                       f"{stats['average_processing_time']:.2f} | {stats['average_cost_usd']:.4f} | "
                       f"{stats['success_rate']:.1%} |\n")

            # Рекомендации
            if comparison:
                f.write("\n## Рекомендации\n\n")
                best_accuracy = max(comparison.values(), key=lambda x: x["word_accuracy"])
                fastest = min([v for v in comparison.values() if v["success_rate"] > 0], key=lambda x: x["average_processing_time"])
                cheapest = min([v for v in comparison.values() if v["success_rate"] > 0], key=lambda x: x["average_cost_usd"])

                best_model = [k for k, v in comparison.items() if v == best_accuracy][0]
                fastest_model = [k for k, v in comparison.items() if v == fastest][0]
                cheapest_model = [k for k, v in comparison.items() if v == cheapest][0]

                f.write(f"- **Лучшая точность:** {best_model} (точность слов: {best_accuracy['word_accuracy']:.3f})\n")
                f.write(f"- **Самая быстрая:** {fastest_model} (время: {fastest['average_processing_time']:.2f}с)\n")
                f.write(f"- **Самая экономичная:** {cheapest_model} (стоимость: ${cheapest['average_cost_usd']:.4f})\n")

            # Детальные результаты по сценариям
            f.write("\n## Детальные результаты\n\n")
            for scenario_name, scenario_data in results["scenarios"].items():
                f.write(f"### {scenario_name}\n\n")
                f.write(f"**Описание:** {scenario_data['scenario_info']['description']}\n")
                language = scenario_data['scenario_info'].get('language', 'Не указан')
                f.write(f"**Язык:** {language}\n")
                f.write(f"**Файл:** {scenario_data['scenario_info']['audio_file']}\n")
                f.write(f"**Эталонный текст:** {scenario_data['scenario_info']['reference_text'][:100]}...\n\n")

                for model_name, result in scenario_data["model_results"].items():
                    if result.get("success", False):
                        metrics = result["quality_metrics"]
                        f.write(f"- **{model_name}:** WER={metrics['wer']:.3f}, "
                               f"CER={metrics['cer']:.3f}, "
                               f"время={result['processing_time']:.2f}с, "
                               f"стоимость={result['estimated_cost']}\n")
                    else:
                        f.write(f"- **{model_name}:** ❌ Ошибка - {result.get('error', 'Неизвестная ошибка')}\n")

                f.write("\n")


def setup_logging(verbose: bool = False) -> None:
    """Настройка логирования"""
    level = logging.DEBUG if verbose else logging.INFO

    # Создаем директорию для логов
    Path('logs').mkdir(exist_ok=True)

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/quality_testing_suite.log', encoding='utf-8')
        ]
    )

    # Отключаем логи библиотек для чистоты вывода
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)


def validate_api_keys() -> tuple:
    """Проверяет наличие и валидность API ключей"""
    openai_key = os.getenv('OPENAI_API_KEY')
    replicate_key = os.getenv('REPLICATE_API_TOKEN')

    if not openai_key:
        print("❌ Ошибка: OPENAI_API_KEY не найден в переменных окружения")
        print("Установите ключ: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    if not replicate_key:
        print("⚠️ Предупреждение: REPLICATE_API_TOKEN не найден")
        print("Replicate модель будет пропущена")

    print(f"✅ OpenAI API ключ: {openai_key[:10]}...")
    if replicate_key:
        print(f"✅ Replicate API ключ: {replicate_key[:10]}...")

    return openai_key, replicate_key


def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Quality Testing Suite - Объединенный инструмент для тестирования качества транскрипции",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

1. Демонстрационное тестирование (без реальных API вызовов):
   python quality_testing_suite.py --demo

2. Реальное тестирование с доступными файлами:
   python quality_testing_suite.py --real

3. Тестирование конкретных файлов:
   python quality_testing_suite.py --audio-files audio1.wav audio2.mp3

4. Тестирование с эталонными текстами:
   python quality_testing_suite.py --audio-files audio.wav --reference-texts "Привет мир"

5. Тестирование конкретных моделей:
   python quality_testing_suite.py --models whisper-1 gpt-4o-transcribe

6. Подробный вывод:
   python quality_testing_suite.py --verbose

Переменные окружения:
- OPENAI_API_KEY: Обязательный ключ OpenAI API
- REPLICATE_API_TOKEN: Опциональный токен Replicate API
        """
    )

    # Режимы тестирования
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--demo',
        action='store_true',
        help='Демонстрационное тестирование с моковыми данными'
    )
    mode_group.add_argument(
        '--real',
        action='store_true',
        help='Реальное тестирование с настоящими API вызовами'
    )

    # Файлы для тестирования
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

    # Настройки тестирования
    parser.add_argument(
        '--models',
        nargs='+',
        choices=['whisper-1', 'gpt-4o-mini-transcribe', 'gpt-4o-transcribe', 'replicate'],
        help='Конкретные модели для тестирования (по умолчанию: все доступные)'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('data/interim'),
        help='Директория для сохранения результатов (по умолчанию: data/interim)'
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

    print("🧪 Quality Testing Suite - Объединенный инструмент тестирования")
    print("=" * 70)

    # Определяем режим тестирования
    if args.demo:
        test_mode = "demo"
        print("🎭 Режим: Демонстрационное тестирование (моковые данные)")
        real_api = False
    elif args.real:
        test_mode = "real"
        print("🔥 Режим: Реальное тестирование (настоящие API вызовы)")
        print("⚠️  ВНИМАНИЕ: Это может занять время и стоить денег!")
        real_api = True
    elif args.audio_files:
        test_mode = "custom"
        print("📁 Режим: Пользовательские файлы")
        real_api = True
    else:
        test_mode = "auto"
        print("🤖 Режим: Автоматический (реальные файлы если доступны)")
        real_api = True

    # Загружаем API ключи
    openai_key, replicate_key = validate_api_keys()

    # Создаем тестер
    suite = QualityTestingSuite(
        openai_api_key=openai_key,
        replicate_api_key=replicate_key
    )

    # Создаем тестовые сценарии
    if args.audio_files:
        scenarios = suite.create_test_scenarios(
            audio_files=args.audio_files,
            reference_texts=args.reference_texts,
            use_real_files=False
        )
    else:
        scenarios = suite.create_test_scenarios(use_real_files=real_api)

    if not scenarios:
        print("❌ Не удалось создать тестовые сценарии")
        if test_mode == "real":
            print("💡 Попробуйте сначала: python3 create_accurate_references.py")
        sys.exit(1)

    # Показываем план тестирования
    print(f"\n📋 План тестирования:")
    print(f"Сценариев: {len(scenarios)}")
    for scenario in scenarios:
        print(f"  - {scenario.name}: {scenario.description}")
        if args.verbose:
            print(f"    Файл: {scenario.audio_file}")
            print(f"    Размер: {scenario.audio_file.stat().st_size / (1024*1024):.2f} MB")

    # Определяем модели
    available_models = suite.openai_models.copy()
    if suite.replicate_available:
        available_models.append("replicate-whisper-diarization")

    if args.models:
        # Фильтруем модели
        filtered_models = []
        for model in args.models:
            if model == "replicate":
                if suite.replicate_available:
                    filtered_models.append("replicate-whisper-diarization")
            elif model in suite.openai_models:
                filtered_models.append(model)
        available_models = filtered_models

    print(f"Модели: {', '.join(available_models)}")
    print(f"Выходная директория: {args.output_dir}")

    if args.dry_run:
        print("\n🔍 Режим dry-run: план показан, тестирование не выполняется")
        return

    # Подтверждение для реального тестирования
    if real_api and test_mode in ["real", "auto"]:
        confirm = input("\n❓ Продолжить тестирование? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Тестирование отменено пользователем")
            sys.exit(0)

    # Запускаем тестирование
    print(f"\n🚀 Начинаю тестирование...")
    try:
        results = suite.run_comprehensive_test(
            scenarios=scenarios,
            models=available_models,
            real_api=real_api
        )

        # Генерируем отчет
        print(f"\n📊 Генерирую отчет...")
        report_path = suite.generate_report(results, args.output_dir)

        # Показываем краткую сводку
        print(f"\n✅ Тестирование завершено!")
        print(f"📄 Отчет сохранен: {report_path}")

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
