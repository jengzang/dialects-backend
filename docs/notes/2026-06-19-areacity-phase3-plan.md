# AreaCity 第三阶段优化计划

更新时间：2026-06-19

## 1. 目标

第三阶段不再解决“有没有查询服务”，而是解决“查询服务如何进一步工程化和优化”。

第二阶段已经完成：
- 第一阶段 WGS84 GeoJSON -> 第二阶段运行时索引资产
- 纯 Python 查询引擎
- FastAPI 接口挂载
- 本地 API 级验证

第三阶段的目标是：
- 提升查询性能
- 降低大面几何的读取与判定成本
- 让资产格式与查询模型更接近稳定生产形态
- 为未来前端地图交互、批量查询、缓存与观测能力打基础

## 2. 当前瓶颈判断

### 2.1 subgeometry 仍过粗
当前 `build_lowmem_index.py` 虽然使用了 `subgeometry` 概念，但基本仍是：
- 一个 feature -> 一个 subgeometry

问题：
- 大 polygon 的 bbox 很大，候选会偏多
- geometry query / tolerance query 仍可能加载较大的完整几何

### 2.2 grid_index 仍然偏粗
当前：
- `grid_factor = 100`
- 经度/纬度按 0.01 度粒度入格

问题：
- 对于边界复杂地区，单格命中仍可能很多
- 没有按 deep 做差异化索引

### 2.3 geometry 存储还是 geojson-bytes
优点：
- 简单
- 纯 Python 容易落地

问题：
- 解码成本高于更紧凑的二进制表达
- 对未来更复杂的几何操作不够友好

### 2.4 缓存还比较原始
当前：
- `_geometry_cache` 为进程内 dict

问题：
- 无上限
- 无命中统计
- 无淘汰策略

### 2.5 观测性较弱
当前有 `QueryStats`，但较基础。
问题：
- 看不到 cache hit/miss
- 看不到 grid candidate 缩小效果
- 看不到按 deep 的命中成本

## 3. 第三阶段建议拆分

建议把第三阶段拆为 5 个子阶段。

### Phase 3.1 真正的子几何切分
目标：
- 将大几何切成更细的可索引单元

建议做法：
1. 对 `Polygon`：
   - 先保持 outer ring 与 hole 关联
   - 以 bbox / 局部片段为单位分块
2. 对 `MultiPolygon`：
   - 先拆成 polygon-level part
   - 再对大 polygon 做二次切分
3. 在 index 中记录：
   - `sub_id`
   - `feature_id`
   - `part_kind`
   - `bbox`
   - `geom_offset`
   - `geom_length`
   - `source_geometry_type`

收益：
- point / geometry 查询的候选更少
- 容差查询不必总是加载整个行政区 polygon

注意：
- 切分后按 `boundary/by-id` 返回时，需要重组
- 需要保证 geometry query 的正确性不因切分丢失 hole 语义

### Phase 3.2 改进网格索引
目标：
- 减少 bbox 候选爆炸

建议做法：
1. 把 `grid_factor` 参数化，并做试验：
   - 100
   - 200
   - 500
2. 增加构建统计输出：
   - 每个 cell 命中 subgeometry 数量分布
   - 最大 cell 热点
   - 平均每条 subgeometry 落入多少 cell
3. 可考虑做分层索引：
   - level0 单独索引
   - level1 单独索引
   - level2 单独索引

收益：
- 查询阶段更容易先粗后细
- 可为不同 deep 定制不同策略

### Phase 3.3 缓存与资源管理
目标：
- 避免进程内 geometry cache 无限制增长

建议做法：
1. 把 `_geometry_cache` 改为 LRU
2. 增加可配置上限，例如：
   - 缓存最大条数
   - 估算最大字节数
3. 增加统计：
   - cache_hit_count
   - cache_miss_count
4. 在应用 shutdown 时显式关闭 geometry store

收益：
- 更稳定
- 更容易做容量规划

### Phase 3.4 观测与压测
目标：
- 把当前“能用”提升为“可量化”

建议做法：
1. 增加基准脚本：
   - 常见城市点查
   - 海岸线附近容差点查
   - bbox 几何查询
2. 记录：
   - 候选数
   - io 读取次数
   - geometry decode 次数
   - cache 命中率
   - 单次耗时
3. 输出压测报告

建议新增脚本：
- `scripts/geo/benchmark_geo_queries.py`
- `scripts/geo/report_geo_index_stats.py`

### Phase 3.5 可选高性能加速层
目标：
- 保持纯 Python 基线不变的同时，允许未来按环境启用增强

建议方向：
1. shapely 作为可选 backend
2. 更强空间索引作为可选 backend
3. 在 `config.py` 中引入模式：
   - `pure-python`
   - `shapely-accelerated`

原则：
- 默认仍然可在无额外 geo C 扩展的环境中运行
- 加速层只作为增强，不改变 API 契约

## 4. 第三阶段推荐实施顺序

推荐优先级如下：

### P0
1. 子几何真正切分
2. shutdown 时关闭 geometry store
3. geometry cache 增加上限与统计

### P1
4. grid_factor 调参与统计报告
5. benchmark 脚本
6. 查询统计增强

### P2
7. boundary 重组为更稳定的标准 geometry 形态
8. 可选 shapely 加速层

## 5. 推荐新增文件

### 脚本
- `scripts/geo/report_geo_index_stats.py`
- `scripts/geo/benchmark_geo_queries.py`
- `scripts/geo/rebuild_subgeometry_index.py`（如果单独拆出切分逻辑）

### 引擎
- `app/geo_query/cache.py`
  - 封装 LRU cache
- `app/geo_query/metrics.py`
  - 统计项定义与聚合

### 文档
- `docs/notes/2026-06-19-areacity-phase3-plan.md`
- 后续可补：
  - `docs/notes/2026-06-xx-geo-benchmark-report.md`
  - `docs/notes/2026-06-xx-geo-index-tuning-report.md`

## 6. 第三阶段验收建议

建议把第三阶段验收拆开，不要一次性混成一个大目标。

### 6.1 子几何切分验收
- 同一 feature 可对应多个 subgeometry
- `boundary/by-id` 仍能正确返回完整边界
- 点查结果不回退、不丢失

### 6.2 索引效果验收
- 平均候选数下降
- 热点 cell 分布可见
- 容差查询明显减少 geometry 读取数

### 6.3 缓存验收
- cache hit/miss 可统计
- 有上限
- 长时间运行不无限膨胀

### 6.4 性能验收
- 基准脚本能稳定输出报告
- 对典型查询给出明确耗时与读放大指标

## 7. 我的建议结论

如果你要继续往前推，我建议第三阶段按下面顺序做：

1. 先做真正的子几何切分
2. 再做 cache/metrics
3. 再做基准与参数调优
4. 最后再考虑可选 shapely 加速

原因很简单：
- 真正的性能提升，首先来自更好的索引粒度
- 不是先上重库
- 先把纯 Python 路线做到结构正确，再谈加速最稳

## 8. 一句话总结

第二阶段已经解决“能查”。
第三阶段要解决的是“查得更快、更稳、更可观测、更接近长期生产形态”。
