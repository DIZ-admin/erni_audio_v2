#!/usr/bin/env python3
"""
CLI утилита для управления голосовыми отпечатками (voiceprints)
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

# Загружаем переменные окружения из .env файла (если есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pipeline.voiceprint_agent import VoiceprintAgent
from pipeline.voiceprint_manager import VoiceprintManager


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_voiceprint(args):
    """Создание нового голосового отпечатка"""
    logger = logging.getLogger(__name__)
    
    # Проверяем API ключ
    api_key = os.getenv("PYANNOTEAI_API_TOKEN") or os.getenv("PYANNOTE_API_KEY")
    if not api_key:
        logger.error("❌ Отсутствует PYANNOTEAI_API_TOKEN или PYANNOTE_API_KEY")
        sys.exit(1)
    
    # Валидация файла
    audio_file = Path(args.audio_file)
    if not audio_file.exists():
        logger.error(f"❌ Аудиофайл не найден: {audio_file}")
        sys.exit(1)
    
    try:
        # Создаем voiceprint
        logger.info(f"🎵 Создаю voiceprint для '{args.label}' из {audio_file.name}")
        
        voiceprint_agent = VoiceprintAgent(api_key)
        
        # Показываем оценку стоимости если запрошено
        if args.show_cost:
            cost_info = voiceprint_agent.estimate_cost(audio_file)
            print(f"\n💰 Оценка стоимости:")
            print(f"📁 Размер файла: {cost_info['file_size_mb']} MB")
            print(f"💵 Примерная стоимость: ${cost_info['estimated_cost_usd']}")
            print(f"💡 {cost_info['note']}\n")
        
        voiceprint_data = voiceprint_agent.create_voiceprint(
            audio_file=audio_file,
            label=args.label,
            max_duration_check=not args.skip_duration_check
        )
        
        # Сохраняем в базу
        manager = VoiceprintManager()
        voiceprint_id = manager.add_voiceprint(
            label=args.label,
            voiceprint_data=voiceprint_data["voiceprint"],
            source_file=str(audio_file),
            metadata={
                "duration": voiceprint_data["duration"],
                "file_size_mb": voiceprint_data["file_size_mb"],
                "created_via": "voiceprint_cli"
            }
        )
        
        print(f"✅ Voiceprint создан успешно!")
        print(f"📝 Имя: {args.label}")
        print(f"🆔 ID: {voiceprint_id}")
        print(f"⏱️ Время создания: {voiceprint_data['duration']:.2f}с")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания voiceprint: {e}")
        sys.exit(1)


def list_voiceprints(args):
    """Список всех голосовых отпечатков"""
    manager = VoiceprintManager()
    voiceprints = manager.list_voiceprints()
    
    if not voiceprints:
        print("📭 База voiceprints пуста")
        return
    
    print(f"📋 Найдено {len(voiceprints)} voiceprints:\n")
    
    for vp in sorted(voiceprints, key=lambda x: x["created_at"]):
        print(f"👤 {vp['label']}")
        print(f"   🆔 ID: {vp['id']}")
        print(f"   📅 Создан: {vp['created_at']}")
        if vp.get("source_file"):
            print(f"   📁 Файл: {Path(vp['source_file']).name}")
        print()


def search_voiceprints(args):
    """Поиск голосовых отпечатков"""
    manager = VoiceprintManager()
    results = manager.search_voiceprints(args.query)
    
    if not results:
        print(f"🔍 Voiceprints не найдены по запросу: '{args.query}'")
        return
    
    print(f"🔍 Найдено {len(results)} voiceprints по запросу '{args.query}':\n")
    
    for vp in results:
        print(f"👤 {vp['label']}")
        print(f"   🆔 ID: {vp['id']}")
        print(f"   📅 Создан: {vp['created_at']}")
        print()


def delete_voiceprint(args):
    """Удаление голосового отпечатка"""
    manager = VoiceprintManager()
    
    # Поиск по имени или ID
    voiceprint = None
    if args.identifier.startswith("vp_") or len(args.identifier) > 20:
        # Похоже на ID
        voiceprint = manager.get_voiceprint(args.identifier)
    else:
        # Поиск по имени
        voiceprint = manager.get_voiceprint_by_label(args.identifier)
    
    if not voiceprint:
        print(f"❌ Voiceprint не найден: '{args.identifier}'")
        sys.exit(1)
    
    # Подтверждение удаления
    if not args.force:
        response = input(f"⚠️ Удалить voiceprint '{voiceprint['label']}'? (y/N): ")
        if response.lower() != 'y':
            print("❌ Удаление отменено")
            return
    
    if manager.delete_voiceprint(voiceprint["id"]):
        print(f"✅ Voiceprint '{voiceprint['label']}' удален")
    else:
        print(f"❌ Ошибка удаления voiceprint")


def show_statistics(args):
    """Показать статистику базы voiceprints"""
    manager = VoiceprintManager()
    stats = manager.get_statistics()
    
    print("📊 Статистика базы voiceprints:")
    print(f"📝 Всего voiceprints: {stats['total']}")
    
    if stats['total'] > 0:
        print(f"👥 Имена: {', '.join(stats['labels'])}")
        print(f"📅 Самый старый: {stats['oldest']}")
        print(f"📅 Самый новый: {stats['newest']}")
    
    print(f"💾 База данных: {stats['database_path']}")
    print(f"📏 Размер базы: {stats['database_size_kb']} KB")


def export_voiceprints(args):
    """Экспорт voiceprints в JSON файл"""
    manager = VoiceprintManager()
    
    labels = args.labels.split(',') if args.labels else None
    if labels:
        labels = [label.strip() for label in labels]
    
    output_path = Path(args.output)
    manager.export_voiceprints(output_path, labels)
    
    print(f"✅ Voiceprints экспортированы в {output_path}")


def import_voiceprints(args):
    """Импорт voiceprints из JSON файла"""
    manager = VoiceprintManager()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        sys.exit(1)
    
    count = manager.import_voiceprints(input_path, args.overwrite)
    print(f"✅ Импортировано {count} voiceprints из {input_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CLI утилита для управления голосовыми отпечатками (voiceprints)"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда create
    create_parser = subparsers.add_parser('create', help='Создать новый voiceprint')
    create_parser.add_argument('audio_file', help='Путь к аудиофайлу (≤30 секунд)')
    create_parser.add_argument('label', help='Человекочитаемое имя (например, "John Doe")')
    create_parser.add_argument('--show-cost', action='store_true', help='Показать оценку стоимости')
    create_parser.add_argument('--skip-duration-check', action='store_true', 
                              help='Пропустить проверку длительности файла')
    
    # Команда list
    list_parser = subparsers.add_parser('list', help='Показать все voiceprints')
    
    # Команда search
    search_parser = subparsers.add_parser('search', help='Поиск voiceprints')
    search_parser.add_argument('query', help='Поисковый запрос')
    
    # Команда delete
    delete_parser = subparsers.add_parser('delete', help='Удалить voiceprint')
    delete_parser.add_argument('identifier', help='Имя или ID voiceprint для удаления')
    delete_parser.add_argument('--force', action='store_true', help='Удалить без подтверждения')
    
    # Команда stats
    stats_parser = subparsers.add_parser('stats', help='Показать статистику')
    
    # Команда export
    export_parser = subparsers.add_parser('export', help='Экспорт voiceprints в JSON')
    export_parser.add_argument('output', help='Путь для сохранения JSON файла')
    export_parser.add_argument('--labels', help='Список имен через запятую (по умолчанию все)')
    
    # Команда import
    import_parser = subparsers.add_parser('import', help='Импорт voiceprints из JSON')
    import_parser.add_argument('input', help='Путь к JSON файлу')
    import_parser.add_argument('--overwrite', action='store_true', 
                              help='Перезаписать существующие voiceprints')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging()
    
    # Выполняем команду
    if args.command == 'create':
        create_voiceprint(args)
    elif args.command == 'list':
        list_voiceprints(args)
    elif args.command == 'search':
        search_voiceprints(args)
    elif args.command == 'delete':
        delete_voiceprint(args)
    elif args.command == 'stats':
        show_statistics(args)
    elif args.command == 'export':
        export_voiceprints(args)
    elif args.command == 'import':
        import_voiceprints(args)


if __name__ == "__main__":
    main()
