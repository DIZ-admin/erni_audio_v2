# pipeline/merge_agent.py

from typing import List, Dict, Any

class MergeAgent:
    """
    Агент для грубой «склейки» диаризации и транскрипции.
    По каждому asr-сегменту находит matching diar-сегмент (по start/end)
    и проставляет spk. Вернёт List[{"start", "end", "speaker", "text"}].
    """
    def __init__(self):
        pass

    def run(self, diar: List[Dict[str, Any]], asr: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged = []

        for seg in asr:
            # Найти подходящий диаризационный сегмент
            best_speaker = "UNK"
            best_overlap = 0

            for diar_seg in diar:
                # Проверяем пересечение сегментов
                overlap_start = max(seg["start"], diar_seg["start"])
                overlap_end = min(seg["end"], diar_seg["end"])
                overlap = max(0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = diar_seg["speaker"]

            merged.append({
                "start": seg["start"],
                "end": seg["end"],
                "speaker": best_speaker,
                "text": seg["text"].strip()
            })
        return merged
