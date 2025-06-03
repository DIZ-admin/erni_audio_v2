# 📊 Руководство по тестированию качества транскрипции (WER)

Комплексная система оценки качества транскрипции с расчетом WER (Word Error Rate) и CER (Character Error Rate) метрик для всех доступных моделей.

## 🎯 Обзор

WER тестирование позволяет:
- Сравнить качество разных моделей транскрипции
- Оценить точность распознавания речи
- Выбрать оптимальную модель для конкретных задач
- Получить детальную статистику производительности

## 🚀 Быстрый старт

### 1. Автоматическое тестирование

```bash
# Тестирование всех доступных моделей с автоматическими сценариями
python transcription_quality_test.py
```

### 2. Демонстрация с моковыми данными

```bash
# Запуск демонстрации без реальных API вызовов
python demo_wer_testing.py
```

### 3. Тестирование конкретных файлов

```bash
# Тестирование ваших аудиофайлов
python transcription_quality_test.py \
  --audio-files meeting.wav presentation.mp3 \
  --reference-texts "Эталонный текст встречи" "Эталонный текст презентации"
```

## 📋 Параметры командной строки

### transcription_quality_test.py

| Параметр | Описание | Пример |
|----------|----------|---------|
| `--audio-files` | Список аудиофайлов | `--audio-files audio1.wav audio2.mp3` |
| `--reference-texts` | Эталонные тексты | `--reference-texts "Текст 1" "Текст 2"` |
| `--output-dir` | Директория результатов | `--output-dir results/` |
| `--models` | Конкретные модели | `--models whisper-1 gpt-4o-transcribe` |
| `--language` | Код языка | `--language ru` |
| `--verbose` | Подробный вывод | `--verbose` |
| `--dry-run` | Предварительный просмотр | `--dry-run` |

### Примеры использования

```bash
# Тестирование только OpenAI моделей
python transcription_quality_test.py \
  --models whisper-1 gpt-4o-mini-transcribe gpt-4o-transcribe

# Тестирование с указанием языка
python transcription_quality_test.py \
  --audio-files german_meeting.wav \
  --language de \
  --verbose

# Предварительный просмотр плана тестирования
python transcription_quality_test.py \
  --audio-files audio.wav \
  --dry-run

# Сохранение в конкретную директорию
python transcription_quality_test.py \
  --output-dir evaluation_results/
```

## 📊 Метрики качества

### WER (Word Error Rate)
- **Определение**: Доля неправильно распознанных слов
- **Формула**: `WER = (S + D + I) / N`
  - S = Замены (Substitutions)
  - D = Удаления (Deletions)  
  - I = Вставки (Insertions)
  - N = Общее количество слов в эталоне
- **Диапазон**: 0.0 (идеально) - 1.0 (полная ошибка)

### CER (Character Error Rate)
- **Определение**: Доля неправильно распознанных символов
- **Формула**: Аналогично WER, но на уровне символов
- **Диапазон**: 0.0 (идеально) - 1.0 (полная ошибка)

### Дополнительные метрики
- **Word Accuracy**: `1 - WER` (точность слов)
- **Character Accuracy**: `1 - CER` (точность символов)
- **Processing Time**: Время обработки в секундах
- **Estimated Cost**: Приблизительная стоимость в USD

## 🎯 Интерпретация результатов

### Уровни качества WER

| WER | Качество | Описание |
|-----|----------|----------|
| 0.00 - 0.05 | Отличное | Практически идеальное распознавание |
| 0.05 - 0.15 | Хорошее | Высокое качество, подходит для большинства задач |
| 0.15 - 0.30 | Приемлемое | Удовлетворительное качество, требует проверки |
| 0.30 - 0.50 | Низкое | Много ошибок, нужна ручная корректировка |
| 0.50+ | Неприемлемое | Критически низкое качество |

### Рекомендации по выбору модели

**gpt-4o-transcribe**:
- ✅ Лучшая точность
- ✅ Отличное качество для сложного контента
- ❌ Высокая стоимость
- ❌ Медленная обработка

**replicate-whisper-diarization**:
- ✅ Отличный баланс качества и скорости
- ✅ Низкая стоимость
- ✅ Встроенная диаризация
- ❌ Требует Replicate API

**gpt-4o-mini-transcribe**:
- ✅ Хороший баланс цены и качества
- ✅ Средняя скорость
- ❌ Качество ниже чем у полной версии

**whisper-1**:
- ✅ Самая низкая стоимость
- ✅ Быстрая обработка
- ❌ Базовое качество
- ❌ Больше ошибок

## 📁 Результаты тестирования

### Структура файлов

```
data/interim/
├── wer_evaluation_results.json     # Детальные метрики в JSON
└── transcription_quality_report.md # Отчет с рекомендациями
```

### JSON структура

```json
{
  "evaluation_metadata": {
    "timestamp": "2025-06-03T...",
    "evaluator_version": "1.0.0",
    "total_models_tested": 4
  },
  "test_summary": {
    "total_scenarios": 3,
    "total_models": 4,
    "total_duration": 45.2
  },
  "scenarios": {
    "scenario_name": {
      "scenario_info": {
        "name": "scenario_name",
        "description": "Описание сценария",
        "reference_text": "Эталонный текст",
        "language": "ru"
      },
      "model_results": {
        "whisper-1": {
          "success": true,
          "quality_metrics": {
            "wer": 0.086,
            "cer": 0.045,
            "word_accuracy": 0.914,
            "char_accuracy": 0.955
          },
          "processing_time": 2.5,
          "estimated_cost": "$0.006"
        }
      }
    }
  },
  "model_comparison": {
    "whisper-1": {
      "success_rate": 1.0,
      "average_wer": 0.086,
      "average_cer": 0.045,
      "word_accuracy": 0.914,
      "char_accuracy": 0.955,
      "average_processing_time": 2.5,
      "average_cost_usd": 0.006
    }
  }
}
```

## 🔧 Настройка эталонных текстов

### Автоматический поиск

Система автоматически ищет эталонные тексты в формате:
```
data/raw/audio_file_reference.txt
```

Например, для файла `meeting.wav` создайте `meeting_reference.txt`.

### Создание качественных эталонов

1. **Точность**: Эталон должен точно соответствовать произнесенному тексту
2. **Нормализация**: Используйте стандартную пунктуацию и регистр
3. **Полнота**: Включайте все произнесенные слова
4. **Язык**: Указывайте правильный язык в параметрах

### Пример эталонного текста

```text
Добро пожаловать на встречу по обсуждению проекта. Сегодня мы рассмотрим основные вопросы повестки дня и примем важные решения. Первый пункт касается бюджетного планирования на следующий квартал.
```

## 🧪 Unit тесты

```bash
# Тесты WER калькулятора
pytest tests/test_wer_evaluator.py -v

# Интеграционные тесты
pytest tests/test_transcription_quality_integration.py -v

# Все WER тесты
pytest tests/test_*wer* -v
```

## 🚨 Устранение неполадок

### Проблема: "Нет доступных тестовых сценариев"

**Решение**:
```bash
# Укажите файлы явно
python transcription_quality_test.py \
  --audio-files your_audio.wav \
  --reference-texts "Ваш эталонный текст"
```

### Проблема: "OPENAI_API_KEY не найден"

**Решение**:
```bash
export OPENAI_API_KEY='your-key-here'
# или добавьте в .env файл
```

### Проблема: Replicate модель недоступна

**Решение**:
```bash
export REPLICATE_API_TOKEN='your-token-here'
# или тестируйте только OpenAI модели
python transcription_quality_test.py --models whisper-1 gpt-4o-transcribe
```

## 📈 Лучшие практики

1. **Используйте качественные эталоны**: Точные эталонные тексты критически важны
2. **Тестируйте на разных языках**: Качество может варьироваться по языкам
3. **Учитывайте контекст**: Разные модели лучше работают с разным контентом
4. **Регулярно тестируйте**: Качество моделей может изменяться со временем
5. **Документируйте результаты**: Сохраняйте отчеты для сравнения

## 🔗 Связанные ресурсы

- [Основное руководство README.md](../../README.md)
- [Руководство по voiceprints](VOICEPRINT_GUIDE.md)
- [Руководство по веб-хукам](WEBHOOK_GUIDE.md)
- [Планирование проекта](../../planning.md)
- [Список задач](../../tasks.md)
