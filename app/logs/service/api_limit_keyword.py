"""
API 日志记录中间件：自动记录 API 调用参数
"""
import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.logs.service.api_logger import log_all_fields
from app.logs.service.route_matcher import match_route_config, should_skip_route


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    """
    API 日志记录中间件

    功能：
    1. 根据配置自动记录 API 参数
    2. 支持记录查询参数、请求体
    3. 不阻塞请求处理
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 跳过白名单路由
        if should_skip_route(path):
            return await call_next(request)

        # 获取路由配置
        config = match_route_config(path)

        # 如果不需要记录日志，直接放行
        if not config.get("log_params") and not config.get("log_body"):
            return await call_next(request)

        print(f"[ApiLoggingMiddleware] 开始记录日志: {path}")

        # 收集要记录的参数
        params_to_log = {}

        # 1. 记录查询参数
        if config.get("log_params") and request.query_params:
            params_to_log.update(dict(request.query_params))
            print(f"[ApiLoggingMiddleware] 记录查询参数: {len(request.query_params)} 个")

        # 2. 记录请求体
        if config.get("log_body") and request.method in ["POST", "PUT", "PATCH"]:
            try:
                # 读取请求体
                body = await request.body()
                if body:
                    try:
                        body_data = json.loads(body)
                        params_to_log.update(body_data)
                        print(f"[ApiLoggingMiddleware] 记录请求体: {len(body_data)} 个字段")
                    except json.JSONDecodeError:
                        params_to_log["_raw_body"] = body.decode("utf-8", errors="ignore")
                        print(f"[ApiLoggingMiddleware] 记录原始请求体")

                # 重新构造请求以便后续处理
                async def receive():
                    return {"type": "http.request", "body": body}

                request._receive = receive
            except Exception as e:
                print(f"[WARN] 读取请求体失败: {e}")

        # 3. 异步记录日志（不阻塞请求）
        if params_to_log:
            try:
                log_all_fields(path, params_to_log)
                print(f"[ApiLoggingMiddleware] ✅ 已放入日志队列: {len(params_to_log)} 个参数")
            except Exception as e:
                print(f"[ERROR] 记录日志失败: {e}")

        # 4. 继续处理请求
        response = await call_next(request)
        return response
