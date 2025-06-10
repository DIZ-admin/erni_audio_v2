# pipeline/qc_agent.py

import json
import logging
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydub import AudioSegment
from dataclasses import dataclass

TARGET_SR = 16_000

@dataclass
class QualityMetrics:
    """Метрики качества для результатов обработки"""
    total_segments: int
    total_duration: float
    speakers_count: int
    average_segment_duration: float
    min_segment_duration: float
    max_segment_duration: float
    speaker_distribution: Dict[str, float]
    silence_ratio: float
    quality_score: float
    issues: List[str]

@dataclass
class ValidationResult:
    """Результат валидации данных"""
    is_valid: bool
    quality_metrics: QualityMetrics
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]

class QCAgent:
    """
    Расширенный агент контроля качества для результатов диаризации и транскрипции.

    Функции:
    - Валидация временных меток
    - Анализ качества диаризации
    - Проверка качества транскрипции
    - Создание voiceprint'ов
    - Генерация отчетов о качестве
    """

    def __init__(self, manifest_dir: Optional[Path] = None, per_speaker_sec: int = 30,
                 min_segment_duration: float = 0.5, max_silence_gap: float = 5.0):
        """
        Args:
            manifest_dir: Путь к папке для сохранения WAV-эталонов voiceprints
            per_speaker_sec: Количество секунд речи для каждого спикера
            min_segment_duration: Минимальная длительность сегмента (сек)
            max_silence_gap: Максимальный разрыв между сегментами (сек)
        """
        self.manifest_dir = manifest_dir
        self.per_speaker_sec = per_speaker_sec
        self.min_segment_duration = min_segment_duration
        self.max_silence_gap = max_silence_gap
        self.logger = logging.getLogger(__name__)

    def validate_timestamps(self, segments: List[Dict[str, Any]]) -> List[str]:
        """
        Валидирует временные метки в сегментах

        Args:
            segments: Список сегментов с временными метками

        Returns:
            Список найденных проблем
        """
        issues = []

        if not segments:
            issues.append("Нет сегментов для валидации")
            return issues

        # Проверяем каждый сегмент
        for i, segment in enumerate(segments):
            # Проверяем наличие обязательных полей
            if 'start' not in segment or 'end' not in segment:
                issues.append(f"Сегмент {i}: отсутствуют временные метки")
                continue

            start = segment['start']
            end = segment['end']

            # Проверяем корректность временных меток
            if start < 0:
                issues.append(f"Сегмент {i}: отрицательное время начала ({start})")

            if end <= start:
                issues.append(f"Сегмент {i}: время окончания <= времени начала ({start}-{end})")

            if end - start < self.min_segment_duration:
                issues.append(f"Сегмент {i}: слишком короткий ({end - start:.2f}с)")

            # Проверяем пересечения с предыдущим сегментом
            if i > 0:
                prev_end = segments[i-1]['end']
                if start < prev_end:
                    issues.append(f"Сегменты {i-1} и {i}: пересечение временных меток")
                elif start - prev_end > self.max_silence_gap:
                    issues.append(f"Сегменты {i-1} и {i}: большой разрыв ({start - prev_end:.2f}с)")

        return issues

    def analyze_diarization_quality(self, diar_segments: List[Dict[str, Any]]) -> QualityMetrics:
        """
        Анализирует качество диаризации

        Args:
            diar_segments: Сегменты диаризации

        Returns:
            Метрики качества диаризации
        """
        if not diar_segments:
            return QualityMetrics(
                total_segments=0, total_duration=0.0, speakers_count=0,
                average_segment_duration=0.0, min_segment_duration=0.0, max_segment_duration=0.0,
                speaker_distribution={}, silence_ratio=1.0, quality_score=0.0,
                issues=["Нет сегментов диаризации"]
            )

        # Базовые метрики
        total_segments = len(diar_segments)
        durations = [seg['end'] - seg['start'] for seg in diar_segments]
        total_duration = sum(durations)

        # Анализ спикеров
        speakers = set(seg.get('speaker', 'UNKNOWN') for seg in diar_segments)
        speakers_count = len(speakers)

        # Распределение времени по спикерам
        speaker_time = {}
        for seg in diar_segments:
            speaker = seg.get('speaker', 'UNKNOWN')
            duration = seg['end'] - seg['start']
            speaker_time[speaker] = speaker_time.get(speaker, 0) + duration

        speaker_distribution = {
            speaker: time / total_duration if total_duration > 0 else 0
            for speaker, time in speaker_time.items()
        }

        # Статистика длительности сегментов
        average_segment_duration = statistics.mean(durations) if durations else 0
        min_segment_duration = min(durations) if durations else 0
        max_segment_duration = max(durations) if durations else 0

        # Анализ пауз (упрощенный)
        total_audio_time = max(seg['end'] for seg in diar_segments) if diar_segments else 0
        silence_ratio = max(0, (total_audio_time - total_duration) / total_audio_time) if total_audio_time > 0 else 0

        # Оценка качества (0-1)
        quality_score = self._calculate_quality_score(
            speakers_count, average_segment_duration, silence_ratio, speaker_distribution
        )

        # Выявление проблем
        issues = self.validate_timestamps(diar_segments)

        # Дополнительные проверки качества
        if speakers_count < 2:
            issues.append("Обнаружен только один спикер")
        elif speakers_count > 10:
            issues.append(f"Слишком много спикеров ({speakers_count})")

        if average_segment_duration < 1.0:
            issues.append("Слишком короткие сегменты в среднем")

        if silence_ratio > 0.5:
            issues.append("Слишком много пауз в записи")

        # Проверяем баланс спикеров
        if speaker_distribution:
            max_speaker_ratio = max(speaker_distribution.values())
            if max_speaker_ratio > 0.8:
                issues.append("Один спикер доминирует в записи")

        return QualityMetrics(
            total_segments=total_segments,
            total_duration=total_duration,
            speakers_count=speakers_count,
            average_segment_duration=average_segment_duration,
            min_segment_duration=min_segment_duration,
            max_segment_duration=max_segment_duration,
            speaker_distribution=speaker_distribution,
            silence_ratio=silence_ratio,
            quality_score=quality_score,
            issues=issues
        )

    def _calculate_quality_score(self, speakers_count: int, avg_duration: float,
                               silence_ratio: float, speaker_distribution: Dict[str, float]) -> float:
        """Вычисляет общую оценку качества (0-1)"""
        score = 1.0

        # Штраф за неоптимальное количество спикеров
        if speakers_count < 2:
            score *= 0.5
        elif speakers_count > 6:
            score *= 0.8

        # Штраф за слишком короткие сегменты
        if avg_duration < 1.0:
            score *= 0.7
        elif avg_duration < 2.0:
            score *= 0.9

        # Штраф за много пауз
        if silence_ratio > 0.3:
            score *= (1.0 - silence_ratio)

        # Штраф за несбалансированность спикеров
        if speaker_distribution:
            max_ratio = max(speaker_distribution.values())
            if max_ratio > 0.7:
                score *= (1.0 - (max_ratio - 0.7) * 2)

        return max(0.0, min(1.0, score))

    def validate_transcription_quality(self, merged_segments: List[Dict[str, Any]]) -> List[str]:
        """
        Валидирует качество транскрипции

        Args:
            merged_segments: Объединенные сегменты с транскрипцией

        Returns:
            Список найденных проблем
        """
        issues = []

        if not merged_segments:
            issues.append("Нет сегментов транскрипции")
            return issues

        total_text_length = 0
        empty_segments = 0

        for i, segment in enumerate(merged_segments):
            text = segment.get('text', '').strip()

            if not text:
                empty_segments += 1
                issues.append(f"Сегмент {i}: пустая транскрипция")
            else:
                total_text_length += len(text)

                # Проверяем на подозрительно короткий текст
                duration = segment.get('end', 0) - segment.get('start', 0)
                if duration > 5.0 and len(text) < 10:
                    issues.append(f"Сегмент {i}: слишком короткий текст для длительности {duration:.1f}с")

                # Проверяем на повторяющийся текст
                if text.lower() in ['[music]', '[silence]', '[noise]', '...']:
                    issues.append(f"Сегмент {i}: нераспознанная речь ({text})")

        # Общие проверки
        if empty_segments > len(merged_segments) * 0.3:
            issues.append(f"Слишком много пустых сегментов ({empty_segments}/{len(merged_segments)})")

        if total_text_length < 100:
            issues.append("Слишком мало распознанного текста")

        return issues

    def generate_quality_report(self, validation_result: ValidationResult,
                              output_path: Optional[Path] = None) -> str:
        """
        Генерирует отчет о качестве

        Args:
            validation_result: Результат валидации
            output_path: Путь для сохранения отчета

        Returns:
            Текст отчета
        """
        metrics = validation_result.quality_metrics

        report = []
        report.append("# Отчет о качестве обработки аудио\n")

        # Общая оценка
        report.append(f"## Общая оценка качества: {metrics.quality_score:.2f}/1.00\n")

        if validation_result.is_valid:
            report.append("✅ **Статус:** Валидация пройдена\n")
        else:
            report.append("❌ **Статус:** Обнаружены проблемы\n")

        # Основные метрики
        report.append("## Основные метрики\n")
        report.append(f"- **Всего сегментов:** {metrics.total_segments}")
        report.append(f"- **Общая длительность:** {metrics.total_duration:.2f} секунд")
        report.append(f"- **Количество спикеров:** {metrics.speakers_count}")
        report.append(f"- **Средняя длительность сегмента:** {metrics.average_segment_duration:.2f} секунд")
        report.append(f"- **Коэффициент пауз:** {metrics.silence_ratio:.2%}\n")

        # Распределение по спикерам
        if metrics.speaker_distribution:
            report.append("## Распределение времени по спикерам\n")
            for speaker, ratio in sorted(metrics.speaker_distribution.items()):
                report.append(f"- **{speaker}:** {ratio:.1%} ({ratio * metrics.total_duration:.1f}с)")
            report.append("")

        # Проблемы и предупреждения
        if validation_result.errors:
            report.append("## ❌ Критические ошибки\n")
            for error in validation_result.errors:
                report.append(f"- {error}")
            report.append("")

        if validation_result.warnings:
            report.append("## ⚠️ Предупреждения\n")
            for warning in validation_result.warnings:
                report.append(f"- {warning}")
            report.append("")

        if metrics.issues:
            report.append("## 🔍 Обнаруженные проблемы\n")
            for issue in metrics.issues:
                report.append(f"- {issue}")
            report.append("")

        # Рекомендации
        if validation_result.recommendations:
            report.append("## 💡 Рекомендации\n")
            for rec in validation_result.recommendations:
                report.append(f"- {rec}")
            report.append("")

        report_text = "\n".join(report)

        # Сохраняем отчет если указан путь
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_text, encoding='utf-8')
            self.logger.info(f"📄 Отчет о качестве сохранен: {output_path}")

        return report_text

    def validate_pipeline_results(self, wav_local: Path, diar_segments: List[Dict[str, Any]],
                                merged_segments: Optional[List[Dict[str, Any]]] = None) -> ValidationResult:
        """
        Комплексная валидация результатов pipeline

        Args:
            wav_local: Путь к аудиофайлу
            diar_segments: Сегменты диаризации
            merged_segments: Объединенные сегменты с транскрипцией

        Returns:
            Результат валидации
        """
        # Анализируем качество диаризации
        quality_metrics = self.analyze_diarization_quality(diar_segments)

        # Собираем все проблемы
        all_issues = quality_metrics.issues.copy()
        warnings = []
        errors = []
        recommendations = []

        # Валидируем транскрипцию если есть
        if merged_segments:
            transcription_issues = self.validate_transcription_quality(merged_segments)
            all_issues.extend(transcription_issues)

        # Классифицируем проблемы
        for issue in all_issues:
            if any(keyword in issue.lower() for keyword in ['ошибка', 'отсутствуют', 'пересечение']):
                errors.append(issue)
            else:
                warnings.append(issue)

        # Генерируем рекомендации
        if quality_metrics.speakers_count < 2:
            recommendations.append("Проверьте настройки диаризации - возможно нужно увеличить чувствительность")

        if quality_metrics.average_segment_duration < 1.0:
            recommendations.append("Рассмотрите возможность объединения коротких сегментов")

        if quality_metrics.silence_ratio > 0.4:
            recommendations.append("Рассмотрите возможность обрезки пауз в аудио")

        if quality_metrics.speakers_count > 6:
            recommendations.append("Проверьте настройки диаризации - возможно слишком высокая чувствительность")

        # Определяем общую валидность
        is_valid = len(errors) == 0 and quality_metrics.quality_score >= 0.5

        return ValidationResult(
            is_valid=is_valid,
            quality_metrics=quality_metrics,
            recommendations=recommendations,
            warnings=warnings,
            errors=errors
        )

    def extract_voiceprints(self, wav_path: Path, diar: List[Dict[str, Any]]):
        """
        Создаёт WAV-эталоны ≤ per_speaker_sec для каждого speaker в diar.
        Улучшенная версия с дополнительной валидацией качества.
        """
        if not self.manifest_dir:
            return

        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        try:
            audio = AudioSegment.from_wav(wav_path)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки аудио {wav_path}: {e}")
            return

        manifest = {}
        grouped = {}

        # Группируем сегменты по спикерам
        for seg in diar:
            speaker = seg.get("speaker", "UNKNOWN")
            grouped.setdefault(speaker, []).append(seg)

        self.logger.info(f"🎤 Создаю voiceprints для {len(grouped)} спикеров...")

        for spk, segs in grouped.items():
            # Сортируем сегменты по качеству (длительности)
            segs_sorted = sorted(segs, key=lambda x: x["end"] - x["start"], reverse=True)

            collected = AudioSegment.empty()
            segments_used = 0

            for seg in segs_sorted:
                # Проверяем качество сегмента
                duration = seg["end"] - seg["start"]
                if duration < 0.5:  # Слишком короткий сегмент
                    continue

                try:
                    snippet = audio[int(1000 * seg["start"]) : int(1000 * seg["end"])]
                    collected += snippet
                    segments_used += 1

                    if len(collected) >= self.per_speaker_sec * 1000:
                        break
                except Exception as e:
                    self.logger.warning(f"Ошибка обработки сегмента {seg}: {e}")
                    continue

            # Проверяем минимальную длительность
            if len(collected) < 5_000:  # Минимум 5 секунд
                self.logger.warning(f"⚠️ Недостаточно данных для {spk}: {len(collected)/1000:.1f}с")
                continue

            # Сохраняем voiceprint
            out_file = self.manifest_dir / f"{spk}.wav"
            try:
                collected.set_frame_rate(TARGET_SR).set_channels(1).export(out_file, format="wav")
                manifest[spk] = {
                    "file": out_file.as_posix(),
                    "duration": len(collected) / 1000,
                    "segments_used": segments_used,
                    "quality": "good" if len(collected) >= 10_000 else "acceptable"
                }
                self.logger.info(f"💾 Voiceprint сохранен: {spk} → {out_file} ({len(collected)/1000:.1f}с)")
            except Exception as e:
                self.logger.error(f"Ошибка сохранения voiceprint для {spk}: {e}")

        # Сохраняем манифест
        if manifest:
            manifest_path = self.manifest_dir / "manifest.json"
            try:
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
                self.logger.info(f"📄 Манифест сохранен: {manifest_path}")
            except Exception as e:
                self.logger.error(f"Ошибка сохранения манифеста: {e}")
        else:
            self.logger.warning("⚠️ Не удалось создать ни одного voiceprint")

    def run(self, wav_local: Path, diar: List[Dict[str, Any]],
            merged_segments: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Основной метод QC агента с расширенной функциональностью

        Args:
            wav_local: Путь к локальному WAV файлу
            diar: Сегменты диаризации
            merged_segments: Объединенные сегменты с транскрипцией (опционально)

        Returns:
            Обработанные сегменты или пустой список если создавались voiceprints
        """
        self.logger.info(f"🔍 QC Agent: анализирую качество результатов...")

        # Выполняем комплексную валидацию
        validation_result = self.validate_pipeline_results(wav_local, diar, merged_segments)

        # Логируем результаты валидации
        if validation_result.is_valid:
            self.logger.info(f"✅ Валидация пройдена (качество: {validation_result.quality_metrics.quality_score:.2f})")
        else:
            self.logger.warning(f"⚠️ Обнаружены проблемы качества (оценка: {validation_result.quality_metrics.quality_score:.2f})")
            for error in validation_result.errors:
                self.logger.error(f"❌ {error}")
            for warning in validation_result.warnings:
                self.logger.warning(f"⚠️ {warning}")

        # Сохраняем отчет о качестве
        if wav_local.parent.name == "interim" or "interim" in str(wav_local):
            report_dir = Path("data/interim")
        else:
            report_dir = wav_local.parent

        report_path = report_dir / f"{wav_local.stem}_quality_report.md"
        self.generate_quality_report(validation_result, report_path)

        # Создаем voiceprints если требуется
        if self.manifest_dir:
            self.logger.info("🎤 Создаю voiceprints...")
            self.extract_voiceprints(wav_local, diar)
            return []  # Сигнал завершения pipeline
        else:
            # Возвращаем результаты для дальнейшей обработки
            return merged_segments if merged_segments else diar

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
