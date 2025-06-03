"""
Transcription Quality Tester - Комплексное тестирование качества транскрипции
Тестирует все доступные модели транскрипции и вычисляет WER/CER метрики
"""

import logging
import time
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from dataclasses import dataclass

from .transcription_agent import TranscriptionAgent
from .replicate_agent import ReplicateAgent
from .wer_evaluator import WERTranscriptionEvaluator, TranscriptionResult, WERCalculator


@dataclass
class TestScenario:
    """Тестовый сценарий для оценки качества"""
    name: str
    audio_file: Path
    reference_text: str
    description: str
    language: Optional[str] = None
    expected_speakers: Optional[int] = None


class TranscriptionQualityTester:
    """Основной класс для комплексного тестирования качества транскрипции"""
    
    def __init__(self, openai_api_key: str, replicate_api_key: Optional[str] = None):
        """
        Инициализация тестера
        
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
        
        self.logger.info(f"🧪 Инициализирован TranscriptionQualityTester")
        self.logger.info(f"📋 OpenAI модели: {', '.join(self.openai_models)}")
        self.logger.info(f"🚀 Replicate доступен: {'Да' if self.replicate_available else 'Нет'}")
    
    def create_test_scenarios(self) -> List[TestScenario]:
        """
        Создает тестовые сценарии на основе доступных данных
        
        Returns:
            Список тестовых сценариев
        """
        scenarios = []
        
        # Проверяем доступные аудиофайлы
        test_files = [
            ("data/raw/Sitzung_GL_converted.mp3", "Немецкая деловая встреча", "de"),
            ("data/raw/Sitzung Erweiterte GL 17.04.2025.m4a", "Расширенная встреча руководства", "de"),
        ]
        
        for file_path, description, language in test_files:
            audio_path = Path(file_path)
            if audio_path.exists():
                # Создаем эталонную транскрипцию на основе имени файла
                reference_text = self._generate_reference_text(audio_path, description)
                
                scenario = TestScenario(
                    name=audio_path.stem,
                    audio_file=audio_path,
                    reference_text=reference_text,
                    description=description,
                    language=language,
                    expected_speakers=2  # Предполагаем 2 спикера для деловых встреч
                )
                scenarios.append(scenario)
                self.logger.info(f"📝 Создан сценарий: {scenario.name}")
        
        # Добавляем тестовые данные из assets если основные файлы недоступны
        if not scenarios:
            scenarios.extend(self._create_mock_scenarios())
        
        return scenarios
    
    def _generate_reference_text(self, audio_path: Path, description: str) -> str:
        """
        Генерирует эталонный текст для аудиофайла
        
        Args:
            audio_path: Путь к аудиофайлу
            description: Описание содержимого
            
        Returns:
            Эталонный текст
        """
        # Проверяем, есть ли готовый эталонный файл
        reference_file = audio_path.parent / f"{audio_path.stem}_reference.txt"
        if reference_file.exists():
            return reference_file.read_text(encoding='utf-8').strip()
        
        # Если нет готового эталона, создаем базовый на основе описания
        if "немецк" in description.lower() or "deutsch" in description.lower():
            return ("Guten Tag, willkommen zur Sitzung. "
                   "Heute besprechen wir die wichtigsten Punkte unserer Agenda. "
                   "Lassen Sie uns mit dem ersten Thema beginnen.")
        else:
            return ("Добро пожаловать на встречу. "
                   "Сегодня мы обсудим основные вопросы повестки дня. "
                   "Давайте начнем с первого пункта.")
    
    def _create_mock_scenarios(self) -> List[TestScenario]:
        """Создает тестовые сценарии с моковыми данными"""
        mock_scenarios = []
        
        # Создаем временный тестовый файл
        test_audio = Path("tests/assets/test_audio_mock.wav")
        if not test_audio.exists():
            # Создаем пустой файл для тестирования
            test_audio.parent.mkdir(parents=True, exist_ok=True)
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
    
    def test_openai_model(self, model: str, scenario: TestScenario) -> TranscriptionResult:
        """
        Тестирует OpenAI модель на сценарии
        
        Args:
            model: Название модели
            scenario: Тестовый сценарий
            
        Returns:
            Результат транскрипции
        """
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
        """
        Тестирует Replicate модель на сценарии
        
        Args:
            scenario: Тестовый сценарий
            
        Returns:
            Результат транскрипции или None если Replicate недоступен
        """
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
    
    def run_comprehensive_test(self, scenarios: Optional[List[TestScenario]] = None) -> Dict:
        """
        Запускает комплексное тестирование всех моделей
        
        Args:
            scenarios: Список сценариев для тестирования (если None, создаются автоматически)
            
        Returns:
            Словарь с результатами тестирования
        """
        if scenarios is None:
            scenarios = self.create_test_scenarios()
        
        if not scenarios:
            raise ValueError("Нет доступных тестовых сценариев")
        
        self.logger.info(f"🧪 Начинаю комплексное тестирование {len(scenarios)} сценариев...")
        
        all_results = {
            "test_summary": {
                "total_scenarios": len(scenarios),
                "total_models": len(self.openai_models) + (1 if self.replicate_available else 0),
                "start_time": time.time()
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
            for model in self.openai_models:
                result = self.test_openai_model(model, scenario)
                evaluation = self.evaluator.evaluate_transcription(scenario.reference_text, result)
                scenario_results["model_results"][model] = evaluation
            
            # Тестируем Replicate модель
            if self.replicate_available:
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
        """
        Создает сравнительную таблицу моделей

        Args:
            scenarios_results: Результаты по сценариям

        Returns:
            Сравнительная таблица моделей
        """
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
        """
        Генерирует подробный отчет о тестировании

        Args:
            results: Результаты тестирования
            output_dir: Директория для сохранения отчета

        Returns:
            Путь к сохраненному отчету
        """
        if output_dir is None:
            output_dir = Path("data/interim")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем JSON результаты
        json_path = output_dir / "wer_evaluation_results.json"
        self.evaluator.save_results(results, json_path)

        # Создаем текстовый отчет
        report_path = output_dir / "transcription_quality_report.md"
        self._generate_markdown_report(results, report_path)

        self.logger.info(f"📊 Отчет сохранен: {report_path}")
        return report_path

    def _generate_markdown_report(self, results: Dict, output_path: Path) -> None:
        """Генерирует Markdown отчет"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Отчет о качестве транскрипции\n\n")

            # Общая информация
            summary = results["test_summary"]
            f.write(f"**Дата тестирования:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Количество сценариев:** {summary['total_scenarios']}\n")
            f.write(f"**Количество моделей:** {summary['total_models']}\n")
            f.write(f"**Общее время тестирования:** {summary['total_duration']:.2f} секунд\n\n")

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
                f.write(f"**Эталонный текст:** {scenario_data['scenario_info']['reference_text'][:100]}...\n\n")

                for model_name, result in scenario_data["model_results"].items():
                    if result.get("success", False):
                        metrics = result["quality_metrics"]
                        f.write(f"- **{model_name}:** WER={metrics['wer']:.3f}, "
                               f"время={result['processing_time']:.2f}с, "
                               f"стоимость={result['estimated_cost']}\n")
                    else:
                        f.write(f"- **{model_name}:** ❌ Ошибка - {result.get('error', 'Неизвестная ошибка')}\n")

                f.write("\n")
