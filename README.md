# 🎙️ Speech Pipeline

**Многоагентный пайплайн для обработки аудио с диаризацией спикеров и транскрипцией**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Возможности

- 🎵 **Обработка аудио**: Автоматическая конвертация в нужный формат (WAV, MP3, M4A, и др.)
- 🎤 **Диаризация спикеров**: Определение кто и когда говорит (pyannote.ai API)
- 📝 **Транскрипция**: Преобразование речи в текст с выбором модели:
  - **Whisper-1**: Быстро и экономично
  - **GPT-4o Mini Transcribe**: Баланс цены и качества
  - **GPT-4o Transcribe**: Максимальное качество и точность
- 🌍 **Многоязычность**: Поддержка 99+ языков с автоопределением
- 🔗 **Объединение**: Синхронизация диаризации с транскрипцией
- 💾 **Экспорт**: Поддержка форматов SRT, ASS, JSON
- 💰 **Оценка стоимости**: Предварительный расчет затрат на транскрипцию
- 🔒 **Безопасность**: Валидация файлов, rate limiting, secure upload
- 📊 **Мониторинг**: Health checks, метрики производительности
- 🔗 **Веб-хуки**: Асинхронная обработка с уведомлениями pyannote.ai

## 🏗️ Архитектура

Пайплайн построен на модульной агентной архитектуре:

```
AudioLoaderAgent → DiarizationAgent → TranscriptionAgent → MergeAgent → ExportAgent
```

### 🤖 Агенты

1. **AudioLoaderAgent**: Загрузка, валидация и конвертация аудио
2. **DiarizationAgent**: Диаризация через pyannote.ai API
3. **TranscriptionAgent**: Транскрипция через OpenAI Whisper API
4. **MergeAgent**: Объединение результатов диаризации и транскрипции
5. **ExportAgent**: Экспорт в различные форматы
6. **WebhookAgent**: Обработка веб-хуков pyannote.ai для асинхронной работы

## 🚀 Быстрый старт

### Предварительные требования

- **Python 3.8+**
- **FFmpeg** (для конвертации аудио)
- **API ключи**:
  - [pyannote.ai](https://dashboard.pyannote.ai) - для диаризации
  - [OpenAI](https://platform.openai.com) - для транскрипции

### Установка

1. **Клонируйте репозиторий:**
```bash
git clone https://github.com/your-username/speech-pipeline.git
cd speech-pipeline
```

2. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

3. **Установите FFmpeg:**

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows:**
- Скачайте с [ffmpeg.org](https://ffmpeg.org/download.html)
- Или используйте: `winget install ffmpeg`

4. **Настройте переменные окружения:**
```bash
cp .env.example .env
```

Отредактируйте `.env` файл:
```env
PYANNOTEAI_API_TOKEN=your_pyannote_api_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### Первый запуск

```bash
# Проверка системы
python health_check.py

# Обработка аудиофайла
python speech_pipeline.py your_audio.wav --format srt -o output.srt
```

## 📖 Использование

### Базовые команды

```bash
# Простая диаризация и транскрипция (Whisper-1)
python speech_pipeline.py audio.wav --format srt -o result.srt

# Высокое качество транскрипции (GPT-4o Transcribe)
python speech_pipeline.py audio.wav \
  --transcription-model gpt-4o-transcribe \
  --format srt -o result.srt

# Баланс цены и качества (GPT-4o Mini Transcribe)
python speech_pipeline.py audio.wav \
  --transcription-model gpt-4o-mini-transcribe \
  --language en \
  --format json -o result.json

# Показать оценку стоимости для всех моделей
python speech_pipeline.py audio.wav --show-cost-estimate
```

### Продвинутые возможности

```bash
# Replicate (быстро и дешево)
python speech_pipeline.py audio.wav \
  --use-replicate \
  --language de \
  --replicate-speakers 2 \
  --format srt -o result.srt

# Идентификация спикеров через voiceprints
# 1. Создать voiceprints
python voiceprint_cli.py create john_sample.wav "John Doe"
python voiceprint_cli.py create jane_sample.wav "Jane Smith"

# 2. Использовать для идентификации
python speech_pipeline.py meeting.wav \
  --use-identification \
  --voiceprints "John Doe,Jane Smith" \
  --matching-threshold 0.5 \
  --format srt -o result.srt

# Обработка удаленного файла
python speech_pipeline.py dummy.wav \
  --remote-wav-url https://example.com/audio.wav \
  --format srt -o result.srt

# Асинхронная обработка с веб-хуками
python webhook_server_cli.py &  # Запуск webhook сервера
python speech_pipeline.py audio.wav \
  --async-webhook http://localhost:8000/webhook \
  --format srt -o result.srt
```

### Параметры командной строки

| Параметр | Описание | Пример |
|----------|----------|---------|
| `input` | Путь к аудиофайлу | `audio.wav` |
| `--format` | Формат вывода | `srt`, `ass`, `json` |
| `-o, --output` | Выходной файл | `-o result.srt` |
| `--transcription-model` | Модель транскрипции | `whisper-1`, `gpt-4o-mini-transcribe`, `gpt-4o-transcribe` |
| `--language` | Код языка | `en`, `ru`, `de`, `fr`, `es` |
| `--show-cost-estimate` | Показать оценку стоимости | `--show-cost-estimate` |
| `--prompt` | Контекстная подсказка | `--prompt "Technical discussion"` |
| `--remote-wav-url` | URL удаленного файла | `--remote-wav-url https://...` |
| `--use-replicate` | Использовать Replicate API | `--use-replicate` |
| `--replicate-speakers` | Количество спикеров для Replicate | `--replicate-speakers 2` |
| `--use-identification` | Идентификация через voiceprints | `--use-identification` |
| `--voiceprints` | Список имен voiceprints | `--voiceprints "John,Jane"` |
| `--matching-threshold` | Порог сходства voiceprints | `--matching-threshold 0.5` |
| `--async-webhook` | URL для асинхронной обработки | `--async-webhook http://localhost:8000/webhook` |

## 🎯 Методы обработки

Speech Pipeline предлагает три различных метода обработки аудио:

### 📊 Сравнение методов

| Метод | Скорость | Точность | Стоимость | Сложность | Рекомендации |
|-------|----------|----------|-----------|-----------|--------------|
| **Стандартный** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | Универсальное решение |
| **Replicate** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | Быстро и дешево |
| **Voiceprint** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | Точная идентификация |

### 🚀 Replicate (рекомендуется)
- **Преимущества**: В 2 раза быстрее, в 167 раз дешевле
- **Технологии**: Whisper Large V3 Turbo + Pyannote 3.3.1
- **Использование**: `--use-replicate`

### 🎯 Voiceprint идентификация
- **Преимущества**: Точная идентификация известных спикеров
- **Требования**: Предварительное создание voiceprints
- **Использование**: `--use-identification --voiceprints "Name1,Name2"`

### 🔧 Стандартный метод
- **Преимущества**: Полный контроль, настраиваемость
- **Технологии**: pyannote.ai + OpenAI API
- **Использование**: По умолчанию

## 🎯 Модели транскрипции

Speech Pipeline поддерживает три модели транскрипции с разными характеристиками:

### 📊 Сравнение моделей

| Модель | Качество | Скорость | Стоимость | Рекомендации |
|--------|----------|----------|-----------|--------------|
| **whisper-1** | Базовое | Быстро | Низкая | Быстрые задачи, черновики |
| **gpt-4o-mini-transcribe** | Хорошее | Средне | Средняя | Баланс цены и качества |
| **gpt-4o-transcribe** | Отличное | Медленно | Высокая | Критически важные задачи |

### 💡 Когда использовать какую модель

**Whisper-1** - выбирайте для:
- Быстрого прототипирования
- Обработки больших объемов аудио
- Когда бюджет ограничен
- Черновых транскрипций

**GPT-4o Mini Transcribe** - выбирайте для:
- Большинства производственных задач
- Когда нужен баланс качества и стоимости
- Многоязычного контента
- Регулярной обработки аудио

**GPT-4o Transcribe** - выбирайте для:
- Максимального качества транскрипции
- Сложного или специализированного контента
- Когда точность критически важна
- Финальных версий документов

### 🌍 Поддержка языков

Все модели поддерживают 99+ языков с автоопределением. Для улучшения точности рекомендуется указывать язык:

```bash
# Русский язык
python speech_pipeline.py audio.wav --language ru --transcription-model gpt-4o-transcribe

# Английский язык
python speech_pipeline.py audio.wav --language en --transcription-model gpt-4o-mini-transcribe

# Автоопределение языка
python speech_pipeline.py audio.wav --transcription-model whisper-1
```

### 🔍 Результаты сравнения моделей

**Пример транскрипции немецкого аудио (1MB, 3.7 минуты):**

| Модель | Время | Символов | Качество | Стоимость |
|--------|-------|----------|----------|-----------|
| **whisper-1** | ~5.6с | 1299 | Базовое | ~$0.006 |
| **gpt-4o-mini-transcribe** | ~3.8с | 1299 | Хорошее | ~$0.012 |
| **gpt-4o-transcribe** | ~5.2с | 1341 | Отличное | ~$0.024 |

**Ключевые различия:**
- **GPT-4o-transcribe** лучше распознает сложные слова и контекст
- **GPT-4o-mini-transcribe** предлагает хороший баланс скорости и качества
- **Whisper-1** остается самым быстрым и экономичным вариантом

**Важно:**
- **Whisper-1** поддерживает `verbose_json` и возвращает детальные сегменты с временными метками
- **GPT-4o модели** поддерживают только `json`, `text`, `srt`, `vtt` форматы (НЕ поддерживают `verbose_json`)
- Speech Pipeline автоматически выбирает оптимальный формат для каждой модели

### 📋 Поддерживаемые форматы ответа

| Формат | Whisper-1 | GPT-4o Mini | GPT-4o Full | Описание |
|--------|-----------|-------------|-------------|----------|
| **verbose_json** | ✅ | ❌ | ❌ | Детальные сегменты с временными метками |
| **json** | ✅ | ✅ | ✅ | Минимальный JSON с полем text |
| **text** | ✅ | ✅ | ✅ | Чистый текст без обёртки |
| **srt** | ✅ | ✅ | ✅ | Субтитры в формате SRT |
| **vtt** | ✅ | ✅ | ✅ | Субтитры в формате WebVTT |

**Автоматический выбор:**
- Whisper-1 → `verbose_json` (детальная сегментация)
- GPT-4o модели → `json` (полный текст)

## ⚙️ Конфигурация

### Основные настройки (.env)

```env
# API ключи (обязательно)
PYANNOTEAI_API_TOKEN=your_token_here
OPENAI_API_KEY=your_key_here

# Дополнительные API ключи (опционально)
REPLICATE_API_TOKEN=your_replicate_token_here

# Производительность
MAX_FILE_SIZE_MB=300
MAX_CONCURRENT_JOBS=3
LOG_LEVEL=INFO

# Безопасность
STRICT_MIME_VALIDATION=true
REQUIRE_HTTPS_URLS=true
ENABLE_RATE_LIMITING=true

# Веб-хуки (опционально)
PYANNOTEAI_WEBHOOK_SECRET=your_webhook_secret_here
WEBHOOK_SERVER_PORT=8000
WEBHOOK_SERVER_HOST=0.0.0.0
```

### Поддерживаемые форматы

**Входные аудиоформаты:**
- WAV, MP3, M4A, FLAC, OGG, AAC
- Максимальный размер: 300MB (настраивается)
- Максимальная длительность: 24 часа

**Выходные форматы:**
- **SRT**: Стандартные субтитры
- **ASS**: Продвинутые субтитры для видео
- **JSON**: Структурированные данные с метаданными

## 🔗 Веб-хуки (Асинхронная обработка)

Speech Pipeline поддерживает веб-хуки pyannote.ai для асинхронной обработки задач, что значительно улучшает производительность.

### 🚀 Быстрый старт с веб-хуками

```bash
# 1. Запуск webhook сервера
python webhook_server_cli.py

# 2. Асинхронная обработка (в другом терминале)
python speech_pipeline.py audio.wav \
  --async-webhook http://localhost:8000/webhook \
  --format srt -o result.srt
```

### ⚡ Преимущества веб-хуков

- **Быстрее**: Мгновенные уведомления вместо polling
- **Эффективнее**: Меньше API запросов
- **Надежнее**: Автоматические повторы при сбоях
- **Безопаснее**: Верификация подписи HMAC-SHA256

### 📋 Настройка веб-хуков

1. **Получите webhook секрет** в [dashboard.pyannote.ai](https://dashboard.pyannote.ai) → Webhooks
2. **Добавьте в .env**:
   ```env
   PYANNOTEAI_WEBHOOK_SECRET=whs_your_secret_here
   ```
3. **Запустите webhook сервер**:
   ```bash
   python webhook_server_cli.py --port 8000
   ```

### 🔧 Команды webhook сервера

```bash
# Базовый запуск
python webhook_server_cli.py

# Режим отладки
python webhook_server_cli.py --debug

# Кастомный порт
python webhook_server_cli.py --port 9000

# Health check
curl http://localhost:8000/health

# Метрики
curl http://localhost:8000/metrics
```

### 📚 Подробная документация

Полное руководство по веб-хукам: [docs/guides/WEBHOOK_GUIDE.md](docs/guides/WEBHOOK_GUIDE.md)

## 🔧 API ключи

### Получение pyannote.ai API ключа

1. Зарегистрируйтесь на [dashboard.pyannote.ai](https://dashboard.pyannote.ai)
2. Перейдите в раздел API Keys
3. Создайте новый ключ
4. Скопируйте в `PYANNOTEAI_API_TOKEN`

### Получение OpenAI API ключа

1. Зарегистрируйтесь на [platform.openai.com](https://platform.openai.com)
2. Перейдите в API Keys
3. Создайте новый секретный ключ
4. Скопируйте в `OPENAI_API_KEY`

### Получение Replicate API ключа (опционально)

1. Зарегистрируйтесь на [replicate.com](https://replicate.com)
2. Перейдите в Account Settings → API tokens
3. Создайте новый токен
4. Скопируйте в `REPLICATE_API_TOKEN`

## 🏥 Мониторинг и диагностика

### Health Check

```bash
python health_check.py
```

Проверяет:
- ✅ Доступность API ключей
- ✅ Установку зависимостей
- ✅ Доступность FFmpeg
- ✅ Права доступа к файлам
- ✅ Сетевое подключение

### Логирование

Логи сохраняются в `logs/` с ротацией по дням:
- `logs/speech_pipeline_YYYY-MM-DD.log`
- `logs/health_report_YYYY-MM-DD.json`

## 🧪 Тестирование

### Основные тесты

```bash
# Запуск всех тестов
pytest

# Тесты с покрытием
pytest --cov=pipeline

# Тесты конкретного модуля
pytest tests/test_audio_agent.py
```

### 📊 Тестирование качества транскрипции (WER)

Speech Pipeline включает комплексную систему оценки качества транскрипции с расчетом WER (Word Error Rate) и CER (Character Error Rate) метрик.

#### 🚀 Быстрый старт WER тестирования

```bash
# Автоматическое тестирование всех доступных моделей
python transcription_quality_test.py

# Тестирование конкретных файлов
python transcription_quality_test.py \
  --audio-files audio1.wav audio2.mp3 \
  --reference-texts "Эталонный текст 1" "Эталонный текст 2"

# Демонстрация с моковыми данными
python demo_wer_testing.py
```

#### 📋 Возможности WER тестирования

- **Автоматический расчет метрик**: WER, CER, точность слов и символов
- **Поддержка всех моделей**: OpenAI (whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe), Replicate
- **Многоязычность**: Тестирование на русском, немецком, английском и других языках
- **Сравнительный анализ**: Производительность, стоимость, время обработки
- **Подробные отчеты**: Markdown и JSON форматы с рекомендациями

#### 📊 Результаты демонстрационного тестирования

| Модель | Точность слов | WER | Время (с) | Стоимость |
|--------|---------------|-----|-----------|-----------|
| **gpt-4o-transcribe** | 100.0% | 0.000 | 4.1 | $0.0240 |
| **replicate-whisper-diarization** | 100.0% | 0.000 | 1.8 | $0.0080 |
| **gpt-4o-mini-transcribe** | 95.6% | 0.044 | 3.2 | $0.0120 |
| **whisper-1** | 91.4% | 0.086 | 2.5 | $0.0060 |

#### 🎯 Рекомендации по выбору модели

- **Лучшая точность**: gpt-4o-transcribe (идеальная точность, но медленнее)
- **Оптимальный баланс**: replicate-whisper-diarization (отличная точность + скорость)
- **Экономичный вариант**: whisper-1 (приемлемая точность, низкая стоимость)

#### 🔧 Параметры WER тестирования

```bash
# Полный список опций
python transcription_quality_test.py --help

# Тестирование конкретных моделей
python transcription_quality_test.py --models whisper-1 gpt-4o-transcribe

# Указание языка
python transcription_quality_test.py --language ru

# Режим предварительного просмотра
python transcription_quality_test.py --dry-run

# Подробный вывод
python transcription_quality_test.py --verbose
```

#### 📁 Результаты тестирования

Результаты сохраняются в:
- `data/interim/wer_evaluation_results.json` - JSON с детальными метриками
- `data/interim/transcription_quality_report.md` - Markdown отчет с рекомендациями

## 📁 Структура проекта

```
speech-pipeline/
├── pipeline/                    # Основные модули
│   ├── audio_agent.py          # Обработка аудио
│   ├── diarization_agent.py    # Диаризация
│   ├── transcription_agent.py  # Транскрипция
│   ├── replicate_agent.py      # Replicate API
│   ├── voiceprint_agent.py     # Создание voiceprints
│   ├── identification_agent.py # Идентификация спикеров
│   ├── voiceprint_manager.py   # Управление voiceprints
│   ├── webhook_agent.py        # Обработка веб-хуков
│   ├── webhook_server.py       # HTTP сервер для веб-хуков
│   ├── wer_evaluator.py        # WER/CER оценка качества
│   ├── transcription_quality_tester.py # Комплексное тестирование
│   ├── merge_agent.py          # Объединение
│   └── export_agent.py         # Экспорт
├── data/                       # Данные
│   ├── raw/                    # Исходные файлы
│   ├── interim/                # Промежуточные результаты
│   └── processed/              # Готовые результаты
├── voiceprints/                # База голосовых отпечатков
│   └── voiceprints.json        # JSON база данных
├── docs/                       # Документация
│   ├── guides/
│   │   ├── VOICEPRINT_GUIDE.md # Руководство по voiceprints
│   │   └── WEBHOOK_GUIDE.md    # Руководство по веб-хукам
├── tests/                      # Тесты
│   ├── test_webhook_agent.py   # Тесты веб-хуков
│   ├── test_webhook_server.py  # Тесты HTTP сервера
│   ├── test_webhook_integration.py # Интеграционные тесты
│   ├── test_wer_evaluator.py   # Тесты WER калькулятора
│   └── test_transcription_quality_integration.py # Тесты WER интеграции
├── logs/                       # Логи
├── speech_pipeline.py          # Главный скрипт
├── voiceprint_cli.py           # CLI для voiceprints
├── webhook_server_cli.py       # CLI для webhook сервера
├── transcription_quality_test.py # CLI для WER тестирования
├── demo_wer_testing.py         # Демонстрация WER тестирования
├── health_check.py             # Диагностика
├── requirements.txt            # Зависимости
├── .env.example               # Пример конфигурации
└── README.md                  # Документация
```

## ⚡ Производительность

Speech Pipeline оптимизирован для высокой производительности с интеллектуальными стратегиями retry и адаптивными таймаутами.

### 🚀 Оптимизации Фазы 3

**Улучшенная обработка ошибок OpenAI API:**
- ✅ **Exponential backoff** с jitter для rate limit ошибок
- ✅ **Интеллектуальное различение ошибок** (RateLimitError vs APIConnectionError)
- ✅ **Адаптивные таймауты** на основе размера файла (60с + 10с/MB, макс 10 мин)
- ✅ **Детальное логирование** retry статистики для мониторинга
- ✅ **8 попыток** вместо 3 с умными стратегиями ожидания

**Ожидаемые улучшения:**
- 📈 **62% снижение времени retry** для OpenAI API
- 📊 **Детальная статистика** retry попыток в логах
- 🎯 **Умные стратегии** для разных типов ошибок

### 📊 Статистика retry

Пример логирования производительности:
```
📊 Статистика retry: всего попыток=5, rate_limit=3, connection=1, other=1, общее время retry=25.5с
🔄 Rate limit hit (попытка 2), ждем 4.2с (base: 4.0с, jitter: 0.2с)
🌐 Сетевая ошибка (попытка 1), быстрый повтор через 0.5с
⚠️ Другая ошибка (попытка 3), повтор через 2.3с: APITimeoutError
```

### 🎯 Планируемые оптимизации

**Фаза 3 (в разработке):**
- 🔄 **Параллельная обработка** частей файлов (до 3 одновременно)
- 📏 **Оптимизация разбиения** файлов по паузам в речи
- 🎛️ **Динамический размер** частей (15-20MB вместо 10 минут)

**Ожидаемый результат:** Ускорение в **6-7 раз** (с 42 мин до 6 мин для 140 мин аудио)

## 🔒 Безопасность

- **API ключи**: Никогда не коммитьте .env файл
- **Валидация файлов**: Проверка MIME типов и размеров
- **Rate limiting**: Защита от превышения лимитов API
- **Временное хранилище**: Файлы автоматически удаляются через 24-48 часов

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 🆘 Поддержка

- **Issues**: [GitHub Issues](https://github.com/your-username/speech-pipeline/issues)
- **Документация**: [Wiki](https://github.com/your-username/speech-pipeline/wiki)
- **Email**: support@yourproject.com

---

**Сделано с ❤️ для сообщества разработчиков**
