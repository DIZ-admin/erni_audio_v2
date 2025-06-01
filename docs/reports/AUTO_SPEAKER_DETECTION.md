# 🎯 Автоматическое определение спикеров для "Schongiland 3.m4a"

**Проблема**: Неизвестно количество участников заседания  
**Решение**: Автоматическое определение через алгоритмы системы

---

## 🚀 РЕКОМЕНДУЕМАЯ КОМАНДА (обновленная)

```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method replicate \
  --language de \
  --format json \
  --format srt \
  --format ass \
  --output data/processed/schongiland_3_meeting \
  --save-interim \
  --verbose
```

### ✅ Что изменилось
- **Убрал** `--num-speakers 4` 
- **Добавил** автоматическое определение
- **Система сама** найдет оптимальное количество спикеров

---

## 🔍 Как работает автоматическое определение

### 🎯 Replicate метод
- **Алгоритм**: Whisper-diarization автоматически анализирует аудио
- **Диапазон**: Обычно определяет от 2 до 10+ спикеров
- **Точность**: 85-90% правильного разделения
- **Время**: Не увеличивает время обработки

### 📊 Процесс определения
1. **Анализ голосовых характеристик** (тембр, частота, интонация)
2. **Кластеризация похожих сегментов** речи
3. **Оптимизация количества кластеров** (спикеров)
4. **Валидация результатов** по длительности сегментов

---

## 📈 Ожидаемые результаты

### 🎯 Для заседания 92 минуты
- **Вероятное количество**: 2-6 спикеров
- **Типичные роли**: Председатель, секретарь, участники
- **Распределение времени**: Неравномерное (председатель говорит больше)

### 📊 Качество определения
- **Основные спикеры**: 90-95% точность
- **Редкие реплики**: 70-80% точность  
- **Перекрывающаяся речь**: Может объединяться в один сегмент

---

## 🔧 Альтернативные варианты

### Если автоопределение неточное

#### 1. Ограничить диапазон спикеров
```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method replicate \
  --language de \
  --num-speakers 3 \
  --format json \
  --output data/processed/schongiland_3_conservative
```

#### 2. Увеличить чувствительность
```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method replicate \
  --language de \
  --num-speakers 6 \
  --format json \
  --output data/processed/schongiland_3_detailed
```

#### 3. Стандартный метод с автоопределением
```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method standard \
  --language de \
  --format json \
  --output data/processed/schongiland_3_standard_auto
```

---

## 📊 Анализ результатов

### После обработки проверьте
```bash
# Количество найденных спикеров
python3 -c "
import json
with open('data/processed/schongiland_3_meeting.json') as f:
    data = json.load(f)
speakers = set(seg['speaker'] for seg in data)
print(f'Найдено спикеров: {len(speakers)}')
print(f'Список: {sorted(speakers)}')
"

# Распределение времени по спикерам
python3 -c "
import json
from collections import defaultdict
with open('data/processed/schongiland_3_meeting.json') as f:
    data = json.load(f)

speaker_time = defaultdict(float)
for seg in data:
    duration = seg['end'] - seg['start']
    speaker_time[seg['speaker']] += duration

print('Время выступления по спикерам:')
for speaker, time in sorted(speaker_time.items()):
    print(f'{speaker}: {time/60:.1f} минут ({time/sum(speaker_time.values())*100:.1f}%)')
"
```

### Признаки хорошего разделения
- ✅ **2-6 спикеров** для заседания
- ✅ **Неравномерное распределение** времени
- ✅ **Логичные переходы** между спикерами
- ✅ **Минимум коротких сегментов** (<2 секунд)

### Признаки проблем
- ❌ **Слишком много спикеров** (>8) - переразделение
- ❌ **Слишком мало** (1-2) - недоразделение  
- ❌ **Много коротких сегментов** - шум в алгоритме
- ❌ **Частые переключения** - ложные срабатывания

---

## 🔄 План коррекции

### Если результат неудовлетворительный

#### Шаг 1: Анализ проблемы
```bash
# Посмотреть статистику сегментов
python3 -c "
import json
with open('data/processed/schongiland_3_meeting.json') as f:
    data = json.load(f)

durations = [seg['end'] - seg['start'] for seg in data]
print(f'Средняя длительность сегмента: {sum(durations)/len(durations):.1f}с')
print(f'Коротких сегментов (<2с): {sum(1 for d in durations if d < 2)}')
print(f'Длинных сегментов (>30с): {sum(1 for d in durations if d > 30)}')
"
```

#### Шаг 2: Коррекция параметров
```bash
# Если слишком много спикеров - ограничить
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method replicate \
  --language de \
  --num-speakers 4 \
  --format json \
  --output data/processed/schongiland_3_corrected

# Если слишком мало - увеличить чувствительность  
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method standard \
  --language de \
  --format json \
  --output data/processed/schongiland_3_sensitive
```

---

## 🎯 Рекомендации

### ✅ Начните с автоопределения
- **Простота**: Не нужно угадывать количество
- **Скорость**: Быстрый результат для оценки
- **Гибкость**: Можно скорректировать при необходимости

### 🔄 Итеративный подход
1. **Первый запуск**: Автоопределение
2. **Анализ результата**: Проверка качества
3. **Коррекция**: При необходимости с фиксированным числом
4. **Финальная обработка**: Лучший результат

### 📊 Критерии успеха
- **Логичное количество** участников (2-6 для заседания)
- **Четкие переходы** между спикерами
- **Минимум артефактов** (коротких сегментов)
- **Соответствие ожиданиям** по содержанию

---

## 🚀 ГОТОВ К ЗАПУСКУ!

**Используйте обновленную команду без указания количества спикеров:**

```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method replicate \
  --language de \
  --format json \
  --format srt \
  --format ass \
  --output data/processed/schongiland_3_meeting \
  --save-interim \
  --verbose
```

**Система автоматически определит оптимальное количество участников заседания!** 🎯✨
