# 数据库架构迁移指南 (Backend Team)

## 执行摘要 (Executive Summary)

**迁移完成时间**: 2026-02-24

数据库优化已完成，数据库大小从 **5.45 GB 减少到 2.3 GB**（节省 58% 空间）。主要变化包括：

1. **移除 run_id 冗余**: 删除了多个历史版本，只保留活跃版本的数据
2. **合并频率/倾向性表**: 将分散的频率表和倾向性表合并为单一分析表
3. **新增查询索引**: 添加 17 个索引以提升 API 查询性能

**对后端的影响**: 所有使用旧表名或 run_id 参数的 API 查询需要更新。本文档提供详细的迁移指南和代码示例。

---

## 数据库变化对比

### 整体指标

| 指标 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| 数据库大小 | 5.45 GB | 2.3 GB | **-58%** |
| 表数量 | 45 | 44 | -1 |
| 总行数 | 21.16M | 2.26M | **-89.3%** |
| 索引数量 | 56 | 73 | +17 |

### 表结构变化汇总

| 旧表 (已删除) | 行数 | 新表 | 行数 | 变化 |
|--------------|------|------|------|------|
| char_frequency_regional | 957,654 | char_regional_analysis | 319,135 | -66.7% |
| regional_tendency | 957,654 | (合并到上表) | - | - |
| pattern_frequency_regional | 3,838,270 | pattern_regional_analysis | 1,928,311 | -49.8% |
| pattern_tendency | 3,838,270 | (合并到上表) | - | - |
| semantic_vtf_regional | 15,381 | semantic_regional_analysis | 14,292 | -7.1% |
| semantic_tendency | 15,381 | (合并到上表) | - | - |

---

## 详细表结构变化

### 变化 1: 字符分析表合并

**旧表结构 (已删除)**:

```sql
-- 表 1: char_frequency_regional (957,654 行, 包含 3 个 run_id)
CREATE TABLE char_frequency_regional (
    run_id TEXT,
    region_level TEXT,
    region_name TEXT,
    char TEXT,
    village_count INTEGER,
    total_villages INTEGER,
    frequency REAL,
    rank_within_region INTEGER
);

-- 表 2: regional_tendency (957,654 行, 包含 3 个 run_id)
CREATE TABLE regional_tendency (
    run_id TEXT,
    region_level TEXT,
    region_name TEXT,
    char TEXT,
    global_village_count INTEGER,
    global_frequency REAL,
    lift REAL,
    log_lift REAL,
    log_odds REAL,
    z_score REAL,
    support_flag INTEGER,
    rank_overrepresented INTEGER,
    rank_underrepresented INTEGER
);
```

**新表结构 (合并后)**:

```sql
-- 新表: char_regional_analysis (319,135 行, 无 run_id)
CREATE TABLE char_regional_analysis (
    region_level TEXT,
    region_name TEXT,
    char TEXT,
    village_count INTEGER,
    total_villages INTEGER,
    frequency REAL,
    rank_within_region INTEGER,
    global_village_count INTEGER,
    global_frequency REAL,
    lift REAL,
    log_lift REAL,
    log_odds REAL,
    z_score REAL,
    support_flag INTEGER,
    rank_overrepresented INTEGER,
    rank_underrepresented INTEGER
);

-- 索引 (新增)
CREATE INDEX idx_char_regional_region ON char_regional_analysis(region_level, region_name);
CREATE INDEX idx_char_regional_char ON char_regional_analysis(char);
CREATE INDEX idx_char_regional_zscore ON char_regional_analysis(z_score DESC);
```

**关键变化**:
- ❌ **移除**: `run_id` 列
- ✅ **保留**: 所有频率和倾向性列
- ✅ **新增**: 3 个索引以提升查询性能

---

### 变化 2: Pattern 分析表合并

**旧表结构 (已删除)**:

```sql
-- 表 1: pattern_frequency_regional (3,838,270 行, 包含 2 个 run_id)
CREATE TABLE pattern_frequency_regional (
    run_id TEXT,
    region_level TEXT,
    region_name TEXT,
    pattern TEXT,
    pattern_type TEXT,
    village_count INTEGER,
    total_villages INTEGER,
    frequency REAL,
    rank_within_region INTEGER
);

-- 表 2: pattern_tendency (3,838,270 行, 包含 2 个 run_id)
CREATE TABLE pattern_tendency (
    run_id TEXT,
    region_level TEXT,
    region_name TEXT,
    pattern TEXT,
    pattern_type TEXT,
    global_village_count INTEGER,
    global_frequency REAL,
    lift REAL,
    log_lift REAL,
    log_odds REAL,
    z_score REAL,
    support_flag INTEGER,
    rank_overrepresented INTEGER,
    rank_underrepresented INTEGER
);
```

**新表结构 (合并后)**:

```sql
-- 新表: pattern_regional_analysis (1,928,311 行, 无 run_id)
CREATE TABLE pattern_regional_analysis (
    region_level TEXT,
    region_name TEXT,
    pattern TEXT,
    pattern_type TEXT,
    village_count INTEGER,
    total_villages INTEGER,
    frequency REAL,
    rank_within_region INTEGER,
    global_village_count INTEGER,
    global_frequency REAL,
    lift REAL,
    log_lift REAL,
    log_odds REAL,
    z_score REAL,
    support_flag INTEGER,
    rank_overrepresented INTEGER,
    rank_underrepresented INTEGER
);

-- 索引 (新增)
CREATE INDEX idx_pattern_regional_region ON pattern_regional_analysis(region_level, region_name);
CREATE INDEX idx_pattern_regional_pattern ON pattern_regional_analysis(pattern);
CREATE INDEX idx_pattern_regional_type ON pattern_regional_analysis(pattern_type);
CREATE INDEX idx_pattern_regional_zscore ON pattern_regional_analysis(z_score DESC);
```

**关键变化**: 与字符表相同（移除 run_id，合并频率/倾向性列）

---

### 变化 3: 语义分析表合并

**旧表结构 (已删除)**:

```sql
-- 表 1: semantic_vtf_regional (15,381 行, 包含 2 个 run_id)
CREATE TABLE semantic_vtf_regional (
    run_id TEXT,
    region_level TEXT,
    region_name TEXT,
    semantic_label TEXT,
    village_count INTEGER,
    total_villages INTEGER,
    frequency REAL,
    rank_within_region INTEGER
);

-- 表 2: semantic_tendency (15,381 行, 包含 2 个 run_id)
CREATE TABLE semantic_tendency (
    run_id TEXT,
    region_level TEXT,
    region_name TEXT,
    semantic_label TEXT,
    global_village_count INTEGER,
    global_frequency REAL,
    lift REAL,
    log_lift REAL,
    log_odds REAL,
    z_score REAL,
    support_flag INTEGER,
    rank_overrepresented INTEGER,
    rank_underrepresented INTEGER
);
```

**新表结构 (合并后)**:

```sql
-- 新表: semantic_regional_analysis (14,292 行, 无 run_id)
CREATE TABLE semantic_regional_analysis (
    region_level TEXT,
    region_name TEXT,
    semantic_label TEXT,
    village_count INTEGER,
    total_villages INTEGER,
    frequency REAL,
    rank_within_region INTEGER,
    global_village_count INTEGER,
    global_frequency REAL,
    lift REAL,
    log_lift REAL,
    log_odds REAL,
    z_score REAL,
    support_flag INTEGER,
    rank_overrepresented INTEGER,
    rank_underrepresented INTEGER
);

-- 索引 (新增)
CREATE INDEX idx_semantic_regional_region ON semantic_regional_analysis(region_level, region_name);
CREATE INDEX idx_semantic_regional_label ON semantic_regional_analysis(semantic_label);
CREATE INDEX idx_semantic_regional_zscore ON semantic_regional_analysis(z_score DESC);
```

**关键变化**: 与字符表相同（移除 run_id，合并频率/倾向性列）

---

## API 查询迁移示例

### 示例 1: 字符全局频率查询

**❌ 旧代码 (不再工作)**:

```python
# api/character/frequency.py (旧版本)
@router.get("/global")
async def get_global_frequency(
    run_id: str = "default",  # ❌ 不再需要
    top_n: int = 100,
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT char, frequency, village_count, rank
        FROM char_frequency_global
        WHERE run_id = ?  -- ❌ run_id 列已不存在
        ORDER BY frequency DESC LIMIT ?
    """
    params = (run_id, top_n)
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

**✅ 新代码 (正确)**:

```python
# api/character/frequency.py (新版本)
@router.get("/global")
async def get_global_frequency(
    top_n: int = 100,  # ✅ 移除 run_id 参数
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT char, frequency, village_count, rank
        FROM char_frequency_global  -- ✅ 表名不变，但无 run_id 列
        ORDER BY frequency DESC LIMIT ?
    """
    params = (top_n,)  # ✅ 只需要 top_n 参数
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

---

### 示例 2: 字符区域频率查询

**❌ 旧代码 (表名已改变)**:

```python
# api/character/frequency.py (旧版本)
@router.get("/regional")
async def get_regional_frequency(
    region_level: str,
    region_name: str,
    run_id: str = "default",  # ❌ 不再需要
    top_n: int = 100,
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT char, frequency, village_count, rank_within_region
        FROM char_frequency_regional  -- ❌ 表名已改变
        WHERE run_id = ? AND region_level = ? AND region_name = ?
        ORDER BY frequency DESC LIMIT ?
    """
    params = (run_id, region_level, region_name, top_n)
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

**✅ 新代码 (正确)**:

```python
# api/character/frequency.py (新版本)
@router.get("/regional")
async def get_regional_frequency(
    region_level: str,
    region_name: str,
    top_n: int = 100,  # ✅ 移除 run_id 参数
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT char, frequency, village_count, rank_within_region
        FROM char_regional_analysis  -- ✅ 新表名
        WHERE region_level = ? AND region_name = ?  -- ✅ 移除 run_id 条件
        ORDER BY frequency DESC LIMIT ?
    """
    params = (region_level, region_name, top_n)  # ✅ 更新参数
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

---

### 示例 3: 字符倾向性查询 (重要!)

**❌ 旧代码 (表名已改变)**:

```python
# api/character/tendency.py (旧版本)
@router.get("/by-region")
async def get_tendency_by_region(
    region_level: str,
    region_name: str,
    run_id: str = "default",  # ❌ 不再需要
    top_n: int = 50,
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT char, lift, log_odds, z_score, support_flag
        FROM regional_tendency  -- ❌ 表名已改变
        WHERE run_id = ? AND region_level = ? AND region_name = ?
        ORDER BY z_score DESC LIMIT ?
    """
    params = (run_id, region_level, region_name, top_n)
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

**✅ 新代码 (正确 - 使用合并后的表)**:

```python
# api/character/tendency.py (新版本)
@router.get("/by-region")
async def get_tendency_by_region(
    region_level: str,
    region_name: str,
    top_n: int = 50,  # ✅ 移除 run_id 参数
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT char, lift, log_odds, z_score, support_flag
        FROM char_regional_analysis  -- ✅ 使用合并后的表
        WHERE region_level = ? AND region_name = ?  -- ✅ 移除 run_id 条件
        ORDER BY z_score DESC LIMIT ?
    """
    params = (region_level, region_name, top_n)  # ✅ 更新参数
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

**关键点**: 倾向性数据现在与频率数据在同一张表中，不需要 JOIN 查询。

---

### 示例 4: Pattern 频率查询

**❌ 旧代码**:

```python
# api/ngrams/frequency.py (旧版本)
@router.get("/regional")
async def get_pattern_regional_frequency(
    region_level: str,
    region_name: str,
    pattern_type: str = "prefix",
    run_id: str = "default",  # ❌ 不再需要
    top_n: int = 100,
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT pattern, frequency, village_count, rank_within_region
        FROM pattern_frequency_regional  -- ❌ 表名已改变
        WHERE run_id = ? AND region_level = ? AND region_name = ? AND pattern_type = ?
        ORDER BY frequency DESC LIMIT ?
    """
    params = (run_id, region_level, region_name, pattern_type, top_n)
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

**✅ 新代码**:

```python
# api/ngrams/frequency.py (新版本)
@router.get("/regional")
async def get_pattern_regional_frequency(
    region_level: str,
    region_name: str,
    pattern_type: str = "prefix",
    top_n: int = 100,  # ✅ 移除 run_id 参数
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT pattern, frequency, village_count, rank_within_region
        FROM pattern_regional_analysis  -- ✅ 新表名
        WHERE region_level = ? AND region_name = ? AND pattern_type = ?
        ORDER BY frequency DESC LIMIT ?
    """
    params = (region_level, region_name, pattern_type, top_n)  # ✅ 更新参数
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

---

### 示例 5: 语义标签查询

**❌ 旧代码**:

```python
# api/semantic/frequency.py (旧版本)
@router.get("/regional")
async def get_semantic_regional_frequency(
    region_level: str,
    region_name: str,
    run_id: str = "default",  # ❌ 不再需要
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT semantic_label, frequency, village_count
        FROM semantic_vtf_regional  -- ❌ 表名已改变
        WHERE run_id = ? AND region_level = ? AND region_name = ?
        ORDER BY frequency DESC
    """
    params = (run_id, region_level, region_name)
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

**✅ 新代码**:

```python
# api/semantic/frequency.py (新版本)
@router.get("/regional")
async def get_semantic_regional_frequency(
    region_level: str,
    region_name: str,
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
        SELECT semantic_label, frequency, village_count
        FROM semantic_regional_analysis  -- ✅ 新表名
        WHERE region_level = ? AND region_name = ?
        ORDER BY frequency DESC
    """
    params = (region_level, region_name)  # ✅ 更新参数
    cursor = db.execute(query, params)
    return cursor.fetchall()
```

---

## 需要修改的 API 文件清单

### ✅ 必须更新的文件

| 文件路径 | 需要修改的内容 | 优先级 |
|---------|---------------|--------|
| `api/character/frequency.py` | 更新表名: `char_frequency_regional` → `char_regional_analysis` | **高** |
| `api/character/tendency.py` | 更新表名: `regional_tendency` → `char_regional_analysis` | **高** |
| `api/ngrams/frequency.py` | 更新表名: `pattern_frequency_regional` → `pattern_regional_analysis` | **高** |
| `api/patterns/*.py` | 更新表名: `pattern_tendency` → `pattern_regional_analysis` | **高** |
| `api/semantic/frequency.py` | 更新表名: `semantic_vtf_regional` → `semantic_regional_analysis` | **高** |
| `api/semantic/tendency.py` | 更新表名: `semantic_tendency` → `semantic_regional_analysis` | **高** |

### ⚠️ 可能需要更新的文件

| 文件路径 | 需要检查的内容 | 优先级 |
|---------|---------------|--------|
| `api/config.py` | 检查 `DEFAULT_RUN_ID` 配置是否还需要 | 中 |
| `api/models.py` | 检查响应模型是否包含 `run_id` 字段 | 中 |
| `api/main.py` | 检查全局中间件或依赖项 | 低 |

### ✅ 不需要更新的文件

- `api/dependencies.py` - 数据库连接逻辑不变
- `api/main.py` - 路由定义不变
- `api/middleware/*.py` - 中间件逻辑不变

---

## 迁移检查清单

请按照以下步骤完成迁移:

### 第 1 步: 更新表名 (30 分钟)

- [ ] 全局搜索 `char_frequency_regional`，替换为 `char_regional_analysis`
- [ ] 全局搜索 `regional_tendency`，替换为 `char_regional_analysis`
- [ ] 全局搜索 `pattern_frequency_regional`，替换为 `pattern_regional_analysis`
- [ ] 全局搜索 `pattern_tendency`，替换为 `pattern_regional_analysis`
- [ ] 全局搜索 `semantic_vtf_regional`，替换为 `semantic_regional_analysis`
- [ ] 全局搜索 `semantic_tendency`，替换为 `semantic_regional_analysis`

### 第 2 步: 移除 run_id 参数 (30 分钟)

- [ ] 从所有 API 端点函数签名中移除 `run_id` 参数
- [ ] 从所有 SQL 查询中移除 `WHERE run_id = ?` 条件
- [ ] 更新所有 `params` 元组，移除 `run_id` 值
- [ ] 检查是否有默认值 `run_id = "default"` 需要删除

### 第 3 步: 更新 API 文档 (20 分钟)

- [ ] 更新 Swagger/OpenAPI 文档字符串
- [ ] 移除响应模型中的 `run_id` 字段（如果有）
- [ ] 更新示例请求/响应
- [ ] 更新 API 参考文档

### 第 4 步: 测试所有受影响的端点 (60 分钟)

- [ ] `/character/frequency/global` - 测试全局字符频率
- [ ] `/character/frequency/regional` - 测试区域字符频率
- [ ] `/character/tendency/by-region` - 测试区域倾向性
- [ ] `/character/tendency/by-char` - 测试字符倾向性
- [ ] `/ngrams/frequency/regional` - 测试 Pattern 频率
- [ ] `/patterns/tendency/*` - 测试 Pattern 倾向性
- [ ] `/semantic/frequency/regional` - 测试语义频率
- [ ] `/semantic/tendency/*` - 测试语义倾向性

### 第 5 步: 验证查询性能 (15 分钟)

- [ ] 检查查询响应时间是否正常（应该更快）
- [ ] 验证索引是否被正确使用
- [ ] 检查是否有慢查询日志

### 第 6 步: 部署和监控 (30 分钟)

- [ ] 在测试环境验证所有更改
- [ ] 部署到生产环境
- [ ] 监控错误日志
- [ ] 验证 API 响应正确性

**预计总时间**: 3-4 小时

---

## 常见问题 FAQ

### Q1: 为什么要做这个改动？

**A**: 数据库存在严重冗余问题：
- 存储了 3 个版本的字符数据（但只使用 1 个）
- 存储了 2 个版本的 Pattern 和语义数据（但只使用 1 个）
- 频率表和倾向性表分离，导致查询需要 JOIN

优化后：
- 节省 3.15 GB 空间（58% 减少）
- 查询更简单（无需 JOIN）
- 性能更好（新增 17 个索引）

### Q2: 旧的 API 代码还能用吗？

**A**: **不能**。旧表已被完全删除，必须更新查询才能工作。如果不更新，API 会返回错误：

```
sqlite3.OperationalError: no such table: char_frequency_regional
```

### Q3: run_id 完全不需要了吗？

**A**: **是的**。现在只保留活跃版本的数据，不需要 run_id 区分版本。如果将来需要版本管理，会采用不同的策略（例如时间戳或版本号表）。

### Q4: 如果我需要查询倾向性数据怎么办？

**A**: 倾向性数据已经合并到区域分析表中。例如：

- 旧方式: 查询 `regional_tendency` 表
- 新方式: 查询 `char_regional_analysis` 表（包含所有倾向性列）

**优势**: 不需要 JOIN，查询更快。

### Q5: 索引会影响查询性能吗？

**A**: **不会，反而更快**。我们新增了 17 个索引，专门针对常见查询模式优化：

- `region_level + region_name` 组合索引
- `char/pattern/semantic_label` 单列索引
- `z_score DESC` 排序索引

查询性能应该比之前更好。

### Q6: 需要多长时间完成迁移？

**A**: 预计 **3-4 小时**：
- 代码更新: 1-1.5 小时
- 测试验证: 1-1.5 小时
- 部署监控: 0.5-1 小时

如果熟悉代码库，可能更快。

### Q7: 如果遇到问题怎么办？

**A**:
1. 检查表名是否正确（最常见错误）
2. 检查是否移除了所有 `run_id` 参数
3. 检查 SQL 语法是否正确
4. 查看错误日志获取详细信息
5. 联系数据团队获取支持

### Q8: 数据会丢失吗？

**A**: **不会**。所有活跃版本的数据都已迁移到新表。只是删除了历史冗余版本。

### Q9: 前端需要修改吗？

**A**: **可能需要**。如果前端 API 调用中包含 `run_id` 参数，需要移除。例如：

```javascript
// ❌ 旧代码
fetch('/api/character/frequency/regional?region_level=市级&region_name=广州市&run_id=default')

// ✅ 新代码
fetch('/api/character/frequency/regional?region_level=市级&region_name=广州市')
```

### Q10: 可以回滚吗？

**A**: **不建议**。旧表已被删除，数据库已 VACUUM。如果确实需要回滚，需要从备份恢复。建议在测试环境充分验证后再部署到生产环境。

---

## 支持与联系

### 迁移信息

- **迁移完成时间**: 2026-02-24
- **文档更新时间**: 2026-02-24
- **数据库版本**: v2.0 (优化后)

### 技术支持

如有问题，请联系数据团队：

- **紧急问题**: 立即联系数据团队
- **一般问题**: 通过项目 Issue 跟踪器提交
- **文档问题**: 查看 `docs/` 目录下的其他文档

### 相关文档

- `docs/guides/DATABASE_OPTIMIZATION_COMPLETE.md` - 优化详细说明
- `docs/reports/DATABASE_STATUS_REPORT.md` - 数据库状态报告
- `docs/frontend/API_REFERENCE.md` - API 完整参考

---

## 附录: 完整表映射

### 字符分析

| 旧表 | 新表 | 说明 |
|------|------|------|
| `char_frequency_global` | `char_frequency_global` | 表名不变，移除 run_id 列 |
| `char_frequency_regional` | `char_regional_analysis` | 合并到新表 |
| `regional_tendency` | `char_regional_analysis` | 合并到新表 |

### Pattern 分析

| 旧表 | 新表 | 说明 |
|------|------|------|
| `pattern_frequency_global` | `pattern_frequency_global` | 表名不变，移除 run_id 列 |
| `pattern_frequency_regional` | `pattern_regional_analysis` | 合并到新表 |
| `pattern_tendency` | `pattern_regional_analysis` | 合并到新表 |

### 语义分析

| 旧表 | 新表 | 说明 |
|------|------|------|
| `semantic_vtf_global` | `semantic_vtf_global` | 表名不变，移除 run_id 列 |
| `semantic_vtf_regional` | `semantic_regional_analysis` | 合并到新表 |
| `semantic_tendency` | `semantic_regional_analysis` | 合并到新表 |

---

**文档版本**: 1.0
**最后更新**: 2026-02-24
**作者**: 数据团队
