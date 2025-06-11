# 🔄 Checkpoint-based Resumption System Guide

## 📋 Обзор

Checkpoint-based resumption система позволяет автоматически возобновлять обработку аудио с любого этапа пайплайна после сбоя или прерывания. Система автоматически сохраняет промежуточные результаты и может продолжить работу с последнего успешно завершенного этапа.

## 🎯 Основные возможности

### ✅ Автоматическое сохранение состояния
- Checkpoint создается после каждого успешного этапа
- Сохраняются промежуточные файлы и метаданные
- Отслеживается прогресс выполнения пайплайна

### 🔄 Умное возобновление
- Автоматическое определение точки возобновления
- Валидация промежуточных файлов
- Пропуск уже выполненных этапов

### 🛠️ Управление checkpoint'ами
- CLI утилита для просмотра и управления
- Очистка устаревших checkpoint'ов
- Экспорт/импорт состояния пайплайна

## 🏗️ Архитектура

### Компоненты системы

1. **CheckpointManager** - основной класс управления
2. **PipelineState** - состояние пайплайна
3. **CheckpointData** - данные отдельного checkpoint'а
4. **PipelineStage** - этапы обработки

### Этапы пайплайна

```
AUDIO_CONVERSION → DIARIZATION → TRANSCRIPTION → MERGE → EXPORT
```

Альтернативные пайплайны:
- **Replicate**: REPLICATE → EXPORT
- **Identification**: IDENTIFICATION → EXPORT

## 🚀 Использование

### Основные команды

```bash
# Обычный запуск (автоматически создает checkpoint'ы)
python speech_pipeline.py audio.wav

# При прерывании - автоматическое возобновление
python speech_pipeline.py audio.wav
# → 🔄 Найден checkpoint: transcription_done
# → Возобновление с этапа объединения

# Принудительный перезапуск (игнорирует checkpoint'ы)
python speech_pipeline.py audio.wav --force-restart

# Список checkpoint'ов для файла
python speech_pipeline.py audio.wav --list-checkpoints

# Очистка старых checkpoint'ов
python speech_pipeline.py --cleanup-checkpoints
```

### CLI утилита checkpoint'ов

```bash
# Список всех checkpoint'ов
python pipeline/checkpoint_cli.py list

# Детальная информация
python pipeline/checkpoint_cli.py list --detailed

# Показать конкретный checkpoint
python pipeline/checkpoint_cli.py show <pipeline_id>

# Валидировать checkpoint
python pipeline/checkpoint_cli.py validate <pipeline_id>

# Очистка checkpoint'ов
python pipeline/checkpoint_cli.py cleanup --older-than 24

# Экспорт checkpoint'а
python pipeline/checkpoint_cli.py export <pipeline_id> backup.json
```

## 📁 Структура данных

### Checkpoint файлы

Checkpoint'ы сохраняются в директории `data/checkpoints/`:

```
data/checkpoints/
├── audio_file_123456_state.json    # Состояние пайплайна
└── ...
```

### Формат checkpoint'а

```json
{
  "input_file": "audio.wav",
  "pipeline_id": "audio_123456",
  "created_at": "2025-01-15T10:30:00",
  "last_updated": "2025-01-15T10:35:00",
  "completed_stages": ["audio_conversion", "diarization"],
  "current_stage": "transcription",
  "failed_stage": null,
  "checkpoints": [
    {
      "stage": "audio_conversion",
      "timestamp": "2025-01-15T10:30:00",
      "input_file": "audio.wav",
      "output_file": "data/interim/audio_converted.wav",
      "metadata": {
        "file_size_mb": 15.2,
        "wav_url": "https://..."
      },
      "success": true,
      "error_message": null
    }
  ],
  "metadata": {}
}
```

## 🔧 Конфигурация

### Настройки checkpoint'ов

- **Директория**: `data/checkpoints/` (создается автоматически)
- **Время жизни**: 7 дней по умолчанию
- **Валидация**: Автоматическая проверка целостности файлов

### Поддерживаемые форматы

- **JSON файлы**: Полная валидация структуры
- **Аудио файлы**: Проверка существования и размера
- **Другие файлы**: Проверка существования

## 🛡️ Обработка ошибок

### Типы ошибок

1. **Ошибки этапов** - сохраняются в checkpoint'е с описанием
2. **Поврежденные файлы** - автоматическое обнаружение и перезапуск
3. **Отсутствующие файлы** - валидация и уведомления

### Стратегии восстановления

- **Автоматическое**: Возобновление с последнего валидного этапа
- **Ручное**: Принудительный перезапуск с `--force-restart`
- **Частичное**: Очистка поврежденных checkpoint'ов

## 📊 Мониторинг

### Статусы пайплайна

- **not_started** - пайплайн не запускался
- **in_progress** - выполняется
- **completed** - успешно завершен
- **failed** - завершен с ошибкой

### Метрики

- Количество checkpoint'ов (успешных/неудачных)
- Время создания и обновления
- Размер промежуточных файлов
- Статистика этапов

## 🔍 Диагностика

### Проверка состояния

```bash
# Статус конкретного файла
python speech_pipeline.py audio.wav --list-checkpoints

# Валидация checkpoint'а
python pipeline/checkpoint_cli.py validate <pipeline_id>

# Детальная информация
python pipeline/checkpoint_cli.py show <pipeline_id>
```

### Решение проблем

1. **Checkpoint не найден**
   - Проверьте путь к файлу
   - Убедитесь, что пайплайн запускался ранее

2. **Поврежденные файлы**
   - Используйте `--force-restart`
   - Очистите checkpoint'ы: `cleanup --invalid`

3. **Старые checkpoint'ы**
   - Регулярная очистка: `cleanup --older-than 48`

## 🧪 Тестирование

### Запуск тестов

```bash
# Базовые тесты checkpoint системы
python test_checkpoint_simple.py

# Полные тесты (требует зависимости)
python -m pytest tests/test_checkpoint_system.py -v
```

### Тестовые сценарии

- Создание и загрузка checkpoint'ов
- Определение точки возобновления
- Валидация файлов
- Очистка устаревших данных
- CLI операции

## 📈 Производительность

### Преимущества

- **Экономия времени**: Пропуск выполненных этапов
- **Экономия API вызовов**: Повторное использование результатов
- **Надежность**: Устойчивость к сбоям

### Overhead

- **Дисковое пространство**: ~10-20% от размера аудио
- **Время сохранения**: <1 секунды на checkpoint
- **Память**: Минимальное влияние

## 🔮 Планы развития

### Ближайшие улучшения

- Сжатие checkpoint'ов
- Удаленное хранение состояния
- Параллельная обработка с checkpoint'ами
- Web интерфейс для управления

### Долгосрочные цели

- Распределенные checkpoint'ы
- Версионирование состояния
- Автоматическое восстановление
- Интеграция с CI/CD

---

*Документ обновлен: 2025-01-15*  
*Версия checkpoint системы: 1.0*
