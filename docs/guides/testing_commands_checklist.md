# 🧪 Проверка работоспособности всех вариантов обработки

## 🏥 ЭТАП 1: Диагностика системы

### Базовая проверка системы
```bash
# ✅ Проверка готовности (КРИТИЧЕСКИ ВАЖНО)
python3 health_check.py

# ✅ Детальная диагностика
python3 health_check.py --detailed --json

# ✅ Проверка зависимостей
pip install -r requirements.txt
```

### Проверка API ключей
```bash
# ✅ Проверка переменных окружения
echo $PYANNOTEAI_API_TOKEN
echo $OPENAI_API_KEY  
echo $REPLICATE_API_TOKEN

# ✅ Создание .env файла (если отсутствует)
cp .env.example .env
# Отредактировать .env с реальными ключами
```

### Создание тестовых данных
```bash
# ✅ Создание тестовых директорий
mkdir -p data/raw data/interim data/processed
mkdir -p logs voiceprints cache

# ✅ Подготовка тестового аудио файла
# Поместить короткий (30-60 сек) WAV файл в data/raw/test_audio.wav
```

---

## 🧪 ЭТАП 2: Тестирование основных сценариев

### 📊 2.1 Стандартный пайплайн

#### Базовые тесты
```bash
# ✅ TEST 1: Минимальная конфигурация
python3 speech_pipeline.py data/raw/test_audio.wav

# ✅ TEST 2: С указанием выходного файла
python3 speech_pipeline.py data/raw/test_audio.wav -o data/processed/test_result.srt

# ✅ TEST 3: JSON формат
python3 speech_pipeline.py data/raw/test_audio.wav --format json -o data/processed/test_result.json

# ✅ TEST 4: Все форматы
python3 speech_pipeline.py data/raw/test_audio.wav --all-formats

# ✅ TEST 5: С временными метками
python3 speech_pipeline.py data/raw/test_audio.wav --add-timestamp
```

#### Тесты моделей транскрипции
```bash
# ✅ TEST 6: Whisper-1
python3 speech_pipeline.py data/raw/test_audio.wav \
  --transcription-model whisper-1 \
  --format srt -o data/processed/whisper1_result.srt

# ✅ TEST 7: GPT-4o Mini
python3 speech_pipeline.py data/raw/test_audio.wav \
  --transcription-model gpt-4o-mini-transcribe \
  --language en \
  --format json -o data/processed/gpt4o_mini_result.json

# ✅ TEST 8: GPT-4o Full
python3 speech_pipeline.py data/raw/test_audio.wav \
  --transcription-model gpt-4o-transcribe \
  --language en \
  --format srt -o data/processed/gpt4o_full_result.srt

# ✅ TEST 9: Оценка стоимости
python3 speech_pipeline.py data/raw/test_audio.wav --show-cost-estimate
```

#### Тесты с языками
```bash
# ✅ TEST 10: Русский язык
python3 speech_pipeline.py data/raw/test_audio.wav --language ru

# ✅ TEST 11: Немецкий язык  
python3 speech_pipeline.py data/raw/test_audio.wav --language de

# ✅ TEST 12: С контекстной подсказкой
python3 speech_pipeline.py data/raw/test_audio.wav \
  --prompt "Technical discussion about AI" \
  --language en
```

### ⚡ 2.2 Replicate пайплайн

```bash
# ✅ TEST 13: Базовый Replicate
python3 speech_pipeline.py data/raw/test_audio.wav --use-replicate

# ✅ TEST 14: Replicate с количеством спикеров
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-replicate \
  --replicate-speakers 2

# ✅ TEST 15: Replicate с языком
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-replicate \
  --language en \
  --format json -o data/processed/replicate_result.json

# ✅ TEST 16: Replicate все форматы
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-replicate \
  --all-formats
```

### 👤 2.3 Voiceprint система

#### Создание voiceprints
```bash
# ✅ TEST 17: Создание тестового voiceprint
python3 pipeline/voiceprint_cli.py create data/raw/test_audio.wav "Test Speaker"

# ✅ TEST 18: Создание с оценкой стоимости
python3 pipeline/voiceprint_cli.py create data/raw/test_audio.wav "Speaker 2" --show-cost

# ✅ TEST 19: Список voiceprints
python3 pipeline/voiceprint_cli.py list

# ✅ TEST 20: Детальная информация о voiceprints
python3 pipeline/voiceprint_cli.py list --detailed

# ✅ TEST 21: Поиск voiceprint
python3 pipeline/voiceprint_cli.py search "Test"

# ✅ TEST 22: Экспорт базы voiceprints
python3 pipeline/voiceprint_cli.py export data/interim/voiceprints_backup.json
```

#### Использование voiceprints для идентификации
```bash
# ✅ TEST 23: Базовая идентификация
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-identification \
  --voiceprints "Test Speaker"

# ✅ TEST 24: Идентификация с порогом сходства
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-identification \
  --voiceprints "Test Speaker,Speaker 2" \
  --matching-threshold 0.5

# ✅ TEST 25: Идентификация + GPT-4o
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-identification \
  --voiceprints "Test Speaker" \
  --transcription-model gpt-4o-mini-transcribe \
  --format json -o data/processed/identified_result.json
```

#### Продвинутое управление voiceprints
```bash
# ✅ TEST 26: Анализ базы voiceprints
python3 pipeline/voiceprint_management_suite.py analyze

# ✅ TEST 27: Валидация voiceprints
python3 pipeline/voiceprint_management_suite.py validate

# ✅ TEST 28: Отчет по качеству
python3 pipeline/voiceprint_management_suite.py quality-check

# ✅ TEST 29: Создание JSON отчета
python3 pipeline/voiceprint_management_suite.py report --format json
```

### 🔗 2.4 Webhook система

#### Запуск webhook сервера
```bash
# ✅ TEST 30: Запуск webhook сервера (в отдельном терминале)
python3 pipeline/webhook_server_cli.py --port 8001 &

# Проверка запуска (в основном терминале)
sleep 5  # Ждем запуска сервера
curl http://localhost:8001/health

# ✅ TEST 31: Проверка метрик
curl http://localhost:8001/metrics

# ✅ TEST 32: Проверка статуса
curl http://localhost:8001/status
```

#### Асинхронная обработка
```bash
# ✅ TEST 33: Асинхронная обработка (требует webhook сервер)
python3 speech_pipeline.py data/raw/test_audio.wav \
  --async-webhook http://localhost:8001/webhook \
  --format srt -o data/processed/async_result.srt

# ✅ TEST 34: Асинхронная обработка с параметрами
python3 speech_pipeline.py data/raw/test_audio.wav \
  --async-webhook http://localhost:8001/webhook \
  --transcription-model gpt-4o-mini-transcribe \
  --language en \
  --all-formats

# Остановка webhook сервера
pkill -f webhook_server_cli.py
```

---

## 🧪 ЭТАП 3: Тестирование качества и производительности

### 📊 3.1 Оценка качества транскрипции

```bash
# ✅ TEST 35: Автоматическое тестирование WER
python3 pipeline/quality_testing_suite.py auto-test

# ✅ TEST 36: Демонстрационное тестирование
python3 pipeline/quality_testing_suite.py demo

# ✅ TEST 37: Детальное демо с метриками
python3 pipeline/quality_testing_suite.py demo --verbose

# ✅ TEST 38: Сравнение моделей
python3 pipeline/quality_testing_suite.py compare \
  --audio-file data/raw/test_audio.wav \
  --reference-text "Эталонный текст для сравнения"

# ✅ TEST 39: Benchmark производительности
python3 pipeline/quality_testing_suite.py benchmark \
  --duration 30 \
  --iterations 3
```

### 📊 3.2 Тестирование конкретных файлов

```bash
# ✅ TEST 40: WER тестирование с референсным текстом
python3 pipeline/quality_testing_suite.py test \
  --audio-files data/raw/test_audio.wav \
  --reference-texts "Известный референсный текст" \
  --models whisper-1 gpt-4o-mini-transcribe

# ✅ TEST 41: Языково-специфическое тестирование
python3 pipeline/quality_testing_suite.py test \
  --audio-files data/raw/test_audio.wav \
  --reference-texts "Reference text" \
  --language en \
  --models gpt-4o-transcribe

# ✅ TEST 42: Создание детального отчета
python3 pipeline/quality_testing_suite.py test \
  --audio-files data/raw/test_audio.wav \
  --reference-texts "Reference text" \
  --verbose \
  --report
```

---

## 🧪 ЭТАП 4: Специальные сценарии

### 🌐 4.1 Работа с удаленными файлами

```bash
# ✅ TEST 43: Обработка удаленного файла (с публичным URL)
python3 speech_pipeline.py dummy.wav \
  --remote-wav-url https://sample-videos.com/zip/10/wav/SampleAudio_0.4mb_wav.wav \
  --format srt -o data/processed/remote_result.srt

# ✅ TEST 44: Удаленный файл + Replicate
python3 speech_pipeline.py dummy.wav \
  --remote-wav-url https://sample-videos.com/zip/10/wav/SampleAudio_0.4mb_wav.wav \
  --use-replicate \
  --format json -o data/processed/remote_replicate_result.json
```

### 🎵 4.2 Извлечение voiceprint сэмплов

```bash
# ✅ TEST 45: Извлечение сэмплов спикеров
python3 speech_pipeline.py data/raw/test_audio.wav \
  --voiceprints-dir data/interim/extracted_samples/

# ✅ TEST 46: Проверка извлеченных сэмплов
ls -la data/interim/extracted_samples/
```

### 🎯 4.3 Комбинированные сценарии

```bash
# ✅ TEST 47: Комплексный тест (все форматы + лучшая модель)
python3 speech_pipeline.py data/raw/test_audio.wav \
  --transcription-model gpt-4o-transcribe \
  --language en \
  --prompt "Professional meeting discussion" \
  --all-formats \
  --add-timestamp

# ✅ TEST 48: Replicate + множественные спикеры
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-replicate \
  --replicate-speakers 3 \
  --language en \
  --all-formats

# ✅ TEST 49: Voiceprint + высокое качество
python3 speech_pipeline.py data/raw/test_audio.wav \
  --use-identification \
  --voiceprints "Test Speaker" \
  --transcription-model gpt-4o-transcribe \
  --matching-threshold 0.3 \
  --format docx -o data/processed/premium_result.docx
```

---

## 🐳 ЭТАП 5: Docker тестирование

### 🏗️ 5.1 Сборка и базовое тестирование

```bash
# ✅ TEST 50: Сборка Docker образа
docker build -t erni-audio-v2:test .

# ✅ TEST 51: Проверка образа
docker images | grep erni-audio-v2

# ✅ TEST 52: Тест контейнера (health check)
docker run --rm erni-audio-v2:test python3 health_check.py --json

# ✅ TEST 53: Базовая обработка в контейнере
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e PYANNOTEAI_API_TOKEN="$PYANNOTEAI_API_TOKEN" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  erni-audio-v2:test data/raw/test_audio.wav --format json
```

### 🔧 5.2 Docker Compose тестирование

```bash
# ✅ TEST 54: Запуск через Docker Compose
docker-compose up -d

# ✅ TEST 55: Проверка контейнеров
docker-compose ps

# ✅ TEST 56: Health check контейнеров
docker-compose exec erni-audio python3 health_check.py

# ✅ TEST 57: Обработка через Docker Compose
docker-compose exec erni-audio python3 speech_pipeline.py data/raw/test_audio.wav

# ✅ TEST 58: Webhook сервер в Docker
curl http://localhost:8001/health

# ✅ TEST 59: Остановка Docker Compose
docker-compose down
```

---

## 🧪 ЭТАП 6: Автоматизированное тестирование

### 🔄 6.1 Запуск полного тестового набора

```bash
# ✅ TEST 60: Запуск unit тестов
python3 -m pytest tests/ -v

# ✅ TEST 61: Тесты с покрытием кода
python3 -m pytest tests/ --cov=pipeline --cov-report=html

# ✅ TEST 62: Интеграционные тесты
python3 -m pytest tests/test_integration.py -v

# ✅ TEST 63: Производительные тесты
python3 -m pytest tests/test_performance.py -v

# ✅ TEST 64: Docker функциональные тесты
python3 tests/docker_functional_test.py

# ✅ TEST 65: Генерация отчета о покрытии
python3 tests/generate_coverage_report.py
```

### 🔧 6.2 Специализированные тесты

```bash
# ✅ TEST 66: Тест webhook системы
python3 -m pytest tests/test_webhook_integration.py -v

# ✅ TEST 67: Тест voiceprint функциональности
python3 -m pytest tests/test_voiceprint_functionality.py -v

# ✅ TEST 68: Тест модельного сравнения
python3 -m pytest tests/test_model_comparison.py -v

# ✅ TEST 69: Тест WER evaluator
python3 -m pytest tests/test_wer_evaluator.py -v

# ✅ TEST 70: Полный диагностический скрипт
python3 tests/diagnostic_script.py
```

---

## 📋 ЭТАП 7: Валидация результатов

### ✅ 7.1 Проверка выходных файлов

```bash
# ✅ TEST 71: Проверка созданных файлов
ls -la data/processed/

# ✅ TEST 72: Валидация SRT файлов
file data/processed/*.srt

# ✅ TEST 73: Валидация JSON файлов
python3 -c "
import json
import glob
for f in glob.glob('data/processed/*.json'):
    try:
        with open(f) as file:
            json.load(file)
        print(f'✅ {f} - валидный JSON')
    except:
        print(f'❌ {f} - невалидный JSON')
"

# ✅ TEST 74: Проверка логов
tail -n 50 logs/speech_pipeline_*.log

# ✅ TEST 75: Проверка базы voiceprints
cat voiceprints/voiceprints.json | python3 -m json.tool
```

### 📊 7.2 Анализ производительности

```bash
# ✅ TEST 76: Анализ времени обработки
grep "Processing time" logs/speech_pipeline_*.log

# ✅ TEST 77: Анализ использования памяти
grep "Memory usage" logs/speech_pipeline_*.log

# ✅ TEST 78: Анализ API вызовов
grep "API call" logs/speech_pipeline_*.log

# ✅ TEST 79: Статистика ошибок
grep "ERROR" logs/speech_pipeline_*.log | wc -l

# ✅ TEST 80: Финальная проверка health
python3 health_check.py --detailed --save-report
```

---

## 🎯 КРИТЕРИИ УСПЕШНОСТИ ТЕСТОВ

### ✅ **Обязательные требования**

1. **Health check проходит** без критических ошибок
2. **Все API ключи** корректно настроены и работают
3. **Базовая обработка** создает валидные выходные файлы
4. **Replicate пайплайн** работает и показывает улучшенную производительность
5. **Voiceprint система** создает и использует voiceprints
6. **Webhook сервер** запускается и принимает запросы
7. **Docker образ** собирается и работает корректно
8. **Unit тесты** проходят с success rate > 95%

### ⚠️ **Допустимые предупреждения**

- Предупреждения о отсутствии опциональных зависимостей
- Rate limiting предупреждения при тестировании API
- Предупреждения о пропуске тестов при отсутствии API ключей

### ❌ **Критические ошибки**

- Ошибки импорта основных модулей
- Ошибки аутентификации API
- Ошибки создания выходных файлов
- Ошибки Docker сборки
- Crash'и основных агентов

---

## 🚀 БЫСТРЫЙ ТЕСТОВЫЙ НАБОР (5 минут)

Для быстрой проверки работоспособности выполните следующие команды:

```bash
# 1. Базовая диагностика
python3 health_check.py

# 2. Простая обработка
python3 speech_pipeline.py data/raw/test_audio.wav

# 3. Replicate тест
python3 speech_pipeline.py data/raw/test_audio.wav --use-replicate

# 4. Создание voiceprint
python3 pipeline/voiceprint_cli.py create data/raw/test_audio.wav "Test"

# 5. Unit тесты (быстрые)
python3 -m pytest tests/test_audio_agent.py -v

# Если все 5 тестов прошли успешно - система готова к работе! ✅
```

---

## 📝 ОТЧЕТ О ТЕСТИРОВАНИИ

После завершения тестирования создайте отчет:

```bash
echo "=== ОТЧЕТ О ТЕСТИРОВАНИИ ERNI AUDIO V2 ===" > test_report.txt
echo "Дата: $(date)" >> test_report.txt
echo "Версия: $(cat VERSION)" >> test_report.txt
echo "" >> test_report.txt

echo "РЕЗУЛЬТАТЫ ТЕСТОВ:" >> test_report.txt
echo "- Health check: $(python3 health_check.py --json > /dev/null 2>&1 && echo '✅ PASS' || echo '❌ FAIL')" >> test_report.txt
echo "- Стандартный пайплайн: $(ls data/processed/*.srt > /dev/null 2>&1 && echo '✅ PASS' || echo '❌ FAIL')" >> test_report.txt
echo "- Replicate пайплайн: $(grep -q 'replicate' logs/*.log 2>/dev/null && echo '✅ PASS' || echo '❌ FAIL')" >> test_report.txt
echo "- Voiceprint система: $(ls voiceprints/voiceprints.json > /dev/null 2>&1 && echo '✅ PASS' || echo '❌ FAIL')" >> test_report.txt

cat test_report.txt
```

Этот comprehensive набор тестов обеспечивает полную проверку всех вариантов обработки аудио в вашей системе!