# 后端API改动指南 - 统一迁移到 village_cluster_assignments 表

**日期**: 2026-02-25
**改动范围**: 4个文件，5处修改
**改动难度**: ⭐ 简单（约15分钟）

---

## 为什么要统一迁移？

### 当前问题
- 聚类分配数据存储在两个地方：
  - `village_spatial_features.spatial_cluster_id`（旧）
  - `village_cluster_assignments`（新）
- 数据冗余，难以维护
- 无法支持多版本聚类

### 统一后的优势
- ✅ 单一数据源，易于维护
- ✅ 支持多版本聚类（通过 run_id）
- ✅ 数据一致性更好
- ✅ 未来扩展更灵活

---

## 改动清单

### 需要修改的文件

| 文件 | 行数 | 改动类型 | 难度 |
|------|------|----------|------|
| `api/village/data.py` | 201-204 | 修改查询 | 简单 |
| `api/village/data.py` | 266-269 | 修改查询 | 简单 |
| `api/village/search.py` | 133-134 | 修改查询 | 简单 |
| `api/regional/aggregates_realtime.py` | 462 | 修改JOIN | 简单 |

---

## 详细改动说明

### 1. api/village/data.py - get_village_spatial_features()

**位置**: 第163-210行

**当前代码**:
```python
@router.get("/spatial-features/{village_id}")
def get_village_spatial_features(
    village_id: int,
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("village_features")

    query = """
        SELECT
            village_id,
            village_name,
            city,
            county,
            town,
            longitude,
            latitude,
            nn_distance_1,
            nn_distance_5,
            nn_distance_10,
            local_density_1km,
            local_density_5km,
            local_density_10km,
            isolation_score,
            is_isolated,
            spatial_cluster_id,    # ← 这个字段需要改
            cluster_size           # ← 这个字段需要改
        FROM village_spatial_features
        WHERE village_id = ? AND run_id = ?
    """
    result = execute_single(db, query, (str(village_id), run_id))
```

**修改后**:
```python
@router.get("/spatial-features/{village_id}")
def get_village_spatial_features(
    village_id: int,
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    clustering_version: Optional[str] = Query(
        "spatial_eps_20",  # 默认版本
        description="聚类版本ID"
    ),
    db: sqlite3.Connection = Depends(get_db)
):
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("village_features")

    query = """
        SELECT
            vsf.village_id,
            vsf.village_name,
            vsf.city,
            vsf.county,
            vsf.town,
            vsf.longitude,
            vsf.latitude,
            vsf.nn_distance_1,
            vsf.nn_distance_5,
            vsf.nn_distance_10,
            vsf.local_density_1km,
            vsf.local_density_5km,
            vsf.local_density_10km,
            vsf.isolation_score,
            vsf.is_isolated,
            vca.cluster_id as spatial_cluster_id,  # ← 从新表获取
            sc.cluster_size                         # ← 从 spatial_clusters 获取
        FROM village_spatial_features vsf
        LEFT JOIN village_cluster_assignments vca
            ON vsf.village_id = vca.village_id AND vca.run_id = ?
        LEFT JOIN spatial_clusters sc
            ON vca.run_id = sc.run_id AND vca.cluster_id = sc.cluster_id
        WHERE vsf.village_id = ? AND vsf.run_id = ?
    """
    result = execute_single(db, query, (clustering_version, str(village_id), run_id))
```

**改动说明**:
- 添加 `clustering_version` 参数（默认 "spatial_eps_20"）
- 使用 LEFT JOIN 连接 `village_cluster_assignments` 和 `spatial_clusters`
- 从新表获取 `cluster_id` 和 `cluster_size`

---

### 2. api/village/data.py - get_village_detail()

**位置**: 第266-269行

**当前代码**:
```python
# Get spatial features (has village_id column)
spatial_query = """
    SELECT *
    FROM village_spatial_features
    WHERE village_id = ? AND run_id = ?
"""
spatial_features = execute_single(db, spatial_query, (f'v_{village_id}', run_id))
```

**修改后**:
```python
# Get spatial features with clustering info
spatial_query = """
    SELECT
        vsf.*,
        vca.cluster_id as spatial_cluster_id,
        sc.cluster_size
    FROM village_spatial_features vsf
    LEFT JOIN village_cluster_assignments vca
        ON vsf.village_id = vca.village_id AND vca.run_id = 'spatial_eps_20'
    LEFT JOIN spatial_clusters sc
        ON vca.run_id = sc.run_id AND vca.cluster_id = sc.cluster_id
    WHERE vsf.village_id = ? AND vsf.run_id = ?
"""
spatial_features = execute_single(db, spatial_query, (f'v_{village_id}', run_id))
```

**改动说明**:
- 使用 LEFT JOIN 获取聚类信息
- 默认使用 'spatial_eps_20' 版本（可以改为参数）

---

### 3. api/village/search.py - search_villages()

**位置**: 第133-134行

**当前代码**:
```python
spatial_query = """
    SELECT
        knn_mean_distance,
        local_density,
        isolation_score
    FROM village_spatial_features
    WHERE run_id = ? AND village_name = ? AND city = ? AND county = ?
"""
spatial = execute_single(db, spatial_query, (run_id, village_name, city, county))
```

**修改后**:
```python
spatial_query = """
    SELECT
        vsf.knn_mean_distance,
        vsf.local_density,
        vsf.isolation_score,
        vca.cluster_id as spatial_cluster_id
    FROM village_spatial_features vsf
    LEFT JOIN village_cluster_assignments vca
        ON vsf.village_id = vca.village_id AND vca.run_id = 'spatial_eps_20'
    WHERE vsf.run_id = ? AND vsf.village_name = ? AND vsf.city = ? AND vsf.county = ?
"""
spatial = execute_single(db, spatial_query, (run_id, village_name, city, county))
```

**改动说明**:
- 添加 LEFT JOIN 获取聚类ID
- 使用默认聚类版本 'spatial_eps_20'

---

### 4. api/regional/aggregates_realtime.py - get_spatial_aggregates()

**位置**: 第462行

**当前代码**:
```python
query = """
    SELECT
        v.{column_name} as region_name,
        COUNT(*) as village_count,
        AVG(sf.local_density) as avg_density,
        STDEV(sf.local_density) as spatial_dispersion
    FROM 广东省自然村 v
    LEFT JOIN village_spatial_features sf ON v.自然村 = sf.village_name
    WHERE 1=1
"""
```

**修改后**:
```python
query = """
    SELECT
        v.{column_name} as region_name,
        COUNT(*) as village_count,
        AVG(sf.local_density) as avg_density,
        STDEV(sf.local_density) as spatial_dispersion,
        COUNT(DISTINCT vca.cluster_id) as num_clusters
    FROM 广东省自然村 v
    LEFT JOIN village_spatial_features sf ON v.自然村 = sf.village_name
    LEFT JOIN village_cluster_assignments vca
        ON sf.village_id = vca.village_id AND vca.run_id = 'spatial_eps_20'
    WHERE 1=1
"""
```

**改动说明**:
- 添加 LEFT JOIN 到 `village_cluster_assignments`
- 可选：添加 `num_clusters` 统计（每个区域有多少个聚类）

---

## 数据库结构变更

### 可选：删除冗余字段

完成API迁移后，可以删除 `village_spatial_features` 表中的冗余字段：

```sql
-- 备份表
CREATE TABLE village_spatial_features_backup AS SELECT * FROM village_spatial_features;

-- 删除冗余字段（可选，建议先测试）
-- ALTER TABLE village_spatial_features DROP COLUMN spatial_cluster_id;
-- ALTER TABLE village_spatial_features DROP COLUMN cluster_size;
```

**注意**: SQLite 不支持 DROP COLUMN，需要重建表。建议先不删除，等API稳定后再考虑。

---

## 测试清单

### 1. 单元测试

```python
# tests/test_api_village_data.py

def test_get_village_spatial_features():
    """测试获取村庄空间特征"""
    response = client.get("/villages/spatial-features/1?clustering_version=spatial_eps_20")
    assert response.status_code == 200
    data = response.json()
    assert "spatial_cluster_id" in data
    assert "cluster_size" in data

def test_get_village_spatial_features_with_hdbscan():
    """测试使用 HDBSCAN 聚类版本"""
    response = client.get("/villages/spatial-features/1?clustering_version=spatial_hdbscan_v1")
    assert response.status_code == 200
    data = response.json()
    assert "spatial_cluster_id" in data
```

### 2. 集成测试

```bash
# 测试所有受影响的端点
curl "http://localhost:5000/api/villages/spatial-features/1"
curl "http://localhost:5000/api/villages/spatial-features/1?clustering_version=spatial_hdbscan_v1"
curl "http://localhost:5000/api/villages/detail/1"
curl "http://localhost:5000/api/villages/search?name=大村"
curl "http://localhost:5000/api/regional/spatial-aggregates?region_level=city"
```

### 3. 性能测试

```python
import time

# 测试查询性能
start = time.time()
response = client.get("/villages/spatial-features/1")
duration = time.time() - start

assert duration < 0.1  # 应该在100ms内完成
```

---

## 迁移步骤

### 第1步：确保数据已填充

```bash
# 检查 village_cluster_assignments 表是否有数据
python -c "
import sqlite3
conn = sqlite3.connect('data/villages.db')
cursor = conn.cursor()
cursor.execute('SELECT run_id, COUNT(*) FROM village_cluster_assignments GROUP BY run_id')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} records')
"
```

**预期输出**:
```
spatial_eps_03: ~200,000 records
spatial_eps_05: ~220,000 records
spatial_eps_10: ~260,000 records
spatial_eps_20: ~283,000 records
spatial_hdbscan_v1: ~200,000 records
```

### 第2步：修改API代码

按照上面的改动说明，修改4个文件。

### 第3步：测试

```bash
# 启动API服务器
python api/main.py

# 运行测试
pytest tests/test_api_village_data.py -v
```

### 第4步：部署

```bash
# 提交代码
git add api/
git commit -m "refactor: 统一使用 village_cluster_assignments 表获取聚类信息"
git push

# 部署到服务器
# ... (你的部署流程)
```

---

## 回滚方案

如果出现问题，可以快速回滚：

```bash
# 1. 回滚代码
git revert HEAD

# 2. 重新部署
# ... (你的部署流程)
```

**数据不会丢失**，因为：
- `village_spatial_features` 表保持不变
- `village_cluster_assignments` 表是新增的
- 可以随时切换回旧的查询方式

---

## FAQ

### Q: 为什么要添加 clustering_version 参数？

A: 这样用户可以选择不同的聚类版本（eps_20, hdbscan_v1等），更灵活。

### Q: 默认使用哪个聚类版本？

A: 建议使用 `spatial_eps_20`（253个聚类，平均1121个村庄），这是粗粒度聚类，适合大多数场景。

### Q: LEFT JOIN 会影响性能吗？

A: 不会。`village_cluster_assignments` 表有适当的索引：
- PRIMARY KEY (run_id, village_id)
- INDEX idx_vca_village_id (village_id)

查询性能应该在 10-50ms 之间。

### Q: 如果某个村庄没有聚类分配怎么办？

A: 使用 LEFT JOIN，所以 `spatial_cluster_id` 会是 NULL。这是正常的（噪声点）。

### Q: 需要修改前端代码吗？

A: 不需要。API 返回的数据结构保持不变，只是数据来源改变了。

---

## 总结

### 改动范围
- **文件数**: 4个
- **代码行数**: 约20行
- **改动难度**: ⭐ 简单
- **预计时间**: 15分钟

### 改动收益
- ✅ 统一数据源，易于维护
- ✅ 支持多版本聚类
- ✅ 数据一致性更好
- ✅ 未来扩展更灵活

### 风险评估
- **风险等级**: 低
- **影响范围**: 4个API端点
- **回滚难度**: 简单（git revert）
- **数据安全**: 高（不删除原有数据）

---

**文档生成时间**: 2026-02-25
**作者**: Claude Code
**建议**: 统一迁移，收益大于成本
