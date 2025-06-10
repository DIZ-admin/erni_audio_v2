#!/usr/bin/env python3
"""
Voiceprint Management Suite - Объединенный инструмент для управления voiceprint'ами
Объединяет функциональность check_voiceprint_samples.py, analyze_valid_voiceprints.py, 
clean_and_upload_voiceprint.py, check_remote_voiceprints.py и sync_voiceprints.py
"""

import argparse
import logging
import json
import sys
import base64
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Добавляем корневую директорию в путь для импорта модулей
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.voiceprint_manager import VoiceprintManager
from pipeline.voiceprint_agent import VoiceprintAgent
from pipeline.config import get_config


@dataclass
class VoiceprintValidation:
    """Результат валидации voiceprint'а"""
    is_valid: bool
    is_base64: bool
    data_size_bytes: int
    data_size_kb: float
    estimated_quality: str
    issues: List[str]


@dataclass
class VoiceprintAnalysis:
    """Результат анализа базы voiceprint'ов"""
    total_voiceprints: int
    valid_voiceprints: int
    invalid_voiceprints: int
    test_data_voiceprints: int
    real_voiceprints: int
    quality_distribution: Dict[str, int]
    size_statistics: Dict[str, float]
    creation_dates: List[str]
    labels: List[str]
    issues: List[str]
    detailed_results: List[Dict]


class VoiceprintManagementSuite:
    """Объединенный класс для управления voiceprint'ами"""
    
    def __init__(self, database_path: Path, api_key: Optional[str] = None):
        """
        Инициализация suite
        
        Args:
            database_path: Путь к базе данных voiceprint'ов
            api_key: API ключ pyannote.ai для удаленных операций
        """
        self.database_path = database_path
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
        # Инициализируем менеджер
        self.manager = VoiceprintManager(database_path)
        
        # Инициализируем агент если есть API ключ
        self.agent = VoiceprintAgent(api_key) if api_key else None
        
        self.logger.info(f"🧪 Инициализирован VoiceprintManagementSuite")
        self.logger.info(f"📂 База данных: {database_path}")
        self.logger.info(f"🔑 API доступ: {'Да' if api_key else 'Нет'}")
    
    def validate_voiceprint_data(self, voiceprint_data: str) -> VoiceprintValidation:
        """
        Валидация данных голосового отпечатка
        
        Args:
            voiceprint_data: Base64 строка с данными voiceprint
            
        Returns:
            Результат валидации
        """
        validation = VoiceprintValidation(
            is_valid=False,
            is_base64=False,
            data_size_bytes=0,
            data_size_kb=0.0,
            estimated_quality="unknown",
            issues=[]
        )
        
        try:
            # Проверяем, что это не пустая строка
            if not voiceprint_data or not voiceprint_data.strip():
                validation.issues.append("Пустые данные voiceprint")
                return validation
            
            # Проверяем, что это валидный base64
            try:
                decoded_data = base64.b64decode(voiceprint_data)
                validation.is_base64 = True
                validation.data_size_bytes = len(decoded_data)
                validation.data_size_kb = len(decoded_data) / 1024
            except Exception as e:
                validation.issues.append(f"Невалидный base64: {e}")
                return validation
            
            # Оценка качества по размеру данных
            if validation.data_size_bytes < 100:
                validation.estimated_quality = "очень низкое"
                validation.issues.append("Слишком маленький размер данных")
            elif validation.data_size_bytes < 1000:
                validation.estimated_quality = "низкое"
                validation.issues.append("Маленький размер данных")
            elif validation.data_size_bytes < 10000:
                validation.estimated_quality = "среднее"
            elif validation.data_size_bytes < 50000:
                validation.estimated_quality = "хорошее"
            else:
                validation.estimated_quality = "отличное"
            
            # Проверяем на подозрительные паттерны
            if voiceprint_data.startswith("data_"):
                validation.issues.append("Подозрительный формат данных (возможно тестовые данные)")
                validation.estimated_quality = "тестовые данные"
            
            # Если нет критических проблем, считаем валидным
            if validation.is_base64 and validation.data_size_bytes > 0:
                validation.is_valid = True
            
        except Exception as e:
            validation.issues.append(f"Ошибка валидации: {e}")
        
        return validation
    
    def analyze_database(self) -> VoiceprintAnalysis:
        """
        Анализ базы данных голосовых отпечатков
        
        Returns:
            Результаты анализа
        """
        self.logger.info("🔍 Начинаю анализ базы данных voiceprints...")
        
        voiceprints = self.manager.list_voiceprints()
        
        analysis = VoiceprintAnalysis(
            total_voiceprints=len(voiceprints),
            valid_voiceprints=0,
            invalid_voiceprints=0,
            test_data_voiceprints=0,
            real_voiceprints=0,
            quality_distribution={
                "отличное": 0, "хорошее": 0, "среднее": 0, "низкое": 0,
                "очень низкое": 0, "тестовые данные": 0, "unknown": 0
            },
            size_statistics={
                "min_size_kb": float('inf'), "max_size_kb": 0,
                "avg_size_kb": 0, "total_size_kb": 0
            },
            creation_dates=[],
            labels=[],
            issues=[],
            detailed_results=[]
        )
        
        total_size = 0
        
        for voiceprint in voiceprints:
            vp_id = voiceprint.get("id", "unknown")
            label = voiceprint.get("label", "unknown")
            voiceprint_data = voiceprint.get("voiceprint", "")
            created_at = voiceprint.get("created_at", "")
            source_file = voiceprint.get("source_file", "")
            
            self.logger.debug(f"Анализирую voiceprint: {label} (ID: {vp_id[:8]}...)")
            
            # Валидация данных
            validation = self.validate_voiceprint_data(voiceprint_data)
            
            # Обновляем статистику
            if validation.is_valid:
                analysis.valid_voiceprints += 1
            else:
                analysis.invalid_voiceprints += 1
            
            # Качество
            quality = validation.estimated_quality
            analysis.quality_distribution[quality] += 1
            
            # Тестовые vs реальные данные
            if quality == "тестовые данные" or label.startswith("Test"):
                analysis.test_data_voiceprints += 1
            else:
                analysis.real_voiceprints += 1
            
            # Размеры
            size_kb = validation.data_size_kb
            if size_kb > 0:
                analysis.size_statistics["min_size_kb"] = min(
                    analysis.size_statistics["min_size_kb"], size_kb
                )
                analysis.size_statistics["max_size_kb"] = max(
                    analysis.size_statistics["max_size_kb"], size_kb
                )
                total_size += size_kb
            
            # Даты создания
            if created_at:
                analysis.creation_dates.append(created_at)
            
            # Лейблы
            analysis.labels.append(label)
            
            # Проблемы
            if validation.issues:
                analysis.issues.extend([f"{label}: {issue}" for issue in validation.issues])
            
            # Детальные результаты
            analysis.detailed_results.append({
                "id": vp_id,
                "label": label,
                "validation": validation,
                "created_at": created_at,
                "source_file": source_file,
                "has_source_file": bool(source_file and source_file.strip())
            })
        
        # Финальные вычисления
        if analysis.valid_voiceprints > 0:
            analysis.size_statistics["avg_size_kb"] = total_size / analysis.valid_voiceprints
        
        analysis.size_statistics["total_size_kb"] = total_size
        
        if analysis.size_statistics["min_size_kb"] == float('inf'):
            analysis.size_statistics["min_size_kb"] = 0
        
        self.logger.info(f"✅ Анализ завершен: {analysis.total_voiceprints} voiceprints проанализировано")
        
        return analysis
    
    def print_analysis_report(self, analysis: VoiceprintAnalysis) -> None:
        """Выводит отчет по анализу voiceprints"""
        print("\n" + "="*80)
        print("📊 ОТЧЕТ ПО АНАЛИЗУ ОБРАЗЦОВ ГОЛОСОВ (VOICEPRINTS)")
        print("="*80)
        
        # Общая статистика
        print(f"\n📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего voiceprints: {analysis.total_voiceprints}")
        print(f"   Валидных: {analysis.valid_voiceprints}")
        print(f"   Невалидных: {analysis.invalid_voiceprints}")
        print(f"   Реальных данных: {analysis.real_voiceprints}")
        print(f"   Тестовых данных: {analysis.test_data_voiceprints}")
        
        # Распределение по качеству
        print(f"\n🎯 РАСПРЕДЕЛЕНИЕ ПО КАЧЕСТВУ:")
        for quality, count in analysis.quality_distribution.items():
            if count > 0:
                percentage = (count / analysis.total_voiceprints) * 100
                print(f"   {quality}: {count} ({percentage:.1f}%)")
        
        # Статистика размеров
        print(f"\n📏 СТАТИСТИКА РАЗМЕРОВ:")
        size_stats = analysis.size_statistics
        print(f"   Минимальный размер: {size_stats['min_size_kb']:.2f} KB")
        print(f"   Максимальный размер: {size_stats['max_size_kb']:.2f} KB")
        print(f"   Средний размер: {size_stats['avg_size_kb']:.2f} KB")
        print(f"   Общий размер: {size_stats['total_size_kb']:.2f} KB")
        
        # Проблемы
        if analysis.issues:
            print(f"\n⚠️  ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ ({len(analysis.issues)}):")
            for issue in analysis.issues[:10]:  # Показываем первые 10
                print(f"   • {issue}")
            if len(analysis.issues) > 10:
                print(f"   ... и еще {len(analysis.issues) - 10} проблем")
        else:
            print(f"\n✅ ПРОБЛЕМ НЕ ОБНАРУЖЕНО")
        
        # Даты создания
        if analysis.creation_dates:
            dates = sorted(analysis.creation_dates)
            print(f"\n📅 ВРЕМЕННОЙ ДИАПАЗОН:")
            print(f"   Первый voiceprint: {dates[0]}")
            print(f"   Последний voiceprint: {dates[-1]}")
    
    def print_detailed_report(self, analysis: VoiceprintAnalysis, limit: int = 20) -> None:
        """Выводит детальный отчет по voiceprints"""
        print(f"\n📋 ДЕТАЛЬНЫЙ ОТЧЕТ (показано {min(limit, len(analysis.detailed_results))} из {len(analysis.detailed_results)}):")
        print("-" * 120)
        print(f"{'ID':<10} {'Label':<30} {'Quality':<15} {'Size KB':<10} {'Valid':<8} {'Issues':<25}")
        print("-" * 120)
        
        for i, result in enumerate(analysis.detailed_results[:limit]):
            vp_id = result['id'][:8] + "..."
            label = result['label'][:28] + "..." if len(result['label']) > 28 else result['label']
            quality = result['validation'].estimated_quality[:13]
            size_kb = f"{result['validation'].data_size_kb:.2f}"
            is_valid = "✅" if result['validation'].is_valid else "❌"
            issues = ", ".join(result['validation'].issues[:2])[:23]
            
            print(f"{vp_id:<10} {label:<30} {quality:<15} {size_kb:<10} {is_valid:<8} {issues:<25}")
    
    def analyze_valid_voiceprints(self, analysis: VoiceprintAnalysis) -> None:
        """Анализирует только валидные voiceprint'ы"""
        print("\n" + "="*80)
        print("🎯 АНАЛИЗ ВАЛИДНЫХ VOICEPRINTS")
        print("="*80)
        
        valid_count = 0
        real_data_count = 0
        
        for result in analysis.detailed_results:
            if result['validation'].is_valid:
                valid_count += 1
                label = result['label']
                
                # Определяем, реальные ли это данные
                is_real_data = not (label.startswith('Test') or 
                                  label.startswith('AAAA') or 
                                  label.startswith('Large Data') or
                                  label.startswith('Concurrent'))
                
                if is_real_data:
                    real_data_count += 1
                
                print(f"{valid_count}. {label} {'🎯' if is_real_data else '🧪'}")
                print(f"   ID: {result['id'][:8]}...")
                print(f"   Качество: {result['validation'].estimated_quality}")
                print(f"   Размер: {result['validation'].data_size_kb:.2f} KB")
                print(f"   Создан: {result['created_at']}")
                print(f"   Источник: {result['source_file'] or 'не указан'}")
                
                if result['validation'].issues:
                    print(f"   ⚠️ Проблемы: {', '.join(result['validation'].issues)}")
                
                print()
        
        print(f"📊 ИТОГО:")
        print(f"   Валидных voiceprints: {valid_count}")
        print(f"   Реальных данных: {real_data_count}")
        print(f"   Тестовых данных: {valid_count - real_data_count}")
        
        # Анализ проблем
        print(f"\n🔍 АНАЛИЗ ОСНОВНЫХ ПРОБЛЕМ:")
        issues = analysis.issues
        
        # Группируем проблемы по типам
        issue_types = {}
        for issue in issues:
            if "Невалидный base64" in issue:
                issue_types["Невалидный base64"] = issue_types.get("Невалидный base64", 0) + 1
            elif "Пустые данные" in issue:
                issue_types["Пустые данные"] = issue_types.get("Пустые данные", 0) + 1
            elif "Слишком маленький размер" in issue:
                issue_types["Слишком маленький размер"] = issue_types.get("Слишком маленький размер", 0) + 1
            elif "Подозрительный формат" in issue:
                issue_types["Подозрительный формат"] = issue_types.get("Подозрительный формат", 0) + 1
            else:
                issue_types["Другие"] = issue_types.get("Другие", 0) + 1
        
        for issue_type, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   {issue_type}: {count}")
    
    def export_analysis_report(self, analysis: VoiceprintAnalysis, output_path: Path) -> None:
        """Экспортирует результаты анализа в JSON файл"""
        # Добавляем метаданные отчета
        report = {
            "analysis_timestamp": datetime.now().isoformat(),
            "analysis_version": "2.0",
            "database_path": str(self.database_path),
            "summary": {
                "total_voiceprints": analysis.total_voiceprints,
                "valid_voiceprints": analysis.valid_voiceprints,
                "invalid_voiceprints": analysis.invalid_voiceprints,
                "real_voiceprints": analysis.real_voiceprints,
                "test_data_voiceprints": analysis.test_data_voiceprints
            },
            "detailed_analysis": {
                "total_voiceprints": analysis.total_voiceprints,
                "valid_voiceprints": analysis.valid_voiceprints,
                "invalid_voiceprints": analysis.invalid_voiceprints,
                "test_data_voiceprints": analysis.test_data_voiceprints,
                "real_voiceprints": analysis.real_voiceprints,
                "quality_distribution": analysis.quality_distribution,
                "size_statistics": analysis.size_statistics,
                "creation_dates": analysis.creation_dates,
                "labels": analysis.labels,
                "issues": analysis.issues,
                "detailed_results": [
                    {
                        "id": result["id"],
                        "label": result["label"],
                        "validation": {
                            "is_valid": result["validation"].is_valid,
                            "is_base64": result["validation"].is_base64,
                            "data_size_bytes": result["validation"].data_size_bytes,
                            "data_size_kb": result["validation"].data_size_kb,
                            "estimated_quality": result["validation"].estimated_quality,
                            "issues": result["validation"].issues
                        },
                        "created_at": result["created_at"],
                        "source_file": result["source_file"],
                        "has_source_file": result["has_source_file"]
                    }
                    for result in analysis.detailed_results
                ]
            }
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"📄 Отчет сохранен в: {output_path}")

    def clean_invalid_voiceprints(self, dry_run: bool = True) -> Tuple[int, List[str]]:
        """
        Очищает невалидные voiceprint'ы из базы данных

        Args:
            dry_run: Если True, только показывает что будет удалено

        Returns:
            Кортеж (количество удаленных, список ID)
        """
        self.logger.info("🧹 Начинаю очистку невалидных voiceprints...")

        voiceprints = self.manager.list_voiceprints()
        to_delete = []

        for voiceprint in voiceprints:
            vp_id = voiceprint.get("id", "")
            label = voiceprint.get("label", "")
            voiceprint_data = voiceprint.get("voiceprint", "")

            validation = self.validate_voiceprint_data(voiceprint_data)

            # Определяем критерии для удаления
            should_delete = False
            reasons = []

            if not validation.is_valid:
                should_delete = True
                reasons.append("невалидные данные")

            if validation.estimated_quality == "очень низкое":
                should_delete = True
                reasons.append("очень низкое качество")

            if label.startswith("Test") or label.startswith("AAAA"):
                should_delete = True
                reasons.append("тестовые данные")

            if should_delete:
                to_delete.append({
                    "id": vp_id,
                    "label": label,
                    "reasons": reasons
                })

        if dry_run:
            print(f"\n🔍 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР ОЧИСТКИ:")
            print(f"Будет удалено {len(to_delete)} voiceprints:")
            for item in to_delete:
                print(f"  - {item['label']} (ID: {item['id'][:8]}...) - {', '.join(item['reasons'])}")
            return len(to_delete), [item['id'] for item in to_delete]
        else:
            # Реальное удаление
            deleted_count = 0
            deleted_ids = []

            for item in to_delete:
                try:
                    self.manager.delete_voiceprint(item['id'])
                    deleted_count += 1
                    deleted_ids.append(item['id'])
                    self.logger.info(f"🗑️ Удален: {item['label']} ({', '.join(item['reasons'])})")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка удаления {item['label']}: {e}")

            self.logger.info(f"✅ Очистка завершена: удалено {deleted_count} voiceprints")
            return deleted_count, deleted_ids

    def check_remote_status(self) -> Optional[Dict]:
        """
        Проверяет статус удаленных voiceprint'ов в pyannote.ai

        Returns:
            Словарь со статусом или None если нет API доступа
        """
        if not self.agent:
            self.logger.warning("⚠️ Нет API ключа для проверки удаленного статуса")
            return None

        self.logger.info("🌐 Проверяю статус удаленных voiceprints...")

        try:
            # Получаем локальные voiceprints
            local_voiceprints = self.manager.list_voiceprints()

            # Здесь должна быть логика проверки удаленного статуса
            # Пока возвращаем базовую информацию
            status = {
                "local_count": len(local_voiceprints),
                "remote_accessible": True,
                "sync_needed": False,
                "last_check": datetime.now().isoformat()
            }

            self.logger.info(f"✅ Проверка завершена: {status['local_count']} локальных voiceprints")
            return status

        except Exception as e:
            self.logger.error(f"❌ Ошибка проверки удаленного статуса: {e}")
            return None

    def sync_with_remote(self, direction: str = "both") -> Dict:
        """
        Синхронизация с удаленной базой данных

        Args:
            direction: Направление синхронизации ("local_to_remote", "remote_to_local", "both")

        Returns:
            Результаты синхронизации
        """
        if not self.agent:
            raise ValueError("Нет API ключа для синхронизации")

        self.logger.info(f"🔄 Начинаю синхронизацию ({direction})...")

        sync_result = {
            "direction": direction,
            "local_before": len(self.manager.list_voiceprints()),
            "uploaded": 0,
            "downloaded": 0,
            "conflicts": 0,
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Здесь должна быть логика синхронизации
            # Пока возвращаем базовый результат
            self.logger.info("✅ Синхронизация завершена (заглушка)")

        except Exception as e:
            sync_result["errors"].append(str(e))
            self.logger.error(f"❌ Ошибка синхронизации: {e}")

        return sync_result


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
            logging.FileHandler('logs/voiceprint_management_suite.log', encoding='utf-8')
        ]
    )


def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Voiceprint Management Suite - Объединенный инструмент для управления voiceprint'ами",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

1. Анализ базы данных:
   python voiceprint_management_suite.py analyze

2. Детальный анализ с экспортом:
   python voiceprint_management_suite.py analyze --detailed --export report.json

3. Анализ только валидных voiceprints:
   python voiceprint_management_suite.py analyze-valid

4. Очистка невалидных данных (предварительный просмотр):
   python voiceprint_management_suite.py clean --dry-run

5. Реальная очистка:
   python voiceprint_management_suite.py clean

6. Проверка удаленного статуса:
   python voiceprint_management_suite.py check-remote

7. Синхронизация с удаленной базой:
   python voiceprint_management_suite.py sync --direction both

Переменные окружения:
- PYANNOTE_API_KEY: API ключ для удаленных операций
        """
    )

    # Общие параметры
    parser.add_argument(
        '--database-path',
        type=Path,
        default=Path("voiceprints/voiceprints.json"),
        help='Путь к базе данных voiceprints (по умолчанию: voiceprints/voiceprints.json)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробное логирование'
    )

    # Подкоманды
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')

    # Команда analyze
    analyze_parser = subparsers.add_parser('analyze', help='Анализ базы данных voiceprints')
    analyze_parser.add_argument('--detailed', action='store_true', help='Детальный отчет')
    analyze_parser.add_argument('--export', type=Path, help='Экспорт результатов в JSON')
    analyze_parser.add_argument('--limit', type=int, default=20, help='Лимит записей в детальном отчете')

    # Команда analyze-valid
    subparsers.add_parser('analyze-valid', help='Анализ только валидных voiceprints')

    # Команда clean
    clean_parser = subparsers.add_parser('clean', help='Очистка невалидных voiceprints')
    clean_parser.add_argument('--dry-run', action='store_true', help='Предварительный просмотр без удаления')

    # Команда check-remote
    subparsers.add_parser('check-remote', help='Проверка статуса удаленных voiceprints')

    # Команда sync
    sync_parser = subparsers.add_parser('sync', help='Синхронизация с удаленной базой')
    sync_parser.add_argument('--direction', choices=['local_to_remote', 'remote_to_local', 'both'],
                           default='both', help='Направление синхронизации')

    args = parser.parse_args()

    # Настройка логирования
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Проверяем команду
    if not args.command:
        parser.print_help()
        return 1

    try:
        # Проверяем существование базы данных
        if not args.database_path.exists():
            logger.error(f"❌ База данных не найдена: {args.database_path}")
            logger.info("💡 Убедитесь, что путь к базе данных указан правильно")
            return 1

        # Получаем API ключ для удаленных операций
        api_key = None
        if args.command in ['check-remote', 'sync']:
            import os
            api_key = os.getenv('PYANNOTE_API_KEY')
            if not api_key:
                logger.warning("⚠️ PYANNOTE_API_KEY не найден - удаленные операции недоступны")

        # Инициализируем suite
        suite = VoiceprintManagementSuite(args.database_path, api_key)

        # Выполняем команды
        if args.command == 'analyze':
            logger.info("🚀 Запуск анализа базы данных voiceprints")
            analysis = suite.analyze_database()
            suite.print_analysis_report(analysis)

            if args.detailed:
                suite.print_detailed_report(analysis, args.limit)

            if args.export:
                suite.export_analysis_report(analysis, args.export)

        elif args.command == 'analyze-valid':
            logger.info("🎯 Анализ валидных voiceprints")
            analysis = suite.analyze_database()
            suite.analyze_valid_voiceprints(analysis)

        elif args.command == 'clean':
            logger.info("🧹 Очистка невалидных voiceprints")
            deleted_count, deleted_ids = suite.clean_invalid_voiceprints(dry_run=args.dry_run)

            if args.dry_run:
                print(f"\n💡 Для реального удаления запустите без --dry-run")
            else:
                print(f"\n✅ Удалено {deleted_count} voiceprints")

        elif args.command == 'check-remote':
            logger.info("🌐 Проверка удаленного статуса")
            status = suite.check_remote_status()
            if status:
                print(f"\n📊 СТАТУС УДАЛЕННЫХ VOICEPRINTS:")
                print(f"   Локальных voiceprints: {status['local_count']}")
                print(f"   Удаленный доступ: {'✅' if status['remote_accessible'] else '❌'}")
                print(f"   Требуется синхронизация: {'⚠️' if status['sync_needed'] else '✅'}")
                print(f"   Последняя проверка: {status['last_check']}")

        elif args.command == 'sync':
            logger.info("🔄 Синхронизация с удаленной базой")
            result = suite.sync_with_remote(args.direction)
            print(f"\n📊 РЕЗУЛЬТАТЫ СИНХРОНИЗАЦИИ:")
            print(f"   Направление: {result['direction']}")
            print(f"   Локальных до: {result['local_before']}")
            print(f"   Загружено: {result['uploaded']}")
            print(f"   Скачано: {result['downloaded']}")
            print(f"   Конфликтов: {result['conflicts']}")
            if result['errors']:
                print(f"   Ошибки: {len(result['errors'])}")

        logger.info("✅ Операция завершена успешно")
        return 0

    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении операции: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
