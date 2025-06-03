"""
WER Evaluator - Модуль для оценки качества транскрипции
Вычисляет WER (Word Error Rate) и CER (Character Error Rate) для сравнения моделей
"""

import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TranscriptionResult:
    """Результат транскрипции для оценки"""
    model_name: str
    segments: List[Dict]
    processing_time: float
    estimated_cost: str
    success: bool
    error: Optional[str] = None
    
    @property
    def full_text(self) -> str:
        """Полный текст транскрипции"""
        if not self.segments:
            return ""
        return " ".join(seg.get("text", "") for seg in self.segments).strip()


@dataclass
class QualityMetrics:
    """Метрики качества транскрипции"""
    wer: float  # Word Error Rate (0.0 - 1.0)
    cer: float  # Character Error Rate (0.0 - 1.0)
    word_accuracy: float  # 1 - WER
    char_accuracy: float  # 1 - CER
    reference_words: int
    hypothesis_words: int
    reference_chars: int
    hypothesis_chars: int
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь для сериализации"""
        return {
            "wer": round(self.wer, 4),
            "cer": round(self.cer, 4),
            "word_accuracy": round(self.word_accuracy, 4),
            "char_accuracy": round(self.char_accuracy, 4),
            "reference_words": self.reference_words,
            "hypothesis_words": self.hypothesis_words,
            "reference_chars": self.reference_chars,
            "hypothesis_chars": self.hypothesis_chars
        }


class WERCalculator:
    """Калькулятор для вычисления WER и CER"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def normalize_text(self, text: str) -> str:
        """
        Нормализация текста для сравнения
        
        Args:
            text: Исходный текст
            
        Returns:
            Нормализованный текст
        """
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Удаляем знаки препинания
        text = re.sub(r'[^\w\s]', '', text)
        
        # Удаляем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def calculate_edit_distance(self, ref_tokens: List[str], hyp_tokens: List[str]) -> Tuple[int, List[List[int]]]:
        """
        Вычисляет расстояние редактирования (Левенштейна) между двумя последовательностями токенов
        
        Args:
            ref_tokens: Эталонные токены
            hyp_tokens: Гипотетические токены
            
        Returns:
            Tuple[расстояние_редактирования, матрица_dp]
        """
        m, n = len(ref_tokens), len(hyp_tokens)
        
        # Создаем матрицу динамического программирования
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        # Инициализация
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        # Заполнение матрицы
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if ref_tokens[i-1] == hyp_tokens[j-1]:
                    dp[i][j] = dp[i-1][j-1]  # Совпадение
                else:
                    dp[i][j] = 1 + min(
                        dp[i-1][j],    # Удаление
                        dp[i][j-1],    # Вставка
                        dp[i-1][j-1]   # Замена
                    )
        
        return dp[m][n], dp
    
    def calculate_wer(self, reference: str, hypothesis: str) -> float:
        """
        Вычисляет WER (Word Error Rate)
        
        Args:
            reference: Эталонный текст
            hypothesis: Гипотетический текст
            
        Returns:
            WER значение (0.0 - 1.0)
        """
        # Нормализуем тексты
        ref_normalized = self.normalize_text(reference)
        hyp_normalized = self.normalize_text(hypothesis)
        
        # Разбиваем на слова
        ref_words = ref_normalized.split()
        hyp_words = hyp_normalized.split()
        
        if not ref_words:
            return 1.0 if hyp_words else 0.0
        
        # Вычисляем расстояние редактирования
        edit_distance, _ = self.calculate_edit_distance(ref_words, hyp_words)
        
        # WER = количество ошибок / количество слов в эталоне
        wer = edit_distance / len(ref_words)
        
        return min(wer, 1.0)  # Ограничиваем максимальным значением 1.0
    
    def calculate_cer(self, reference: str, hypothesis: str) -> float:
        """
        Вычисляет CER (Character Error Rate)
        
        Args:
            reference: Эталонный текст
            hypothesis: Гипотетический текст
            
        Returns:
            CER значение (0.0 - 1.0)
        """
        # Нормализуем тексты
        ref_normalized = self.normalize_text(reference)
        hyp_normalized = self.normalize_text(hypothesis)
        
        # Разбиваем на символы
        ref_chars = list(ref_normalized.replace(' ', ''))  # Убираем пробелы для CER
        hyp_chars = list(hyp_normalized.replace(' ', ''))
        
        if not ref_chars:
            return 1.0 if hyp_chars else 0.0
        
        # Вычисляем расстояние редактирования
        edit_distance, _ = self.calculate_edit_distance(ref_chars, hyp_chars)
        
        # CER = количество ошибок / количество символов в эталоне
        cer = edit_distance / len(ref_chars)
        
        return min(cer, 1.0)  # Ограничиваем максимальным значением 1.0
    
    def calculate_metrics(self, reference: str, hypothesis: str) -> QualityMetrics:
        """
        Вычисляет все метрики качества
        
        Args:
            reference: Эталонный текст
            hypothesis: Гипотетический текст
            
        Returns:
            QualityMetrics объект с метриками
        """
        # Нормализуем тексты
        ref_normalized = self.normalize_text(reference)
        hyp_normalized = self.normalize_text(hypothesis)
        
        # Подсчитываем слова и символы
        ref_words = ref_normalized.split()
        hyp_words = hyp_normalized.split()
        ref_chars = list(ref_normalized.replace(' ', ''))
        hyp_chars = list(hyp_normalized.replace(' ', ''))
        
        # Вычисляем WER и CER
        wer = self.calculate_wer(reference, hypothesis)
        cer = self.calculate_cer(reference, hypothesis)
        
        return QualityMetrics(
            wer=wer,
            cer=cer,
            word_accuracy=1.0 - wer,
            char_accuracy=1.0 - cer,
            reference_words=len(ref_words),
            hypothesis_words=len(hyp_words),
            reference_chars=len(ref_chars),
            hypothesis_chars=len(hyp_chars)
        )


class WERTranscriptionEvaluator:
    """Основной класс для оценки качества транскрипции"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.calculator = WERCalculator()
        self.results = {}
        
    def evaluate_transcription(self, 
                             reference_text: str, 
                             transcription_result: TranscriptionResult) -> Dict:
        """
        Оценивает качество одной транскрипции
        
        Args:
            reference_text: Эталонный текст
            transcription_result: Результат транскрипции
            
        Returns:
            Словарь с результатами оценки
        """
        if not transcription_result.success:
            return {
                "model": transcription_result.model_name,
                "success": False,
                "error": transcription_result.error,
                "processing_time": transcription_result.processing_time,
                "estimated_cost": transcription_result.estimated_cost
            }
        
        # Вычисляем метрики качества
        metrics = self.calculator.calculate_metrics(reference_text, transcription_result.full_text)
        
        result = {
            "model": transcription_result.model_name,
            "success": True,
            "processing_time": transcription_result.processing_time,
            "estimated_cost": transcription_result.estimated_cost,
            "segments_count": len(transcription_result.segments),
            "quality_metrics": metrics.to_dict(),
            "transcribed_text": transcription_result.full_text[:200] + "..." if len(transcription_result.full_text) > 200 else transcription_result.full_text
        }
        
        self.logger.info(f"📊 {transcription_result.model_name}: WER={metrics.wer:.3f}, CER={metrics.cer:.3f}, время={transcription_result.processing_time:.2f}с")
        
        return result
    
    def save_results(self, results: Dict, output_path: Path) -> None:
        """
        Сохраняет результаты оценки в JSON файл
        
        Args:
            results: Результаты оценки
            output_path: Путь для сохранения
        """
        # Создаем директорию если не существует
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Добавляем метаданные
        results_with_metadata = {
            "evaluation_metadata": {
                "timestamp": datetime.now().isoformat(),
                "evaluator_version": "1.0.0",
                "total_models_tested": len([r for r in results.get("model_results", {}).values() if r.get("success", False)])
            },
            **results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_with_metadata, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"💾 Результаты оценки сохранены: {output_path}")
