# Charlist API 性能分析报告

## 执行时间：2026-03-11

## 1. 性能瓶颈分析

### 1.1 整体性能表现

测试场景：
- 单个查询 `[知]{組}[三]{等}`：**224ms**
- 组合查询（6个组合）：**577ms**（平均96ms/组合）
- 多个查询（3个）：**534ms**

### 1.2 耗时分布（单个查询）

| 阶段 | 耗时 | 占比 | 说明 |
|------|------|------|------|
| SQL查询 | 7ms | 3.4% | 数据库查询本身很快 |
| pandas转换 | 1.2ms | 0.6% | DataFrame构建开销很小 |
| **后处理（多地位字检查）** | **197.4ms** | **96%** | **主要瓶颈** |
| **总计** | **205.6ms** | **100%** | |

### 1.3 瓶颈根因

**多地位字检查逻辑**（`query_characters_by_path` 函数第125-130行）：

```python
for word in candidates:  # 303个候选字
    all_rows = df[df["漢字"] == word]  # O(n) DataFrame过滤
    sub = all_rows[filter_columns].drop_duplicates()  # O(m) 去重
    if len(sub) > 1:
        multi_chars.append(word)
```

**问题**：
- 时间复杂度：O(candidates × rows) = O(303 × 912) ≈ 276K次操作
- 每次循环都要过滤整个DataFrame
- 测试耗时：208.6ms

## 2. 优化方案

### 2.1 方案1：使用groupby优化（推荐）

**优化代码**：
```python
# 使用groupby一次性处理所有字
multi_df = df[df['多地位標記'] == '1']
grouped = multi_df.groupby('漢字')[filter_columns].apply(
    lambda x: x.drop_duplicates().shape[0]
)
multi_chars = grouped[grouped > 1].index.tolist()
```

**性能提升**：
- 优化后耗时：80.1ms
- 性能提升：**2.6倍**
- 结果一致性：✅ 完全一致

**预期整体提升**：
- 单个查询：224ms → 96ms（**57%提升**）
- 组合查询：577ms → 345ms（**40%提升**）

### 2.2 方案2：SQL层面优化（更激进）

直接在SQL查询中完成多地位字检查：

```python
query = f"""
SELECT
    漢字,
    COUNT(DISTINCT {' || '.join(filter_columns)}) as distinct_count
FROM characters
WHERE {where_clause}
AND 多地位標記 = '1'
GROUP BY 漢字
HAVING distinct_count > 1
"""
```

**优势**：
- 完全在数据库层面完成
- 预计耗时 < 10ms
- 性能提升：**20倍以上**

**劣势**：
- 需要两次SQL查询（一次查字，一次查多地位）
- 代码改动较大

### 2.3 方案3：批量查询优化

对于 `combine_query=True` 的场景，当前是串行执行多个查询：

```python
for value_combination in itertools.product(*value_combinations):
    query_string = path_string + ...
    characters, _ = query_characters_by_path(query_string)  # 每次都查询
```

**优化方向**：
- 使用 UNION ALL 合并多个查询
- 一次性获取所有组合的结果
- 在Python层面分组

**预期提升**：
- 减少数据库连接开销
- 减少重复的DataFrame构建
- 组合查询提升：**30-50%**

## 3. 索引状况

### 3.1 现有索引

characters表已有充足的索引：
- 单列索引：組、母、攝、等、呼、調等（16个）
- 复合索引：(組,母,漢字)、(攝,調,漢字)等（4个）
- 层级索引：(組,母,攝,等,調)

### 3.2 索引使用情况

✅ 查询已正确使用索引，SQL查询本身不是瓶颈（仅7ms）

## 4. 优化建议

### 4.1 立即实施（低风险，高收益）

1. **优化多地位字检查逻辑**（方案1）
   - 修改 `query_characters_by_path` 函数
   - 使用groupby代替循环
   - 预期提升：2.6倍
   - 风险：低（逻辑等价）

### 4.2 中期优化（中等改动）

2. **批量查询优化**（方案3）
   - 修改 `process_chars_status` 函数
   - 对combine_query场景使用UNION ALL
   - 预期提升：30-50%
   - 风险：中（需要重构查询逻辑）

### 4.3 长期优化（激进方案）

3. **SQL层面优化**（方案2）
   - 完全在数据库层面完成多地位字检查
   - 预期提升：20倍以上
   - 风险：高（需要大幅重构）

## 5. 实施计划

### Phase 1：groupby优化（立即）
- 修改 `query_characters_by_path` 函数
- 替换多地位字检查逻辑
- 测试验证结果一致性
- 预期完成时间：30分钟

### Phase 2：批量查询优化（可选）
- 分析combine_query使用频率
- 如果频繁使用，实施UNION ALL优化
- 预期完成时间：2小时

### Phase 3：SQL优化（可选）
- 评估收益/成本比
- 如果性能仍不满足需求，考虑实施
- 预期完成时间：4小时

## 6. 测试数据

### 6.1 测试环境
- 数据库：characters.db（6.2MB）
- 测试查询：`[知]{組}[三]{等}`
- 返回结果：912行，797个唯一汉字
- 多地位候选字：303个

### 6.2 性能对比

| 方法 | 耗时 | 提升 |
|------|------|------|
| 原始（循环） | 208.6ms | 基准 |
| 优化（groupby） | 80.1ms | 2.6x |
| 预期（SQL） | <10ms | >20x |

## 7. 结论

**主要发现**：
- SQL查询不是瓶颈（仅占3.4%）
- 多地位字检查是主要瓶颈（占96%）
- 使用groupby可以轻松获得2.6倍提升

**推荐行动**：
1. ✅ 立即实施groupby优化（低风险，高收益）
2. ⏸️ 观察优化效果，评估是否需要进一步优化
3. ❓ 如果仍不满足需求，考虑批量查询或SQL优化
