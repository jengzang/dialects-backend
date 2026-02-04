# logs/database.py
"""
日志数据库配置
"""
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker
from app.logs.models import Base
from common.config import LOGS_DATABASE_URL

engine = create_engine(
    LOGS_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)


# SQLite 优化设置
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    # WAL 模式在某些只读挂载场景下可能失败，改用 DELETE 模式
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
    except Exception as e:
        print(f"[!] 无法设置 WAL 模式: {e}，使用默认 DELETE 模式")
        cur.execute("PRAGMA journal_mode=DELETE;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA cache_size=-64000;")  # 64MB 缓存
    cur.close()


event.listen(engine, "connect", _sqlite_pragmas)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def migrate_api_visit_log_table():
    """
    检查并迁移 api_visit_log 表结构
    如果表结构不匹配（旧版本），则删除并重建
    """
    inspector = inspect(engine)

    # 检查表是否存在
    if 'api_visit_log' not in inspector.get_table_names():
        print("[i] api_visit_log 表不存在，将自动创建")
        return

    # 检查表结构
    columns = {col['name'] for col in inspector.get_columns('api_visit_log')}
    expected_columns = {'id', 'path', 'date', 'count', 'updated_at'}

    # 如果表结构不匹配（存在旧字段 timestamp 或 status_code）
    if 'timestamp' in columns or 'status_code' in columns or columns != expected_columns:
        print("[!] 检测到旧版本的 api_visit_log 表结构，正在重建...")
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS api_visit_log"))
            conn.commit()
        print("[OK] 旧表已删除，将创建新表结构")


# 先迁移表结构
# migrate_api_visit_log_table()

# 创建所有表
# Base.metadata.create_all(bind=engine)
# print("[OK] logs.db 数据库表已创建")


# FastAPI 依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
