# 📡 API интерфейсы и контракты

> Описание всех API интерфейсов системы ERNI Audio v2

## 🎯 Основные интерфейсы

### 1. Speech Pipeline API
```python
class SpeechPipeline:
    def process_audio(
        self, 
        audio_path: str, 
        method: str = "standard",
        voiceprint_path: Optional[str] = None
    ) -> ProcessingResult
```

### 2. Webhook Interface
```python
class WebhookHandler:
    def send_completion_webhook(
        self,
        processing_id: str,
        status: str,
        results: Dict[str, Any]
    ) -> bool
```

### 3. Agent Interface
```python
class BaseAgent:
    def process(self, audio_path: str) -> AgentResult
    def validate_input(self, audio_path: str) -> bool
    def get_capabilities(self) -> Dict[str, Any]
```

## 🔗 API Endpoints

### Processing Endpoints
- `POST /process` - Запуск обработки
- `GET /status/{id}` - Статус обработки
- `GET /results/{id}` - Результаты обработки

### Management Endpoints
- `GET /health` - Проверка состояния
- `POST /voiceprint` - Загрузка voiceprint
- `GET /methods` - Доступные методы

---

*Подробная документация API доступна в папке `/api`*
