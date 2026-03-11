# 依赖注入封装重构 vs 服务层重构对比

## 概览对比

| 维度 | 依赖注入封装重构 | 服务层重构 |
|------|-----------------|-----------|
| **目标** | 消除路由层重复代码 | 降低服务层对 User 对象的依赖 |
| **范围** | 路由层（app/routes/） | 服务层（app/service/）+ 路由层 |
| **改动量** | 中等（22 个函数） | 大（需要改服务层接口） |
| **复杂度** | 低 | 中高 |
| **风险** | 低 | 中 |
| **当前状态** | 进行中（59.1%） | 未开始 |

## 详细对比

### 1. 依赖注入封装重构（当前正在做）

#### 目标
消除路由层中重复的数据库选择逻辑

#### 问题
```python
# 22 个函数都有这样的重复代码
@router.post("/phonology")
async def api_run_phonology_analysis(
    payload: AnalysisPayload,
    user: Optional[User] = Depends(get_current_user)
):
    # 重复代码 1
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
    # 重复代码 2
    query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

    result = run_phonology_analysis(..., dialects_db=db_path, query_db=query_db)
```

#### 解决方案
```python
# 创建依赖注入函数（只写一次）
# app/sql/db_selector.py
def get_dialects_db(user: Optional[User] = Depends(get_current_user)) -> str:
    return DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER

def get_query_db(user: Optional[User] = Depends(get_current_user)) -> str:
    return QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

# 路由层使用（22 个函数都这样改）
@router.post("/phonology")
async def api_run_phonology_analysis(
    payload: AnalysisPayload,
    dialects_db: str = Depends(get_dialects_db),  # 自动注入
    query_db: str = Depends(get_query_db)         # 自动注入
):
    # 不需要判断，直接使用
    result = run_phonology_analysis(..., dialects_db=dialects_db, query_db=query_db)
```

#### 改动范围
- ✅ 创建 `app/sql/db_selector.py`（1 个新文件）
- ✅ 修改路由层函数签名（22 个函数）
- ✅ 移除路由层的数据库选择逻辑（22 处）
- ❌ **不改**服务层

#### 效果
- 代码重复：22 处 → 1 处（减少 95.5%）
- 维护成本：22 个文件 → 1 个文件
- 服务层接口：**不变**

---

### 2. 服务层重构（建议的下一步）

#### 目标
降低服务层对 User 对象的依赖，提高可测试性

#### 问题
```python
# 服务层过度依赖 User 对象
# app/service/custom.py
def get_from_submission(
    locations: List[str],
    regions: List[str],
    features: List[str],
    user: Optional[User],  # 依赖整个 User 对象
    db: Session
):
    # 实际只用了 user.id
    query = db.query(Submission).filter(
        Submission.user_id == user.id if user else True
    )
    return query.all()

# 路由层必须传递整个 User 对象
@router.get("/get_custom")
async def query_location_data(
    user: Optional[User] = Depends(get_current_user)
):
    result = get_from_submission(..., user=user, db=db)
```

**问题分析**：
1. 服务层依赖 User 模型（来自 app/auth/models.py）
2. 实际只需要 `user.id`（一个整数）
3. 测试困难（需要构造完整的 User 对象）
4. 违反最小知识原则

#### 解决方案
```python
# 服务层只接受必要的参数
# app/service/custom.py
def get_from_submission(
    locations: List[str],
    regions: List[str],
    features: List[str],
    user_id: Optional[int],  # 只要 ID
    db: Session
):
    # 直接使用 user_id
    query = db.query(Submission).filter(
        Submission.user_id == user_id if user_id else True
    )
    return query.all()

# 创建专门的依赖注入
# app/auth/dependencies.py
def get_current_user_id(user: Optional[User] = Depends(get_current_user)) -> Optional[int]:
    return user.id if user else None

# 路由层只注入 ID
@router.get("/get_custom")
async def query_location_data(
    user_id: Optional[int] = Depends(get_current_user_id)
):
    result = get_from_submission(..., user_id=user_id, db=db)
```

#### 改动范围
- ✅ 创建 `get_current_user_id` 依赖注入（1 个新函数）
- ✅ 修改服务层函数签名（约 10 个函数）
- ✅ 修改服务层函数实现（user.id → user_id）
- ✅ 修改路由层调用（约 10 个函数）

#### 效果
- 服务层不再依赖 User 模型
- 测试更简单（只需传递 int）
- 更符合依赖倒置原则

---

## 两个重构的关系

### 独立性
- ✅ 两个重构**相互独立**
- ✅ 可以分别进行
- ✅ 不会互相冲突

### 顺序建议
1. **先完成依赖注入封装重构**（当前进行中）
   - 风险低
   - 改动小
   - 立即见效

2. **再进行服务层重构**（可选）
   - 需要更多规划
   - 改动较大
   - 长期收益

### 组合效果

如果两个重构都完成：

**之前**（原始代码）：
```python
# 路由层
@router.get("/get_custom")
async def query_location_data(
    user: Optional[User] = Depends(get_current_user)
):
    # 重复的数据库选择逻辑
    query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

    # 传递整个 user 对象
    result = get_from_submission(..., user=user, db=db)

# 服务层
def get_from_submission(locations, regions, features, user, db):
    query = db.query(Submission).filter(
        Submission.user_id == user.id if user else True
    )
```

**之后**（两个重构都完成）：
```python
# 路由层
@router.get("/get_custom")
async def query_location_data(
    query_db: str = Depends(get_query_db),        # 依赖注入封装
    user_id: Optional[int] = Depends(get_current_user_id)  # 服务层重构
):
    # 不需要判断，直接使用
    result = get_from_submission(..., user_id=user_id, db=db)

# 服务层
def get_from_submission(locations, regions, features, user_id: Optional[int], db):
    query = db.query(Submission).filter(
        Submission.user_id == user_id if user_id else True
    )
```

---

## 实际例子对比

### 例子：search_chars 函数

#### 原始代码
```python
@router.get("/search_chars/")
async def search_chars(
    chars: List[str] = Query(...),
    locations: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    # 重复代码 1：数据库选择
    query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER

    # 重复代码 2：地点处理
    locations_processed = match_locations_batch_all(
        locations or [],
        query_db=query_db,
        db=db,
        user=user  # 传递整个 user 对象
    )

    # 调用服务层
    result = search_characters(
        chars=chars,
        locations=locations_processed,
        db_path=db_path,
        query_db_path=query_db
    )
```

#### 只完成依赖注入封装重构
```python
@router.get("/search_chars/")
async def search_chars(
    chars: List[str] = Query(...),
    locations: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    dialects_db: str = Depends(get_dialects_db),  # ✅ 自动注入
    query_db: str = Depends(get_query_db),        # ✅ 自动注入
    user: Optional[User] = Depends(get_current_user)  # ⚠️ 仍需要
):
    # ✅ 不需要数据库选择逻辑

    # ⚠️ 仍需要传递 user 对象
    locations_processed = match_locations_batch_all(
        locations or [],
        query_db=query_db,
        db=db,
        user=user  # 仍需要传递
    )

    # ✅ 直接使用注入的数据库路径
    result = search_characters(
        chars=chars,
        locations=locations_processed,
        db_path=dialects_db,
        query_db_path=query_db
    )
```

**改进**：
- ✅ 消除了数据库选择的重复代码
- ⚠️ 仍需要 user 对象（因为 match_locations_batch_all 需要）

#### 两个重构都完成
```python
@router.get("/search_chars/")
async def search_chars(
    chars: List[str] = Query(...),
    locations: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    dialects_db: str = Depends(get_dialects_db),  # ✅ 自动注入
    query_db: str = Depends(get_query_db),        # ✅ 自动注入
    user_id: Optional[int] = Depends(get_current_user_id)  # ✅ 只注入 ID
):
    # ✅ 不需要数据库选择逻辑

    # ✅ 只传递 user_id
    locations_processed = match_locations_batch_all(
        locations or [],
        query_db=query_db,
        db=db,
        user_id=user_id  # 只传递 ID
    )

    # ✅ 直接使用注入的数据库路径
    result = search_characters(
        chars=chars,
        locations=locations_processed,
        db_path=dialects_db,
        query_db_path=query_db
    )
```

**改进**：
- ✅ 消除了数据库选择的重复代码
- ✅ 不需要完整的 user 对象
- ✅ 服务层更简洁、可测试

---

## 决策建议

### 当前阶段：完成依赖注入封装重构

**理由**：
1. ✅ 已经完成 59.1%
2. ✅ 风险低，改动小
3. ✅ 立即见效（消除 22 处重复）
4. ✅ 不影响服务层

**剩余工作**：
- 还有 9 个函数未完成
- 预计 30 分钟完成

### 下一阶段：考虑服务层重构

**何时进行**：
- ✅ 依赖注入封装重构完成后
- ✅ 有充足的测试覆盖
- ✅ 团队达成共识

**是否必须**：
- ❌ 不是必须的
- ✅ 但是推荐的（长期收益）

**优先级**：
- 高优先级：纯查询函数（只需要 user_id）
- 中优先级：创建/更新函数（需要 user_id + username）
- 低优先级：复杂函数（需要完整 user 对象）

---

## 总结

| 特性 | 依赖注入封装重构 | 服务层重构 |
|------|-----------------|-----------|
| **解决的问题** | 路由层代码重复 | 服务层过度依赖 |
| **改动层次** | 路由层 | 服务层 + 路由层 |
| **改动量** | 中（22 个函数） | 大（约 20 个函数） |
| **风险** | 低 | 中 |
| **测试影响** | 小 | 大 |
| **立即收益** | 高 | 中 |
| **长期收益** | 中 | 高 |
| **是否必须** | 推荐 | 可选 |
| **当前状态** | 59.1% 完成 | 未开始 |

**建议**：
1. ✅ 先完成依赖注入封装重构（剩余 9 个函数）
2. ⏸️ 暂停，评估效果
3. 🤔 讨论是否进行服务层重构
4. ✅ 如果决定进行，分阶段实施

---

**日期**: 2026-03-05
**作者**: Claude Sonnet 4.5
