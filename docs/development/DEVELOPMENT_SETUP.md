# 🛠️ Настройка окружения разработки

## 📋 Предварительные требования

### Системные требования
- Python 3.11+
- Git
- 4GB+ RAM
- 10GB+ свободного места

### Установка зависимостей
```bash
# Клонирование репозитория
git clone <repository-url>
cd erni_audio_v2

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Установка зависимостей
pip install -r requirements.txt
```

## 🔑 Настройка API ключей

### Создание .env файла
```bash
cp .env.example .env
```

### Заполнение переменных
```bash
# Обязательные
PYANNOTE_AUTH_TOKEN=your_token_here
OPENAI_API_KEY=your_openai_key
REPLICATE_API_TOKEN=your_replicate_token

# Опциональные
WEBHOOK_URL=your_webhook_url
WEBHOOK_SECRET=your_secret
```

## 🧪 Проверка установки

```bash
# Проверка health check
python health_check.py

# Запуск базового теста
python -m pytest tests/test_basic.py -v
```

## 🔧 IDE настройка

### VS Code
Рекомендуемые расширения:
- Python
- Python Docstring Generator
- GitLens
- Markdown All in One

### PyCharm
- Настройка интерпретатора
- Включение type checking
- Настройка code style

---

*Далее: [Руководство по тестированию](TESTING_GUIDE.md)*
