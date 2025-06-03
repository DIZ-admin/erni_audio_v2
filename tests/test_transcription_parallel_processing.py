# tests/test_transcription_parallel_processing.py

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from pipeline.transcription_agent import TranscriptionAgent


class TestTranscriptionParallelProcessing:
    """Тесты для параллельной обработки частей файлов в TranscriptionAgent."""

    @pytest.fixture
    def agent(self):
        """Создает экземпляр TranscriptionAgent для тестов."""
        # Мокаем переменные окружения для тестов
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-openai-key',
            'PYANNOTE_API_KEY': 'test-pyannote-key'
        }):
            return TranscriptionAgent(api_key="test-key", model="whisper-1")

    @pytest.fixture
    def mock_chunk_files(self, tmp_path):
        """Создает временные файлы частей для тестов."""
        chunk_files = []
        for i in range(3):
            chunk_file = tmp_path / f"test_chunk_{i:03d}.wav"
            chunk_file.write_bytes(b"fake audio data" * 1000)  # ~15KB
            chunk_files.append(chunk_file)
        return chunk_files

    def test_parallel_configuration_initialization(self, agent):
        """Тест инициализации конфигурации параллельной обработки."""
        assert hasattr(agent, 'max_concurrent_chunks')
        assert hasattr(agent, 'chunk_processing_timeout')
        assert hasattr(agent, 'parallel_stats')
        
        # Проверяем значения по умолчанию
        assert agent.max_concurrent_chunks == 3
        assert agent.chunk_processing_timeout == 1800  # 30 минут
        
        # Проверяем инициализацию статистики
        assert agent.parallel_stats["total_chunks_processed"] == 0
        assert agent.parallel_stats["concurrent_chunks_peak"] == 0
        assert agent.parallel_stats["total_parallel_time"] == 0.0
        assert agent.parallel_stats["chunks_failed"] == 0
        assert agent.parallel_stats["chunks_retried"] == 0

    def test_process_chunk_parallel_success(self, agent, mock_chunk_files):
        """Тест успешной обработки одной части файла."""
        # Мокаем метод _transcribe_single_file
        mock_segments = [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "Test segment 1"},
            {"id": 1, "start": 5.0, "end": 10.0, "text": "Test segment 2"}
        ]
        
        with patch.object(agent, '_transcribe_single_file', return_value=mock_segments):
            chunk_info = {
                "path": mock_chunk_files[0],
                "index": 0,
                "offset": 0.0,
                "prompt": "test prompt"
            }
            
            result = agent._process_chunk_parallel(chunk_info)
            
            # Проверяем результат
            assert result["success"] is True
            assert result["index"] == 0
            assert result["error"] is None
            assert len(result["segments"]) == 2
            assert result["processing_time"] > 0
            
            # Проверяем, что временные метки не изменились (offset = 0)
            assert result["segments"][0]["start"] == 0.0
            assert result["segments"][1]["start"] == 5.0

    def test_process_chunk_parallel_with_offset(self, agent, mock_chunk_files):
        """Тест обработки части файла с временным смещением."""
        mock_segments = [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "Test segment"}
        ]
        
        with patch.object(agent, '_transcribe_single_file', return_value=mock_segments):
            chunk_info = {
                "path": mock_chunk_files[0],
                "index": 1,
                "offset": 600.0,  # 10 минут
                "prompt": "test prompt"
            }
            
            result = agent._process_chunk_parallel(chunk_info)
            
            # Проверяем, что временные метки скорректированы
            assert result["segments"][0]["start"] == 600.0  # 0.0 + 600.0
            assert result["segments"][0]["end"] == 605.0    # 5.0 + 600.0

    def test_process_chunk_parallel_failure(self, agent, mock_chunk_files):
        """Тест обработки ошибки при обработке части файла."""
        # Мокаем исключение в _transcribe_single_file
        with patch.object(agent, '_transcribe_single_file', side_effect=Exception("Test error")):
            chunk_info = {
                "path": mock_chunk_files[0],
                "index": 0,
                "offset": 0.0,
                "prompt": "test prompt"
            }
            
            result = agent._process_chunk_parallel(chunk_info)
            
            # Проверяем результат ошибки
            assert result["success"] is False
            assert result["index"] == 0
            assert "Test error" in result["error"]
            assert len(result["segments"]) == 0
            assert result["processing_time"] > 0
            
            # Проверяем, что статистика ошибок обновлена
            assert agent.parallel_stats["chunks_failed"] == 1

    def test_process_chunks_parallel_success(self, agent, mock_chunk_files):
        """Тест параллельной обработки нескольких частей файлов."""
        # Мокаем _process_chunk_parallel для возврата успешных результатов
        def mock_process_chunk(chunk_info):
            return {
                "index": chunk_info["index"],
                "segments": [{"id": 0, "start": 0.0, "end": 5.0, "text": f"Chunk {chunk_info['index']}"}],
                "offset": chunk_info["offset"],
                "success": True,
                "error": None,
                "processing_time": 1.0
            }
        
        with patch.object(agent, '_process_chunk_parallel', side_effect=mock_process_chunk):
            chunk_infos = [
                {"path": mock_chunk_files[i], "index": i, "offset": i * 600.0, "prompt": "test"}
                for i in range(3)
            ]
            
            results = agent._process_chunks_parallel(chunk_infos)
            
            # Проверяем результаты
            assert len(results) == 3

            # Сортируем результаты по индексу для проверки
            results.sort(key=lambda x: x["index"])

            for i, result in enumerate(results):
                assert result["success"] is True
                assert result["index"] == i
                
            # Проверяем, что пик одновременных задач обновлен
            assert agent.parallel_stats["concurrent_chunks_peak"] >= 3

    def test_process_chunks_parallel_with_timeout(self, agent, mock_chunk_files):
        """Тест обработки таймаута при параллельной обработке."""
        # Устанавливаем короткий таймаут для теста
        agent.chunk_processing_timeout = 0.1

        # Мокаем as_completed для выброса TimeoutError
        with patch('pipeline.transcription_agent.as_completed') as mock_as_completed:
            mock_as_completed.side_effect = concurrent.futures.TimeoutError("Test timeout")

            chunk_infos = [
                {"path": mock_chunk_files[0], "index": 0, "offset": 0.0, "prompt": "test"}
            ]

            # Мокаем ThreadPoolExecutor
            with patch('pipeline.transcription_agent.ThreadPoolExecutor') as mock_executor_class:
                mock_executor = Mock()
                mock_executor_class.return_value.__enter__.return_value = mock_executor
                mock_executor.submit.return_value = Mock()

                results = agent._process_chunks_parallel(chunk_infos)

                # При TimeoutError в as_completed, метод должен вернуть пустой список
                # или обработать ошибку соответствующим образом
                assert isinstance(results, list)

    def test_cleanup_chunk_files(self, agent, mock_chunk_files):
        """Тест удаления временных файлов частей."""
        # Проверяем, что файлы существуют
        for chunk_file in mock_chunk_files:
            assert chunk_file.exists()
        
        # Удаляем файлы
        agent._cleanup_chunk_files(mock_chunk_files)
        
        # Проверяем, что файлы удалены
        for chunk_file in mock_chunk_files:
            assert not chunk_file.exists()

    def test_cleanup_chunk_files_with_missing_files(self, agent, tmp_path):
        """Тест удаления несуществующих файлов (не должно вызывать ошибок)."""
        non_existent_files = [
            tmp_path / "non_existent_1.wav",
            tmp_path / "non_existent_2.wav"
        ]
        
        # Не должно вызывать исключений
        agent._cleanup_chunk_files(non_existent_files)

    def test_log_parallel_statistics(self, agent, caplog):
        """Тест логирования статистики параллельной обработки."""
        import logging
        
        # Устанавливаем уровень логирования
        caplog.set_level(logging.INFO)
        
        # Устанавливаем статистику
        agent.parallel_stats["total_chunks_processed"] = 5
        agent.parallel_stats["concurrent_chunks_peak"] = 3
        agent.parallel_stats["total_parallel_time"] = 45.5
        agent.parallel_stats["chunks_failed"] = 1
        agent.parallel_stats["chunks_retried"] = 2
        
        # Логируем статистику
        agent._log_parallel_statistics()
        
        # Проверяем лог
        assert "🔄 Статистика параллельной обработки" in caplog.text
        assert "обработано частей=5" in caplog.text
        assert "пик одновременных=3" in caplog.text
        assert "время обработки=45.5с" in caplog.text
        assert "неудачных=1" in caplog.text
        assert "повторных=2" in caplog.text

    def test_log_parallel_statistics_no_processing(self, agent, caplog):
        """Тест логирования статистики когда не было параллельной обработки."""
        # Логируем статистику без обработки
        agent._log_parallel_statistics()
        
        # Проверяем, что лог пустой
        assert "🔄 Статистика параллельной обработки" not in caplog.text

    @patch('pipeline.transcription_agent.ThreadPoolExecutor')
    def test_process_chunks_parallel_executor_usage(self, mock_executor_class, agent, mock_chunk_files):
        """Тест правильного использования ThreadPoolExecutor."""
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor
        
        # Мокаем submit и as_completed
        mock_future = Mock()
        mock_future.result.return_value = {
            "index": 0, "success": True, "segments": [], "offset": 0.0, 
            "error": None, "processing_time": 1.0
        }
        mock_executor.submit.return_value = mock_future
        
        with patch('pipeline.transcription_agent.as_completed', return_value=[mock_future]):
            chunk_infos = [
                {"path": mock_chunk_files[0], "index": 0, "offset": 0.0, "prompt": "test"}
            ]
            
            agent._process_chunks_parallel(chunk_infos)
            
            # Проверяем, что ThreadPoolExecutor создан с правильными параметрами
            mock_executor_class.assert_called_once_with(max_workers=agent.max_concurrent_chunks)
            
            # Проверяем, что submit был вызван
            mock_executor.submit.assert_called_once()

    def test_transcribe_large_file_parallel_integration(self, agent, tmp_path):
        """Интеграционный тест параллельной обработки большого файла."""
        # Создаем тестовый аудиофайл
        large_audio_file = tmp_path / "large_test_audio.wav"
        large_audio_file.write_bytes(b"fake large audio data" * 10000)  # ~150KB
        
        # Мокаем методы для контроля процесса
        mock_chunks = [tmp_path / f"chunk_{i}.wav" for i in range(3)]
        for chunk in mock_chunks:
            chunk.write_bytes(b"fake chunk data")
        
        def mock_transcribe_single_file(*args, **kwargs):
            # Возвращаем новые объекты каждый раз, чтобы избежать изменения in-place
            return [
                {"id": 0, "start": 0.0, "end": 5.0, "text": "Test segment"}
            ]

        with patch.object(agent, '_split_audio_file', return_value=mock_chunks), \
             patch.object(agent, '_transcribe_single_file', side_effect=mock_transcribe_single_file), \
             patch.object(agent, '_cleanup_chunk_files') as mock_cleanup:
            
            result = agent._transcribe_large_file(large_audio_file, "test prompt")
            
            # Проверяем результат
            assert len(result) == 3  # 3 части * 1 сегмент каждая

            # Сортируем результаты по start времени для проверки
            result.sort(key=lambda x: x["start"])

            # Проверяем, что есть сегменты с правильными временными метками
            start_times = [seg["start"] for seg in result]
            assert 0.0 in start_times      # Первая часть: 0 + 0
            assert 600.0 in start_times    # Вторая часть: 0 + 600
            assert 1200.0 in start_times   # Третья часть: 0 + 1200

            # Проверяем, что ID перенумерованы последовательно
            ids = [seg["id"] for seg in result]
            assert set(ids) == {0, 1, 2}
            
            # Проверяем, что cleanup был вызван
            mock_cleanup.assert_called_once_with(mock_chunks)
            
            # Проверяем обновление статистики
            assert agent.parallel_stats["total_chunks_processed"] == 3
            assert agent.parallel_stats["total_parallel_time"] > 0
