# pipeline/base_agent.py

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Union
import os


class BaseAgent(ABC):
    """
    Базовый класс для всех агентов в pipeline.
    
    Предоставляет общую функциональность:
    - Унифицированное логирование с эмодзи
    - Стандартная обработка ошибок
    - Метрики производительности
    - Общие утилиты
    """
    
    def __init__(self, name: Optional[str] = None):
        """
        Инициализация базового агента.
        
        Args:
            name: Имя агента для логирования (по умолчанию - имя класса)
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        
        # Метрики производительности
        self._start_time: Optional[float] = None
        self._operation_count = 0
        self._total_processing_time = 0.0
        
        # Статистика ошибок
        self._error_count = 0
        self._last_error: Optional[Exception] = None
        
        self.logger.debug(f"🚀 Инициализирован {self.name}")
    
    def start_operation(self, operation_name: str = "operation") -> None:
        """Начинает отслеживание времени операции."""
        self._start_time = time.time()
        self._operation_count += 1
        self.logger.info(f"🔄 Начинаю {operation_name}...")
    
    def end_operation(self, operation_name: str = "operation", success: bool = True) -> float:
        """
        Завершает отслеживание времени операции.
        
        Args:
            operation_name: Название операции
            success: Успешно ли завершена операция
            
        Returns:
            Время выполнения в секундах
        """
        if self._start_time is None:
            self.logger.warning("⚠️ end_operation вызван без start_operation")
            return 0.0
        
        duration = time.time() - self._start_time
        self._total_processing_time += duration
        
        if success:
            self.logger.info(f"✅ {operation_name} завершена за {duration:.2f}с")
        else:
            self.logger.error(f"❌ {operation_name} завершена с ошибкой за {duration:.2f}с")
            self._error_count += 1
        
        self._start_time = None
        return duration
    
    def log_performance_metrics(self) -> Dict[str, Any]:
        """
        Логирует и возвращает метрики производительности.
        
        Returns:
            Словарь с метриками
        """
        metrics = {
            "agent_name": self.name,
            "operation_count": self._operation_count,
            "total_processing_time": self._total_processing_time,
            "average_processing_time": (
                self._total_processing_time / self._operation_count 
                if self._operation_count > 0 else 0.0
            ),
            "error_count": self._error_count,
            "success_rate": (
                (self._operation_count - self._error_count) / self._operation_count * 100
                if self._operation_count > 0 else 100.0
            )
        }
        
        self.logger.info(
            f"📊 Метрики {self.name}: "
            f"{metrics['operation_count']} операций, "
            f"{metrics['success_rate']:.1f}% успех, "
            f"среднее время: {metrics['average_processing_time']:.2f}с"
        )
        
        return metrics
    
    def handle_error(self, error: Exception, operation_name: str = "operation", 
                    reraise: bool = True) -> None:
        """
        Стандартная обработка ошибок.
        
        Args:
            error: Исключение для обработки
            operation_name: Название операции, где произошла ошибка
            reraise: Перебрасывать ли исключение после логирования
        """
        self._last_error = error
        self._error_count += 1
        
        error_type = type(error).__name__
        self.logger.error(f"❌ Ошибка в {operation_name}: {error_type}: {error}")
        
        if reraise:
            raise RuntimeError(f"Ошибка в {self.name}.{operation_name}: {error}") from error
    
    def get_api_key(self, key_name: str, env_vars: list[str]) -> str:
        """
        Получает API ключ из переменных окружения.
        
        Args:
            key_name: Название ключа для сообщений об ошибках
            env_vars: Список переменных окружения для поиска ключа
            
        Returns:
            API ключ
            
        Raises:
            ValueError: Если ключ не найден
        """
        for env_var in env_vars:
            api_key = os.getenv(env_var)
            if api_key:
                self.logger.debug(f"🔑 {key_name} ключ найден в {env_var}")
                return api_key
        
        env_vars_str = ", ".join(env_vars)
        error_msg = f"Требуется {key_name} ключ. Установите одну из переменных: {env_vars_str}"
        self.logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    def log_with_emoji(self, level: str, emoji: str, message: str) -> None:
        """
        Логирует сообщение с эмодзи.
        
        Args:
            level: Уровень логирования (info, warning, error, debug)
            emoji: Эмодзи для сообщения
            message: Текст сообщения
        """
        formatted_message = f"{emoji} {message}"
        
        if level == "info":
            self.logger.info(formatted_message)
        elif level == "warning":
            self.logger.warning(formatted_message)
        elif level == "error":
            self.logger.error(formatted_message)
        elif level == "debug":
            self.logger.debug(formatted_message)
        else:
            self.logger.info(formatted_message)
    
    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """
        Основной метод выполнения агента.
        Должен быть реализован в каждом наследнике.
        """
        pass
    
    def __str__(self) -> str:
        """Строковое представление агента."""
        return f"{self.name}(operations={self._operation_count}, errors={self._error_count})"
    
    def __repr__(self) -> str:
        """Детальное представление агента."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"operations={self._operation_count}, "
            f"errors={self._error_count}, "
            f"total_time={self._total_processing_time:.2f}s"
            f")"
        )
