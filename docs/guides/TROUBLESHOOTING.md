# 🐛 Руководство по устранению неполадок

## ⚠️ Частые проблемы и решения

### 🔑 Проблемы с API ключами

#### Ошибка: "Invalid API key"
**Симптомы**: 
```
Error: Invalid pyannote.ai API key
Error: OpenAI API key is invalid
```

**Решения**:
1. Проверьте правильность ключей:
   ```bash
   echo $PYANNOTEAI_API_TOKEN
   echo $OPENAI_API_KEY
   ```

2. Убедитесь в отсутствии лишних символов:
   ```bash
   # Удалите переносы строк и пробелы
   export PYANNOTEAI_API_TOKEN="your_key_here"
   ```

3. Проверьте .env файл:
   ```bash
   cat .env
   # Должно быть без кавычек и пробелов
   PYANNOTEAI_API_TOKEN=your_key_here
   OPENAI_API_KEY=your_openai_key
   ```

#### Ошибка: "API key not found"
**Решение**: Установите переменные окружения:
```bash
export PYANNOTEAI_API_TOKEN="your_token"
export OPENAI_API_KEY="your_key"
```

### 📁 Проблемы с файлами

#### Ошибка: "File not found" 
**Решения**:
1. Проверьте существование файла:
   ```bash
   ls -la your_audio_file.wav
   ```

2. Используйте абсолютный путь:
   ```bash
   python3 speech_pipeline.py /full/path/to/audio.wav
   ```

3. Проверьте права доступа:
   ```bash
   chmod 644 audio_file.wav
   ```

#### Ошибка: "Unsupported file format"
**Поддерживаемые форматы**: MP3, WAV, M4A, MP4, AVI, MOV, FLAC

**Решение**: Конвертируйте файл:
```bash
ffmpeg -i input.avi -c:a libmp3lame output.mp3
```

#### Ошибка: "File size too large"
**Лимиты**:
- Стандартный: 500MB
- Replicate: 1GB
- Voiceprint: 100MB (≤30 секунд)

**Решение**: Сожмите файл:
```bash
ffmpeg -i large_file.wav -b:a 128k compressed.wav
```

### 🌐 Сетевые проблемы

#### Ошибка: "Connection timeout"
**Решения**:
1. Проверьте интернет-соединение
2. Повторите попытку (система автоматически делает 3 попытки)
3. Проверьте firewall настройки

#### Ошибка: "Rate limit exceeded"
**Решения**:
1. Подождите несколько минут
2. Проверьте лимиты в личном кабинете API
3. Используйте альтернативный метод (Replicate)

### 🎯 Проблемы с диаризацией

#### Плохое качество разделения спикеров
**Решения**:
1. Улучшите качество аудио:
   ```bash
   ffmpeg -i noisy.wav -af "highpass=f=200,lowpass=f=3000" clean.wav
   ```

2. Используйте метод Replicate:
   ```bash
   python3 speech_pipeline.py audio.wav --use-replicate
   ```

3. Проверьте количество спикеров:
   ```bash
   python3 speech_pipeline.py audio.wav --use-replicate --replicate-speakers 3
   ```

#### Спикеры объединяются некорректно
**Решения**:
1. Используйте более качественное аудио
2. Попробуйте voiceprint метод для известных спикеров
3. Проверьте, что спикеры не говорят одновременно

### 🎤 Проблемы с транскрипцией

#### Плохое качество распознавания текста
**Решения**:
1. Используйте более качественную модель:
   ```bash
   python3 speech_pipeline.py audio.wav --transcription-model gpt-4o-transcribe
   ```

2. Укажите язык явно:
   ```bash
   python3 speech_pipeline.py audio.wav --language de
   ```

3. Улучшите качество аудио:
   ```bash
   ffmpeg -i audio.wav -af "highpass=f=80,lowpass=f=8000,volume=1.5" enhanced.wav
   ```

#### Неправильный язык распознавания
**Решение**: Укажите язык:
```bash
python3 speech_pipeline.py audio.wav --language ru
```

### 👥 Проблемы с voiceprints

#### Voiceprint не создается
**Решения**:
1. Проверьте длительность файла:
   ```bash
   ffprobe -i sample.wav 2>&1 | grep Duration
   ```

2. Убедитесь, что только один спикер в записи
3. Используйте чистую речь без музыки/шума

#### Низкая точность идентификации
**Решения**:
1. Понизьте порог сходства:
   ```bash
   python3 speech_pipeline.py audio.wav \
     --use-identification \
     --voiceprints "Speaker Name" \
     --matching-threshold 0.3
   ```

2. Создайте voiceprint из более качественного образца
3. Проверьте, что спикер присутствует в аудио

#### Ошибка: "Voiceprint not found"
**Решения**:
1. Проверьте список voiceprints:
   ```bash
   python3 voiceprint_cli.py list
   ```

2. Используйте точное имя:
   ```bash
   python3 voiceprint_cli.py search "John"
   ```

### 🔧 Системные проблемы

#### Ошибка: "FFmpeg not found"
**Установка FFmpeg**:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows
# Скачайте с https://ffmpeg.org/download.html
```

#### Нехватка памяти
**Решения**:
1. Разбейте большой файл на части:
   ```bash
   ffmpeg -i large.wav -t 600 -c copy part1.wav
   ffmpeg -i large.wav -ss 600 -c copy part2.wav
   ```

2. Очистите промежуточные файлы:
   ```bash
   rm data/interim/*_converted.wav
   ```

#### Медленная обработка
**Оптимизации**:
1. Используйте Replicate для скорости:
   ```bash
   python3 speech_pipeline.py audio.wav --use-replicate
   ```

2. Используйте более быструю модель:
   ```bash
   python3 speech_pipeline.py audio.wav --transcription-model whisper-1
   ```

3. Проверьте загрузку системы:
   ```bash
   top
   htop
   ```

### 📊 Проблемы с форматами экспорта

#### Некорректный SRT файл
**Проверки**:
1. Убедитесь в правильности кодировки:
   ```bash
   file output.srt
   ```

2. Проверьте временные метки:
   ```bash
   head -20 output.srt
   ```

#### Проблемы с ASS форматом
**Решение**: Проверьте совместимость с вашим плеером:
```bash
# Конвертация в SRT для совместимости
python3 speech_pipeline.py audio.wav --format srt
```

### 🔍 Отладка

#### Включение подробных логов
```bash
export LOG_LEVEL=DEBUG
python3 speech_pipeline.py audio.wav
```

#### Проверка промежуточных файлов
```bash
ls -la data/interim/
cat data/interim/audio_diarization.json | jq '.[0:3]'
```

#### Health check системы
```bash
python3 health_check.py --detailed
```

### 🆘 Экстренные решения

#### Полный сброс
```bash
# Удалить все промежуточные файлы
rm -rf data/interim/*
rm -rf data/processed/*

# Проверить API ключи
python3 health_check.py

# Тестовый запуск
python3 speech_pipeline.py samples/sample.wav --format txt
```

#### Переход на Replicate при проблемах
```bash
# Если стандартный метод не работает
python3 speech_pipeline.py audio.wav \
  --use-replicate \
  --format srt \
  -o backup_result.srt
```

## 📞 Получение помощи

### Проверка логов
```bash
# Основные логи
tail -100 logs/pipeline.log

# Логи ошибок
tail -50 logs/errors.log

# Поиск конкретной ошибки
grep -n "ERROR" logs/pipeline.log
```

### Создание отчета об ошибке
```bash
# Соберите информацию для отчета
echo "=== System Info ===" > debug_report.txt
python3 --version >> debug_report.txt
ffmpeg -version | head -3 >> debug_report.txt

echo "=== Environment ===" >> debug_report.txt
env | grep -E "(PYANNOTEAI|OPENAI)" >> debug_report.txt

echo "=== Last Error ===" >> debug_report.txt
tail -20 logs/errors.log >> debug_report.txt

echo "=== Health Check ===" >> debug_report.txt
python3 health_check.py >> debug_report.txt
```

### Контакты поддержки
- **Документация**: [docs/README.md](../README.md)
- **GitHub Issues**: Создайте issue с отчетом об ошибке
- **Логи**: Приложите relevant части из logs/

## ✅ Профилактика проблем

### Регулярные проверки
```bash
# Еженедельная проверка системы
python3 health_check.py --detailed

# Проверка API лимитов
python3 -c "
from pipeline.config_manager import ConfigManager
config = ConfigManager()
print('API keys configured:', bool(config.get_api_keys()))
"
```

### Мониторинг дискового пространства
```bash
# Очистка старых файлов (>7 дней)
find data/interim -name "*.wav" -mtime +7 -delete
find data/processed -name "*.json" -mtime +30 -delete
```

### Backup важных данных
```bash
# Backup voiceprints
python3 voiceprint_cli.py export voiceprints_backup.json

# Backup конфигурации
cp .env config_backup.env
cp config/*.json config_backup/
```

Следуя этому руководству, вы сможете решить большинство проблем с Speech Pipeline быстро и эффективно.
