# tests/test_simple_parallel.py

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed


def test_simple_parallel_processing():
    """Простой тест параллельной обработки без зависимостей."""
    
    def process_item(item):
        """Простая функция для обработки элемента."""
        time.sleep(0.1)  # Имитируем работу
        return {"index": item["index"], "result": item["value"] * 2}
    
    # Тестовые данные
    items = [
        {"index": 0, "value": 10},
        {"index": 1, "value": 20},
        {"index": 2, "value": 30}
    ]
    
    # Параллельная обработка
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_item = {executor.submit(process_item, item): item for item in items}
        
        for future in as_completed(future_to_item):
            result = future.result()
            results.append(result)
    
    # Проверяем результаты
    assert len(results) == 3
    
    # Сортируем по индексу
    results.sort(key=lambda x: x["index"])
    
    assert results[0]["result"] == 20  # 10 * 2
    assert results[1]["result"] == 40  # 20 * 2
    assert results[2]["result"] == 60  # 30 * 2


def test_parallel_processing_with_timeout():
    """Тест параллельной обработки с таймаутом."""
    
    def slow_process_item(item):
        """Медленная функция для тестирования таймаута."""
        time.sleep(0.5)  # Больше таймаута
        return {"index": item["index"], "result": item["value"]}
    
    items = [{"index": 0, "value": 10}]
    
    # Тестируем обработку таймаута
    with ThreadPoolExecutor(max_workers=1) as executor:
        future_to_item = {executor.submit(slow_process_item, item): item for item in items}
        
        try:
            # Устанавливаем короткий таймаут
            for future in as_completed(future_to_item, timeout=0.1):
                result = future.result()
        except concurrent.futures.TimeoutError:
            # Ожидаем таймаут
            assert True
        else:
            # Если таймаута не было, тест провален
            assert False, "Ожидался TimeoutError"


def test_parallel_processing_with_exception():
    """Тест параллельной обработки с исключениями."""
    
    def failing_process_item(item):
        """Функция, которая выбрасывает исключение."""
        if item["index"] == 1:
            raise ValueError("Test error")
        return {"index": item["index"], "result": item["value"]}
    
    items = [
        {"index": 0, "value": 10},
        {"index": 1, "value": 20},  # Эта вызовет ошибку
        {"index": 2, "value": 30}
    ]
    
    results = []
    errors = []
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_item = {executor.submit(failing_process_item, item): item for item in items}
        
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append({"index": item["index"], "error": str(e)})
    
    # Проверяем результаты
    assert len(results) == 2  # Два успешных
    assert len(errors) == 1   # Одна ошибка
    
    # Проверяем, что ошибка от правильного элемента
    assert errors[0]["index"] == 1
    assert "Test error" in errors[0]["error"]


def test_concurrent_chunks_peak_tracking():
    """Тест отслеживания пика одновременных задач."""
    
    max_concurrent = 0
    current_concurrent = 0
    
    def track_concurrent_item(item):
        nonlocal max_concurrent, current_concurrent
        current_concurrent += 1
        if current_concurrent > max_concurrent:
            max_concurrent = current_concurrent
        
        time.sleep(0.1)  # Имитируем работу
        
        current_concurrent -= 1
        return {"index": item["index"], "result": item["value"]}
    
    items = [{"index": i, "value": i * 10} for i in range(5)]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(track_concurrent_item, item) for item in items]
        
        # Ждем завершения всех задач
        for future in as_completed(futures):
            future.result()
    
    # Проверяем, что пик не превысил максимум воркеров
    assert max_concurrent <= 3
    assert max_concurrent > 0


def test_chunk_processing_simulation():
    """Симуляция обработки частей файла."""
    
    def process_chunk_simulation(chunk_info):
        """Симулирует обработку части файла."""
        chunk_index = chunk_info["index"]
        chunk_offset = chunk_info["offset"]
        
        # Имитируем обработку
        time.sleep(0.05)
        
        # Создаем фиктивные сегменты
        segments = [
            {
                "id": 0,
                "start": 0.0 + chunk_offset,
                "end": 5.0 + chunk_offset,
                "text": f"Segment from chunk {chunk_index}"
            }
        ]
        
        return {
            "index": chunk_index,
            "segments": segments,
            "offset": chunk_offset,
            "success": True,
            "error": None,
            "processing_time": 0.05
        }
    
    # Симулируем 3 части файла по 10 минут каждая
    chunk_infos = [
        {"index": i, "offset": i * 600.0}  # 600 секунд = 10 минут
        for i in range(3)
    ]
    
    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_chunk = {
            executor.submit(process_chunk_simulation, chunk_info): chunk_info 
            for chunk_info in chunk_infos
        }
        
        for future in as_completed(future_to_chunk):
            result = future.result()
            results.append(result)
    
    # Проверяем результаты
    assert len(results) == 3
    
    # Сортируем по индексу
    results.sort(key=lambda x: x["index"])
    
    # Проверяем временные смещения
    assert results[0]["segments"][0]["start"] == 0.0    # 0 + 0
    assert results[1]["segments"][0]["start"] == 600.0  # 0 + 600
    assert results[2]["segments"][0]["start"] == 1200.0 # 0 + 1200
    
    # Проверяем успешность
    for result in results:
        assert result["success"] is True
        assert result["error"] is None


if __name__ == "__main__":
    print("Запуск простых тестов параллельной обработки...")
    
    test_simple_parallel_processing()
    print("✅ test_simple_parallel_processing прошел")
    
    test_parallel_processing_with_timeout()
    print("✅ test_parallel_processing_with_timeout прошел")
    
    test_parallel_processing_with_exception()
    print("✅ test_parallel_processing_with_exception прошел")
    
    test_concurrent_chunks_peak_tracking()
    print("✅ test_concurrent_chunks_peak_tracking прошел")
    
    test_chunk_processing_simulation()
    print("✅ test_chunk_processing_simulation прошел")
    
    print("🎉 Все тесты прошли успешно!")
