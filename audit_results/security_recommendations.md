# 🔒 Рекомендации по безопасности - Устранение захардкоженных параметров

## 🚨 Критические уязвимости безопасности

### 1. Захардкоженные API ключи в тестах

**Проблема:** Тестовые файлы содержат примеры API ключей, которые могут быть случайно заменены на реальные.

**Найдено в:**
- `tests/docker_functional_test.py` (строки 81-85)
- `tests/docker_test.py` (строки 138-139)  
- `tests/test_webhook_server.py` (строка 21)

**Риск:** ВЫСОКИЙ - возможна утечка реальных API ключей в Git репозиторий

**Решение:**
```python
# ПЛОХО (текущее состояние)
PYANNOTEAI_API_TOKEN=test_pyannote_token_mock

# ХОРОШО (рекомендуемое)
@pytest.fixture
def mock_api_key():
    return f"test_key_{uuid.uuid4().hex[:16]}"
```

---

## 🛡️ Рекомендации по защите секретов

### 2. Автоматическая валидация отсутствия секретов

**Создать pre-commit hook:**
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Проверка на наличие потенциальных API ключей
if grep -r "sk-[a-zA-Z0-9]" . --exclude-dir=.git; then
    echo "❌ Найден потенциальный OpenAI API ключ!"
    exit 1
fi

if grep -r "r8_[a-zA-Z0-9]" . --exclude-dir=.git; then
    echo "❌ Найден потенциальный Replicate API ключ!"
    exit 1
fi

if grep -r "whs_[a-zA-Z0-9]" . --exclude-dir=.git; then
    echo "❌ Найден потенциальный webhook секрет!"
    exit 1
fi

echo "✅ Проверка секретов пройдена"
```

### 3. GitHub Actions для проверки секретов

**Создать .github/workflows/security-check.yml:**
```yaml
name: Security Check
on: [push, pull_request]

jobs:
  check-secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Check for hardcoded secrets
        run: |
          # Проверка API ключей
          if grep -r "sk-[a-zA-Z0-9]" . --exclude-dir=.git; then
            echo "❌ Found potential OpenAI API key!"
            exit 1
          fi
          
          # Проверка тестовых ключей в production коде
          if grep -r "test_.*_key\|test_.*_token" pipeline/; then
            echo "❌ Found test keys in production code!"
            exit 1
          fi
          
          echo "✅ No hardcoded secrets found"
```

---

## 🔐 Безопасное управление конфигурацией

### 4. Иерархия приоритетов конфигурации

**Рекомендуемый порядок (от высшего к низшему):**

1. **Переменные окружения** (самый высокий приоритет)
2. **Файл .env** (для локальной разработки)
3. **Профили конфигурации** (config_profiles/*.yaml)
4. **Значения по умолчанию** (в коде)

```python
# Пример безопасной загрузки конфигурации
def get_api_key(service: str) -> str:
    # 1. Переменные окружения (production)
    key = os.getenv(f"{service.upper()}_API_KEY")
    if key:
        return key
    
    # 2. .env файл (development)
    load_dotenv()
    key = os.getenv(f"{service.upper()}_API_KEY")
    if key:
        return key
    
    # 3. Ошибка если ключ не найден
    raise ValueError(f"API ключ для {service} не найден")
```

### 5. Валидация API ключей

**Добавить проверки формата:**
```python
def validate_api_key(service: str, key: str) -> bool:
    """Валидирует формат API ключа"""
    patterns = {
        "openai": r"^sk-[a-zA-Z0-9]{48}$",
        "replicate": r"^r8_[a-zA-Z0-9]{40}$", 
        "pyannote": r"^[a-zA-Z0-9]{32,}$"
    }
    
    pattern = patterns.get(service.lower())
    if not pattern:
        return True  # Неизвестный сервис - пропускаем
    
    import re
    return bool(re.match(pattern, key))
```

---

## 📋 Чек-лист безопасности

### ✅ Немедленные действия (сегодня)

- [ ] Удалить все захардкоженные API ключи из тестов
- [ ] Добавить .env в .gitignore (если еще не добавлен)
- [ ] Создать .env.example с примерами переменных
- [ ] Настроить pre-commit hook для проверки секретов

### ✅ Краткосрочные действия (эта неделя)

- [ ] Создать GitHub Actions для проверки секретов
- [ ] Добавить валидацию формата API ключей
- [ ] Обновить документацию по безопасности
- [ ] Провести аудит всех конфигурационных файлов

### ✅ Долгосрочные действия (этот месяц)

- [ ] Настроить ротацию API ключей
- [ ] Добавить мониторинг использования API
- [ ] Создать систему алертов при подозрительной активности
- [ ] Документировать процедуры инцидент-реагирования

---

## 🔍 Инструменты для мониторинга

### 6. Автоматическое сканирование секретов

**Установить truffleHog:**
```bash
# Установка
pip install truffleHog

# Сканирование репозитория
trufflehog --regex --entropy=False .

# Сканирование с высокой энтропией
trufflehog --regex --entropy=True --max_depth=50 .
```

**Настроить регулярное сканирование:**
```bash
# Добавить в crontab
0 2 * * * cd /path/to/project && trufflehog --regex . > /var/log/security-scan.log
```

### 7. Мониторинг использования API

**Добавить в код логирование:**
```python
import logging
import hashlib

def log_api_usage(service: str, endpoint: str, api_key: str):
    """Безопасное логирование использования API"""
    # Хэшируем ключ для идентификации без раскрытия
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
    
    logging.info(f"API_USAGE: {service}.{endpoint} key_hash={key_hash}")
```

---

## 🚨 План реагирования на инциденты

### 8. Если API ключ попал в Git

**Немедленные действия:**
1. **Отозвать скомпрометированный ключ** в панели провайдера
2. **Создать новый ключ** и обновить переменные окружения
3. **Удалить ключ из истории Git** (если возможно)
4. **Уведомить команду** о произошедшем инциденте

**Команды для очистки истории:**
```bash
# ВНИМАНИЕ: Это переписывает историю Git!
git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch path/to/file/with/secret' \
--prune-empty --tag-name-filter cat -- --all

# Принудительно обновить remote
git push origin --force --all
git push origin --force --tags
```

### 9. Мониторинг подозрительной активности

**Настроить алерты на:**
- Необычно высокое использование API
- Запросы из неожиданных IP адресов
- Ошибки аутентификации
- Превышение rate limits

**Пример мониторинга:**
```python
def monitor_api_usage():
    """Мониторинг подозрительной активности API"""
    # Проверка превышения обычного использования
    if current_usage > normal_usage * 2:
        send_alert("Необычно высокое использование API")
    
    # Проверка новых IP адресов
    if request_ip not in known_ips:
        send_alert(f"Запрос с нового IP: {request_ip}")
```

---

## 📚 Дополнительные ресурсы

### Полезные ссылки:
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [12-Factor App Config](https://12factor.net/config)

### Инструменты безопасности:
- **git-secrets** - предотвращение коммитов с секретами
- **detect-secrets** - обнаружение секретов в коде
- **GitLeaks** - сканирование Git репозиториев
- **TruffleHog** - поиск секретов с высокой энтропией

---

## 🎯 Ожидаемые результаты

После выполнения всех рекомендаций:

✅ **Безопасность:** 0 захардкоженных секретов в коде  
✅ **Мониторинг:** Автоматическое обнаружение утечек  
✅ **Процессы:** Четкие процедуры реагирования на инциденты  
✅ **Автоматизация:** CI/CD проверки безопасности  
✅ **Документация:** Полное покрытие процедур безопасности  

**Общий уровень безопасности:** ВЫСОКИЙ ⭐⭐⭐⭐⭐

---

*Рекомендации по безопасности созданы: 2025-01-15*  
*Следующий аудит безопасности: 2025-02-15*
