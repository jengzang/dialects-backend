from sqlalchemy import create_engine, event  # [NEW] 新增 event
from sqlalchemy.orm import sessionmaker
from app.auth.models import Base
from common.config import USER_DATABASE_URL

engine = create_engine(
    USER_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True  # [NEW] 建议
)


# [NEW] 新增：为每个新连接开启 WAL / 外键 / 同步级别
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    # WAL 模式在某些只读挂载场景下可能失败，改用 DELETE 模式
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
    except Exception as e:
        print(f"[!] auth.db 无法设置 WAL 模式: {e}，使用默认 DELETE 模式")
        cur.execute("PRAGMA journal_mode=DELETE;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.close()


event.listen(engine, "connect", _sqlite_pragmas)  # [NEW] 新增

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建表（保持原样）
Base.metadata.create_all(bind=engine)


# FastAPI 依賴（保持原样）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
