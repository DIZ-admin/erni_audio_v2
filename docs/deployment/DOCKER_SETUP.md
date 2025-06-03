# 🐳 Настройка Docker

## 📦 Dockerfile

Проект уже включает готовый Dockerfile в корне проекта.

### Сборка образа
```bash
# Сборка образа
docker build -t erni-audio-v2 .

# Запуск контейнера
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e PYANNOTE_AUTH_TOKEN=your_token \
  -e REPLICATE_API_TOKEN=your_token \
  erni-audio-v2
```

## 🔧 Docker Compose

### docker-compose.yml
```yaml
version: '3.8'
services:
  erni-audio:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PYANNOTE_AUTH_TOKEN=${PYANNOTE_AUTH_TOKEN}
      - REPLICATE_API_TOKEN=${REPLICATE_API_TOKEN}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

### Запуск
```bash
# Запуск в фоне
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## 🌐 Production Deployment

### Рекомендации:
- Использовать multi-stage build
- Оптимизировать размер образа
- Настроить health checks
- Использовать secrets для API ключей

---

*См. также: [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)*
