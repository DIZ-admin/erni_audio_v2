# 🚀 Быстрый старт: Обработка "Schongiland 3.m4a"

**Файл**: `data/raw/Schongiland 3.m4a`  
**Размер**: 46.6 MB | **Длительность**: 92 минуты | **Формат**: M4A (AAC)

---

## ⚡ Рекомендуемая команда (быстрая обработка)

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

> **Автоматическое определение спикеров** - система сама определит количество участников

**Ожидаемое время**: 25-30 минут  
**Стоимость**: ~$1.50-2.00

---

## 🎯 Альтернативные варианты

### Максимальная точность (медленнее)
```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method standard \
  --transcription-model gpt-4o-transcribe \
  --language de \
  --format json \
  --output data/processed/schongiland_3_premium
```
**Время**: 50-65 минут | **Стоимость**: ~$2.50-3.00

### С именованными участниками (если есть voiceprints)
```bash
python3 speech_pipeline.py "data/raw/Schongiland 3.m4a" \
  --method standard \
  --use-identification \
  --voiceprints "Hans Mueller,Anna Schmidt,Peter Weber" \
  --format json \
  --output data/processed/schongiland_3_identified
```

---

## 📊 Ожидаемые результаты

- **Сегментов**: ~800-1200
- **Спикеров**: 2-5 участников  
- **Точность**: 90-95% (немецкий язык)
- **Форматы**: JSON, SRT, ASS, TXT

---

## 🔍 Мониторинг выполнения

```bash
# Отслеживание прогресса
tail -f logs/speech_pipeline_$(date +%Y-%m-%d).log

# Проверка результатов
ls -la data/processed/schongiland_3_meeting.*
```

---

**Полный план**: [MEETING_PROCESSING_PLAN.md](MEETING_PROCESSING_PLAN.md)
