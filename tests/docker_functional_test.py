#!/usr/bin/env python3
"""
Расширенный функциональный тест Docker контейнера Erni Audio v2

Тестирует реальную функциональность pipeline с использованием тестовых файлов
и mock API ключей для безопасного тестирования.

Использование:
    python docker_functional_test.py                    # Полный функциональный тест
    python docker_functional_test.py --quick            # Быстрый тест
    python docker_functional_test.py --no-cleanup       # Не удалять контейнеры
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/docker_functional_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class DockerFunctionalTester:
    """Класс для функционального тестирования Docker контейнера"""
    
    def __init__(self, cleanup: bool = True):
        self.cleanup = cleanup
        self.container_name = "erni-audio-functional-test"
        self.image_name = "erni-audio-v2:latest"
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_status": "unknown",
            "errors": [],
            "warnings": []
        }
        
        # Создаём директории для логов
        Path("logs").mkdir(exist_ok=True)
        Path("logs/functional_tests").mkdir(exist_ok=True)
    
    def run_command(self, cmd: List[str], timeout: int = 60, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Выполняет команду с логированием"""
        logger.debug(f"Выполняю команду: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, 
                timeout=timeout, 
                capture_output=capture_output,
                text=True,
                check=False
            )
            if result.returncode != 0:
                logger.error(f"Команда завершилась с ошибкой {result.returncode}: {result.stderr}")
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Команда превысила таймаут {timeout}с")
            raise
    
    def setup_test_environment(self) -> bool:
        """Настраивает тестовое окружение"""
        logger.info("🔧 Настройка тестового окружения...")
        
        # Создаём тестовый .env файл с mock данными
        import uuid
        test_env_content = f"""
# Тестовые переменные окружения (MOCK данные - генерируются динамически)
PYANNOTEAI_API_TOKEN=test_pyannote_{uuid.uuid4().hex[:16]}
PYANNOTE_API_KEY=test_pyannote_{uuid.uuid4().hex[:16]}
OPENAI_API_KEY=test_openai_{uuid.uuid4().hex[:16]}
REPLICATE_API_TOKEN=test_replicate_{uuid.uuid4().hex[:16]}
PYANNOTEAI_WEBHOOK_SECRET=test_webhook_{uuid.uuid4().hex[:16]}

# Конфигурация для тестирования
LOG_LEVEL=DEBUG
MAX_FILE_SIZE_MB=50
MAX_CONCURRENT_JOBS=1
ENABLE_HEALTH_CHECKS=true
ENABLE_PERFORMANCE_METRICS=true
STRICT_MIME_VALIDATION=false
REQUIRE_HTTPS_URLS=false
ENABLE_RATE_LIMITING=false

# Webhook настройки
WEBHOOK_SERVER_PORT=8000
WEBHOOK_SERVER_HOST=0.0.0.0
"""
        
        with open(".env.functional_test", "w") as f:
            f.write(test_env_content)
        
        # Проверяем наличие тестовых файлов
        test_files = [
            "tests/samples/Testdatei.m4a",
            "tests/samples/sample_audio.wav"
        ]
        
        available_files = []
        for test_file in test_files:
            if Path(test_file).exists():
                available_files.append(test_file)
                logger.info(f"✅ Найден тестовый файл: {test_file}")
            else:
                logger.warning(f"⚠️ Тестовый файл не найден: {test_file}")
        
        if not available_files:
            logger.error("❌ Не найдено ни одного тестового файла")
            return False
        
        self.test_files = available_files
        logger.info(f"✅ Настройка завершена. Доступно {len(available_files)} тестовых файлов")
        return True
    
    def start_container(self) -> bool:
        """Запускает контейнер для функционального тестирования"""
        logger.info("🚀 Запуск контейнера для функционального тестирования...")
        
        # Останавливаем существующий контейнер если есть
        self.run_command(["docker", "stop", self.container_name])
        self.run_command(["docker", "rm", self.container_name])
        
        # Запускаем контейнер
        cmd = [
            "docker", "run", "-d",
            "--name", self.container_name,
            "--env-file", ".env.functional_test",
            "-p", "8000:8000",
            "-v", f"{Path.cwd()}/data:/app/data",
            "-v", f"{Path.cwd()}/logs:/app/logs",
            "-v", f"{Path.cwd()}/tests:/app/tests",
            "-v", f"{Path.cwd()}/voiceprints:/app/voiceprints",
            "--entrypoint", "sleep",  # Переопределяем entrypoint
            self.image_name,
            "600"  # Запускаем контейнер на 10 минут
        ]
        
        result = self.run_command(cmd)
        
        if result.returncode == 0:
            logger.info("✅ Контейнер запущен")
            time.sleep(3)  # Даём время на запуск
            return True
        else:
            logger.error(f"❌ Ошибка запуска контейнера: {result.stderr}")
            return False
    
    def test_help_command(self) -> bool:
        """Тестирует help команду"""
        logger.info("📖 Тестирование help команды...")
        
        cmd = ["docker", "exec", self.container_name, "python", "speech_pipeline.py", "--help"]
        result = self.run_command(cmd)
        
        if result.returncode == 0 and "speech_pipeline" in result.stdout:
            logger.info("✅ Help команда работает корректно")
            self.test_results["tests"]["help_command"] = {
                "status": "pass",
                "message": "Help команда работает"
            }
            return True
        else:
            logger.error("❌ Help команда не работает")
            self.test_results["tests"]["help_command"] = {
                "status": "fail",
                "message": "Help команда не работает",
                "error": result.stderr
            }
            return False
    
    def test_health_check(self) -> bool:
        """Тестирует health check"""
        logger.info("🏥 Тестирование health check...")
        
        cmd = ["docker", "exec", self.container_name, "python", "health_check.py", "--json"]
        result = self.run_command(cmd)
        
        if result.returncode == 0:
            try:
                health_data = json.loads(result.stdout)
                status = health_data.get("overall_status", "unknown")
                logger.info(f"✅ Health check статус: {status}")
                
                self.test_results["tests"]["health_check"] = {
                    "status": "pass" if status in ["healthy", "warning"] else "fail",
                    "health_status": status,
                    "details": health_data
                }
                return status in ["healthy", "warning"]
            except json.JSONDecodeError:
                logger.error("❌ Некорректный JSON в health check")
                return False
        else:
            logger.error(f"❌ Health check завершился с ошибкой: {result.stderr}")
            return False
    
    def test_cost_estimation(self) -> bool:
        """Тестирует оценку стоимости"""
        logger.info("💰 Тестирование оценки стоимости...")
        
        if not self.test_files:
            logger.warning("⚠️ Нет тестовых файлов для оценки стоимости")
            return False
        
        test_file = self.test_files[0]
        
        # Копируем тестовый файл в контейнер
        copy_cmd = ["docker", "cp", test_file, f"{self.container_name}:/app/test_audio.m4a"]
        copy_result = self.run_command(copy_cmd)
        
        if copy_result.returncode != 0:
            logger.error("❌ Не удалось скопировать тестовый файл")
            return False
        
        # Тестируем оценку стоимости
        cmd = ["docker", "exec", self.container_name, "python", "speech_pipeline.py", 
               "/app/test_audio.m4a", "--show-cost-estimate"]
        result = self.run_command(cmd, timeout=120)
        
        if result.returncode == 0 and ("Cost estimate" in result.stdout or "Оценка стоимости" in result.stdout):
            logger.info("✅ Оценка стоимости работает")
            self.test_results["tests"]["cost_estimation"] = {
                "status": "pass",
                "message": "Оценка стоимости работает"
            }
            return True
        else:
            logger.warning("⚠️ Оценка стоимости не работает (возможно, нет API ключей)")
            self.test_results["tests"]["cost_estimation"] = {
                "status": "warning",
                "message": "Оценка стоимости не работает (mock API ключи)",
                "output": result.stdout[:500] if result.stdout else "Нет вывода"
            }
            return False
    
    def test_file_validation(self) -> bool:
        """Тестирует валидацию файлов"""
        logger.info("🔍 Тестирование валидации файлов...")
        
        # Тестируем с несуществующим файлом
        cmd = ["docker", "exec", self.container_name, "python", "speech_pipeline.py", 
               "/app/nonexistent.wav"]
        result = self.run_command(cmd)
        
        # Проверяем что команда завершилась с ошибкой и есть сообщение об ошибке
        error_output = result.stderr + result.stdout
        if result.returncode != 0 and ("not found" in error_output.lower() or "не найден" in error_output.lower() or "файл не найден" in error_output.lower()):
            logger.info("✅ Валидация несуществующих файлов работает")

            self.test_results["tests"]["file_validation"] = {
                "status": "pass",
                "message": "Валидация файлов работает корректно"
            }
            return True
        else:
            logger.error("❌ Валидация файлов не работает")
            self.test_results["tests"]["file_validation"] = {
                "status": "fail",
                "message": "Валидация файлов не работает",
                "error": error_output,
                "return_code": result.returncode
            }
            return False
    
    def cleanup_containers(self):
        """Очищает тестовые контейнеры"""
        if not self.cleanup:
            logger.info("🧹 Пропуск очистки (--no-cleanup)")
            return
            
        logger.info("🧹 Очистка функциональных тестовых контейнеров...")
        
        # Останавливаем и удаляем контейнер
        self.run_command(["docker", "stop", self.container_name])
        self.run_command(["docker", "rm", self.container_name])
        
        # Удаляем тестовый .env файл
        if Path(".env.functional_test").exists():
            Path(".env.functional_test").unlink()
        
        logger.info("✅ Очистка завершена")
    
    def run_functional_tests(self, quick: bool = False) -> bool:
        """Запускает функциональные тесты"""
        logger.info("🧪 Начало функционального тестирования Docker контейнера")
        
        try:
            # 1. Настройка окружения
            if not self.setup_test_environment():
                return False
            
            # 2. Запуск контейнера
            if not self.start_container():
                return False
            
            # 3. Тестирование help команды
            if not self.test_help_command():
                self.test_results["errors"].append("Help команда не работает")
            
            # 4. Health check
            if not self.test_health_check():
                self.test_results["warnings"].append("Health check не прошёл")
            
            # 5. Валидация файлов
            if not self.test_file_validation():
                self.test_results["errors"].append("Валидация файлов не работает")
            
            # 6. Оценка стоимости (только для полного теста)
            if not quick:
                if not self.test_cost_estimation():
                    self.test_results["warnings"].append("Оценка стоимости не работает")
            
            # Определяем общий статус
            if self.test_results["errors"]:
                self.test_results["overall_status"] = "failed"
            elif self.test_results["warnings"]:
                self.test_results["overall_status"] = "warning"
            else:
                self.test_results["overall_status"] = "passed"
            
            return self.test_results["overall_status"] in ["passed", "warning"]
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка функционального тестирования: {e}")
            self.test_results["overall_status"] = "error"
            self.test_results["errors"].append(f"Критическая ошибка: {e}")
            return False
        
        finally:
            self.cleanup_containers()
    
    def save_report(self):
        """Сохраняет отчёт о функциональном тестировании"""
        report_file = Path("logs/functional_tests") / f"functional_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Отчёт сохранён: {report_file}")
        
        # Выводим краткий отчёт
        status_emoji = {
            "passed": "✅",
            "warning": "⚠️",
            "failed": "❌",
            "error": "💥"
        }
        
        print(f"\n🧪 Functional Test Report")
        print(f"📅 {self.test_results['timestamp']}")
        print(f"🎯 Статус: {status_emoji.get(self.test_results['overall_status'], '❓')} {self.test_results['overall_status'].upper()}")
        
        if self.test_results["warnings"]:
            print(f"\n⚠️ Предупреждения:")
            for warning in self.test_results["warnings"]:
                print(f"  • {warning}")
        
        if self.test_results["errors"]:
            print(f"\n❌ Ошибки:")
            for error in self.test_results["errors"]:
                print(f"  • {error}")


def main():
    parser = argparse.ArgumentParser(description="Функциональное тестирование Docker контейнера")
    parser.add_argument("--quick", action="store_true", help="Быстрый тест (без оценки стоимости)")
    parser.add_argument("--no-cleanup", action="store_true", help="Не удалять контейнеры после теста")
    
    args = parser.parse_args()
    
    tester = DockerFunctionalTester(cleanup=not args.no_cleanup)
    
    try:
        success = tester.run_functional_tests(quick=args.quick)
        tester.save_report()
        
        if success:
            logger.info("🎉 Функциональное тестирование завершено успешно!")
            sys.exit(0)
        else:
            logger.error("💥 Функциональное тестирование завершилось с ошибками!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️ Тестирование прервано пользователем")
        tester.cleanup_containers()
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Неожиданная ошибка: {e}")
        tester.cleanup_containers()
        sys.exit(1)


if __name__ == "__main__":
    main()
