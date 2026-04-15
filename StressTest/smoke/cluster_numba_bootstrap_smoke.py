"""
验证 numba 线程层默认引导逻辑。

目标：
1. 未显式配置时，默认将 NUMBA_THREADING_LAYER 设为 omp；
2. 在 macOS + Homebrew libomp 场景下，自动补齐动态库搜索路径；
3. 不覆盖用户已经显式给出的 NUMBA_THREADING_LAYER。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.common.numba_bootstrap import configure_numba_threading_environment


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    brew_libomp_dir = "/opt/homebrew/opt/libomp/lib"

    simulated_env = {}
    configure_numba_threading_environment(
        env=simulated_env,
        platform_name="darwin",
        path_exists=lambda path: path == brew_libomp_dir,
    )
    _assert(
        simulated_env.get("NUMBA_THREADING_LAYER") == "omp",
        "默认应该把 NUMBA_THREADING_LAYER 设为 omp",
    )
    _assert(
        brew_libomp_dir in simulated_env.get("DYLD_LIBRARY_PATH", ""),
        "macOS 下应自动补齐 Homebrew libomp 路径",
    )

    explicit_env = {"NUMBA_THREADING_LAYER": "workqueue"}
    configure_numba_threading_environment(
        env=explicit_env,
        platform_name="darwin",
        path_exists=lambda path: path == brew_libomp_dir,
    )
    _assert(
        explicit_env.get("NUMBA_THREADING_LAYER") == "workqueue",
        "不应覆盖用户显式给定的 NUMBA_THREADING_LAYER",
    )

    linux_env = {}
    configure_numba_threading_environment(
        env=linux_env,
        platform_name="linux",
        path_exists=lambda path: False,
    )
    _assert(
        linux_env.get("NUMBA_THREADING_LAYER") == "omp",
        "Linux 下默认也应倾向 omp",
    )
    _assert(
        "DYLD_LIBRARY_PATH" not in linux_env,
        "非 macOS 不应写入 DYLD_LIBRARY_PATH",
    )

    live_env = {
        key: value
        for key, value in os.environ.items()
        if key in {"NUMBA_THREADING_LAYER", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"}
    }
    configure_numba_threading_environment(env=live_env, platform_name=sys.platform)
    _assert(
        live_env.get("NUMBA_THREADING_LAYER"),
        "真实环境下也应至少产生 NUMBA_THREADING_LAYER 配置",
    )

    runtime_env = dict(os.environ)
    runtime_env.pop("NUMBA_THREADING_LAYER", None)
    runtime_env.pop("DYLD_LIBRARY_PATH", None)
    runtime_env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
    configure_numba_threading_environment(env=runtime_env, platform_name=sys.platform)
    runtime_code = """
import numba
from numba import njit, prange

@njit(parallel=True)
def f(n):
    total = 0
    for index in prange(n):
        total += index
    return total

f(10)
print({"threading_layer": numba.threading_layer(), "result": int(f(10))})
"""
    proc = subprocess.run(
        [sys.executable, "-c", runtime_code],
        env=runtime_env,
        capture_output=True,
        text=True,
    )
    _assert(proc.returncode == 0, f"子进程应能正常跑通 numba parallel: {proc.stderr}")
    _assert("'threading_layer': 'omp'" in proc.stdout, "子进程应默认进入 omp")

    print("cluster_numba_bootstrap_smoke: OK")


if __name__ == "__main__":
    main()
