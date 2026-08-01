from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index

from sqlalchemy.orm import declarative_base

from app.common.time_utils import now_utc_naive

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
    created_at = Column(DateTime, default=now_utc_naive)

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
    created_at = Column(DateTime, default=now_utc_naive)
    updated_at = Column(DateTime, default=now_utc_naive, onupdate=now_utc_naive)

    __table_args__ = (
        UniqueConstraint('user_id', 'region_name', name='uq_user_region'),
        Index('idx_user_regions_user_id', 'user_id'),
        Index('idx_user_regions_region_name', 'region_name'),
    )


class UserSuggestion(Base):
    """用户建议表 - 允许匿名或登录用户提交站内反馈。"""
    __tablename__ = "user_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(100), nullable=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="general", index=True)
    source_path = Column(String(300), nullable=True)
    context_json = Column(Text, nullable=True)
    contact = Column(String(200), nullable=True)
    submitter_ip = Column(String(45), nullable=True)
    user_agent = Column(String(300), nullable=True)
    recent_api = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    priority = Column(String(20), nullable=False, default="normal")
    admin_note = Column(Text, nullable=True)
    handled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc_naive, index=True)
    updated_at = Column(DateTime, default=now_utc_naive, onupdate=now_utc_naive)

    __table_args__ = (
        Index("idx_user_suggestions_user_id", "user_id"),
        Index("idx_user_suggestions_status", "status"),
        Index("idx_user_suggestions_category", "category"),
        Index("idx_user_suggestions_created_at", "created_at"),
    )
