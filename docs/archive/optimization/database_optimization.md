# VillagesML API 更新说明 - 为数据库优化做准备

**日期**: 2026-02-25
**版本**: v1.1.0
**影响**: N-gram 相关 API

---

## 📋 概述

为了配合即将进行的数据库优化（删除不显著的 N-gram 数据），后端新增了统计端点和元数据支持，帮助前端更好地展示数据状态和变化。

**数据库优化计划**:
- 删除不显著的 N-gram (p_value >= 0.05)
- 保留 58.7% 的数据（2,302,287 / 3,919,345 条）
- 预计执行时间：2026-03-02

---

## 🆕 新增端点

### 1. N-gram 统计信息

**端点**: `GET /api/villages/statistics/ngrams`

**用途**: 获取 N-gram 数据的统计信息，包括显著性分布、按级别统计等

**响应示例**:
```json
{
  "ngram_significance": {
    "total": 3919345,
    "significant": 2302287,
    "insignificant": 1617058,
    "significant_rate": 58.7
  },
  "by_level": {
    "city": {
      "total": 1641738,
      "significant": 560980,
      "significant_rate": 34.2
    },
    "county": {
      "total": 998164,
      "significant": 673668,
      "significant_rate": 67.5
    },
    "township": {
      "total": 1279443,
      "significant": 1067639,
      "significant_rate": 83.4
    }
  },
  "regional_ngram_frequency": {
    "total": 4917509
  },
  "note": "Statistics based on current database state. After optimization, only significant n-grams (p < 0.05) will be retained."
}
```

**何时调用**:
- ✅ 在统计页面/仪表板显示数据概览
- ✅ 在数据优化前后对比展示
- ✅ 在帮助文档中说明数据范围

**使用示例**:
```typescript
// 获取 N-gram 统计
const stats = await fetch('/api/villages/statistics/ngrams');
const data = await stats.json();

// 显示在 UI 中
console.log(`总 N-gram: ${data.ngram_significance.total}`);
console.log(`显著 N-gram: ${data.ngram_significance.significant} (${data.ngram_significance.significant_rate}%)`);
```

---

### 2. 数据库统计信息

**端点**: `GET /api/villages/statistics/database`

**用途**: 获取数据库各表的记录数统计

**响应示例**:
```json
{
  "tables": {
    "regional_ngram_frequency": 4917509,
    "ngram_tendency": 3919345,
    "ngram_significance": 3919345,
    "pattern_regional_analysis": 1900580,
    "char_regional_analysis": 419626,
    "semantic_regional_analysis": 15489
  },
  "total_records": 11172894,
  "note": "Total record count across major villagesML tables"
}
```

**何时调用**:
- ✅ 在管理后台显示数据库状态
- ✅ 在系统监控页面
- ✅ 调试时检查数据完整性

---

## 🔄 更新的端点

### 3. 区域 N-gram 频率（已增强）

**端点**: `GET /api/villages/ngrams/regional`

**新增参数**: `return_metadata` (boolean, 默认 false)

**变化**:
- 添加了 `return_metadata` 参数
- 当设置为 `true` 时，返回包含元数据的响应

**响应格式对比**:

**旧格式** (return_metadata=false 或不传):
```json
[
  {
    "region_level": "city",
    "region_name": "广州市",
    "city": "广州市",
    "county": null,
    "township": null,
    "ngram": "新村",
    "frequency": 1234,
    "rank": 1
  }
]
```

**新格式** (return_metadata=true):
```json
{
  "data": [
    {
      "region_level": "city",
      "region_name": "广州市",
      "city": "广州市",
      "county": null,
      "township": null,
      "ngram": "新村",
      "frequency": 1234,
      "rank": 1
    }
  ],
  "metadata": {
    "total_count": 50,
    "includes_insignificant": false,
    "note": "Only statistically significant n-grams (p < 0.05) are included",
    "data_version": "optimized_20260302",
    "optimization_date": "2026-03-02",
    "coverage_rate": 0.587
  }
}
```

**何时使用 return_metadata=true**:
- ✅ 在数据优化后，需要向用户说明数据范围
- ✅ 在数据导出功能中，添加元数据说明
- ✅ 在 API 文档示例中展示完整信息

**使用示例**:
```typescript
// 不需要元数据（默认，向后兼容）
const response1 = await fetch('/api/villages/ngrams/regional?region_level=city&city=广州市&n=2');
const data1 = await response1.json();
// data1 是数组: [{ngram: "新村", ...}, ...]

// 需要元数据（数据优化后推荐）
const response2 = await fetch('/api/villages/ngrams/regional?region_level=city&city=广州市&n=2&return_metadata=true');
const data2 = await response2.json();
// data2 是对象: {data: [...], metadata: {...}}

// 显示元数据
if (data2.metadata.note) {
  showInfoTooltip(data2.metadata.note);
}
```

---

## 📊 前端适配建议

### 阶段 1: 数据优化前（现在 - 2026-03-02）

#### 1.1 添加统计信息展示

**位置**: 统计页面 / 仪表板

```typescript
// 在统计页面添加 N-gram 数据概览
async function loadNgramStats() {
  const response = await fetch('/api/villages/statistics/ngrams');
  const stats = await response.json();

  return {
    total: stats.ngram_significance.total,
    significant: stats.ngram_significance.significant,
    significantRate: stats.ngram_significance.significant_rate,
    byLevel: stats.by_level
  };
}

// UI 展示
<Card title="N-gram 数据统计">
  <Statistic label="总 N-gram" value={stats.total} />
  <Statistic label="显著 N-gram" value={stats.significant} suffix={`(${stats.significantRate}%)`} />
  <Divider />
  <Row>
    <Col>City: {stats.byLevel.city.significant_rate}%</Col>
    <Col>County: {stats.byLevel.county.significant_rate}%</Col>
    <Col>Township: {stats.byLevel.township.significant_rate}%</Col>
  </Row>
</Card>
```

#### 1.2 添加数据优化通知

**位置**: 全局通知栏

```typescript
// 在应用顶部显示维护通知
<Alert
  type="info"
  message="系统维护通知"
  description="数据库将于 2026-03-02 进行优化，届时将只保留统计显著的 N-gram 数据（58.7%）。优化后查询速度将提升 30-40%。"
  closable
/>
```

### 阶段 2: 数据优化后（2026-03-02 之后）

#### 2.1 更新所有 N-gram 查询

**推荐**: 所有 N-gram 相关查询都添加 `return_metadata=true`

```typescript
// 统一的 API 调用函数
async function fetchNgrams(params: NgramParams) {
  const url = new URL('/api/villages/ngrams/regional', API_BASE);
  url.searchParams.append('return_metadata', 'true');  // 添加这行

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      url.searchParams.append(key, String(value));
    }
  });

  const response = await fetch(url);
  const result = await response.json();

  // 检查是否有元数据
  if (result.metadata) {
    // 显示数据说明
    if (result.metadata.note) {
      console.info(result.metadata.note);
    }
    return result.data;
  }

  // 向后兼容：如果没有元数据，直接返回数据
  return result;
}
```

#### 2.2 更新 UI 标题和说明

**修改前**:
```tsx
<PageHeader title="N-gram 分布" />
```

**修改后**:
```tsx
<PageHeader
  title="显著 N-gram 分布"
  extra={
    <Tooltip title="只显示统计显著的 N-gram (p < 0.05)">
      <InfoCircleOutlined />
    </Tooltip>
  }
/>
```

#### 2.3 更新统计数字

**修改前**:
```tsx
<Statistic title="N-gram 总数" value={3919345} />
```

**修改后**:
```tsx
<Statistic
  title="显著 N-gram 总数"
  value={2302287}
  suffix={
    <Tooltip title="数据已优化，只包含统计显著的 N-gram">
      <InfoCircleOutlined />
    </Tooltip>
  }
/>
```

#### 2.4 添加数据覆盖率说明

```typescript
// 在数据表格底部添加说明
<Table.Footer>
  <div style={{ textAlign: 'center', padding: '16px', color: '#666' }}>
    数据覆盖率: 58.7% (2,302,287 / 3,919,345)
    <br />
    <small>只显示统计显著的 N-gram (p < 0.05)，已于 2026-03-02 优化</small>
  </div>
</Table.Footer>
```

#### 2.5 更新数据导出功能

```typescript
// 导出时包含元数据说明
async function exportNgramData() {
  const response = await fetch('/api/villages/ngrams/regional?return_metadata=true&...');
  const result = await response.json();

  // 在导出文件中添加说明
  const csvHeader = [
    '# N-gram 数据导出',
    `# 导出时间: ${new Date().toISOString()}`,
    `# 数据版本: ${result.metadata.data_version}`,
    `# 说明: ${result.metadata.note}`,
    `# 数据覆盖率: ${(result.metadata.coverage_rate * 100).toFixed(1)}%`,
    '',
    'ngram,frequency,rank,...'
  ].join('\n');

  // ... 导出逻辑
}
```

---

## 🔧 需要修改的页面/组件

### 高优先级（必须修改）

1. **N-gram 统计页面**
   - 添加 `/statistics/ngrams` 端点调用
   - 显示显著性分布
   - 添加数据优化说明

2. **N-gram 查询页面**
   - 更新标题为"显著 N-gram"
   - 添加工具提示说明
   - 使用 `return_metadata=true`

3. **数据导出功能**
   - 文件名改为 `significant_ngrams_export.csv`
   - 添加元数据说明

### 中优先级（建议修改）

4. **仪表板/首页**
   - 更新统计数字
   - 添加数据优化说明

5. **帮助文档/FAQ**
   - 添加"为什么 N-gram 数量减少了？"
   - 说明数据优化的好处

### 低优先级（可选）

6. **API 文档页面**
   - 更新示例代码
   - 说明新参数用法

---

## ⚠️ 注意事项

### 1. 向后兼容性

✅ **所有修改都是向后兼容的**:
- `return_metadata` 参数默认为 `false`
- 不传参数时，行为与之前完全一致
- 新端点是额外添加的，不影响现有端点

### 2. 数据优化时间窗口

**维护时间**: 2026-03-02 02:00-03:00 (UTC+8)
**停机时间**: 约 60 分钟
**影响**: 所有 API 服务暂停

**前端需要做的**:
- 提前 3 天显示维护通知
- 维护期间显示维护页面
- 维护后更新 UI 说明

### 3. 测试建议

**优化前测试**:
```bash
# 测试新端点
curl http://localhost:5000/api/villages/statistics/ngrams
curl http://localhost:5000/api/villages/statistics/database

# 测试元数据参数
curl "http://localhost:5000/api/villages/ngrams/regional?region_level=city&city=广州市&n=2&return_metadata=true"
```

**优化后测试**:
- 验证所有 N-gram 查询仍然正常
- 检查统计数字是否更新
- 确认元数据正确显示

---

## 📞 联系方式

如有疑问，请联系：
- 后端开发: [你的联系方式]
- 数据分析: [数据分析同事]

---

## 📝 变更日志

### v1.1.0 (2026-02-25)

**新增**:
- ✨ 新增 `GET /api/villages/statistics/ngrams` 端点
- ✨ 新增 `GET /api/villages/statistics/database` 端点
- ✨ `/ngrams/regional` 端点添加 `return_metadata` 参数

**优化**:
- 🎯 为数据库优化做好准备
- 📊 提供更详细的数据统计信息
- 📝 添加元数据支持，方便前端展示数据说明

**向后兼容**:
- ✅ 所有现有 API 调用不受影响
- ✅ 新参数都是可选的
