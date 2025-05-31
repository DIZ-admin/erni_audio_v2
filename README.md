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
# Обработка удаленного файла
python speech_pipeline.py dummy.wav \
  --remote-wav-url https://example.com/audio.wav \
  --format srt -o result.srt

# Идентификация спикеров по голосовым отпечаткам
python speech_pipeline.py audio.wav \
  --voiceprints-dir ./voiceprints \
  --identify speaker1,speaker2 \
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
| `--voiceprints-dir` | Папка с голосовыми отпечатками | `--voiceprints-dir ./voices` |
| `--identify` | ID голосовых отпечатков | `--identify speaker1,speaker2` |

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

**Важно:** GPT-4o модели возвращают один сегмент с полным текстом, в отличие от Whisper-1, который предоставляет детальную сегментацию по времени.

## ⚙️ Конфигурация

### Основные настройки (.env)

```env
# API ключи (обязательно)
PYANNOTEAI_API_TOKEN=your_token_here
OPENAI_API_KEY=your_key_here

# Производительность
MAX_FILE_SIZE_MB=300
MAX_CONCURRENT_JOBS=3
LOG_LEVEL=INFO

# Безопасность
STRICT_MIME_VALIDATION=true
REQUIRE_HTTPS_URLS=true
ENABLE_RATE_LIMITING=true
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

```bash
# Запуск всех тестов
pytest

# Тесты с покрытием
pytest --cov=pipeline

# Тесты конкретного модуля
pytest tests/test_audio_agent.py
```

## 📁 Структура проекта

```
speech-pipeline/
├── pipeline/                 # Основные модули
│   ├── audio_agent.py       # Обработка аудио
│   ├── diarization_agent.py # Диаризация
│   ├── transcription_agent.py # Транскрипция
│   ├── merge_agent.py       # Объединение
│   └── export_agent.py      # Экспорт
├── data/                    # Данные
│   ├── raw/                 # Исходные файлы
│   ├── interim/             # Промежуточные результаты
│   └── processed/           # Готовые результаты
├── tests/                   # Тесты
├── logs/                    # Логи
├── speech_pipeline.py       # Главный скрипт
├── health_check.py          # Диагностика
├── requirements.txt         # Зависимости
├── .env.example            # Пример конфигурации
└── README.md               # Документация
```

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
