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
from pipeline.monitoring import PERFORMANCE_MONITOR, log_performance_metrics
from pipeline.checkpoint_manager import CheckpointManager, PipelineStage

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

    # Опции checkpoint системы
    p.add_argument("--resume", action="store_true",
                   help="автоматически возобновить с последнего checkpoint'а (по умолчанию)")
    p.add_argument("--force-restart", action="store_true",
                   help="игнорировать checkpoint'ы и начать заново")
    p.add_argument("--cleanup-checkpoints", action="store_true",
                   help="очистить старые checkpoint'ы (старше 7 дней)")
    p.add_argument("--list-checkpoints", action="store_true",
                   help="показать доступные checkpoint'ы для файла")
    p.add_argument("--delete-checkpoint", metavar="PIPELINE_ID",
                   help="удалить конкретный checkpoint по ID")

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
        "data/checkpoints",
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

def handle_checkpoint_commands(args, logger):
    """Обработка команд управления checkpoint'ами"""
    checkpoint_manager = CheckpointManager()

    if args.cleanup_checkpoints:
        removed_count = checkpoint_manager.cleanup_old_checkpoints(days_old=7)
        logger.info(f"🧹 Очищено {removed_count} старых checkpoint'ов")
        return True

    if args.list_checkpoints:
        if not args.input:
            logger.error("❌ Для --list-checkpoints необходимо указать входной файл")
            return True

        summary = checkpoint_manager.get_pipeline_summary(args.input)
        if summary:
            logger.info(f"📋 Checkpoint для файла: {args.input}")
            logger.info(f"   Pipeline ID: {summary['pipeline_id']}")
            logger.info(f"   Статус: {summary['status']}")
            logger.info(f"   Создан: {summary['created_at']}")
            logger.info(f"   Обновлен: {summary['last_updated']}")
            logger.info(f"   Завершенные этапы: {', '.join(summary['completed_stages'])}")
            if summary['current_stage']:
                logger.info(f"   Текущий этап: {summary['current_stage']}")
            if summary['failed_stage']:
                logger.info(f"   Неудачный этап: {summary['failed_stage']}")
            logger.info(f"   Checkpoint'ы: {summary['successful_checkpoints']}/{summary['total_checkpoints']} успешных")
        else:
            logger.info(f"📋 Checkpoint'ы для файла {args.input} не найдены")
        return True

    if args.delete_checkpoint:
        # Здесь можно добавить логику удаления конкретного checkpoint'а
        logger.info(f"🗑️ Удаление checkpoint'а {args.delete_checkpoint} (функция в разработке)")
        return True

    return False

@log_performance_metrics
def run_replicate_pipeline(args, logger, replicate_key: str, start_time: float):
    """Запуск упрощенного пайплайна через Replicate"""
    import time
    from pipeline.replicate_agent import ReplicateAgent
    from pipeline.export_agent import ExportAgent
    from pipeline.utils import save_json

    try:
        # Записываем начало обработки
        PERFORMANCE_MONITOR.start_processing()
        logger.info("📊 Мониторинг: начало Replicate pipeline")
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
        PERFORMANCE_MONITOR.record_api_call()

        segments = replicate_agent.run(
            audio_file=input_path,
            num_speakers=args.replicate_speakers,
            language=args.language,
            prompt=args.prompt
        )

        logger.info(f"✅ Replicate обработка завершена: {len(segments)} сегментов")
        PERFORMANCE_MONITOR.end_processing(success=True)

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

@log_performance_metrics
def run_standard_pipeline_with_checkpoints(args, logger, pyannote_key: str, openai_key: str, start_time: float):
    """Запуск стандартного пайплайна с поддержкой checkpoint'ов"""
    import time
    import shutil

    try:
        # Инициализация checkpoint manager
        checkpoint_manager = CheckpointManager()
        input_name = Path(args.input).stem

        # Проверяем возможность возобновления
        resume_point, existing_files = checkpoint_manager.get_resume_point(args.input, "standard")

        if resume_point and not args.force_restart:
            logger.info(f"🔄 Найден checkpoint, возобновление с этапа: {resume_point.value}")

            # Валидируем существующие файлы
            validation_results = checkpoint_manager.validate_checkpoint_files(args.input)
            invalid_files = [f for f, valid in validation_results.items() if not valid]

            if invalid_files:
                logger.warning(f"⚠️ Найдены невалидные файлы: {invalid_files}")
                logger.info("🔄 Перезапуск с начала из-за поврежденных checkpoint'ов")
                resume_point = None
        else:
            if args.force_restart:
                logger.info("🆕 Принудительный перезапуск (игнорируем checkpoint'ы)")
            else:
                logger.info("🆕 Начинаем новый пайплайн")
            resume_point = None

        # Начинаем мониторинг
        PERFORMANCE_MONITOR.start_processing()
        logger.info("📊 Мониторинг: начало стандартного pipeline с checkpoint'ами")

        # Переменные для хранения результатов этапов
        wav_local = None
        wav_url = None
        raw_diar = None
        whisper_segments = None
        merged_segments = None

        # ЭТАП 1: Конвертация аудио
        if resume_point is None or resume_point == PipelineStage.AUDIO_CONVERSION:
            logger.info(f"[1/5] 🎵 Конвертирую аудио: {args.input}")
            try:
                logger.info("📁 Метод загрузки: pyannote.ai Media API (безопасное временное хранилище)")

                audio_agent = AudioLoaderAgent(
                    remote_wav_url=args.remote_wav_url,
                    pyannote_api_key=pyannote_key
                )
                wav_local, wav_url = audio_agent.run(args.input)
                logger.info(f"✅ Аудио готово: {wav_local} → {wav_url}")
                PERFORMANCE_MONITOR.record_api_call()

                # Сохраняем промежуточный WAV файл
                interim_wav = Path("data/interim") / f"{input_name}_converted.wav"
                shutil.copy2(wav_local, interim_wav)
                logger.debug(f"Промежуточный WAV сохранён: {interim_wav}")

                # Создаем checkpoint
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.AUDIO_CONVERSION,
                    output_file=str(interim_wav),
                    metadata={
                        "wav_local": str(wav_local),
                        "wav_url": wav_url,
                        "file_size_mb": interim_wav.stat().st_size / (1024 * 1024)
                    },
                    success=True
                )

            except Exception as e:
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.AUDIO_CONVERSION,
                    output_file="",
                    success=False,
                    error_message=str(e)
                )
                logger.error(f"❌ Ошибка обработки аудио: {e}")
                sys.exit(1)
        else:
            # Загружаем данные из checkpoint'а
            logger.info("📂 Загружаю данные аудио из checkpoint'а")
            state = checkpoint_manager.load_pipeline_state(args.input)
            if state:
                for cp in state.checkpoints:
                    if cp.stage == PipelineStage.AUDIO_CONVERSION.value and cp.success:
                        wav_local = Path(cp.metadata.get("wav_local", ""))
                        wav_url = cp.metadata.get("wav_url", "")
                        logger.info(f"✅ Аудио загружено из checkpoint'а: {wav_local}")
                        break

        # ЭТАП 2: Диаризация
        if resume_point is None or resume_point == PipelineStage.DIARIZATION:
            logger.info("[2/5] 🎤 Запуск диаризации...")
            use_identify = bool(args.identify)
            voiceprint_ids = []
            if use_identify:
                mapping = load_json(Path(args.identify))  # { "vp_uuid": "Alice", ... }
                voiceprint_ids = list(mapping.keys())
                logger.info(f"Режим идентификации: {len(voiceprint_ids)} голосовых отпечатков")

            try:
                diar_agent = DiarizationAgent(api_key=pyannote_key,
                                              use_identify=use_identify,
                                              voiceprint_ids=voiceprint_ids)
                PERFORMANCE_MONITOR.record_api_call()
                raw_diar = diar_agent.run(wav_url)
                logger.info(f"✅ Диаризация завершена: {len(raw_diar)} сегментов")

                # Сохраняем результат диаризации
                diar_file = Path("data/interim") / f"{input_name}_diarization.json"
                save_json(raw_diar, diar_file)
                logger.debug(f"Результат диаризации сохранён: {diar_file}")

                # Создаем checkpoint
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.DIARIZATION,
                    output_file=str(diar_file),
                    metadata={
                        "segments_count": len(raw_diar),
                        "use_identify": use_identify,
                        "voiceprint_ids": voiceprint_ids
                    },
                    success=True
                )

            except Exception as e:
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.DIARIZATION,
                    output_file="",
                    success=False,
                    error_message=str(e)
                )
                logger.error(f"❌ Ошибка диаризации: {e}")
                sys.exit(1)
        else:
            # Загружаем данные из checkpoint'а
            logger.info("📂 Загружаю данные диаризации из checkpoint'а")
            state = checkpoint_manager.load_pipeline_state(args.input)
            if state:
                for cp in state.checkpoints:
                    if cp.stage == PipelineStage.DIARIZATION.value and cp.success:
                        raw_diar = load_json(Path(cp.output_file))
                        logger.info(f"✅ Диаризация загружена из checkpoint'а: {len(raw_diar)} сегментов")
                        break

        # ЭТАП 3: Транскрипция
        if resume_point is None or resume_point == PipelineStage.TRANSCRIPTION:
            model_name = TranscriptionAgent.SUPPORTED_MODELS.get(args.transcription_model, {}).get('name', args.transcription_model)
            logger.info(f"[3/5] 📝 Транскрибирую через {model_name}...")
            try:
                trans_agent = TranscriptionAgent(
                    api_key=openai_key,
                    model=args.transcription_model,
                    language=args.language
                )

                # Показываем информацию о модели
                model_info = trans_agent.get_model_info()
                logger.info(f"🔧 Модель: {model_info['name']} ({model_info['cost_tier']} cost)")

                PERFORMANCE_MONITOR.record_api_call()
                whisper_segments = trans_agent.run(wav_local, args.prompt)
                logger.info(f"✅ Транскрипция завершена: {len(whisper_segments)} сегментов")

                # Сохраняем результат транскрипции
                whisper_file = Path("data/interim") / f"{input_name}_transcription.json"
                save_json(whisper_segments, whisper_file)
                logger.debug(f"Результат транскрипции сохранён: {whisper_file}")

                # Создаем checkpoint
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.TRANSCRIPTION,
                    output_file=str(whisper_file),
                    metadata={
                        "segments_count": len(whisper_segments),
                        "model": args.transcription_model,
                        "language": args.language,
                        "prompt": args.prompt
                    },
                    success=True
                )

            except Exception as e:
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.TRANSCRIPTION,
                    output_file="",
                    success=False,
                    error_message=str(e)
                )
                logger.error(f"❌ Ошибка транскрипции: {e}")
                sys.exit(1)
        else:
            # Загружаем данные из checkpoint'а
            logger.info("📂 Загружаю данные транскрипции из checkpoint'а")
            state = checkpoint_manager.load_pipeline_state(args.input)
            if state:
                for cp in state.checkpoints:
                    if cp.stage == PipelineStage.TRANSCRIPTION.value and cp.success:
                        whisper_segments = load_json(Path(cp.output_file))
                        logger.info(f"✅ Транскрипция загружена из checkpoint'а: {len(whisper_segments)} сегментов")
                        break

        # QC Agent (опционально для извлечения голосовых отпечатков)
        if args.voiceprints_dir:
            qc_agent = QCAgent(manifest_dir=Path(args.voiceprints_dir), per_speaker_sec=30)
            qc_result = qc_agent.run(wav_local, raw_diar)
            logger.info(f"✅ Голосовые отпечатки сохранены в {args.voiceprints_dir}")
            return

        # Если было identify, нужно заменить токены на человеческие имена в raw_diar
        if args.identify:
            mapping = load_json(Path(args.identify))  # { "vp_uuid": "Alice", … }
            for seg in raw_diar:
                seg["speaker"] = mapping.get(seg["speaker"], seg["speaker"])
            logger.info("✅ Применён маппинг голосовых отпечатков")

        # ЭТАП 4: Объединение
        if resume_point is None or resume_point == PipelineStage.MERGE:
            logger.info("[4/5] 🔗 Объединяю диаризацию с транскрипцией...")
            try:
                merge_agent = MergeAgent()
                merged_segments = merge_agent.run(raw_diar, whisper_segments)
                logger.info(f"✅ Объединение завершено: {len(merged_segments)} финальных сегментов")

                # Сохраняем финальный результат
                merged_file = Path("data/interim") / f"{input_name}_merged.json"
                save_json(merged_segments, merged_file)
                logger.debug(f"Финальный результат сохранён: {merged_file}")

                # Создаем checkpoint
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.MERGE,
                    output_file=str(merged_file),
                    metadata={
                        "final_segments_count": len(merged_segments)
                    },
                    success=True
                )

            except Exception as e:
                checkpoint_manager.create_checkpoint(
                    input_file=args.input,
                    stage=PipelineStage.MERGE,
                    output_file="",
                    success=False,
                    error_message=str(e)
                )
                logger.error(f"❌ Ошибка объединения: {e}")
                sys.exit(1)
        else:
            # Загружаем данные из checkpoint'а
            logger.info("📂 Загружаю данные объединения из checkpoint'а")
            state = checkpoint_manager.load_pipeline_state(args.input)
            if state:
                for cp in state.checkpoints:
                    if cp.stage == PipelineStage.MERGE.value and cp.success:
                        merged_segments = load_json(Path(cp.output_file))
                        logger.info(f"✅ Объединение загружено из checkpoint'а: {len(merged_segments)} сегментов")
                        break

        # ЭТАП 5: Экспорт
        if args.all_formats:
            logger.info(f"[5/5] 💾 Экспортирую во всех форматах (SRT, JSON, ASS)...")
        else:
            logger.info(f"[5/5] 💾 Экспортирую в {args.format.upper()}...")

        try:
            export_agent = ExportAgent(format=args.format, create_all_formats=args.all_formats,
                                       overwrite_existing=args.overwrite, add_timestamp=args.add_timestamp)
            out_path = Path(args.output)
            created_files = export_agent.run(merged_segments, out_path)

            # Создаем финальный checkpoint
            checkpoint_manager.create_checkpoint(
                input_file=args.input,
                stage=PipelineStage.EXPORT,
                output_file=str(created_files[0]) if created_files else str(out_path),
                metadata={
                    "created_files": [str(f) for f in created_files],
                    "format": args.format,
                    "all_formats": args.all_formats
                },
                success=True
            )

            if args.all_formats:
                logger.info(f"🎉 Готово! Созданы файлы: {[str(f) for f in created_files]}")
            else:
                logger.info(f"🎉 Готово! Результат сохранён: {created_files[0]}")

        except Exception as e:
            checkpoint_manager.create_checkpoint(
                input_file=args.input,
                stage=PipelineStage.EXPORT,
                output_file="",
                success=False,
                error_message=str(e)
            )
            logger.error(f"❌ Ошибка экспорта: {e}")
            sys.exit(1)

        # Завершаем мониторинг
        PERFORMANCE_MONITOR.end_processing(success=True)

        # Сохраняем метрики производительности
        PERFORMANCE_MONITOR.save_metrics()

        # Получаем статус здоровья системы
        health_status = PERFORMANCE_MONITOR.get_health_status()
        logger.info(f"📊 Статус системы: {health_status['status']}")
        if health_status['issues']:
            for issue in health_status['issues']:
                logger.warning(f"⚠️ {issue}")

        # Финальные метрики
        end_time = time.time()
        total_time = end_time - start_time
        logger.info("✨ Standard Pipeline с checkpoint'ами завершён успешно", extra={
            'total_time_seconds': round(total_time, 2),
            'total_segments': len(merged_segments),
            'output_file': str(out_path),
            'system_status': health_status['status'],
            'resume_point': resume_point.value if resume_point else None,
            'success': True
        })

    except Exception as e:
        logger.error(f"❌ Ошибка Standard Pipeline с checkpoint'ами: {e}")
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
        'pipeline_version': '2.1-checkpoint'
    })

    try:
        # 0) Обработка команд checkpoint'ов
        if handle_checkpoint_commands(args, logger):
            return  # Команда checkpoint'а выполнена, выходим

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

    # Запускаем стандартный пайплайн с поддержкой checkpoint'ов
    return run_standard_pipeline_with_checkpoints(args, logger, PYANNOTE_KEY, OPENAI_KEY, start_time)

if __name__ == "__main__":
    main()
