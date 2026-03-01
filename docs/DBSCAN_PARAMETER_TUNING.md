# DBSCAN参数调优指南

## 问题描述

当使用DBSCAN算法对21个城市进行聚类时,所有区域都被标记为噪声点(cluster_id=-1),没有形成任何有效聚类。

## 原因分析

### 原始硬编码参数
```python
DBSCAN(eps=0.5, min_samples=5)
```

### 为什么失败
1. **数据规模小**: 只有21个城市
2. **维度较高**: 11个特征(9个语义 + 1个形态 + 1个多样性)
3. **预处理影响**: 标准化和PCA变换后,点之间距离发生变化
4. **参数过严**:
   - `eps=0.5` 邻域半径太小
   - `min_samples=5` 对于21个样本来说要求太高(需要24%的样本在邻域内)

## 解决方案

### 1. 参数可配置化

添加了`DBSCANConfig`配置类:

```python
class DBSCANConfig(BaseModel):
    eps: float = Field(0.5, gt=0, le=10, description="邻域半径")
    min_samples: int = Field(5, ge=1, le=20, description="最小样本数")
```

### 2. 自动参数调整

对于小数据集(< 30个样本),系统会自动调整参数:

```python
if n_samples < 30 and eps == 0.5 and min_samples == 5:
    eps = 1.5  # 增大邻域半径
    min_samples = max(2, n_samples // 10)  # 降低最小样本数
```

## API使用示例

### 方式1: 使用自动调整(推荐)

不指定`dbscan_config`,系统会自动为小数据集调整参数:

```json
{
  "algorithm": "dbscan",
  "region_level": "city",
  "features": {
    "use_semantic": true,
    "use_morphology": true,
    "use_diversity": true
  },
  "preprocessing": {
    "use_pca": true,
    "pca_n_components": 50,
    "standardize": true
  },
  "random_state": 42
}
```

对于21个城市,自动调整为: `eps=1.5, min_samples=2`

### 方式2: 手动指定参数

```json
{
  "algorithm": "dbscan",
  "region_level": "city",
  "dbscan_config": {
    "eps": 2.0,
    "min_samples": 3
  },
  "features": {
    "use_semantic": true,
    "use_morphology": true,
    "use_diversity": true
  },
  "preprocessing": {
    "use_pca": true,
    "pca_n_components": 50,
    "standardize": true
  },
  "random_state": 42
}
```

## 参数调优建议

### 根据数据规模选择参数

| 样本数 | 推荐eps | 推荐min_samples | 说明 |
|--------|---------|-----------------|------|
| < 30   | 1.5-2.5 | 2-3             | 小数据集,参数要宽松 |
| 30-100 | 1.0-2.0 | 3-5             | 中等数据集 |
| > 100  | 0.5-1.5 | 5-10            | 大数据集,可以更严格 |

### 调优策略

1. **先看数据分布**: 使用PCA降维到2D可视化,观察点的分布
2. **从宽松开始**: 先用较大的eps和较小的min_samples
3. **逐步收紧**: 如果聚类太少,逐步减小eps或增大min_samples
4. **评估指标**: 关注噪声点比例,通常应该 < 20%

### 常见问题

**Q: 所有点都是噪声怎么办?**
- 增大`eps`值(如从0.5增到1.5-2.0)
- 减小`min_samples`(如从5减到2-3)

**Q: 只有一个大聚类怎么办?**
- 减小`eps`值
- 增大`min_samples`

**Q: DBSCAN vs KMeans如何选择?**
- 数据有明显密度差异 → DBSCAN
- 数据分布均匀,需要固定数量的聚类 → KMeans
- 小数据集(< 50) → 优先考虑KMeans

## 技术细节

### 修改的文件

1. `app/tools/VillagesML/compute/validators.py`
   - 添加`DBSCANConfig`类
   - 在`ClusteringParams`中添加`dbscan_config`字段

2. `app/tools/VillagesML/compute/engine.py`
   - 修改DBSCAN聚类逻辑
   - 添加自动参数调整
   - 改进日志输出(显示聚类数和噪声点数)

### 向后兼容性

- 不指定`dbscan_config`时使用默认值
- 小数据集会自动触发参数调整
- 不影响现有API调用
