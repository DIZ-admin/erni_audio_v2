# pipeline/export_agent.py

import datetime as _dt
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional

class ExportAgent:
    """
    Агент для финального экспорта: поддерживаем три формата: SRT, JSON, ASS.
    Автоматически добавляет правильные расширения файлов и может создавать все форматы.
    Поддерживает проверку существующих файлов и генерацию уникальных имен.
    """
    def __init__(self, format: str = "srt", create_all_formats: bool = False,
                 overwrite_existing: bool = False, add_timestamp: bool = False):
        assert format in ("srt", "json", "ass"), f"Неподдерживаемый формат: {format}"
        self.format = format
        self.create_all_formats = create_all_formats
        self.overwrite_existing = overwrite_existing
        self.add_timestamp = add_timestamp
        self.logger = logging.getLogger(__name__)

    def _ts_srt(self, sec: float) -> str:
        td = _dt.timedelta(seconds=sec)
        h, r = divmod(td.seconds, 3600)
        m, s = divmod(r, 60)
        ms = int(td.microseconds / 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _ts_ass(self, sec: float) -> str:
        td = _dt.timedelta(seconds=sec)
        h, r = divmod(td.seconds, 3600)
        m, s = divmod(r, 60)
        cs = int(td.microseconds / 10_000)  # centiseconds
        return f"{h:d}:{m:02}:{s:02}.{cs:02}"

    def _generate_unique_filename(self, output_path: Path, format: str) -> Path:
        """
        Генерирует уникальное имя файла, избегая перезаписи существующих файлов.
        Добавляет временную метку или числовой суффикс при необходимости.
        """
        corrected_path = self._ensure_correct_extension(output_path, format)

        # Если перезапись разрешена, возвращаем исходный путь
        if self.overwrite_existing:
            return corrected_path

        # Если файл не существует, возвращаем исходный путь
        if not corrected_path.exists():
            return corrected_path

        # Генерируем уникальное имя
        base_path = corrected_path.with_suffix('')
        extension = corrected_path.suffix

        if self.add_timestamp:
            # Добавляем временную метку
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            unique_path = Path(f"{base_path}_{timestamp}{extension}")

            # Если файл с временной меткой тоже существует, добавляем счетчик
            counter = 1
            while unique_path.exists():
                unique_path = Path(f"{base_path}_{timestamp}_{counter:03d}{extension}")
                counter += 1
        else:
            # Добавляем числовой суффикс
            counter = 1
            unique_path = Path(f"{base_path}_{counter:03d}{extension}")
            while unique_path.exists():
                counter += 1
                unique_path = Path(f"{base_path}_{counter:03d}{extension}")

        self.logger.info(f"📝 Файл {corrected_path} уже существует, создаю уникальное имя: {unique_path}")
        return unique_path

    def _ensure_correct_extension(self, output_path: Path, format: str) -> Path:
        """
        Обеспечивает правильное расширение файла для указанного формата.
        Если файл уже имеет правильное расширение, возвращает его как есть.
        Если нет - добавляет правильное расширение.
        """
        format_extensions = {
            "srt": ".srt",
            "json": ".json",
            "ass": ".ass"
        }

        expected_ext = format_extensions[format]

        # Если файл уже имеет правильное расширение
        if output_path.suffix.lower() == expected_ext:
            return output_path

        # Если файл имеет другое расширение или не имеет расширения
        if output_path.suffix:
            # Заменяем существующее расширение
            return output_path.with_suffix(expected_ext)
        else:
            # Добавляем расширение к файлу без расширения
            return Path(str(output_path) + expected_ext)

    def write_json(self, segs: List[Dict], outfile: Path):
        outfile.write_text(json.dumps(segs, indent=2, ensure_ascii=False))

    def write_srt(self, segs: List[Dict], outfile: Path):
        with open(outfile, "w", encoding="utf-8") as f:
            for idx, s in enumerate(segs, 1):
                f.write(f"{idx}\n{self._ts_srt(s['start'])} --> {self._ts_srt(s['end'])}\n")
                f.write(f"{s['speaker']}: {s['text']}\n\n")

    def write_ass(self, segs: List[Dict], outfile: Path):
        header = (
            "[Script Info]\n"
            "Title: speech_pipeline export\n"
            "ScriptType: v4.00+\n"
            "Collisions: Normal\n"
            "PlayResX: 384\n"
            "PlayResY: 288\n"
            "[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
            "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
            "Alignment,MarginL,MarginR,MarginV,Encoding\n"
            "Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
            "-1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(header)
            for s in segs:
                f.write(
                    f"Dialogue: 0,{self._ts_ass(s['start'])},{self._ts_ass(s['end'])},"
                    f"Default,{s['speaker']},0,0,0,,{s['text']}\n"
                )

    def run(self, merged: List[Dict], output_path: Path):
        """
        Экспортирует данные в указанный формат с автоматическим добавлением расширений.
        Если create_all_formats=True, создает файлы во всех поддерживаемых форматах.
        """
        created_files = []

        if self.create_all_formats:
            # Создаем файлы во всех форматах
            base_path = output_path.with_suffix('')  # Убираем расширение

            formats_to_create = ["srt", "json", "ass"]
            for fmt in formats_to_create:
                fmt_path = self._generate_unique_filename(base_path, fmt)
                self._export_single_format(merged, fmt_path, fmt)
                created_files.append(fmt_path)

            self.logger.info(f"✅ ExportAgent: Созданы файлы во всех форматах: {[str(f) for f in created_files]}")
        else:
            # Создаем файл только в указанном формате
            unique_path = self._generate_unique_filename(output_path, self.format)
            self._export_single_format(merged, unique_path, self.format)
            created_files.append(unique_path)

            self.logger.info(f"✅ ExportAgent: Создан файл в формате {self.format.upper()}: {unique_path}")

        return created_files

    def _export_single_format(self, merged: List[Dict], output_path: Path, format: str):
        """Экспортирует данные в один конкретный формат"""
        if format == "srt":
            self.write_srt(merged, output_path)
        elif format == "json":
            self.write_json(merged, output_path)
        elif format == "ass":
            self.write_ass(merged, output_path)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")
