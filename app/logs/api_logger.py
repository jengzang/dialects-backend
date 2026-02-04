import asyncio
# import gzip
# import io
# import json
# import os
import threading
import multiprocessing  # [FIX] 改用跨进程队列
# import re
import time
from datetime import datetime, timedelta
# from collections import defaultdict
# import ast
from decimal import Decimal
# from typing import AsyncIterable, Optional

from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session
# from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from queue import Empty  # 只引入這個異常類，不引入 Queue 類
from app.auth.database import get_db
from app.auth.dependencies import get_current_user, get_current_user_for_middleware
from app.auth.models import ApiUsageLog, ApiUsageSummary, User
from app.logs.database import SessionLocal as LogsSessionLocal
from app.logs.models import ApiKeywordLog, ApiStatistics, ApiVisitLog
from common.config import KEYWORD_LOG_FILE, SUMMARY_FILE, API_USAGE_FILE, API_DETAILED_JSON, API_DETAILED_FILE, \
    CLEAR_WEEK, RECORD_API, MAX_ANONYMOUS_SIZE, MAX_USER_SIZE, BATCH_SIZE, SIZE_THRESHOLD, IGNORE_API

# === 队列（跨进程） ===
# [FIX] 改用 multiprocessing.Queue 以支持主进程中的后台线程
# keyword_queue = queue.Queue()  # [X] 不再使用 txt文件队列
log_queue = multiprocessing.Queue(maxsize=2000)  # [OK] ApiUsageLog 队列（auth.db）- 限制 2000 条
keyword_log_queue = multiprocessing.Queue(maxsize=5000)  # [OK] ApiKeywordLog 队列（logs.db）- 限制 5000 条
statistics_queue = multiprocessing.Queue(maxsize=1000)  # [OK] ApiStatistics 队列（logs.db）- 限制 1000 条
html_visit_queue = multiprocessing.Queue(maxsize=500)  # [OK] HTML 页面访问统计队列（logs.db）- 限制 500 条
summary_queue = multiprocessing.Queue(maxsize=1000)  # [NEW] ApiUsageSummary 队列（auth.db）- 限制 1000 条


# === 关键词日志（写入logs.db） ===
def log_keyword(path: str, field: str, value):
    """记录 API 调用的参数关键词到数据库"""
    timestamp = datetime.now()
    log = ApiKeywordLog(
        timestamp=timestamp,
        path=path,
        field=field,
        value=str(value)
    )
    keyword_log_queue.put(log)


def log_all_fields(path: str, param_dict: dict):
    """记录 API 调用的所有参数"""
    for field, value in param_dict.items():
        if value is not None and value != [] and value != "":
            log_keyword(path, field, value)


# ===关键词日志写入线程（logs.db）===
def keyword_log_writer():
    """后台线程：批量写入 ApiKeywordLog 到 logs.db"""
    batch = []
    batch_size = 50  # 每 50 条批量写入一次

    while True:
        try:
            # 等待队列中的数据，超时1秒
            item = keyword_log_queue.get(timeout=1)
            if item is None:  # 停止信号
                break

            batch.append(item)

            # 批量写入
            if len(batch) >= batch_size:
                db = LogsSessionLocal()
                try:
                    db.bulk_save_objects(batch)
                    db.commit()
                    batch = []
                except Exception as e:
                    print(f"[X] 写入关键词日志失败: {e}")
                    db.rollback()
                finally:
                    db.close()

        except Empty:
            # 队列空时，写入剩余数据
            if batch:
                db = LogsSessionLocal()
                try:
                    db.bulk_save_objects(batch)
                    db.commit()
                    batch = []
                except Exception as e:
                    print(f"[X] 写入关键词日志失败: {e}")
                    db.rollback()
                finally:
                    db.close()
        except Exception as e:
            print(f"[X] 关键词日志线程错误: {e}")

    # 线程结束前，写入剩余数据
    if batch:
        db = LogsSessionLocal()
        try:
            db.bulk_save_objects(batch)
            db.commit()
        except Exception as e:
            print(f"[X] 写入关键词日志失败: {e}")
            db.rollback()
        finally:
            db.close()


# === API统计更新线程（logs.db）===
def statistics_writer():
    """后台线程：批量更新 ApiStatistics"""
    batch = []
    batch_size = 50
    batch_timeout = 120.0

    while True:
        try:
            item = statistics_queue.get(timeout=batch_timeout)
            if item is None:  # 停止信号
                break

            batch.append(item)

            # 批次满时写入
            if len(batch) >= batch_size:
                _process_statistics_batch(batch)
                batch = []

        except Empty:
            # 超时时写入剩余项
            if batch:
                _process_statistics_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] statistics_writer 错误: {e}")

    # 线程结束前写入剩余数据
    if batch:
        _process_statistics_batch(batch)


def _process_statistics_batch(batch: list):
    """批量处理统计更新"""
    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:
            # 更新总计
            update_statistic(db, "usage_total", None, "path", path)

            # 更新每日统计
            if date_obj:
                update_statistic(db, "usage_daily", date_obj, "path", path)

        db.commit()
        print(f"[OK] 批量更新 {len(batch)} 条统计")
    except Exception as e:
        print(f"[X] 统计批次失败: {e}")
        db.rollback()
    finally:
        db.close()


def update_statistic(db: Session, stat_type: str, date: datetime, category: str, item: str):
    """更新或创建统计记录（使用 UPSERT 避免并发问题）"""
    from sqlalchemy import text

    # 使用 SQLite 的 INSERT OR IGNORE + UPDATE 策略
    try:
        # 先尝试更新
        result = db.execute(
            text("""
                UPDATE api_statistics
                SET count = count + 1, updated_at = datetime('now')
                WHERE stat_type = :stat_type
                  AND category = :category
                  AND item = :item
                  AND (
                    (date IS NULL AND :date IS NULL) OR
                    (date = :date)
                  )
            """),
            {
                "stat_type": stat_type,
                "date": date,
                "category": category,
                "item": item
            }
        )

        # 如果没有更新任何行（记录不存在），则插入新记录
        if result.rowcount == 0:
            db.execute(
                text("""
                    INSERT OR IGNORE INTO api_statistics (stat_type, date, category, item, count, updated_at)
                    VALUES (:stat_type, :date, :category, :item, 1, datetime('now'))
                """),
                {
                    "stat_type": stat_type,
                    "date": date,
                    "category": category,
                    "item": item
                }
            )
    except Exception as e:
        print(f"[X] 更新统计失败: stat_type={stat_type}, category={category}, item={item}, error={e}")
        raise



# === API调用统计（写入logs.db）===
def update_count(path: str):
    """更新 API 调用次数统计"""
    today = datetime.now()
    statistics_queue.put((path, today))


def update_html_visit(path: str):
    """更新 HTML 页面访问次数统计"""
    today = datetime.now()
    html_visit_queue.put((path, today))


# === HTML 页面访问统计写入线程（logs.db）===
def html_visit_writer():
    """后台线程：批量更新 HTML 页面访问统计"""
    batch = []
    batch_size = 3
    batch_timeout = 5.0

    while True:
        try:
            item = html_visit_queue.get(timeout=batch_timeout)
            if item is None:  # 停止信号
                break

            batch.append(item)

            # 批次满时写入
            if len(batch) >= batch_size:
                _process_html_visit_batch(batch)
                batch = []

        except Empty:
            # 超时时写入剩余项
            if batch:
                _process_html_visit_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] html_visit_writer 错误: {e}")

    # 线程结束前写入剩余数据
    if batch:
        _process_html_visit_batch(batch)


def _process_html_visit_batch(batch: list):
    """批量处理 HTML 访问统计"""
    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:
            # 更新总计
            update_html_visit_stat(db, path, None)

            # 更新每日统计
            update_html_visit_stat(db, path, date_obj.date())

        db.commit()
        print(f"[OK] 批量更新 {len(batch)} 条 HTML 访问统计")
    except Exception as e:
        print(f"[X] HTML 访问统计批次失败: {e}")
        db.rollback()
    finally:
        db.close()


def update_html_visit_stat(db: Session, path: str, date):
    """更新或创建 HTML 页面访问统计记录（使用 UPSERT 避免并发问题）"""
    from sqlalchemy import text

    # 使用 SQLite 的 INSERT OR REPLACE 语法（UPSERT）
    # 这样可以避免 rollback 影响整个 session
    try:
        # 先尝试更新
        result = db.execute(
            text("""
                UPDATE api_visit_log
                SET count = count + 1, updated_at = datetime('now')
                WHERE path = :path AND (
                    (date IS NULL AND :date IS NULL) OR
                    (date = :date)
                )
            """),
            {"path": path, "date": date}
        )

        # 如果没有更新任何行（记录不存在），则插入新记录
        if result.rowcount == 0:
            db.execute(
                text("""
                    INSERT OR IGNORE INTO api_visit_log (path, date, count, updated_at)
                    VALUES (:path, :date, 1, datetime('now'))
                """),
                {"path": path, "date": date}
            )
    except Exception as e:
        print(f"[X] 更新 HTML 访问统计失败: path={path}, date={date}, error={e}")
        raise



def log_writer_thread(db: Session):
    """批量写入 ApiUsageLog 到 auth.db"""
    batch = []
    batch_size = 50
    batch_timeout = 120.0

    while True:
        try:
            # 使用超时等待，而非 sleep
            item = log_queue.get(timeout=batch_timeout)

            if item is None:  # 停止信号
                break

            batch.append(item)

            # 批次满时写入
            if len(batch) >= batch_size:
                _write_log_batch(db, batch)
                batch = []

        except Empty:
            # 超时时写入剩余项
            if batch:
                _write_log_batch(db, batch)
                batch = []
        except Exception as e:
            print(f"[X] log_writer_thread 错误: {e}")

    # 线程结束前写入剩余数据
    if batch:
        _write_log_batch(db, batch)


def _write_log_batch(db: Session, batch: list):
    """批量写入日志"""
    try:
        db.bulk_save_objects(batch)
        db.commit()
        print(f"[OK] 批量写入 {len(batch)} 条日志")
    except Exception as e:
        print(f"[X] 批量写入失败: {e}")
        db.rollback()


# 异步写入日志的函数
def log_detailed_api_to_db(
        db: Session,
        path: str,
        duration: float,
        status_code: int,
        ip: str,
        user_agent: str,
        referer: str,
        user_id: int = None,
        clear_old: bool = False,
        request_size: int = 0,
        response_size: int = 0,
        start_time: float = None  # start_time 参数保持可选
):
    # Step 1: Optional cleanup of old logs
    if clear_old:
        one_week_ago = datetime.utcnow() - timedelta(weeks=1)
        db.query(ApiUsageLog).filter(ApiUsageLog.called_at < one_week_ago).delete()
        db.commit()

    # Step 2: Insert detailed log (short-term log)
    log = ApiUsageLog(
        path=path,
        duration=duration,
        status_code=status_code,
        ip=ip,
        user_agent=user_agent,
        referer=referer,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        # 如果传入了 start_time，使用它；否则，使用数据库默认时间
        called_at=datetime.utcfromtimestamp(start_time) if start_time else None  # 直接在创建时处理
    )

    # 将日志添加到队列
    log_queue.put(log)

    # Step 3: 将 ApiUsageSummary 更新移至队列
    if user_id:
        summary_queue.put({
            'user_id': user_id,
            'path': path,
            'duration': duration,
            'request_size': request_size,
            'response_size': response_size
        })


def summary_writer():
    """批量更新 ApiUsageSummary"""
    batch = []
    batch_size = 50
    batch_timeout = 60.0

    while True:
        try:
            item = summary_queue.get(timeout=batch_timeout)

            if item is None:
                break

            batch.append(item)

            if len(batch) >= batch_size:
                _process_summary_batch(batch)
                batch = []

        except Empty:
            if batch:
                _process_summary_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] summary_writer 错误: {e}")

    if batch:
        _process_summary_batch(batch)


def _process_summary_batch(batch: list):
    """批量处理 ApiUsageSummary 更新"""
    from app.auth.database import SessionLocal as AuthSessionLocal
    db = AuthSessionLocal()

    try:
        # 按 (user_id, path) 分组聚合
        aggregated = {}
        for item in batch:
            key = (item['user_id'], item['path'])
            if key not in aggregated:
                aggregated[key] = {
                    'count': 0,
                    'total_duration': 0,
                    'total_upload': 0,
                    'total_download': 0
                }

            aggregated[key]['count'] += 1
            aggregated[key]['total_duration'] += item['duration']
            aggregated[key]['total_upload'] += item['request_size'] / 1024
            aggregated[key]['total_download'] += item['response_size'] / 1024

        # 批量更新
        for (user_id, path), stats in aggregated.items():
            summary = db.query(ApiUsageSummary).filter_by(
                user_id=user_id, path=path
            ).first()

            if summary:
                summary.count += stats['count']
                summary.total_duration += Decimal(round(stats['total_duration'], 2))
                summary.total_upload += Decimal(round(stats['total_upload'], 2))
                summary.total_download += Decimal(round(stats['total_download'], 2))
                summary.last_updated = datetime.utcnow()
            else:
                summary = ApiUsageSummary(
                    user_id=user_id,
                    path=path,
                    count=stats['count'],
                    total_duration=Decimal(round(stats['total_duration'], 2)),
                    total_upload=Decimal(round(stats['total_upload'], 2)),
                    total_download=Decimal(round(stats['total_download'], 2)),
                    last_updated=datetime.utcnow()
                )
                db.add(summary)

        db.commit()
        print(f"[OK] 批量更新 {len(aggregated)} 条 ApiUsageSummary")
    except Exception as e:
        print(f"[X] ApiUsageSummary 批次失败: {e}")
        db.rollback()
    finally:
        db.close()


async def log_detailed_api_to_db_async(
        db: Session,
        path: str,
        duration: float,
        status_code: int,
        ip: str,
        user_agent: str,
        referer: str,
        user_id: int = None,
        clear_old: bool = False,
        request_size: int = 0,
        response_size: int = 0,
        start_time: float = None
):
    """异步包装器：将同步的数据库操作异步化"""
    await asyncio.to_thread(
        log_detailed_api_to_db,
        db,
        path,
        duration,
        status_code,
        ip,
        user_agent,
        referer,
        user_id,
        clear_old,
        request_size,
        response_size,
        start_time
    )


# app/service/api_logger.py
_workers_started = False
_start_lock = threading.Lock()


def start_api_logger_workers(db: Session):
    """启动所有日志后台线程"""
    global _workers_started
    with _start_lock:
        if _workers_started:
            return

        # [OK] 启动关键词日志写入线程（logs.db）
        threading.Thread(target=keyword_log_writer, daemon=True).start()

        # [OK] 启动API统计更新线程（logs.db）
        threading.Thread(target=statistics_writer, daemon=True).start()

        # [OK] 启动HTML页面访问统计线程（logs.db）
        threading.Thread(target=html_visit_writer, daemon=True).start()

        # [OK] 启动 ApiUsageLog 写入线程（auth.db）
        threading.Thread(target=log_writer_thread, args=(db,), daemon=True).start()

        # [NEW] 启动 ApiUsageSummary 更新线程（auth.db）
        threading.Thread(target=summary_writer, daemon=True).start()

        _workers_started = True
        print("[OK] API 日志后台线程已启动")


def stop_api_logger_workers():
    """停止所有日志后台线程"""
    try:
        keyword_log_queue.put_nowait(None)  # [OK] 停止关键词日志线程
    except:
        pass

    try:
        statistics_queue.put_nowait(None)  # [OK] 停止统计线程
    except:
        pass

    try:
        html_visit_queue.put_nowait(None)  # [OK] 停止HTML访问统计线程
    except:
        pass

    try:
        log_queue.put_nowait(None)  # 停止 ApiUsageLog 线程
    except:
        pass

    try:
        summary_queue.put_nowait(None)  # [NEW] 停止 ApiUsageSummary 线程
    except:
        pass

    print("🛑 API 日志后台线程已停止")


class StreamingResponseWrapper:
    """流式响应包装器 - 边传输边统计，不缓冲整个响应"""

    def __init__(self, iterator, content_type, user_role, max_size, response, on_complete_callback=None):
        self.iterator = iterator
        self.content_type = content_type
        self.user_role = user_role
        self.max_size = max_size
        self.response = response
        self.total_size = 0
        self.on_complete_callback = on_complete_callback

    async def __aiter__(self):
        """异步迭代器 - 流式传输响应"""
        try:
            async for chunk in self.iterator:
                chunk_size = len(chunk)
                self.total_size += chunk_size

                # 渐进式大小检查 - 超限立即中断
                if self.total_size > self.max_size:
                    raise HTTPException(
                        status_code=413,
                        detail="🚫 由於服務器限制，您的返回數據超過限制，請減少請求範圍 🛑"
                    )

                # 直接转发数据，不做任何修改
                yield chunk

        finally:
            # 流式传输完成后调用回调
            if self.on_complete_callback:
                await self.on_complete_callback(self)


# 这里是中间件，负责记录请求和响应的流量大小
class TrafficLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()  # 记录开始时间

        # 1. 快速过滤
        path = request.url.path
        if any(k in path for k in IGNORE_API) or not any(k in path for k in RECORD_API):
            return await call_next(request)

        # 2. 獲取 DB Session
        # [!] 警告：直接用 next(get_db()) 會導致連接洩漏！必須手動關閉。
        db = next(get_db())
        user = None
        try:
            # 3. [OK] 使用 await 調用異步函數
            user = await get_current_user_for_middleware(request, db=db)
        except Exception as e:
            print(f"Middleware Auth Error: {e}")
            # 認證出錯不應影響請求繼續，視為匿名用戶
            user = None
        finally:
            # 4. [OK] 必須關閉數據庫連接！這非常重要！
            db.close()

        # 5. 计算请求大小
        cl = request.headers.get("Content-Length")

        if cl is not None and cl.isdigit():
            request_size = int(cl)
        else:
            # 如果是 GET 请求，计算 URL 和查询参数的大小
            if request.method == "GET":
                url_size = len(request.url.path) + len(request.url.query)
                request_size = url_size
            else:
                # 获取请求体大小
                request_body = await request.body()
                request_size = len(request_body)

        # 6. 调用下游应用（视图函数）
        response = await call_next(request)

        # 7. 确定用户的响应大小限制
        max_size = MAX_ANONYMOUS_SIZE if user is None else (
            float('inf') if user.role == "admin" else MAX_USER_SIZE
        )

        # 8. 定义流式传输完成后的回调函数
        async def on_streaming_complete(wrapper):
            """流式传输完成后记录日志"""
            # 计算处理时间
            duration = time.time() - start_time

            # 获取最终的响应大小
            # 注意：始终记录压缩前的大小，以保证统计一致性
            # 压缩是服务器优化手段，对用户应该是透明的
            response_size = wrapper.total_size  # 压缩前的原始大小

            # 异步记录日志
            await log_detailed_api_to_db_async(
                db=db,
                path=request.url.path,
                duration=duration,
                status_code=response.status_code,
                ip=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                referer=request.headers.get("Referer"),
                user_id=user.id if user else None,
                request_size=request_size,
                response_size=response_size,
                clear_old=CLEAR_WEEK,
                start_time=start_time
            )

        # 9. 使用流式包装器（不缓冲整个响应）
        wrapper = StreamingResponseWrapper(
            iterator=response.body_iterator,
            content_type=response.headers.get("Content-Type", ""),
            user_role=user.role if user else None,
            max_size=max_size,
            response=response,
            on_complete_callback=on_streaming_complete
        )

        # 10. 替换响应迭代器
        response.body_iterator = wrapper

        return response

# 以下代码已废弃
# === 详细响应记录入队 ===
# def log_detailed_api(path, duration, status_code, ip, user_agent, referer):
#     today = datetime.now().strftime("%Y-%m-%d")
#     detailed_queue.put((path, duration, status_code, ip, user_agent, referer, today))
#
# # === 后台线程写入详细响应 ===
# def detailed_writer():
#     # 初始化数据结构
#     def init_stats():
#         return {
#             "count": 0, "total_time": 0.0, "status_codes": defaultdict(int),
#             "ips": set(), "agents": set(), "referers": set()
#         }
#
#     # 从 JSON 加载旧数据
#     if os.path.exists(API_DETAILED_JSON):
#         with open(API_DETAILED_JSON, "r", encoding="utf-8") as f:
#             raw = json.load(f)
#             detailed_stats = defaultdict(init_stats, {
#                 k: {
#                     "count": v["count"],
#                     "total_time": v["total_time"],
#                     "status_codes": defaultdict(int, v["status_codes"]),
#                     "ips": set(v["ips"]),
#                     "agents": set(v["agents"]),
#                     "referers": set(v["referers"]),
#                 } for k, v in raw["detailed_stats"].items()
#             })
#             daily_stats = defaultdict(lambda: defaultdict(init_stats))
#             for date, paths in raw["daily_stats"].items():
#                 for path, v in paths.items():
#                     daily_stats[date][path] = {
#                         "count": v["count"],
#                         "total_time": v["total_time"],
#                         "status_codes": defaultdict(int, v["status_codes"]),
#                         "ips": set(v["ips"]),
#                         "agents": set(v["agents"]),
#                         "referers": set(v["referers"]),
#                     }
#     else:
#         detailed_stats = defaultdict(init_stats)
#         daily_stats = defaultdict(lambda: defaultdict(init_stats))
#
#     while True:
#         item = detailed_queue.get()
#         if item is None:
#             break
#         path, duration, status, ip, agent, referer, date = item
#
#         d = detailed_stats[path]
#         d["count"] += 1
#         d["total_time"] += duration
#         d["status_codes"][status] += 1
#         d["ips"].add(ip)
#         d["agents"].add(agent)
#         if referer:
#             d["referers"].add(referer)
#
#         d_day = daily_stats[date][path]
#         d_day["count"] += 1
#         d_day["total_time"] += duration
#         d_day["status_codes"][status] += 1
#         d_day["ips"].add(ip)
#         d_day["agents"].add(agent)
#         if referer:
#             d_day["referers"].add(referer)
#
#         # 写入结构化 JSON 文件（持久化）
#         with open(API_DETAILED_JSON, "w", encoding="utf-8") as f:
#             json.dump({
#                 "detailed_stats": {
#                     k: {
#                         "count": v["count"],
#                         "total_time": v["total_time"],
#                         "status_codes": dict(v["status_codes"]),
#                         "ips": list(v["ips"]),
#                         "agents": list(v["agents"]),
#                         "referers": list(v["referers"]),
#                     } for k, v in detailed_stats.items()
#                 },
#                 "daily_stats": {
#                     date: {
#                         path: {
#                             "count": v["count"],
#                             "total_time": v["total_time"],
#                             "status_codes": dict(v["status_codes"]),
#                             "ips": list(v["ips"]),
#                             "agents": list(v["agents"]),
#                             "referers": list(v["referers"]),
#                         } for path, v in paths.items()
#                     } for date, paths in daily_stats.items()
#                 }
#             }, f, ensure_ascii=False, indent=2)
#
#         # 写入可读汇总（和原来一样）
#         with open(API_DETAILED_FILE, "w", encoding="utf-8") as f:
#             f.write("=== Total Summary ===\n")
#             for path, d in detailed_stats.items():
#                 avg = d["total_time"] / d["count"] if d["count"] else 0
#                 f.write(f"{path}\n  Count: {d['count']}\n  Avg Response Time: {avg:.3f}s\n")
#                 f.write(f"  Status Codes: {', '.join(f'{k}:{v}' for k, v in d['status_codes'].items())}\n")
#                 f.write("  IPs:\n" + ''.join(f"    - {ip}\n" for ip in sorted(d['ips'])))
#                 f.write("  User-Agents:\n" + ''.join(f"    - {ua}\n" for ua in sorted(d['agents'])))
#                 f.write("  Referers:\n" + ''.join(f"    - {r}\n" for r in sorted(d['referers'])))
#                 f.write("\n")
#             f.write("=== Daily Summary ===\n")
#             for date in sorted(daily_stats):
#                 f.write(f"{date}\n")
#                 for path, d in daily_stats[date].items():
#                     avg = d["total_time"] / d["count"] if d["count"] else 0
#                     f.write(f"{path}\n  Count: {d['count']}\n  Avg Response Time: {avg:.3f}s\n")
#                     f.write(f"  Status Codes: {', '.join(f'{k}:{v}' for k, v in d['status_codes'].items())}\n")
#                     f.write("  IPs:\n" + ''.join(f"    - {ip}\n" for ip in sorted(d['ips'])))
#                     f.write("  User-Agents:\n" + ''.join(f"    - {ua}\n" for ua in sorted(d['agents'])))
#                     f.write("  Referers:\n" + ''.join(f"    - {r}\n" for r in sorted(d['referers'])))
#                 f.write("\n")
