# 📊 Лимиты и ограничения API

## 🚦 OpenAI API Limits

### Rate Limits
- **Tier 1**: 3 RPM, 200 tokens/min
- **Tier 2**: 3,500 RPM, 450,000 tokens/min
- **Tier 3**: 5,000 RPM, 600,000 tokens/min

### File Limits
- Максимальный размер: 25MB
- Поддерживаемые форматы: mp3, mp4, mpeg, mpga, m4a, wav, webm
- Максимальная длительность: автоматически

## 🔄 Replicate API Limits

### Concurrency
- По умолчанию: 1 одновременная задача
- Можно увеличить по запросу
- Timeout: 600 секунд по умолчанию

### File Limits
- Максимальный размер: 100MB
- Различные форматы аудио
- Автоматическое преобразование

## 🎭 Pyannote Limits

### Authentication
- Требуется HuggingFace токен
- Лимиты зависят от аккаунта
- Бесплатное использование ограничено

## 🛠️ Обработка лимитов

### Retry Logic
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def api_call_with_retry():
    # API call logic
    pass
```

### Error Handling
- Rate limit detection
- Automatic backoff
- Graceful degradation
- User notifications

---

*Актуальные лимиты см. в документации провайдеров*
