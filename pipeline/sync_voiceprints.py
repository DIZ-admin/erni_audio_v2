#!/usr/bin/env python3
"""
Скрипт для синхронизации локальной и удаленной базы голосовых отпечатков

Этот скрипт обеспечивает синхронизацию между локальной базой voiceprints
и удаленными voiceprints на сервере pyannote.ai.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import json
from datetime import datetime

# Добавляем корневую директорию в путь для импорта модулей
sys.path.append(str(Path(__file__).parent.parent))

# Загружаем переменные окружения из .env файла
def load_env_file():
    """Загружает переменные окружения из .env файла."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()

from pipeline.voiceprint_manager import VoiceprintManager
from pipeline.voiceprint_agent import VoiceprintAgent
from pipeline.check_remote_voiceprints import PyannoteAPIChecker
from pipeline.config import get_config


def setup_logging(verbose: bool = False) -> None:
    """Настройка логирования."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


class VoiceprintSynchronizer:
    """Класс для синхронизации локальных и удаленных voiceprints."""
    
    def __init__(self, api_key: str):
        """
        Инициализация синхронизатора.
        
        Args:
            api_key: API ключ pyannote.ai
        """
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
        # Инициализируем компоненты
        self.local_manager = VoiceprintManager()
        self.remote_checker = PyannoteAPIChecker(api_key)
        self.voiceprint_agent = VoiceprintAgent(api_key)
    
    def analyze_sync_status(self) -> Dict[str, any]:
        """
        Анализирует текущее состояние синхронизации.
        
        Returns:
            Словарь с анализом состояния
        """
        self.logger.info("🔍 Анализирую состояние синхронизации...")
        
        # Получаем локальные voiceprints
        local_voiceprints = self.local_manager.list_voiceprints()
        
        # Получаем удаленные voiceprints
        remote_jobs = self.remote_checker.get_voiceprint_jobs(100)
        remote_analysis = self.remote_checker.analyze_voiceprint_jobs(remote_jobs)
        
        analysis = {
            "local_count": len(local_voiceprints),
            "remote_count": len(remote_analysis["voiceprints_created"]),
            "local_voiceprints": local_voiceprints,
            "remote_voiceprints": remote_analysis["voiceprints_created"],
            "sync_needed": False,
            "actions_required": [],
            "target_voiceprint": None
        }
        
        # Определяем целевой voiceprint (Andreas Wermelinger)
        target_label = "Andreas Wermelinger"
        target_local = None
        target_remote = []
        
        # Ищем Andreas Wermelinger в локальной базе
        for vp in local_voiceprints:
            if vp["label"] == target_label:
                target_local = vp
                break
        
        # Ищем соответствующие voiceprints на сервере
        # Поскольку у нас нет прямого способа определить label удаленных voiceprints,
        # мы будем ориентироваться на размер и время создания
        if target_local:
            target_size = len(target_local["voiceprint"])
            for remote_vp in remote_analysis["voiceprints_created"]:
                # Проверяем соответствие по размеру (с небольшой погрешностью)
                if abs(remote_vp["voiceprint_size"] - target_size) < 100:
                    target_remote.append(remote_vp)
        
        analysis["target_voiceprint"] = {
            "label": target_label,
            "local": target_local,
            "remote": target_remote,
            "remote_count": len(target_remote)
        }
        
        # Определяем необходимые действия
        if target_local and len(target_remote) == 0:
            analysis["sync_needed"] = True
            analysis["actions_required"].append("create_remote")
            self.logger.info(f"📤 Нужно создать удаленный voiceprint для '{target_label}'")
            
        elif target_local and len(target_remote) == 1:
            analysis["sync_needed"] = False
            self.logger.info(f"✅ Синхронизация в порядке: 1 локальный, 1 удаленный")
            
        elif target_local and len(target_remote) > 1:
            analysis["sync_needed"] = True
            analysis["actions_required"].append("remove_duplicate_remote")
            self.logger.info(f"🗑️ Нужно удалить дублированные удаленные voiceprints ({len(target_remote)} найдено)")
            
        elif not target_local and len(target_remote) > 0:
            analysis["sync_needed"] = True
            analysis["actions_required"].append("recreate_local")
            self.logger.info(f"📥 Нужно пересоздать локальный voiceprint")
            
        else:
            analysis["sync_needed"] = True
            analysis["actions_required"].append("create_both")
            self.logger.info(f"🆕 Нужно создать voiceprint и локально, и удаленно")
        
        return analysis
    
    def sync_voiceprints(self, strategy: str = "keep_local") -> Dict[str, any]:
        """
        Выполняет синхронизацию voiceprints.
        
        Args:
            strategy: Стратегия синхронизации:
                     - "keep_local": Приоритет локальной версии
                     - "keep_remote": Приоритет удаленной версии
                     - "recreate": Пересоздать все заново
        
        Returns:
            Результаты синхронизации
        """
        self.logger.info(f"🔄 Начинаю синхронизацию (стратегия: {strategy})...")
        
        # Анализируем текущее состояние
        analysis = self.analyze_sync_status()
        
        if not analysis["sync_needed"]:
            self.logger.info("✅ Синхронизация не требуется")
            return {"status": "no_sync_needed", "analysis": analysis}
        
        sync_result = {
            "status": "in_progress",
            "actions_performed": [],
            "errors": [],
            "final_state": None
        }
        
        target_label = "Andreas Wermelinger"
        audio_file = Path("voiceprints/Andreas_Wermelinger_opt.wav")
        
        try:
            if strategy == "keep_local":
                sync_result = self._sync_keep_local(analysis, target_label, audio_file)
            elif strategy == "keep_remote":
                sync_result = self._sync_keep_remote(analysis, target_label)
            elif strategy == "recreate":
                sync_result = self._sync_recreate(analysis, target_label, audio_file)
            else:
                raise ValueError(f"Неизвестная стратегия синхронизации: {strategy}")
            
            # Проверяем финальное состояние
            final_analysis = self.analyze_sync_status()
            sync_result["final_state"] = final_analysis
            sync_result["status"] = "completed" if not final_analysis["sync_needed"] else "partial"
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка синхронизации: {e}")
            sync_result["status"] = "failed"
            sync_result["errors"].append(str(e))
        
        return sync_result
    
    def _sync_keep_local(self, analysis: Dict, target_label: str, audio_file: Path) -> Dict:
        """Синхронизация с приоритетом локальной версии."""
        result = {"actions_performed": [], "errors": []}
        
        target_info = analysis["target_voiceprint"]
        
        if "create_remote" in analysis["actions_required"]:
            # Создаем удаленный voiceprint на основе локального
            self.logger.info(f"📤 Создаю удаленный voiceprint для '{target_label}'...")
            try:
                if audio_file.exists():
                    voiceprint_result = self.voiceprint_agent.create_voiceprint(
                        audio_file=audio_file,
                        label=target_label,
                        max_duration_check=True
                    )
                    result["actions_performed"].append("created_remote_voiceprint")
                    self.logger.info(f"✅ Удаленный voiceprint создан")
                else:
                    raise FileNotFoundError(f"Аудиофайл не найден: {audio_file}")
            except Exception as e:
                result["errors"].append(f"Ошибка создания удаленного voiceprint: {e}")
        
        if "remove_duplicate_remote" in analysis["actions_required"]:
            # Примечание: API pyannote.ai не предоставляет прямого способа удаления voiceprints
            # Они автоматически удаляются через 24 часа
            self.logger.warning("⚠️ Обнаружены дублированные удаленные voiceprints")
            self.logger.info("ℹ️ Удаленные voiceprints автоматически удаляются через 24 часа")
            result["actions_performed"].append("noted_duplicate_remote")
        
        return result
    
    def _sync_keep_remote(self, analysis: Dict, target_label: str) -> Dict:
        """Синхронизация с приоритетом удаленной версии."""
        result = {"actions_performed": [], "errors": []}
        
        # Примечание: Мы не можем получить данные voiceprint с сервера напрямую
        # Поэтому эта стратегия ограничена
        self.logger.warning("⚠️ Стратегия 'keep_remote' ограничена возможностями API")
        self.logger.info("ℹ️ API pyannote.ai не позволяет скачивать voiceprint данные")
        
        result["actions_performed"].append("strategy_limited")
        return result
    
    def _sync_recreate(self, analysis: Dict, target_label: str, audio_file: Path) -> Dict:
        """Полное пересоздание voiceprints."""
        result = {"actions_performed": [], "errors": []}
        
        self.logger.info(f"🔄 Пересоздаю voiceprints для '{target_label}'...")
        
        # Удаляем локальный voiceprint если существует
        target_info = analysis["target_voiceprint"]
        if target_info["local"]:
            self.local_manager.delete_voiceprint(target_info["local"]["id"])
            result["actions_performed"].append("deleted_local_voiceprint")
            self.logger.info("🗑️ Локальный voiceprint удален")
        
        # Создаем новый voiceprint
        try:
            if audio_file.exists():
                # Создаем удаленный voiceprint
                voiceprint_result = self.voiceprint_agent.create_voiceprint(
                    audio_file=audio_file,
                    label=target_label,
                    max_duration_check=True
                )
                
                # Сохраняем в локальную базу
                vp_id = self.local_manager.add_voiceprint(
                    label=target_label,
                    voiceprint_data=voiceprint_result["voiceprint"],
                    source_file=str(audio_file),
                    metadata={
                        "recreated_at": datetime.now().isoformat(),
                        "sync_strategy": "recreate"
                    }
                )
                
                result["actions_performed"].extend(["created_remote_voiceprint", "created_local_voiceprint"])
                self.logger.info(f"✅ Voiceprints пересозданы (ID: {vp_id})")
            else:
                raise FileNotFoundError(f"Аудиофайл не найден: {audio_file}")
                
        except Exception as e:
            result["errors"].append(f"Ошибка пересоздания voiceprints: {e}")
        
        return result


def print_sync_report(sync_result: Dict) -> None:
    """
    Выводит отчет о синхронизации.
    
    Args:
        sync_result: Результаты синхронизации
    """
    print("\n" + "="*80)
    print("🔄 ОТЧЕТ ПО СИНХРОНИЗАЦИИ ОБРАЗЦОВ ГОЛОСОВ")
    print("="*80)
    
    status = sync_result["status"]
    if status == "no_sync_needed":
        print("✅ СИНХРОНИЗАЦИЯ НЕ ТРЕБУЕТСЯ")
        print("   Локальная и удаленная базы уже синхронизированы")
    elif status == "completed":
        print("✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
    elif status == "partial":
        print("⚠️ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА ЧАСТИЧНО")
    elif status == "failed":
        print("❌ СИНХРОНИЗАЦИЯ НЕ УДАЛАСЬ")
    else:
        print(f"🔄 СТАТУС: {status}")
    
    # Выполненные действия
    if sync_result.get("actions_performed"):
        print(f"\n📋 ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ:")
        for action in sync_result["actions_performed"]:
            print(f"   ✓ {action}")
    
    # Ошибки
    if sync_result.get("errors"):
        print(f"\n❌ ОШИБКИ:")
        for error in sync_result["errors"]:
            print(f"   • {error}")
    
    # Финальное состояние
    if sync_result.get("final_state"):
        final = sync_result["final_state"]
        print(f"\n📊 ФИНАЛЬНОЕ СОСТОЯНИЕ:")
        print(f"   Локальных voiceprints: {final['local_count']}")
        print(f"   Удаленных voiceprints: {final['remote_count']}")
        
        target = final["target_voiceprint"]
        print(f"   Целевой voiceprint '{target['label']}':")
        print(f"     Локально: {'✅' if target['local'] else '❌'}")
        print(f"     Удаленно: {target['remote_count']} шт.")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Синхронизация локальной и удаленной базы голосовых отпечатков",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Стратегии синхронизации:
  keep_local   - Приоритет локальной версии (по умолчанию)
  keep_remote  - Приоритет удаленной версии (ограничено API)
  recreate     - Пересоздать все заново

Примеры использования:
  python sync_voiceprints.py                           # Анализ без изменений
  python sync_voiceprints.py --sync keep_local         # Синхронизация с приоритетом локальной версии
  python sync_voiceprints.py --sync recreate           # Полное пересоздание
  python sync_voiceprints.py --export report.json     # Экспорт результатов
        """
    )
    
    parser.add_argument(
        "--sync",
        choices=["keep_local", "keep_remote", "recreate"],
        help="Выполнить синхронизацию с указанной стратегией"
    )
    
    parser.add_argument(
        "--export",
        type=Path,
        help="Экспортировать результаты в JSON файл"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробное логирование"
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🚀 Запуск синхронизации образцов голосов")
        
        # Получаем API ключ
        try:
            config = get_config()
            api_key = config.get_api_key("pyannote")
        except Exception as e:
            logger.error(f"❌ Ошибка получения API ключа pyannote: {e}")
            logger.info("💡 Убедитесь, что переменная PYANNOTE_API_KEY установлена")
            return 1
        
        # Инициализируем синхронизатор
        synchronizer = VoiceprintSynchronizer(api_key)
        
        if args.sync:
            # Выполняем синхронизацию
            sync_result = synchronizer.sync_voiceprints(args.sync)
        else:
            # Только анализ
            analysis = synchronizer.analyze_sync_status()
            sync_result = {"status": "analysis_only", "analysis": analysis}
        
        # Выводим отчет
        print_sync_report(sync_result)
        
        # Экспорт если требуется
        if args.export:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "sync_result": sync_result
            }
            
            with open(args.export, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 Отчет экспортирован в: {args.export}")
        
        logger.info("✅ Операция завершена успешно")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении синхронизации: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
