# 🚀 План оптимизации производительности Erni_audio_v2

## 📊 Анализ текущего состояния (2025-06-01)

### Выявленные узкие места
На основе анализа обработки файла "Sitzung Erweiterte GL 17.04.2025.m4a" (214MB, 140 минут):

| Компонент | Время | Доля | Проблема |
|-----------|-------|------|----------|
| **OpenAI API retry** | 27 мин 48 сек | 70% | Нестабильность API, простые retry |
| **Rate limiting** | 6 мин 6 сек | 15% | Превышение лимитов запросов |
| **Сетевые задержки** | 4 мин | 10% | Загрузка больших файлов |
| **Overhead разбиения** | 2 мин | 5% | Обработка 14 частей |
| **Итого** | **39 мин 54 сек** | 100% | Вместо ожидаемых 14 минут |

### Поддерживаемые форматы API

#### pyannote.ai API
- **Форматы**: mp3, wav, m4a, ogg, flac
- **Лимиты**: до 1GB (диаризация), до 100MB (voiceprints)
- **Длительность**: до 24 часов (диаризация), до 30 секунд (voiceprints)

#### OpenAI Whisper API
- **Форматы**: m4a, mp3, webm, mp4, mpga, wav, mpeg
- **Лимиты**: до 25MB на файл
- **Рекомендации**: 16kHz mono WAV, 128-256 kbps

## 🎯 План оптимизации

### Фаза 1: Критические улучшения (Июль 2025)

#### 1.1 Улучшенная обработка ошибок OpenAI API
**Цель**: Снижение времени retry на 62% (с 27 мин до 10 мин)

```python
# Текущая реализация (проблемная)
def simple_retry():
    for attempt in range(3):
        try:
            return api_call()
        except Exception:
            time.sleep(1)  # Фиксированная задержка

# Новая реализация (оптимизированная)
def exponential_backoff_retry():
    max_retries = 5
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            return api_call()
        except openai.RateLimitError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Rate limit hit, retrying in {delay:.2f}s...")
                time.sleep(delay)
            else:
                raise
        except openai.APIConnectionError as e:
            # Быстрый retry для сетевых ошибок
            if attempt < 2:
                time.sleep(0.5)
                continue
            raise
```

**Задачи**:
- [ ] Реализация exponential backoff с jitter
- [ ] Интеллектуальное определение типов ошибок
- [ ] Адаптивные таймауты на основе размера файла
- [ ] Детальное логирование статистики retry

#### 1.2 Параллельная обработка частей файлов
**Цель**: Ускорение обработки на 47%

```python
async def parallel_transcription(chunks: List[Path]) -> List[Dict]:
    """Параллельная обработка до 3 частей одновременно"""
    semaphore = asyncio.Semaphore(3)  # Лимит одновременных запросов
    
    async def process_chunk(chunk_path, offset):
        async with semaphore:
            return await transcribe_chunk_async(chunk_path, offset)
    
    tasks = [process_chunk(chunk, i*600) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return merge_chunk_results(results)
```

**Задачи**:
- [ ] Асинхронная обработка до 3 частей одновременно
- [ ] Семафоры для контроля нагрузки на OpenAI API
- [ ] Очередь задач с приоритетами
- [ ] Мониторинг производительности в реальном времени

### Фаза 2: Архитектурные улучшения (Август 2025)

#### 2.1 Оптимизация разбиения файлов
**Цель**: Улучшение на 25%

```python
def smart_split_audio(wav_local: Path) -> List[Path]:
    """Разбиение с учетом пауз в речи"""
    audio = AudioSegment.from_wav(wav_local)
    
    # Детекция пауз для естественного разбиения
    silence_thresh = audio.dBFS - 16
    chunks = split_on_silence(
        audio,
        min_silence_len=2000,  # 2 секунды тишины
        silence_thresh=silence_thresh,
        keep_silence=500  # Сохранить 0.5с тишины
    )
    
    return optimize_chunk_sizes(chunks, target_size_mb=20)
```

**Задачи**:
- [ ] Умное разбиение по паузам в речи (silence detection)
- [ ] Динамический размер частей (15-20MB вместо фиксированных 10 минут)
- [ ] Предварительная оценка времени обработки
- [ ] Оптимизация для минимизации overhead

#### 2.2 Кэширование результатов
**Цель**: 80% cache hit rate

```python
def cache_key(file_path: Path, params: Dict) -> str:
    """Генерация ключа кэша на основе хэша файла и параметров"""
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
    params_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
    return f"transcription:{file_hash}:{params_hash}"

async def cached_transcription(file_path: Path, params: Dict) -> Dict:
    """Транскрипция с кэшированием"""
    cache_key_str = cache_key(file_path, params)
    
    # Проверка кэша
    cached_result = await redis_client.get(cache_key_str)
    if cached_result:
        return json.loads(cached_result)
    
    # Обработка и сохранение в кэш
    result = await transcribe_file(file_path, params)
    await redis_client.setex(cache_key_str, 86400, json.dumps(result))  # TTL 24ч
    
    return result
```

### Фаза 3: Мониторинг и метрики (Сентябрь 2025)

#### 3.1 Prometheus метрики
```python
# Метрики производительности
TRANSCRIPTION_DURATION = Histogram(
    'transcription_duration_seconds',
    'Time spent on transcription',
    ['model', 'file_size_mb']
)

API_RETRY_COUNT = Counter(
    'api_retry_total',
    'Total API retry attempts',
    ['api_provider', 'error_type']
)

PARALLEL_PROCESSING_EFFICIENCY = Gauge(
    'parallel_processing_efficiency',
    'Efficiency of parallel processing (0-1)'
)
```

#### 3.2 Алертинг
- Превышение времени обработки > 0.2x от длительности аудио
- Количество retry > 5 для одного файла
- Cache hit rate < 60%
- API error rate > 5%

## 📈 Ожидаемые результаты

### Производительность
| Метрика | Текущее | После оптимизации | Улучшение |
|---------|---------|-------------------|-----------|
| **Время обработки** | 42 мин (0.3x) | 6 мин (0.05x) | **85% быстрее** |
| **API retry время** | 27 мин (70%) | 4 мин (10%) | **62% быстрее** |
| **Параллелизм** | 1 часть | 3 части | **47% быстрее** |
| **Умное разбиение** | Фиксированное | Динамическое | **25% быстрее** |

### Надежность
- **API error rate**: 5% → 1%
- **Retry success rate**: 85% → 95%
- **Cache hit rate**: 0% → 80%
- **Uptime**: 95% → 99.5%

## 🛠️ Инструменты и технологии

### Новые зависимости
```bash
pip install redis asyncio aiohttp pydub
```

### Конфигурация
```yaml
# config/performance.yaml
retry:
  max_attempts: 5
  base_delay: 1.0
  max_delay: 60.0
  jitter: true

parallel:
  max_concurrent_chunks: 3
  semaphore_timeout: 300

cache:
  redis_url: "redis://localhost:6379"
  ttl_seconds: 86400
  max_memory: "2gb"

splitting:
  target_size_mb: 20
  silence_threshold_db: -16
  min_silence_ms: 2000
```

## 📋 Критерии готовности

### Для каждой фазы:
- [ ] Код написан и протестирован
- [ ] Performance тесты показывают ожидаемые улучшения
- [ ] Backward compatibility сохранена
- [ ] Документация обновлена
- [ ] Метрики настроены и работают

### Для финального релиза:
- [ ] Общее ускорение > 80%
- [ ] API retry время < 15% от общего времени
- [ ] Cache hit rate > 70%
- [ ] Все существующие тесты проходят
- [ ] Новые performance тесты добавлены

---

*Документ создан: 2025-06-01*
*Ответственный: Development Team*
*Следующий обзор: 2025-07-01*
