from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index

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


class UserRegion(Base):
    """用戶自定義區域表 - 允許用戶創建自己的地點分組"""
    __tablename__ = "user_regions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    region_name = Column(String(200), nullable=False, index=True)
    locations = Column(Text, nullable=False)  # JSON array: ["簡稱1", "簡稱2", ...]
    description = Column(Text)  # Optional user notes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'region_name', name='uq_user_region'),
        Index('idx_user_regions_user_id', 'user_id'),
        Index('idx_user_regions_region_name', 'region_name'),
    )
