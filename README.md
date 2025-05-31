# 🎙️ Speech Pipeline

**Многоагентный пайплайн для обработки аудио с диаризацией спикеров и транскрипцией**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Возможности

- 🎵 **Обработка аудио**: Автоматическая конвертация в нужный формат (WAV, MP3, M4A, и др.)
- 🎤 **Диаризация спикеров**: Определение кто и когда говорит (pyannote.ai API)
- 📝 **Транскрипция**: Преобразование речи в текст (OpenAI Whisper)
- 🔗 **Объединение**: Синхронизация диаризации с транскрипцией
- 💾 **Экспорт**: Поддержка форматов SRT, ASS, JSON
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
# Простая диаризация и транскрипция
python speech_pipeline.py audio.wav --format srt -o result.srt

# Экспорт в JSON с метаданными
python speech_pipeline.py audio.wav --format json -o result.json

# Экспорт в ASS для видео
python speech_pipeline.py audio.wav --format ass -o subtitles.ass
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
| `--remote-wav-url` | URL удаленного файла | `--remote-wav-url https://...` |
| `--voiceprints-dir` | Папка с голосовыми отпечатками | `--voiceprints-dir ./voices` |
| `--identify` | ID голосовых отпечатков | `--identify speaker1,speaker2` |

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
