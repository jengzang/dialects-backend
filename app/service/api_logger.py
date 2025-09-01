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
from app.auth.dependencies import get_current_user, get_current_user_sync
from app.auth.models import ApiUsageLog, ApiUsageSummary, User
from common.config import API_USAGE_FILE, \
    CLEAR_WEEK, RECORD_API, MAX_ANONYMOUS_SIZE, MAX_USER_SIZE

# === 队列 ===
keyword_queue = queue.Queue()
detailed_queue = queue.Queue()


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
                k, v = line.split("\t")
                total_counts[k] = int(v)
            elif section == "daily" and line:
                k, v = line.split("\t")
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


def log_detailed_api_to_db(
        db: Session,
        path: str,
        duration: float,
        status_code: int,
        ip: str,
        user_agent: str,
        referer: str,
        user_id: int = None,  # optional
        clear_old: bool = False,  # ✅ 新增參數：是否清理舊資料
        request_size: int = 0,  # ✅ 新增：请求体大小
        response_size: int = 0  # ✅ 新增：响应体大小
):
    # Step 1: Optional cleanup of old logs
    if clear_old:
        one_week_ago = datetime.utcnow() - timedelta(weeks=1)  # 修改为1周
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
        request_size=request_size,  # Add request size to the log
        response_size=response_size  # Add response size to the log
    )
    db.add(log)

    # Step 3: Update summary table (long-term accumulated data)
    if user_id:
        summary = db.query(ApiUsageSummary).filter_by(user_id=user_id, path=path).first()
        if summary:
            # 累加计数
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

    db.commit()


# app/service/api_logger.py
_workers_started = False
_start_lock = threading.Lock()


# 这里是中间件，负责记录请求和响应的流量大小
class TrafficLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()  # 记录开始时间

        if not any(keyword in request.url.path for keyword in RECORD_API):
            return await call_next(request)  # 如果路径不包含任何允许的词，跳过日志记录

        # 手动调用 get_current_user 获取用户
        db = next(get_db())  # 确保我们从生成器中获取会话对象
        try:
            user = get_current_user_sync(request, db=db)
        except HTTPException as e:
            if e.status_code == 401:
                user = None  # 匿名使用者，允許繼續執行
            else:
                raise  # 其他錯誤照常丟出

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
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        # 如果响应是 JSON 格式，进行压缩
        if "application/json" in response.headers.get("Content-Type", ""):
            # 压缩 JSON 响应体
            # print("壓縮")
            response_body = compress_json(response_body)
            response.headers["Content-Encoding"] = "gzip"  # 设置响应的编码类型
            # 更新 Content-Length 为压缩后的大小
            response.headers["Content-Length"] = str(len(response_body))

        response_size = len(response_body)
        # if user is None:
        #     print("未登錄")
        # else :
        #     if user and user.role != "admin":
        #         print("普通")
        #     else:
        #         print("管理")
        # 判断用户和响应体大小是否符合限制
        if user is None and response_size > MAX_ANONYMOUS_SIZE:
            raise HTTPException(
                status_code=413,  # Payload Too Large
                detail="🚫 由於服務器限制，未登錄用戶暫不允許請求過多的數據 🙅‍♂️🙅‍♀️"
            )
        else:
            if user and user.role != "admin" and response_size > MAX_USER_SIZE:
                raise HTTPException(
                    status_code=413,  # Payload Too Large
                    detail="🚫 由於服務器限制，您的返回數據超過限制，請減少請求範圍 🛑💾"
                )

        # 计算处理时间
        duration = time.time() - start_time
        log_detailed_api_to_db(
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
            clear_old=CLEAR_WEEK
        )

        # 将响应体变为异步迭代器
        response.body_iterator = iter_response_body(response_body)
        return response


async def iter_response_body(response_body: bytes) -> AsyncIterable[bytes]:
    yield response_body


def compress_json(response_body: bytes) -> bytes:
    # 使用 gzip 压缩 JSON 数据
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(response_body)
    return buf.getvalue()
