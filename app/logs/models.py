# logs/models.py
"""
日志系统数据库模型
用于替代原有的 txt 文件日志
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ApiVisitLog(Base):
    """
    HTML 页面访问统计
    存储聚合数据，记录各 HTML 页面的访问次数
    类似 api_usage_stats.txt 的数据结构
    """
    __tablename__ = "api_visit_log"

    id = Column(Integer, primary_key=True)
    path = Column(String(255), nullable=False, index=True)
    # path: HTML 页面路径（如 '/', '/admin', '/detail'）

    date = Column(DateTime, nullable=True, index=True)
    # date: NULL 表示总计，具体日期表示每日统计

    count = Column(Integer, default=0)
    # count: 访问次数

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 唯一约束：确保同一路径、同一日期只有一条记录
    __table_args__ = (
        Index('idx_unique_visit', 'path', 'date', unique=True),
        Index('idx_path_date', 'path', 'date'),
    )


class ApiKeywordLog(Base):
    """
    API 关键词日志
    替代 api_keywords_log.txt
    记录每次 API 调用的具体参数
    """
    __tablename__ = "api_keyword_log"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    path = Column(String(255), nullable=False, index=True)
    field = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 联合索引，用于按时间和路径快速查询
    __table_args__ = (
        Index('idx_timestamp_path', 'timestamp', 'path'),
        Index('idx_field_value', 'field', 'value', mysql_length={'value': 100}),
    )


class ApiStatistics(Base):
    """
    API 统计数据
    替代 api_keywords_summary.txt 和 api_usage_stats.txt
    存储聚合后的统计数据
    """
    __tablename__ = "api_statistics"

    id = Column(Integer, primary_key=True)
    stat_type = Column(String(50), nullable=False, index=True)
    # 统计类型：
    # - 'keyword_total': 关键词总计
    # - 'keyword_daily': 关键词每日统计
    # - 'usage_total': API调用总计
    # - 'usage_daily': API调用每日统计

    date = Column(DateTime, nullable=True, index=True)
    # NULL 表示总计，非 NULL 表示日期统计

    category = Column(String(100), nullable=False)
    # 分类：path（API路径）或 field（参数字段名）

    item = Column(String(255), nullable=False)
    # 具体项：具体的 API 路径或关键词

    count = Column(Integer, default=0)
    # 计数

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 唯一约束：确保同一类型、日期、分类、项目只有一条记录
    __table_args__ = (
        Index('idx_unique_stat', 'stat_type', 'date', 'category', 'item', unique=True),
        Index('idx_stat_type_date', 'stat_type', 'date'),
    )

    def __repr__(self):
        return f"<ApiStatistics(type={self.stat_type}, date={self.date}, category={self.category}, item={self.item}, count={self.count})>"
