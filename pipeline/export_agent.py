# pipeline/export_agent.py

import datetime as _dt
import json
from pathlib import Path
from typing import List, Dict

class ExportAgent:
    """
    Агент для финального экспорта: поддерживаем три формата: SRT, JSON, ASS.
    """
    def __init__(self, format: str = "srt"):
        assert format in ("srt", "json", "ass"), "Неподдерживаемый формат"
        self.format = format

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
        В зависимости от self.format выбрасывает SRT, JSON или ASS.
        """
        if self.format == "srt":
            self.write_srt(merged, output_path)
        elif self.format == "json":
            self.write_json(merged, output_path)
        else:  # "ass"
            self.write_ass(merged, output_path)
        print(f"✅  ExportAgent: Done → {output_path}")
