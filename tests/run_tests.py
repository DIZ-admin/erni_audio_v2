#!/usr/bin/env python3
"""
Скрипт для запуска тестов Erni Audio v2 с различными конфигурациями
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description=""):
    """Запуск команды с логированием"""
    print(f"\n🚀 {description}")
    print(f"Команда: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"⏱️  Время выполнения: {end_time - start_time:.2f} секунд")
    
    if result.returncode == 0:
        print("✅ Успешно")
    else:
        print("❌ Ошибка")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
    
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Запуск тестов Erni Audio v2")
    parser.add_argument("--unit", action="store_true", help="Запустить только unit тесты")
    parser.add_argument("--integration", action="store_true", help="Запустить интеграционные тесты")
    parser.add_argument("--performance", action="store_true", help="Запустить тесты производительности")
    parser.add_argument("--docker", action="store_true", help="Запустить Docker тесты")
    parser.add_argument("--all", action="store_true", help="Запустить все тесты")
    parser.add_argument("--quick", action="store_true", help="Быстрые тесты (без slow)")
    parser.add_argument("--real-api", action="store_true", help="Тесты с реальными API ключами")
    parser.add_argument("--coverage", action="store_true", help="Генерировать отчет покрытия")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    
    args = parser.parse_args()
    
    # Создаем директорию для отчетов
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True)
    
    base_cmd = ["python3", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.append("-v")
    
    # Определяем какие тесты запускать
    if args.unit:
        cmd = base_cmd + ["tests/", "-m", "unit or not (integration or slow or docker)"]
        run_command(cmd, "Запуск unit тестов")
        
    elif args.integration:
        if args.real_api:
            cmd = base_cmd + ["tests/", "-m", "integration or real_api"]
        else:
            cmd = base_cmd + ["tests/", "-m", "integration and not real_api"]
        run_command(cmd, "Запуск интеграционных тестов")
        
    elif args.performance:
        cmd = base_cmd + ["tests/", "-m", "performance or slow"]
        run_command(cmd, "Запуск тестов производительности")
        
    elif args.docker:
        # Запуск Docker тестов
        docker_success = True
        
        # Основные Docker тесты
        cmd = ["python3", "tests/docker_test.py", "--quick"]
        if not run_command(cmd, "Запуск основных Docker тестов"):
            docker_success = False
            
        # Функциональные Docker тесты
        cmd = ["python3", "tests/docker_functional_test.py", "--quick"]
        if not run_command(cmd, "Запуск функциональных Docker тестов"):
            docker_success = False
            
        if docker_success:
            print("\n✅ Все Docker тесты прошли успешно!")
        else:
            print("\n❌ Некоторые Docker тесты упали")
            
    elif args.quick:
        cmd = base_cmd + ["tests/", "-m", "not slow and not integration and not docker"]
        run_command(cmd, "Запуск быстрых тестов")
        
    elif args.all:
        # Запуск всех тестов по группам
        success_count = 0
        total_count = 0
        
        # Unit тесты
        total_count += 1
        cmd = base_cmd + ["tests/", "-m", "not slow and not integration and not docker"]
        if run_command(cmd, "Запуск unit тестов"):
            success_count += 1
            
        # Интеграционные тесты (без реальных API)
        total_count += 1
        cmd = base_cmd + ["tests/", "-m", "integration and not real_api"]
        if run_command(cmd, "Запуск интеграционных тестов"):
            success_count += 1
            
        # Тесты производительности
        total_count += 1
        cmd = base_cmd + ["tests/", "-m", "performance"]
        if run_command(cmd, "Запуск тестов производительности"):
            success_count += 1
            
        # Docker тесты
        total_count += 1
        cmd = ["python3", "tests/docker_test.py", "--quick"]
        if run_command(cmd, "Запуск Docker тестов"):
            success_count += 1
            
        print(f"\n📊 Итоговый результат: {success_count}/{total_count} групп тестов прошли успешно")
        
        if success_count == total_count:
            print("🎉 Все тесты прошли успешно!")
            return 0
        else:
            print("⚠️  Некоторые тесты упали")
            return 1
            
    else:
        # По умолчанию запускаем быстрые тесты
        cmd = base_cmd + ["tests/", "-m", "not slow and not integration and not docker"]
        run_command(cmd, "Запуск быстрых тестов (по умолчанию)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
