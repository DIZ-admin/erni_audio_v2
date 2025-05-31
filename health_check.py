#!/usr/bin/env python3
# health_check.py

"""
Health check скрипт для проверки состояния Speech Pipeline системы.

Использование:
    python health_check.py                    # Базовая проверка
    python health_check.py --detailed         # Детальная проверка
    python health_check.py --json             # JSON вывод
    python health_check.py --save-report      # Сохранить отчет
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Добавляем текущую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent))

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv не обязателен

try:
    from pipeline.monitoring import PERFORMANCE_MONITOR
    from pipeline.security_validator import SECURITY_VALIDATOR
    from pipeline.rate_limiter import PYANNOTE_RATE_LIMITER, OPENAI_RATE_LIMITER
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    print("Убедитесь, что все зависимости установлены: pip install -r requirements.txt")
    sys.exit(1)


class HealthChecker:
    """Класс для проведения комплексной проверки здоровья системы"""
    
    def __init__(self):
        self.checks = []
        self.warnings = []
        self.errors = []
    
    def check_environment_variables(self) -> Dict[str, Any]:
        """Проверка переменных окружения"""
        result = {
            "name": "Environment Variables",
            "status": "pass",
            "details": {}
        }
        
        required_vars = ["PYANNOTEAI_API_TOKEN", "PYANNOTE_API_KEY", "OPENAI_API_KEY"]
        missing_vars = []
        
        for var in required_vars:
            if os.getenv(var):
                result["details"][var] = "✅ Установлена"
            else:
                missing_vars.append(var)
                result["details"][var] = "❌ Отсутствует"
        
        if missing_vars:
            # Проверяем наличие хотя бы одного ключа Pyannote
            pyannote_key_exists = any(os.getenv(v) and os.getenv(v) != "your_pyannote_api_token_here"
                                    for v in ["PYANNOTEAI_API_TOKEN", "PYANNOTE_API_KEY"])

            if not pyannote_key_exists:
                result["status"] = "warning"
                self.warnings.append("API ключ Pyannote не настроен. Скопируйте .env.example в .env и добавьте ваши ключи.")

            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key or openai_key == "your_openai_api_key_here":
                result["status"] = "warning"
                self.warnings.append("API ключ OpenAI не настроен. Скопируйте .env.example в .env и добавьте ваши ключи.")
        
        return result
    
    def check_directories(self) -> Dict[str, Any]:
        """Проверка необходимых директорий"""
        result = {
            "name": "Required Directories",
            "status": "pass",
            "details": {}
        }
        
        required_dirs = [
            "data/raw",
            "data/interim", 
            "data/processed",
            "voiceprints",
            "logs",
            "logs/metrics"
        ]
        
        for dir_path in required_dirs:
            path = Path(dir_path)
            if path.exists():
                result["details"][dir_path] = "✅ Существует"
            else:
                result["details"][dir_path] = "⚠️ Отсутствует (будет создана)"
                self.warnings.append(f"Директория {dir_path} будет создана автоматически")
        
        return result
    
    def check_dependencies(self) -> Dict[str, Any]:
        """Проверка зависимостей Python"""
        result = {
            "name": "Python Dependencies",
            "status": "pass",
            "details": {}
        }
        
        required_packages = [
            "requests",
            "tenacity", 
            "pydub",
            "openai",
            "pytest",
            "python-dotenv",
            "psutil",
            "python-magic"
        ]
        
        for package in required_packages:
            try:
                # Специальная обработка для некоторых пакетов
                if package == "python-dotenv":
                    import dotenv
                elif package == "python-magic":
                    import magic
                else:
                    __import__(package.replace("-", "_"))
                result["details"][package] = "✅ Установлен"
            except ImportError:
                result["details"][package] = "❌ Отсутствует"
                if package == "python-magic":
                    result["status"] = "warning"
                    self.warnings.append(f"Рекомендуется установить пакет: {package}")
                else:
                    result["status"] = "fail"
                    self.errors.append(f"Отсутствует пакет: {package}")
        
        return result
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Проверка системных ресурсов"""
        result = {
            "name": "System Resources",
            "status": "pass",
            "details": {}
        }
        
        try:
            system_metrics = PERFORMANCE_MONITOR.get_system_metrics()
            
            # CPU
            if system_metrics.cpu_percent < 80:
                result["details"]["CPU"] = f"✅ {system_metrics.cpu_percent:.1f}%"
            else:
                result["details"]["CPU"] = f"⚠️ {system_metrics.cpu_percent:.1f}% (высокая загрузка)"
                result["status"] = "warning"
                self.warnings.append("Высокая загрузка CPU")
            
            # Память
            if system_metrics.memory_percent < 80:
                result["details"]["Memory"] = f"✅ {system_metrics.memory_percent:.1f}% ({system_metrics.memory_used_mb:.0f}MB)"
            else:
                result["details"]["Memory"] = f"⚠️ {system_metrics.memory_percent:.1f}% (высокое использование)"
                result["status"] = "warning"
                self.warnings.append("Высокое использование памяти")
            
            # Диск
            if system_metrics.disk_free_gb > 1:
                result["details"]["Disk"] = f"✅ {system_metrics.disk_free_gb:.1f}GB свободно"
            else:
                result["details"]["Disk"] = f"❌ {system_metrics.disk_free_gb:.1f}GB свободно (критически мало)"
                result["status"] = "fail"
                self.errors.append("Критически мало места на диске")
                
        except Exception as e:
            result["status"] = "fail"
            result["details"]["error"] = f"Ошибка получения метрик: {e}"
            self.errors.append("Не удалось получить системные метрики")
        
        return result
    
    def check_rate_limiters(self) -> Dict[str, Any]:
        """Проверка rate limiters"""
        result = {
            "name": "Rate Limiters",
            "status": "pass",
            "details": {}
        }
        
        try:
            # Pyannote rate limiter
            pyannote_remaining = PYANNOTE_RATE_LIMITER.get_remaining_requests("default")
            result["details"]["Pyannote API"] = f"✅ {pyannote_remaining}/30 запросов доступно"
            
            # OpenAI rate limiter
            openai_remaining = OPENAI_RATE_LIMITER.get_remaining_requests("default")
            result["details"]["OpenAI API"] = f"✅ {openai_remaining}/50 запросов доступно"
        except Exception as e:
            result["status"] = "warning"
            result["details"]["error"] = f"Ошибка проверки rate limiters: {e}"
            self.warnings.append("Не удалось проверить rate limiters")
        
        return result
    
    def check_security_validator(self) -> Dict[str, Any]:
        """Проверка валидатора безопасности"""
        result = {
            "name": "Security Validator",
            "status": "pass",
            "details": {}
        }
        
        try:
            # Проверяем, что валидатор инициализирован
            if hasattr(SECURITY_VALIDATOR, 'magic_available'):
                if SECURITY_VALIDATOR.magic_available:
                    result["details"]["MIME Detection"] = "✅ python-magic доступен"
                else:
                    result["details"]["MIME Detection"] = "⚠️ python-magic недоступен (fallback на mimetypes)"
                    result["status"] = "warning"
                    self.warnings.append("Рекомендуется установить python-magic для лучшей безопасности")
            
            # Тестируем валидацию URL
            is_valid, _ = SECURITY_VALIDATOR.validate_url("https://example.com/test.wav")
            if is_valid:
                result["details"]["URL Validation"] = "✅ Работает"
            else:
                result["details"]["URL Validation"] = "❌ Не работает"
                result["status"] = "fail"
                self.errors.append("Валидация URL не работает")
                
        except Exception as e:
            result["status"] = "fail"
            result["details"]["error"] = f"Ошибка проверки валидатора: {e}"
            self.errors.append("Ошибка валидатора безопасности")
        
        return result
    
    def run_all_checks(self, detailed: bool = False) -> Dict[str, Any]:
        """Запуск всех проверок"""
        checks = [
            self.check_environment_variables(),
            self.check_directories(),
            self.check_dependencies(),
            self.check_system_resources(),
            self.check_rate_limiters(),
            self.check_security_validator()
        ]
        
        # Определяем общий статус
        overall_status = "healthy"
        if self.errors:
            overall_status = "critical"
        elif self.warnings:
            overall_status = "warning"
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "summary": {
                "total_checks": len(checks),
                "passed": len([c for c in checks if c["status"] == "pass"]),
                "warnings": len(self.warnings),
                "errors": len(self.errors)
            },
            "checks": checks if detailed else [{"name": c["name"], "status": c["status"]} for c in checks],
            "warnings": self.warnings,
            "errors": self.errors
        }
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Health check для Speech Pipeline")
    parser.add_argument("--detailed", action="store_true", help="Детальная проверка")
    parser.add_argument("--json", action="store_true", help="JSON вывод")
    parser.add_argument("--save-report", action="store_true", help="Сохранить отчет в файл")
    
    args = parser.parse_args()
    
    checker = HealthChecker()
    result = checker.run_all_checks(detailed=args.detailed)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Человекочитаемый вывод
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️", 
            "critical": "❌"
        }
        
        print(f"\n🏥 Speech Pipeline Health Check")
        print(f"📅 {result['timestamp']}")
        print(f"🎯 Общий статус: {status_emoji[result['overall_status']]} {result['overall_status'].upper()}")
        print(f"📊 Проверок: {result['summary']['passed']}/{result['summary']['total_checks']} прошли")
        
        if result['warnings']:
            print(f"\n⚠️ Предупреждения ({len(result['warnings'])}):")
            for warning in result['warnings']:
                print(f"  • {warning}")
        
        if result['errors']:
            print(f"\n❌ Ошибки ({len(result['errors'])}):")
            for error in result['errors']:
                print(f"  • {error}")
        
        if args.detailed:
            print(f"\n📋 Детальные результаты:")
            for check in result['checks']:
                status_icon = "✅" if check['status'] == 'pass' else "⚠️" if check['status'] == 'warning' else "❌"
                print(f"\n{status_icon} {check['name']}")
                for key, value in check['details'].items():
                    print(f"  {key}: {value}")
    
    if args.save_report:
        report_file = Path("logs") / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Отчет сохранен: {report_file}")
    
    # Возвращаем соответствующий exit code
    if result['overall_status'] == 'critical':
        sys.exit(1)
    elif result['overall_status'] == 'warning':
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
