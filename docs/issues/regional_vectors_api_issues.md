# Regional Vectors API 问题分析报告

## 执行时间
2026-03-02

## 问题概述

在检查 `/api/villages/regional/vectors/compare` 端点时，发现 `aggregates_realtime.py` 文件中存在多个**重名区域歧义问题**，这些问题会导致查询结果不准确。

## 发现的问题

### 🔴 严重问题 1: `get_semantic_vector_by_hierarchy()` 函数（第751行）

**问题描述：**
该函数虽然接收了完整的层级参数（city, county, township），但在查询 `semantic_indices` 表时**只使用了 `region_name`**，没有使用层级参数进行精确匹配。

**当前代码（错误）：**
```python
query = """
    SELECT category, raw_intensity
    FROM semantic_indices
    WHERE region_name = ? AND region_level = ? AND run_id = ?
    ORDER BY category
"""
rows = execute_query(db, query, (region_name, level, run_id))
```

**影响：**
- 如果有重名区域（如广州天河区龙洞街道 vs 深圳龙岗区龙洞街道），会返回错误的数据
- `/vectors/compare` 端点会比较错误的区域

**修复方案：**
```python
query = """
    SELECT category, raw_intensity
    FROM semantic_indices
    WHERE region_level = ? AND run_id = ?
"""
params = [level, run_id]

# 添加层级过滤条件
if city is not None:
    query += " AND city = ?"
    params.append(city)
if county is not None:
    query += " AND county = ?"
    params.append(county)
elif city is not None and level == 'township':
    # Handle 东莞市/中山市 (no county level)
    query += " AND (county IS NULL OR county = '')"
if township is not None:
    query += " AND township = ?"
    params.append(township)

query += " ORDER BY category"
rows = execute_query(db, query, tuple(params))
```

---

### 🔴 严重问题 2: `/vectors` 端点（第491行）

**问题描述：**
该端点在查询 `semantic_indices` 表时使用 `region_name IN (...)` 方式，存在两个问题：

1. **第619-626行**：使用字典 `region_hierarchy_map` 存储层级信息，key 是 `region_name`。如果有重名区域，后面的会覆盖前面的！
2. **第637行**：查询时只用 `region_name IN (...)`，如果表中有重名数据，会返回所有同名区域的数据。

**当前代码（错误）：**
```python
# 构建 region_name 到层级信息的映射
region_hierarchy_map = {
    row['region_name']: {  # ❌ 重名会覆盖！
        'city': row['city'],
        'county': row['county'],
        'township': row['township']
    }
    for row in hierarchy_rows
}

# 查询 semantic_indices
semantic_query = f"""
    SELECT region_name, category, raw_intensity, village_count
    FROM semantic_indices
    WHERE run_id = ? AND region_level = ? AND region_name IN ({placeholders})
    ORDER BY region_name, category
"""  # ❌ 只用 region_name，会返回所有同名区域！
```

**影响：**
- 如果查询包含重名区域，会返回错误的向量数据
- 层级信息会丢失（被覆盖）

**修复方案：**
改用列表存储层级信息，并为每个区域单独查询（使用完整层级参数）：

```python
# 构建层级信息列表（支持重名区域）
hierarchy_list = []
for row in hierarchy_rows:
    hierarchy_list.append({
        'region_name': row['region_name'],
        'city': row['city'],
        'county': row['county'],
        'township': row['township']
    })

# 为每个区域单独查询（使用层级参数）
results = []
for hierarchy in hierarchy_list:
    semantic_query = """
        SELECT region_name, city, county, township, category, raw_intensity, village_count
        FROM semantic_indices
        WHERE run_id = ? AND region_level = ?
    """
    semantic_params = [run_id, level]

    # 添加层级过滤条件
    if hierarchy['city'] is not None:
        semantic_query += " AND city = ?"
        semantic_params.append(hierarchy['city'])
    if hierarchy['county'] is not None:
        semantic_query += " AND county = ?"
        semantic_params.append(hierarchy['county'])
    elif hierarchy['city'] is not None and level == 'township':
        semantic_query += " AND (county IS NULL OR county = '')"
    if hierarchy['township'] is not None:
        semantic_query += " AND township = ?"
        semantic_params.append(hierarchy['township'])

    semantic_rows = execute_query(db, semantic_query, tuple(semantic_params))
    # ... 处理结果
```

---

### 🟡 中等问题 3: `compute_city_aggregates()` 函数（第29行）

**问题描述：**
该函数参数名为 `city_name`，但在查询 `semantic_indices` 时使用 `region_name` 字段，没有使用 `city` 字段。

**当前代码（不一致）：**
```python
def compute_city_aggregates(
    db: sqlite3.Connection,
    city_name: Optional[str] = None,  # 参数名是 city_name
    run_id: Optional[str] = None
):
    # ...
    query_semantic = """
        SELECT region_name as city, category, raw_intensity
        FROM semantic_indices
        WHERE region_level = 'city' AND run_id = ?
    """
    if city_name is not None:
        query_semantic += " AND region_name = ?"  # 使用 region_name 字段
        params_semantic.append(city_name)
```

**影响：**
- 虽然市级名称通常不重名，但不符合统一的层级查询规范
- 与其他15个已修复的端点不一致

**修复方案：**
```python
def compute_city_aggregates(
    db: sqlite3.Connection,
    city: Optional[str] = None,  # 改为 city
    run_id: Optional[str] = None
):
    # ...
    query_semantic = """
        SELECT city, category, raw_intensity
        FROM semantic_indices
        WHERE region_level = 'city' AND run_id = ?
    """
    if city is not None:
        query_semantic += " AND city = ?"  # 使用 city 字段
        params_semantic.append(city)
```

---

### 🟡 中等问题 4: `compute_county_aggregates()` 函数（第154行）

**问题描述：**
类似问题 3，使用 `region_name` 而不是 `city/county` 字段。

**修复方案：**
参考之前修复的版本（已在 Phase 1 中修复，但被还原了）。

---

### 🟡 中等问题 5: `get_town_aggregates()` 端点（第294行）

**问题描述：**
类似问题 3 和 4，使用 `region_name` 而不是层级字段。

**修复方案：**
参考之前修复的版本（已在 Phase 1 中修复，但被还原了）。

---

## 问题根源

**核心问题：** `semantic_indices` 表虽然有 `city`, `county`, `township` 列，但代码中仍然使用 `region_name` 进行查询，导致无法区分重名区域。

**为什么会出现这个问题：**
1. 代码是在数据表添加层级列之前编写的
2. 后来数据团队添加了层级列，但代码没有相应更新
3. 用户"根据本地缓存还原"，覆盖了之前的修复

---

## 影响范围

### 受影响的端点

1. **`POST /api/villages/regional/vectors/compare`** - 🔴 严重
   - 会比较错误的区域
   - 用户报告的 405 错误已解决，但功能有 bug

2. **`GET /api/villages/regional/vectors`** - 🔴 严重
   - 返回错误的向量数据
   - 层级信息可能丢失

3. **`POST /api/villages/regional/vectors/compare/batch`** - 🔴 严重
   - 依赖 `get_multiple_vectors()`，会受问题 1 影响

4. **`POST /api/villages/regional/vectors/reduce`** - 🔴 严重
   - 依赖 `get_multiple_vectors()`，会受问题 1 影响

5. **`POST /api/villages/regional/vectors/cluster`** - 🔴 严重
   - 依赖 `get_multiple_vectors()`，会受问题 1 影响

6. **`GET /api/villages/regional/aggregates/city`** - 🟡 中等
   - 市级名称通常不重名，但不符合规范

7. **`GET /api/villages/regional/aggregates/county`** - 🟡 中等
   - 县级名称在省内唯一，但不符合规范

8. **`GET /api/villages/regional/aggregates/town`** - 🟡 中等
   - 乡镇级有重名问题

---

## 修复优先级

### P0 - 立即修复（严重影响功能）
1. `get_semantic_vector_by_hierarchy()` 函数
2. `/vectors` 端点

### P1 - 尽快修复（影响一致性）
3. `compute_city_aggregates()` 函数
4. `compute_county_aggregates()` 函数
5. `get_town_aggregates()` 端点

---

## 与之前修复的关系

**之前已修复的 15 个端点（Phase 1 + Phase 2）：**
- 这些端点已经正确使用层级参数
- 但 `aggregates_realtime.py` 文件被用户还原，修复丢失

**需要重新应用的修复：**
1. Phase 1 的 6 个端点修复（aggregates_realtime.py 中的 3 个）
2. Phase 2 的东莞市/中山市支持
3. 新发现的 2 个严重问题

---

## 建议

1. **立即修复** P0 问题（`get_semantic_vector_by_hierarchy()` 和 `/vectors` 端点）
2. **重新应用** Phase 1 和 Phase 2 的修复
3. **添加测试用例** 验证重名区域的处理
4. **代码审查** 确保所有查询 `semantic_indices` 的地方都使用层级参数

---

## 测试建议

### 测试用例 1: 重名乡镇比较
```bash
POST /api/villages/regional/vectors/compare
{
  "level1": "township",
  "city1": "广州市",
  "county1": "天河区",
  "township1": "龙洞街道",
  "level2": "township",
  "city2": "深圳市",
  "county2": "龙岗区",
  "township2": "龙洞街道"
}
```

**预期结果：** 返回两个不同区域的比较结果

### 测试用例 2: 批量查询包含重名
```bash
GET /api/villages/regional/vectors?level=township&limit=100
```

**预期结果：**
- 如果结果中有重名乡镇，每个应该有完整的层级信息（city, county, township）
- 不应该有层级信息丢失或覆盖的情况

---

## 总结

`aggregates_realtime.py` 文件中存在多个严重的重名区域歧义问题，需要立即修复。这些问题会导致：
- 向量比较功能返回错误结果
- 批量操作处理错误的区域
- 数据不一致

建议立即修复 P0 问题，并重新应用之前的 Phase 1 和 Phase 2 修复。
