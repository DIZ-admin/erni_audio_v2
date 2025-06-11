#!/usr/bin/env python3
"""
Тесты для checkpoint-based resumption системы
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Импортируем напрямую, минуя pipeline/__init__.py
from pipeline.checkpoint_manager import CheckpointManager, PipelineStage, CheckpointData, PipelineState

# Простая реализация save_json и load_json для тестов
def save_json(data, file_path):
    """Сохранить данные в JSON файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(file_path):
    """Загрузить данные из JSON файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


class TestCheckpointManager:
    """Тесты для CheckpointManager"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.checkpoint_manager = CheckpointManager(checkpoints_dir=self.temp_dir)
        self.test_input_file = "test_audio.wav"
    
    def teardown_method(self):
        """Очистка после каждого теста"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_checkpoint_manager_initialization(self):
        """Тест инициализации CheckpointManager"""
        assert self.checkpoint_manager.checkpoints_dir == self.temp_dir
        assert self.temp_dir.exists()
        assert len(self.checkpoint_manager.stage_order) == 5
        assert PipelineStage.AUDIO_CONVERSION in self.checkpoint_manager.stage_order
    
    def test_get_pipeline_id(self):
        """Тест генерации pipeline ID"""
        pipeline_id = self.checkpoint_manager.get_pipeline_id(self.test_input_file)
        assert isinstance(pipeline_id, str)
        assert len(pipeline_id) > 0
        
        # Проверяем, что ID одинаковый для одного файла
        pipeline_id2 = self.checkpoint_manager.get_pipeline_id(self.test_input_file)
        assert pipeline_id == pipeline_id2
    
    def test_create_checkpoint_success(self):
        """Тест создания успешного checkpoint'а"""
        output_file = self.temp_dir / "test_output.json"
        save_json({"test": "data"}, output_file)
        
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file=str(output_file),
            metadata={"test_meta": "value"},
            success=True
        )
        
        # Проверяем, что checkpoint создался
        state = self.checkpoint_manager.load_pipeline_state(self.test_input_file)
        assert state is not None
        assert len(state.checkpoints) == 1
        assert state.checkpoints[0].stage == PipelineStage.AUDIO_CONVERSION.value
        assert state.checkpoints[0].success is True
        assert PipelineStage.AUDIO_CONVERSION.value in state.completed_stages
    
    def test_create_checkpoint_failure(self):
        """Тест создания checkpoint'а с ошибкой"""
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.DIARIZATION,
            output_file="",
            success=False,
            error_message="Test error"
        )
        
        # Проверяем, что checkpoint создался с ошибкой
        state = self.checkpoint_manager.load_pipeline_state(self.test_input_file)
        assert state is not None
        assert len(state.checkpoints) == 1
        assert state.checkpoints[0].success is False
        assert state.checkpoints[0].error_message == "Test error"
        assert state.failed_stage == PipelineStage.DIARIZATION.value
    
    def test_get_resume_point_no_checkpoints(self):
        """Тест определения точки возобновления без checkpoint'ов"""
        resume_point, existing_files = self.checkpoint_manager.get_resume_point(
            self.test_input_file, "standard"
        )
        assert resume_point is None
        assert existing_files == []
    
    def test_get_resume_point_with_checkpoints(self):
        """Тест определения точки возобновления с checkpoint'ами"""
        # Создаем checkpoint для первого этапа
        output_file = self.temp_dir / "audio_output.wav"
        output_file.write_text("test audio data")
        
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file=str(output_file),
            success=True
        )
        
        # Проверяем точку возобновления
        resume_point, existing_files = self.checkpoint_manager.get_resume_point(
            self.test_input_file, "standard"
        )
        assert resume_point == PipelineStage.DIARIZATION
        assert str(output_file) in existing_files
    
    def test_validate_checkpoint_files(self):
        """Тест валидации checkpoint файлов"""
        # Создаем валидный JSON файл
        valid_file = self.temp_dir / "valid.json"
        save_json({"test": "data"}, valid_file)
        
        # Создаем невалидный файл
        invalid_file = self.temp_dir / "invalid.json"
        invalid_file.write_text("invalid json content")
        
        # Создаем checkpoint'ы
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file=str(valid_file),
            success=True
        )
        
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.DIARIZATION,
            output_file=str(invalid_file),
            success=True
        )
        
        # Валидируем файлы
        validation_results = self.checkpoint_manager.validate_checkpoint_files(self.test_input_file)
        assert validation_results[str(valid_file)] is True
        assert validation_results[str(invalid_file)] is False
    
    def test_cleanup_old_checkpoints(self):
        """Тест очистки старых checkpoint'ов"""
        # Создаем checkpoint
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file="test_output.json",
            success=True
        )
        
        # Проверяем, что checkpoint существует
        state = self.checkpoint_manager.load_pipeline_state(self.test_input_file)
        assert state is not None
        
        # Очищаем checkpoint'ы (0 дней = все)
        removed_count = self.checkpoint_manager.cleanup_old_checkpoints(days_old=0)
        assert removed_count == 1
        
        # Проверяем, что checkpoint удален
        state = self.checkpoint_manager.load_pipeline_state(self.test_input_file)
        assert state is None
    
    def test_get_pipeline_summary(self):
        """Тест получения сводки по пайплайну"""
        # Создаем несколько checkpoint'ов
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file="audio.wav",
            success=True
        )
        
        self.checkpoint_manager.create_checkpoint(
            input_file=self.test_input_file,
            stage=PipelineStage.DIARIZATION,
            output_file="",
            success=False,
            error_message="Test error"
        )
        
        # Получаем сводку
        summary = self.checkpoint_manager.get_pipeline_summary(self.test_input_file)
        assert summary is not None
        assert summary["status"] == "failed"
        assert summary["total_checkpoints"] == 2
        assert summary["successful_checkpoints"] == 1
        assert summary["failed_checkpoints"] == 1
        assert summary["failed_stage"] == PipelineStage.DIARIZATION.value


class TestCheckpointIntegration:
    """Интеграционные тесты checkpoint системы"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.checkpoint_manager = CheckpointManager(checkpoints_dir=self.temp_dir)
    
    def teardown_method(self):
        """Очистка после каждого теста"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @patch('pipeline.checkpoint_manager.datetime')
    def test_checkpoint_timestamps(self, mock_datetime):
        """Тест корректности временных меток в checkpoint'ах"""
        # Мокаем время
        mock_now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        self.checkpoint_manager.create_checkpoint(
            input_file="test.wav",
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file="output.wav",
            success=True
        )
        
        state = self.checkpoint_manager.load_pipeline_state("test.wav")
        assert state.created_at == mock_now.isoformat()
        assert state.last_updated == mock_now.isoformat()
        assert state.checkpoints[0].timestamp == mock_now.isoformat()
    
    def test_multiple_pipeline_isolation(self):
        """Тест изоляции между разными пайплайнами"""
        # Создаем checkpoint'ы для разных файлов
        self.checkpoint_manager.create_checkpoint(
            input_file="file1.wav",
            stage=PipelineStage.AUDIO_CONVERSION,
            output_file="output1.wav",
            success=True
        )
        
        self.checkpoint_manager.create_checkpoint(
            input_file="file2.wav",
            stage=PipelineStage.DIARIZATION,
            output_file="output2.json",
            success=True
        )
        
        # Проверяем изоляцию
        state1 = self.checkpoint_manager.load_pipeline_state("file1.wav")
        state2 = self.checkpoint_manager.load_pipeline_state("file2.wav")
        
        assert state1.pipeline_id != state2.pipeline_id
        assert len(state1.checkpoints) == 1
        assert len(state2.checkpoints) == 1
        assert state1.checkpoints[0].stage != state2.checkpoints[0].stage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
