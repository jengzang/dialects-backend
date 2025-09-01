from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.auth.models import Base
from common.config import USER_DATABASE_URL

engine = create_engine(
    USER_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建表（第一次導入時自動創建）
Base.metadata.create_all(bind=engine)

# FastAPI 依賴
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
