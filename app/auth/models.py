from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey, Float, Text, DECIMAL, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from sqlalchemy.orm import declarative_base
Base = declarative_base()
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # 基本資料
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    # full_name = Column(String(100), nullable=True)  # 可為空
    # phone = Column(String(20), nullable=True)  # 可為空

    # 角色/狀態
    role = Column(String(20), default="user")           # user/admin
    status = Column(String(20), default="active")       # active/disabled/banned
    is_verified = Column(Boolean, default=False)

    # 審計 & 行為
    # 下面時間默認存 UTC；如果要北京時區，改成 server_default=func.timezone('Asia/Shanghai', func.now()) (PostgreSQL)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    register_ip = Column(String(45), nullable=True)     # IPv4/IPv6
    last_login = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)

    login_count = Column(Integer, default=0)
    failed_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime, nullable=True)

    # 在線時長（秒）
    total_online_seconds = Column(Integer, default=0)
    current_session_started_at = Column(DateTime, nullable=True)  # 登入成功時設置；登出時計入時長並清空
    last_seen = Column(DateTime, nullable=True)                   # 最近一次有有效 token 的請求時間

    profile_picture = Column(String(255), nullable=True)
    usage_summary = relationship("ApiUsageSummary", back_populates="user", lazy="joined")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")  # ✅ 添加sessions关系
    db_permissions = relationship("UserDbPermission", back_populates="user", cascade="all, delete-orphan")

    # informations = relationship("Information", back_populates="user")

    # ✅ 添加计算属性（不存储，动态计算）
    @property
    def total_online_time(self) -> int:
        """所有会话的累计在线时长"""
        return sum(s.total_online_seconds for s in self.sessions)

    @property
    def active_session_count(self) -> int:
        """当前活跃会话数"""
        from datetime import datetime
        now = datetime.utcnow()
        return len([s for s in self.sessions if not s.revoked and s.expires_at > now])


class Session(Base):
    """用户会话追踪表"""
    __tablename__ = "sessions"

    # 主键
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(128), unique=True, index=True, nullable=False)  # UUID

    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)  # 冗余字段，提升查询性能

    # 会话生命周期
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_activity_at = Column(DateTime, default=func.now(), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(100), nullable=True)  # "logout", "admin_revoke", "suspicious", "expired"

    # 设备与网络追踪（用户需求）
    device_info = Column(String(255), nullable=True)  # 当前User-Agent
    first_device_info = Column(String(255), nullable=True)  # 首次User-Agent（用于对比）
    device_fingerprint = Column(String(64), nullable=True)  # 设备指纹hash
    device_change_count = Column(Integer, default=0, nullable=False)  # 设备切换次数（User-Agent变化）
    first_ip = Column(String(45), nullable=False)  # 会话创建时的IP
    current_ip = Column(String(45), nullable=False)  # 最后已知IP
    ip_change_count = Column(Integer, default=0, nullable=False)  # IP切换次数
    ip_history = Column(Text, nullable=True)  # JSON数组: [{ip, timestamp}, ...]
    device_changed = Column(Boolean, default=False, nullable=False)  # 设备指纹是否变化

    # 使用统计（用户需求）
    refresh_count = Column(Integer, default=0, nullable=False)  # Token刷新次数
    total_online_seconds = Column(Integer, default=0, nullable=False)  # 会话在线时长
    current_session_started_at = Column(DateTime, nullable=True)  # 当前活跃时段开始时间
    last_seen = Column(DateTime, nullable=True)  # 最后API请求时间

    # 安全标记
    is_suspicious = Column(Boolean, default=False, nullable=False)  # 可疑会话标记
    suspicious_reason = Column(String(255), nullable=True)  # 标记原因

    # 关系
    user = relationship("User", back_populates="sessions")
    refresh_tokens = relationship("RefreshToken", back_populates="session", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'revoked', 'expires_at'),
        Index('idx_session_activity', 'last_activity_at'),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)

    # ✅ 关联到session（而非直接关联user）
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True)  # nullable for migration
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 冗余字段，方便查询

    # 生命周期
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    replaced_by = Column(String, nullable=True)  # Token轮换链

    # 追踪信息
    ip_address = Column(String(45), nullable=True)  # Token创建时的IP
    device_info = Column(String, nullable=True)  # Token创建时的设备

    # 关系
    session = relationship("Session", back_populates="refresh_tokens")
    user = relationship("User", back_populates="refresh_tokens")

class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # optional: 若有 user 模型
    path = Column(String(255), nullable=False)
    duration = Column(Float, nullable=False)
    status_code = Column(Integer, nullable=False)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    referer = Column(String(255), nullable=True)
    called_at = Column(DateTime, server_default=func.now())
    request_size = Column(Integer, nullable=False, default=0)  # 新增：请求大小
    response_size = Column(Integer, nullable=False, default=0)  # 新增：响应大小

    user = relationship("User", backref="api_logs")


class ApiUsageSummary(Base):
    __tablename__ = "api_usage_summary"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    path = Column(String(255), nullable=False)
    count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

    total_duration = Column(DECIMAL(10, 2), default=0.00)
    # 修改字段类型为 DECIMAL，保留两位小数
    total_upload = Column(DECIMAL(10, 2), default=0.00)  # 上行流量，单位 KB
    total_download = Column(DECIMAL(10, 2), default=0.00)  # 下行流量，单位 KB

    user = relationship("User", back_populates="usage_summary")


class UserDbPermission(Base):
    """用户数据库权限表"""
    __tablename__ = "user_db_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)  # 冗余字段，方便查询
    db_key = Column(String(50), nullable=False, index=True)    # 数据库代号
    can_write = Column(Boolean, default=False, nullable=False) # 是否可写
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 唯一约束：每个用户对每个数据库只能有一条权限记录
    __table_args__ = (
        UniqueConstraint('user_id', 'db_key', name='uix_user_db'),
        Index('idx_user_db', 'user_id', 'db_key'),
        {'extend_existing': True}  # 允许扩展已存在的表
    )

    # 关系
    user = relationship("User", back_populates="db_permissions")


class SecretKey(Base):
    """SECRET_KEY存储表"""
    __tablename__ = "secret_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_value = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True, nullable=False)  # 当前活跃的密钥
    revoked_reason = Column(String(100), nullable=True)  # "rotated", "compromised"

    __table_args__ = (
        Index('idx_active_key', 'active', 'expires_at'),
    )

