# pipeline/retry_mixin.py

import time
import random
from typing import Any, Callable, Dict, Optional, Type, Union
from functools import wraps
import requests
import openai


class RetryMixin:
    """
    Миксин для унифицированной retry логики.
    
    Предоставляет:
    - Интеллектуальный exponential backoff
    - Адаптивные таймауты
    - Статистика retry попыток
    - Специализированная обработка различных типов ошибок
    """
    
    def __init__(self):
        """Инициализация статистики retry."""
        # Статистика retry для мониторинга
        self.retry_stats = {
            "total_attempts": 0,
            "rate_limit_retries": 0,
            "connection_retries": 0,
            "timeout_retries": 0,
            "server_error_retries": 0,
            "other_retries": 0,
            "total_retry_time": 0.0,
            "successful_operations": 0,
            "failed_operations": 0
        }
    
    def calculate_intelligent_backoff(self, attempt: int, exception: Exception, 
                                    base_delay: float = 1.0, max_delay: float = 60.0,
                                    jitter: bool = True) -> float:
        """
        Вычисляет интеллектуальную задержку на основе типа ошибки.
        
        Args:
            attempt: Номер попытки (начиная с 1)
            exception: Исключение, которое вызвало retry
            base_delay: Базовая задержка в секундах
            max_delay: Максимальная задержка в секундах
            jitter: Добавлять ли случайное отклонение
            
        Returns:
            Задержка в секундах
        """
        # Определяем тип ошибки и соответствующую стратегию
        if isinstance(exception, (openai.RateLimitError, requests.exceptions.HTTPError)):
            if hasattr(exception, 'response') and exception.response:
                status_code = getattr(exception.response, 'status_code', 429)
                if status_code == 429:  # Rate limit
                    # Для rate limit - более агрессивный backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    self.retry_stats["rate_limit_retries"] += 1
                    
                    if hasattr(self, 'logger'):
                        self.logger.warning(
                            f"🚦 Rate limit (попытка {attempt}), ожидание {delay:.1f}с"
                        )
            else:
                # Общий случай rate limit
                delay = min(base_delay * (2 ** attempt), max_delay)
                self.retry_stats["rate_limit_retries"] += 1
        
        elif isinstance(exception, (openai.APIConnectionError, requests.exceptions.ConnectionError)):
            # Для сетевых ошибок - быстрые повторы
            delay = min(base_delay * (1.5 ** (attempt - 1)), 10.0)  # Максимум 10 секунд
            self.retry_stats["connection_retries"] += 1
            
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"🌐 Сетевая ошибка (попытка {attempt}), быстрый повтор через {delay:.1f}с"
                )
        
        elif isinstance(exception, (openai.APITimeoutError, requests.exceptions.Timeout)):
            # Для таймаутов - умеренный backoff
            delay = min(base_delay * (1.8 ** (attempt - 1)), 30.0)  # Максимум 30 секунд
            self.retry_stats["timeout_retries"] += 1
            
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"⏱️ Таймаут (попытка {attempt}), повтор через {delay:.1f}с"
                )
        
        elif isinstance(exception, (openai.InternalServerError, requests.exceptions.HTTPError)):
            # Для серверных ошибок - стандартный backoff
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            self.retry_stats["server_error_retries"] += 1
            
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"🔧 Серверная ошибка (попытка {attempt}), повтор через {delay:.1f}с"
                )
        
        else:
            # Для других ошибок - стандартный backoff
            delay = min(base_delay * (1.5 ** (attempt - 1)), max_delay)
            self.retry_stats["other_retries"] += 1
            
            if hasattr(self, 'logger'):
                self.logger.warning(
                    f"⚠️ Другая ошибка (попытка {attempt}), повтор через {delay:.1f}с: {type(exception).__name__}"
                )
        
        # Добавляем jitter для избежания thundering herd
        if jitter:
            jitter_amount = delay * 0.1  # 10% от задержки
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay)  # Минимум 0.1 секунды
        
        # Обновляем общее время retry
        self.retry_stats["total_retry_time"] += delay
        self.retry_stats["total_attempts"] += 1
        
        return delay
    
    def get_adaptive_timeout(self, file_size_mb: float, base_timeout: float = 30.0,
                           size_multiplier: float = 2.0, max_timeout: float = 1800.0) -> float:
        """
        Вычисляет адаптивный таймаут на основе размера файла.
        
        Args:
            file_size_mb: Размер файла в МБ
            base_timeout: Базовый таймаут в секундах
            size_multiplier: Множитель для размера файла
            max_timeout: Максимальный таймаут в секундах
            
        Returns:
            Адаптивный таймаут в секундах
        """
        # Формула: base_timeout + (file_size_mb * size_multiplier)
        adaptive_timeout = base_timeout + (file_size_mb * size_multiplier)
        
        # Ограничиваем максимальным значением
        adaptive_timeout = min(adaptive_timeout, max_timeout)
        
        if hasattr(self, 'logger'):
            self.logger.debug(
                f"📊 Адаптивный таймаут для файла {file_size_mb:.1f}MB: {adaptive_timeout:.1f}с"
            )
        
        return adaptive_timeout
    
    def retry_with_backoff(self, func: Callable, max_attempts: int = 3, 
                          base_delay: float = 1.0, max_delay: float = 60.0,
                          exceptions: tuple = None) -> Any:
        """
        Выполняет функцию с retry логикой.
        
        Args:
            func: Функция для выполнения
            max_attempts: Максимальное количество попыток
            base_delay: Базовая задержка
            max_delay: Максимальная задержка
            exceptions: Кортеж исключений для retry (по умолчанию - стандартные)
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Exception: Последнее исключение, если все попытки неудачны
        """
        if exceptions is None:
            exceptions = (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError
            )
        
        last_exception = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                result = func()
                self.retry_stats["successful_operations"] += 1
                
                if attempt > 1 and hasattr(self, 'logger'):
                    self.logger.info(f"✅ Операция успешна с попытки {attempt}")
                
                return result
                
            except exceptions as e:
                last_exception = e
                
                if attempt == max_attempts:
                    # Последняя попытка - не делаем retry
                    self.retry_stats["failed_operations"] += 1
                    if hasattr(self, 'logger'):
                        self.logger.error(
                            f"❌ Все {max_attempts} попыток неудачны. Последняя ошибка: {e}"
                        )
                    break
                
                # Вычисляем задержку и ждем
                delay = self.calculate_intelligent_backoff(
                    attempt, e, base_delay, max_delay
                )
                time.sleep(delay)
            
            except Exception as e:
                # Неожиданное исключение - не делаем retry
                self.retry_stats["failed_operations"] += 1
                if hasattr(self, 'logger'):
                    self.logger.error(f"❌ Неожиданная ошибка (не retry): {type(e).__name__}: {e}")
                raise
        
        # Если дошли сюда, значит все попытки неудачны
        if last_exception:
            raise last_exception
    
    def log_retry_statistics(self) -> Dict[str, Any]:
        """
        Логирует и возвращает статистику retry.
        
        Returns:
            Словарь со статистикой
        """
        total_operations = (
            self.retry_stats["successful_operations"] + 
            self.retry_stats["failed_operations"]
        )
        
        if total_operations == 0:
            return self.retry_stats
        
        success_rate = (
            self.retry_stats["successful_operations"] / total_operations * 100
        )
        
        avg_retry_time = (
            self.retry_stats["total_retry_time"] / 
            max(self.retry_stats["total_attempts"], 1)
        )
        
        if hasattr(self, 'logger'):
            self.logger.info(
                f"📊 Статистика retry: "
                f"{total_operations} операций, "
                f"{success_rate:.1f}% успех, "
                f"{self.retry_stats['total_attempts']} retry попыток, "
                f"среднее время retry: {avg_retry_time:.1f}с"
            )
            
            # Детальная статистика по типам ошибок
            if self.retry_stats["total_attempts"] > 0:
                self.logger.debug(
                    f"🔍 Детали retry: "
                    f"rate_limit={self.retry_stats['rate_limit_retries']}, "
                    f"connection={self.retry_stats['connection_retries']}, "
                    f"timeout={self.retry_stats['timeout_retries']}, "
                    f"server={self.retry_stats['server_error_retries']}, "
                    f"other={self.retry_stats['other_retries']}"
                )
        
        return {
            **self.retry_stats,
            "total_operations": total_operations,
            "success_rate": success_rate,
            "average_retry_time": avg_retry_time
        }
    
    def reset_retry_stats(self) -> None:
        """Сбрасывает статистику retry."""
        self.retry_stats = {
            "total_attempts": 0,
            "rate_limit_retries": 0,
            "connection_retries": 0,
            "timeout_retries": 0,
            "server_error_retries": 0,
            "other_retries": 0,
            "total_retry_time": 0.0,
            "successful_operations": 0,
            "failed_operations": 0
        }
        
        if hasattr(self, 'logger'):
            self.logger.debug("🔄 Статистика retry сброшена")
