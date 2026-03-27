# phonology_matrix 和 classification_matrix API 性能分析

## 执行时间：2026-03-11

## 1. 性能测试结果

### 1.1 phonology_matrix API

| 场景 | 地点数 | 耗时 | 评估 |
|------|--------|------|------|
| 小规模 | 3个地点 | 50.9ms | ✅ 很快 |
| 中规模 | 10个地点 | 113.9ms | ✅ 可接受 |
| **大规模** | **2617个地点（全部）** | **34.87s** | ❌ **严重瓶颈** |

**问题分析**：
- 查询所有地点时性能急剧下降
- 34.87秒对于API来说太慢
- 但有Redis缓存（1小时），实际影响有限

### 1.2 classification_matrix API

| 场景 | 地点数 | 耗时 | 评估 |
|------|--------|------|------|
| 小规模 | 2个地点 | 86.3ms | ✅ 可接受 |
| 中规模 | 5个地点 | 998.8ms | ⚠️ **接近1秒** |

**问题分析**：
- 5个地点就接近1秒，性能不理想
- 涉及两个数据库查询（dialects + characters）
- 有大量的嵌套循环和字典操作

---

## 2. 代码分析

### 2.1 phonology_matrix 性能瓶颈

**当前实现**（`get_all_phonology_matrices`）：

```python
# 查询所有数据
SELECT 簡稱, 聲母, 韻母, 聲調, 漢字
FROM dialects
WHERE 簡稱 IN (...)  # 或查询所有
ORDER BY 簡稱, 聲母, 韻母, 聲調

# Python处理
for row in rows:  # 可能有几百万行
    location = row[0]
    initial = row[1]
    final = row[2]
    tone = row[3]
    char = row[4]

    # 构建嵌套字典
    loc_data["matrix"][initial][final][tone].append(char)
```

**瓶颈**：
1. ❌ 查询所有地点时返回几百万行数据
2. ❌ Python循环处理几百万行
3. ❌ 构建深度嵌套的字典结构
4. ❌ 没有使用pandas（但这里不适合用pandas）

**优化方向**：
- ✅ 限制查询范围（强制要求locations参数）
- ✅ 使用SQL GROUP_CONCAT减少行数
- ✅ 分页查询大数据集

### 2.2 classification_matrix 性能瓶颈

**当前实现**（`build_phonology_classification_matrix`）：

```python
# 步骤1: 查询dialects.db
SELECT 簡稱, 漢字, {feature}, 音節, 多音字
FROM dialects
WHERE 簡稱 IN (...)

# 步骤2: 查询characters.db
SELECT 漢字, {h_col}, {v_col}, {c_col}
FROM characters
WHERE 漢字 IN (...)  # 可能有几千个汉字

# 步骤3: Python嵌套循环
for row in dialect_data:  # N行
    char = row['漢字']
    classifications = char_classification_map.get(char, [])  # M个分类
    for classification in classifications:  # O(N*M)
        # 构建4层嵌套字典
        matrix[h_val][v_val][c_val][feature_value].append(char)
```

**瓶颈**：
1. ⚠️ 两次数据库查询
2. ⚠️ O(N*M)的嵌套循环
3. ⚠️ 4层嵌套的defaultdict
4. ⚠️ 大量的字典操作

**优化方向**：
- ✅ 使用SQL JOIN合并两次查询
- ✅ 使用SQL GROUP BY减少Python处理
- ✅ 优化数据结构

---

## 3. 优化方案

### 3.1 phonology_matrix 优化

#### 方案1：强制要求locations参数（推荐）

```python
def get_all_phonology_matrices(locations, db_path=DIALECTS_DB_USER, table="dialects"):
    if not locations:
        raise HTTPException(
            status_code=400,
            detail="locations参数不能为空，请指定地点列表"
        )
    # 限制最大地点数
    if len(locations) > 50:
        raise HTTPException(
            status_code=400,
            detail="一次最多查询50个地点"
        )
```

**优点**：
- 简单有效
- 避免查询全部数据
- 用户体验更好（明确告知限制）

**预期提升**：避免34秒的查询

#### 方案2：使用SQL GROUP_CONCAT优化

```python
# 使用SQL聚合减少行数
query = f"""
SELECT
    簡稱, 聲母, 韻母, 聲調,
    GROUP_CONCAT(漢字) as chars
FROM {table}
WHERE 簡稱 IN (...)
GROUP BY 簡稱, 聲母, 韻母, 聲調
"""
```

**优点**：
- 减少返回行数
- 减少Python循环次数

**预期提升**：2-3倍

### 3.2 classification_matrix 优化

#### 方案1：使用SQL JOIN合并查询（推荐）

```python
# 一次查询完成
query = f"""
SELECT
    d.簡稱, d.漢字, d.{feature}, d.音節, d.多音字,
    c.{horizontal_column}, c.{vertical_column}, c.{cell_row_column}
FROM dialects d
LEFT JOIN characters c ON d.漢字 = c.漢字
WHERE d.簡稱 IN (...)
AND d.{feature} IS NOT NULL
"""
```

**优点**：
- 一次查询代替两次
- 减少数据传输
- 数据库层面完成JOIN

**预期提升**：2-3倍

#### 方案2：优化数据结构

使用更扁平的数据结构代替4层嵌套：

```python
# 使用元组作为key
matrix = defaultdict(list)
key = (h_val, v_val, c_val, feature_value)
matrix[key].append(char)
```

**优点**：
- 更快的字典访问
- 更少的内存开销

**预期提升**：1.5-2倍

---

## 4. 优化优先级

### 🔴 高优先级（立即优化）

#### 1. phonology_matrix - 添加参数验证
- **原因**：避免34秒的全量查询
- **难度**：低
- **预期提升**：避免性能问题
- **实施时间**：10分钟

#### 2. classification_matrix - SQL JOIN优化
- **原因**：5个地点就接近1秒
- **难度**：中
- **预期提升**：2-3倍
- **实施时间**：30分钟

### 🟡 中优先级（可选）

#### 3. phonology_matrix - SQL GROUP_CONCAT
- **原因**：进一步提升性能
- **难度**：中
- **预期提升**：2-3倍
- **实施时间**：30分钟

#### 4. classification_matrix - 数据结构优化
- **原因**：减少内存开销
- **难度**：低
- **预期提升**：1.5-2倍
- **实施时间**：20分钟

---

## 5. 缓存策略分析

### 5.1 当前缓存

**phonology_matrix**：
- ✅ 使用Redis缓存
- ✅ 1小时过期
- ✅ 按地点列表缓存

**classification_matrix**：
- ❌ 没有缓存
- ⚠️ 每次请求都查询数据库

### 5.2 缓存建议

**classification_matrix 应该添加缓存**：

```python
# 构建缓存键
cache_key = f"classification_matrix:{db_type}:{','.join(sorted(locations))}:{feature}:{h_col}:{v_col}:{c_col}"

# 尝试从Redis获取
cached_data = await redis_client.get(cache_key)
if cached_data:
    return json.loads(cached_data)

# 查询并缓存
result = build_phonology_classification_matrix(...)
await redis_client.setex(cache_key, 3600, json.dumps(result))
```

**预期提升**：缓存命中时接近0ms

---

## 6. 对比其他API

| API | 小规模 | 中规模 | 大规模 | 缓存 | 评估 |
|-----|--------|--------|--------|------|------|
| charlist | 16ms | 15ms | 33ms | ✅ | ✅ 优秀 |
| query_by_status | 18ms | - | - | ❌ | ✅ 优秀 |
| search_tones | 10ms | - | - | ❌ | ✅ 优秀 |
| **phonology_matrix** | **51ms** | **114ms** | **34.87s** | ✅ | ⚠️ **需优化** |
| **classification_matrix** | **86ms** | **999ms** | - | ❌ | ⚠️ **需优化** |

---

## 7. 实施建议

### Phase 1：立即实施（本次）

1. ✅ **phonology_matrix 参数验证**
   - 强制要求locations参数
   - 限制最大地点数（50个）
   - 避免全量查询

2. ✅ **classification_matrix 添加缓存**
   - 添加Redis缓存
   - 1小时过期
   - 减少重复查询

### Phase 2：后续优化（可选）

3. **classification_matrix SQL JOIN**
   - 合并两次查询
   - 预期2-3倍提升

4. **phonology_matrix SQL GROUP_CONCAT**
   - 减少返回行数
   - 预期2-3倍提升

---

## 8. 结论

### 8.1 当前状态

**phonology_matrix**：
- ✅ 小规模查询快（50ms）
- ⚠️ 中规模可接受（114ms）
- ❌ 大规模严重慢（34.87s）
- ✅ 有缓存保护

**classification_matrix**：
- ✅ 小规模可接受（86ms）
- ⚠️ 中规模接近1秒（999ms）
- ❌ 没有缓存

### 8.2 优化建议

**立即优化**：
1. ✅ phonology_matrix 添加参数验证
2. ✅ classification_matrix 添加缓存

**可选优化**：
3. classification_matrix SQL JOIN优化
4. phonology_matrix SQL GROUP_CONCAT优化

### 8.3 预期效果

优化后：
- phonology_matrix：避免34秒查询，保持50-114ms
- classification_matrix：缓存命中时接近0ms，未命中时减少到300-400ms

---

## 9. 补充：feature_stats 和 feature_counts

### 9.1 快速检查

让我检查这两个API的实现...

（待补充分析）
