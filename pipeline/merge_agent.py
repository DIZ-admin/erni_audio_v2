# pipeline/merge_agent.py

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from .base_agent import BaseAgent
from .validation_mixin import ValidationMixin


@dataclass
class MergeMetrics:
    """Метрики качества слияния"""
    total_asr_segments: int
    total_diar_segments: int
    merged_segments: int
    unmatched_asr_segments: int
    unmatched_diar_segments: int
    average_overlap_ratio: float
    speaker_distribution: Dict[str, int]
    confidence_score: float


class MergeAgent(BaseAgent, ValidationMixin):
    """
    Улучшенный агент для слияния диаризации и транскрипции.

    Поддерживает:
    - Множественные алгоритмы слияния
    - Обработка перекрывающихся сегментов
    - Валидация временных меток
    - Метрики качества слияния
    - Обработка пауз и коротких сегментов
    """

    def __init__(self, merge_strategy: str = "best_overlap",
                 min_overlap_threshold: float = 0.1,
                 confidence_threshold: float = 0.5):
        """
        Args:
            merge_strategy: Стратегия слияния ("best_overlap", "weighted", "majority_vote")
            min_overlap_threshold: Минимальное пересечение для считания совпадения
            confidence_threshold: Порог уверенности для принятия решения
        """
        # Инициализация базовых классов
        BaseAgent.__init__(self, name="MergeAgent")
        ValidationMixin.__init__(self)

        self.merge_strategy = merge_strategy
        self.min_overlap_threshold = min_overlap_threshold
        self.confidence_threshold = confidence_threshold

        self.log_with_emoji("info", "🔗", f"Инициализирован с стратегией: {merge_strategy}")

    def calculate_overlap(self, seg1: Dict[str, Any], seg2: Dict[str, Any]) -> Tuple[float, float]:
        """
        Вычисляет пересечение между двумя сегментами

        Args:
            seg1: Первый сегмент
            seg2: Второй сегмент

        Returns:
            Кортеж (абсолютное_пересечение, относительное_пересечение)
        """
        overlap_start = max(seg1["start"], seg2["start"])
        overlap_end = min(seg1["end"], seg2["end"])
        overlap_duration = max(0, overlap_end - overlap_start)

        # Относительное пересечение к длительности ASR сегмента
        asr_duration = seg1["end"] - seg1["start"]
        overlap_ratio = overlap_duration / asr_duration if asr_duration > 0 else 0

        return overlap_duration, overlap_ratio

    def find_best_speaker_overlap(self, asr_seg: Dict[str, Any],
                                diar_segments: List[Dict[str, Any]]) -> Tuple[str, float, float]:
        """
        Находит лучшего спикера по максимальному пересечению

        Args:
            asr_seg: ASR сегмент
            diar_segments: Список диаризационных сегментов

        Returns:
            Кортеж (speaker, overlap_duration, confidence)
        """
        best_speaker = "UNK"
        best_overlap = 0
        best_ratio = 0

        for diar_seg in diar_segments:
            overlap_duration, overlap_ratio = self.calculate_overlap(asr_seg, diar_seg)

            if overlap_duration > best_overlap and overlap_ratio >= self.min_overlap_threshold:
                best_overlap = overlap_duration
                best_ratio = overlap_ratio
                best_speaker = diar_seg["speaker"]

        # Уверенность основана на относительном пересечении
        confidence = min(1.0, best_ratio * 2)  # Масштабируем до 1.0

        return best_speaker, best_overlap, confidence

    def find_speaker_weighted(self, asr_seg: Dict[str, Any],
                            diar_segments: List[Dict[str, Any]]) -> Tuple[str, float]:
        """
        Находит спикера по взвешенному голосованию

        Args:
            asr_seg: ASR сегмент
            diar_segments: Список диаризационных сегментов

        Returns:
            Кортеж (speaker, confidence)
        """
        speaker_weights = {}
        total_weight = 0

        for diar_seg in diar_segments:
            overlap_duration, overlap_ratio = self.calculate_overlap(asr_seg, diar_seg)

            if overlap_ratio >= self.min_overlap_threshold:
                speaker = diar_seg["speaker"]
                weight = overlap_duration * overlap_ratio  # Комбинированный вес

                speaker_weights[speaker] = speaker_weights.get(speaker, 0) + weight
                total_weight += weight

        if not speaker_weights:
            return "UNK", 0.0

        # Находим спикера с максимальным весом
        best_speaker = max(speaker_weights.items(), key=lambda x: x[1])
        confidence = best_speaker[1] / total_weight if total_weight > 0 else 0

        return best_speaker[0], confidence

    def find_speaker_majority_vote(self, asr_seg: Dict[str, Any],
                                 diar_segments: List[Dict[str, Any]]) -> Tuple[str, float]:
        """
        Находит спикера по мажоритарному голосованию

        Args:
            asr_seg: ASR сегмент
            diar_segments: Список диаризационных сегментов

        Returns:
            Кортеж (speaker, confidence)
        """
        speaker_votes = {}
        total_votes = 0

        # Разбиваем ASR сегмент на мелкие части для голосования
        segment_duration = asr_seg["end"] - asr_seg["start"]
        num_samples = max(1, int(segment_duration * 10))  # 10 сэмплов в секунду

        for i in range(num_samples):
            sample_time = asr_seg["start"] + (i / num_samples) * segment_duration

            # Находим спикера в этой точке времени
            for diar_seg in diar_segments:
                if diar_seg["start"] <= sample_time <= diar_seg["end"]:
                    speaker = diar_seg["speaker"]
                    speaker_votes[speaker] = speaker_votes.get(speaker, 0) + 1
                    total_votes += 1
                    break

        if not speaker_votes:
            return "UNK", 0.0

        # Находим спикера с максимальным количеством голосов
        best_speaker = max(speaker_votes.items(), key=lambda x: x[1])
        confidence = best_speaker[1] / total_votes if total_votes > 0 else 0

        return best_speaker[0], confidence

    def merge_segments(self, asr_seg: Dict[str, Any],
                      diar_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Объединяет ASR сегмент с диаризационными данными

        Args:
            asr_seg: ASR сегмент
            diar_segments: Список диаризационных сегментов

        Returns:
            Объединенный сегмент
        """
        # Выбираем стратегию слияния
        if self.merge_strategy == "best_overlap":
            speaker, overlap, confidence = self.find_best_speaker_overlap(asr_seg, diar_segments)
        elif self.merge_strategy == "weighted":
            speaker, confidence = self.find_speaker_weighted(asr_seg, diar_segments)
        elif self.merge_strategy == "majority_vote":
            speaker, confidence = self.find_speaker_majority_vote(asr_seg, diar_segments)
        else:
            # Fallback к простому алгоритму
            speaker, overlap, confidence = self.find_best_speaker_overlap(asr_seg, diar_segments)

        # Если уверенность слишком низкая, помечаем как неопределенного
        if confidence < self.confidence_threshold:
            speaker = f"UNK_{speaker}" if speaker != "UNK" else "UNK"

        merged_segment = {
            "start": asr_seg["start"],
            "end": asr_seg["end"],
            "speaker": speaker,
            "text": asr_seg["text"].strip(),
            "confidence": confidence
        }

        # Добавляем дополнительные метаданные если есть
        if "language" in asr_seg:
            merged_segment["language"] = asr_seg["language"]

        if "words" in asr_seg:
            merged_segment["words"] = asr_seg["words"]

        return merged_segment

    def validate_segment(self, segment: Dict[str, Any], segment_index: int = 0) -> List[str]:
        """
        Валидация одного сегмента.

        Args:
            segment: Сегмент для валидации
            segment_index: Индекс сегмента для сообщений об ошибках

        Returns:
            Список найденных проблем
        """
        issues = []

        # Проверяем обязательные поля
        required_fields = ["start", "end"]
        for field in required_fields:
            if field not in segment:
                issues.append(f"Сегмент {segment_index}: отсутствует поле '{field}'")

        if issues:  # Если нет базовых полей, дальше не проверяем
            return issues

        # Проверяем типы данных
        if not isinstance(segment["start"], (int, float)):
            issues.append(f"Сегмент {segment_index}: 'start' должно быть числом")

        if not isinstance(segment["end"], (int, float)):
            issues.append(f"Сегмент {segment_index}: 'end' должно быть числом")

        # Проверяем корректность временных меток
        if isinstance(segment["start"], (int, float)) and isinstance(segment["end"], (int, float)):
            if segment["start"] < 0:
                issues.append(f"Сегмент {segment_index}: отрицательное время начала ({segment['start']})")

            if segment["end"] < 0:
                issues.append(f"Сегмент {segment_index}: отрицательное время окончания ({segment['end']})")

            if segment["start"] >= segment["end"]:
                issues.append(f"Сегмент {segment_index}: некорректные временные метки ({segment['start']}-{segment['end']})")

            # Проверяем разумную длительность (не более 24 часов)
            duration = segment["end"] - segment["start"]
            if duration > 24 * 3600:  # 24 часа в секундах
                issues.append(f"Сегмент {segment_index}: слишком длинный сегмент ({duration/3600:.1f}ч)")

        # Проверяем speaker ID если есть
        if "speaker" in segment:
            speaker = segment["speaker"]
            if not isinstance(speaker, str):
                issues.append(f"Сегмент {segment_index}: 'speaker' должно быть строкой")
            elif not speaker.strip():
                issues.append(f"Сегмент {segment_index}: пустой speaker ID")

        # Проверяем текст если есть
        if "text" in segment:
            text = segment["text"]
            if not isinstance(text, str):
                issues.append(f"Сегмент {segment_index}: 'text' должно быть строкой")

        return issues

    def validate_segments_overlap(self, segments: List[Dict[str, Any]]) -> List[str]:
        """
        Проверка пересечений между сегментами.

        Args:
            segments: Список сегментов для проверки

        Returns:
            Список найденных проблем с пересечениями
        """
        issues = []

        for i in range(len(segments) - 1):
            current = segments[i]
            next_seg = segments[i + 1]

            # Пропускаем сегменты без временных меток
            if not all(field in current for field in ["start", "end"]) or \
               not all(field in next_seg for field in ["start", "end"]):
                continue

            # Проверяем пересечение
            if current["end"] > next_seg["start"]:
                overlap = current["end"] - next_seg["start"]
                issues.append(
                    f"Сегменты {i} и {i+1}: пересечение {overlap:.3f}с "
                    f"({current['start']:.3f}-{current['end']:.3f} и {next_seg['start']:.3f}-{next_seg['end']:.3f})"
                )

        return issues

    def validate_segments(self, segments: List[Dict[str, Any]]) -> List[str]:
        """
        Комплексная валидация сегментов перед слиянием.

        Args:
            segments: Список сегментов для валидации

        Returns:
            Список найденных проблем
        """
        all_issues = []

        # Валидация каждого сегмента
        for i, seg in enumerate(segments):
            segment_issues = self.validate_segment(seg, i)
            all_issues.extend(segment_issues)

        # Проверка пересечений между сегментами
        overlap_issues = self.validate_segments_overlap(segments)
        all_issues.extend(overlap_issues)

        return all_issues

    def calculate_merge_metrics(self, diar: List[Dict[str, Any]],
                              asr: List[Dict[str, Any]],
                              merged: List[Dict[str, Any]]) -> MergeMetrics:
        """
        Вычисляет метрики качества слияния

        Args:
            diar: Диаризационные сегменты
            asr: ASR сегменты
            merged: Объединенные сегменты

        Returns:
            Метрики слияния
        """
        # Подсчитываем распределение спикеров
        speaker_distribution = {}
        total_overlap = 0
        confidence_sum = 0

        for seg in merged:
            speaker = seg["speaker"]
            speaker_distribution[speaker] = speaker_distribution.get(speaker, 0) + 1

            if "confidence" in seg:
                confidence_sum += seg["confidence"]

        # Вычисляем среднее пересечение
        for asr_seg in asr:
            best_overlap = 0
            for diar_seg in diar:
                overlap, _ = self.calculate_overlap(asr_seg, diar_seg)
                best_overlap = max(best_overlap, overlap)
            total_overlap += best_overlap

        avg_overlap_ratio = total_overlap / sum(seg["end"] - seg["start"] for seg in asr) if asr else 0
        avg_confidence = confidence_sum / len(merged) if merged else 0

        # Подсчитываем несопоставленные сегменты
        unmatched_asr = sum(1 for seg in merged if seg["speaker"].startswith("UNK"))
        unmatched_diar = len(diar) - len([seg for seg in merged if not seg["speaker"].startswith("UNK")])

        return MergeMetrics(
            total_asr_segments=len(asr),
            total_diar_segments=len(diar),
            merged_segments=len(merged),
            unmatched_asr_segments=unmatched_asr,
            unmatched_diar_segments=max(0, unmatched_diar),
            average_overlap_ratio=avg_overlap_ratio,
            speaker_distribution=speaker_distribution,
            confidence_score=avg_confidence
        )

    def resolve_overlaps(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Улучшенный алгоритм разрешения пересечений в сегментах

        Args:
            segments: Список сегментов с возможными пересечениями

        Returns:
            Список сегментов без пересечений
        """
        if not segments:
            return segments

        # Сортируем по времени начала
        sorted_segments = sorted(segments, key=lambda x: x["start"])
        resolved_segments = []
        overlap_count = 0

        for i, current in enumerate(sorted_segments):
            if not resolved_segments:
                resolved_segments.append(current.copy())
                continue

            previous = resolved_segments[-1]

            # Проверяем пересечение с предыдущим сегментом
            if current["start"] < previous["end"]:
                overlap_duration = previous["end"] - current["start"]
                overlap_count += 1

                # Стратегии разрешения пересечений
                if overlap_duration < 0.1:
                    # Минимальное пересечение - просто корректируем границы
                    previous["end"] = current["start"]
                    resolved_segments.append(current.copy())
                    self.log_with_emoji("debug", "🔧", f"Скорректировано минимальное пересечение: {overlap_duration:.3f}с")

                elif overlap_duration < 0.5:
                    # Небольшое пересечение - делим пополам
                    split_point = (previous["end"] + current["start"]) / 2
                    previous["end"] = split_point
                    current_copy = current.copy()
                    current_copy["start"] = split_point
                    resolved_segments.append(current_copy)
                    self.log_with_emoji("debug", "✂️", f"Разделено пересечение пополам: {overlap_duration:.3f}с")

                else:
                    # Большое пересечение - выбираем сегмент с большей уверенностью
                    prev_confidence = previous.get("confidence", 0.5)
                    curr_confidence = current.get("confidence", 0.5)

                    if curr_confidence > prev_confidence + 0.1:  # Значительно больше уверенности
                        # Заменяем предыдущий сегмент
                        resolved_segments[-1] = current.copy()
                        self.log_with_emoji("debug", "🔄", f"Заменен сегмент с меньшей уверенностью: {overlap_duration:.3f}с")
                    elif prev_confidence > curr_confidence + 0.1:
                        # Пропускаем текущий сегмент
                        self.log_with_emoji("debug", "⏭️", f"Пропущен сегмент с меньшей уверенностью: {overlap_duration:.3f}с")
                        continue
                    else:
                        # Уверенности примерно равны - укорачиваем предыдущий сегмент
                        previous["end"] = current["start"] + overlap_duration / 2
                        current_copy = current.copy()
                        current_copy["start"] = previous["end"]
                        resolved_segments.append(current_copy)
                        self.log_with_emoji("debug", "⚖️", f"Разделено пересечение по уверенности: {overlap_duration:.3f}с")
            else:
                resolved_segments.append(current.copy())

        if overlap_count > 0:
            self.log_with_emoji("info", "🔧", f"Разрешено пересечений: {overlap_count}")

        return resolved_segments

    def post_process_segments(self, merged: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Постобработка объединенных сегментов:
        - Сортировка по времени
        - Разрешение пересечений
        - Удаление пустых сегментов
        - Объединение соседних сегментов одного спикера

        Args:
            merged: Объединенные сегменты

        Returns:
            Обработанные сегменты
        """
        if not merged:
            return merged

        self.log_with_emoji("info", "🔧", "Начинаю постобработку сегментов...")

        # 1. Сортировка по времени начала
        sorted_segments = sorted(merged, key=lambda x: x["start"])

        # 2. Разрешение пересечений
        resolved_segments = self.resolve_overlaps(sorted_segments)

        # 3. Удаление пустых сегментов и очистка текста
        cleaned_segments = []
        for i, seg in enumerate(resolved_segments):
            text = seg["text"].strip()
            if not text:
                self.log_with_emoji("debug", "⏭️", f"Пропускаю пустой сегмент {i}")
                continue

            cleaned_seg = seg.copy()
            cleaned_seg["text"] = text
            cleaned_segments.append(cleaned_seg)

        # 4. Объединение соседних сегментов одного спикера
        processed = []
        for seg in cleaned_segments:
            # Объединяем соседние сегменты одного спикера
            if (processed and
                processed[-1]["speaker"] == seg["speaker"] and
                abs(processed[-1]["end"] - seg["start"]) < 1.0):  # Разрыв менее 1 секунды

                # Объединяем сегменты
                processed[-1]["end"] = seg["end"]
                processed[-1]["text"] += " " + seg["text"]

                # Обновляем уверенность (среднее)
                if "confidence" in processed[-1] and "confidence" in seg:
                    processed[-1]["confidence"] = (processed[-1]["confidence"] + seg["confidence"]) / 2

                self.log_with_emoji("debug", "🔗", f"Объединил соседние сегменты спикера {seg['speaker']}")
            else:
                # Добавляем как новый сегмент
                processed.append(seg)

        self.log_with_emoji("info", "✅", f"Постобработка завершена: {len(merged)} → {len(processed)} сегментов")
        return processed

    def run(self, diar: List[Dict[str, Any]], asr: List[Dict[str, Any]],
            enable_post_processing: bool = True,
            save_metrics: bool = False) -> List[Dict[str, Any]]:
        """
        Основной метод слияния диаризации и транскрипции

        Args:
            diar: Диаризационные сегменты
            asr: ASR сегменты
            enable_post_processing: Включить постобработку
            save_metrics: Сохранить метрики слияния

        Returns:
            Объединенные сегменты
        """
        self.start_operation("слияние")

        try:
            self.log_with_emoji("info", "🔗", f"Начинаю слияние: {len(diar)} diar + {len(asr)} asr сегментов")

            # Валидация входных данных
            diar_issues = self.validate_segments(diar)
            asr_issues = self.validate_segments(asr)

            if diar_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы в диаризации: {len(diar_issues)}")
                for issue in diar_issues[:3]:  # Показываем первые 3
                    self.log_with_emoji("warning", "   ", issue)

            if asr_issues:
                self.log_with_emoji("warning", "⚠️", f"Проблемы в ASR: {len(asr_issues)}")
                for issue in asr_issues[:3]:  # Показываем первые 3
                    self.log_with_emoji("warning", "   ", issue)

            if not asr:
                self.log_with_emoji("warning", "⚠️", "Нет ASR сегментов для слияния")
                self.end_operation("слияние", success=True)
                return []

            if not diar:
                self.log_with_emoji("warning", "⚠️", "Нет диаризационных сегментов - все спикеры будут UNK")
                result = [{"start": seg["start"], "end": seg["end"], "speaker": "UNK",
                         "text": seg["text"].strip(), "confidence": 0.0} for seg in asr]
                self.end_operation("слияние", success=True)
                return result

            # Сортируем сегменты по времени
            diar_sorted = sorted(diar, key=lambda x: x["start"])
            asr_sorted = sorted(asr, key=lambda x: x["start"])

            # Выполняем слияние
            merged = []
            for asr_seg in asr_sorted:
                merged_seg = self.merge_segments(asr_seg, diar_sorted)
                merged.append(merged_seg)

            self.log_with_emoji("info", "✅", f"Базовое слияние завершено: {len(merged)} сегментов")

            # Постобработка если включена
            if enable_post_processing:
                merged = self.post_process_segments(merged)

            # Вычисляем и логируем метрики
            metrics = self.calculate_merge_metrics(diar, asr, merged)
            self.log_with_emoji("info", "📊", "Метрики слияния:")
            self.log_with_emoji("info", "   ", f"Средняя уверенность: {metrics.confidence_score:.3f}")
            self.log_with_emoji("info", "   ", f"Несопоставленных ASR: {metrics.unmatched_asr_segments}")
            self.log_with_emoji("info", "   ", f"Распределение спикеров: {dict(list(metrics.speaker_distribution.items())[:3])}")

            # Сохраняем метрики если требуется
            if save_metrics:
                self._save_metrics(metrics)

            self.log_with_emoji("info", "🎯", f"Слияние завершено: {len(merged)} финальных сегментов")
            self.end_operation("слияние", success=True)
            return merged

        except Exception as e:
            self.end_operation("слияние", success=False)
            self.handle_error(e, "слияние", reraise=True)

    def _save_metrics(self, metrics: MergeMetrics) -> None:
        """Сохраняет метрики слияния в файл"""
        try:
            from pathlib import Path
            import json
            from datetime import datetime

            metrics_data = {
                "timestamp": datetime.now().isoformat(),
                "merge_strategy": self.merge_strategy,
                "min_overlap_threshold": self.min_overlap_threshold,
                "confidence_threshold": self.confidence_threshold,
                "metrics": {
                    "total_asr_segments": metrics.total_asr_segments,
                    "total_diar_segments": metrics.total_diar_segments,
                    "merged_segments": metrics.merged_segments,
                    "unmatched_asr_segments": metrics.unmatched_asr_segments,
                    "unmatched_diar_segments": metrics.unmatched_diar_segments,
                    "average_overlap_ratio": metrics.average_overlap_ratio,
                    "speaker_distribution": metrics.speaker_distribution,
                    "confidence_score": metrics.confidence_score
                }
            }

            metrics_dir = Path("data/interim")
            metrics_dir.mkdir(parents=True, exist_ok=True)
            metrics_file = metrics_dir / "merge_metrics.json"

            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)

            self.log_with_emoji("info", "📊", f"Метрики сохранены: {metrics_file}")

        except Exception as e:
            self.log_with_emoji("error", "❌", f"Ошибка сохранения метрик: {e}")

    def get_merge_strategies(self) -> List[str]:
        """Возвращает список доступных стратегий слияния"""
        return ["best_overlap", "weighted", "majority_vote"]

    def set_merge_strategy(self, strategy: str) -> None:
        """Устанавливает стратегию слияния"""
        if strategy not in self.get_merge_strategies():
            raise ValueError(f"Неизвестная стратегия: {strategy}")

        self.merge_strategy = strategy
        self.log_with_emoji("info", "🔄", f"Стратегия слияния изменена на: {strategy}")
