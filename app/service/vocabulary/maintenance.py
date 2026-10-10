"""vocabulary.db 启动维护：按膨胀率回收空闲页，并刷新查询统计。

导入是按地点整批 delete 再 insert，而 auto_vacuum 关闭，释放的页不会还给文件，
所以文件会持续膨胀（实测空闲页曾占到 35%）。这里在启动时按空闲页占比决定是否
VACUUM，并总是跑 ANALYZE 刷新 sqlite_stat1。

必须在 gunicorn master（或单进程模式）里只跑一次：VACUUM 需要独占锁和约 2 倍
文件的临时空间，多个 worker 同时跑会互相抢锁，把启动拖到 busy_timeout 之外。
"""

import sqlite3
import time
from pathlib import Path

from app.common.path import VOCABULARY_DB_PATH

# 空闲页占比达到该阈值才值得重写整个文件
FREE_PAGE_RATIO_THRESHOLD = 0.15
# 小库重写收益有限，页数低于此值不触发 VACUUM
MIN_PAGES_FOR_VACUUM = 1024
BUSY_TIMEOUT_SECONDS = 10.0


def _format_mb(byte_count: int) -> str:
    return f"{byte_count / 1024 / 1024:.1f}MB"


def _read_page_stats(cursor: sqlite3.Cursor) -> tuple[int, int, int]:
    page_size = cursor.execute("PRAGMA page_size").fetchone()[0]
    page_count = cursor.execute("PRAGMA page_count").fetchone()[0]
    freelist_count = cursor.execute("PRAGMA freelist_count").fetchone()[0]
    return page_size, page_count, freelist_count


def maintain_vocabulary_database(
    *,
    force: bool = False,
    db_path: str | Path = VOCABULARY_DB_PATH,
) -> dict:
    """按需回收空闲页并刷新查询统计。

    force=True 时忽略膨胀率强制 VACUUM。任何失败都只记录告警、不抛出，
    避免维护动作阻塞服务启动。
    """
    if not Path(db_path).exists():
        print(f"[vocabulary] 维护跳过：{db_path} 不存在")
        return {"status": "missing"}

    started_at = time.monotonic()
    try:
        # isolation_level=None 走自动提交，VACUUM 不允许在事务内执行
        conn = sqlite3.connect(
            db_path,
            timeout=BUSY_TIMEOUT_SECONDS,
            isolation_level=None,
        )
    except sqlite3.Error as exc:
        print(f"[!] vocabulary 维护跳过：无法打开数据库（{exc}）")
        return {"status": "error", "error": str(exc)}

    try:
        page_size, page_count, freelist_count = _read_page_stats(conn.cursor())
        free_ratio = freelist_count / page_count if page_count else 0.0
        should_vacuum = force or (
            page_count >= MIN_PAGES_FOR_VACUUM
            and free_ratio >= FREE_PAGE_RATIO_THRESHOLD
        )

        if should_vacuum:
            conn.execute("VACUUM")

        conn.execute("ANALYZE")

        _, page_count_after, freelist_after = _read_page_stats(conn.cursor())
    except sqlite3.Error as exc:
        print(f"[!] vocabulary 维护失败：{exc}")
        return {"status": "error", "error": str(exc)}
    finally:
        conn.close()

    elapsed = time.monotonic() - started_at
    before_bytes = page_count * page_size
    after_bytes = page_count_after * page_size

    if should_vacuum:
        print(
            f"[vocabulary] VACUUM {_format_mb(before_bytes)} -> {_format_mb(after_bytes)}"
            f"（空闲页 {freelist_count}/{page_count} -> {freelist_after}/{page_count_after}），"
            f"ANALYZE 完成，用时 {elapsed:.2f}s"
        )
    else:
        print(
            f"[vocabulary] 跳過 VACUUM（空闲页占比 {free_ratio:.1%} < "
            f"{FREE_PAGE_RATIO_THRESHOLD:.0%}），仅刷新 ANALYZE，用时 {elapsed:.2f}s"
        )

    return {
        "status": "ok",
        "vacuumed": should_vacuum,
        "bytes_before": before_bytes,
        "bytes_after": after_bytes,
        "freelist_before": freelist_count,
        "freelist_after": freelist_after,
        "elapsed_seconds": elapsed,
    }
