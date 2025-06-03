#!/usr/bin/env python3
"""
Скрипт для конвертации аудиофайлов для транскрипции с оптимизацией размера.
Конвертирует аудио в оптимальный формат для обработки ИИ с ограничением размера.
"""

import os
import argparse
import subprocess
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_audio_info(input_file):
    """Получает информацию об аудиофайле"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
            input_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        import json
        info = json.loads(result.stdout)
        
        # Извлекаем информацию
        format_info = info.get('format', {})
        duration = float(format_info.get('duration', 0))
        size_bytes = int(format_info.get('size', 0))
        size_mb = size_bytes / (1024 * 1024)
        
        # Информация о потоке
        audio_stream = None
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break
        
        if audio_stream:
            sample_rate = int(audio_stream.get('sample_rate', 0))
            channels = int(audio_stream.get('channels', 0))
            codec = audio_stream.get('codec_name', 'unknown')
        else:
            sample_rate = channels = 0
            codec = 'unknown'
        
        return {
            'duration': duration,
            'size_mb': size_mb,
            'sample_rate': sample_rate,
            'channels': channels,
            'codec': codec
        }
    
    except Exception as e:
        logger.error(f"Ошибка при получении информации об аудио: {e}")
        return None

def calculate_optimal_bitrate(duration_seconds, target_size_mb=190):
    """Вычисляет оптимальный битрейт для достижения целевого размера"""
    # Оставляем запас в 10 МБ от лимита
    target_size_bytes = target_size_mb * 1024 * 1024
    target_bitrate_bps = (target_size_bytes * 8) / duration_seconds
    target_bitrate_kbps = int(target_bitrate_bps / 1000)
    
    # Ограничиваем битрейт разумными пределами для речи
    min_bitrate = 32  # Минимум для понятной речи
    max_bitrate = 128  # Максимум для высокого качества речи
    
    return max(min_bitrate, min(target_bitrate_kbps, max_bitrate))

def convert_audio(input_file, output_file, max_size_mb=200, quality='balanced'):
    """
    Конвертирует аудиофайл в оптимальный формат для транскрипции
    
    Args:
        input_file: Путь к входному файлу
        output_file: Путь к выходному файлу
        max_size_mb: Максимальный размер в МБ
        quality: Качество ('fast', 'balanced', 'high')
    """
    
    # Получаем информацию о входном файле
    info = get_audio_info(input_file)
    if not info:
        return False
    
    logger.info(f"📁 Входной файл: {Path(input_file).name}")
    logger.info(f"⏱️  Длительность: {info['duration']:.1f} сек ({info['duration']/60:.1f} мин)")
    logger.info(f"📊 Размер: {info['size_mb']:.1f} МБ")
    logger.info(f"🎵 Формат: {info['codec']}, {info['sample_rate']} Hz, {info['channels']} каналов")
    
    # Определяем параметры конвертации
    if quality == 'fast':
        sample_rate = 16000
        bitrate = calculate_optimal_bitrate(info['duration'], max_size_mb - 10)
        preset = 'ultrafast'
    elif quality == 'high':
        sample_rate = 22050
        bitrate = calculate_optimal_bitrate(info['duration'], max_size_mb - 5)
        preset = 'slow'
    else:  # balanced
        sample_rate = 16000
        bitrate = calculate_optimal_bitrate(info['duration'], max_size_mb - 10)
        preset = 'medium'
    
    logger.info(f"🎯 Целевые параметры:")
    logger.info(f"   • Битрейт: {bitrate} kbps")
    logger.info(f"   • Частота дискретизации: {sample_rate} Hz")
    logger.info(f"   • Каналы: 1 (моно)")
    logger.info(f"   • Формат: MP3")
    
    # Команда FFmpeg для конвертации
    cmd = [
        'ffmpeg', '-i', input_file,
        '-acodec', 'mp3',           # Кодек MP3 для хорошего сжатия
        '-ar', str(sample_rate),    # Частота дискретизации
        '-ac', '1',                 # Моно
        '-ab', f'{bitrate}k',       # Битрейт
        '-preset', preset,          # Скорость кодирования
        '-y',                       # Перезаписать выходной файл
        output_file
    ]
    
    try:
        logger.info("🔄 Начинаем конвертацию...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Проверяем результат
        if os.path.exists(output_file):
            output_info = get_audio_info(output_file)
            if output_info:
                logger.info(f"✅ Конвертация завершена успешно!")
                logger.info(f"📁 Выходной файл: {Path(output_file).name}")
                logger.info(f"📊 Новый размер: {output_info['size_mb']:.1f} МБ")
                logger.info(f"📉 Сжатие: {((info['size_mb'] - output_info['size_mb']) / info['size_mb'] * 100):.1f}%")
                
                if output_info['size_mb'] <= max_size_mb:
                    logger.info(f"🎯 Размер в пределах лимита ({max_size_mb} МБ)")
                else:
                    logger.warning(f"⚠️  Размер превышает лимит! Попробуйте режим 'fast' или уменьшите лимит")
                
                return True
            else:
                logger.error("❌ Не удалось получить информацию о выходном файле")
                return False
        else:
            logger.error("❌ Выходной файл не создан")
            return False
    
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Ошибка FFmpeg: {e}")
        logger.error(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Конвертация аудиофайлов для транскрипции')
    parser.add_argument('input_file', help='Входной аудиофайл')
    parser.add_argument('-o', '--output', help='Выходной файл (по умолчанию: добавляется _converted)')
    parser.add_argument('-s', '--max-size', type=int, default=200, 
                       help='Максимальный размер в МБ (по умолчанию: 200)')
    parser.add_argument('-q', '--quality', choices=['fast', 'balanced', 'high'], default='balanced',
                       help='Качество конвертации (по умолчанию: balanced)')
    parser.add_argument('--info-only', action='store_true',
                       help='Только показать информацию о файле без конвертации')
    
    args = parser.parse_args()
    
    # Проверяем существование входного файла
    if not os.path.exists(args.input_file):
        logger.error(f"❌ Входной файл не найден: {args.input_file}")
        return 1
    
    # Проверяем наличие FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ FFmpeg не найден. Установите FFmpeg для работы скрипта.")
        return 1
    
    # Если только информация
    if args.info_only:
        info = get_audio_info(args.input_file)
        if info:
            logger.info("📊 Информация об аудиофайле:")
            logger.info(f"   • Длительность: {info['duration']:.1f} сек ({info['duration']/60:.1f} мин)")
            logger.info(f"   • Размер: {info['size_mb']:.1f} МБ")
            logger.info(f"   • Кодек: {info['codec']}")
            logger.info(f"   • Частота: {info['sample_rate']} Hz")
            logger.info(f"   • Каналы: {info['channels']}")
            
            if info['size_mb'] > args.max_size:
                optimal_bitrate = calculate_optimal_bitrate(info['duration'], args.max_size - 10)
                logger.info(f"💡 Рекомендации для сжатия до {args.max_size} МБ:")
                logger.info(f"   • Рекомендуемый битрейт: {optimal_bitrate} kbps")
                logger.info(f"   • Ожидаемое сжатие: ~{((info['size_mb'] - args.max_size) / info['size_mb'] * 100):.1f}%")
        return 0
    
    # Определяем выходной файл
    if args.output:
        output_file = args.output
    else:
        input_path = Path(args.input_file)
        output_file = input_path.parent / f"{input_path.stem}_converted.mp3"
    
    # Конвертируем
    success = convert_audio(args.input_file, output_file, args.max_size, args.quality)
    
    if success:
        logger.info(f"🎉 Файл готов для транскрипции: {output_file}")
        return 0
    else:
        logger.error("❌ Конвертация не удалась")
        return 1

if __name__ == '__main__':
    exit(main())
