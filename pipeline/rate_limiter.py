# pipeline/rate_limiter.py

import time
import threading
from collections import defaultdict, deque
from typing import Dict, Optional
import logging


class RateLimiter:
    """
    Простой rate limiter для ограничения количества запросов к API.
    
    Реализует алгоритм sliding window для точного контроля частоты запросов.
    Thread-safe для использования в многопоточных приложениях.
    """
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        """
        Args:
            max_requests: Максимальное количество запросов в окне
            window_seconds: Размер окна в секундах
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
    def is_allowed(self, key: str = "default") -> bool:
        """
        Проверяет, разрешен ли запрос для данного ключа.
        
        Args:
            key: Ключ для группировки запросов (например, API endpoint)
            
        Returns:
            True если запрос разрешен, False если превышен лимит
        """
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Удаляем старые запросы из окна
            while self.requests[key] and self.requests[key][0] < window_start:
                self.requests[key].popleft()
            
            # Проверяем лимит
            if len(self.requests[key]) >= self.max_requests:
                self.logger.warning(f"Rate limit exceeded for key: {key}")
                return False
            
            # Добавляем текущий запрос
            self.requests[key].append(now)
            return True
    
    def wait_if_needed(self, key: str = "default") -> None:
        """
        Ждет, если необходимо, чтобы не превысить лимит.
        
        Args:
            key: Ключ для группировки запросов
        """
        while not self.is_allowed(key):
            sleep_time = 1.0  # Ждем 1 секунду перед повторной проверкой
            self.logger.info(f"Rate limit reached for {key}, waiting {sleep_time}s...")
            time.sleep(sleep_time)
    
    def get_remaining_requests(self, key: str = "default") -> int:
        """
        Возвращает количество оставшихся запросов в текущем окне.
        
        Args:
            key: Ключ для группировки запросов
            
        Returns:
            Количество оставшихся запросов
        """
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Удаляем старые запросы
            while self.requests[key] and self.requests[key][0] < window_start:
                self.requests[key].popleft()
            
            return max(0, self.max_requests - len(self.requests[key]))
    
    def reset(self, key: Optional[str] = None) -> None:
        """
        Сбрасывает счетчики для ключа или всех ключей.
        
        Args:
            key: Ключ для сброса (если None, сбрасывает все)
        """
        with self.lock:
            if key is None:
                self.requests.clear()
                self.logger.info("Rate limiter reset for all keys")
            else:
                self.requests[key].clear()
                self.logger.info(f"Rate limiter reset for key: {key}")


# Глобальные rate limiters для разных API
PYANNOTE_RATE_LIMITER = RateLimiter(max_requests=30, window_seconds=60)  # 30 req/min для Pyannote
OPENAI_RATE_LIMITER = RateLimiter(max_requests=50, window_seconds=60)    # 50 req/min для OpenAI


def rate_limit_decorator(limiter: RateLimiter, key: str = "default"):
    """
    Декоратор для автоматического применения rate limiting к функциям.
    
    Args:
        limiter: Экземпляр RateLimiter
        key: Ключ для группировки запросов
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed(key)
            return func(*args, **kwargs)
        return wrapper
    return decorator
