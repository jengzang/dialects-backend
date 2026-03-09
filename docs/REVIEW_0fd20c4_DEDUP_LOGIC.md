# 0fd20c4 去重逻辑审查报告

**提交**: 0fd20c4 - optimize compare/phonology query path and add feature guards
**审查日期**: 2026-03-09

---

## 📋 变更内容

### 添加的去重逻辑

```python
# 第283-284行：地点和特征去重
locations_processed = list(dict.fromkeys(locations_processed))
features_processed = list(dict.fromkeys(payload.features))

# 第302-303行：汉字去重
chars1_unique = list(dict.fromkeys(chars1))
chars2_unique = list(dict.fromkeys(chars2))
```

---

## 🔍 深入分析

### 1. 汉字去重（chars1_unique, chars2_unique）

#### 数据来源
```python
# Step 4: 收集所有汉字
chars1 = []
for item in cached_char_result1:
    chars1.extend(item.get('汉字', []))  # 从多个查询结果中收集
```

#### 可能的重复场景
- 如果用户查询条件匹配到同一个汉字的多个记录
- 例如：查询"声母=p"可能返回 ['破', '破', '破'] （不同方言点的同一个字）

#### 去重的影响

**查看SQL查询**（第647行）：
```sql
SELECT 简称 as loc, 声母 as value,
       COUNT(DISTINCT 汉字) as count  -- ← 关键：使用了 DISTINCT
FROM dialects
WHERE 简称 IN (...)
  AND 汉字 IN (...)  -- ← 这里传入的是 char_list
GROUP BY 简称, 声母
```

**关键发现**：
- SQL查询使用了 `COUNT(DISTINCT 汉字)`
- 即使 `char_list` 中有重复，SQL也会自动去重
- **因此，去重对结果没有影响**

#### 性能影响

**去重前**：
```python
# 假设 chars1 = ['破', '破', '破', '坡', '坡']
char_placeholders = ','.join('?' for _ in chars1)  # 5个占位符
params = locations + chars1  # 传递5个参数
```

**去重后**：
```python
# chars1_unique = ['破', '坡']
char_placeholders = ','.join('?' for _ in chars1_unique)  # 2个占位符
params = locations + chars1_unique  # 传递2个参数
```

**性能提升**：
- ✅ 减少SQL参数数量
- ✅ 减少SQL IN子句的长度
- ✅ 提高查询效率（虽然SQL会自动去重，但减少参数仍有帮助）

---

### 2. 地点去重（locations_processed）

#### 数据来源
```python
locations_processed = await _resolve_locations()
# 从 query_dialect_abbreviations 返回
```

#### 可能的重复场景
- 如果 `query_dialect_abbreviations` 函数返回重复的地点简称
- 例如：用户选择了重叠的区域

#### 去重的影响

**查看函数内部**（第629行）：
```python
def query_by_status_stats_only(...):
    locations = list(dict.fromkeys(locations))  # ← 函数内部也去重了！
```

**发现**：
- `query_by_status_stats_only` 函数内部已经对 `locations` 去重
- **外部去重是多余的，但无害**

#### 性能影响
- ✅ 减少后续循环次数（第313行的 `for loc in locations_processed`）
- ✅ 减少SQL查询参数

---

### 3. 特征去重（features_processed）

#### 数据来源
```python
features_processed = list(dict.fromkeys(payload.features))
# 来自用户输入
```

#### 可能的重复场景
- 用户可能在前端误选了重复的特征
- 例如：`["声母", "声母", "韵母"]`

#### 去重的影响

**查看函数内部**（第630行）：
```python
def query_by_status_stats_only(...):
    features = list(dict.fromkeys(features))  # ← 函数内部也去重了！
```

**发现**：
- 函数内部也对 `features` 去重
- **外部去重是多余的，但无害**

#### 性能影响
- ✅ 减少后续循环次数（第321行的 `for feature in features_processed`）
- ✅ 避免重复的SQL查询

---

## 📊 总结评估

### 去重的必要性

| 去重位置 | 是否必要 | 原因 |
|---------|---------|------|
| **chars1_unique** | ✅ 有益 | 减少SQL参数，提高性能 |
| **chars2_unique** | ✅ 有益 | 减少SQL参数，提高性能 |
| **locations_processed** | ⚠️ 多余但无害 | 函数内部已去重 |
| **features_processed** | ⚠️ 多余但无害 | 函数内部已去重 |

### 对业务逻辑的影响

#### ✅ 无负面影响
1. **汉字去重**：
   - SQL使用 `COUNT(DISTINCT 汉字)`，结果不变
   - 只是提高了性能

2. **地点去重**：
   - 避免在响应中返回重复的地点数据
   - 这是正确的行为

3. **特征去重**：
   - 避免在响应中返回重复的特征数据
   - 这是正确的行为

#### ✅ 性能提升
1. **减少SQL参数**：
   - 如果 chars1 有100个重复，去重后可能只有20个
   - SQL查询效率提升

2. **减少循环次数**：
   - 响应组织阶段的循环次数减少
   - 内存占用减少

---

## 🎯 结论

### 这个去重逻辑是**正确且有益的**

**理由**：
1. ✅ **不改变业务逻辑**：SQL已经使用DISTINCT，结果一致
2. ✅ **提高性能**：减少SQL参数和循环次数
3. ✅ **防御性编程**：即使函数内部去重，外部去重也能防止意外
4. ✅ **改善用户体验**：避免返回重复数据

### 建议

#### 保留这个提交 ✅

**但可以优化**：
```python
# 当前代码（有轻微冗余）
locations_processed = await _resolve_locations()
locations_processed = list(dict.fromkeys(locations_processed))  # 外部去重
features_processed = list(dict.fromkeys(payload.features))  # 外部去重

# 在 query_by_status_stats_only 内部：
locations = list(dict.fromkeys(locations))  # 内部也去重
features = list(dict.fromkeys(features))  # 内部也去重
```

**优化建议**（可选）：
- 可以移除 `query_by_status_stats_only` 内部的去重
- 统一在调用前去重
- 但当前的双重去重也无害，可以保留作为防御性编程

---

## 📝 测试建议

### 测试场景1：重复汉字
```python
# 输入
chars1 = ['破', '破', '破', '坡', '坡']

# 预期
chars1_unique = ['破', '坡']

# 验证：结果应该与不去重时一致
```

### 测试场景2：重复地点
```python
# 输入
locations = ['广州', '广州', '深圳']

# 预期
locations_processed = ['广州', '深圳']

# 验证：响应中每个地点只出现一次
```

### 测试场景3：重复特征
```python
# 输入
features = ['声母', '声母', '韵母']

# 预期
features_processed = ['声母', '韵母']

# 验证：响应中每个特征只出现一次
```

---

## ✅ 最终建议

**保留这个提交**，因为：
1. 去重逻辑正确
2. 提高了性能
3. 没有改变业务逻辑
4. 改善了代码质量

**无需回滚或修改**。
