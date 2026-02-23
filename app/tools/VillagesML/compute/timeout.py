"""
超时控制模块 (Timeout Control)

提供计算超时保护，防止长时间运行阻塞服务器
"""

import signal
import asyncio
from contextlib import contextmanager
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """超时异常"""
    pass


@contextmanager
def timeout(seconds: int):
    """
    超时上下文管理器（同步版本）

    Args:
        seconds: 超时时间（秒）

    Raises:
        TimeoutException: 如果计算超时

    Example:
        with timeout(5):
            result = expensive_computation()
    """
    def timeout_handler(signum, frame):
        raise TimeoutException(f"Computation exceeded {seconds} seconds")

    # 设置信号处理器
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


async def timeout_async(coro, seconds: int):
    """
    异步超时控制

    Args:
        coro: 协程对象
        seconds: 超时时间（秒）

    Returns:
        协程执行结果

    Raises:
        TimeoutException: 如果计算超时

    Example:
        result = await timeout_async(async_computation(), 5)
    """
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutException(f"Async computation exceeded {seconds} seconds")


def with_timeout(seconds: int):
    """
    超时装饰器

    Args:
        seconds: 超时时间（秒）

    Example:
        @with_timeout(5)
        def expensive_function():
            # ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            with timeout(seconds):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class TimeoutManager:
    """超时管理器"""

    def __init__(self, default_timeout: int = 5):
        """
        初始化超时管理器

        Args:
            default_timeout: 默认超时时间（秒）
        """
        self.default_timeout = default_timeout
        self.timeout_counts = {}  # 记录超时次数

    def execute_with_timeout(self, func: Callable, timeout_seconds: int = None,
                            *args, **kwargs) -> Any:
        """
        执行函数并应用超时控制

        Args:
            func: 要执行的函数
            timeout_seconds: 超时时间，如果为None则使用默认值
            *args, **kwargs: 函数参数

        Returns:
            函数执行结果

        Raises:
            TimeoutException: 如果执行超时
        """
        timeout_seconds = timeout_seconds or self.default_timeout
        func_name = func.__name__

        try:
            with timeout(timeout_seconds):
                result = func(*args, **kwargs)
                logger.info(f"Function {func_name} completed within {timeout_seconds}s")
                return result
        except TimeoutException as e:
            self.timeout_counts[func_name] = self.timeout_counts.get(func_name, 0) + 1
            logger.error(f"Function {func_name} timed out (count: {self.timeout_counts[func_name]})")
            raise

    def get_timeout_stats(self) -> dict:
        """
        获取超时统计信息

        Returns:
            超时统计字典
        """
        return {
            'default_timeout': self.default_timeout,
            'timeout_counts': self.timeout_counts.copy(),
            'total_timeouts': sum(self.timeout_counts.values())
        }


# 全局超时管理器
timeout_manager = TimeoutManager(default_timeout=5)
