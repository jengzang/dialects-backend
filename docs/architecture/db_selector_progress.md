# 依赖注入封装实施进度

## 已完成 ✅

### 1. 核心模块
- ✅ `app/sql/db_selector.py` - 创建依赖注入函数

### 2. 已修改的路由文件
- ✅ `app/routes/phonology.py` (5 个函数)
  - api_run_phonology_analysis
  - feature_counts
  - phonology_matrix
  - api_phonology_classification_matrix
  - feature_stats

- ✅ `app/routes/compare.py` (2 个函数)
  - compare_chars
  - compare_tones_route

## 待完成 ⏳

### 3. 剩余路由文件 (15 个函数)

#### app/routes/search.py (2 个函数)
```python
# 修改导入
from app.sql.db_selector import get_dialects_db, get_query_db

# search_chars
@router.get("/search_chars/")
async def search_chars(
    chars: List[str] = Query(...),
    locations: Optional[List[str]] = Query(None),
    regions: Optional[List[str]] = Query(None),
    region_mode: str = Query("yindian"),
    db: Session = Depends(get_db),
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db)
):
    # 移除：query_db = QUERY_DB_ADMIN if user...
    # 移除：db_path = DIALECTS_DB_ADMIN if user...
    locations_processed = match_locations_batch_all(
        locations or [],
        filter_valid_abbrs_only=True,
        exact_only=True,
        query_db=query_db,
        db=db,
        user=None  # 不再需要
    )
    result = search_characters(
        chars=chars,
        locations=locations_processed,
        regions=regions,
        db_path=dialects_db,  # 使用注入的
        region_mode=region_mode,
        query_db_path=query_db  # 使用注入的
    )

# search_tones_o - 类似修改
```

#### app/routes/new_pho.py (2 个函数)
```python
# 修改导入
from app.sql.db_selector import get_dialects_db, get_query_db

# analyze_zhonggu
@router.post("/ZhongGu")
async def analyze_zhonggu(
    payload: ZhongGuAnalysis,
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db)
):
    # 移除：db_path = DIALECTS_DB_ADMIN if user...
    # 移除：query_db = QUERY_DB_ADMIN if user...
    analysis_results = await run_in_threadpool(
        _run_dialect_analysis_sync,
        char_data_list=cached_char_result,
        locations=locations,
        regions=regions,
        features=features,
        region_mode=payload.region_mode,
        db_path_dialect=dialects_db,  # 使用注入的
        db_path_query=query_db  # 使用注入的
    )

# analyze_yinwei - 类似修改
```

#### app/routes/geo/batch_match.py (1 个函数)
```python
# 修改导入
from app.sql.db_selector import get_query_db

# batch_match
@router.get("/batch_match")
async def batch_match(
    request: Request,
    input_string: str = Query(...),
    filter_valid_abbrs_only: bool = Query(True),
    db: Session = Depends(get_db_custom),
    query_db: str = Depends(get_query_db)
):
    # 移除：query_db = QUERY_DB_ADMIN if user...
    results = match_locations_batch(
        input_string,
        filter_valid_abbrs_only,
        False,
        query_db=query_db,  # 使用注入的
        db=db,
        user=None  # 不再需要
    )
```

#### app/routes/geo/get_locs.py (1 个函数)
```python
# 修改导入
from app.sql.db_selector import get_query_db

# get_all_locs
@router.get("/get_locs/")
async def get_all_locs(
    locations: Optional[List[str]] = Query(None),
    regions: Optional[List[str]] = Query(None),
    region_mode: str = Query("yindian"),
    query_db: str = Depends(get_query_db)
):
    # 移除：query_db = QUERY_DB_ADMIN if user...
    for location in locations or []:
        matched = match_locations_batch_exact(
            location,
            query_db=query_db  # 使用注入的
        )
```

#### app/routes/geo/get_coordinates.py (1 个函数)
**注意**：这个文件比较特殊，需要保留 user 参数，因为第 62 行传递 user 给 `query_dialect_abbreviations_orm`

```python
# 修改导入
from app.sql.db_selector import get_query_db
from app.service.auth import get_current_user
from app.service.auth import User

# get_coordinates
@router.get("/get_coordinates")
async def get_coordinates(
    query: CoordinatesQuery = Depends(),
    db: Session = Depends(get_db_custom),
    db_user: Session = Depends(get_db_user),
    query_db: str = Depends(get_query_db),
    user: Optional[User] = Depends(get_current_user)  # 保留！
):
    # 移除：query_db = QUERY_DB_ADMIN if user...
    # 但保留 user 参数，因为需要传递给 query_dialect_abbreviations_orm
    for location in locations_list:
        matched = match_locations_batch_exact(
            location,
            query_db=query_db  # 使用注入的
        )

    if query.iscustom and query.region_mode == 'yindian':
        abbr1 = query_dialect_abbreviations_orm(
            db, user, regions_list, locations_list  # 需要 user
        )
```

#### app/routes/geo/get_regions.py (1 个函数)
**注意**：这个文件也需要保留 user 参数，因为传递给 `fetch_dialect_region`

```python
# 修改导入 - 保留 get_current_user
from app.service.auth import get_current_user
from app.service.auth import User

# get_regions
@router.get("/get_regions")
async def get_regions(
    input_data: Union[str, List[str]] = Query(..., alias="input_data"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)  # 保留！
):
    # 不修改，因为需要传递 user 给 fetch_dialect_region
    return fetch_dialect_region(input_data, db=db, user=user)
```

#### app/routes/user/custom_query.py (2 个函数)
**注意**：这两个函数需要保留 user 参数，因为传递给服务层

```python
# 保留 get_current_user 导入
from app.service.auth import get_current_user
from app.service.auth import User

# query_location_data
@router.get("/get_custom")
async def query_location_data(
    locations: List[str] = Query(...),
    regions: List[str] = Query(...),
    need_features: str = Query(...),
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user)  # 保留！
):
    # 不修改，因为需要传递 user 给 get_from_submission
    result = get_from_submission(
        query_params.locations,
        query_params.regions,
        query_params.need_features,
        user,  # 需要
        db
    )

# get_custom_feature - 类似，保留 user
```

#### app/routes/user/form_submit.py (2 个函数)
**注意**：这两个函数需要保留 user 参数

```python
# 保留 get_current_user 导入
from app.service.auth import get_current_user
from app.service.auth import User

# submit_form
@router.post("/submit_form")
async def submit_form(
    payload: FormData,
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user)  # 保留！
):
    # 不修改，因为需要传递 user 给 handle_form_submission
    result = handle_form_submission(payload.dict(), user, db)

# delete_form - 类似，保留 user
```

#### app/routes/user/custom_regions.py (3 个函数)
**注意**：这三个函数需要保留 user 参数，因为需要 user.id 和 user.username

```python
# 保留 get_current_user 导入
from app.service.auth import get_current_user
from app.service.auth import User

# 所有三个函数都保留 user 参数
# 因为需要 user.id, user.username 等属性
```

## 总结

### 可以完全移除 user 参数的文件 (7 个文件，14 个函数)
1. ✅ app/routes/phonology.py (5 个函数)
2. ✅ app/routes/compare.py (2 个函数)
3. ⏳ app/routes/search.py (2 个函数)
4. ⏳ app/routes/new_pho.py (2 个函数)
5. ⏳ app/routes/geo/batch_match.py (1 个函数)
6. ⏳ app/routes/geo/get_locs.py (1 个函数)

### 需要保留 user 参数的文件 (5 个文件，8 个函数)
原因：这些函数不仅需要数据库路径，还需要 user 对象本身（user.id, user.username 等）

7. ⏳ app/routes/geo/get_coordinates.py (1 个函数) - 传递给 query_dialect_abbreviations_orm
8. ⏳ app/routes/geo/get_regions.py (1 个函数) - 传递给 fetch_dialect_region
9. ⏳ app/routes/user/custom_query.py (2 个函数) - 传递给服务层
10. ⏳ app/routes/user/form_submit.py (2 个函数) - 传递给服务层
11. ⏳ app/routes/user/custom_regions.py (3 个函数) - 使用 user.id, user.username

## 改进效果

### 代码重复消除
- **之前**：22 个函数都有相同的数据库选择逻辑
- **之后**：只在 db_selector.py 中定义一次

### 维护成本降低
- **之前**：修改数据库选择逻辑需要改 22 个地方
- **之后**：只需修改 db_selector.py 一个文件

### 测试友好
- **之前**：每个函数都要测试不同用户角色
- **之后**：只需测试 db_selector.py，路由函数可以直接 mock 数据库路径

## 下一步

继续修改剩余的 6 个文件（14 个函数），完成整个重构。
