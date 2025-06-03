# 🔗 Интеграция с Replicate API

## 🎯 Модель для диаризации

### Используемая модель
- **incredibly-fast-whisper**: Быстрая транскрипция с диаризацией
- Встроенная Speaker Diarization
- Высокая скорость обработки
- Хорошее качество разделения спикеров

## ⚙️ Конфигурация

```python
import replicate

# Параметры модели
model_params = {
    "audio": audio_file,
    "diarization": True,
    "batch_size": 64,
    "hf_token": os.getenv("PYANNOTE_AUTH_TOKEN")
}

# Запуск обработки
output = replicate.run(
    "incredibly-fast-whisper:latest",
    input=model_params
)
```

## 💡 Преимущества

- ⚡ Быстрая обработка (0.3x времени аудио)
- 🎭 Встроенная диаризация
- 🌍 Многоязычная поддержка
- 📊 Высокое качество

## 💰 Стоимость

- Оплата за время обработки
- Примерно $0.01-0.05 за минуту аудио
- Зависит от сложности файла

---

*Документация: [Replicate Model Page](https://replicate.com/)*
