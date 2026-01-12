import asyncio
import gzip
import io
import json
import os
import threading
import queue
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict
import ast
from decimal import Decimal
from typing import AsyncIterable, Optional

from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.database import get_db
from app.auth.dependencies import get_current_user, get_current_user_for_middleware
from app.auth.models import ApiUsageLog, ApiUsageSummary, User
from common.config import KEYWORD_LOG_FILE, SUMMARY_FILE, API_USAGE_FILE, API_DETAILED_JSON, API_DETAILED_FILE, \
    CLEAR_WEEK, RECORD_API, MAX_ANONYMOUS_SIZE, MAX_USER_SIZE, BATCH_SIZE, SIZE_THRESHOLD

# === 队列 ===
keyword_queue = queue.Queue()
# detailed_queue = queue.Queue()
log_queue = queue.Queue()


# === 关键词日志 ===
def log_keyword(path: str, field: str, value):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keyword_queue.put((timestamp, path, field, value))


def log_all_fields(path: str, param_dict: dict):
    for field, value in param_dict.items():
        if value is not None and value != [] and value != "":
            log_keyword(path, field, value)


def keyword_writer():
    with open(KEYWORD_LOG_FILE, "a", encoding="utf-8") as f:
        while True:
            item = keyword_queue.get()
            if item is None:
                break
            timestamp, path, field, value = item
            line = f"{timestamp} | {path} | {field}: {repr(value)}\n"
            f.write(line)
            f.flush()


# === 聚合关键词日志 ===
def aggregate_keyword_log():
    total_counts = defaultdict(lambda: defaultdict(int))
    daily_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    today = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(KEYWORD_LOG_FILE):
        return

    with open(KEYWORD_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                timestamp, path, rest = line.strip().split(" | ", 2)
                field_part, value_part = rest.split(": ", 1)
                field = field_part.strip()
                value = ast.literal_eval(value_part.strip())
                date = timestamp.split(" ")[0]
                if not isinstance(value, list):
                    value = [value]
                for item in value:
                    total_counts[field][item] += 1
                    daily_counts[date][field][item] += 1
            except HTTPException:
                raise  # ✅ 让 HTTPException 保持原样传递
            except Exception as e:
                print(f"[aggregate_keyword_log] Error: {e} | Line: {line}")

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write("=== Total Summary ===\n")
        for field, keywords in total_counts.items():
            f.write(f"{field}:")
            for k, v in sorted(keywords.items(), key=lambda x: -x[1]):
                f.write(f"\n  {k}: {v}")
            f.write("\n")

        f.write("\n=== Daily Summary ===\n")
        for date in sorted(daily_counts.keys()):
            f.write(f"{date}:\n")
            for field, keywords in daily_counts[date].items():
                f.write(f"{field}:")
                for k, v in sorted(keywords.items(), key=lambda x: -x[1]):
                    f.write(f"\n  {k}: {v}")
                f.write("\n")


# === API调用统计 ===
def update_count(path: str):
    today = datetime.now().strftime("%Y-%m-%d")
    with threading.Lock():
        if not os.path.exists(API_USAGE_FILE):
            with open(API_USAGE_FILE, "w", encoding="utf-8") as f:
                f.write("=== Total Counts ===\n")
                f.write(f"{path}\t1\n")
                f.write("\n=== Daily Counts ===\n")
                f.write(f"{today}\n{path}\t1\n")
            return

        with open(API_USAGE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_counts = defaultdict(int)
        daily_counts = defaultdict(lambda: defaultdict(int))
        section = None
        current_day = None
        for line in lines:
            line = line.strip()
            if line == "=== Total Counts ===":
                section = "total"
                continue
            elif line == "=== Daily Counts ===":
                section = "daily"
                continue
            elif section == "daily" and re.match(r"\d{4}-\d{2}-\d{2}", line):
                current_day = line
                continue
            elif section == "total" and line:
                if "\t" in line:
                    k, v = line.split("\t")
                else:
                    # 处理没有制表符的情况，或者记录日志、跳过该行
                    print(f"Skipping invalid line: {line}")

                total_counts[k] = int(v)
            elif section == "daily" and line:
                if "\t" in line:
                    k, v = line.split("\t")
                else:
                    # 处理没有制表符的情况，或者记录日志、跳过该行
                    print(f"Skipping invalid line: {line}")

                daily_counts[current_day][k] = int(v)

        total_counts[path] += 1
        daily_counts[today][path] += 1

        with open(API_USAGE_FILE, "w", encoding="utf-8") as f:
            f.write("=== Total Counts ===\n")
            for k, v in sorted(total_counts.items()):
                f.write(f"{k}\t{v}\n")
            f.write("\n=== Daily Counts ===\n")
            for date in sorted(daily_counts):
                f.write(f"{date}\n")
                for k, v in sorted(daily_counts[date].items()):
                    f.write(f"{k}\t{v}\n")


def log_writer_thread(db: Session):
    while True:
        # 获取一条日志并立即写入数据库
        if not log_queue.empty():
            log = log_queue.get()  # 获取日志
            try:
                # 写入数据库
                with db.begin():  # 使用事务确保写入操作的原子性
                    db.add(log)
                db.commit()  # 提交事务
                # print("已提交一条日志到数据库")
            except Exception as e:
                print(f"错误：写入数据库时出错：{e}")
                db.rollback()  # 错误时回滚事务

        # 等待一段时间，避免过度消耗资源
        time.sleep(1)


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

    # Step 3: Update summary table (long-term accumulated data)
    if user_id:
        summary = db.query(ApiUsageSummary).filter_by(user_id=user_id, path=path).first()
        if summary:
            summary.count += 1
            summary.total_duration += Decimal(round(log.duration, 2))
            # 累加上行流量和下行流量（将字节转换为 KB 并保留两位小数）
            summary.total_upload += Decimal(round(log.request_size / 1024, 2))  # 转换为 Decimal 类型
            summary.total_download += Decimal(round(log.response_size / 1024, 2))  # 转换为 Decimal 类型
            # 更新最后更新时间
            summary.last_updated = datetime.utcnow()
        else:
            summary = ApiUsageSummary(
                user_id=user_id,
                path=path,
                count=1,
                last_updated=datetime.utcnow(),
                # 初始化上行流量和下行流量，转换为 KB 并保留两位小数
                total_upload=round(log.request_size / 1024, 2),
                total_download=round(log.response_size / 1024, 2)
            )
            db.add(summary)

        db.commit()


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
        start_time: float = None  # 添加 start_time 参数
):
    # 使用 asyncio.to_thread 将同步的数据库操作异步化，并传递 start_time 参数
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
        start_time  # 将 start_time 参数传递给同步函数
    )



# app/service/api_logger.py
_workers_started = False
_start_lock = threading.Lock()


def start_api_logger_workers(db: Session):
    global _workers_started
    with _start_lock:
        if _workers_started:
            return
        threading.Thread(target=keyword_writer, daemon=True).start()
        # 启动日志写入线程
        threading.Thread(target=log_writer_thread, args=(db,), daemon=True).start()  # 启动 log_writer_thread 处理 log_queue
        # threading.Thread(target=detailed_writer, daemon=True).start()
        threading.Thread(target=aggregate_keyword_log, daemon=True).start()
        _workers_started = True


def stop_api_logger_workers():
    # 发哨兵，尽量优雅退出
    try:
        keyword_queue.put_nowait(None)
    except:
        pass
    # 发送停止信号给日志线程
    try:
        log_queue.put_nowait(None)  # 停止 log_writer_thread
    except:
        pass
    # try:
    #     detailed_queue.put_nowait(None)
    # except:
    #     pass


# 这里是中间件，负责记录请求和响应的流量大小
class TrafficLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()  # 记录开始时间

        if not any(keyword in request.url.path for keyword in RECORD_API):
            return await call_next(request)  # 如果路径不包含任何允许的词，跳过日志记录

        # 1. 獲取 DB Session
        # ⚠️ 警告：直接用 next(get_db()) 會導致連接洩漏！必須手動關閉。
        db = next(get_db())
        user = None

        try:
            # 2. ✅ 使用 await 調用異步函數
            user = await get_current_user_for_middleware(request, db=db)
        except Exception as e:
            print(f"Middleware Auth Error: {e}")
            # 認證出錯不應影響請求繼續，視為匿名用戶
            user = None
        finally:
            # 3. ✅ 必須關閉數據庫連接！這非常重要！
            db.close()

        # 如果是 GET 请求，计算 URL 和查询参数的大小
        if request.method == "GET":
            url_size = len(request.url.path) + len(request.url.query)  # URL 路径 + 查询字符串的长度
            request_size = url_size  # 只计算 URL 的大小
        else:
            # 获取请求体大小
            request_body = await request.body()
            request_size = len(request_body)

        # 调用下游应用（视图函数）
        response = await call_next(request)

        # 记录响应体大小
        response_body = bytearray()  # 使用 bytearray 来高效拼接
        async for chunk in response.body_iterator:
            response_body.extend(chunk)  # 使用 extend 更高效

        # 压缩 JSON 响应体
        if "application/json" in response.headers.get("Content-Type", ""):
            if len(response_body) > 10 * 1024:  # 仅对大于 10KB 的响应体进行压缩
                response_body = await compress_json(response_body)
                response.headers["Content-Encoding"] = "gzip"  # 设置响应的编码类型
                response.headers["Content-Length"] = str(len(response_body))

        response_size = len(response_body)

        # 判断用户和响应体大小是否符合限制
        if user is None and response_size > MAX_ANONYMOUS_SIZE:
            raise HTTPException(
                status_code=413,  # Payload Too Large
                detail="🚫 由於服務器限制，未登錄用戶暫不允許請求過多的數據 🙅‍♂️🙅‍♀️"
            )
        elif user and user.role != "admin" and response_size > MAX_USER_SIZE:
            raise HTTPException(
                status_code=413,  # Payload Too Large
                detail="🚫 由於服務器限制，您的返回數據超過限制，請減少請求範圍 🛑💾"
            )

        # 计算处理时间
        duration = time.time() - start_time

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
            start_time=start_time  # 传递 start_time
        )

        # 将响应体变为异步迭代器
        response.body_iterator = iter_response_body(response_body)
        return response


async def iter_response_body(response_body: bytes) -> AsyncIterable[bytes]:
    yield response_body


async def compress_json(response_body: bytes) -> bytes:
    # 如果响应体小于10KB，直接返回原始响应体
    if len(response_body) <= SIZE_THRESHOLD:
        return response_body
    # 否则，执行压缩
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(response_body)
    return buf.getvalue()

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
