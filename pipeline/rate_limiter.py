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


class DynamicRateLimiter(RateLimiter):
    """
    Расширенный rate limiter с динамическими лимитами и мониторингом.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60,
                 api_name: str = "unknown"):
        super().__init__(max_requests, window_seconds)
        self.api_name = api_name
        self.hit_count = 0
        self.blocked_count = 0
        self.total_wait_time = 0.0

    def is_allowed(self, key: str = "default") -> bool:
        """Переопределенный метод с мониторингом."""
        allowed = super().is_allowed(key)

        if allowed:
            self.hit_count += 1
        else:
            self.blocked_count += 1
            self.logger.warning(
                f"🚦 Rate limit превышен для {self.api_name}.{key} "
                f"({self.blocked_count} блокировок)"
            )

        return allowed

    def wait_if_needed(self, key: str = "default") -> float:
        """
        Ждет с отслеживанием времени ожидания.

        Returns:
            Время ожидания в секундах
        """
        wait_start = time.time()

        while not self.is_allowed(key):
            sleep_time = 1.0
            self.logger.info(
                f"⏳ Rate limit для {self.api_name}.{key}, ожидание {sleep_time}с..."
            )
            time.sleep(sleep_time)

        wait_time = time.time() - wait_start
        self.total_wait_time += wait_time

        if wait_time > 0:
            self.logger.info(
                f"✅ Rate limit ожидание завершено для {self.api_name}.{key} "
                f"({wait_time:.1f}с)"
            )

        return wait_time

    def get_statistics(self) -> dict:
        """Возвращает статистику использования."""
        total_requests = self.hit_count + self.blocked_count
        block_rate = (self.blocked_count / total_requests * 100) if total_requests > 0 else 0

        return {
            "api_name": self.api_name,
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "hit_count": self.hit_count,
            "blocked_count": self.blocked_count,
            "total_requests": total_requests,
            "block_rate_percent": block_rate,
            "total_wait_time": self.total_wait_time
        }

    def log_statistics(self) -> None:
        """Логирует статистику использования."""
        stats = self.get_statistics()
        self.logger.info(
            f"📊 Rate limiter {self.api_name}: "
            f"{stats['total_requests']} запросов, "
            f"{stats['block_rate_percent']:.1f}% блокировок, "
            f"общее ожидание: {stats['total_wait_time']:.1f}с"
        )


# Глобальные rate limiters с динамическими лимитами
def create_rate_limiters():
    """Создает rate limiters с настройками из переменных окружения."""
    import os

    # Pyannote.ai rate limiter
    pyannote_max_requests = int(os.getenv("PYANNOTE_RATE_LIMIT", "30"))
    pyannote_window = int(os.getenv("PYANNOTE_RATE_WINDOW", "60"))

    # OpenAI rate limiter
    openai_max_requests = int(os.getenv("OPENAI_RATE_LIMIT", "50"))
    openai_window = int(os.getenv("OPENAI_RATE_WINDOW", "60"))

    # Replicate rate limiter
    replicate_max_requests = int(os.getenv("REPLICATE_RATE_LIMIT", "100"))
    replicate_window = int(os.getenv("REPLICATE_RATE_WINDOW", "60"))

    return {
        "pyannote": DynamicRateLimiter(pyannote_max_requests, pyannote_window, "pyannote"),
        "openai": DynamicRateLimiter(openai_max_requests, openai_window, "openai"),
        "replicate": DynamicRateLimiter(replicate_max_requests, replicate_window, "replicate")
    }

# Глобальные rate limiters
RATE_LIMITERS = create_rate_limiters()

# Обратная совместимость
PYANNOTE_RATE_LIMITER = RATE_LIMITERS["pyannote"]
OPENAI_RATE_LIMITER = RATE_LIMITERS["openai"]


def rate_limit_decorator(api_name: str, key: str = "default"):
    """
    Декоратор для автоматического применения rate limiting к функциям.

    Args:
        api_name: Название API (pyannote, openai, replicate)
        key: Ключ для группировки запросов
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            limiter = RATE_LIMITERS.get(api_name)
            if limiter:
                limiter.wait_if_needed(key)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_rate_limiter(api_name: str) -> Optional[DynamicRateLimiter]:
    """
    Получает rate limiter для указанного API.

    Args:
        api_name: Название API

    Returns:
        Rate limiter или None если не найден
    """
    return RATE_LIMITERS.get(api_name)
