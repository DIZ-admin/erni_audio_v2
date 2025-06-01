#!/usr/bin/env python
# speech_pipeline.py

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict
import requests

# Загружаем переменные окружения из .env файла (если есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен, используем системные переменные

# Импортируем всех агентов из нашего пакета pipeline
from pipeline.audio_agent import AudioLoaderAgent
from pipeline.diarization_agent import DiarizationAgent
from pipeline.qc_agent import QCAgent
from pipeline.transcription_agent import TranscriptionAgent
from pipeline.merge_agent import MergeAgent
from pipeline.export_agent import ExportAgent
from pipeline.utils import load_json, save_json
from pipeline.security_validator import SECURITY_VALIDATOR

def parse_args():
    p = argparse.ArgumentParser("speech_pipeline: multi-agent version")
    p.add_argument("input", help="audio/video FILE или HTTPS URL (16 kHz WAV)")
    p.add_argument("-o", "--output", default="data/processed/transcript.srt",
                   help="куда сохранить финальный файл")
    p.add_argument("--format", choices=["srt", "json", "ass"], default="srt",
                   help="формат выходных субтитров")
    p.add_argument("--all-formats", action="store_true",
                   help="создать файлы во всех форматах (SRT, JSON, ASS)")
    p.add_argument("--overwrite", action="store_true",
                   help="перезаписывать существующие файлы")
    p.add_argument("--add-timestamp", action="store_true",
                   help="добавлять временную метку к именам файлов")
    p.add_argument("--prompt", default="", help="начальный Whisper prompt")
    p.add_argument("--remote-wav-url", help="пропустить upload → использовать этот HTTPS URL")
    p.add_argument("--voiceprints-dir", help="извлечь WAV≤30с на каждого speakers → exit")
    p.add_argument("--identify", help="JSON mapping {voiceprintId:HumanName} → включить идентификацию")

    # Опции транскрипции
    p.add_argument("--transcription-model",
                   choices=["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"],
                   default="whisper-1",
                   help="модель для транскрипции (whisper-1: быстро/дешево, gpt-4o-mini-transcribe: баланс, gpt-4o-transcribe: максимальное качество)")
    p.add_argument("--language",
                   help="код языка для транскрипции (en, ru, de, fr, es, etc.) - улучшает точность")
    p.add_argument("--show-cost-estimate", action="store_true",
                   help="показать оценку стоимости транскрипции для всех моделей")

    # Опции Replicate
    p.add_argument("--use-replicate", action="store_true",
                   help="использовать Replicate whisper-diarization вместо стандартного пайплайна (быстрее и дешевле)")
    p.add_argument("--replicate-speakers", type=int, metavar="N",
                   help="количество спикеров для Replicate (1-50, по умолчанию автоопределение)")

    # Опции Voiceprint (идентификация спикеров)
    p.add_argument("--use-identification", action="store_true",
                   help="использовать идентификацию спикеров через voiceprints вместо обычной диаризации")
    p.add_argument("--voiceprints", metavar="NAMES",
                   help="список имен voiceprints через запятую (например: 'John Doe,Jane Smith')")
    p.add_argument("--matching-threshold", type=float, default=0.0, metavar="FLOAT",
                   help="порог сходства для сопоставления voiceprints (0.0-1.0, по умолчанию 0.0)")
    p.add_argument("--exclusive-matching", action="store_true", default=True,
                   help="эксклюзивное сопоставление (один voiceprint = один спикер)")

    # Опции загрузки файлов (только pyannote.ai Media API)
    # Примечание: OneDrive и transfer.sh удалены для повышения безопасности

    return p.parse_args()

def sys_exit(msg: str):
    raise SystemExit(f"❌  {msg}")

def setup_logging():
    """Настройка логирования с ротацией и структурированными логами"""
    from logging.handlers import RotatingFileHandler
    import json
    import datetime

    # Создаём директорию для логов
    Path('logs').mkdir(exist_ok=True)

    # Кастомный форматтер для JSON логов
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            if record.exc_info:
                log_entry['exception'] = self.formatException(record.exc_info)
            return json.dumps(log_entry, ensure_ascii=False)

    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Очищаем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (человекочитаемый формат)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler с ротацией (JSON формат)
    file_handler = RotatingFileHandler(
        'logs/pipeline.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Отдельный handler для ошибок
    error_handler = RotatingFileHandler(
        'logs/errors.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

def ensure_directories():
    """Создаёт необходимые директории если они не существуют"""
    directories = [
        "data/raw",
        "data/interim",
        "data/processed",
        "voiceprints"
    ]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

def validate_input_file(input_path: str) -> None:
    """Улучшенная валидация входного файла с проверкой безопасности"""
    logger = logging.getLogger(__name__)

    # Если это URL, используем валидацию URL
    if input_path.startswith(('http://', 'https://')):
        is_valid, message = SECURITY_VALIDATOR.validate_url(input_path)
        if not is_valid:
            raise ValueError(f"Небезопасный URL: {message}")
        logger.info(f"Входной URL валиден: {input_path}")
        return

    # Для локальных файлов используем комплексную валидацию
    file_path = Path(input_path)
    is_valid, message = SECURITY_VALIDATOR.validate_file(file_path)
    if not is_valid:
        raise ValueError(f"Файл не прошел валидацию: {message}")

    logger.info(f"Файл прошел валидацию безопасности: {message}")

def show_cost_estimates(file_path: str, transcription_model: str) -> None:
    """Показывает оценку стоимости транскрипции для всех моделей"""
    logger = logging.getLogger(__name__)

    try:
        # Определяем размер файла
        if file_path.startswith(('http://', 'https://')):
            # Для URL пытаемся получить размер через HEAD запрос
            try:
                response = requests.head(file_path, timeout=10)
                file_size_mb = int(response.headers.get('content-length', 0)) / (1024 * 1024)
                if file_size_mb == 0:
                    file_size_mb = 10  # Примерная оценка для URL
            except:
                file_size_mb = 10  # Примерная оценка
        else:
            # Для локальных файлов
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)

        # Получаем оценки стоимости для всех моделей
        from pipeline.transcription_agent import TranscriptionAgent

        print("\n💰 Оценка стоимости транскрипции:")
        print(f"📁 Размер файла: {file_size_mb:.1f} MB")
        print("─" * 60)

        for model_name, model_info in TranscriptionAgent.SUPPORTED_MODELS.items():
            # Создаем временный агент для оценки
            temp_agent = TranscriptionAgent("dummy_key", model_name)
            cost_estimate = temp_agent.estimate_cost(file_size_mb)

            # Отмечаем выбранную модель
            marker = "👉 " if model_name == transcription_model else "   "

            print(f"{marker}{model_info['name']:<25} | {cost_estimate:>10} | {model_info['cost_tier']}")

        print("─" * 60)
        print("💡 Примечание: Оценки приблизительные и могут отличаться от фактической стоимости")
        print()

    except Exception as e:
        logger.warning(f"Не удалось рассчитать оценку стоимости: {e}")

def run_replicate_pipeline(args, logger, replicate_key: str, start_time: float):
    """Запуск упрощенного пайплайна через Replicate"""
    import time
    from pipeline.replicate_agent import ReplicateAgent
    from pipeline.export_agent import ExportAgent
    from pipeline.utils import save_json

    try:
        # 1) Валидация входного файла для Replicate
        if args.input.startswith(('http://', 'https://')):
            logger.error("❌ Replicate не поддерживает URL. Используйте локальный файл.")
            sys.exit(1)

        input_path = Path(args.input)
        if not input_path.exists():
            logger.error(f"❌ Файл не найден: {input_path}")
            sys.exit(1)

        # 2) Создание Replicate агента
        logger.info("🚀 Инициализация Replicate Agent...")
        replicate_agent = ReplicateAgent(api_token=replicate_key)

        # 3) Показать оценку стоимости для Replicate
        if args.show_cost_estimate:
            cost_info = replicate_agent.estimate_cost(input_path)
            print("\n💰 Оценка стоимости Replicate:")
            print(f"📁 Размер файла: {cost_info['file_size_mb']} MB")
            print(f"💵 Примерная стоимость: ${cost_info['estimated_cost_usd']}")
            print(f"💡 {cost_info['note']}")
            print()

        # 4) Запуск обработки
        logger.info(f"[1/2] 🎵 Обрабатываю через Replicate: {input_path.name}")

        segments = replicate_agent.run(
            audio_file=input_path,
            num_speakers=args.replicate_speakers,
            language=args.language,
            prompt=args.prompt
        )

        logger.info(f"✅ Replicate обработка завершена: {len(segments)} сегментов")

        # 5) Сохранение промежуточного результата
        input_name = input_path.stem
        interim_file = Path("data/interim") / f"{input_name}_replicate.json"
        save_json(segments, interim_file)
        logger.debug(f"Результат Replicate сохранён: {interim_file}")

        # 6) Экспорт в финальный формат
        if args.all_formats:
            logger.info(f"[2/2] 💾 Экспортирую во всех форматах (SRT, JSON, ASS)...")
        else:
            logger.info(f"[2/2] 💾 Экспортирую в {args.format.upper()}...")
        export_agent = ExportAgent(format=args.format, create_all_formats=args.all_formats,
                                   overwrite_existing=args.overwrite, add_timestamp=args.add_timestamp)
        out_path = Path(args.output)
        created_files = export_agent.run(segments, out_path)

        if args.all_formats:
            logger.info(f"🎉 Готово! Созданы файлы: {[str(f) for f in created_files]}")
        else:
            logger.info(f"🎉 Готово! Результат сохранён: {created_files[0]}")

        # Финальные метрики
        end_time = time.time()
        total_time = end_time - start_time
        logger.info("✨ Replicate Pipeline завершён успешно", extra={
            'total_time_seconds': round(total_time, 2),
            'total_segments': len(segments),
            'output_file': str(out_path),
            'method': 'replicate',
            'success': True
        })

    except Exception as e:
        logger.error(f"❌ Ошибка Replicate Pipeline: {e}")
        sys.exit(1)

def run_identification_pipeline(args, logger, pyannote_key: str, start_time: float):
    """Запуск пайплайна с идентификацией спикеров через voiceprints"""
    import time
    from pipeline.identification_agent import IdentificationAgent
    from pipeline.voiceprint_manager import VoiceprintManager
    from pipeline.export_agent import ExportAgent
    from pipeline.utils import save_json

    try:
        # 1) Валидация входного файла для идентификации
        if args.input.startswith(('http://', 'https://')):
            logger.error("❌ Identification пока не поддерживает URL. Используйте локальный файл.")
            sys.exit(1)

        input_path = Path(args.input)
        if not input_path.exists():
            logger.error(f"❌ Файл не найден: {input_path}")
            sys.exit(1)

        # 2) Проверка voiceprints
        if not args.voiceprints:
            logger.error("❌ Для идентификации необходимо указать --voiceprints")
            sys.exit(1)

        voiceprint_names = [name.strip() for name in args.voiceprints.split(',')]
        logger.info(f"👥 Запрошенные voiceprints: {', '.join(voiceprint_names)}")

        # 3) Загрузка voiceprints из базы
        manager = VoiceprintManager()
        voiceprints = manager.get_voiceprints_for_identification(voiceprint_names)

        if not voiceprints:
            logger.error("❌ Не найдено ни одного voiceprint в базе")
            logger.info("💡 Используйте voiceprint_cli.py для создания voiceprints")
            sys.exit(1)

        logger.info(f"✅ Загружено {len(voiceprints)} voiceprints из базы")

        # 4) Создание Identification агента
        logger.info("🚀 Инициализация Identification Agent...")
        identification_agent = IdentificationAgent(api_key=pyannote_key)

        # 5) Показать оценку стоимости если запрошено
        if args.show_cost_estimate:
            cost_info = identification_agent.estimate_cost(input_path, len(voiceprints))
            print(f"\n💰 Оценка стоимости Identification:")
            print(f"📁 Размер файла: {cost_info['file_size_mb']} MB")
            print(f"👥 Voiceprints: {cost_info['num_voiceprints']}")
            print(f"💵 Примерная стоимость: ${cost_info['estimated_cost_usd']}")
            print(f"💡 {cost_info['note']}")
            print()

        # 6) Запуск идентификации
        logger.info(f"[1/2] 🎵 Обрабатываю через Identification: {input_path.name}")

        segments = identification_agent.run(
            audio_file=input_path,
            voiceprints=voiceprints,
            num_speakers=getattr(args, 'replicate_speakers', None),  # Используем тот же параметр
            confidence=True,
            matching_threshold=args.matching_threshold,
            exclusive_matching=args.exclusive_matching
        )

        logger.info(f"✅ Identification завершена: {len(segments)} сегментов")

        # 7) Сохранение промежуточного результата
        input_name = input_path.stem
        interim_file = Path("data/interim") / f"{input_name}_identification.json"
        save_json(segments, interim_file)
        logger.debug(f"Результат Identification сохранён: {interim_file}")

        # 8) Экспорт в финальный формат
        if args.all_formats:
            logger.info(f"[2/2] 💾 Экспортирую во всех форматах (SRT, JSON, ASS)...")
        else:
            logger.info(f"[2/2] 💾 Экспортирую в {args.format.upper()}...")
        export_agent = ExportAgent(format=args.format, create_all_formats=args.all_formats,
                                   overwrite_existing=args.overwrite, add_timestamp=args.add_timestamp)
        out_path = Path(args.output)
        created_files = export_agent.run(segments, out_path)

        if args.all_formats:
            logger.info(f"🎉 Готово! Созданы файлы: {[str(f) for f in created_files]}")
        else:
            logger.info(f"🎉 Готово! Результат сохранён: {created_files[0]}")

        # Финальные метрики
        end_time = time.time()
        total_time = end_time - start_time
        logger.info("✨ Identification Pipeline завершён успешно", extra={
            'total_time_seconds': round(total_time, 2),
            'total_segments': len(segments),
            'output_file': str(out_path),
            'method': 'identification',
            'voiceprints_used': len(voiceprints),
            'success': True
        })

    except Exception as e:
        logger.error(f"❌ Ошибка Identification Pipeline: {e}")
        sys.exit(1)

def main():
    import time
    start_time = time.time()

    args = parse_args()

    # 0) Настройка логирования и создание директорий
    setup_logging()
    ensure_directories()

    logger = logging.getLogger(__name__)
    logger.info("🚀 Запуск Speech Pipeline", extra={
        'input_file': args.input,
        'output_format': args.format,
        'transcription_model': args.transcription_model,
        'language': args.language,
        'pipeline_version': '2.0'
    })

    try:
        # 1) Валидация входного файла
        validate_input_file(args.input)

        # 2) Показать оценку стоимости если запрошено
        if args.show_cost_estimate:
            show_cost_estimates(args.input, args.transcription_model)

        # 3) Проверка обязательных окружений
        REPLICATE_KEY = None
        PYANNOTE_KEY = None
        OPENAI_KEY = None

        if args.use_replicate:
            # Для Replicate нужен только его API токен
            REPLICATE_KEY = os.getenv("REPLICATE_API_TOKEN") or sys_exit("Missing REPLICATE_API_TOKEN для --use-replicate")
            logger.info("🔄 Режим Replicate: используется thomasmol/whisper-diarization")
        elif args.use_identification:
            # Для идентификации нужен только pyannote.ai ключ
            PYANNOTE_KEY = os.getenv("PYANNOTEAI_API_TOKEN") or os.getenv("PYANNOTE_API_KEY") or sys_exit("Missing PYANNOTEAI_API_TOKEN or PYANNOTE_API_KEY для --use-identification")
            logger.info("🔄 Режим идентификации: используется pyannote.ai identification")
        else:
            # Для стандартного пайплайна нужны оба ключа
            PYANNOTE_KEY = os.getenv("PYANNOTEAI_API_TOKEN") or os.getenv("PYANNOTE_API_KEY") or sys_exit("Missing PYANNOTEAI_API_TOKEN or PYANNOTE_API_KEY")
            OPENAI_KEY   = os.getenv("OPENAI_API_KEY")   or sys_exit("Missing OPENAI_API_KEY")

        # 4) Логируем выбранную модель транскрипции
        from pipeline.transcription_agent import TranscriptionAgent
        model_info = TranscriptionAgent.SUPPORTED_MODELS.get(args.transcription_model, {})
        logger.info(f"🎯 Выбрана модель транскрипции: {model_info.get('name', args.transcription_model)}")
        if args.language:
            logger.info(f"🌍 Установлен язык: {args.language}")

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Ошибка валидации: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при инициализации: {e}")
        sys.exit(1)

    # Если используется Replicate, запускаем упрощенный пайплайн
    if args.use_replicate:
        if not REPLICATE_KEY:
            sys_exit("REPLICATE_KEY не установлен")
        return run_replicate_pipeline(args, logger, REPLICATE_KEY, start_time)

    # Если используется идентификация, запускаем пайплайн с identification
    if args.use_identification:
        if not PYANNOTE_KEY:
            sys_exit("PYANNOTE_KEY не установлен")
        return run_identification_pipeline(args, logger, PYANNOTE_KEY, start_time)

    # 2) AudioLoaderAgent → (wav_local, wav_url)
    logger.info(f"[1/5] 🎵 Конвертирую аудио: {args.input}")
    try:
        logger.info("📁 Метод загрузки: pyannote.ai Media API (безопасное временное хранилище)")

        audio_agent = AudioLoaderAgent(
            remote_wav_url=args.remote_wav_url,
            pyannote_api_key=PYANNOTE_KEY
        )
        wav_local, wav_url = audio_agent.run(args.input)
        logger.info(f"✅ Аудио готово: {wav_local} → {wav_url}")

        # Сохраняем промежуточный WAV файл
        input_name = Path(args.input).stem
        interim_wav = Path("data/interim") / f"{input_name}_converted.wav"
        import shutil
        shutil.copy2(wav_local, interim_wav)
        logger.debug(f"Промежуточный WAV сохранён: {interim_wav}")

    except Exception as e:
        logger.error(f"Ошибка обработки аудио: {e}")
        sys.exit(1)

    # 3) DiarizationAgent → raw_diar (List[Dict])
    logger.info("[2/5] 🎤 Запуск диаризации...")
    use_identify = bool(args.identify)
    voiceprint_ids = []
    if use_identify:
        mapping = load_json(Path(args.identify))  # { "vp_uuid": "Alice", ... }
        voiceprint_ids = list(mapping.keys())
        logger.info(f"Режим идентификации: {len(voiceprint_ids)} голосовых отпечатков")

    try:
        diar_agent = DiarizationAgent(api_key=PYANNOTE_KEY,
                                      use_identify=use_identify,
                                      voiceprint_ids=voiceprint_ids)
        raw_diar: List[Dict] = diar_agent.run(wav_url)
        logger.info(f"✅ Диаризация завершена: {len(raw_diar)} сегментов")

        # Сохраняем результат диаризации
        diar_file = Path("data/interim") / f"{input_name}_diarization.json"
        save_json(raw_diar, diar_file)
        logger.debug(f"Результат диаризации сохранён: {diar_file}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при обращении к Pyannote API: {e}")
        logger.error("Проверьте подключение к интернету и корректность API ключа")
        sys.exit(1)
    except RuntimeError as e:
        if "not-ready" in str(e):
            logger.error("Превышено время ожидания обработки диаризации")
            logger.error("Попробуйте с более коротким аудио файлом")
        else:
            logger.error(f"Ошибка Pyannote API: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неожиданная ошибка диаризации: {e}")
        sys.exit(1)

    # QC Agent (опционально для извлечения голосовых отпечатков)
    qc_agent = QCAgent(manifest_dir=Path(args.voiceprints_dir) if args.voiceprints_dir else None,
                       per_speaker_sec=30)
    qc_result = qc_agent.run(wav_local, raw_diar)
    if args.voiceprints_dir:
        logger.info(f"✅ Голосовые отпечатки сохранены в {args.voiceprints_dir}")
        return

    # Если было identify, нужно заменить токены на человеческие имена в raw_diar
    if use_identify:
        # mapping = { "vp_uuid": "Alice", … }
        for seg in raw_diar:
            seg["speaker"] = mapping.get(seg["speaker"], seg["speaker"])
        logger.info("✅ Применён маппинг голосовых отпечатков")

    # 4) TranscriptionAgent → whisper_segments (List[Dict])
    model_name = TranscriptionAgent.SUPPORTED_MODELS.get(args.transcription_model, {}).get('name', args.transcription_model)
    logger.info(f"[3/5] 📝 Транскрибирую через {model_name}...")
    try:
        trans_agent = TranscriptionAgent(
            api_key=OPENAI_KEY,
            model=args.transcription_model,
            language=args.language
        )

        # Показываем информацию о модели
        model_info = trans_agent.get_model_info()
        logger.info(f"🔧 Модель: {model_info['name']} ({model_info['cost_tier']} cost)")

        whisper_segments = trans_agent.run(wav_local, args.prompt)
        logger.info(f"✅ Транскрипция завершена: {len(whisper_segments)} сегментов")

        # Сохраняем результат транскрипции
        whisper_file = Path("data/interim") / f"{input_name}_transcription.json"
        save_json(whisper_segments, whisper_file)
        logger.debug(f"Результат транскрипции сохранён: {whisper_file}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при обращении к OpenAI API: {e}")
        logger.error("Проверьте подключение к интернету и корректность API ключа")
        sys.exit(1)
    except Exception as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "quota" in error_msg:
            logger.error("Превышен лимит запросов к OpenAI API")
            logger.error("Подождите некоторое время или проверьте ваш план подписки")
        elif "invalid" in error_msg and "key" in error_msg:
            logger.error("Неверный API ключ OpenAI")
            logger.error("Проверьте правильность OPENAI_API_KEY")
        else:
            logger.error(f"Ошибка OpenAI API: {e}")
        sys.exit(1)

    # 5) MergeAgent → merged_segments (List[{"start","end","speaker","text"}])
    logger.info("[4/5] 🔗 Объединяю диаризацию с транскрипцией...")
    merge_agent = MergeAgent()
    merged_segments = merge_agent.run(raw_diar, whisper_segments)
    logger.info(f"✅ Объединение завершено: {len(merged_segments)} финальных сегментов")

    # Сохраняем финальный результат
    merged_file = Path("data/interim") / f"{input_name}_merged.json"
    save_json(merged_segments, merged_file)
    logger.debug(f"Финальный результат сохранён: {merged_file}")

    # 6) ExportAgent → финальный файл (SRT/JSON/ASS)
    if args.all_formats:
        logger.info(f"[5/5] 💾 Экспортирую во всех форматах (SRT, JSON, ASS)...")
    else:
        logger.info(f"[5/5] 💾 Экспортирую в {args.format.upper()}...")
    export_agent = ExportAgent(format=args.format, create_all_formats=args.all_formats,
                               overwrite_existing=args.overwrite, add_timestamp=args.add_timestamp)
    out_path = Path(args.output)
    created_files = export_agent.run(merged_segments, out_path)

    if args.all_formats:
        logger.info(f"🎉 Готово! Созданы файлы: {[str(f) for f in created_files]}")
    else:
        logger.info(f"🎉 Готово! Результат сохранён: {created_files[0]}")

    # Финальные метрики
    end_time = time.time()
    total_time = end_time - start_time
    logger.info("✨ Speech Pipeline завершён успешно", extra={
        'total_time_seconds': round(total_time, 2),
        'total_segments': len(merged_segments),
        'output_file': str(out_path),
        'success': True
    })

if __name__ == "__main__":
    main()
