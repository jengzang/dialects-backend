from sqlalchemy import create_engine, event  # ✨ 新增 event
from sqlalchemy.orm import sessionmaker
from app.auth.models import Base
from common.config import USER_DATABASE_URL

engine = create_engine(
    USER_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True  # ✨ 建议
)


# ✨ 新增：为每个新连接开启 WAL / 外键 / 同步级别
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.close()


event.listen(engine, "connect", _sqlite_pragmas)  # ✨ 新增

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
