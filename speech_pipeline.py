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
    logger.info(f"[5/5] 💾 Экспортирую в {args.format.upper()}...")
    export_agent = ExportAgent(format=args.format)
    out_path = Path(args.output)
    export_agent.run(merged_segments, out_path)
    logger.info(f"🎉 Готово! Результат сохранён: {out_path}")

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
