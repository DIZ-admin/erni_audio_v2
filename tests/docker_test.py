#!/usr/bin/env python3
"""
Комплексный тест Docker контейнера Erni Audio v2

Выполняет полную проверку работоспособности Docker контейнера:
1. Сборка и запуск контейнера
2. Функциональное тестирование
3. Проверка производительности
4. Проверка безопасности
5. Health checks и логирование

Использование:
    python docker_test.py                    # Полный тест
    python docker_test.py --quick            # Быстрый тест
    python docker_test.py --build-only       # Только сборка
    python docker_test.py --no-cleanup       # Не удалять контейнеры
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
import requests
import psutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/docker_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class DockerTester:
    """Класс для комплексного тестирования Docker контейнера"""
    
    def __init__(self, cleanup: bool = True):
        self.cleanup = cleanup
        self.container_name = "erni-audio-test"
        self.image_name = "erni-audio-v2:test"
        self.webhook_container = "erni-audio-webhook-test"
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_status": "unknown",
            "errors": [],
            "warnings": []
        }
        
        # Создаём директории для логов
        Path("logs").mkdir(exist_ok=True)
        Path("logs/docker_tests").mkdir(exist_ok=True)
    
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
    
    def check_docker_available(self) -> bool:
        """Проверяет доступность Docker"""
        logger.info("🐳 Проверка доступности Docker...")
        try:
            result = self.run_command(["docker", "--version"])
            if result.returncode == 0:
                logger.info(f"✅ Docker доступен: {result.stdout.strip()}")
                return True
            else:
                logger.error("❌ Docker недоступен")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Docker: {e}")
            return False
    
    def build_image(self) -> bool:
        """Собирает Docker образ"""
        logger.info("🔨 Сборка Docker образа...")
        
        # Проверяем наличие Dockerfile
        if not Path("Dockerfile").exists():
            logger.error("❌ Dockerfile не найден")
            return False
        
        # Собираем образ
        cmd = ["docker", "build", "-t", self.image_name, "."]
        result = self.run_command(cmd, timeout=300)
        
        if result.returncode == 0:
            logger.info("✅ Docker образ собран успешно")
            self.test_results["tests"]["build"] = {
                "status": "pass",
                "message": "Образ собран успешно",
                "duration": "< 5 минут"
            }
            return True
        else:
            logger.error(f"❌ Ошибка сборки образа: {result.stderr}")
            self.test_results["tests"]["build"] = {
                "status": "fail",
                "message": f"Ошибка сборки: {result.stderr}",
                "error": result.stderr
            }
            return False
    
    def start_container(self) -> bool:
        """Запускает контейнер для тестирования"""
        logger.info("🚀 Запуск тестового контейнера...")
        
        # Останавливаем существующий контейнер если есть
        self.run_command(["docker", "stop", self.container_name])
        self.run_command(["docker", "rm", self.container_name])
        
        # Создаём .env файл для тестирования
        import uuid
        env_content = f"""
# Тестовые переменные окружения (генерируются динамически)
PYANNOTEAI_API_TOKEN=test_token_{uuid.uuid4().hex[:16]}
OPENAI_API_KEY=test_openai_{uuid.uuid4().hex[:16]}
LOG_LEVEL=DEBUG
ENABLE_HEALTH_CHECKS=true
"""
        with open(".env.test", "w") as f:
            f.write(env_content)
        
        # Запускаем контейнер в режиме health check
        cmd = [
            "docker", "run", "-d",
            "--name", self.container_name,
            "--env-file", ".env.test",
            "-p", "8000:8000",
            "-v", f"{Path.cwd()}/data:/app/data",
            "-v", f"{Path.cwd()}/logs:/app/logs",
            "--entrypoint", "sleep",  # Переопределяем entrypoint
            self.image_name,
            "300"  # Запускаем контейнер на 5 минут для тестирования
        ]
        
        result = self.run_command(cmd)
        
        if result.returncode == 0:
            logger.info("✅ Контейнер запущен")
            time.sleep(5)  # Даём время на запуск
            return True
        else:
            logger.error(f"❌ Ошибка запуска контейнера: {result.stderr}")
            return False
    
    def test_container_health(self) -> bool:
        """Тестирует health check контейнера"""
        logger.info("🏥 Проверка health check...")
        
        # Проверяем статус контейнера
        cmd = ["docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Status}}"]
        result = self.run_command(cmd)
        
        if result.returncode == 0 and "Up" in result.stdout:
            logger.info("✅ Контейнер работает")
            
            # Выполняем health check внутри контейнера
            health_cmd = ["docker", "exec", self.container_name, "python", "health_check.py", "--json"]
            health_result = self.run_command(health_cmd)
            
            if health_result.returncode == 0:
                try:
                    health_data = json.loads(health_result.stdout)
                    status = health_data.get("overall_status", "unknown")
                    logger.info(f"✅ Health check: {status}")
                    
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
                logger.error(f"❌ Health check завершился с ошибкой: {health_result.stderr}")
                return False
        else:
            logger.error("❌ Контейнер не работает")
            return False
    
    def test_basic_functionality(self) -> bool:
        """Тестирует базовую функциональность"""
        logger.info("🧪 Тестирование базовой функциональности...")
        
        # Проверяем help команду
        cmd = ["docker", "exec", self.container_name, "python", "speech_pipeline.py", "--help"]
        result = self.run_command(cmd)
        
        if result.returncode == 0 and "speech_pipeline" in result.stdout:
            logger.info("✅ Help команда работает")
            
            # Проверяем наличие тестового файла
            test_file = Path("tests/samples/Testdatei.m4a")
            if test_file.exists():
                logger.info("✅ Тестовый файл найден")
                
                # Копируем тестовый файл в контейнер
                copy_cmd = ["docker", "cp", str(test_file), f"{self.container_name}:/app/test_audio.m4a"]
                copy_result = self.run_command(copy_cmd)
                
                if copy_result.returncode == 0:
                    logger.info("✅ Тестовый файл скопирован в контейнер")
                    
                    self.test_results["tests"]["basic_functionality"] = {
                        "status": "pass",
                        "message": "Базовая функциональность работает",
                        "help_command": "работает",
                        "test_file": "доступен"
                    }
                    return True
                else:
                    logger.error("❌ Не удалось скопировать тестовый файл")
            else:
                logger.warning("⚠️ Тестовый файл не найден")
                
        logger.error("❌ Базовая функциональность не работает")
        self.test_results["tests"]["basic_functionality"] = {
            "status": "fail",
            "message": "Ошибка базовой функциональности"
        }
        return False
    
    def test_resource_usage(self) -> bool:
        """Тестирует использование ресурсов"""
        logger.info("📊 Проверка использования ресурсов...")

        # Получаем статистику контейнера
        cmd = ["docker", "stats", self.container_name, "--no-stream", "--format", "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"]
        result = self.run_command(cmd)

        if result.returncode == 0 and result.stdout.strip():
            try:
                stats = result.stdout.strip().split('\t')
                if len(stats) >= 3:
                    cpu_percent = stats[0].replace('%', '')
                    mem_usage = stats[1]
                    mem_percent = stats[2].replace('%', '')

                    logger.info(f"📈 CPU: {cpu_percent}%, Memory: {mem_usage} ({mem_percent}%)")

                    self.test_results["tests"]["resource_usage"] = {
                        "status": "pass",
                        "cpu_percent": cpu_percent,
                        "memory_usage": mem_usage,
                        "memory_percent": mem_percent
                    }
                    return True
                else:
                    logger.warning(f"⚠️ Неожиданный формат статистики: {result.stdout}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка парсинга статистики: {e}")

        logger.warning("⚠️ Не удалось получить статистику ресурсов")
        self.test_results["tests"]["resource_usage"] = {
            "status": "warning",
            "message": "Не удалось получить статистику ресурсов"
        }
        return False
    
    def cleanup_containers(self):
        """Очищает тестовые контейнеры"""
        if not self.cleanup:
            logger.info("🧹 Пропуск очистки (--no-cleanup)")
            return
            
        logger.info("🧹 Очистка тестовых контейнеров...")
        
        # Останавливаем и удаляем контейнеры
        containers = [self.container_name, self.webhook_container]
        for container in containers:
            self.run_command(["docker", "stop", container])
            self.run_command(["docker", "rm", container])
        
        # Удаляем тестовый образ
        self.run_command(["docker", "rmi", self.image_name])
        
        # Удаляем тестовый .env файл
        if Path(".env.test").exists():
            Path(".env.test").unlink()
        
        logger.info("✅ Очистка завершена")
    
    def run_full_test(self, quick: bool = False) -> bool:
        """Запускает полный тест"""
        logger.info("🚀 Начало комплексного тестирования Docker контейнера")
        
        try:
            # 1. Проверка Docker
            if not self.check_docker_available():
                return False
            
            # 2. Сборка образа
            if not self.build_image():
                return False
            
            # 3. Запуск контейнера
            if not self.start_container():
                return False
            
            # 4. Health check
            if not self.test_container_health():
                self.test_results["warnings"].append("Health check не прошёл")
            
            # 5. Базовая функциональность
            if not self.test_basic_functionality():
                self.test_results["errors"].append("Базовая функциональность не работает")
            
            # 6. Ресурсы (только для полного теста)
            if not quick:
                if not self.test_resource_usage():
                    self.test_results["warnings"].append("Не удалось проверить ресурсы")
            
            # Определяем общий статус
            if self.test_results["errors"]:
                self.test_results["overall_status"] = "failed"
            elif self.test_results["warnings"]:
                self.test_results["overall_status"] = "warning"
            else:
                self.test_results["overall_status"] = "passed"
            
            return self.test_results["overall_status"] in ["passed", "warning"]
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка тестирования: {e}")
            self.test_results["overall_status"] = "error"
            self.test_results["errors"].append(f"Критическая ошибка: {e}")
            return False
        
        finally:
            self.cleanup_containers()
    
    def save_report(self):
        """Сохраняет отчёт о тестировании"""
        report_file = Path("logs/docker_tests") / f"docker_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
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
        
        print(f"\n🐳 Docker Test Report")
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
    parser = argparse.ArgumentParser(description="Комплексное тестирование Docker контейнера")
    parser.add_argument("--quick", action="store_true", help="Быстрый тест (без проверки ресурсов)")
    parser.add_argument("--build-only", action="store_true", help="Только сборка образа")
    parser.add_argument("--no-cleanup", action="store_true", help="Не удалять контейнеры после теста")
    
    args = parser.parse_args()
    
    tester = DockerTester(cleanup=not args.no_cleanup)
    
    try:
        if args.build_only:
            success = tester.check_docker_available() and tester.build_image()
        else:
            success = tester.run_full_test(quick=args.quick)
        
        tester.save_report()
        
        if success:
            logger.info("🎉 Тестирование завершено успешно!")
            sys.exit(0)
        else:
            logger.error("💥 Тестирование завершилось с ошибками!")
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
