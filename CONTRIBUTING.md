# Contributing to Speech Pipeline

Спасибо за интерес к улучшению Speech Pipeline! 🎉

## 🚀 Как внести вклад

### 1. Подготовка окружения

```bash
# Fork и клонирование
git clone https://github.com/your-username/speech-pipeline.git
cd speech-pipeline

# Установка зависимостей
pip install -r requirements.txt

# Настройка окружения
cp .env.example .env
# Добавьте ваши API ключи в .env
```

### 2. Создание feature branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Разработка

- Следуйте существующему стилю кода
- Добавляйте тесты для новой функциональности
- Обновляйте документацию при необходимости
- Используйте осмысленные commit сообщения

### 4. Тестирование

```bash
# Запуск всех тестов
pytest

# Проверка health check
python health_check.py

# Тестирование с реальными файлами
python speech_pipeline.py test_audio.wav --format srt -o test.srt
```

### 5. Отправка Pull Request

```bash
git add .
git commit -m "feat: add amazing feature"
git push origin feature/your-feature-name
```

Затем создайте Pull Request через GitHub.

## 📋 Стандарты кода

### Python Style Guide

- Следуйте PEP 8
- Используйте type hints где возможно
- Максимальная длина строки: 88 символов
- Используйте docstrings для функций и классов

### Commit Messages

Используйте conventional commits:

```
feat: add new feature
fix: fix bug
docs: update documentation
test: add tests
refactor: refactor code
style: formatting changes
```

### Структура тестов

```python
def test_function_name():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_output
```

## 🐛 Сообщение об ошибках

При создании issue включите:

1. **Описание проблемы**
2. **Шаги для воспроизведения**
3. **Ожидаемое поведение**
4. **Фактическое поведение**
5. **Версия Python и ОС**
6. **Логи (без API ключей!)**

## 💡 Предложения улучшений

Мы приветствуем предложения по:

- Новым форматам экспорта
- Улучшению производительности
- Дополнительным языкам
- Улучшению UX
- Оптимизации архитектуры

## 🔒 Безопасность

- **Никогда не коммитьте API ключи**
- **Не загружайте конфиденциальные аудиофайлы**
- **Используйте .env для секретов**
- **Проверяйте .gitignore перед commit**

## 📚 Ресурсы

- [Python Style Guide](https://pep8.org/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Git Best Practices](https://git-scm.com/book)
- [Conventional Commits](https://www.conventionalcommits.org/)

## ❓ Вопросы

Если у вас есть вопросы, создайте issue с тегом `question` или свяжитесь с мейнтейнерами.

---

**Спасибо за ваш вклад! 🙏**
