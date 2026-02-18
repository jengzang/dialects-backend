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

# 建表（处理多worker竞争）
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    # 多worker环境下可能出现"table already exists"竞争
    if "already exists" not in str(e).lower():
        raise  # 其他错误需要抛出


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


# ============ 数据库迁移：创建 user_regions 表 ============
def migrate_user_regions_table():
    """检查并创建 user_regions 表"""
    with engine.connect() as conn:
        # 检查 user_regions 表是否存在
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_regions'"
        ))
        table_exists = result.fetchone() is not None

        if not table_exists:
            print("[!] 检测到缺少 user_regions 表，正在创建...")

            # 创建表
            conn.execute(text("""
                CREATE TABLE user_regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    region_name VARCHAR(200) NOT NULL,
                    locations TEXT NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_user_region UNIQUE (user_id, region_name)
                )
            """))

            # 创建索引
            conn.execute(text(
                "CREATE INDEX idx_user_regions_user_id ON user_regions (user_id)"
            ))
            conn.execute(text(
                "CREATE INDEX idx_user_regions_region_name ON user_regions (region_name)"
            ))

            conn.commit()
            print("[OK] user_regions 表及索引已成功创建")
        else:
            print("[OK] user_regions 表已存在")


# FastAPI 依賴（保持原样）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
