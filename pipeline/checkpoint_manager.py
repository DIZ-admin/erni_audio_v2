# pipeline/checkpoint_manager.py

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


def load_json(file_path):
    """Загрузить данные из JSON файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, file_path):
    """Сохранить данные в JSON файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class PipelineStage(Enum):
    """Этапы пайплайна обработки"""
    AUDIO_CONVERSION = "audio_conversion"
    DIARIZATION = "diarization"
    TRANSCRIPTION = "transcription"
    MERGE = "merge"
    EXPORT = "export"
    IDENTIFICATION = "identification"
    REPLICATE = "replicate"


@dataclass
class CheckpointData:
    """Данные checkpoint'а"""
    stage: str
    timestamp: str
    input_file: str
    output_file: str
    metadata: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None


@dataclass
class PipelineState:
    """Состояние пайплайна"""
    input_file: str
    pipeline_id: str
    created_at: str
    last_updated: str
    completed_stages: List[str]
    current_stage: Optional[str]
    failed_stage: Optional[str]
    checkpoints: List[CheckpointData]
    metadata: Dict[str, Any]


class CheckpointManager:
    """
    Менеджер checkpoint'ов для возобновления пайплайна.
    
    Функции:
    - Автоматическое сохранение состояния после каждого этапа
    - Определение точки возобновления
    - Валидация промежуточных результатов
    - Очистка устаревших checkpoint'ов
    """
    
    def __init__(self, checkpoints_dir: Path = Path("data/checkpoints")):
        self.checkpoints_dir = checkpoints_dir
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Определяем порядок этапов
        self.stage_order = [
            PipelineStage.AUDIO_CONVERSION,
            PipelineStage.DIARIZATION,
            PipelineStage.TRANSCRIPTION,
            PipelineStage.MERGE,
            PipelineStage.EXPORT
        ]
        
        # Альтернативные пайплайны
        self.replicate_order = [
            PipelineStage.REPLICATE,
            PipelineStage.EXPORT
        ]
        
        self.identification_order = [
            PipelineStage.IDENTIFICATION,
            PipelineStage.EXPORT
        ]
    
    def get_pipeline_id(self, input_file: str) -> str:
        """Генерирует уникальный ID пайплайна на основе входного файла"""
        input_path = Path(input_file)
        return f"{input_path.stem}_{hash(input_path.absolute())}"
    
    def get_state_file(self, pipeline_id: str) -> Path:
        """Возвращает путь к файлу состояния пайплайна"""
        return self.checkpoints_dir / f"{pipeline_id}_state.json"
    
    def load_pipeline_state(self, input_file: str) -> Optional[PipelineState]:
        """Загружает состояние пайплайна если оно существует"""
        pipeline_id = self.get_pipeline_id(input_file)
        state_file = self.get_state_file(pipeline_id)
        
        if not state_file.exists():
            return None
        
        try:
            data = load_json(state_file)
            checkpoints = [CheckpointData(**cp) for cp in data.get('checkpoints', [])]
            
            state = PipelineState(
                input_file=data['input_file'],
                pipeline_id=data['pipeline_id'],
                created_at=data['created_at'],
                last_updated=data['last_updated'],
                completed_stages=data['completed_stages'],
                current_stage=data.get('current_stage'),
                failed_stage=data.get('failed_stage'),
                checkpoints=checkpoints,
                metadata=data.get('metadata', {})
            )
            
            self.logger.info(f"📂 Загружено состояние пайплайна: {pipeline_id}")
            return state
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки состояния {pipeline_id}: {e}")
            return None
    
    def save_pipeline_state(self, state: PipelineState) -> None:
        """Сохраняет состояние пайплайна"""
        try:
            state_file = self.get_state_file(state.pipeline_id)
            
            # Обновляем время последнего изменения
            state.last_updated = datetime.now().isoformat()
            
            # Конвертируем в словарь для сохранения
            data = asdict(state)
            
            save_json(data, state_file)
            self.logger.debug(f"💾 Состояние пайплайна сохранено: {state_file}")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка сохранения состояния: {e}")
    
    def create_checkpoint(self, input_file: str, stage: PipelineStage, 
                         output_file: str, metadata: Dict[str, Any] = None,
                         success: bool = True, error_message: str = None) -> None:
        """Создает checkpoint для этапа"""
        pipeline_id = self.get_pipeline_id(input_file)
        
        # Загружаем или создаем состояние
        state = self.load_pipeline_state(input_file)
        if state is None:
            state = PipelineState(
                input_file=input_file,
                pipeline_id=pipeline_id,
                created_at=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
                completed_stages=[],
                current_stage=stage.value,
                failed_stage=None,
                checkpoints=[],
                metadata=metadata or {}
            )
        
        # Создаем checkpoint
        checkpoint = CheckpointData(
            stage=stage.value,
            timestamp=datetime.now().isoformat(),
            input_file=input_file,
            output_file=output_file,
            metadata=metadata or {},
            success=success,
            error_message=error_message
        )
        
        # Обновляем состояние
        state.checkpoints.append(checkpoint)
        
        if success:
            if stage.value not in state.completed_stages:
                state.completed_stages.append(stage.value)
            state.failed_stage = None
            self.logger.info(f"✅ Checkpoint создан: {stage.value} → {output_file}")
        else:
            state.failed_stage = stage.value
            self.logger.error(f"❌ Checkpoint с ошибкой: {stage.value} - {error_message}")
        
        # Сохраняем состояние
        self.save_pipeline_state(state)
    
    def get_resume_point(self, input_file: str, pipeline_type: str = "standard") -> Tuple[Optional[PipelineStage], List[str]]:
        """
        Определяет точку возобновления пайплайна.
        
        Returns:
            Tuple[next_stage, existing_files] - следующий этап и список существующих файлов
        """
        state = self.load_pipeline_state(input_file)
        
        if state is None:
            return None, []
        
        # Выбираем порядок этапов в зависимости от типа пайплайна
        if pipeline_type == "replicate":
            stage_order = self.replicate_order
        elif pipeline_type == "identification":
            stage_order = self.identification_order
        else:
            stage_order = self.stage_order
        
        # Находим последний успешно завершенный этап
        completed_stages = set(state.completed_stages)
        existing_files = []
        
        # Собираем существующие файлы
        for checkpoint in state.checkpoints:
            if checkpoint.success and Path(checkpoint.output_file).exists():
                existing_files.append(checkpoint.output_file)
        
        # Определяем следующий этап
        for i, stage in enumerate(stage_order):
            if stage.value not in completed_stages:
                self.logger.info(f"🔄 Точка возобновления: {stage.value}")
                return stage, existing_files
        
        # Все этапы завершены
        self.logger.info("✅ Пайплайн уже завершен")
        return None, existing_files
    
    def validate_checkpoint_files(self, input_file: str) -> Dict[str, bool]:
        """Валидирует существование и целостность checkpoint файлов"""
        state = self.load_pipeline_state(input_file)
        
        if state is None:
            return {}
        
        validation_results = {}
        
        for checkpoint in state.checkpoints:
            if not checkpoint.success:
                continue
                
            file_path = Path(checkpoint.output_file)
            is_valid = False
            
            if file_path.exists():
                try:
                    # Проверяем размер файла
                    if file_path.stat().st_size > 0:
                        # Для JSON файлов проверяем валидность
                        if file_path.suffix == '.json':
                            load_json(file_path)
                        is_valid = True
                except Exception as e:
                    self.logger.warning(f"⚠️ Невалидный файл {file_path}: {e}")
            
            validation_results[checkpoint.output_file] = is_valid
        
        return validation_results
    
    def cleanup_old_checkpoints(self, days_old: int = 7) -> int:
        """Удаляет старые checkpoint'ы"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        removed_count = 0
        
        for state_file in self.checkpoints_dir.glob("*_state.json"):
            try:
                data = load_json(state_file)
                created_at = datetime.fromisoformat(data.get('created_at', ''))
                
                if created_at < cutoff_date:
                    state_file.unlink()
                    removed_count += 1
                    self.logger.debug(f"🗑️ Удален старый checkpoint: {state_file}")
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Ошибка при очистке {state_file}: {e}")
        
        if removed_count > 0:
            self.logger.info(f"🧹 Очищено {removed_count} старых checkpoint'ов")
        
        return removed_count
    
    def get_pipeline_summary(self, input_file: str) -> Optional[Dict[str, Any]]:
        """Возвращает сводку по состоянию пайплайна"""
        state = self.load_pipeline_state(input_file)
        
        if state is None:
            return None
        
        # Подсчитываем статистику
        total_checkpoints = len(state.checkpoints)
        successful_checkpoints = sum(1 for cp in state.checkpoints if cp.success)
        failed_checkpoints = total_checkpoints - successful_checkpoints
        
        # Определяем статус
        if state.failed_stage:
            status = "failed"
        elif len(state.completed_stages) == 0:
            status = "not_started"
        elif state.current_stage:
            status = "in_progress"
        else:
            status = "completed"
        
        return {
            "pipeline_id": state.pipeline_id,
            "input_file": state.input_file,
            "status": status,
            "created_at": state.created_at,
            "last_updated": state.last_updated,
            "completed_stages": state.completed_stages,
            "current_stage": state.current_stage,
            "failed_stage": state.failed_stage,
            "total_checkpoints": total_checkpoints,
            "successful_checkpoints": successful_checkpoints,
            "failed_checkpoints": failed_checkpoints,
            "metadata": state.metadata
        }
