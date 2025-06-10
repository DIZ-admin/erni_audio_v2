#!/usr/bin/env python3
"""
Скрипт для проверки образцов голосов на сервере pyannote.ai

Этот скрипт подключается к pyannote.ai API и проверяет:
- Доступные voiceprints на сервере
- Статус API ключа
- Информацию об аккаунте
- Сравнение с локальной базой данных
"""

import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import json
from datetime import datetime
import requests

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


class PyannoteAPIChecker:
    """Класс для проверки API pyannote.ai и удаленных voiceprints."""
    
    def __init__(self, api_key: str):
        """
        Инициализация checker'а.
        
        Args:
            api_key: API ключ pyannote.ai
        """
        self.api_key = api_key
        self.base_url = "https://api.pyannote.ai/v1"
        self.logger = logging.getLogger(__name__)
    
    def validate_api_key(self) -> Dict[str, any]:
        """
        Проверяет валидность API ключа.
        
        Returns:
            Словарь с результатами проверки
        """
        self.logger.info("🔑 Проверяю API ключ pyannote.ai...")
        
        result = {
            "is_valid": False,
            "error": None,
            "account_info": None
        }
        
        try:
            # Пробуем сделать простой запрос к API
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # Используем endpoint для проверки аккаунта (если доступен)
            # Если нет специального endpoint, используем любой доступный
            response = requests.get(
                f"{self.base_url}/jobs",  # Получаем список jobs
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result["is_valid"] = True
                self.logger.info("✅ API ключ валиден")
            elif response.status_code == 401:
                result["error"] = "Неверный API ключ"
                self.logger.error("❌ Неверный API ключ")
            elif response.status_code == 403:
                result["error"] = "Доступ запрещен"
                self.logger.error("❌ Доступ запрещен")
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
                self.logger.error(f"❌ Ошибка API: {result['error']}")
                
        except requests.RequestException as e:
            result["error"] = f"Ошибка сети: {e}"
            self.logger.error(f"❌ Ошибка подключения: {e}")
        
        return result
    
    def get_recent_jobs(self, limit: int = 20) -> List[Dict]:
        """
        Получает список недавних jobs с сервера.

        Args:
            limit: Максимальное количество jobs для получения

        Returns:
            Список jobs
        """
        self.logger.info(f"📋 Получаю список недавних jobs (лимит: {limit})...")

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # Получаем список jobs с правильными параметрами
            response = requests.get(
                f"{self.base_url}/jobs",
                headers=headers,
                params={"take": min(limit, 100)},  # API поддерживает максимум 100
                timeout=30
            )

            if response.status_code != 200:
                error_text = ""
                try:
                    error_detail = response.json().get("detail", response.text)
                    error_text = f": {error_detail}"
                except:
                    error_text = f": {response.text}"
                raise RuntimeError(f"Ошибка получения jobs: HTTP {response.status_code}{error_text}")

            jobs_data = response.json()
            jobs = jobs_data.get("items", [])
            total = jobs_data.get("total", 0)

            self.logger.info(f"✅ Получено {len(jobs)} jobs из {total} общих")

            return jobs

        except Exception as e:
            self.logger.error(f"❌ Ошибка получения jobs: {e}")
            return []
    
    def get_voiceprint_jobs(self, limit: int = 50) -> List[Dict]:
        """
        Получает список voiceprint jobs с сервера.

        Args:
            limit: Максимальное количество jobs для получения

        Returns:
            Список voiceprint jobs с деталями
        """
        self.logger.info(f"🎯 Ищу voiceprint jobs (лимит: {limit})...")

        # Сначала попробуем получить только успешные jobs
        successful_jobs = self.get_jobs_by_status("succeeded", limit)
        self.logger.info(f"📊 Получено {len(successful_jobs)} успешных jobs")

        voiceprint_jobs = []

        for job in successful_jobs:
            # Получаем детальную информацию о job
            job_details = self.get_job_details(job.get("id", ""))
            if job_details and self._is_voiceprint_job_from_details(job_details):
                voiceprint_jobs.append(job_details)

        # Если не нашли достаточно, проверим все jobs
        if len(voiceprint_jobs) < 5:
            self.logger.info("🔍 Проверяю все jobs для поиска voiceprint jobs...")
            all_jobs = self.get_recent_jobs(limit)

            for job in all_jobs:
                if job.get("id") not in [vj.get("id") for vj in voiceprint_jobs]:
                    job_details = self.get_job_details(job.get("id", ""))
                    if job_details and self._is_voiceprint_job_from_details(job_details):
                        voiceprint_jobs.append(job_details)

        self.logger.info(f"✅ Найдено {len(voiceprint_jobs)} voiceprint jobs")
        return voiceprint_jobs

    def get_jobs_by_status(self, status: str, limit: int = 50) -> List[Dict]:
        """
        Получает jobs с определенным статусом.

        Args:
            status: Статус jobs (succeeded, failed, pending, etc.)
            limit: Максимальное количество jobs

        Returns:
            Список jobs
        """
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}

            response = requests.get(
                f"{self.base_url}/jobs",
                headers=headers,
                params={"take": min(limit, 100), "status": status},
                timeout=30
            )

            if response.status_code == 200:
                jobs_data = response.json()
                return jobs_data.get("items", [])
            else:
                self.logger.warning(f"⚠️ Не удалось получить jobs со статусом {status}: HTTP {response.status_code}")
                return []

        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка получения jobs со статусом {status}: {e}")
            return []

    def _is_voiceprint_job_from_details(self, job_details: Dict) -> bool:
        """
        Проверяет, является ли job voiceprint job на основе детальной информации.

        Args:
            job_details: Детальные данные job'а

        Returns:
            True если это voiceprint job
        """
        # Проверяем наличие voiceprint в output
        output = job_details.get("output", {})
        has_voiceprint = "voiceprint" in output and output.get("voiceprint") is not None

        # Проверяем тип job'а или endpoint
        job_type = str(job_details.get("type", "")).lower()
        endpoint = str(job_details.get("endpoint", "")).lower()

        return (
            has_voiceprint or
            "voiceprint" in job_type or
            "voiceprint" in endpoint
        )
    
    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """
        Получает детальную информацию о job.
        
        Args:
            job_id: ID job'а
            
        Returns:
            Детали job'а или None
        """
        if not job_id:
            return None
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(
                f"{self.base_url}/jobs/{job_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"⚠️ Не удалось получить детали job {job_id}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка получения деталей job {job_id}: {e}")
            return None
    

    
    def analyze_voiceprint_jobs(self, jobs: List[Dict]) -> Dict[str, any]:
        """
        Анализирует voiceprint jobs.
        
        Args:
            jobs: Список voiceprint jobs
            
        Returns:
            Результаты анализа
        """
        analysis = {
            "total_jobs": len(jobs),
            "successful_jobs": 0,
            "failed_jobs": 0,
            "pending_jobs": 0,
            "voiceprints_created": [],
            "recent_activity": [],
            "status_distribution": {},
            "creation_dates": []
        }
        
        for job in jobs:
            status = job.get("status", "unknown").lower()
            
            # Подсчет по статусам
            analysis["status_distribution"][status] = analysis["status_distribution"].get(status, 0) + 1
            
            if status == "succeeded":
                analysis["successful_jobs"] += 1
                
                # Извлекаем информацию о созданном voiceprint
                output = job.get("output", {})
                voiceprint_data = output.get("voiceprint")

                if voiceprint_data:
                    voiceprint_info = {
                        "job_id": job.get("id"),
                        "created_at": job.get("createdAt") or job.get("created_at"),
                        "voiceprint_size": len(voiceprint_data) if voiceprint_data else 0,
                        "input_url": job.get("input", {}).get("url", "")
                    }
                    analysis["voiceprints_created"].append(voiceprint_info)
                    
            elif status == "failed":
                analysis["failed_jobs"] += 1
            elif status in ["created", "processing", "running"]:
                analysis["pending_jobs"] += 1
            
            # Даты создания
            created_at = job.get("createdAt") or job.get("created_at")
            if created_at:
                analysis["creation_dates"].append(created_at)

            # Недавняя активность
            analysis["recent_activity"].append({
                "job_id": job.get("id", "unknown"),
                "status": status,
                "created_at": created_at or "unknown",
                "input_url": job.get("input", {}).get("url", "")
            })
        
        return analysis


def compare_with_local_database(remote_analysis: Dict, local_manager: VoiceprintManager) -> Dict:
    """
    Сравнивает удаленные voiceprints с локальной базой данных.
    
    Args:
        remote_analysis: Анализ удаленных voiceprints
        local_manager: Менеджер локальной базы
        
    Returns:
        Результаты сравнения
    """
    logger = logging.getLogger(__name__)
    logger.info("🔄 Сравниваю с локальной базой данных...")
    
    local_voiceprints = local_manager.list_voiceprints()
    
    comparison = {
        "local_count": len(local_voiceprints),
        "remote_successful_count": remote_analysis["successful_jobs"],
        "remote_total_count": remote_analysis["total_jobs"],
        "sync_status": "unknown",
        "recommendations": []
    }
    
    # Анализ синхронизации
    if comparison["local_count"] == 0 and comparison["remote_successful_count"] == 0:
        comparison["sync_status"] = "both_empty"
        comparison["recommendations"].append("Создайте первые voiceprints")
    elif comparison["local_count"] > 0 and comparison["remote_successful_count"] == 0:
        comparison["sync_status"] = "local_only"
        comparison["recommendations"].append("Локальные voiceprints не синхронизированы с сервером")
    elif comparison["local_count"] == 0 and comparison["remote_successful_count"] > 0:
        comparison["sync_status"] = "remote_only"
        comparison["recommendations"].append("На сервере есть voiceprints, но локальная база пуста")
    else:
        comparison["sync_status"] = "both_have_data"
        comparison["recommendations"].append("И локально, и на сервере есть данные")
    
    return comparison


def print_analysis_report(api_result: Dict, jobs_analysis: Dict, comparison: Dict) -> None:
    """
    Выводит отчет по анализу удаленных voiceprints.
    
    Args:
        api_result: Результат проверки API
        jobs_analysis: Анализ jobs
        comparison: Сравнение с локальной базой
    """
    print("\n" + "="*80)
    print("🌐 ОТЧЕТ ПО ПРОВЕРКЕ УДАЛЕННЫХ ОБРАЗЦОВ ГОЛОСОВ (PYANNOTE.AI)")
    print("="*80)
    
    # Статус API
    print(f"\n🔑 СТАТУС API:")
    if api_result["is_valid"]:
        print("   ✅ API ключ валиден")
    else:
        print(f"   ❌ Проблема с API: {api_result['error']}")
        return
    
    # Статистика jobs
    print(f"\n📊 СТАТИСТИКА JOBS:")
    print(f"   Всего voiceprint jobs: {jobs_analysis['total_jobs']}")
    print(f"   Успешных: {jobs_analysis['successful_jobs']}")
    print(f"   Неудачных: {jobs_analysis['failed_jobs']}")
    print(f"   В обработке: {jobs_analysis['pending_jobs']}")
    
    # Распределение по статусам
    if jobs_analysis['status_distribution']:
        print(f"\n📈 РАСПРЕДЕЛЕНИЕ ПО СТАТУСАМ:")
        for status, count in jobs_analysis['status_distribution'].items():
            percentage = (count / jobs_analysis['total_jobs']) * 100 if jobs_analysis['total_jobs'] > 0 else 0
            print(f"   {status}: {count} ({percentage:.1f}%)")
    
    # Созданные voiceprints
    print(f"\n🎯 СОЗДАННЫЕ VOICEPRINTS:")
    if jobs_analysis['voiceprints_created']:
        print(f"   Количество: {len(jobs_analysis['voiceprints_created'])}")
        for i, vp in enumerate(jobs_analysis['voiceprints_created'][:5]):  # Показываем первые 5
            job_id = vp.get('job_id', 'unknown') or 'unknown'
            job_id_short = job_id[:8] + "..." if job_id and len(job_id) > 8 else job_id
            size = vp.get('voiceprint_size', 0)
            created = vp.get('created_at', 'unknown') or 'unknown'
            print(f"   {i+1}. Job: {job_id_short} | Размер: {size} символов | Создан: {created}")
        if len(jobs_analysis['voiceprints_created']) > 5:
            print(f"   ... и еще {len(jobs_analysis['voiceprints_created']) - 5}")
    else:
        print("   Нет созданных voiceprints")
    
    # Сравнение с локальной базой
    print(f"\n🔄 СРАВНЕНИЕ С ЛОКАЛЬНОЙ БАЗОЙ:")
    print(f"   Локальных voiceprints: {comparison['local_count']}")
    print(f"   Удаленных успешных: {comparison['remote_successful_count']}")
    print(f"   Статус синхронизации: {comparison['sync_status']}")
    
    if comparison['recommendations']:
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        for rec in comparison['recommendations']:
            print(f"   • {rec}")
    
    # Недавняя активность
    if jobs_analysis['recent_activity']:
        print(f"\n📅 НЕДАВНЯЯ АКТИВНОСТЬ (последние 5):")
        for activity in jobs_analysis['recent_activity'][:5]:
            print(f"   {activity['created_at']} | {activity['status']} | Job: {activity['job_id'][:8]}...")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Проверка образцов голосов на сервере pyannote.ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python check_remote_voiceprints.py                    # Базовая проверка
  python check_remote_voiceprints.py --jobs-limit 100   # Проверить больше jobs
  python check_remote_voiceprints.py --export report.json  # Экспорт в JSON
  python check_remote_voiceprints.py --verbose          # Подробное логирование
        """
    )
    
    parser.add_argument(
        "--jobs-limit",
        type=int,
        default=50,
        help="Максимальное количество jobs для проверки (по умолчанию: 50)"
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
        logger.info("🚀 Запуск проверки удаленных образцов голосов в pyannote.ai")
        
        # Получаем API ключ
        try:
            config = get_config()
            api_key = config.get_api_key("pyannote")
        except Exception as e:
            logger.error(f"❌ Ошибка получения API ключа pyannote: {e}")
            logger.info("💡 Убедитесь, что переменная PYANNOTE_API_KEY установлена")
            return 1
        
        # Инициализируем checker и локальный менеджер
        checker = PyannoteAPIChecker(api_key)
        local_manager = VoiceprintManager()
        
        # Проверяем API ключ
        api_result = checker.validate_api_key()
        if not api_result["is_valid"]:
            logger.error(f"❌ Невозможно продолжить: {api_result['error']}")
            return 1
        
        # Получаем voiceprint jobs
        voiceprint_jobs = checker.get_voiceprint_jobs(args.jobs_limit)
        
        # Анализируем jobs
        jobs_analysis = checker.analyze_voiceprint_jobs(voiceprint_jobs)
        
        # Сравниваем с локальной базой
        comparison = compare_with_local_database(jobs_analysis, local_manager)
        
        # Выводим отчет
        print_analysis_report(api_result, jobs_analysis, comparison)
        
        # Экспорт если требуется
        if args.export:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "api_status": api_result,
                "jobs_analysis": jobs_analysis,
                "local_comparison": comparison
            }
            
            with open(args.export, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 Отчет экспортирован в: {args.export}")
        
        logger.info("✅ Проверка завершена успешно")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении проверки: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
