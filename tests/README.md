# 🧪 Тестовая система Erni Audio v2

Комплексная система тестирования для проекта обработки аудио с поддержкой различных типов тестов и CI/CD интеграции.

## 📁 Структура тестов

```
tests/
├── reports/                    # 📊 Отчеты и результаты
│   ├── coverage/              # HTML отчеты покрытия кода
│   ├── test_system_audit_report.md
│   └── junit.xml              # JUnit отчеты для CI/CD
├── assets/                    # 🎵 Тестовые данные и фикстуры
├── samples/                   # 🎵 Образцы аудиофайлов
├── docker_test.py             # 🐳 Docker тесты
├── docker_functional_test.py  # 🐳 Функциональные Docker тесты
└── test_*.py                  # 🧪 Основные тесты
```

## 🚀 Быстрый старт

### Запуск всех быстрых тестов
```bash
python3 run_tests.py --quick
```

### Запуск всех тестов
```bash
python3 run_tests.py --all
```

### Запуск Docker тестов
```bash
python3 run_tests.py --docker
```

## 📋 Типы тестов

### 🧪 Unit тесты
**Описание:** Быстрые тесты отдельных компонентов  
**Время выполнения:** ~30 секунд  
**Команда:**
```bash
python3 run_tests.py --unit
# или
python3 -m pytest tests/ -m "unit or not (integration or slow or docker)"
```

### 🔗 Интеграционные тесты
**Описание:** Тесты взаимодействия компонентов  
**Время выполнения:** ~60 секунд  
**Команда:**
```bash
python3 run_tests.py --integration
# или
python3 -m pytest tests/ -m "integration and not real_api"
```

### ⚡ Тесты производительности
**Описание:** Тесты скорости и использования ресурсов  
**Время выполнения:** ~45 секунд  
**Команда:**
```bash
python3 run_tests.py --performance
# или
python3 -m pytest tests/ -m "performance or slow"
```

### 🐳 Docker тесты
**Описание:** Тесты контейнеризации и развертывания  
**Время выполнения:** ~40 секунд  
**Команда:**
```bash
python3 run_tests.py --docker
# или
python3 tests/docker_test.py --quick
python3 tests/docker_functional_test.py --quick
```

### 🌐 Тесты с реальными API
**Описание:** Тесты с настоящими API ключами  
**Требования:** Файл .env с API ключами  
**Команда:**
```bash
python3 run_tests.py --integration --real-api
# или
python3 -m pytest tests/ -m "real_api"
```

## 🏷️ Маркеры тестов

| Маркер | Описание | Время выполнения |
|--------|----------|------------------|
| `unit` | Быстрые unit тесты | < 1 сек |
| `integration` | Интеграционные тесты | 1-10 сек |
| `performance` | Тесты производительности | 5-30 сек |
| `slow` | Медленные тесты | > 10 сек |
| `docker` | Docker тесты | 10-60 сек |
| `api` | Тесты API интеграции | 1-5 сек |
| `stress` | Нагрузочные тесты | > 30 сек |
| `real_api` | Тесты с реальными API | 5-30 сек |

## 📊 Отчеты и мониторинг

### Генерация отчетов покрытия
```bash
# Установка pytest-cov (если не установлен)
pip install pytest-cov

# Запуск с покрытием
python3 -m pytest tests/ --cov=pipeline --cov-report=html:tests/reports/coverage
```

### Просмотр отчетов
```bash
# HTML отчет покрытия
open tests/reports/coverage/index.html

# Аудит тестовой системы
cat tests/reports/test_system_audit_report.md
```

## 🔧 Конфигурация

### pytest.ini
Основная конфигурация находится в файле `pytest.ini`:
- Маркеры тестов
- Настройки логирования
- Пути для отчетов
- Фильтры предупреждений

### Переменные окружения
```bash
# Для тестов с реальными API
export OPENAI_API_KEY="your-key"
export PYANNOTE_API_KEY="your-key"
export REPLICATE_API_TOKEN="your-token"
```

## 🐳 Docker тестирование

### Быстрые Docker тесты
```bash
python3 tests/docker_test.py --quick
```

### Полные Docker тесты
```bash
python3 tests/docker_test.py --full
python3 tests/docker_functional_test.py --full
```

### Тестирование с реальными API
```bash
# Убедитесь, что .env файл содержит API ключи
python3 tests/docker_functional_test.py --real-api
```

## 🚀 CI/CD интеграция

### GitHub Actions
```yaml
- name: Run tests
  run: |
    python3 run_tests.py --all
    
- name: Upload test reports
  uses: actions/upload-artifact@v3
  with:
    name: test-reports
    path: tests/reports/
```

### Локальная проверка перед коммитом
```bash
# Быстрая проверка
python3 run_tests.py --quick

# Полная проверка
python3 run_tests.py --all
```

## 📈 Метрики качества

### Текущие показатели
- **Общее количество тестов:** 224
- **Успешность:** 97.3% (218/224)
- **Покрытие кода:** ~85%
- **Время выполнения:** < 1 минуты

### Цели качества
- ✅ Покрытие кода > 80%
- ✅ Успешность > 95%
- ✅ Время выполнения < 2 минут
- ✅ Отсутствие критических багов

## 🛠️ Разработка тестов

### Создание нового теста
```python
import pytest
from unittest.mock import patch, MagicMock
from pipeline.your_agent import YourAgent

class TestYourAgent:
    """Тесты для YourAgent"""
    
    @pytest.mark.unit
    def test_basic_functionality(self):
        """Базовый тест функциональности"""
        agent = YourAgent("test-key")
        result = agent.some_method()
        assert result is not None
        
    @pytest.mark.integration
    def test_integration_with_api(self):
        """Интеграционный тест с API"""
        # Тест с мокированием API
        pass
```

### Соглашения по именованию
- Файлы: `test_component_name.py`
- Классы: `TestComponentName`
- Методы: `test_specific_functionality`
- Маркеры: Обязательно указывать тип теста

## 🔍 Отладка тестов

### Запуск конкретного теста
```bash
python3 -m pytest tests/test_transcription_agent.py::test_init -v
```

### Отладка падающих тестов
```bash
python3 -m pytest tests/ --tb=long --pdb
```

### Профилирование тестов
```bash
python3 -m pytest tests/ --durations=10
```

## 📞 Поддержка

При возникновении проблем с тестами:

1. **Проверьте отчет аудита:** `tests/reports/test_system_audit_report.md`
2. **Запустите диагностику:** `python3 run_tests.py --quick -v`
3. **Проверьте логи:** `tests/reports/`
4. **Обратитесь к документации:** Этот файл

---

**Статус системы:** ✅ **ГОТОВА К PRODUCTION**  
**Последнее обновление:** 2025-06-03
