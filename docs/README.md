# 📚 Документация ERNI Audio v2

> **Speech Pipeline** - Система автоматической обработки аудио с диаризацией и транскрипцией

## 🎯 Быстрый старт

### Для новых пользователей
1. **[🚀 Руководство по установке](../README.md)** - Установка и первый запуск
2. **[📊 Обзор методов обработки](./guides/METHODS_OVERVIEW.md)** - Выбор оптимального метода
3. **[💡 Примеры использования](./guides/USAGE_EXAMPLES.md)** - Практические примеры

### Для разработчиков
1. **[🏗️ Архитектура системы](./architecture/ARCHITECTURE_OVERVIEW.md)** - Обзор компонентов
2. **[🔄 Потоки данных](./architecture/DATA_FLOWS.md)** - Детальные схемы обработки
3. **[🧪 Руководство по тестированию](./development/TESTING_GUIDE.md)** - Запуск и написание тестов

---

## 📖 Структура документации

### 🏗️ `/architecture` - Архитектура и дизайн
- **[ARCHITECTURE_OVERVIEW.md](./architecture/ARCHITECTURE_OVERVIEW.md)** - Общий обзор архитектуры
- **[DATA_FLOWS.md](./architecture/DATA_FLOWS.md)** - Потоки данных и взаимодействие компонентов
- **[API_INTERFACES.md](./architecture/API_INTERFACES.md)** - Описание интерфейсов и контрактов
- **[SECURITY_DESIGN.md](./architecture/SECURITY_DESIGN.md)** - Архитектура безопасности

### 📘 `/guides` - Руководства пользователя
- **[METHODS_OVERVIEW.md](./guides/METHODS_OVERVIEW.md)** - Сравнение методов обработки
- **[VOICEPRINT_GUIDE.md](./guides/VOICEPRINT_GUIDE.md)** - Работа с голосовыми отпечатками
- **[USAGE_EXAMPLES.md](./guides/USAGE_EXAMPLES.md)** - Примеры для различных сценариев
- **[TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md)** - Решение типичных проблем

### 🔧 `/api` - API документация
- **[PYANNOTE_SETUP.md](./api/PYANNOTE_SETUP.md)** - Настройка pyannote.ai
- **[OPENAI_MODELS.md](./api/OPENAI_MODELS.md)** - Модели транскрипции OpenAI
- **[REPLICATE_API.md](./api/REPLICATE_API.md)** - Интеграция с Replicate
- **[API_LIMITS.md](./api/API_LIMITS.md)** - Лимиты и ограничения API

### 🚀 `/deployment` - Развертывание
- **[DEPLOYMENT_CHECKLIST.md](./deployment/DEPLOYMENT_CHECKLIST.md)** - Чеклист для production
- **[DOCKER_SETUP.md](./deployment/DOCKER_SETUP.md)** - Контейнеризация
- **[MONITORING_SETUP.md](./deployment/MONITORING_SETUP.md)** - Настройка мониторинга
- **[SCALING_GUIDE.md](./deployment/SCALING_GUIDE.md)** - Масштабирование

### 💻 `/development` - Для разработчиков
- **[DEVELOPMENT_SETUP.md](./development/DEVELOPMENT_SETUP.md)** - Настройка окружения
- **[TESTING_GUIDE.md](./development/TESTING_GUIDE.md)** - Тестирование
- **[CONTRIBUTING.md](./development/CONTRIBUTING.md)** - Руководство контрибьютора
- **[CODE_STANDARDS.md](./development/CODE_STANDARDS.md)** - Стандарты кода

### 📊 `/benchmarks` - Тесты производительности
- **[PERFORMANCE_TESTS.md](./benchmarks/PERFORMANCE_TESTS.md)** - Результаты тестов
- **[LARGE_FILES_TESTS.md](./benchmarks/LARGE_FILES_TESTS.md)** - Обработка больших файлов
- **[COST_ANALYSIS.md](./benchmarks/COST_ANALYSIS.md)** - Анализ стоимости

### 📝 `/releases` - История релизов
- **[CHANGELOG.md](./releases/CHANGELOG.md)** - История изменений
- **[v2.0_RELEASE_NOTES.md](./releases/v2.0_RELEASE_NOTES.md)** - Релиз v2.0
- **[v1.3_RELEASE_NOTES.md](./releases/v1.3_RELEASE_NOTES.md)** - Релиз v1.3
- **[ROADMAP_2025.md](./releases/ROADMAP_2025.md)** - План развития

---

## 🔍 Быстрый поиск по темам

### Установка и настройка
- [Системные требования](../README.md#предварительные-требования)
- [Получение API ключей](./api/PYANNOTE_SETUP.md#получение-api-ключа)
- [Переменные окружения](../README.md#настройте-переменные-окружения)

### Использование
- [Базовые команды](../README.md#базовые-команды)
- [Выбор метода обработки](./guides/METHODS_OVERVIEW.md)
- [Создание voiceprints](./guides/VOICEPRINT_GUIDE.md#создание-voiceprint)
- [Примеры для разных сценариев](./guides/USAGE_EXAMPLES.md)

### Разработка
- [Архитектура агентов](./architecture/ARCHITECTURE_OVERVIEW.md#агенты)
- [Написание тестов](./development/TESTING_GUIDE.md#написание-тестов)
- [Добавление нового агента](./development/CONTRIBUTING.md#добавление-агента)

### Проблемы и решения
- [Ошибки API](./guides/TROUBLESHOOTING.md#ошибки-api)
- [Проблемы с производительностью](./guides/TROUBLESHOOTING.md#производительность)
- [Вопросы безопасности](./architecture/SECURITY_DESIGN.md)

---

## 📈 Статус проекта

**Текущая версия**: 2.0 (Speech Pipeline)  
**Статус**: Production Ready ✅  
**Покрытие тестами**: 95%  
**Поддержка языков**: 99+  

### Ключевые метрики
- **Производительность**: 0.3x длительности аудио (Replicate)
- **Точность**: >90% транскрипция, >85% диаризация
- **Методы обработки**: 3 (Стандартный, Replicate, Voiceprint)

---

## 🤝 Поддержка

- **Issues**: [GitHub Issues](https://github.com/erni/audio_v2/issues)
- **Email**: support@erni.com
- **Документация**: Вы здесь! 😊

---

*Последнее обновление: Июнь 2025*
