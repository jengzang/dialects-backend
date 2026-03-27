# 服务层 user 参数使用分析

## 问题

用户提出两个问题：
1. 类型 B（9 个函数）为什么需要保留 user 参数？
2. `match_locations_batch` 函数为什么要传 user？user 参数的作用是什么？

## 分析

### 1. match_locations_batch 中的 user 参数

**位置**：`app/service/match_input_tip.py:579`

**代码**：
```python
def match_locations_batch(input_string: str, filter_valid_abbrs_only=True, exact_only=True,
                          query_db=QUERY_DB_ADMIN, db: Session = None, user=None):
    # ...
    for idx, part in enumerate(parts):
        res = match_locations(part, filter_valid_abbrs_only, exact_only, query_db=query_db)

        # 关键逻辑：当 user 存在且不是精确匹配时
        if user and not filter_valid_abbrs_only and not exact_only:
            # 查询用户自定义的地点简称
            abbreviations = db.query(Information.簡稱).filter(
                Information.user_id == user.id  # 需要 user.id
            ).all()

            # 计算相似度，添加用户自定义的地点
            valid_abbrs = [
                abbr[0] for abbr in abbreviations
                if calculate_similarity(part, abbr[0]) > 50
            ]
            res_with_valid_abbrs = (valid_abbrs + list(res[0]), *res[1:])
            results.append(res_with_valid_abbrs)
```

**user 参数的作用**：
1. **查询用户自定义数据**：`Information.user_id == user.id`
2. **个性化匹配**：将用户自己提交的地点简称加入匹配结果
3. **可选功能**：只有在非精确匹配模式下才启用

### 2. 类型 B 函数需要 user 的原因

#### 分类说明

**类型 A（可以移除 user）**：
- 只需要数据库路径
- 不需要 user 对象的属性
- 可以用依赖注入的 `dialects_db` 和 `query_db` 替代

**类型 B（必须保留 user）**：
- 需要 `user.id` 或 `user.username`
- 需要传递给服务层函数
- 服务层需要查询用户特定的数据

#### 类型 B 函数详细分析

##### 1. app/routes/geo/get_coordinates.py - get_coordinates

**原因**：传递给 `query_dialect_abbreviations_orm`

```python
if query.iscustom and query.region_mode == 'yindian':
    abbr1 = query_dialect_abbreviations_orm(
        db, user, regions_list, locations_list  # 需要 user 对象
    )
```

**服务层使用**：
```python
def query_dialect_abbreviations_orm(db, user, region_input, location_sequence):
    # 查询用户自定义的区域和地点
    if user:
        custom_data = db.query(CustomRegion).filter(
            CustomRegion.user_id == user.id  # 需要 user.id
        ).all()
```

##### 2. app/routes/geo/get_regions.py - get_regions

**原因**：传递给 `fetch_dialect_region`

```python
return fetch_dialect_region(input_data, db=db, user=user)
```

**服务层使用**：
```python
def fetch_dialect_region(input_data, db, user):
    # 查询用户自定义的区域映射
    if user:
        custom_regions = db.query(CustomRegion).filter(
            CustomRegion.user_id == user.id
        ).all()
```

##### 3. app/routes/user/custom_query.py - query_location_data, get_custom_feature

**原因**：传递给 `get_from_submission` 和 `match_custom_feature`

```python
result = get_from_submission(
    query_params.locations,
    query_params.regions,
    query_params.need_features,
    user,  # 需要 user 对象
    db
)
```

**服务层使用**：
```python
def get_from_submission(locations, regions, features, user, db):
    # 查询用户提交的自定义数据
    query = db.query(Submission).filter(
        Submission.user_id == user.id if user else True  # 需要 user.id
    )
```

##### 4. app/routes/user/form_submit.py - submit_form, delete_form

**原因**：传递给 `handle_form_submission` 和 `handle_form_deletion`

```python
result = handle_form_submission(payload.dict(), user, db)
```

**服务层使用**：
```python
def handle_form_submission(data, user, db):
    # 创建提交记录，关联用户
    submission = Submission(
        user_id=user.id if user else None,  # 需要 user.id
        username=user.username if user else "anonymous",  # 需要 user.username
        location=data['location'],
        ...
    )
```

##### 5. app/routes/user/custom_regions.py - 3 个函数

**原因**：直接使用 `user.id` 和 `user.username`

```python
@router.post("/api/custom_regions")
async def create_or_update_custom_region(data, db, user):
    if not user:
        raise HTTPException(status_code=401, detail="需要登录")

    region, action = region_service.create_or_update_region(
        db=db,
        user_id=user.id,  # 直接使用
        username=user.username,  # 直接使用
        region_name=data.region_name,
        ...
    )
```

## 设计问题分析

### 当前设计的问题

1. **服务层过度依赖 user 对象**
   - 服务层函数接受整个 user 对象
   - 实际只需要 `user.id` 或 `user.username`
   - 违反了最小知识原则

2. **路由层和服务层耦合**
   - 路由层必须获取 user 对象才能调用服务层
   - 无法使用依赖注入优化

### 改进建议

#### 方案 1：服务层接受 user_id 而不是 user 对象

**之前**：
```python
def get_from_submission(locations, regions, features, user, db):
    query = db.query(Submission).filter(
        Submission.user_id == user.id if user else True
    )
```

**之后**：
```python
def get_from_submission(locations, regions, features, user_id: Optional[int], db):
    query = db.query(Submission).filter(
        Submission.user_id == user_id if user_id else True
    )
```

**路由层**：
```python
@router.get("/get_custom")
async def query_location_data(
    locations: List[str] = Query(...),
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user)
):
    result = get_from_submission(
        locations,
        regions,
        features,
        user_id=user.id if user else None,  # 只传递 ID
        db=db
    )
```

#### 方案 2：创建 user_id 依赖注入

```python
# app/auth/dependencies.py
def get_current_user_id(user: Optional[User] = Depends(get_current_user)) -> Optional[int]:
    """获取当前用户 ID"""
    return user.id if user else None

def get_current_username(user: Optional[User] = Depends(get_current_user)) -> Optional[str]:
    """获取当前用户名"""
    return user.username if user else None
```

**使用**：
```python
@router.get("/get_custom")
async def query_location_data(
    locations: List[str] = Query(...),
    db: Session = Depends(get_db_custom),
    user_id: Optional[int] = Depends(get_current_user_id)  # 只注入 ID
):
    result = get_from_submission(
        locations,
        regions,
        features,
        user_id=user_id,
        db=db
    )
```

**优势**：
- 服务层不依赖 User 模型
- 更容易测试（只需传递 int）
- 更符合依赖注入原则

## 总结

### 为什么需要 user 参数？

1. **查询用户特定数据**：
   - 用户自定义的地点简称
   - 用户提交的表单数据
   - 用户创建的自定义区域

2. **记录数据归属**：
   - 创建记录时需要 `user_id`
   - 显示提交者需要 `username`

3. **权限控制**：
   - 只能查询/修改自己的数据
   - 需要 `user.id` 进行过滤

### 当前实现的问题

- ❌ 服务层过度依赖 User 对象
- ❌ 无法充分利用依赖注入优化
- ❌ 测试困难（需要构造完整的 User 对象）

### 改进方向

- ✅ 服务层只接受必要的参数（user_id, username）
- ✅ 创建专门的依赖注入函数（get_current_user_id）
- ✅ 降低耦合，提高可测试性

### 是否需要立即改进？

**建议**：
1. **短期**：保持现状，完成当前重构
2. **中期**：逐步优化服务层接口
3. **长期**：统一使用依赖注入模式

**原因**：
- 当前重构已经消除了 13 处重复代码
- 服务层优化是更大的重构，需要单独规划
- 不影响当前的功能和性能
