# 🐳 Docker Deployment Guide - Erni Audio v2

Полное руководство по развёртыванию Erni Audio v2 в Docker контейнерах.

## 🚀 Быстрый старт

### 1. Подготовка окружения
```bash
# Клонируйте репозиторий
git clone <repository-url>
cd erni_audio_v2

# Создайте .env файл из шаблона
cp .env.example .env

# Отредактируйте .env файл с вашими API ключами
nano .env
```

### 2. Автоматическое развёртывание
```bash
# Полное развёртывание с тестами
./docker_production_deploy.sh

# Быстрое развёртывание без тестов
./docker_production_deploy.sh --skip-tests

# Развёртывание без пересборки образа
./docker_production_deploy.sh --skip-build
```

### 3. Ручное развёртывание
```bash
# Сборка образа
docker build -t erni-audio-v2:latest .

# Запуск с Docker Compose
docker-compose up -d

# Проверка статуса
docker-compose ps
```

---

## 📋 Требования

### Системные требования:
- **Docker:** >= 20.10
- **Docker Compose:** >= 2.0
- **RAM:** Минимум 2GB, рекомендуется 4GB
- **CPU:** Минимум 2 ядра
- **Диск:** Минимум 5GB свободного места

### API ключи:
- **pyannote.ai:** Для диаризации и voiceprint анализа
- **OpenAI:** Для транскрипции (whisper-1, gpt-4o-transcribe)
- **Replicate:** Для альтернативной диаризации (опционально)

---

## 🔧 Конфигурация

### Переменные окружения (.env):
```bash
# API ключи (ОБЯЗАТЕЛЬНО)
PYANNOTEAI_API_TOKEN=your_pyannote_token_here
OPENAI_API_KEY=your_openai_key_here
REPLICATE_API_TOKEN=your_replicate_token_here

# Webhook настройки
PYANNOTEAI_WEBHOOK_SECRET=your_webhook_secret_here

# Производительность
MAX_FILE_SIZE_MB=100
MAX_CONCURRENT_JOBS=3
LOG_LEVEL=INFO

# Безопасность
STRICT_MIME_VALIDATION=true
REQUIRE_HTTPS_URLS=true
ENABLE_RATE_LIMITING=true
```

### Docker Compose сервисы:
- **erni-audio:** Основной pipeline (порт 8000)
- **webhook-server:** Webhook сервер (порт 8001)

---

## 🧪 Тестирование

### Автоматические тесты:
```bash
# Базовое тестирование Docker контейнера
python3 docker_test.py --quick

# Функциональное тестирование
python3 docker_functional_test.py --quick

# Полное тестирование
python3 docker_test.py && python3 docker_functional_test.py
```

### Ручное тестирование:
```bash
# Проверка help команды
docker run --rm erni-audio-v2:latest --help

# Health check
docker-compose exec erni-audio python health_check.py --json

# Тестовая обработка файла
docker-compose exec erni-audio python speech_pipeline.py \
  tests/samples/Testdatei.m4a --show-cost-estimate
```

---

## 📊 Мониторинг

### Health Checks:
```bash
# Статус сервисов
docker-compose ps

# Health check основного сервиса
curl http://localhost:8000/health

# Health check webhook сервера
curl http://localhost:8001/health
```

### Логи:
```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f erni-audio

# Файловые логи
tail -f logs/speech_pipeline.log
tail -f logs/health_check.log
```

### Метрики:
```bash
# Использование ресурсов
docker stats

# Метрики приложения
ls -la logs/metrics/
cat logs/metrics/performance_metrics.json
```

---

## 🔒 Безопасность

### Best Practices:
- ✅ Контейнеры работают под непривилегированным пользователем
- ✅ API ключи загружаются из переменных окружения
- ✅ Сетевая изоляция между сервисами
- ✅ Валидация входных файлов
- ✅ Rate limiting для API запросов

### Важные замечания:
- 🚨 **НЕ** коммитьте .env файлы в git
- 🚨 Регулярно обновляйте API ключи
- 🚨 Мониторьте логи на предмет подозрительной активности

---

## 🛠️ Управление

### Основные команды:
```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Обновление образа
docker-compose pull
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Выполнение команд в контейнере
docker-compose exec erni-audio bash
```

### Backup и восстановление:
```bash
# Backup данных
tar -czf backup_$(date +%Y%m%d).tar.gz data/ voiceprints/ logs/

# Восстановление
tar -xzf backup_20250603.tar.gz
```

---

## 🐛 Troubleshooting

### Частые проблемы:

#### Контейнер не запускается:
```bash
# Проверьте логи
docker-compose logs erni-audio

# Проверьте .env файл
cat .env | grep -v "^#" | grep -v "^$"

# Проверьте права на файлы
ls -la data/ voiceprints/ logs/
```

#### Health check не проходит:
```bash
# Проверьте статус
docker-compose ps

# Выполните health check вручную
docker-compose exec erni-audio python health_check.py --json

# Проверьте зависимости
docker-compose exec erni-audio pip list
```

#### Ошибки API:
```bash
# Проверьте API ключи
docker-compose exec erni-audio env | grep API

# Тестируйте с mock данными
docker-compose exec erni-audio python speech_pipeline.py \
  tests/samples/Testdatei.m4a --show-cost-estimate
```

---

## 📈 Производительность

### Оптимизация:
- **CPU:** Увеличьте `MAX_CONCURRENT_JOBS` для многоядерных систем
- **Память:** Увеличьте лимиты в docker-compose.yml для больших файлов
- **Диск:** Используйте SSD для директории `data/`
- **Сеть:** Убедитесь в стабильном интернет-соединении для API

### Мониторинг производительности:
```bash
# Использование ресурсов
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Время обработки файлов
grep "Processing completed" logs/speech_pipeline.log | tail -10
```

---

## 📞 Поддержка

При возникновении проблем:

1. **Проверьте логи:** `docker-compose logs -f`
2. **Запустите тесты:** `python3 docker_test.py`
3. **Проверьте конфигурацию:** `docker-compose config`
4. **Создайте issue** с подробным описанием проблемы

---

*Документация обновлена: 3 июня 2025 г.*
