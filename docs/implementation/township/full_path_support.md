# 镇级区域名称完整路径支持

## 问题背景

在中国的行政区划中,镇级(township)和县级(county)存在大量重名现象:

### 重名统计
- **太平镇**: 7个 (分布在茂名、梅州、韶关等地)
- **新兴镇**: 6个
- **水口镇**: 5个
- **横陂镇**: 5个

如果API只返回 `"太平镇"`,前端无法区分是哪个太平镇。

## 解决方案

### 修改内容

修改了 `app/tools/VillagesML/compute/engine.py` 中的两处:

1. **`get_regional_features()` 方法** (Line 79-103)
2. **`aggregate_features()` 方法** (Line 1452-1466)

### 返回格式

现在API返回的区域名称包含完整行政路径:

| region_level | 返回格式 | 示例 |
|--------------|----------|------|
| city | `市` | `茂名市` |
| county | `市 > 县` | `茂名市 > 高州市` |
| township | `市 > 县 > 镇` | `茂名市 > 高州市 > 太平镇` |

### API响应示例

**请求**:
```json
{
  "algorithm": "kmeans",
  "k": 3,
  "region_level": "township",
  ...
}
```

**响应**:
```json
{
  "run_id": "online_clustering_1772170418",
  "algorithm": "kmeans",
  "k": 3,
  "n_regions": 1623,
  "assignments": [
    {
      "region_name": "茂名市 > 高州市 > 太平镇",
      "cluster_id": 0
    },
    {
      "region_name": "梅州市 > 兴宁市 > 太平镇",
      "cluster_id": 1
    },
    {
      "region_name": "韶关市 > 始兴县 > 太平镇",
      "cluster_id": 2
    }
  ]
}
```

## 前端适配

### 1. 显示完整路径

```jsx
// 直接显示
<div>{assignment.region_name}</div>
// 输出: 茂名市 > 高州市 > 太平镇
```

### 2. 解析路径层级

```javascript
function parseRegionPath(regionName) {
  const parts = regionName.split(' > ');

  if (parts.length === 3) {
    return {
      city: parts[0],
      county: parts[1],
      town: parts[2],
      level: 'township'
    };
  } else if (parts.length === 2) {
    return {
      city: parts[0],
      county: parts[1],
      level: 'county'
    };
  } else {
    return {
      city: parts[0],
      level: 'city'
    };
  }
}

// 使用
const region = parseRegionPath("茂名市 > 高州市 > 太平镇");
console.log(region.town); // "太平镇"
```

### 3. 面包屑导航

```jsx
function RegionBreadcrumb({ regionName }) {
  const parts = regionName.split(' > ');

  return (
    <nav className="breadcrumb">
      {parts.map((part, index) => (
        <span key={index}>
          {index > 0 && <span className="separator"> › </span>}
          <span className="breadcrumb-item">{part}</span>
        </span>
      ))}
    </nav>
  );
}

// 渲染: 茂名市 › 高州市 › 太平镇
```

### 4. 搜索和过滤

```javascript
// 支持多级搜索
function searchRegion(regions, query) {
  return regions.filter(r =>
    r.region_name.toLowerCase().includes(query.toLowerCase())
  );
}

// 搜索 "太平" 会匹配所有包含"太平"的完整路径
// 搜索 "茂名" 会匹配茂名市下的所有区域
```

### 5. 分组显示

```javascript
// 按市分组
function groupByCity(assignments) {
  const groups = {};

  assignments.forEach(a => {
    const city = a.region_name.split(' > ')[0];
    if (!groups[city]) groups[city] = [];
    groups[city].push(a);
  });

  return groups;
}
```

## 向后兼容性

### 影响的API端点

1. `POST /api/villages/compute/clustering/run` - 聚类分析
2. `POST /api/villages/compute/features/aggregate` - 特征聚合

### 不影响的端点

- 市级(city)聚类: 返回格式不变,仍然是 `"茂名市"`
- 县级(county)聚类: 现在返回 `"茂名市 > 高州市"` (之前可能只返回 `"高州市"`)

### 迁移建议

**如果前端已经在使用 township 或 county 级别的聚类**:

1. **检查显示逻辑**: 确保UI能正确显示包含 ` > ` 的字符串
2. **更新搜索**: 搜索逻辑需要考虑完整路径
3. **更新比较**: 如果有区域比较功能,需要使用完整路径作为唯一标识

**推荐做法**:

```javascript
// ❌ 错误 - 只使用镇名作为key
const regionMap = {};
assignments.forEach(a => {
  const town = a.region_name.split(' > ').pop();
  regionMap[town] = a;  // 会被覆盖!
});

// ✅ 正确 - 使用完整路径作为key
const regionMap = {};
assignments.forEach(a => {
  regionMap[a.region_name] = a;  // 唯一标识
});
```

## 测试

运行测试脚本验证:

```bash
python test_township_full_path.py
```

预期输出:
- ✅ 所有镇级区域都包含完整路径
- ✅ 可以正确区分重名的镇
- ✅ 路径格式统一为 `市 > 县 > 镇`

## 数据库支持

`town_aggregates` 表结构已包含完整层级:

```sql
CREATE TABLE town_aggregates (
  city TEXT,           -- 市
  county TEXT,         -- 县
  town TEXT,           -- 镇
  total_villages INTEGER,
  -- 其他特征字段...
);
```

查询示例:
```sql
SELECT city, county, town, total_villages
FROM town_aggregates
WHERE town = '太平镇';
```

结果:
```
茂名市 | 高州市 | 太平镇 | 193
梅州市 | 兴宁市 | 太平镇 | 334
韶关市 | 始兴县 | 太平镇 | 222
...
```
