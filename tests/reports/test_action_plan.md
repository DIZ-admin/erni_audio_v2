# План действий по улучшению тестов Erni_audio_v2

**Дата создания:** 2024-12-19  
**Приоритет:** Высокий  
**Ответственный:** Команда разработки  

## 🎯 Цель
Достичь 100% успешности тестов и улучшить общую стабильность тестовой системы.

## 📊 Текущее состояние
- ✅ **Пройдено:** 213 тестов (95.1%)
- ⏭️ **Пропущено:** 10 тестов (4.5%)
- ❌ **Провалено:** 1 тест (0.4%)
- ⚠️ **Предупреждения:** 8

## 🚨 Критические задачи (Приоритет 1)

### 1. Исправить провалившийся webhook тест
**Файл:** `tests/test_webhook_integration.py:308`  
**Проблема:** 401 Unauthorized от pyannote.ai API  
**Срок:** 1 день  

**Действия:**
```python
# Добавить в начало теста
@pytest.fixture
def valid_api_key():
    api_key = os.getenv('PYANNOTE_API_KEY')
    if not api_key or api_key == "test_key":
        pytest.skip("Требуется валидный PYANNOTE_API_KEY")
    return api_key

# Или использовать mock для внешних API
@patch('requests.get')
def test_webhook_payload_includes_webhook_url(self, mock_get):
    mock_get.return_value.json.return_value = {"status": "completed"}
    # ... остальной код теста
```

### 2. Зарегистрировать pytest маркеры
**Файл:** `tests/pytest.ini`  
**Проблема:** Unknown pytest marks  
**Срок:** 30 минут  

**Действия:**
```ini
# Добавить в pytest.ini
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')
    slow: marks tests as slow running (deselect with '-m "not slow"')
```

## 📋 Важные задачи (Приоритет 2)

### 3. Добавить тестовые аудиофайлы
**Проблема:** 5 тестов пропущены из-за отсутствия аудиоданных  
**Срок:** 2 дня  

**Действия:**
1. Создать директорию `tests/assets/audio/`
2. Добавить короткие тестовые файлы (5-10 сек):
   - `test_russian_speech.wav` - русская речь
   - `test_english_speech.wav` - английская речь
   - `test_multi_speaker.wav` - несколько говорящих
   - `test_noisy_audio.wav` - с фоновым шумом
3. Обновить пропущенные тесты для использования этих файлов

### 4. Улучшить обработку API ключей
**Проблема:** 2 теста пропущены из-за отсутствия API ключей  
**Срок:** 1 день  

**Действия:**
```python
# Создать фикстуру для проверки API ключей
@pytest.fixture
def check_api_keys():
    required_keys = ['PYANNOTE_API_KEY', 'OPENAI_API_KEY', 'REPLICATE_API_TOKEN']
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        pytest.skip(f"Отсутствуют API ключи: {', '.join(missing_keys)}")
```

## 🔧 Технические улучшения (Приоритет 3)

### 5. Исправить предупреждения
**Срок:** 1 день  

**Действия:**
1. **TestScenario warning:**
   ```python
   # Убрать __init__ из TestScenario или переименовать класс
   class TranscriptionTestScenario:  # вместо TestScenario
   ```

2. **Return value warning:**
   ```python
   # Заменить return на assert в тестах
   def test_error_handling_and_recovery(self):
       result = self._test_scenarios()
       assert result['all_errors_handled'] is True
       # вместо return result
   ```

3. **Async warning:**
   ```python
   # Правильно обработать async mock
   @patch('pipeline.webhook_agent.WebhookAgent.process_webhook_event')
   async def test_webhook_endpoint_background_processing(self, mock_process):
       await mock_process.return_value
   ```

### 6. Оптимизировать время выполнения
**Текущее время:** 1:26:48  
**Цель:** <60 минут  
**Срок:** 3 дня  

**Действия:**
1. Распараллелить медленные тесты:
   ```bash
   pytest -n auto  # требует pytest-xdist
   ```

2. Оптимизировать тяжелые тесты:
   - Уменьшить размер тестовых данных
   - Использовать более эффективные mock-объекты
   - Кэшировать результаты инициализации

## 📈 Мониторинг и отчетность (Приоритет 4)

### 7. Настроить автоматические отчеты
**Срок:** 2 дня  

**Действия:**
1. Создать скрипт для генерации отчетов:
   ```python
   # tests/generate_reports.py
   def generate_test_report():
       # Запуск тестов с отчетами
       # Анализ результатов
       # Отправка уведомлений
   ```

2. Настроить HTML отчеты:
   ```bash
   pytest --html=tests/reports/latest_report.html --self-contained-html
   ```

### 8. Добавить coverage отчеты
**Срок:** 1 день  

**Действия:**
```bash
pytest --cov=pipeline --cov-report=html --cov-report=term-missing
```

## 📅 Временной план

### Неделя 1 (Критические задачи)
- **День 1:** Исправить webhook тест + зарегистрировать маркеры
- **День 2-3:** Добавить тестовые аудиофайлы
- **День 4:** Улучшить обработку API ключей
- **День 5:** Исправить предупреждения

### Неделя 2 (Оптимизация)
- **День 1-3:** Оптимизировать время выполнения
- **День 4-5:** Настроить автоматические отчеты и coverage

## ✅ Критерии успеха

### Количественные:
- [ ] 100% успешных тестов (224/224)
- [ ] 0 пропущенных тестов
- [ ] 0 предупреждений
- [ ] Время выполнения <60 минут
- [ ] Coverage >95%

### Качественные:
- [ ] Стабильные тесты без flaky behavior
- [ ] Понятные сообщения об ошибках
- [ ] Автоматические отчеты
- [ ] Документированные тестовые данные

## 🔄 Процесс контроля

### Ежедневно:
- Запуск полного набора тестов
- Проверка новых предупреждений
- Мониторинг времени выполнения

### Еженедельно:
- Анализ coverage отчетов
- Обновление тестовых данных
- Ревью новых тестов

### Ежемесячно:
- Полный аудит тестовой системы
- Оптимизация производительности
- Планирование улучшений

## 📞 Контакты и ответственность

**Основной ответственный:** Команда разработки  
**Ревьюер:** Tech Lead  
**Срок завершения:** 2 недели  

---

**Статус:** 🟡 В процессе  
**Последнее обновление:** 2024-12-19
