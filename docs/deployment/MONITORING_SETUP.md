# 📊 Настройка мониторинга

## 🔍 Health Check Endpoint

Система включает встроенный health check:
```bash
# Проверка состояния
curl http://localhost:8000/health

# Ответ
{
  "status": "healthy",
  "timestamp": "2025-06-03T10:00:00Z",
  "services": {
    "openai": "connected",
    "replicate": "connected",
    "pyannote": "connected"
  }
}
```

## 📈 Логирование

### Структура логов
```
logs/
├── app.log          # Основные события
├── error.log        # Ошибки
├── performance.log  # Метрики производительности
└── webhook.log      # Webhook активность
```

### Уровни логирования
- **INFO**: Обычные операции
- **WARNING**: Предупреждения
- **ERROR**: Ошибки
- **DEBUG**: Отладочная информация

## 🚨 Алерты

### Критические метрики:
- API response time > 30s
- Error rate > 5%
- Disk space < 10%
- Memory usage > 90%

### Настройка уведомлений:
```python
# Webhook для алертов
ALERT_WEBHOOK_URL = "your_monitoring_webhook"
```

## 📊 Метрики

### Ключевые показатели:
- Время обработки файлов
- Успешность API вызовов
- Количество обработанных файлов
- Использование ресурсов

---

*Для production рекомендуется интеграция с Prometheus/Grafana*
