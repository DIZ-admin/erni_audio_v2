#!/usr/bin/env python3
"""
CLI утилита для управления checkpoint'ами
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from checkpoint_manager import CheckpointManager, PipelineStage

def load_json(file_path):
    """Загрузить данные из JSON файла"""
    import json
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def list_checkpoints(checkpoint_manager: CheckpointManager, detailed: bool = False) -> None:
    """Список всех checkpoint'ов"""
    checkpoints_dir = checkpoint_manager.checkpoints_dir
    state_files = list(checkpoints_dir.glob("*_state.json"))
    
    if not state_files:
        print("📋 Checkpoint'ы не найдены")
        return
    
    print(f"📋 Найдено {len(state_files)} checkpoint'ов:")
    print("=" * 80)
    
    for state_file in sorted(state_files):
        try:
            data = load_json(state_file)
            pipeline_id = data.get('pipeline_id', 'unknown')
            input_file = data.get('input_file', 'unknown')
            created_at = data.get('created_at', 'unknown')
            status = "completed" if not data.get('failed_stage') else "failed"
            completed_stages = data.get('completed_stages', [])
            
            print(f"🔹 Pipeline ID: {pipeline_id}")
            print(f"   Файл: {input_file}")
            print(f"   Создан: {created_at}")
            print(f"   Статус: {status}")
            print(f"   Завершенные этапы: {', '.join(completed_stages) if completed_stages else 'нет'}")
            
            if detailed:
                checkpoints = data.get('checkpoints', [])
                print(f"   Checkpoint'ы ({len(checkpoints)}):")
                for cp in checkpoints:
                    status_icon = "✅" if cp.get('success') else "❌"
                    print(f"     {status_icon} {cp.get('stage', 'unknown')} - {cp.get('timestamp', 'unknown')}")
                    if not cp.get('success') and cp.get('error_message'):
                        print(f"       Ошибка: {cp.get('error_message')}")
            
            print("-" * 80)
            
        except Exception as e:
            print(f"⚠️ Ошибка чтения {state_file}: {e}")


def show_checkpoint(checkpoint_manager: CheckpointManager, pipeline_id: str) -> None:
    """Показать детали конкретного checkpoint'а"""
    checkpoints_dir = checkpoint_manager.checkpoints_dir
    state_file = checkpoints_dir / f"{pipeline_id}_state.json"
    
    if not state_file.exists():
        print(f"❌ Checkpoint с ID {pipeline_id} не найден")
        return
    
    try:
        data = load_json(state_file)
        
        print(f"📋 Детали checkpoint'а: {pipeline_id}")
        print("=" * 80)
        print(f"Входной файл: {data.get('input_file', 'unknown')}")
        print(f"Создан: {data.get('created_at', 'unknown')}")
        print(f"Обновлен: {data.get('last_updated', 'unknown')}")
        print(f"Текущий этап: {data.get('current_stage', 'нет')}")
        print(f"Неудачный этап: {data.get('failed_stage', 'нет')}")
        print(f"Завершенные этапы: {', '.join(data.get('completed_stages', []))}")
        
        checkpoints = data.get('checkpoints', [])
        print(f"\nCheckpoint'ы ({len(checkpoints)}):")
        print("-" * 80)
        
        for i, cp in enumerate(checkpoints, 1):
            status_icon = "✅" if cp.get('success') else "❌"
            print(f"{i}. {status_icon} {cp.get('stage', 'unknown')}")
            print(f"   Время: {cp.get('timestamp', 'unknown')}")
            print(f"   Выходной файл: {cp.get('output_file', 'нет')}")
            
            if cp.get('metadata'):
                print(f"   Метаданные: {json.dumps(cp['metadata'], indent=2, ensure_ascii=False)}")
            
            if not cp.get('success') and cp.get('error_message'):
                print(f"   ❌ Ошибка: {cp.get('error_message')}")
            
            print()
        
    except Exception as e:
        print(f"❌ Ошибка чтения checkpoint'а: {e}")


def validate_checkpoint(checkpoint_manager: CheckpointManager, pipeline_id: str) -> None:
    """Валидация checkpoint'а"""
    checkpoints_dir = checkpoint_manager.checkpoints_dir
    state_file = checkpoints_dir / f"{pipeline_id}_state.json"
    
    if not state_file.exists():
        print(f"❌ Checkpoint с ID {pipeline_id} не найден")
        return
    
    try:
        data = load_json(state_file)
        input_file = data.get('input_file', '')
        
        print(f"🔍 Валидация checkpoint'а: {pipeline_id}")
        print("=" * 80)
        
        # Валидируем файлы
        validation_results = checkpoint_manager.validate_checkpoint_files(input_file)
        
        if not validation_results:
            print("📋 Нет файлов для валидации")
            return
        
        valid_count = sum(1 for valid in validation_results.values() if valid)
        total_count = len(validation_results)
        
        print(f"📊 Результат: {valid_count}/{total_count} файлов валидны")
        print("-" * 80)
        
        for file_path, is_valid in validation_results.items():
            status_icon = "✅" if is_valid else "❌"
            file_exists = Path(file_path).exists()
            existence_icon = "📁" if file_exists else "🚫"
            
            print(f"{status_icon} {existence_icon} {file_path}")
            
            if not is_valid and file_exists:
                print(f"   ⚠️ Файл существует, но содержимое невалидно")
            elif not file_exists:
                print(f"   🚫 Файл не найден")
        
        if valid_count == total_count:
            print("\n✅ Все файлы checkpoint'а валидны")
        else:
            print(f"\n⚠️ {total_count - valid_count} файлов невалидны")
        
    except Exception as e:
        print(f"❌ Ошибка валидации: {e}")


def cleanup_checkpoints(checkpoint_manager: CheckpointManager, 
                       older_than_hours: int = None, 
                       invalid_only: bool = False,
                       dry_run: bool = False) -> None:
    """Очистка checkpoint'ов"""
    print("🧹 Очистка checkpoint'ов")
    print("=" * 80)
    
    if dry_run:
        print("🔍 Режим предварительного просмотра (файлы не будут удалены)")
    
    if invalid_only:
        print("🎯 Удаление только невалидных checkpoint'ов")
        # Здесь можно добавить логику удаления только невалидных checkpoint'ов
        print("⚠️ Функция удаления невалидных checkpoint'ов в разработке")
        return
    
    if older_than_hours:
        days_old = older_than_hours / 24
        print(f"🕒 Удаление checkpoint'ов старше {older_than_hours} часов")
    else:
        days_old = 7
        print(f"🕒 Удаление checkpoint'ов старше {days_old} дней")
    
    if not dry_run:
        removed_count = checkpoint_manager.cleanup_old_checkpoints(days_old=days_old)
        print(f"✅ Удалено {removed_count} checkpoint'ов")
    else:
        # Подсчитываем, сколько будет удалено
        checkpoints_dir = checkpoint_manager.checkpoints_dir
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        to_remove = []
        for state_file in checkpoints_dir.glob("*_state.json"):
            try:
                data = load_json(state_file)
                created_at = datetime.fromisoformat(data.get('created_at', ''))
                if created_at < cutoff_date:
                    to_remove.append(state_file)
            except:
                continue
        
        print(f"📋 Будет удалено {len(to_remove)} checkpoint'ов:")
        for file_path in to_remove:
            print(f"   🗑️ {file_path.name}")


def export_checkpoint(checkpoint_manager: CheckpointManager, 
                     pipeline_id: str, 
                     output_file: str) -> None:
    """Экспорт checkpoint'а"""
    checkpoints_dir = checkpoint_manager.checkpoints_dir
    state_file = checkpoints_dir / f"{pipeline_id}_state.json"
    
    if not state_file.exists():
        print(f"❌ Checkpoint с ID {pipeline_id} не найден")
        return
    
    try:
        data = load_json(state_file)
        
        # Добавляем метаданные экспорта
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "export_version": "1.0",
            "checkpoint_data": data
        }
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Checkpoint экспортирован в {output_path}")
        
    except Exception as e:
        print(f"❌ Ошибка экспорта: {e}")


def main():
    """Главная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Управление checkpoint'ами Speech Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s list                          # Список всех checkpoint'ов
  %(prog)s list --detailed               # Детальный список
  %(prog)s show abc123def456             # Показать конкретный checkpoint
  %(prog)s validate abc123def456         # Валидировать checkpoint
  %(prog)s cleanup --older-than 24       # Очистить старше 24 часов
  %(prog)s cleanup --invalid --dry-run   # Предварительный просмотр очистки
  %(prog)s export abc123def456 backup.json  # Экспорт checkpoint'а
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда list
    list_parser = subparsers.add_parser('list', help='Список checkpoint\'ов')
    list_parser.add_argument('--detailed', action='store_true', 
                           help='Показать детальную информацию')
    
    # Команда show
    show_parser = subparsers.add_parser('show', help='Показать checkpoint')
    show_parser.add_argument('pipeline_id', help='ID checkpoint\'а')
    
    # Команда validate
    validate_parser = subparsers.add_parser('validate', help='Валидировать checkpoint')
    validate_parser.add_argument('pipeline_id', help='ID checkpoint\'а')
    
    # Команда cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Очистить checkpoint\'ы')
    cleanup_parser.add_argument('--older-than', type=int, metavar='HOURS',
                               help='Удалить checkpoint\'ы старше N часов')
    cleanup_parser.add_argument('--invalid', action='store_true',
                               help='Удалить только невалидные checkpoint\'ы')
    cleanup_parser.add_argument('--dry-run', action='store_true',
                               help='Предварительный просмотр (не удалять)')
    
    # Команда export
    export_parser = subparsers.add_parser('export', help='Экспорт checkpoint\'а')
    export_parser.add_argument('pipeline_id', help='ID checkpoint\'а')
    export_parser.add_argument('output_file', help='Файл для экспорта')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    setup_logging()
    checkpoint_manager = CheckpointManager()
    
    try:
        if args.command == 'list':
            list_checkpoints(checkpoint_manager, detailed=args.detailed)
        elif args.command == 'show':
            show_checkpoint(checkpoint_manager, args.pipeline_id)
        elif args.command == 'validate':
            validate_checkpoint(checkpoint_manager, args.pipeline_id)
        elif args.command == 'cleanup':
            cleanup_checkpoints(
                checkpoint_manager,
                older_than_hours=args.older_than,
                invalid_only=args.invalid,
                dry_run=args.dry_run
            )
        elif args.command == 'export':
            export_checkpoint(checkpoint_manager, args.pipeline_id, args.output_file)
    
    except KeyboardInterrupt:
        print("\n⚠️ Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
