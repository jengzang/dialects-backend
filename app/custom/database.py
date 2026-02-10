from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from app.auth.models import Base
from common.path import SUPPLE_DB_URL

engine = create_engine(
    SUPPLE_DB_URL,
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
        print(f"[!] supplements.db 无法设置 WAL 模式: {e}，使用默认 DELETE 模式")
        cur.execute("PRAGMA journal_mode=DELETE;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.close()


event.listen(engine, "connect", _sqlite_pragmas)  # [NEW] 新增

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建表（保持原样）
Base.metadata.create_all(bind=engine)


# ============ 数据库迁移：检查并添加缺失的列 ============
def migrate_database():
    """检查 informations 表是否有所有必需的列，如果缺失则添加"""
    with engine.connect() as conn:
        # 检查 informations 表是否存在"聲韻調"列
        result = conn.execute(text("PRAGMA table_info(informations)"))
        columns = [row[1] for row in result]  # row[1] 是列名

        # 如果没有"聲韻調"列，则添加
        if "聲韻調" not in columns:
            print("[!] 检测到 informations 表缺少'聲韻調'列，正在添加...")
            conn.execute(text('ALTER TABLE informations ADD COLUMN "聲韻調" VARCHAR NOT NULL DEFAULT ""'))
            # SQLite 不支持在 ALTER TABLE 中直接创建索引，需要单独创建
            conn.execute(text('CREATE INDEX IF NOT EXISTS "ix_informations_聲韻調" ON informations ("聲韻調")'))
            conn.commit()
            print("[OK] '聲韻調'列及索引已成功添加到 informations 表")
        else:
            print("[OK] informations 表结构正常，包含'聲韻調'列")


# 执行迁移
# migrate_database()


# FastAPI 依賴（保持原样）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
