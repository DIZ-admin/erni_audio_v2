# 🎯 Руководство по Voiceprint функционалу

## 📖 Обзор

Voiceprint функционал позволяет создавать голосовые отпечатки (voiceprints) и использовать их для идентификации спикеров в аудиозаписях. Это более точная альтернатива обычной диаризации, когда вы знаете, кого ищете.

## 🏗️ Архитектура

### Компоненты:
1. **VoiceprintAgent** - создание голосовых отпечатков
2. **IdentificationAgent** - диаризация с идентификацией спикеров  
3. **VoiceprintManager** - управление базой голосовых отпечатков
4. **voiceprint_cli.py** - CLI утилита для управления

### Workflow:
```
Аудио (≤30с) → VoiceprintAgent → Base64 отпечаток → VoiceprintManager → База JSON
                                                                            ↓
Аудио + Voiceprints → IdentificationAgent → Диаризация с именами спикеров
```

## 🚀 Быстрый старт

### 1. Создание voiceprint

```bash
# Создать voiceprint из короткого аудиофайла (≤30 секунд)
python3 voiceprint_cli.py create audio_sample.wav "John Doe"

# С показом оценки стоимости
python3 voiceprint_cli.py create audio_sample.wav "John Doe" --show-cost
```

### 2. Управление voiceprints

```bash
# Показать все voiceprints
python3 voiceprint_cli.py list

# Поиск voiceprints
python3 voiceprint_cli.py search "John"

# Статистика базы
python3 voiceprint_cli.py stats

# Удалить voiceprint
python3 voiceprint_cli.py delete "John Doe"
```

### 3. Идентификация спикеров

```bash
# Использовать voiceprints для идентификации
python3 speech_pipeline.py audio.wav \
  --use-identification \
  --voiceprints "John Doe,Jane Smith" \
  --matching-threshold 0.5 \
  --format json \
  -o result.json
```

## 📋 Детальное руководство

### VoiceprintAgent

**Назначение**: Создание голосовых отпечатков из аудиофайлов

**Требования к аудио**:
- Длительность: ≤30 секунд
- Размер: ≤100MB
- Содержание: только 1 спикер
- Качество: чистая речь без шума

**Пример использования**:
```python
from pipeline.voiceprint_agent import VoiceprintAgent

agent = VoiceprintAgent(api_key="your_pyannote_key")
voiceprint_data = agent.create_voiceprint(
    audio_file=Path("speaker_sample.wav"),
    label="John Doe"
)
```

### IdentificationAgent

**Назначение**: Диаризация с идентификацией известных спикеров

**Параметры**:
- `voiceprints`: Список голосовых отпечатков
- `matching_threshold`: Порог сходства (0.0-1.0)
- `exclusive_matching`: Эксклюзивное сопоставление
- `confidence`: Включить confidence scores

**Пример использования**:
```python
from pipeline.identification_agent import IdentificationAgent

agent = IdentificationAgent(api_key="your_pyannote_key")
segments = agent.run(
    audio_file=Path("meeting.wav"),
    voiceprints=[
        {"label": "John Doe", "voiceprint": "base64_data"},
        {"label": "Jane Smith", "voiceprint": "base64_data"}
    ],
    matching_threshold=0.5
)
```

### VoiceprintManager

**Назначение**: Управление локальной базой голосовых отпечатков

**База данных**: JSON файл в `voiceprints/voiceprints.json`

**Основные методы**:
```python
from pipeline.voiceprint_manager import VoiceprintManager

manager = VoiceprintManager()

# Добавить voiceprint
vp_id = manager.add_voiceprint("John Doe", base64_data)

# Получить voiceprint
voiceprint = manager.get_voiceprint_by_label("John Doe")

# Получить для идентификации
voiceprints = manager.get_voiceprints_for_identification(["John Doe", "Jane Smith"])
```

## 🔧 CLI команды

### create
```bash
python3 voiceprint_cli.py create <audio_file> <label> [options]

Options:
  --show-cost              Показать оценку стоимости
  --skip-duration-check    Пропустить проверку длительности
```

### list
```bash
python3 voiceprint_cli.py list
```

### search
```bash
python3 voiceprint_cli.py search <query>
```

### delete
```bash
python3 voiceprint_cli.py delete <name_or_id> [--force]
```

### stats
```bash
python3 voiceprint_cli.py stats
```

### export/import
```bash
# Экспорт
python3 voiceprint_cli.py export output.json [--labels "John,Jane"]

# Импорт
python3 voiceprint_cli.py import input.json [--overwrite]
```

## 🎯 Интеграция в Speech Pipeline

### Новые опции командной строки:

```bash
--use-identification          # Использовать идентификацию вместо диаризации
--voiceprints "Name1,Name2"   # Список имен voiceprints
--matching-threshold 0.5      # Порог сходства (0.0-1.0)
--exclusive-matching          # Эксклюзивное сопоставление
```

### Пример полного workflow:

```bash
# 1. Создать voiceprints
python3 voiceprint_cli.py create john_sample.wav "John Doe"
python3 voiceprint_cli.py create jane_sample.wav "Jane Smith"

# 2. Использовать для идентификации
python3 speech_pipeline.py meeting.wav \
  --use-identification \
  --voiceprints "John Doe,Jane Smith" \
  --matching-threshold 0.4 \
  --format srt \
  -o meeting_identified.srt
```

## 💰 Стоимость

### Voiceprint создание:
- **Базовая стоимость**: ~$0.01 за voiceprint
- **Время**: 5-10 секунд
- **Лимиты**: ≤30 секунд аудио, ≤100MB

### Identification:
- **Базовая стоимость**: ~$0.05 + $0.01/MB + $0.005/voiceprint
- **Время**: зависит от длительности аудио
- **Лимиты**: ≤24 часа аудио, ≤1GB

## ⚠️ Ограничения и рекомендации

### Ограничения:
1. **Качество voiceprint**: Требует чистой речи одного спикера
2. **Длительность**: Voiceprint ≤30 секунд
3. **Совместимость**: Работает только с локальными файлами
4. **API зависимость**: Требует pyannote.ai API

### Рекомендации:
1. **Качество аудио**: Используйте чистые записи без шума
2. **Длительность voiceprint**: 10-25 секунд оптимально
3. **Порог сходства**: Начните с 0.5, понижайте при необходимости
4. **Тестирование**: Проверяйте voiceprints на известных записях

## 🔍 Troubleshooting

### Проблема: Voiceprint не создается
**Решение**: 
- Проверьте длительность файла (≤30с)
- Убедитесь в качестве аудио
- Проверьте API ключ pyannote.ai

### Проблема: Идентификация не находит спикеров
**Решение**:
- Понизьте matching-threshold (0.3-0.4)
- Проверьте качество voiceprint
- Убедитесь, что спикер присутствует в аудио

### Проблема: Низкая точность идентификации
**Решение**:
- Создайте voiceprint из более качественного образца
- Используйте exclusive-matching
- Проверьте соответствие голосов

## 📊 Сравнение методов

| Метод | Скорость | Точность | Стоимость | Сложность |
|-------|----------|----------|-----------|-----------|
| **Стандартная диаризация** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| **Replicate** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **Voiceprint идентификация** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

**Рекомендации по выбору**:
- **Replicate**: Для быстрой обработки неизвестных спикеров
- **Voiceprint**: Для точной идентификации известных спикеров
- **Стандартная**: Для бюджетных проектов

## 🎉 Заключение

Voiceprint функционал предоставляет мощный инструмент для точной идентификации известных спикеров. Хотя он требует предварительной подготовки (создание voiceprints), результат значительно превосходит обычную диаризацию по точности.
