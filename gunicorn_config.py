"""
Gunicorn 配置文件
用于在主进程中启动后台线程，避免多 worker 重复启动
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def on_starting(server):
    """
    在 Gunicorn 主进程启动时执行（只执行一次）
    在这里启动后台线程，所有 worker 进程将共享这些队列
    """
    print("=" * 60)
    print("🚀 [Gunicorn Master] 启动后台线程...")
    print("=" * 60)

    # 导入必要的模块
    from app.auth.database import get_db
    from app.logging.service.api_logger import start_api_logger_workers
    from app.auth.service import start_user_activity_writer
    from app.logging.scheduler import start_scheduler

    # 获取数据库连接
    db = next(get_db())

    # 启动日志后台线程（在主进程中）
    start_api_logger_workers(db)

    # 启动用户活动更新后台线程（在主进程中）
    start_user_activity_writer()

    # 启动定时任务调度器（在主进程中）
    start_scheduler()

    print("=" * 60)
    print("✅ [Gunicorn Master] 后台线程启动完成")
    print("   - 5个日志线程（logs.db + auth.db）")
    print("   - 1个用户活动线程（auth.db）")
    print("   - 1个定时任务调度器")
    print("   - 总计：6个后台线程 + 1个调度器在主进程中运行")
    print("=" * 60)


def on_exit(server):
    """
    在 Gunicorn 主进程退出时执行
    停止所有后台线程
    """
    print("=" * 60)
    print("🛑 [Gunicorn Master] 停止后台线程...")
    print("=" * 60)

    try:
        from app.logging.service.api_logger import stop_api_logger_workers
        from app.auth.service import stop_user_activity_writer
        from app.logging.scheduler import stop_scheduler

        stop_api_logger_workers()
        stop_user_activity_writer()
        stop_scheduler()

        print("✅ [Gunicorn Master] 后台线程已停止")
    except Exception as e:
        print(f"⚠️ [Gunicorn Master] 停止后台线程时出错: {e}")
    finally:
        print("=" * 60)


def worker_exit(server, worker):
    """
    在 worker 进程退出时执行
    确保资源被释放
    """
    print(f"🔄 [Worker {worker.pid}] 正在退出...")

    # 强制关闭数据库连接
    try:
        from app.sql.db_pool import close_all_pools
        close_all_pools()
    except Exception as e:
        print(f"⚠️ [Worker {worker.pid}] 关闭数据库连接池失败: {e}")


# Gunicorn 配置参数
bind = "0.0.0.0:5000"
workers = 3  # 迁移完成，恢复为3
worker_class = "uvicorn.workers.UvicornWorker"

# 请求处理超时（单个请求的最大处理时间）
timeout = 300  # 5分钟，适合大多数同步 API

# Worker 重启配置
max_requests = 1000  # 每个 worker 处理 1000 个请求后重启（防止内存泄漏）
max_requests_jitter = 50  # 随机增加 0-50 个请求（避免所有 worker 同时重启）

# 优雅关闭配置
graceful_timeout = 60  # Worker 重启时，等待现有请求完成的时间（60秒）
# 注意：graceful_timeout 应该 >= timeout，确保正在处理的请求能完成

# Keep-Alive 配置
keepalive = 5  # HTTP keep-alive 空闲超时（不影响正在处理的请求）

# 日志配置
accesslog = "-"  # 输出到 stdout
errorlog = "-"   # 输出到 stderr
loglevel = "info"
