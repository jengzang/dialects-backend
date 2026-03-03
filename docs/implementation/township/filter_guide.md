# Township 过滤参数使用指南

## 问题背景

镇级(township)存在大量重名:
- 太平镇: 7个
- 新兴镇: 6个
- 水口镇: 5个

如果只传 `region_filter: ["太平镇"]`,会匹配到所有7个太平镇。

## 解决方案: 层级过滤

新增了 `city_filter` 和 `county_filter` 参数,支持多层级过滤。

### API参数

```typescript
interface ClusteringParams {
  algorithm: "kmeans" | "dbscan" | "gmm";
  k?: number;
  region_level: "city" | "county" | "township";

  // 过滤参数 (按顺序应用)
  city_filter?: string[];      // 新增: 市级过滤
  county_filter?: string[];    // 新增: 县级过滤
  region_filter?: string[];    // 原有: 当前层级过滤

  // 其他参数...
}
```

### 过滤顺序

```
原始数据
  → city_filter (如果提供)
  → county_filter (如果提供)
  → region_filter (如果提供)
  → 最终结果
```

## 使用场景

### 场景1: 分析特定的镇 (精确指定)

**需求**: 只分析"茂名市 > 高州市 > 太平镇"

```json
{
  "algorithm": "kmeans",
  "k": 3,
  "region_level": "township",
  "city_filter": ["茂名市"],
  "county_filter": ["高州市"],
  "region_filter": ["太平镇"]
}
```

**结果**: 只匹配1个镇

---

### 场景2: 分析某个县下的所有镇

**需求**: 分析高州市下的所有镇

```json
{
  "algorithm": "kmeans",
  "k": 5,
  "region_level": "township",
  "city_filter": ["茂名市"],
  "county_filter": ["高州市"]
  // 不提供 region_filter
}
```

**结果**: 匹配高州市下的所有镇(约20-30个)

---

### 场景3: 分析某个市下的所有镇

**需求**: 分析茂名市下的所有镇

```json
{
  "algorithm": "kmeans",
  "k": 10,
  "region_level": "township",
  "city_filter": ["茂名市"]
  // 不提供 county_filter 和 region_filter
}
```

**结果**: 匹配茂名市下所有县的所有镇

---

### 场景4: 分析多个市的特定镇

**需求**: 分析所有叫"太平镇"的镇,但只限于茂名市和梅州市

```json
{
  "algorithm": "kmeans",
  "k": 3,
  "region_level": "township",
  "city_filter": ["茂名市", "梅州市"],
  "region_filter": ["太平镇"]
}
```

**结果**: 匹配3个镇
- 茂名市 > 高州市 > 太平镇
- 茂名市 > 信宜市 > 太平镇
- 梅州市 > 兴宁市 > 太平镇

---

### 场景5: 分析多个县的多个镇

**需求**: 分析高州市和信宜市的太平镇和新兴镇

```json
{
  "algorithm": "kmeans",
  "k": 4,
  "region_level": "township",
  "city_filter": ["茂名市"],
  "county_filter": ["高州市", "信宜市"],
  "region_filter": ["太平镇", "新兴镇"]
}
```

**结果**: 匹配4个镇 (2个县 × 2个镇)

---

### 场景6: 不使用过滤 (分析所有镇)

**需求**: 对广东省所有镇进行聚类

```json
{
  "algorithm": "kmeans",
  "k": 20,
  "region_level": "township"
  // 不提供任何过滤参数
}
```

**结果**: 匹配所有~1600个镇

---

## County 级别也支持

### 场景: 分析某个市下的所有县

```json
{
  "algorithm": "kmeans",
  "k": 5,
  "region_level": "county",
  "city_filter": ["茂名市"]
}
```

**结果**: 匹配茂名市下的所有县(高州市、信宜市、电白区等)

---

## 前端实现建议

### 1. 级联选择器

```jsx
<Select
  placeholder="选择市"
  onChange={setSelectedCity}
>
  {cities.map(city => <Option key={city}>{city}</Option>)}
</Select>

{selectedCity && (
  <Select
    placeholder="选择县(可选)"
    onChange={setSelectedCounty}
  >
    {counties.filter(c => c.city === selectedCity).map(county =>
      <Option key={county.name}>{county.name}</Option>
    )}
  </Select>
)}

{selectedCounty && regionLevel === 'township' && (
  <Select
    mode="multiple"
    placeholder="选择镇(可选)"
    onChange={setSelectedTowns}
  >
    {towns.filter(t => t.county === selectedCounty).map(town =>
      <Option key={town.name}>{town.name}</Option>
    )}
  </Select>
)}
```

### 2. 构建请求参数

```javascript
function buildClusteringParams() {
  const params = {
    algorithm: "kmeans",
    k: 5,
    region_level: regionLevel,
    features: { ... },
    preprocessing: { ... }
  };

  // 添加过滤参数
  if (selectedCity) {
    params.city_filter = [selectedCity];
  }

  if (selectedCounty) {
    params.county_filter = [selectedCounty];
  }

  if (selectedTowns && selectedTowns.length > 0) {
    params.region_filter = selectedTowns;
  }

  return params;
}
```

### 3. 显示提示

```jsx
function FilterSummary({ cityFilter, countyFilter, regionFilter, regionLevel }) {
  if (!cityFilter && !countyFilter && !regionFilter) {
    return <div>分析所有{regionLevel === 'township' ? '镇' : '县'}</div>;
  }

  return (
    <div>
      分析范围:
      {cityFilter && <Tag>{cityFilter.join(', ')}</Tag>}
      {countyFilter && <Tag>{countyFilter.join(', ')}</Tag>}
      {regionFilter && <Tag>{regionFilter.join(', ')}</Tag>}
    </div>
  );
}
```

---

## 响应格式

响应中的 `region_name` 包含完整路径,便于区分:

```json
{
  "assignments": [
    {
      "region_name": "茂名市 > 高州市 > 太平镇",
      "cluster_id": 0
    },
    {
      "region_name": "梅州市 > 兴宁市 > 太平镇",
      "cluster_id": 1
    }
  ]
}
```

---

## 向后兼容性

### 旧的调用方式仍然有效

```json
{
  "region_level": "township",
  "region_filter": ["太平镇"]
}
```

**行为**: 匹配所有叫"太平镇"的镇(7个)

**建议**: 升级到新的过滤方式,使用 `city_filter` 或 `county_filter` 精确指定

---

## 测试示例

```bash
# 测试1: 精确指定一个镇
curl -X POST "http://localhost:5000/api/villages/compute/clustering/run" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "kmeans",
    "k": 3,
    "region_level": "township",
    "city_filter": ["茂名市"],
    "county_filter": ["高州市"],
    "region_filter": ["太平镇"]
  }'

# 测试2: 某个县的所有镇
curl -X POST "http://localhost:5000/api/villages/compute/clustering/run" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "kmeans",
    "k": 5,
    "region_level": "township",
    "city_filter": ["茂名市"],
    "county_filter": ["高州市"]
  }'
```
