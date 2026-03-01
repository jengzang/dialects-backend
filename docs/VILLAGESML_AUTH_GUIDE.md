# VillagesML 身份验证修改指南
# VillagesML Authentication Implementation Guide

**创建日期**: 2026-02-23
**状态**: 需要实施

---

## 📋 问题说明

VillagesML 模块的路由当前**没有实现身份验证**，导致：
1. Compute 端点（计算密集型）任何人都可以调用
2. Admin 端点（管理功能）任何人都可以访问
3. 无法追踪是谁在使用这些功能

## 🔐 项目的身份验证模式

### 模式 1: 管理员端点（Admin Only）

```python
from app.auth.dependencies import get_current_admin_user
from app.auth.models import User

@router.get("/admin/something")
def admin_endpoint(
    admin: User = Depends(get_current_admin_user)  # 强制 admin 角色
):
    # admin 必定是 admin 角色，否则抛出 403
    pass
```

**特点:**
- 自动验证 JWT token
- 自动检查 admin 角色
- 未登录 → 401 Unauthorized
- 非 admin → 403 Forbidden

### 模式 2: 需要登录的端点（Authenticated）

```python
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User
from typing import Optional

@router.post("/api/something")
async def authenticated_endpoint(
    user: Optional[User] = Depends(ApiLimiter)  # 可能是 None
):
    # 手动检查登录
    if not user:
        raise HTTPException(status_code=401, detail="需要登录")

    # user 是已登录用户
    pass
```

**特点:**
- `ApiLimiter` 自动处理速率限制
- 返回 `Optional[User]`（可能是 None）
- 需要手动检查 `if not user`
- 或者在 `common/api_config.py` 中配置 `require_login: True`

### 模式 3: 公开端点（Public）

```python
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User
from typing import Optional

@router.get("/api/something")
async def public_endpoint(
    user: Optional[User] = Depends(ApiLimiter)  # 可以是 None
):
    # user 可能是 None（匿名）或 User（已登录）
    # 根据 user 是否存在决定权限
    if user:
        # 已登录用户的逻辑
        pass
    else:
        # 匿名用户的逻辑
        pass
```

**特点:**
- 允许匿名访问
- 但仍然有速率限制（匿名用户限制更严格）
- 可以根据登录状态提供不同功能

---

## 🔧 需要修改的文件

### 1. Compute 模块（4 个文件）

所有 compute 模块的端点都应该**需要登录**。

#### 文件: `app/tools/VillagesML/compute/clustering.py`

**需要修改的端点:**
- `POST /compute/clustering/run` ✅ 已修改
- `POST /compute/clustering/scan` ✅ 已修改
- `GET /compute/clustering/cache-stats` - 可以公开
- `DELETE /compute/clustering/cache` - 需要 admin

**修改模板:**
```python
# 在文件顶部添加导入
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User
from typing import Optional

# 修改端点签名
@router.post("/run")
async def run_clustering(
    params: ClusteringParams,
    user: Optional[User] = Depends(ApiLimiter),  # 添加这行
    engine: ClusteringEngine = Depends(get_clustering_engine)
):
    # 在函数开头添加检查
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

    # 原有逻辑...
```

#### 文件: `app/tools/VillagesML/compute/semantic.py`

**需要修改的端点:**
- `POST /compute/semantic/cooccurrence` - 需要登录
- `POST /compute/semantic/network` - 需要登录

**修改方法:** 同上

#### 文件: `app/tools/VillagesML/compute/features.py`

**需要修改的端点:**
- `POST /compute/features/extract` - 需要登录

**修改方法:** 同上

#### 文件: `app/tools/VillagesML/compute/subset.py`

**需要修改的端点:**
- `POST /compute/subset/analyze` - 需要登录

**修改方法:** 同上

---

### 2. Admin 模块（1 个文件）

所有 admin 端点都应该**需要 admin 角色**。

#### 文件: `app/tools/VillagesML/admin/run_ids.py`

**需要修改的端点:**
- `GET /run-ids/active` - 可以公开（只读）
- `GET /run-ids/active/{analysis_type}` - 可以公开（只读）
- `POST /run-ids/active/{analysis_type}` - 需要 admin
- `GET /run-ids/history` - 需要 admin
- `DELETE /run-ids/cache` - 需要 admin

**修改模板（admin 端点）:**
```python
# 在文件顶部添加导入
from app.auth.dependencies import get_current_admin_user
from app.auth.models import User

# 修改端点签名
@router.post("/run-ids/active/{analysis_type}")
def set_active_run_id(
    analysis_type: str,
    request: SetActiveRunIDRequest,
    admin: User = Depends(get_current_admin_user)  # 添加这行
):
    # 不需要手动检查，get_current_admin_user 会自动验证
    # admin 必定是 admin 角色

    # 原有逻辑...
```

**修改模板（公开端点）:**
```python
# 在文件顶部添加导入
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User
from typing import Optional

# 修改端点签名
@router.get("/run-ids/active")
def get_all_active_run_ids(
    user: Optional[User] = Depends(ApiLimiter)  # 添加这行
):
    # 不需要检查 user，允许匿名访问
    # 但仍然有速率限制

    # 原有逻辑...
```

---

## 📝 修改步骤

### Step 1: 修改 compute/clustering.py ✅ 已完成

- [x] 添加导入
- [x] 修改 `/run` 端点
- [x] 修改 `/scan` 端点

### Step 2: 修改 compute/semantic.py

```bash
# 需要修改的端点
- POST /compute/semantic/cooccurrence
- POST /compute/semantic/network
```

### Step 3: 修改 compute/features.py

```bash
# 需要修改的端点
- POST /compute/features/extract
```

### Step 4: 修改 compute/subset.py

```bash
# 需要修改的端点
- POST /compute/subset/analyze
```

### Step 5: 修改 admin/run_ids.py

```bash
# 需要 admin 的端点
- POST /run-ids/active/{analysis_type}
- DELETE /run-ids/cache

# 可以公开的端点（添加 ApiLimiter 但不检查）
- GET /run-ids/active
- GET /run-ids/active/{analysis_type}
- GET /run-ids/history
```

---

## 🧪 测试方法

### 测试未登录访问（应该返回 401）

```bash
# 测试 compute 端点
curl -X POST http://localhost:5000/api/villages/compute/clustering/run \
  -H "Content-Type: application/json" \
  -d '{"region_level": "county", "algorithm": "kmeans", "k": 4}'

# 预期: 401 Unauthorized, detail: "此功能需要登录"
```

### 测试已登录访问（应该成功）

```bash
# 1. 先登录获取 token
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user@example.com", "password": "password"}'

# 2. 使用 token 访问
curl -X POST http://localhost:5000/api/villages/compute/clustering/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"region_level": "county", "algorithm": "kmeans", "k": 4}'

# 预期: 200 OK, 返回聚类结果
```

### 测试 admin 端点（应该返回 403 for non-admin）

```bash
# 使用普通用户 token
curl -X POST http://localhost:5000/api/villages/admin/run-ids/active/clustering \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <user_token>" \
  -d '{"run_id": "test_001"}'

# 预期: 403 Forbidden, detail: "Admin access required"

# 使用 admin token
curl -X POST http://localhost:5000/api/villages/admin/run-ids/active/clustering \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"run_id": "test_001"}'

# 预期: 200 OK
```

---

## 📊 修改总结

| 模块 | 文件 | 端点数 | 需要登录 | 需要 Admin | 公开 |
|------|------|--------|----------|-----------|------|
| compute | clustering.py | 4 | 2 | 1 | 1 |
| compute | semantic.py | 2 | 2 | 0 | 0 |
| compute | features.py | 1 | 1 | 0 | 0 |
| compute | subset.py | 1 | 1 | 0 | 0 |
| admin | run_ids.py | 5 | 0 | 2 | 3 |
| **总计** | **5 个文件** | **13 个端点** | **6 个** | **3 个** | **4 个** |

---

## ⚠️ 重要提示

1. **不要忘记导入**: 每个修改的文件都需要添加导入语句
2. **手动检查**: 使用 `ApiLimiter` 时需要手动 `if not user` 检查
3. **自动检查**: 使用 `get_current_admin_user` 时自动检查，无需手动
4. **配置同步**: 确保 `common/api_config.py` 中的配置与实际实现一致
5. **测试覆盖**: 修改后务必测试所有端点

---

## 🔗 相关文件

- 身份验证依赖: `app/auth/dependencies.py`
- API 限流器: `app/logs/service/api_limiter.py`
- API 配置: `common/api_config.py`
- 用户模型: `app/auth/models.py`

---

**下一步**: 按照上述步骤逐个修改文件，并进行测试验证。
