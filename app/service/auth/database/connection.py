from app.common.sqlite_orm import POLICIES, create_engine_and_session
from app.service.auth.database.models import Base
from app.common.path import USER_DATABASE_URL

# Keep request-side waits bounded; background auth writers retry confirmed lock errors.
SQLITE_BUSY_TIMEOUT_MS = POLICIES['auth'].busy_timeout_ms
engine, SessionLocal = create_engine_and_session('auth', USER_DATABASE_URL)

# 建表（处理多worker竞争）
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    # 多worker环境下可能出现"table already exists"竞争
    if "already exists" not in str(e).lower():
        raise  # 其他错误需要抛出


# FastAPI 依賴（保持原样）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
