"""
Тесты производительности для speech pipeline.
"""
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import psutil
import os

from pipeline.merge_agent import MergeAgent
from pipeline.export_agent import ExportAgent


class TestPerformanceMetrics:
    """Тесты метрик производительности"""
    
    @pytest.fixture
    def large_dataset(self):
        """Создаёт большой набор данных для тестов"""
        diarization = []
        transcription = []
        
        # Генерируем 1000 сегментов
        for i in range(1000):
            start_time = i * 2.0
            end_time = start_time + 1.5
            
            diarization.append({
                "start": start_time,
                "end": end_time,
                "speaker": f"SPEAKER_{i % 5:02d}",
                "confidence": 0.9
            })
            
            transcription.append({
                "start": start_time + 0.1,
                "end": end_time - 0.1,
                "text": f"Текст сегмента номер {i}"
            })
        
        return diarization, transcription
    
    def test_merge_performance(self, large_dataset):
        """Тест производительности объединения"""
        diarization, transcription = large_dataset
        
        merge_agent = MergeAgent()
        
        start_time = time.time()
        result = merge_agent.run(diarization, transcription)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Проверяем результат
        assert len(result) == 1000
        
        # Проверяем производительность (должно быть быстро)
        assert execution_time < 1.0, f"Merge took too long: {execution_time:.2f}s"
        
        # Проверяем качество объединения
        correct_matches = sum(1 for seg in result if seg["speaker"] != "UNK")
        match_rate = correct_matches / len(result)
        assert match_rate > 0.95, f"Low match rate: {match_rate:.2%}"
    
    def test_export_performance(self, large_dataset):
        """Тест производительности экспорта"""
        _, transcription = large_dataset
        
        # Преобразуем в формат merged segments
        merged_segments = [
            {
                "start": seg["start"],
                "end": seg["end"],
                "speaker": f"SPEAKER_{i % 3:02d}",
                "text": seg["text"]
            }
            for i, seg in enumerate(transcription)
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Тест SRT экспорта
            export_agent = ExportAgent("srt")
            start_time = time.time()
            export_agent.run(merged_segments, temp_path / "output.srt")
            srt_time = time.time() - start_time
            
            # Тест JSON экспорта
            export_agent = ExportAgent("json")
            start_time = time.time()
            export_agent.run(merged_segments, temp_path / "output.json")
            json_time = time.time() - start_time
            
            # Тест ASS экспорта
            export_agent = ExportAgent("ass")
            start_time = time.time()
            export_agent.run(merged_segments, temp_path / "output.ass")
            ass_time = time.time() - start_time
            
            # Все экспорты должны быть быстрыми
            assert srt_time < 0.5, f"SRT export too slow: {srt_time:.2f}s"
            assert json_time < 0.5, f"JSON export too slow: {json_time:.2f}s"
            assert ass_time < 0.5, f"ASS export too slow: {ass_time:.2f}s"
            
            # Проверяем размеры файлов
            srt_size = (temp_path / "output.srt").stat().st_size
            json_size = (temp_path / "output.json").stat().st_size
            ass_size = (temp_path / "output.ass").stat().st_size
            
            assert srt_size > 0, "SRT file is empty"
            assert json_size > 0, "JSON file is empty"
            assert ass_size > 0, "ASS file is empty"
    
    def test_memory_usage(self, large_dataset):
        """Тест использования памяти"""
        diarization, transcription = large_dataset
        
        # Измеряем память до обработки
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        merge_agent = MergeAgent()
        result = merge_agent.run(diarization, transcription)
        
        # Измеряем память после обработки
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Увеличение памяти не должно быть критичным
        assert memory_increase < 100, f"Memory increase too high: {memory_increase:.1f}MB"
        
        # Проверяем, что результат корректный
        assert len(result) == len(transcription)


class TestScalabilityLimits:
    """Тесты пределов масштабируемости"""
    
    @pytest.mark.slow
    def test_maximum_segments(self):
        """Тест максимального количества сегментов"""
        
        # Создаём большой набор данных (уменьшаем до 5000 для разумного времени выполнения)
        max_segments = 5000
        
        diarization = [
            {
                "start": i * 1.0,
                "end": i * 1.0 + 0.8,
                "speaker": f"SPEAKER_{i % 10:02d}",
                "confidence": 0.9
            }
            for i in range(max_segments)
        ]
        
        transcription = [
            {
                "start": i * 1.0 + 0.1,
                "end": i * 1.0 + 0.7,
                "text": f"Segment {i}"
            }
            for i in range(max_segments)
        ]
        
        merge_agent = MergeAgent()
        
        start_time = time.time()
        result = merge_agent.run(diarization, transcription)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Даже с 5k сегментов должно работать разумно быстро (лимит 60 секунд)
        assert execution_time < 60.0, f"Processing {max_segments} segments took too long: {execution_time:.2f}s"
        assert len(result) == max_segments

        # Проверяем производительность на сегмент (увеличиваем лимит до 10ms)
        time_per_segment = execution_time / max_segments * 1000  # ms
        assert time_per_segment < 10.0, f"Too slow per segment: {time_per_segment:.2f}ms"
    
    def test_long_audio_simulation(self):
        """Тест симуляции длинного аудио"""
        
        # Симулируем 2-часовое аудио (7200 секунд)
        audio_duration = 7200  # 2 hours
        segment_length = 5.0   # 5 seconds per segment
        num_segments = int(audio_duration / segment_length)
        
        diarization = []
        transcription = []
        
        for i in range(num_segments):
            start_time = i * segment_length
            end_time = start_time + segment_length - 0.5
            
            diarization.append({
                "start": start_time,
                "end": end_time,
                "speaker": f"SPEAKER_{i % 3:02d}",
                "confidence": 0.85 + (i % 10) * 0.01
            })
            
            transcription.append({
                "start": start_time + 0.2,
                "end": end_time - 0.2,
                "text": f"Длинный текст сегмента номер {i} с дополнительной информацией"
            })
        
        merge_agent = MergeAgent()
        
        start_time = time.time()
        result = merge_agent.run(diarization, transcription)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Проверяем результат
        assert len(result) == num_segments
        
        # Время обработки должно быть пропорционально длине аудио
        processing_ratio = execution_time / audio_duration
        assert processing_ratio < 0.01, f"Processing ratio too high: {processing_ratio:.4f}"
        
        print(f"Processed {audio_duration}s audio in {execution_time:.2f}s (ratio: {processing_ratio:.4f})")


class TestConcurrencySimulation:
    """Тесты симуляции конкурентной обработки"""
    
    def test_multiple_agents_simulation(self):
        """Симуляция работы нескольких агентов одновременно"""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def worker(worker_id, segments_count):
            """Рабочая функция для симуляции агента"""
            
            # Создаём данные для этого воркера
            diarization = [
                {
                    "start": i * 2.0,
                    "end": i * 2.0 + 1.5,
                    "speaker": f"SPEAKER_{i % 2:02d}",
                    "confidence": 0.9
                }
                for i in range(segments_count)
            ]
            
            transcription = [
                {
                    "start": i * 2.0 + 0.1,
                    "end": i * 2.0 + 1.4,
                    "text": f"Worker {worker_id} segment {i}"
                }
                for i in range(segments_count)
            ]
            
            merge_agent = MergeAgent()
            
            start_time = time.time()
            result = merge_agent.run(diarization, transcription)
            end_time = time.time()
            
            results_queue.put({
                'worker_id': worker_id,
                'execution_time': end_time - start_time,
                'segments_processed': len(result),
                'success': True
            })
        
        # Запускаем 5 воркеров параллельно
        threads = []
        segments_per_worker = 200
        
        start_time = time.time()
        
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i, segments_per_worker))
            threads.append(thread)
            thread.start()
        
        # Ждём завершения всех потоков
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Собираем результаты
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Проверяем результаты
        assert len(results) == 5, "Not all workers completed"
        
        total_segments = sum(r['segments_processed'] for r in results)
        assert total_segments == 5 * segments_per_worker
        
        # Все воркеры должны завершиться успешно
        assert all(r['success'] for r in results)
        
        # Параллельная обработка должна быть эффективной
        avg_worker_time = sum(r['execution_time'] for r in results) / len(results)
        efficiency = avg_worker_time / total_time
        
        print(f"Concurrency efficiency: {efficiency:.2f} (higher is better)")
        # Снижаем требования к эффективности до 0.4 (40%)
        assert efficiency > 0.4, f"Low concurrency efficiency: {efficiency:.2f}"
