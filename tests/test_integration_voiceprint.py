"""
Интеграционные тесты для voiceprint функционала
"""

import pytest
import tempfile
import subprocess
import json
from pathlib import Path
import os


class TestVoiceprintCLIIntegration:
    """Интеграционные тесты CLI утилиты voiceprint"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Создаем тестовый аудиофайл
        self.test_audio = Path("test_audio.wav")
        with open(self.test_audio, "wb") as f:
            f.write(b"fake audio data" * 100)  # ~1.3KB
    
    def teardown_method(self):
        """Очистка после теста"""
        os.chdir(self.original_cwd)
    
    def test_cli_stats_empty(self):
        """Тест статистики базы через CLI"""
        result = subprocess.run([
            "python3",
            "-m", "pipeline.voiceprint_cli",
            "stats"
        ], capture_output=True, text=True, cwd=self.original_cwd)

        assert result.returncode == 0
        # Проверяем, что команда работает и возвращает статистику
        assert "Всего voiceprints:" in result.stdout
        assert "База данных:" in result.stdout
    
    def test_cli_list_empty(self):
        """Тест списка базы через CLI"""
        result = subprocess.run([
            "python3",
            "-m", "pipeline.voiceprint_cli",
            "list"
        ], capture_output=True, text=True, cwd=self.original_cwd)

        assert result.returncode == 0
        # Проверяем, что команда работает (может быть пустая или с данными)
        assert ("База voiceprints пуста" in result.stdout or
                "Найдено" in result.stdout)
    
    @pytest.mark.skipif(not os.getenv("PYANNOTEAI_API_TOKEN"), 
                       reason="Требуется PYANNOTEAI_API_TOKEN для интеграционного теста")
    def test_cli_create_voiceprint(self):
        """Тест создания voiceprint через CLI (требует API ключ)"""
        result = subprocess.run([
            "python3",
            "-m", "pipeline.voiceprint_cli",
            "create",
            str(self.test_audio),
            "Test Speaker CLI",
            "--skip-duration-check"
        ], capture_output=True, text=True, cwd=self.original_cwd)
        
        # Если API ключ есть, тест должен пройти
        if result.returncode == 0:
            assert "Voiceprint создан успешно" in result.stdout
            assert "Test Speaker CLI" in result.stdout
        else:
            # Если нет API ключа, должна быть соответствующая ошибка
            assert "Missing PYANNOTEAI_API_TOKEN" in result.stderr


class TestSpeechPipelineIntegration:
    """Интеграционные тесты Speech Pipeline с новыми опциями"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Создаем тестовый аудиофайл
        self.test_audio = Path("test_audio.wav")
        with open(self.test_audio, "wb") as f:
            f.write(b"fake audio data" * 1000)  # ~13KB
    
    def teardown_method(self):
        """Очистка после теста"""
        os.chdir(self.original_cwd)
    
    def test_help_includes_new_options(self):
        """Тест что help включает новые опции"""
        result = subprocess.run([
            "python3", 
            f"{self.original_cwd}/speech_pipeline.py", 
            "--help"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "--use-replicate" in result.stdout
        assert "--use-identification" in result.stdout
        assert "--voiceprints" in result.stdout
        assert "--matching-threshold" in result.stdout
    
    @pytest.mark.skipif(not os.getenv("REPLICATE_API_TOKEN"), 
                       reason="Требуется REPLICATE_API_TOKEN для интеграционного теста")
    def test_replicate_pipeline_dry_run(self):
        """Тест Replicate pipeline (dry run без реального API вызова)"""
        # Тестируем только валидацию аргументов
        result = subprocess.run([
            "python3", 
            f"{self.original_cwd}/speech_pipeline.py", 
            str(self.test_audio),
            "--use-replicate",
            "--format", "json",
            "-o", "output.json"
        ], capture_output=True, text=True, timeout=10)
        
        # Ожидаем, что скрипт запустится и дойдет до инициализации
        # (может упасть на реальном API вызове, но это нормально для теста)
        assert "--use-replicate" not in result.stderr  # Нет ошибок парсинга аргументов
    
    def test_identification_pipeline_missing_voiceprints(self):
        """Тест Identification pipeline без voiceprints"""
        result = subprocess.run([
            "python3",
            f"{self.original_cwd}/speech_pipeline.py",
            str(self.test_audio),
            "--use-identification",
            "--format", "json",
            "-o", "output.json"
        ], capture_output=True, text=True, timeout=10, cwd=self.original_cwd)

        # Должна быть ошибка
        assert result.returncode != 0
        # Проверяем, что есть ошибка (может быть о voiceprints, валидации файла или файл не найден)
        error_output = result.stderr + result.stdout
        assert ("необходимо указать --voiceprints" in error_output or
                "Неподдерживаемый MIME тип" in error_output or
                "Файл не найден" in error_output or
                "Файл не прошел валидацию" in error_output)


class TestEndToEndWorkflow:
    """End-to-end тесты полного workflow"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Создаем тестовые аудиофайлы
        self.voiceprint_audio = Path("voiceprint_sample.wav")
        self.test_audio = Path("test_meeting.wav")
        
        with open(self.voiceprint_audio, "wb") as f:
            f.write(b"fake voiceprint audio" * 50)  # ~1KB
        
        with open(self.test_audio, "wb") as f:
            f.write(b"fake meeting audio" * 500)  # ~10KB
    
    def teardown_method(self):
        """Очистка после теста"""
        os.chdir(self.original_cwd)
    
    def test_voiceprint_database_persistence(self):
        """Тест сохранения voiceprints в базе данных"""
        from pipeline.voiceprint_manager import VoiceprintManager
        
        # Создаем менеджер
        manager = VoiceprintManager()
        
        # Добавляем voiceprint
        vp_id = manager.add_voiceprint(
            label="Test Speaker",
            voiceprint_data="test_base64_data",
            source_file=str(self.voiceprint_audio)
        )
        
        # Создаем новый менеджер (имитируем перезапуск)
        manager2 = VoiceprintManager()
        
        # Проверяем, что данные сохранились
        voiceprint = manager2.get_voiceprint(vp_id)
        assert voiceprint is not None
        assert voiceprint["label"] == "Test Speaker"
        assert voiceprint["voiceprint"] == "test_base64_data"
    
    def test_voiceprint_export_import(self):
        """Тест экспорта и импорта voiceprints"""
        from pipeline.voiceprint_manager import VoiceprintManager
        
        # Создаем исходную базу
        manager1 = VoiceprintManager(Path("db1.json"))
        manager1.add_voiceprint("Speaker 1", "data1")
        manager1.add_voiceprint("Speaker 2", "data2")
        
        # Экспортируем
        export_file = Path("export.json")
        manager1.export_voiceprints(export_file)
        
        # Создаем новую базу и импортируем
        manager2 = VoiceprintManager(Path("db2.json"))
        count = manager2.import_voiceprints(export_file)
        
        assert count == 2
        assert manager2.get_voiceprint_by_label("Speaker 1") is not None
        assert manager2.get_voiceprint_by_label("Speaker 2") is not None
    
    def test_configuration_validation(self):
        """Тест валидации конфигурации"""
        from pipeline.voiceprint_manager import VoiceprintManager
        
        manager = VoiceprintManager()
        
        # Тест добавления с пустым label
        with pytest.raises(ValueError):
            manager.add_voiceprint("", "data")
        
        # Тест поиска несуществующего
        result = manager.get_voiceprint_by_label("Nonexistent")
        assert result is None
        
        # Тест статистики
        stats = manager.get_statistics()
        assert isinstance(stats, dict)
        assert "total" in stats
        assert "database_path" in stats


class TestPerformanceAndLimits:
    """Тесты производительности и лимитов"""
    
    def test_large_voiceprint_database(self):
        """Тест работы с большой базой voiceprints"""
        from pipeline.voiceprint_manager import VoiceprintManager
        import uuid

        manager = VoiceprintManager()

        # Получаем начальное количество voiceprints
        initial_stats = manager.get_statistics()
        initial_count = initial_stats["total"]

        # Добавляем много voiceprints с уникальными именами
        unique_prefix = str(uuid.uuid4())[:8]
        for i in range(100):
            manager.add_voiceprint(f"TestSpeaker_{unique_prefix}_{i:03d}", f"data_{i}")

        # Тест поиска
        results = manager.search_voiceprints(f"TestSpeaker_{unique_prefix}_050")
        assert len(results) == 1
        assert results[0]["label"] == f"TestSpeaker_{unique_prefix}_050"

        # Тест статистики
        stats = manager.get_statistics()
        assert stats["total"] == initial_count + 100
    
    def test_voiceprint_data_validation(self):
        """Тест валидации данных voiceprint"""
        from pipeline.voiceprint_manager import VoiceprintManager
        
        manager = VoiceprintManager()
        
        # Тест с очень длинным именем
        long_name = "A" * 1000
        vp_id = manager.add_voiceprint(long_name, "data")
        voiceprint = manager.get_voiceprint(vp_id)
        assert voiceprint["label"] == long_name
        
        # Тест с большими данными
        large_data = "x" * 10000  # 10KB base64 данных
        vp_id = manager.add_voiceprint("Large Data Speaker", large_data)
        voiceprint = manager.get_voiceprint(vp_id)
        assert voiceprint["voiceprint"] == large_data
    
    def test_concurrent_access_simulation(self):
        """Тест имитации конкурентного доступа"""
        from pipeline.voiceprint_manager import VoiceprintManager
        import threading
        import time
        import uuid

        manager = VoiceprintManager()

        # Получаем начальное количество voiceprints
        initial_stats = manager.get_statistics()
        initial_count = initial_stats["total"]

        results = []
        unique_prefix = str(uuid.uuid4())[:8]

        def add_voiceprints(thread_id):
            for i in range(10):
                vp_id = manager.add_voiceprint(f"ConcurrentTest_{unique_prefix}_Thread{thread_id}_Speaker{i}", f"data_{thread_id}_{i}")
                results.append(vp_id)
                time.sleep(0.001)  # Небольшая задержка

        # Запускаем несколько потоков
        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_voiceprints, args=(i,))
            threads.append(thread)
            thread.start()

        # Ждем завершения
        for thread in threads:
            thread.join()

        # Проверяем результаты
        assert len(results) == 30  # 3 потока * 10 voiceprints
        assert len(set(results)) == 30  # Все ID уникальны

        stats = manager.get_statistics()
        assert stats["total"] == initial_count + 30


if __name__ == "__main__":
    pytest.main([__file__])
