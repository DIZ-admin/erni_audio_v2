# pipeline/rate_limit_mixin.py

from typing import Optional, Callable, Any
from .rate_limiter import get_rate_limiter, DynamicRateLimiter


class RateLimitMixin:
    """
    Миксин для интеграции rate limiting в агенты.
    
    Предоставляет методы для:
    - Автоматического rate limiting API вызовов
    - Мониторинга использования лимитов
    - Graceful degradation при превышении лимитов
    """
    
    def __init__(self, api_name: Optional[str] = None):
        """
        Инициализация rate limiting.
        
        Args:
            api_name: Название API для rate limiting (pyannote, openai, replicate)
        """
        self.api_name = api_name
        self._rate_limiter: Optional[DynamicRateLimiter] = None
        
        if api_name:
            self._rate_limiter = get_rate_limiter(api_name)
            if self._rate_limiter and hasattr(self, 'logger'):
                self.logger.debug(
                    f"🚦 Rate limiter инициализирован для {api_name}: "
                    f"{self._rate_limiter.max_requests} req/{self._rate_limiter.window_seconds}s"
                )
    
    def with_rate_limit(self, func: Callable, operation_key: str = "default", 
                       timeout: Optional[float] = None) -> Any:
        """
        Выполняет функцию с rate limiting.
        
        Args:
            func: Функция для выполнения
            operation_key: Ключ операции для группировки
            timeout: Максимальное время ожидания rate limit (секунды)
            
        Returns:
            Результат выполнения функции
            
        Raises:
            TimeoutError: Если превышено время ожидания rate limit
        """
        if not self._rate_limiter:
            # Если rate limiter не настроен, выполняем без ограничений
            return func()
        
        # Ждем разрешения от rate limiter
        wait_time = self._rate_limiter.wait_if_needed(operation_key)
        
        # Проверяем таймаут
        if timeout and wait_time > timeout:
            error_msg = (
                f"Rate limit ожидание ({wait_time:.1f}с) превысило таймаут ({timeout}с) "
                f"для {self.api_name}.{operation_key}"
            )
            if hasattr(self, 'logger'):
                self.logger.error(f"⏰ {error_msg}")
            raise TimeoutError(error_msg)
        
        # Выполняем функцию
        try:
            result = func()
            
            if wait_time > 0 and hasattr(self, 'logger'):
                self.logger.debug(
                    f"✅ Операция {self.api_name}.{operation_key} выполнена "
                    f"после ожидания {wait_time:.1f}с"
                )
            
            return result
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(
                    f"❌ Ошибка в операции {self.api_name}.{operation_key} "
                    f"после ожидания {wait_time:.1f}с: {e}"
                )
            raise
    
    def check_rate_limit_status(self, operation_key: str = "default") -> dict:
        """
        Проверяет текущий статус rate limit.
        
        Args:
            operation_key: Ключ операции
            
        Returns:
            Словарь со статусом rate limit
        """
        if not self._rate_limiter:
            return {
                "rate_limit_enabled": False,
                "remaining_requests": float('inf'),
                "api_name": self.api_name or "unknown"
            }
        
        remaining = self._rate_limiter.get_remaining_requests(operation_key)
        is_allowed = self._rate_limiter.is_allowed(operation_key)
        
        # Если проверили is_allowed, нужно "вернуть" запрос обратно
        if is_allowed and self._rate_limiter.requests[operation_key]:
            self._rate_limiter.requests[operation_key].pop()
        
        return {
            "rate_limit_enabled": True,
            "api_name": self.api_name,
            "remaining_requests": remaining,
            "is_allowed": is_allowed,
            "max_requests": self._rate_limiter.max_requests,
            "window_seconds": self._rate_limiter.window_seconds
        }
    
    def log_rate_limit_statistics(self) -> Optional[dict]:
        """
        Логирует статистику rate limiting.
        
        Returns:
            Словарь со статистикой или None если rate limiter не настроен
        """
        if not self._rate_limiter:
            return None
        
        stats = self._rate_limiter.get_statistics()
        
        if hasattr(self, 'logger'):
            self.logger.info(
                f"📊 Rate limit статистика {self.api_name}: "
                f"{stats['total_requests']} запросов, "
                f"{stats['blocked_count']} блокировок "
                f"({stats['block_rate_percent']:.1f}%), "
                f"общее ожидание: {stats['total_wait_time']:.1f}с"
            )
        
        return stats
    
    def reset_rate_limit_stats(self, operation_key: Optional[str] = None) -> None:
        """
        Сбрасывает статистику rate limiting.
        
        Args:
            operation_key: Ключ операции для сброса (если None, сбрасывает все)
        """
        if not self._rate_limiter:
            return
        
        self._rate_limiter.reset(operation_key)
        
        if hasattr(self, 'logger'):
            if operation_key:
                self.logger.debug(f"🔄 Rate limit статистика сброшена для {operation_key}")
            else:
                self.logger.debug("🔄 Вся rate limit статистика сброшена")
    
    def get_rate_limit_info(self) -> dict:
        """
        Возвращает информацию о настройках rate limiting.
        
        Returns:
            Словарь с информацией о rate limiting
        """
        if not self._rate_limiter:
            return {
                "enabled": False,
                "api_name": self.api_name or "unknown",
                "reason": "Rate limiter not configured"
            }
        
        return {
            "enabled": True,
            "api_name": self.api_name,
            "max_requests": self._rate_limiter.max_requests,
            "window_seconds": self._rate_limiter.window_seconds,
            "current_statistics": self._rate_limiter.get_statistics()
        }
    
    def is_rate_limited(self, operation_key: str = "default") -> bool:
        """
        Проверяет, заблокирована ли операция rate limiting.
        
        Args:
            operation_key: Ключ операции
            
        Returns:
            True если операция заблокирована rate limiting
        """
        if not self._rate_limiter:
            return False
        
        # Проверяем без добавления запроса в счетчик
        with self._rate_limiter.lock:
            import time
            now = time.time()
            window_start = now - self._rate_limiter.window_seconds
            
            # Удаляем старые запросы из окна
            while (self._rate_limiter.requests[operation_key] and 
                   self._rate_limiter.requests[operation_key][0] < window_start):
                self._rate_limiter.requests[operation_key].popleft()
            
            # Проверяем лимит без добавления запроса
            return len(self._rate_limiter.requests[operation_key]) >= self._rate_limiter.max_requests
