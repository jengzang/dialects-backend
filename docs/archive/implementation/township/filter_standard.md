# Township 过滤 - 项目标准模式

## 项目标准

VillagesML项目使用统一的层级过滤模式,所有API遵循相同的参数命名:

```typescript
{
  region_level: "city" | "county" | "township",
  region_name?: string,  // 向后兼容,模糊匹配
  city?: string,         // 精确匹配
  county?: string,       // 精确匹配
  township?: string      // 精确匹配
}
```

## 聚类API参数

```typescript
interface ClusteringParams {
  algorithm: "kmeans" | "dbscan" | "gmm";
  k?: number;
  region_level: "city" | "county" | "township";

  // 层级过滤参数(精确匹配)
  city?: string;
  county?: string;
  township?: string;

  // 向后兼容(模糊匹配)
  region_filter?: string[];

  // 其他参数...
}
```

## 使用示例

### 场景1: 精确指定一个镇

```json
{
  "algorithm": "kmeans",
  "k": 3,
  "region_level": "township",
  "city": "茂名市",
  "county": "高州市",
  "township": "太平镇"
}
```

**结果**: 只匹配 "茂名市 > 高州市 > 太平镇"

---

### 场景2: 某个县的所有镇

```json
{
  "algorithm": "kmeans",
  "k": 5,
  "region_level": "township",
  "city": "茂名市",
  "county": "高州市"
}
```

**结果**: 匹配高州市下的所有镇

---

### 场景3: 某个市的所有镇

```json
{
  "algorithm": "kmeans",
  "k": 10,
  "region_level": "township",
  "city": "茂名市"
}
```

**结果**: 匹配茂名市下所有镇

---

### 场景4: 向后兼容 - 使用 region_filter

```json
{
  "algorithm": "kmeans",
  "k": 3,
  "region_level": "township",
  "region_filter": ["太平镇", "新兴镇"]
}
```

**结果**: 匹配所有叫"太平镇"或"新兴镇"的镇(可能有多个)

**注意**: 这种方式会匹配所有重名的镇,不推荐使用。建议使用 `city`/`county`/`township` 参数精确指定。

---

## 与其他API的一致性

这种模式在整个VillagesML项目中统一使用:

### 字符频率API
```
GET /api/villages/character/frequency/regional?region_level=township&city=茂名市&county=高州市&township=太平镇
```

### 字符倾向性API
```
GET /api/villages/character/tendency/by-region?region_level=township&city=茂名市&county=高州市&township=太平镇
```

### 语义类别API
```
GET /api/villages/semantic/category/vtf/regional?region_level=township&city=茂名市&county=高州市&township=太平镇
```

### 聚类API (新增支持)
```
POST /api/villages/compute/clustering/run
{
  "region_level": "township",
  "city": "茂名市",
  "county": "高州市",
  "township": "太平镇"
}
```

---

## 前端实现

### 1. 级联选择器

```jsx
<Select placeholder="选择市" onChange={setCity}>
  {cities.map(c => <Option key={c}>{c}</Option>)}
</Select>

{city && (
  <Select placeholder="选择县" onChange={setCounty}>
    {counties.filter(c => c.city === city).map(c =>
      <Option key={c.name}>{c.name}</Option>
    )}
  </Select>
)}

{county && regionLevel === 'township' && (
  <Select placeholder="选择镇" onChange={setTownship}>
    {townships.filter(t => t.county === county).map(t =>
      <Option key={t.name}>{t.name}</Option>
    )}
  </Select>
)}
```

### 2. 构建请求

```javascript
const params = {
  algorithm: "kmeans",
  k: 5,
  region_level: regionLevel,
  features: { ... },
  preprocessing: { ... }
};

// 添加层级过滤
if (city) params.city = city;
if (county) params.county = county;
if (township) params.township = township;
```

---

## 响应格式

响应中的 `region_name` 包含完整路径:

```json
{
  "assignments": [
    {
      "region_name": "茂名市 > 高州市 > 太平镇",
      "cluster_id": 0
    }
  ]
}
```

---

## 数据库表结构

所有聚合表都包含完整的层级字段:

```sql
-- town_aggregates
CREATE TABLE town_aggregates (
  city TEXT,
  county TEXT,
  town TEXT,
  ...
);

-- county_aggregates
CREATE TABLE county_aggregates (
  city TEXT,
  county TEXT,
  ...
);

-- city_aggregates
CREATE TABLE city_aggregates (
  city TEXT,
  ...
);
```

---

## 迁移指南

如果之前使用了 `region_filter`:

**旧方式** (不推荐):
```json
{
  "region_level": "township",
  "region_filter": ["太平镇"]
}
```

**新方式** (推荐):
```json
{
  "region_level": "township",
  "city": "茂名市",
  "county": "高州市",
  "township": "太平镇"
}
```

---

## 总结

- ✅ 使用 `city`, `county`, `township` 参数(不是 `city_filter`)
- ✅ 这些参数是精确匹配,不是数组
- ✅ 遵循项目统一的命名规范
- ✅ 与其他VillagesML API保持一致
- ✅ 响应包含完整路径,避免歧义
