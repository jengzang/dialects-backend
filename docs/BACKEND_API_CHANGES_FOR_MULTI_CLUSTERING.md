# 后端API改动指南

**日期**: 2026-02-25
**变更**: 新增 `village_cluster_assignments` 表用于存储多版本聚类数据

---

## 变更概述

### 新增表结构

```sql
CREATE TABLE village_cluster_assignments (
    run_id TEXT NOT NULL,              -- 聚类版本ID
    village_id TEXT NOT NULL,          -- 村庄ID (如 "v_1")
    cluster_id INTEGER NOT NULL,       -- 聚类ID
    cluster_size INTEGER,              -- 聚类大小
    cluster_probability REAL,          -- 聚类概率（HDBSCAN）
    created_at REAL NOT NULL,          -- 创建时间戳
    PRIMARY KEY (run_id, village_id)
);

-- 索引
CREATE INDEX idx_vca_run_id ON village_cluster_assignments(run_id);
CREATE INDEX idx_vca_cluster_id ON village_cluster_assignments(run_id, cluster_id);
CREATE INDEX idx_vca_village_id ON village_cluster_assignments(village_id);
```

### 可用的聚类版本

| run_id | 聚类数 | 平均大小 | 说明 |
|--------|--------|----------|------|
| spatial_eps_03 | 8,222 | 8.4 | 极细粒度（eps=0.03km） |
| spatial_eps_05 | 12,791 | 13.1 | 细粒度（eps=0.05km） |
| spatial_eps_10 | 4,852 | 54.2 | 中粒度（eps=0.1km） |
| spatial_eps_20 | 253 | 1,121.6 | 粗粒度（eps=20km） |
| spatial_hdbscan_v1 | 7,213 | 27.7 | 自适应密度聚类 |

---

## 后端需要的改动

### 选项1：不改动（推荐）

**适用场景**: 现有API不需要支持多版本聚类

**说明**:
- `village_spatial_features` 表保持不变
- 现有API继续使用 `village_spatial_features.spatial_cluster_id`
- 这个字段存储的是"当前/默认"版本的聚类分配
- **零改动，完全兼容**

**示例**（无需修改）:
```python
# api/village/data.py
def get_village_spatial_features(village_id: str):
    query = """
        SELECT village_id, spatial_cluster_id, cluster_size
        FROM village_spatial_features
        WHERE village_id = ?
    """
    # 继续使用，无需改动
```

---

### 选项2：支持多版本（可选）

**适用场景**: 需要让用户选择不同的聚类版本

**改动点**: 添加新的API端点或参数

#### 2.1 添加新的API端点

```python
# api/village/clustering.py (新文件)

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

@router.get("/villages/{village_id}/cluster")
def get_village_cluster(
    village_id: str,
    run_id: str = Query(
        default="spatial_eps_20",
        description="聚类版本ID"
    )
):
    """
    获取村庄的聚类分配（支持多版本）

    参数:
        village_id: 村庄ID
        run_id: 聚类版本ID (spatial_eps_20, spatial_hdbscan_v1, 等)

    返回:
        {
            "village_id": "v_1",
            "run_id": "spatial_eps_20",
            "cluster_id": 0,
            "cluster_size": 276936
        }
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT vca.village_id, vca.run_id, vca.cluster_id,
               sc.cluster_size, sc.dominant_city, sc.dominant_county
        FROM village_cluster_assignments vca
        JOIN spatial_clusters sc
            ON vca.run_id = sc.run_id AND vca.cluster_id = sc.cluster_id
        WHERE vca.village_id = ? AND vca.run_id = ?
    """, (village_id, run_id))

    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Village not found")

    return {
        "village_id": result[0],
        "run_id": result[1],
        "cluster_id": result[2],
        "cluster_size": result[3],
        "dominant_city": result[4],
        "dominant_county": result[5]
    }


@router.get("/clustering/versions")
def list_clustering_versions():
    """
    列出所有可用的聚类版本

    返回:
        [
            {
                "run_id": "spatial_eps_20",
                "n_clusters": 253,
                "avg_cluster_size": 1121.6,
                "description": "粗粒度聚类（eps=20km）"
            },
            ...
        ]
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT run_id, COUNT(*) as n_clusters, AVG(cluster_size) as avg_size
        FROM spatial_clusters
        GROUP BY run_id
        ORDER BY run_id
    """)

    versions = []
    descriptions = {
        "spatial_eps_03": "极细粒度聚类（eps=0.03km）",
        "spatial_eps_05": "细粒度聚类（eps=0.05km）",
        "spatial_eps_10": "中粒度聚类（eps=0.1km）",
        "spatial_eps_20": "粗粒度聚类（eps=20km）",
        "spatial_hdbscan_v1": "自适应密度聚类（HDBSCAN）"
    }

    for row in cursor.fetchall():
        versions.append({
            "run_id": row[0],
            "n_clusters": row[1],
            "avg_cluster_size": round(row[2], 1),
            "description": descriptions.get(row[0], "")
        })

    conn.close()
    return versions
```

#### 2.2 修改现有端点（可选）

如果想在现有端点中支持多版本，可以添加可选参数：

```python
# api/village/data.py (修改)

@router.get("/villages/{village_id}/spatial-features")
def get_village_spatial_features(
    village_id: str,
    clustering_version: Optional[str] = Query(
        default=None,
        description="聚类版本ID（可选，默认使用 village_spatial_features 中的版本）"
    )
):
    """
    获取村庄的空间特征

    如果指定 clustering_version，则从 village_cluster_assignments 表获取聚类信息
    否则使用 village_spatial_features 表中的默认版本
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if clustering_version:
        # 使用指定版本
        cursor.execute("""
            SELECT vsf.*, vca.cluster_id, sc.cluster_size
            FROM village_spatial_features vsf
            LEFT JOIN village_cluster_assignments vca
                ON vsf.village_id = vca.village_id AND vca.run_id = ?
            LEFT JOIN spatial_clusters sc
                ON vca.run_id = sc.run_id AND vca.cluster_id = sc.cluster_id
            WHERE vsf.village_id = ?
        """, (clustering_version, village_id))
    else:
        # 使用默认版本
        cursor.execute("""
            SELECT * FROM village_spatial_features
            WHERE village_id = ?
        """, (village_id,))

    result = cursor.fetchone()
    conn.close()

    # ... 返回结果
```

---

## 数据迁移

### 当前状态

- `village_spatial_features.spatial_cluster_id` 存储的是 `spatial_eps_20` 的数据
- `village_cluster_assignments` 表已创建并迁移了 `spatial_eps_20` 的数据

### 需要执行的脚本

```bash
# 1. 填充所有聚类版本的数据（可选，如果需要其他版本）
python scripts/maintenance/populate_village_cluster_assignments.py

# 注意：这个脚本会重新运行 DBSCAN，需要较长时间（约5-10分钟）
```

---

## 查询示例

### 查询村庄的聚类分配（特定版本）

```sql
SELECT vca.village_id, vca.cluster_id, sc.cluster_size,
       sc.dominant_city, sc.dominant_county
FROM village_cluster_assignments vca
JOIN spatial_clusters sc
    ON vca.run_id = sc.run_id AND vca.cluster_id = sc.cluster_id
WHERE vca.village_id = 'v_1'
  AND vca.run_id = 'spatial_hdbscan_v1';
```

### 查询某个聚类中的所有村庄（特定版本）

```sql
SELECT vca.village_id, vsf.village_name, vsf.city, vsf.county
FROM village_cluster_assignments vca
JOIN village_spatial_features vsf ON vca.village_id = vsf.village_id
WHERE vca.run_id = 'spatial_eps_20'
  AND vca.cluster_id = 0
LIMIT 100;
```

### 统计每个聚类的村庄数（特定版本）

```sql
SELECT cluster_id, COUNT(*) as village_count
FROM village_cluster_assignments
WHERE run_id = 'spatial_hdbscan_v1'
GROUP BY cluster_id
ORDER BY village_count DESC;
```

---

## 性能考虑

### 索引已创建

- `idx_vca_run_id`: 按 run_id 查询
- `idx_vca_cluster_id`: 按 (run_id, cluster_id) 查询
- `idx_vca_village_id`: 按 village_id 查询

### 查询性能

- 单村庄查询：O(1) - 使用主键索引
- 聚类内村庄查询：O(n) - 使用复合索引，n 为聚类大小
- JOIN 操作：高效，因为有适当的索引

---

## 兼容性保证

### 向后兼容

- ✅ 现有API无需改动
- ✅ `village_spatial_features` 表保持不变
- ✅ 现有查询继续工作

### 前向兼容

- ✅ 可以随时添加新的聚类版本
- ✅ 不影响现有数据
- ✅ 新旧API可以共存

---

## 总结

### 必须做的改动

**无！** 如果不需要支持多版本聚类，后端API完全不需要改动。

### 可选的改动

如果需要支持多版本聚类：
1. 添加新的API端点 `/villages/{village_id}/cluster?run_id=xxx`
2. 添加聚类版本列表端点 `/clustering/versions`
3. （可选）在现有端点中添加 `clustering_version` 参数

### 推荐做法

1. **短期**：保持现有API不变，零改动
2. **中期**：添加新的API端点支持多版本（不影响现有API）
3. **长期**：根据用户需求决定是否在现有端点中添加版本参数

---

**文档生成时间**: 2026-02-25
**作者**: Claude Code
