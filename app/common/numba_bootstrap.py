"""
numba 线程层启动引导。

目标很简单：
1. 在未显式配置时，默认把 NUMBA_THREADING_LAYER 设为 omp；
2. 在 macOS + Homebrew 环境下，尽量自动补齐 libomp 的搜索路径；
3. 尊重用户已经显式给出的 NUMBA_THREADING_LAYER，不强行覆盖。

这里不直接导入 numba，只负责在进程尽早阶段准备环境变量。
"""

from __future__ import annotations

import os
import sys
from typing import Callable, MutableMapping, Optional


DEFAULT_NUMBA_THREADING_LAYER = "omp"
_BOOTSTRAP_APPLIED = False
_REEXEC_SENTINEL = "DIALECTS_NUMBA_BOOTSTRAP_REEXECED"
_MACOS_LIBOMP_CANDIDATES = (
    "/opt/homebrew/opt/libomp/lib",
    "/usr/local/opt/libomp/lib",
)


def _prepend_path_value(
    current_value: Optional[str],
    new_path: str,
) -> str:
    if not current_value:
        return new_path

    parts = [item for item in current_value.split(os.pathsep) if item]
    if new_path in parts:
        return current_value
    return os.pathsep.join([new_path, *parts])


def configure_numba_threading_environment(
    *,
    env: Optional[MutableMapping[str, str]] = None,
    platform_name: Optional[str] = None,
    path_exists: Optional[Callable[[str], bool]] = None,
) -> MutableMapping[str, str]:
    """
    纯配置函数，便于 smoke / 单测直接验证。

    不做任何 numba import，只修改传入的环境映射并返回。
    """
    target_env = env if env is not None else os.environ
    current_platform = (platform_name or sys.platform).lower()
    exists = path_exists or os.path.isdir

    configured_layer = str(target_env.get("NUMBA_THREADING_LAYER") or "").strip()
    if not configured_layer:
        target_env["NUMBA_THREADING_LAYER"] = DEFAULT_NUMBA_THREADING_LAYER
        configured_layer = DEFAULT_NUMBA_THREADING_LAYER

    effective_layer = configured_layer.lower()
    should_prepare_omp_runtime = effective_layer in {"omp", "safe", "threadsafe"}

    if current_platform.startswith("darwin") and should_prepare_omp_runtime:
        for candidate in _MACOS_LIBOMP_CANDIDATES:
            if not exists(candidate):
                continue

            target_env["DYLD_LIBRARY_PATH"] = _prepend_path_value(
                target_env.get("DYLD_LIBRARY_PATH"),
                candidate,
            )
            target_env["DYLD_FALLBACK_LIBRARY_PATH"] = _prepend_path_value(
                target_env.get("DYLD_FALLBACK_LIBRARY_PATH"),
                candidate,
            )
            break

    return target_env


def bootstrap_numba_threading_environment() -> MutableMapping[str, str]:
    """
    进程级引导入口。

    这个函数是幂等的，可以在多个入口重复调用。
    """
    global _BOOTSTRAP_APPLIED
    if _BOOTSTRAP_APPLIED:
        return os.environ

    configured = configure_numba_threading_environment()
    _BOOTSTRAP_APPLIED = True
    return configured


def restart_current_python_process_for_numba_environment(
    argv: Optional[list[str]] = None,
) -> bool:
    """
    在 macOS 本地开发模式下，必要时带着修正后的环境重启当前 Python 进程。

    原因：
    - Homebrew 的 libomp 路径通常不在系统默认搜索路径里；
    - 仅在 Python 进程内部临时写 DYLD_* 环境变量，对 numba/omppool 不一定足够；
    - 让新进程从启动时就带上环境，才能稳定进入 omp。

    返回值：
    - False: 当前无需重启；
    - True: 已调用 os.execvpe 重启当前进程（正常情况下不会返回）。
    """
    if not sys.platform.lower().startswith("darwin"):
        return False
    if os.environ.get(_REEXEC_SENTINEL) == "1":
        return False

    desired_env = dict(os.environ)
    configure_numba_threading_environment(env=desired_env)

    keys_to_compare = (
        "NUMBA_THREADING_LAYER",
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
    )
    changed = any(desired_env.get(key) != os.environ.get(key) for key in keys_to_compare)
    if not changed:
        return False

    desired_env[_REEXEC_SENTINEL] = "1"
    current_argv = list(argv or sys.argv)
    os.execvpe(sys.executable, [sys.executable, *current_argv], desired_env)
    return True


__all__ = [
    "DEFAULT_NUMBA_THREADING_LAYER",
    "bootstrap_numba_threading_environment",
    "configure_numba_threading_environment",
    "restart_current_python_process_for_numba_environment",
]
