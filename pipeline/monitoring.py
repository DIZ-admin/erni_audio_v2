# pipeline/monitoring.py

import time
import psutil
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import threading
from datetime import datetime


@dataclass
class SystemMetrics:
    """Системные метрики для мониторинга"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    
    
@dataclass
class PipelineMetrics:
    """Метрики пайплайна обработки"""
    timestamp: str
    total_files_processed: int
    successful_processes: int
    failed_processes: int
    average_processing_time: float
    current_processing_time: Optional[float]
    api_calls_count: int
    rate_limit_hits: int


class PerformanceMonitor:
    """
    Монитор производительности для отслеживания метрик системы и пайплайна.
    
    Собирает и сохраняет метрики для последующего анализа и алертинга.
    """
    
    def __init__(self, metrics_dir: Path = Path("logs/metrics")):
        self.metrics_dir = metrics_dir
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Счетчики пайплайна
        self.total_files = 0
        self.successful_files = 0
        self.failed_files = 0
        self.processing_times = []
        self.api_calls = 0
        self.rate_limit_hits = 0
        self.current_start_time = None
        
        # Блокировка для thread-safety
        self.lock = threading.Lock()
        
    def start_processing(self) -> None:
        """Отмечает начало обработки файла"""
        with self.lock:
            self.current_start_time = time.time()
            self.total_files += 1
    
    def end_processing(self, success: bool = True) -> None:
        """Отмечает окончание обработки файла"""
        with self.lock:
            if self.current_start_time:
                processing_time = time.time() - self.current_start_time
                self.processing_times.append(processing_time)
                self.current_start_time = None
                
                if success:
                    self.successful_files += 1
                else:
                    self.failed_files += 1
    
    def record_api_call(self) -> None:
        """Записывает API вызов"""
        with self.lock:
            self.api_calls += 1
    
    def record_rate_limit_hit(self) -> None:
        """Записывает попадание в rate limit"""
        with self.lock:
            self.rate_limit_hits += 1
    
    def get_system_metrics(self) -> SystemMetrics:
        """Получает текущие системные метрики"""
        try:
            # CPU и память
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Дисковое пространство
            disk = psutil.disk_usage('/')
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                disk_usage_percent=(disk.used / disk.total) * 100,
                disk_free_gb=disk.free / 1024 / 1024 / 1024
            )
        except Exception as e:
            self.logger.error(f"Ошибка получения системных метрик: {e}")
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0
            )
    
    def get_pipeline_metrics(self) -> PipelineMetrics:
        """Получает метрики пайплайна"""
        with self.lock:
            avg_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0.0
            current_time = time.time() - self.current_start_time if self.current_start_time else None
            
            return PipelineMetrics(
                timestamp=datetime.now().isoformat(),
                total_files_processed=self.total_files,
                successful_processes=self.successful_files,
                failed_processes=self.failed_files,
                average_processing_time=avg_time,
                current_processing_time=current_time,
                api_calls_count=self.api_calls,
                rate_limit_hits=self.rate_limit_hits
            )
    
    def save_metrics(self) -> None:
        """Сохраняет текущие метрики в файл"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Системные метрики
            system_metrics = self.get_system_metrics()
            system_file = self.metrics_dir / f"system_{timestamp}.json"
            with open(system_file, 'w') as f:
                json.dump(asdict(system_metrics), f, indent=2)
            
            # Метрики пайплайна
            pipeline_metrics = self.get_pipeline_metrics()
            pipeline_file = self.metrics_dir / f"pipeline_{timestamp}.json"
            with open(pipeline_file, 'w') as f:
                json.dump(asdict(pipeline_metrics), f, indent=2)
                
            self.logger.debug(f"Метрики сохранены: {system_file}, {pipeline_file}")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения метрик: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Возвращает статус здоровья системы"""
        system_metrics = self.get_system_metrics()
        pipeline_metrics = self.get_pipeline_metrics()
        
        # Определяем статус здоровья
        health_issues = []
        
        if system_metrics.cpu_percent > 90:
            health_issues.append("Высокая загрузка CPU")
        
        if system_metrics.memory_percent > 90:
            health_issues.append("Высокое использование памяти")
        
        if system_metrics.disk_free_gb < 1:
            health_issues.append("Мало свободного места на диске")
        
        if pipeline_metrics.failed_processes > pipeline_metrics.successful_processes:
            health_issues.append("Высокий процент ошибок обработки")
        
        if pipeline_metrics.rate_limit_hits > 10:
            health_issues.append("Частые попадания в rate limit")
        
        status = "healthy" if not health_issues else "warning" if len(health_issues) < 3 else "critical"
        
        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "issues": health_issues,
            "system": asdict(system_metrics),
            "pipeline": asdict(pipeline_metrics)
        }


# Глобальный монитор производительности
PERFORMANCE_MONITOR = PerformanceMonitor()


def log_performance_metrics(func):
    """Декоратор для автоматического логирования метрик производительности"""
    def wrapper(*args, **kwargs):
        PERFORMANCE_MONITOR.start_processing()
        try:
            result = func(*args, **kwargs)
            PERFORMANCE_MONITOR.end_processing(success=True)
            return result
        except Exception as e:
            PERFORMANCE_MONITOR.end_processing(success=False)
            raise
    return wrapper
