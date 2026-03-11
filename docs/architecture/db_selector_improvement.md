# 数据库选择架构改进方案

## 方案 1：依赖注入封装（推荐）

### 实现

```python
# app/sql/db_selector.py
"""
数据库选择依赖注入
根据用户角色自动选择合适的数据库
"""
from typing import Optional
from fastapi import Depends
from app.service.auth import get_current_user
from app.service.auth import User
from app.common.path import (
   DIALECTS_DB_ADMIN, DIALECTS_DB_USER,
   QUERY_DB_ADMIN, QUERY_DB_USER
)


def get_dialects_db(user: Optional[User] = Depends(get_current_user)) -> str:
   """根据用户角色返回方言数据库路径"""
   return DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER


def get_query_db(user: Optional[User] = Depends(get_current_user)) -> str:
   """根据用户角色返回查询数据库路径"""
   return QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
```

### 使用方式

**之前（22 个函数都要写）：**
```python
@router.post("/phonology")
async def api_run_phonology_analysis(
    payload: AnalysisPayload,
    user: Optional[User] = Depends(get_current_user)
):
    # 每个函数都要写这两行
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
    query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

    result = await asyncio.to_thread(
        run_phonology_analysis,
        **payload.dict(),
        dialects_db=db_path,
        query_db=query_db
    )
    return result
```

**之后（依赖注入自动处理）：**
```python
@router.post("/phonology")
async def api_run_phonology_analysis(
    payload: AnalysisPayload,
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db)
):
    # 直接使用，不需要判断
    result = await asyncio.to_thread(
        run_phonology_analysis,
        **payload.dict(),
        dialects_db=dialects_db,
        query_db=query_db
    )
    return result
```

### 优点
✅ **消除重复代码**：数据库选择逻辑只写一次
✅ **自动处理**：FastAPI 自动注入正确的数据库路径
✅ **易于维护**：修改逻辑只需改一个地方
✅ **易于测试**：可以轻松 mock 依赖
✅ **类型安全**：返回类型明确（str）
✅ **向后兼容**：不需要大规模重构

### 迁移步骤

1. 创建 `app/sql/db_selector.py`
2. 逐个修改路由函数：
   - 移除 `user: Optional[User] = Depends(get_current_user)`
   - 添加 `dialects_db: str = Depends(get_dialects_db)`
   - 添加 `query_db: str = Depends(get_query_db)`
   - 移除函数内部的数据库选择逻辑
3. 测试验证

---

## 方案 2：服务层封装

### 实现

```python
# app/service/base.py
"""
基础服务类，封装数据库选择逻辑
"""
from typing import Optional
from app.service.auth import User
from app.common.path import (
   DIALECTS_DB_ADMIN, DIALECTS_DB_USER,
   QUERY_DB_ADMIN, QUERY_DB_USER
)


class BaseService:
   """基础服务类，所有服务继承此类"""

   def __init__(self, user: Optional[User] = None):
      self.user = user
      self.dialects_db = self._get_dialects_db()
      self.query_db = self._get_query_db()

   def _get_dialects_db(self) -> str:
      """根据用户角色返回方言数据库路径"""
      return DIALECTS_DB_ADMIN if self.user and self.user.role == "admin" else DIALECTS_DB_USER

   def _get_query_db(self) -> str:
      """根据用户角色返回查询数据库路径"""
      return QUERY_DB_ADMIN if self.user and self.user.role == "admin" else QUERY_DB_USER


# app/service/phonology_service.py
class PhonologyService(BaseService):
   """音韵分析服务"""

   async def analyze(self, payload: AnalysisPayload):
      """执行音韵分析"""
      result = await asyncio.to_thread(
         run_phonology_analysis,
         **payload.dict(),
         dialects_db=self.dialects_db,
         query_db=self.query_db
      )
      return result
```

### 使用方式

```python
@router.post("/phonology")
async def api_run_phonology_analysis(
    payload: AnalysisPayload,
    user: Optional[User] = Depends(get_current_user)
):
    service = PhonologyService(user)
    result = await service.analyze(payload)
    return result
```

### 优点
✅ **业务逻辑封装**：服务层更清晰
✅ **符合分层架构**：路由层只负责请求处理
✅ **易于扩展**：可以添加更多服务方法
✅ **代码复用**：多个路由可以共享服务

### 缺点
❌ **重构成本高**：需要创建服务类
❌ **学习曲线**：团队需要理解服务层模式

---

## 方案 3：数据库连接池改进

### 实现

```python
# app/sql/db_pool.py
"""
数据库连接池，支持基于用户角色的连接获取
"""
from typing import Optional
from fastapi import Depends
from app.service.auth import get_current_user
from app.service.auth import User

def get_dialects_connection(user: Optional[User] = Depends(get_current_user)):
    """获取方言数据库连接"""
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        yield conn

def get_query_connection(user: Optional[User] = Depends(get_current_user)):
    """获取查询数据库连接"""
    db_path = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        yield conn
```

### 使用方式

```python
@router.post("/phonology")
async def api_run_phonology_analysis(
    payload: AnalysisPayload,
    dialects_conn = Depends(get_dialects_connection),
    query_conn = Depends(get_query_connection)
):
    # 直接使用连接对象
    result = dialects_conn.execute(query)
    return result
```

### 优点
✅ **基础设施层处理**：路由层完全不关心数据库选择
✅ **连接管理自动化**：自动获取和释放连接

### 缺点
❌ **不适合当前架构**：你的服务层函数需要数据库路径，不是连接对象
❌ **改动较大**：需要修改服务层接口

---

## 方案对比

| 特性 | 方案 1（依赖注入） | 方案 2（服务层） | 方案 3（连接池） | 当前设计 |
|------|------------------|----------------|----------------|---------|
| 代码重复 | ✅ 无 | ✅ 无 | ✅ 无 | ❌ 严重 |
| 易于维护 | ✅ 优秀 | ✅ 优秀 | ✅ 优秀 | ❌ 困难 |
| 重构成本 | ✅ 低 | ⚠️ 中 | ❌ 高 | - |
| 测试友好 | ✅ 优秀 | ✅ 优秀 | ⚠️ 一般 | ❌ 困难 |
| 类型安全 | ✅ 是 | ✅ 是 | ✅ 是 | ⚠️ 一般 |
| 符合现有架构 | ✅ 完全 | ⚠️ 需调整 | ❌ 需大改 | - |

---

## 推荐方案：方案 1（依赖注入封装）

### 理由

1. **最小改动**：只需创建一个文件，修改函数签名
2. **符合 FastAPI 哲学**：充分利用依赖注入
3. **向后兼容**：不破坏现有架构
4. **立即见效**：消除 22 个函数的重复代码
5. **易于测试**：可以轻松 mock 依赖

### 实施计划

**第一步：创建依赖注入函数**
```bash
# 创建文件
touch app/sql/db_selector.py
```

**第二步：逐步迁移**
优先迁移使用频率高的路由：
1. phonology.py (5 个函数)
2. search.py (2 个函数)
3. compare.py (2 个函数)
4. ...

**第三步：验证测试**
每迁移一个文件，立即测试：
```python
# 测试脚本
python -c "from app.routes.phonology import router; print('OK')"
```

**第四步：清理旧代码**
迁移完成后，删除不再需要的 user 参数。

---

## 其他改进建议

### 1. 使用枚举定义角色
```python
# app/auth/models.py
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class User(Base):
    role: UserRole  # 而不是 str
```

### 2. 配置化数据库映射
```python
# app/common/config.py
DB_MAPPING = {
    UserRole.ADMIN: {
        "dialects": DIALECTS_DB_ADMIN,
        "query": QUERY_DB_ADMIN,
    },
    UserRole.USER: {
        "dialects": DIALECTS_DB_USER,
        "query": QUERY_DB_USER,
    }
}

def get_db_for_role(role: UserRole, db_type: str) -> str:
    return DB_MAPPING.get(role, DB_MAPPING[UserRole.USER])[db_type]
```

### 3. 添加数据库选择日志
```python
def get_dialects_db(user: Optional[User] = Depends(get_current_user)) -> str:
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
    logger.debug(f"Selected dialects DB: {db_path} for user: {user.username if user else 'anonymous'}")
    return db_path
```

---

## 总结

**当前设计的问题**：
- ❌ 代码重复（22 个函数）
- ❌ 容易出错（这次就证明了）
- ❌ 维护困难（修改需要改 22 个地方）

**推荐改进**：
- ✅ 使用依赖注入封装数据库选择逻辑
- ✅ 消除重复代码
- ✅ 集中管理，易于维护
- ✅ 符合 FastAPI 最佳实践

**实施建议**：
1. 先创建 `app/sql/db_selector.py`
2. 逐步迁移现有路由
3. 每迁移一个文件立即测试
4. 最后清理旧代码

这样可以在不破坏现有功能的前提下，大幅提升代码质量和可维护性。
