# 🤖 Модели транскрипции OpenAI

## 📋 Доступные модели

### Whisper Models
- **whisper-1**: Основная модель для транскрипции
- Поддержка 99+ языков
- Высокое качество транскрипции
- Встроенная обработка шума

## 🔧 Настройка

### API Configuration
```python
openai.api_key = os.getenv("OPENAI_API_KEY")

# Параметры транскрипции
transcription_params = {
    "model": "whisper-1",
    "language": "auto",  # или конкретный язык
    "temperature": 0,
    "response_format": "json"
}
```

## 💰 Стоимость

- **Whisper API**: $0.006 per minute
- Минимальная единица: 1 секунда
- Максимальный размер файла: 25MB

## 🚀 Оптимизация

### Рекомендации:
- Предварительная обработка аудио
- Оптимальный битрейт: 16kHz, 16-bit
- Удаление тишины
- Сегментирование длинных файлов

---

*См. также: [OpenAI API Documentation](https://platform.openai.com/docs/guides/speech-to-text)*
