# API 功能状态报告

## 总览
- **总端点数**: 80 个
- **功能模块**: 11 个
- **状态**: 大部分正常，5 个聚类端点受影响

---

## 1. 管理模块 (Admin) - 6 个端点 ✅

**功能**: Run_ID 版本管理

| 端点 | 方法 | 功能 | 状态 |
|------|------|------|------|
| `/api/admin/run-ids/active` | GET | 获取所有活跃 run_id | ✅ |
| `/api/admin/run-ids/active/{type}` | GET | 获取特定类型的活跃 run_id | ✅ |
| `/api/admin/run-ids/available/{type}` | GET | 获取可用的 run_id 列表 | ✅ |
| `/api/admin/run-ids/metadata/{id}` | GET | 获取 run_id 元数据 | ✅ |
| `/api/admin/run-ids/refresh` | POST | 刷新 run_id 缓存 | ✅ |
| `/api/admin/run-ids/active/{type}` | PUT | 设置活跃 run_id | ✅ |

**用途**: 管理不同分析阶段的数据版本

---

## 2. 字符分析模块 (Character) - 10 个端点 ✅

**功能**: 字符频率、嵌入、倾向性、显著性分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/character/frequency/global` | 全局字符频率统计 | ✅ |
| `/api/character/frequency/regional` | 区域字符频率统计 | ✅ |
| `/api/character/tendency/by-char` | 按字符查询倾向性 | ✅ |
| `/api/character/tendency/by-region` | 按区域查询倾向性 | ✅ |
| `/api/character/embeddings/list` | 字符嵌入列表 | ✅ |
| `/api/character/embeddings/vector` | 获取字符向量 | ✅ |
| `/api/character/embeddings/similarities` | 字符相似度查询 | ✅ |
| `/api/character/significance/by-character` | 按字符查询显著性 | ✅ |
| `/api/character/significance/by-region` | 按区域查询显著性 | ✅ |
| `/api/character/significance/summary` | 显著性统计摘要 | ✅ |

**核心功能**:
- 字符使用频率分析（全局/区域）
- 倾向性分析（某字符在特定区域的相对使用倾向）
- Word2Vec 字符嵌入（100 维向量，9,209 个字符）
- 统计显著性测试（Chi-square, p-value, effect size）

---

## 3. 聚类模块 (Clustering) - 5 个端点 ⚠️

**功能**: 区域聚类分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/clustering/assignments` | 获取聚类分配结果 | ⚠️ 表已删除 |
| `/api/clustering/assignments/by-region` | 按区域查询聚类 | ⚠️ 表已删除 |
| `/api/clustering/profiles` | 聚类特征画像 | ⚠️ 表已删除 |
| `/api/clustering/metrics` | 聚类评估指标 | ⚠️ 表已删除 |
| `/api/clustering/metrics/best` | 最佳聚类参数 | ⚠️ 表已删除 |

**状态**: 这些端点依赖已删除的表（cluster_assignments, cluster_profiles, clustering_metrics）

**替代方案**: 使用计算模块的实时聚类功能
- `POST /api/compute/clustering/run` - 实时运行聚类
- `POST /api/compute/clustering/scan` - 扫描多个 k 值

---

## 4. 计算模块 (Compute) - 10 个端点 ✅

**功能**: 实时计算和探索性分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `POST /api/compute/clustering/run` | 实时聚类（KMeans/DBSCAN/GMM） | ✅ |
| `POST /api/compute/clustering/scan` | 扫描多个 k 值 | ✅ |
| `GET /api/compute/clustering/cache-stats` | 缓存统计 | ✅ |
| `DELETE /api/compute/clustering/cache` | 清除缓存 | ✅ |
| `POST /api/compute/features/extract` | 特征提取 | ✅ |
| `POST /api/compute/features/aggregate` | 特征聚合 | ✅ |
| `POST /api/compute/semantic/cooccurrence` | 语义共现分析 | ✅ |
| `POST /api/compute/semantic/network` | 语义网络构建 | ✅ |
| `POST /api/compute/subset/cluster` | 子集聚类 | ✅ |
| `POST /api/compute/subset/compare` | 子集比较 | ✅ |

**特点**:
- 实时计算（3-15 秒超时）
- 带缓存机制
- 适合探索性分析

---

## 5. 元数据模块 (Metadata) - 2 个端点 ✅

**功能**: 数据库统计信息

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/metadata/stats/overview` | 数据库概览 | ✅ |
| `/api/metadata/stats/tables` | 表统计信息 | ✅ |

**用途**: 查看数据库规模、表数量、记录数等

---

## 6. N-gram 模块 (Ngrams) - 5 个端点 ✅

**功能**: 村名模式分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/ngrams/frequency` | N-gram 频率统计 | ✅ |
| `/api/ngrams/patterns` | 模式查询 | ✅ |
| `/api/ngrams/regional` | 区域 N-gram 分布 | ✅ |
| `/api/ngrams/tendency` | N-gram 倾向性 | ✅ |
| `/api/ngrams/significance` | N-gram 显著性 | ✅ |

**数据规模**: 1,909,959 个 N-gram 模式（1-3 字）

**用途**:
- 发现高频命名模式（如"村"、"围"、"坑"）
- 分析前缀/后缀倾向性
- 区域命名习惯差异

---

## 7. 模式模块 (Patterns) - 4 个端点 ✅

**功能**: 结构化模式分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/patterns/frequency/global` | 全局模式频率 | ✅ |
| `/api/patterns/frequency/regional` | 区域模式频率 | ✅ |
| `/api/patterns/structural` | 结构模式分析 | ✅ |
| `/api/patterns/tendency` | 模式倾向性 | ✅ |

**用途**: 分析村名的结构特征（长度、组成等）

---

## 8. 区域聚合模块 (Regional) - 5 个端点 ✅ (已修复)

**功能**: 区域级统计聚合

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/regional/aggregates/city` | 城市级聚合统计 | ✅ 已修复 |
| `/api/regional/aggregates/county` | 县区级聚合统计 | ✅ 已修复 |
| `/api/regional/aggregates/town` | 乡镇级聚合统计 | ✅ 已修复 |
| `/api/regional/spatial-aggregates` | 区域空间聚合 | ✅ 已修复 |
| `/api/regional/vectors` | 区域特征向量 | ✅ |

**返回数据**:
- 村庄总数
- 平均名称长度
- 9 个语义类别的统计（山、水、聚落、方位、宗族、象征、农业、植被、基础设施）
- 每个类别的计数和百分比

**性能**: <300ms 响应时间

---

## 9. 语义模块 (Semantic) - 12 个端点 ✅

**功能**: 语义类别和组合分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/semantic/category/list` | 语义类别列表 | ✅ |
| `/api/semantic/category/tendency` | 类别倾向性 | ✅ |
| `/api/semantic/category/vtf/global` | 全局虚拟词频 | ✅ |
| `/api/semantic/category/vtf/regional` | 区域虚拟词频 | ✅ |
| `/api/semantic/labels/categories` | 标签类别统计 | ✅ |
| `/api/semantic/labels/by-category` | 按类别查询标签 | ✅ |
| `/api/semantic/labels/by-character` | 按字符查询标签 | ✅ |
| `/api/semantic/composition/patterns` | 组合模式 | ✅ |
| `/api/semantic/composition/bigrams` | 二元组合 | ✅ |
| `/api/semantic/composition/trigrams` | 三元组合 | ✅ |
| `/api/semantic/composition/pmi` | 点互信息 | ✅ |
| `/api/semantic/indices` | 语义指数 | ✅ |

**9 个语义类别**:
1. mountain (山地地形)
2. water (水系)
3. settlement (聚落)
4. direction (方位)
5. clan (宗族)
6. symbolic (象征)
7. agriculture (农业)
8. vegetation (植被)
9. infrastructure (基础设施)

**用途**:
- 分析村名的语义构成
- 发现语义组合规律
- 区域文化特征分析

---

## 10. 空间模块 (Spatial) - 8 个端点 ✅

**功能**: 空间分布和热点分析

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/spatial/hotspots` | 空间热点列表 | ✅ |
| `/api/spatial/hotspots/{id}` | 热点详情 | ✅ |
| `/api/spatial/clusters` | 空间聚类 | ✅ |
| `/api/spatial/clusters/summary` | 聚类摘要 | ✅ |
| `/api/spatial/integration` | 空间-倾向性整合 | ✅ |
| `/api/spatial/integration/by-character/{char}` | 按字符查询整合数据 | ✅ |
| `/api/spatial/integration/by-cluster/{id}` | 按聚类查询整合数据 | ✅ |
| `/api/spatial/integration/summary` | 整合数据摘要 | ✅ |

**数据**:
- 283,986 个村庄的空间特征
- 8 个空间热点（KDE 核密度估计）
- 253 个空间聚类（DBSCAN）

**用途**:
- 发现村庄密集区域
- 分析空间分布模式
- 结合倾向性分析地理-文化关联

---

## 11. 村庄查询模块 (Village) - 7 个端点 ✅

**功能**: 单个村庄的详细信息

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/village/search` | 村庄搜索 | ✅ |
| `/api/village/search/detail` | 详细搜索 | ✅ |
| `/api/village/complete/{id}` | 完整村庄信息 | ✅ |
| `/api/village/features/{id}` | 村庄特征 | ✅ |
| `/api/village/spatial-features/{id}` | 空间特征 | ✅ |
| `/api/village/semantic-structure/{id}` | 语义结构 | ✅ |
| `/api/village/ngrams/{id}` | N-gram 分解 | ✅ |

**用途**:
- 按名称/拼音/区域搜索村庄
- 查看单个村庄的全部分析结果
- 获取村庄的特征向量

---

## 状态总结

### ✅ 正常工作 (75 个端点)
- 管理模块: 6 个
- 字符分析: 10 个
- 计算模块: 10 个
- 元数据: 2 个
- N-gram: 5 个
- 模式: 4 个
- 区域聚合: 5 个 (已修复)
- 语义: 12 个
- 空间: 8 个
- 村庄查询: 7 个

### ⚠️ 受影响 (5 个端点)
- 聚类模块: 5 个（依赖已删除的表）

**替代方案**: 使用 `/api/compute/clustering/run` 进行实时聚类

---

## 核心功能亮点

### 1. 倾向性分析 (Tendency Analysis)
- 计算字符在特定区域的相对使用倾向
- 公式: `T = (regional_freq - global_freq) / global_freq × 100%`
- 揭示区域命名偏好

### 2. 语义分析
- 9 个语义类别的自动标注
- 语义组合模式发现
- 虚拟词频（VTF）计算

### 3. 空间分析
- k-NN 密度估计
- DBSCAN 空间聚类
- KDE 热点检测

### 4. 统计显著性
- Chi-square 检验
- P 值和效应量
- Z-score 标准化

### 5. 实时计算
- 灵活的探索性分析
- 缓存机制优化性能
- 支持自定义参数

---

## 性能指标

- **查询端点**: <100ms (简单查询)
- **聚合端点**: <300ms (区域聚合)
- **计算端点**: 3-15 秒 (实时计算)
- **数据规模**: 285,860 个村庄
- **数据库大小**: 5.32 GB (优化后)

---

## 使用建议

### 前端集成
1. 使用 `/api/metadata/stats/overview` 获取数据概览
2. 使用 `/api/regional/aggregates/*` 展示区域统计
3. 使用 `/api/character/tendency/*` 分析字符倾向性
4. 使用 `/api/spatial/hotspots` 展示地图热点
5. 使用 `/api/village/search` 实现搜索功能

### 数据分析
1. 使用 `/api/compute/clustering/run` 进行探索性聚类
2. 使用 `/api/semantic/composition/*` 分析语义模式
3. 使用 `/api/character/significance/*` 进行统计检验
4. 使用 `/api/spatial/integration` 结合空间和语义分析

### 性能优化
1. 使用 `limit` 参数控制返回数量
2. 使用 `run_id` 参数指定数据版本
3. 计算端点会自动缓存结果
4. 避免频繁调用实时计算端点
