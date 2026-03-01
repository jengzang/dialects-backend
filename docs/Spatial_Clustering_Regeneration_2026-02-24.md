# 空间聚类重新生成 - 2026-02-24

## 背景

原有空间聚类存在严重问题：
- DBSCAN eps=2.0km 参数过大
- Cluster 0 包含 97.1% 的村庄（276,936 个）
- 其他 252 个聚类仅包含 2.9% 的村庄
- 聚类结果缺乏实用价值

## 修复方案

### 生成 3 个不同粒度的聚类版本

| 版本 | eps | 预期聚类数 | 噪声点比例 | 最大聚类占比 | 适用场景 |
|------|-----|-----------|-----------|-------------|---------|
| `spatial_eps_03` | 0.3km | 5,000-10,000 | 30-40% | <5% | 精细空间分析，村庄级别聚类 |
| `spatial_eps_05` | 0.5km | 1,000-3,000 | 15-25% | <10% | **默认推荐**，平衡粒度 |
| `spatial_eps_10` | 1.0km | 500-1,000 | 5-15% | <20% | 区域级别宏观分析 |

### 执行时间线

- **开始时间**: 2026-02-24 21:45
- **预计完成**: 2026-02-24 22:15 (30分钟)
- **数据验证**: 2026-02-24 22:30
- **API 测试**: 2026-02-24 22:45

## API 测试计划

### 1. 测试聚类列表端点

```bash
# 测试默认版本 (spatial_eps_05)
curl "http://localhost:5000/api/villages/spatial/clusters"

# 测试细粒度版本
curl "http://localhost:5000/api/villages/spatial/clusters?run_id=spatial_eps_03"

# 测试粗粒度版本
curl "http://localhost:5000/api/villages/spatial/clusters?run_id=spatial_eps_10"

# 过滤大聚类
curl "http://localhost:5000/api/villages/spatial/clusters?min_size=100"
```

### 2. 测试聚类汇总端点

```bash
# 获取聚类统计
curl "http://localhost:5000/api/villages/spatial/clusters/summary"

# 不同版本的统计对比
curl "http://localhost:5000/api/villages/spatial/clusters/summary?run_id=spatial_eps_03"
curl "http://localhost:5000/api/villages/spatial/clusters/summary?run_id=spatial_eps_05"
curl "http://localhost:5000/api/villages/spatial/clusters/summary?run_id=spatial_eps_10"
```

### 3. 测试空间热点端点

```bash
# 获取热点列表
curl "http://localhost:5000/api/villages/spatial/hotspots"

# 过滤高密度热点
curl "http://localhost:5000/api/villages/spatial/hotspots?min_density=0.5&min_village_count=50"
```

### 4. 测试空间-倾向性整合端点

```bash
# 获取整合分析结果
curl "http://localhost:5000/api/villages/spatial/integration"

# 按字符查询
curl "http://localhost:5000/api/villages/spatial/integration/by-character/水"

# 按聚类查询
curl "http://localhost:5000/api/villages/spatial/integration/by-cluster/1"

# 获取汇总统计
curl "http://localhost:5000/api/villages/spatial/integration/summary"
```

## 验证标准

### 聚类质量指标

1. **聚类分布均匀性**
   - 最大聚类占比 < 20%
   - 前 10 大聚类占比 < 50%
   - 聚类大小标准差合理

2. **噪声点比例**
   - eps=0.3km: 30-40% (可接受，精细聚类)
   - eps=0.5km: 15-25% (理想)
   - eps=1.0km: 5-15% (较低)

3. **聚类数量**
   - eps=0.3km: 5,000-10,000 个聚类
   - eps=0.5km: 1,000-3,000 个聚类
   - eps=1.0km: 500-1,000 个聚类

4. **空间连续性**
   - 同一聚类的村庄地理位置相近
   - 聚类边界清晰
   - 无明显的跨区域聚类

### API 响应验证

1. **数据完整性**
   - 所有聚类都有 centroid_lon, centroid_lat
   - cluster_size 与实际村庄数匹配
   - avg_distance_km 合理（< eps）

2. **查询性能**
   - 聚类列表查询 < 1s
   - 汇总统计查询 < 2s
   - 整合分析查询 < 3s

3. **数据一致性**
   - cluster_assignments 与 spatial_clusters 数据一致
   - spatial_tendency_integration 引用的 cluster_id 都存在

## 预期改进

### 当前问题
- ❌ Cluster 0 占 97.1%，聚类无意义
- ❌ 只有 253 个聚类，粒度太粗
- ❌ 无法进行精细的空间分析

### 改进后
- ✅ 最大聚类占比 < 20%
- ✅ 生成数千个有意义的聚类
- ✅ 支持多粒度空间分析
- ✅ 提供 3 个版本供不同场景使用

## 后续工作

### 本周内
1. ✅ 空间聚类重新生成（进行中）
2. ⏳ structural_patterns 扩展到 n=3, n=4
3. ⏳ semantic_bigrams 扩展（50+ 类别）

### 下周
4. ⏳ regional_ngram_frequency 添加 run_id

## 相关文件

- API 实现: `app/tools/VillagesML/spatial/hotspots.py`
- API 实现: `app/tools/VillagesML/spatial/integration.py`
- 数据库表: `spatial_clusters`, `cluster_assignments`, `spatial_hotspots`, `spatial_tendency_integration`
- Run ID 管理: `app/tools/VillagesML/run_id_manager.py`

## 联系人

- 后端开发: [你的名字]
- 数据分析: [数据分析同事]
- 完成时间: 预计 2026-02-24 22:15
