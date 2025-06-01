# Руководство по веб-хукам pyannote.ai

Это руководство описывает интеграцию веб-хуков pyannote.ai в проект аудиообработки для асинхронной обработки задач.

## 📋 Содержание

- [Обзор](#обзор)
- [Настройка](#настройка)
- [Запуск webhook сервера](#запуск-webhook-сервера)
- [Асинхронная обработка](#асинхронная-обработка)
- [Верификация подписи](#верификация-подписи)
- [Обработка событий](#обработка-событий)
- [Мониторинг](#мониторинг)
- [Примеры использования](#примеры-использования)
- [Устранение неполадок](#устранение-неполадок)

## 🎯 Обзор

Веб-хуки pyannote.ai позволяют получать уведомления о завершении задач асинхронно, вместо использования polling. Это значительно улучшает производительность и снижает нагрузку на API.

### Поддерживаемые типы задач

- **Diarization**: Диаризация аудио (разделение спикеров)
- **Identify**: Идентификация спикеров через voiceprints
- **Voiceprint**: Создание голосовых отпечатков

### Преимущества веб-хуков

- ⚡ **Быстрее**: Мгновенные уведомления вместо polling
- 🔋 **Эффективнее**: Меньше API запросов
- 📊 **Надежнее**: Автоматические повторы при сбоях
- 🔒 **Безопаснее**: Верификация подписи HMAC-SHA256

## ⚙️ Настройка

### 1. Получение webhook секрета

1. Войдите в [dashboard.pyannote.ai](https://dashboard.pyannote.ai)
2. Перейдите в раздел "Webhooks"
3. Скопируйте ваш webhook секрет (формат: `whs_...`)

### 2. Конфигурация переменных окружения

Добавьте в файл `.env`:

```bash
# Webhook секрет pyannote.ai
PYANNOTEAI_WEBHOOK_SECRET=whs_95db6ebca6fc447cafbc90594601555e

# Настройки webhook сервера
WEBHOOK_SERVER_PORT=8000
WEBHOOK_SERVER_HOST=0.0.0.0
```

### 3. Установка зависимостей

```bash
pip install fastapi uvicorn
```

## 🚀 Запуск webhook сервера

### Базовый запуск

```bash
python webhook_server_cli.py
```

### Расширенные опции

```bash
# Запуск в режиме отладки
python webhook_server_cli.py --debug

# Запуск на определенном порту
python webhook_server_cli.py --port 9000

# Кастомный webhook секрет
python webhook_server_cli.py --webhook-secret "whs_your_secret"

# Кастомная директория для результатов
python webhook_server_cli.py --data-dir /path/to/results
```

### Проверка работы сервера

```bash
# Health check
curl http://localhost:8000/health

# Метрики
curl http://localhost:8000/metrics
```

## 🔄 Асинхронная обработка

### DiarizationAgent

```python
from pipeline.diarization_agent import DiarizationAgent

# Инициализация с webhook URL
agent = DiarizationAgent(
    api_key="your_pyannote_key",
    webhook_url="http://your-server.com:8000/webhook"
)

# Асинхронный запуск диаризации
job_id = agent.diarize_async("media://audio-file")
print(f"Задача запущена: {job_id}")

# Результат будет отправлен на webhook URL
```

### VoiceprintAgent

```python
from pipeline.voiceprint_agent import VoiceprintAgent
from pathlib import Path

# Инициализация с webhook URL
agent = VoiceprintAgent(
    api_key="your_pyannote_key",
    webhook_url="http://your-server.com:8000/webhook"
)

# Асинхронное создание voiceprint
job_id = agent.create_voiceprint_async(
    audio_file=Path("speaker_sample.wav"),
    label="John Doe"
)
print(f"Voiceprint задача запущена: {job_id}")
```

### IdentificationAgent

```python
from pipeline.identification_agent import IdentificationAgent
from pathlib import Path

# Инициализация с webhook URL
agent = IdentificationAgent(
    api_key="your_pyannote_key",
    webhook_url="http://your-server.com:8000/webhook"
)

# Асинхронная идентификация
voiceprints = [
    {"label": "John Doe", "voiceprint": "base64_data_1"},
    {"label": "Jane Smith", "voiceprint": "base64_data_2"}
]

job_id = agent.run_async(
    audio_file=Path("meeting.wav"),
    voiceprints=voiceprints,
    matching_threshold=0.5
)
print(f"Идентификация запущена: {job_id}")
```

## 🔒 Верификация подписи

Webhook сервер автоматически верифицирует подписи согласно документации pyannote.ai:

### Алгоритм верификации

1. Создание подписанного контента: `v0:{timestamp}:{body}`
2. Вычисление HMAC-SHA256 с webhook секретом
3. Сравнение с подписью из заголовка `X-Signature`

### Заголовки webhook запроса

```
X-Request-Timestamp: 1640995200
X-Signature: calculated_hmac_sha256_signature
X-Retry-Num: 2 (при повторах)
X-Retry-Reason: http_timeout (при повторах)
```

## 📨 Обработка событий

### Структура webhook события

```json
{
  "jobId": "123e4567-e89b-12d3-a456-426614174000",
  "status": "succeeded",
  "output": {
    "diarization": [
      {"start": 0.0, "end": 5.0, "speaker": "speaker_1"},
      {"start": 5.0, "end": 10.0, "speaker": "speaker_2"}
    ]
  }
}
```

### Регистрация обработчиков

```python
from pipeline.webhook_server import WebhookServer

server = WebhookServer()

def handle_diarization(event):
    print(f"Диаризация завершена: {event.job_id}")
    if event.status == "succeeded":
        segments = event.output.get("diarization", [])
        print(f"Найдено {len(segments)} сегментов")

def handle_voiceprint(event):
    print(f"Voiceprint создан: {event.job_id}")
    if event.status == "succeeded":
        voiceprint = event.output.get("voiceprint")
        print(f"Voiceprint готов: {len(voiceprint)} символов")

server.register_event_handler("diarization", handle_diarization)
server.register_event_handler("voiceprint", handle_voiceprint)

server.run()
```

## 📊 Мониторинг

### Метрики webhook сервера

```bash
curl http://localhost:8000/metrics
```

```json
{
  "processed_webhooks": 150,
  "failed_verifications": 2,
  "successful_events": 148,
  "verification_success_rate": 98.67
}
```

### Логирование

Webhook сервер ведет структурированные логи:

```
2024-01-15 10:30:15 - webhook_server - INFO - 📥 POST /webhook от 192.168.1.100
2024-01-15 10:30:15 - webhook_agent - INFO - ✅ Подпись веб-хука валидна для job timestamp 1640995200
2024-01-15 10:30:15 - webhook_agent - INFO - 🎯 Обрабатываю diarization webhook: test-job-123 (статус: succeeded)
2024-01-15 10:30:15 - webhook_agent - INFO - 💾 Результат сохранен: data/interim/test-job-123_diarization_20240115_103015.json
```

## 💡 Примеры использования

### Полный пример асинхронной обработки

```python
import asyncio
from pathlib import Path
from pipeline.diarization_agent import DiarizationAgent
from pipeline.webhook_server import WebhookServer

# 1. Запуск webhook сервера (в отдельном процессе)
def start_webhook_server():
    server = WebhookServer()
    server.run()

# 2. Асинхронная обработка аудио
async def process_audio_async():
    agent = DiarizationAgent(
        api_key="your_key",
        webhook_url="http://localhost:8000/webhook"
    )
    
    # Запускаем несколько задач параллельно
    jobs = []
    for audio_file in ["audio1.wav", "audio2.wav", "audio3.wav"]:
        job_id = agent.diarize_async(f"media://{audio_file}")
        jobs.append(job_id)
        print(f"Запущена задача: {job_id}")
    
    print(f"Запущено {len(jobs)} задач. Результаты будут в data/interim/")

# Запуск
asyncio.run(process_audio_async())
```

### Интеграция с существующим pipeline

```python
# Модификация speech_pipeline.py для поддержки webhook
def main_async():
    webhook_url = "http://localhost:8000/webhook"
    
    # Асинхронный запуск диаризации
    diar_agent = DiarizationAgent(
        api_key=PYANNOTE_KEY,
        webhook_url=webhook_url
    )
    
    job_id = diar_agent.diarize_async(wav_url)
    print(f"Диаризация запущена асинхронно: {job_id}")
    print("Результат будет сохранен автоматически при завершении")
```

## 🔧 Устранение неполадок

### Частые проблемы

#### 1. Ошибка верификации подписи

```
❌ Неверная подпись веб-хука
```

**Решение**: Проверьте webhook секрет в переменных окружения

#### 2. Webhook сервер недоступен

```
❌ Ошибка подключения к webhook URL
```

**Решение**: 
- Убедитесь, что сервер запущен
- Проверьте firewall и сетевые настройки
- Используйте публичный URL для production

#### 3. Отсутствуют заголовки

```
❌ Отсутствуют заголовки X-Request-Timestamp или X-Signature
```

**Решение**: Проверьте, что запросы приходят от pyannote.ai

### Отладка

```bash
# Запуск в режиме отладки
python webhook_server_cli.py --debug

# Проверка логов
tail -f logs/webhook_server.log
```

### Тестирование webhook

```bash
# Тест с curl (замените на реальные значения)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Request-Timestamp: 1640995200" \
  -H "X-Signature: your_calculated_signature" \
  -d '{"jobId": "test", "status": "succeeded", "output": {}}'
```

## 📚 Дополнительные ресурсы

- [Документация pyannote.ai webhooks](https://docs.pyannote.ai/webhooks/)
- [FastAPI документация](https://fastapi.tiangolo.com/)
- [Примеры кода в tests/test_webhook_*.py](../../tests/)

---

*Обновлено: 2024-01-15*
