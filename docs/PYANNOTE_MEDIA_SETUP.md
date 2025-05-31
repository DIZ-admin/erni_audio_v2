# Настройка pyannote.ai Media API

Руководство по настройке и использованию безопасного временного хранилища pyannote.ai Media API.

## 🎯 Обзор

pyannote.ai Media API предоставляет безопасное временное хранилище для аудио файлов:

- ✅ **Безопасность**: Изолированное хранилище, доступное только с вашим API ключом
- ✅ **Автоматическая очистка**: Файлы удаляются через 24-48 часов
- ✅ **Шифрование**: HTTPS для передачи данных
- ✅ **Pre-signed URLs**: Безопасная загрузка без передачи API ключей

## 🔧 Настройка

### 1. Получение API ключа

1. Зарегистрируйтесь на [pyannote.ai](https://pyannote.ai)
2. Получите API ключ в личном кабинете
3. Настройте переменную окружения:

```bash
# Рекомендуемый формат (новый)
export PYANNOTEAI_API_TOKEN=your_api_key_here

# Или старый формат (поддерживается)
export PYANNOTE_API_KEY=your_api_key_here
```

### 2. Настройка в .env файле

```bash
# .env
PYANNOTEAI_API_TOKEN=your_api_key_here
OPENAI_API_KEY=your_openai_key_here

# Только pyannote.ai Media API (безопасный метод)
```

## 🚀 Использование

### Базовое использование (по умолчанию)

```bash
# pyannote.ai Media API используется автоматически как приоритет #1
python speech_pipeline.py audio.mp3 --format srt -o output.srt
```

### Единственный безопасный метод

```bash
# pyannote.ai Media API - единственный поддерживаемый метод загрузки
# Автоматически используется по умолчанию
python speech_pipeline.py audio.mp3 --format srt -o output.srt

# Все файлы загружаются в безопасное временное хранилище
# с автоматическим удалением через 24-48 часов
```

### Docker использование

```bash
docker run -e PYANNOTEAI_API_TOKEN=your_key -e OPENAI_API_KEY=your_key \
       -v $(pwd)/data:/app/data \
       speech-pipeline audio.mp3 --format srt -o output.srt
```

## 🔍 Проверка работы

### Проверка API ключа

```python
from pipeline.pyannote_media_agent import PyannoteMediaAgent

agent = PyannoteMediaAgent("your_api_key")
if agent.validate_api_key():
    print("✅ API ключ валиден")
else:
    print("❌ Неверный API ключ")
```

### Логи

Система автоматически логирует использование pyannote.ai Media API:

```
INFO - 📁 Методы загрузки: pyannote.ai Media API (приоритет #1) → OneDrive (приоритет #2) → transfer.sh (fallback)
INFO - ✅ Pyannote.ai Media агент инициализирован
INFO - 📤 Загружаю audio.wav в pyannote.ai временное хранилище...
INFO - ✅ Файл загружен в pyannote.ai: media://temp/audio_12345678_audio.wav
INFO - ℹ️ Файл будет автоматически удален через 24-48 часов
```

## 🛠️ Устранение неполадок

### Проблема: "Неверный API ключ pyannote.ai"

**Решение:**
1. Проверьте правильность API ключа
2. Убедитесь, что ключ активен в личном кабинете pyannote.ai
3. Проверьте переменную окружения:
   ```bash
   echo $PYANNOTEAI_API_TOKEN
   ```

### Проблема: "Превышен лимит запросов pyannote.ai"

**Решение:**
1. Подождите некоторое время перед повторной попыткой
2. Проверьте лимиты в личном кабинете pyannote.ai
3. Система автоматически переключится на OneDrive или transfer.sh

### Проблема: Fallback на transfer.sh

**Причины:**
- Неверный или отсутствующий API ключ
- Превышение лимитов API
- Временная недоступность сервиса

**Решение:**
- Проверьте логи для определения причины
- Исправьте проблему с API ключом
- При необходимости используйте OneDrive как альтернативу

## 🔒 Безопасность

### Рекомендации

1. **Используйте только pyannote.ai Media API** - единственный безопасный метод
2. **Не передавайте API ключи** в командной строке или логах
3. **Файлы автоматически удаляются** через 24-48 часов
4. **Все данные передаются по HTTPS** с шифрованием

### Что происходит с файлами

- **pyannote.ai Media API**: Файлы хранятся в изолированном временном хранилище 24-48ч ✅
- **Автоматическое удаление**: Никаких следов после обработки ✅
- **HTTPS шифрование**: Безопасная передача данных ✅

## 📚 Дополнительные ресурсы

- [Документация pyannote.ai Media API](https://docs.pyannote.ai/tutorials/how-to-upload-files)
- [Основное руководство](../README.md)
- [Архитектура проекта](../planning.md)
- [Статус безопасности](../tasks.md)

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи в `logs/pipeline.log`
2. Убедитесь в корректности API ключей
3. Проверьте подключение к интернету
4. Обратитесь к документации pyannote.ai

---

*Обновлено: 2024-12-19*
*Версия: 1.0*
