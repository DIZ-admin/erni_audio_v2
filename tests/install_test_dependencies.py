#!/usr/bin/env python3
"""
Скрипт для установки зависимостей тестирования Erni Audio v2
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description=""):
    """Запуск команды с логированием"""
    print(f"\n🚀 {description}")
    print(f"Команда: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Успешно")
        if result.stdout.strip():
            print(f"Вывод: {result.stdout.strip()}")
    else:
        print("❌ Ошибка")
        print(f"STDERR: {result.stderr}")
        return False
    
    return True


def main():
    print("🧪 Установка зависимостей для тестирования Erni Audio v2")
    
    # Основные зависимости для тестирования
    test_dependencies = [
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0",
        "pytest-asyncio>=0.21.0",
        "pytest-mock>=3.11.0",
        "pytest-xdist>=3.3.0",  # Для параллельного запуска тестов
        "pytest-html>=3.2.0",   # Для HTML отчетов
        "pytest-json-report>=1.5.0",  # Для JSON отчетов
        "coverage>=7.3.0",
        "mock>=5.1.0"
    ]
    
    # Дополнительные инструменты для анализа
    analysis_tools = [
        "flake8>=6.0.0",        # Линтер
        "black>=23.0.0",        # Форматтер кода
        "isort>=5.12.0",        # Сортировка импортов
        "mypy>=1.5.0",          # Проверка типов
        "bandit>=1.7.0",        # Проверка безопасности
        "safety>=2.3.0"         # Проверка уязвимостей в зависимостях
    ]
    
    success_count = 0
    total_count = 0
    
    # Устанавливаем основные зависимости
    print("\n📦 Установка основных зависимостей для тестирования...")
    for dep in test_dependencies:
        total_count += 1
        if run_command(["pip", "install", dep], f"Установка {dep}"):
            success_count += 1
    
    # Устанавливаем инструменты анализа
    print("\n🔍 Установка инструментов анализа кода...")
    for tool in analysis_tools:
        total_count += 1
        if run_command(["pip", "install", tool], f"Установка {tool}"):
            success_count += 1
    
    # Создаем конфигурационные файлы
    print("\n⚙️ Создание конфигурационных файлов...")
    
    # .coveragerc для настройки покрытия
    coveragerc_content = """[run]
source = pipeline
omit = 
    */tests/*
    */venv/*
    */env/*
    */__pycache__/*
    */migrations/*
    setup.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if self.debug:
    if settings.DEBUG
    raise AssertionError
    raise NotImplementedError
    if 0:
    if __name__ == .__main__.:
    class .*\\bProtocol\\):
    @(abc\\.)?abstractmethod

[html]
directory = tests/reports/coverage
"""
    
    with open(".coveragerc", "w") as f:
        f.write(coveragerc_content)
    print("✅ Создан .coveragerc")
    
    # setup.cfg для flake8 и других инструментов
    setup_cfg_content = """[flake8]
max-line-length = 120
exclude = 
    .git,
    __pycache__,
    venv,
    env,
    .venv,
    .env,
    build,
    dist,
    *.egg-info
ignore = 
    E203,  # whitespace before ':'
    W503,  # line break before binary operator
    E501   # line too long (handled by black)

[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
ignore_missing_imports = True

[isort]
profile = black
multi_line_output = 3
line_length = 120
"""
    
    with open("setup.cfg", "w") as f:
        f.write(setup_cfg_content)
    print("✅ Создан setup.cfg")
    
    # pyproject.toml для black
    pyproject_content = """[tool.black]
line-length = 120
target-version = ['py39']
include = '\\.pyi?$'
extend-exclude = '''
/(
  # directories
  \\.eggs
  | \\.git
  | \\.hg
  | \\.mypy_cache
  | \\.tox
  | \\.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 120
"""
    
    # Проверяем, существует ли pyproject.toml
    if not Path("pyproject.toml").exists():
        with open("pyproject.toml", "w") as f:
            f.write(pyproject_content)
        print("✅ Создан pyproject.toml")
    else:
        print("⚠️ pyproject.toml уже существует, пропускаем")
    
    # Создаем Makefile для удобства
    makefile_content = """# Makefile для тестирования Erni Audio v2

.PHONY: test test-quick test-all test-docker test-coverage lint format check install-deps clean

# Быстрые тесты
test-quick:
	python3 run_tests.py --quick

# Все тесты
test-all:
	python3 run_tests.py --all

# Docker тесты
test-docker:
	python3 run_tests.py --docker

# Тесты с покрытием
test-coverage:
	python3 -m pytest tests/ --cov=pipeline --cov-report=html:tests/reports/coverage --cov-report=term-missing

# Линтинг
lint:
	flake8 pipeline/ tests/
	mypy pipeline/
	bandit -r pipeline/

# Форматирование кода
format:
	black pipeline/ tests/
	isort pipeline/ tests/

# Проверка безопасности
check:
	safety check
	bandit -r pipeline/

# Установка зависимостей
install-deps:
	python3 install_test_dependencies.py

# Очистка
clean:
	rm -rf tests/reports/coverage/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Полная проверка перед коммитом
pre-commit: format lint test-quick
	@echo "✅ Все проверки пройдены!"
"""
    
    with open("Makefile", "w") as f:
        f.write(makefile_content)
    print("✅ Создан Makefile")
    
    # Итоговый отчет
    print(f"\n📊 Итоговый результат: {success_count}/{total_count} пакетов установлено успешно")
    
    if success_count == total_count:
        print("\n🎉 Все зависимости установлены успешно!")
        print("\n📋 Доступные команды:")
        print("  make test-quick     - Быстрые тесты")
        print("  make test-all       - Все тесты")
        print("  make test-docker    - Docker тесты")
        print("  make test-coverage  - Тесты с покрытием")
        print("  make lint           - Проверка кода")
        print("  make format         - Форматирование кода")
        print("  make pre-commit     - Полная проверка")
        print("\n🚀 Система тестирования готова к использованию!")
        return 0
    else:
        print("\n⚠️ Некоторые пакеты не удалось установить")
        print("Попробуйте установить их вручную:")
        print("pip install pytest pytest-cov pytest-asyncio")
        return 1


if __name__ == "__main__":
    sys.exit(main())
