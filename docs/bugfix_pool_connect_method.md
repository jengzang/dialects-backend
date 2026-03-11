# Bug Fix: Analytics API 数据库连接错误

## 问题描述

**错误信息 1**:
```
AttributeError: 'SQLiteConnectionPool' object has no attribute 'connect'
```

**错误信息 2**:
```
AttributeError: 'sqlite3.Connection' object has no attribute 'query'
```

**触发端点**: `GET /admin/analytics/user-segments?include_users=false`

**错误位置**:
1. `app/routes/admin/analytics.py:48` - 错误的连接池方法
2. `app/admin/analytics/segmentation.py:36` - 类型不匹配

## 根本原因

### 问题 1: 错误的连接池方法名
代码中使用了错误的方法名 `pool.connect()` 来获取数据库连接，但 `SQLiteConnectionPool` 类的正确方法名是 `pool.get_connection()`。

### 问题 2: 数据库连接类型不匹配
更严重的问题是 `get_auth_db()` 函数返回的是原始 `sqlite3.Connection` 对象，但 analytics 函数期望的是 SQLAlchemy `Session` 对象。

- ❌ `get_auth_db()` 返回: `sqlite3.Connection` (原始连接)
- ✅ Analytics 函数需要: `sqlalchemy.orm.Session` (ORM 会话)

Analytics 函数使用 SQLAlchemy ORM 语法 (`db.query()`, `db.outerjoin()` 等)，必须接收 SQLAlchemy Session 对象。

## 修复方案

### 方案：使用正确的依赖注入

删除自定义的 `get_auth_db()` 函数，改用项目中已有的标准 `get_db()` 函数。

### 修复前代码
```python
from app.sql.db_pool import get_db_pool

def get_auth_db():
    """Get auth database session."""
    pool = get_db_pool("data/auth.db")
    with pool.connect() as conn:  # ❌ 错误1: connect() 方法不存在
        yield conn  # ❌ 错误2: 返回 sqlite3.Connection，不是 Session

@router.get("/user-segments")
async def api_user_segments(
    db: Session = Depends(get_auth_db)  # ❌ 类型不匹配
):
    return get_user_segments(db)  # ❌ 期望 Session，实际是 Connection
```

### 修复后代码
```python
from app.auth.database import get_db  # ✅ 使用标准依赖

@router.get("/user-segments")
async def api_user_segments(
    db: Session = Depends(get_db)  # ✅ 正确：返回 SQLAlchemy Session
):
    return get_user_segments(db)  # ✅ 类型匹配
```

## 修复内容

### 1. 删除错误的依赖函数
**文件**: `app/routes/admin/analytics.py`
- 删除自定义的 `get_auth_db()` 函数
- 删除 `from app.sql.db_pool import get_db_pool` 导入

### 2. 使用正确的依赖
**文件**: `app/routes/admin/analytics.py`
- 添加 `from app.auth.database import get_db` 导入
- 将所有端点的 `Depends(get_auth_db)` 替换为 `Depends(get_db)`
- 共修改 12 个端点

### 3. 文档修复
**文件**: `CLAUDE.md`
- 第 201 行: 更新数据库操作示例代码

**文件**: `docs/api_stats_write_mechanism.md`
- 第 400 行: 更新连接池使用示例

## 为什么需要使用 SQLAlchemy Session？

Analytics 函数使用 SQLAlchemy ORM 语法，例如：

```python
# app/admin/analytics/segmentation.py
def get_user_segments(db: Session, include_users: bool = False):
    user_stats = db.query(  # ← 需要 Session.query()
        User.id,
        User.username,
        func.sum(ApiUsageSummary.count)
    ).outerjoin(  # ← 需要 Session.outerjoin()
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    ).group_by(User.id).all()  # ← 需要 Query.all()
```

这些方法只存在于 SQLAlchemy Session 对象中，原始 `sqlite3.Connection` 没有这些方法。

## 数据库连接方式对比

### 方式 1: SQLAlchemy ORM (推荐用于复杂查询)
```python
from app.auth.database import get_db

def my_route(db: Session = Depends(get_db)):
    # 使用 ORM
    users = db.query(User).filter(User.role == 'admin').all()
    return users
```

**优点**:
- 类型安全
- 自动关系映射
- 支持复杂查询
- 代码可读性高

**缺点**:
- 性能略低于原始 SQL
- 需要定义 ORM 模型

### 方式 2: 原始 SQLite 连接 (用于简单查询)
```python
from app.sql.db_pool import get_db_pool

pool = get_db_pool("data/auth.db")
with pool.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = ?", ("admin",))
    results = cursor.fetchall()
```

**优点**:
- 性能更高
- 更灵活

**缺点**:
- 需要手动处理 SQL
- 容易出现 SQL 注入
- 代码可读性较低

## 影响范围

### 受影响的端点
- `GET /admin/analytics/user-segments`
- `GET /admin/analytics/rfm-analysis`
- `GET /admin/analytics/anomaly-detection`
- `GET /admin/analytics/api-diversity`
- `GET /admin/analytics/user-preferences`
- `GET /admin/analytics/user-growth`
- `GET /admin/analytics/dashboard`
- `GET /admin/analytics/recent-trends`
- `GET /admin/analytics/api-performance`
- `GET /admin/analytics/geo-distribution`
- `GET /admin/analytics/device-distribution`
- `POST /admin/analytics/export`

所有使用 `get_auth_db()` 依赖注入的 analytics 端点都受影响。

## 测试验证

### 测试步骤
1. 启动服务器
2. 访问任意 analytics 端点，例如:
   ```
   GET /admin/analytics/user-segments?include_users=false
   ```
3. 验证返回 200 状态码而非 500 错误

### 预期结果
- ✅ 端点正常返回数据
- ✅ 无 AttributeError 异常
- ✅ 数据库连接正常获取和释放

## 预防措施

### 1. 代码审查
在代码审查时注意检查连接池的使用方式，确保使用正确的方法名。

### 2. 单元测试
建议为 analytics 路由添加单元测试，覆盖所有端点。

### 3. 文档更新
确保所有文档中的示例代码与实际 API 一致。

## 相关文件

- `app/sql/db_pool.py` - 连接池实现
- `app/routes/admin/analytics.py` - 修复的路由文件
- `CLAUDE.md` - 项目文档
- `docs/api_stats_write_mechanism.md` - API 统计文档

## 修复时间
2026-03-04

## 修复状态
✅ 已完成
- ✅ 代码修复
- ✅ 文档更新
- ✅ 验证无其他类似问题
