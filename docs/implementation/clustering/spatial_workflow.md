# 空间聚类数据生成工作流程

**更新日期**: 2026-02-25
**状态**: ✅ 已更新为自动写入 village_cluster_assignments 表

---

## 新的工作流程

### 1. 生成 HDBSCAN 聚类

```bash
python scripts/core/run_hdbscan_clustering.py \
    --run-id spatial_hdbscan_v1 \
    --min-cluster-size 10 \
    --min-samples 5
```

**自动完成**：
- ✅ 写入 `spatial_clusters` 表（聚类元数据）
- ✅ 写入 `village_cluster_assignments` 表（村庄-聚类分配）
- ✅ 包含聚类概率信息

### 2. 生成 DBSCAN 聚类（不同 eps 值）

目前需要使用填充脚本：

```bash
python scripts/maintenance/populate_village_cluster_assignments.py
```

这个脚本会生成：
- spatial_eps_03 (eps=0.03km)
- spatial_eps_05 (eps=0.05km)
- spatial_eps_10 (eps=0.1km)
- spatial_eps_20 (eps=20km)

**TODO**: 创建独立的 DBSCAN 生成脚本，类似 HDBSCAN

### 3. 运行空间-倾向性整合分析

```bash
# 修改脚本中的 SPATIAL_RUN_ID 变量
# 然后运行
python scripts/maintenance/regenerate_spatial_tendency_integration.py
```

支持的 run_id:
- spatial_eps_03
- spatial_eps_05
- spatial_eps_10
- spatial_eps_20
- spatial_hdbscan_v1

---

## 数据表关系

```
广东省自然村_预处理 (285,860 villages)
    ↓
    ├─→ spatial_clusters (聚类元数据)
    │   - run_id, cluster_id, cluster_size, centroid, etc.
    │   - 每个 run_id 有多个聚类
    │
    └─→ village_cluster_assignments (村庄-聚类分配)
        - run_id, village_id, cluster_id, cluster_probability
        - 每个 (run_id, village_id) 唯一
        ↓
spatial_tendency_integration (空间-倾向性整合)
    - 基于 village_cluster_assignments 计算
    - 分析字符在不同聚类中的倾向性
```

---

## 已更新的脚本

### ✅ run_hdbscan_clustering.py

**修改内容**：
- 添加了写入 `village_cluster_assignments` 表的逻辑
- 包含聚类概率信息
- 自动删除旧数据（如果 run_id 已存在）

**关键代码**：
```python
# 写入村庄聚类分配
village_assignments = []
for village_id, cluster_id, prob in zip(coords_df['village_id'], labels, probabilities):
    if cluster_id >= 0:  # 只存储非噪声点
        village_assignments.append({
            'run_id': run_id,
            'village_id': village_id,
            'cluster_id': int(cluster_id),
            'cluster_probability': float(prob),
            'created_at': time.time()
        })

# 删除旧数据
cursor.execute('DELETE FROM village_cluster_assignments WHERE run_id = ?', (run_id,))

# 写入新数据
assignments_df.to_sql('village_cluster_assignments', conn, if_exists='append', index=False)
```

### ✅ regenerate_spatial_tendency_integration.py

**修改内容**：
- 从 `village_cluster_assignments` 表读取数据（而不是 `village_spatial_features`）
- 支持通过 `SPATIAL_RUN_ID` 变量选择聚类版本

**关键代码**：
```python
# Step 4: 获取每个聚类中的村庄
cursor.execute('''
    SELECT cluster_id, village_id
    FROM village_cluster_assignments
    WHERE run_id = ?
''', (SPATIAL_RUN_ID,))
```

---

## 待创建的脚本

### TODO: run_dbscan_clustering.py

创建一个通用的 DBSCAN 聚类脚本：

```python
#!/usr/bin/env python3
"""
运行 DBSCAN 空间聚类

用法:
    python scripts/core/run_dbscan_clustering.py --eps 20 --min-samples 5
"""

import argparse
import sqlite3
import numpy as np
from sklearn.cluster import DBSCAN

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--eps', type=float, required=True, help='eps 参数（公里）')
    parser.add_argument('--min-samples', type=int, default=5)
    parser.add_argument('--run-id', help='Run ID (默认: spatial_eps_{eps})')

    args = parser.parse_args()

    # 生成 run_id
    if not args.run_id:
        eps_str = str(args.eps).replace('.', '')
        args.run_id = f'spatial_eps_{eps_str}'

    # 加载坐标
    # 运行 DBSCAN
    # 写入 spatial_clusters
    # 写入 village_cluster_assignments

    # ... (实现细节)
```

---

## 数据验证

### 检查所有版本的数据

```sql
SELECT run_id, COUNT(*) as village_count
FROM village_cluster_assignments
GROUP BY run_id
ORDER BY run_id;
```

**预期结果**：
```
spatial_eps_03      | ~200,000
spatial_eps_05      | ~220,000
spatial_eps_10      | ~260,000
spatial_eps_20      | ~283,000
spatial_hdbscan_v1  | ~200,000
```

### 检查聚类元数据

```sql
SELECT run_id, COUNT(*) as n_clusters, AVG(cluster_size) as avg_size
FROM spatial_clusters
GROUP BY run_id;
```

---

## 迁移说明

### 从旧系统迁移

如果你有旧的 `village_spatial_features.spatial_cluster_id` 数据：

1. **识别版本**：
   ```sql
   SELECT COUNT(DISTINCT spatial_cluster_id) FROM village_spatial_features;
   ```
   - 253 → spatial_eps_20
   - 7213 → spatial_hdbscan_v1
   - 等等

2. **迁移数据**：
   ```sql
   INSERT INTO village_cluster_assignments (run_id, village_id, cluster_id, created_at)
   SELECT 'spatial_eps_20', village_id, spatial_cluster_id, strftime('%s', 'now')
   FROM village_spatial_features
   WHERE spatial_cluster_id >= 0;
   ```

3. **验证**：
   ```sql
   SELECT COUNT(*) FROM village_cluster_assignments WHERE run_id = 'spatial_eps_20';
   ```

---

## 常见问题

### Q: 为什么不直接更新 village_spatial_features 表？

A: 因为 `village_spatial_features` 表没有 `run_id` 字段，只能存储一个版本的聚类分配。新的 `village_cluster_assignments` 表支持多版本。

### Q: 旧的 API 会受影响吗？

A: 不会。`village_spatial_features` 表保持不变，旧的 API 继续工作。

### Q: 如何选择使用哪个聚类版本？

A: 在 `regenerate_spatial_tendency_integration.py` 脚本中修改 `SPATIAL_RUN_ID` 变量。

### Q: 可以删除 village_spatial_features.spatial_cluster_id 吗？

A: 不建议。保留它作为"默认版本"，供现有 API 使用。

---

**文档生成时间**: 2026-02-25
**维护者**: Claude Code
