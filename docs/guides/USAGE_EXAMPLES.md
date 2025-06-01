  python3 voiceprint_cli.py create "${participant// /_}_sample.wav" "$participant"
done

# Обработка фокус-группы
python3 speech_pipeline.py focus_group.wav \
  --use-identification \
  --voiceprints "Alice Brown,Charlie Davis,Eva Garcia" \
  --format ass \
  -o focus_group_styled.ass
```

## 🎵 Медиа и развлечения

### Обработка подкаста с несколькими ведущими
```bash
# Replicate для быстрой обработки медиа-контента
python3 speech_pipeline.py podcast_multi_host.mp3 \
  --use-replicate \
  --replicate-speakers 3 \
  --format srt \
  -o podcast_episode_12.srt
```

### Интервью знаменитости
```bash
# Создать voiceprint знаменитости из предыдущих интервью
python3 voiceprint_cli.py create celebrity_sample.wav "Celebrity Name"

# Обработать новое интервью
python3 speech_pipeline.py new_interview.wav \
  --use-identification \
  --voiceprints "Celebrity Name" \
  --format json \
  -o celebrity_interview.json
```

## 🔬 Исследовательские задачи

### Анализ групповой дискуссии
```bash
# Детальный анализ с метаданными
python3 speech_pipeline.py group_discussion.wav \
  --format json \
  -o research_data.json

# Извлечение статистики
python3 -c "
import json
with open('research_data.json') as f:
    data = json.load(f)
    
speakers = {}
for segment in data['segments']:
    speaker = segment['speaker']
    speakers[speaker] = speakers.get(speaker, 0) + (segment['end'] - segment['start'])

print('Время говорения по спикерам:')
for speaker, time in speakers.items():
    print(f'{speaker}: {time:.1f} секунд')
"
```

### Многоязычное исследование
```bash
# Обработка разных языков
for lang in "en" "de" "fr" "es"; do
  python3 speech_pipeline.py "interview_${lang}.wav" \
    --language "$lang" \
    --format json \
    -o "results_${lang}.json"
done
```

## 🏥 Медицинские сценарии

### Консультация врача с пациентом
```bash
# Создать voiceprints медперсонала
python3 voiceprint_cli.py create dr_smith_sample.wav "Dr. Smith"
python3 voiceprint_cli.py create nurse_jones_sample.wav "Nurse Jones"

# Обработать консультацию
python3 speech_pipeline.py consultation.wav \
  --use-identification \
  --voiceprints "Dr. Smith,Nurse Jones" \
  --format json \
  -o medical_consultation.json
```

## 🎬 Производство контента

### Субтитры для видео
```bash
# Создание субтитров для YouTube
python3 speech_pipeline.py video_content.mp4 \
  --use-replicate \
  --format srt \
  -o youtube_subtitles.srt

# ASS субтитры с оформлением для профессионального видео
python3 speech_pipeline.py professional_video.wav \
  --format ass \
  -o styled_subtitles.ass
```

### Обработка интервью для документального фильма
```bash
# Высококачественная транскрипция для монтажа
python3 speech_pipeline.py documentary_interview.wav \
  --transcription-model gpt-4o-transcribe \
  --format json \
  -o documentary_source.json
```

## 🔄 Batch обработка

### Обработка множества файлов
```bash
#!/bin/bash
# Скрипт для массовой обработки

for file in recordings/*.wav; do
  basename=$(basename "$file" .wav)
  echo "Обрабатываю: $file"
  
  python3 speech_pipeline.py "$file" \
    --use-replicate \
    --format srt \
    -o "transcripts/${basename}.srt"
    
  echo "Завершено: ${basename}.srt"
done
```

### Создание voiceprints для команды
```bash
#!/bin/bash
# Массовое создание voiceprints

declare -A team_samples=(
  ["John Doe"]="samples/john.wav"
  ["Jane Smith"]="samples/jane.wav"
  ["Bob Wilson"]="samples/bob.wav"
  ["Alice Brown"]="samples/alice.wav"
)

for name in "${!team_samples[@]}"; do
  sample="${team_samples[$name]}"
  echo "Создаю voiceprint для: $name"
  python3 voiceprint_cli.py create "$sample" "$name"
done

echo "Voiceprints созданы для всей команды"
python3 voiceprint_cli.py stats
```

## 🔧 Отладка и тестирование

### Тестирование качества voiceprints
```bash
# Создать тестовый voiceprint
python3 voiceprint_cli.py create test_sample.wav "Test Speaker"

# Протестировать на известной записи
python3 speech_pipeline.py test_audio.wav \
  --use-identification \
  --voiceprints "Test Speaker" \
  --matching-threshold 0.3 \
  --format json \
  -o test_results.json

# Проанализировать результаты
python3 -c "
import json
with open('test_results.json') as f:
    data = json.load(f)
    
matches = [s for s in data['segments'] if s.get('match') == 'Test Speaker']
print(f'Найдено совпадений: {len(matches)}')
if matches:
    avg_confidence = sum(s['confidence'] for s in matches) / len(matches)
    print(f'Средний confidence: {avg_confidence:.3f}')
"
```

### Сравнение методов обработки
```bash
# Тестовый файл
TEST_FILE="comparison_test.wav"

echo "=== Тестирование разных методов ==="

# Стандартный метод
echo "1. Стандартный метод..."
time python3 speech_pipeline.py "$TEST_FILE" \
  --format json -o "standard_result.json"

# Replicate метод  
echo "2. Replicate метод..."
time python3 speech_pipeline.py "$TEST_FILE" \
  --use-replicate --format json -o "replicate_result.json"

# Voiceprint метод (если есть voiceprints)
if python3 voiceprint_cli.py list | grep -q "Test Speaker"; then
  echo "3. Voiceprint метод..."
  time python3 speech_pipeline.py "$TEST_FILE" \
    --use-identification --voiceprints "Test Speaker" \
    --format json -o "voiceprint_result.json"
fi

echo "=== Сравнение завершено ==="
```

## 🎯 Специализированные кейсы

### Телефонные переговоры
```bash
# Обработка телефонного звонка (обычно 2 спикера)
python3 speech_pipeline.py phone_call.wav \
  --use-replicate \
  --replicate-speakers 2 \
  --format srt \
  -o phone_transcript.srt
```

### Вебинар с Q&A
```bash
# Создать voiceprint ведущего
python3 voiceprint_cli.py create host_sample.wav "Webinar Host"

# Обработать вебинар
python3 speech_pipeline.py webinar.wav \
  --use-identification \
  --voiceprints "Webinar Host" \
  --format json \
  -o webinar_with_host.json
```

### Радиошоу
```bash
# Быстрая обработка радиопрограммы
python3 speech_pipeline.py radio_show.mp3 \
  --use-replicate \
  --replicate-speakers 4 \
  --format txt \
  -o radio_transcript.txt
```

## 🏆 Лучшие практики

### Для максимального качества
```bash
# Оптимальные настройки для критичных задач
python3 speech_pipeline.py important_meeting.wav \
  --transcription-model gpt-4o-transcribe \
  --language auto \
  --format json \
  -o high_quality_result.json
```

### Для экономии средств
```bash
# Экономичный режим
python3 speech_pipeline.py budget_audio.wav \
  --use-replicate \
  --format txt \
  -o budget_transcript.txt
```

### Для персонализации
```bash
# Максимально персонализированный результат
python3 speech_pipeline.py team_meeting.wav \
  --use-identification \
  --voiceprints "CEO,CTO,CFO,VP Sales,VP Marketing" \
  --matching-threshold 0.4 \
  --format ass \
  -o executive_meeting.ass
```

## 📊 Мониторинг и отчетность

### Сбор статистики обработки
```bash
# Создать отчет о voiceprints
python3 voiceprint_cli.py stats > voiceprint_report.txt

# Анализ результатов
python3 -c "
import json, glob

total_segments = 0
total_duration = 0

for file in glob.glob('*.json'):
    try:
        with open(file) as f:
            data = json.load(f)
            if 'segments' in data:
                segments = data['segments']
                total_segments += len(segments)
                if segments:
                    total_duration += segments[-1]['end']
    except:
        continue

print(f'Общая статистика:')
print(f'Файлов обработано: {len(glob.glob(\"*.json\"))}')
print(f'Сегментов создано: {total_segments}')
print(f'Общая длительность: {total_duration/60:.1f} минут')
"
```

## 🎉 Заключение

Эти примеры покрывают основные сценарии использования Speech Pipeline. Выбирайте подходящий метод в зависимости от ваших потребностей:

- **Скорость** → Replicate
- **Качество** → Стандартный с gpt-4o-transcribe  
- **Персонализация** → Voiceprint идентификация

Экспериментируйте с разными параметрами для достижения оптимальных результатов в ваших конкретных задачах.
