# pipeline/qc_agent.py

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydub import AudioSegment

TARGET_SR = 16_000

class QCAgent:
    """
    Агент для «качества» и подготовки эталонов голосовых отпечатков.
    Функция run() проверяет, если передан флаг --voiceprints-dir, то
    режет WAV по 30 сек «чистой речи» для каждого SPEAKER_XX → voiceprints/*.wav.
    Иначе просто возвращает тот же raw_diar далее, без изменений.
    """

    def __init__(self, manifest_dir: Optional[Path] = None, per_speaker_sec: int = 30):
        """
        :param manifest_dir: путь к папке, куда складывать WAV-эталоны (voiceprints/).
                             Если None, QCAgent ничего не сохраняет и просто возвращает raw_diar.
        :param per_speaker_sec: сколько секунд речи собрать для каждого спикера (≤ 30).
        """
        self.manifest_dir = manifest_dir
        self.per_speaker_sec = per_speaker_sec

    def extract_voiceprints(self, wav_path: Path, diar: List[Dict[str, Any]]):
        """
        Создаёт WAV-эталоны ≤ per_speaker_sec для каждого speaker в diar.
        Аналогично предыдущему extract_voiceprints, только называем Skeleton "Agent".
        """
        if not self.manifest_dir:
            return

        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        audio = AudioSegment.from_wav(wav_path)
        manifest = {}
        grouped = {}
        for seg in diar:
            grouped.setdefault(seg["speaker"], []).append(seg)

        for spk, segs in grouped.items():
            collected = AudioSegment.empty()
            for seg in segs:
                snippet = audio[int(1000 * seg["start"]) : int(1000 * seg["end"])]
                collected += snippet
                if len(collected) >= self.per_speaker_sec * 1000:
                    break
            if len(collected) < 5_000:
                continue

            out_file = self.manifest_dir / f"{spk}.wav"
            collected.set_frame_rate(TARGET_SR).set_channels(1).export(out_file, format="wav")
            manifest[spk] = out_file.as_posix()
            print(f"💾  QCAgent: saved voiceprint → {out_file}")

        manifest_path = self.manifest_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        print(f"📄  QCAgent: manifest written → {manifest_path}")

    def run(self, wav_local: Path, diar: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Если manifest_dir задан, режем WAV на эталоны и выходим (возвращаем [], потому что
        дальнейшие агенты не должны запускаться). Если manifest_dir = None, просто передаём diar дальше.
        """
        if self.manifest_dir:
            self.extract_voiceprints(wav_local, diar)
            return []  # сигнал, что pipeline на этом шаге завершился
        else:
            return diar  # передаём «вперед» без изменений
