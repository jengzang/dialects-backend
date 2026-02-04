from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Information(Base):
    __tablename__ = "informations"

    id = Column(Integer, primary_key=True)
    簡稱 = Column(String, nullable=False, index=True)
    音典分區 = Column(String, nullable=False, index=True)
    經緯度 = Column(String, nullable=False)
    聲韻調 = Column(String, nullable=True, index=True)
    特徵 = Column(String, nullable=False, index=True)
    值 = Column(Text, nullable=False)
    說明 = Column(Text)
    存儲標記 = Column(Integer, default=1, index=True)
    maxValue = Column(String, nullable=False)

    # 手動記錄用戶資訊（不關聯）
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # username = Column(String, nullable=False)
    # user = relationship("User", back_populates="informations")  # [OK] 字串只寫 "User"
