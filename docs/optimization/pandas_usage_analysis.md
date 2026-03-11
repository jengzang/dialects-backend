# 项目中 pandas 使用情况全面分析

## 执行时间：2026-03-11

## 1. 概览

### 使用pandas的文件统计

| 文件 | 描述 | pd.read_sql | pd.DataFrame | 总使用 | 优先级 |
|------|------|-------------|--------------|--------|--------|
| **核心服务** |
| app/service/phonology2status.py | 音韵分析核心 | 2 | 4 | 7 | 🔴 高 |
| app/service/status_arrange_pho.py | 音韵状态处理 | 4 | 5 | 12 | 🔴 高 |
| app/service/search_tones.py | 声调搜索 | 1 | 0 | 1 | 🟡 中 |
| **路由层** |
| app/routes/new_pho.py | 新音韵API | 0 | 2 | 5 | 🟢 低 |
| app/routes/phonology.py | 音韵API | 0 | 3 | 6 | 🟢 低 |
| **工具模块** |
| app/tools/check/check_routes.py | 检查工具 | 0 | 3 | 4 | 🟢 低 |
| app/tools/check/format_convert.py | 格式转换 | 0 | 3 | 3 | 🟢 低 |
| app/tools/jyut2ipa/jyut2ipa_core.py | 粤拼转IPA | 0 | 2 | 2 | 🟢 低 |
| app/tools/jyut2ipa/jyut2ipa_routes.py | 粤拼路由 | 0 | 2 | 3 | 🟢 低 |

---

## 2. 详细分析

### 🔴 高优先级优化（核心服务）

#### 2.1 app/service/phonology2status.py

**当前使用**：
1. ✅ `query_dialect_features()` - **已优化**（使用SQL GROUP BY）
2. ❌ `analyze_characters_from_db()` - **需要优化**
   - 使用 `pd.read_sql_query()` 读取characters表
   - 使用 `df.groupby()` 进行分组
   - 返回 `pd.DataFrame()`
3. ❌ `pho2sta()` - **需要优化**
   - 使用 `pd.read_sql_query()` 批量查询characters
   - 使用 `pd.DataFrame()` 构建空DataFrame

**优化建议**：
- `analyze_characters_from_db()`:
  - ⚠️ **已部分优化**（使用SQL GROUP BY）
  - 但仍使用 `pd.read_sql_query()` 读取数据
  - 可以进一步优化为纯cursor操作
  - **预期提升**: 2-3倍

- `pho2sta()`:
  - 批量查询可以保留（一次性读取所有字符）
  - 但可以用cursor代替pandas读取
  - **预期提升**: 1.5-2倍

**优化优先级**: ⭐⭐⭐⭐ (高)

---

#### 2.2 app/service/status_arrange_pho.py

**当前使用**：
1. ❌ `query_by_status()` - **需要优化**
   - 使用 `pd.read_sql_query()` 读取dialects表（2次）
   - 使用 `df.groupby()` 处理多音字
   - 大量DataFrame过滤操作
   - 返回 `pd.DataFrame()`

2. ✅ `query_by_status_stats_only()` - **已优化**（不使用pandas）

3. ❌ `run_status()` - **需要优化**
   - 使用 `pd.read_sql_query()` 读取characters表
   - 使用DataFrame操作

**优化建议**：
- `query_by_status()`:
  - 这是zhonggu API的核心函数
  - 逻辑复杂，涉及统计、分组、百分比计算
  - **可以优化**：使用SQL GROUP BY + Python字典
  - **预期提升**: 3-5倍
  - **难度**: 中等

**优化优先级**: ⭐⭐⭐⭐⭐ (最高)

---

#### 2.3 app/service/search_tones.py

**当前使用**：
1. ❌ `search_tones()` - **需要优化**
   - 使用 `pd.read_sql()` 读取声调数据
   - 使用 `df.set_index()` 设置索引
   - 使用 `df.loc[]` 过滤数据
   - 使用 `pd.isnull()` 检查空值

**优化建议**：
- 这个函数逻辑简单，主要是读取和格式化
- 可以用cursor + 字典代替
- **预期提升**: 5-10倍
- **难度**: 低

**优化优先级**: ⭐⭐⭐ (中)

---

### 🟡 中优先级优化（路由层）

#### 2.4 app/routes/new_pho.py & app/routes/phonology.py

**当前使用**：
- 主要用于结果格式转换
- `pd.DataFrame.to_dict(orient="records")`
- `pd.concat()` 合并多个DataFrame

**优化建议**：
- 这些是路由层的格式转换
- 如果底层服务已经返回字典，可以直接返回
- 不需要DataFrame中转
- **预期提升**: 1.5-2倍
- **难度**: 低

**优化优先级**: ⭐⭐ (低-中)

---

### 🟢 低优先级优化（工具模块）

#### 2.5 app/tools/check/* & app/tools/jyut2ipa/*

**当前使用**：
- 主要用于数据格式转换和展示
- 使用 `pd.DataFrame()` 构建表格
- 使用 `pd.concat()` 合并结果

**优化建议**：
- 这些是工具模块，使用频率较低
- pandas在这里提供了便利性
- 优化收益有限
- **建议**: 保持现状

**优化优先级**: ⭐ (低)

---

## 3. 优化策略总结

### 3.1 应该立即优化的（高收益）

| 函数 | 文件 | 原因 | 预期提升 | 难度 |
|------|------|------|---------|------|
| `query_by_status()` | status_arrange_pho.py | zhonggu API核心，频繁调用 | 3-5x | 中 |
| `search_tones()` | search_tones.py | 逻辑简单，易优化 | 5-10x | 低 |
| `analyze_characters_from_db()` | phonology2status.py | 已部分优化，可进一步提升 | 2-3x | 中 |

### 3.2 可以考虑优化的（中等收益）

| 函数 | 文件 | 原因 | 预期提升 | 难度 |
|------|------|------|---------|------|
| `pho2sta()` | phonology2status.py | yinwei API核心 | 1.5-2x | 中 |
| 路由层格式转换 | routes/*.py | 简化数据流 | 1.5-2x | 低 |

### 3.3 建议保持现状的（低收益）

| 模块 | 原因 |
|------|------|
| 工具模块 (check, jyut2ipa) | 使用频率低，pandas提供便利性 |
| VillagesML | 数据分析模块，pandas是合适的工具 |

---

## 4. 优化原则

### 4.1 何时应该去除pandas

✅ **应该去除**：
- 简单的数据库查询 + 列表提取
- 简单的分组和聚合（可以用SQL GROUP BY）
- 数据格式转换（可以用字典和列表）
- 性能敏感的热路径代码

❌ **可以保留**：
- 复杂的数据分析和统计
- 需要矩阵运算的场景
- 数据可视化准备
- 使用频率低的工具代码

### 4.2 优化方法

1. **SQL层面优化**
   - 使用 `cursor.execute()` 代替 `pd.read_sql()`
   - 使用 SQL `GROUP BY` 代替 pandas `groupby()`
   - 使用 SQL 聚合函数代替pandas统计

2. **Python原生数据结构**
   - 使用字典代替DataFrame
   - 使用列表代替Series
   - 使用集合进行去重

3. **保持向后兼容**
   - 如果函数返回DataFrame，保持接口不变
   - 内部实现可以优化，但外部接口保持一致

---

## 5. 实施计划

### Phase 1: 高优先级优化（立即）

**Week 1**:
1. ✅ 优化 `query_dialect_features()` - **已完成**
2. ⏳ 优化 `query_by_status()` - **待实施**
3. ⏳ 优化 `search_tones()` - **待实施**

**预期收益**:
- zhonggu API: 3-5倍提升
- search_tones API: 5-10倍提升

### Phase 2: 中优先级优化（可选）

**Week 2**:
1. 优化 `analyze_characters_from_db()` 进一步提升
2. 优化 `pho2sta()` 批量查询部分
3. 简化路由层的DataFrame转换

**预期收益**:
- yinwei API: 额外1.5-2倍提升
- 整体代码简化

### Phase 3: 评估和清理（长期）

**Week 3+**:
1. 评估工具模块是否需要优化
2. 清理不必要的pandas导入
3. 更新文档和测试

---

## 6. 风险评估

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 结果不一致 | 高 | 充分测试，对比优化前后结果 |
| 性能回退 | 中 | 性能测试，确保提升 |
| 代码复杂度增加 | 低 | 保持代码清晰，添加注释 |

### 6.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| API行为变化 | 高 | 保持接口不变，只优化内部实现 |
| 向后兼容性 | 中 | 保留DataFrame返回类型 |
| 维护成本 | 低 | 代码更简单，实际降低维护成本 |

---

## 7. 性能对比（已优化部分）

| API/函数 | 优化前 | 优化后 | 提升 | 状态 |
|---------|--------|--------|------|------|
| charlist (单查询) | 224ms | 16.1ms | 13.9x | ✅ 已完成 |
| charlist (组合) | 577ms | 14.5ms | 39.8x | ✅ 已完成 |
| query_dialect_features | 339ms | 81.8ms | 4.1x | ✅ 已完成 |
| yinwei (20地点) | 7.5s | 5.89s | 1.3x | ✅ 已完成 |
| query_by_status | ? | ? | 3-5x | ⏳ 待优化 |
| search_tones | ? | ? | 5-10x | ⏳ 待优化 |

---

## 8. 结论

### 8.1 关键发现

1. **pandas开销显著**：在简单查询场景，pandas开销占85-96%
2. **优化效果明显**：已优化的API性能提升4-40倍
3. **并非所有场景都需要优化**：工具模块可以保留pandas

### 8.2 推荐行动

**立即行动**：
1. ✅ 优化 `query_by_status()` - zhonggu API核心
2. ✅ 优化 `search_tones()` - 简单且高收益

**后续考虑**：
1. 进一步优化 `analyze_characters_from_db()`
2. 简化路由层的数据转换

**保持现状**：
1. 工具模块（check, jyut2ipa）
2. VillagesML数据分析模块

### 8.3 预期总体提升

优化完成后，核心API性能预期：
- **charlist API**: 13.9-39.8倍 ✅
- **zhonggu API**: 3-5倍 ⏳
- **yinwei API**: 2-3倍 ⏳
- **search_tones API**: 5-10倍 ⏳

**总体项目性能提升**: 5-10倍
