# 语义子类别API更新说明

## 更新概述

数据分析团队已补充完整的县级和镇级子类别数据，API已更新以支持三级行政区划查询并添加噪声过滤功能。

## 数据完整性

### 更新前
- 仅市级数据：21个市，1,578条记录

### 更新后
- **市级**：21个市，1,578条记录
- **区县级**：121个县，7,905条记录（新增）
- **乡镇级**：1,439个镇，61,533条记录（新增）
- **总计**：71,016条记录

## API更新

### 1. `/comparison` 端点更新

**新增参数**：
- `min_villages`: 最小村庄数过滤（默认0，建议乡镇级使用5+）

**请求示例**：
```bash
# 查询新兴县的 mountain 子类别（县级）
GET /api/villages/semantic/subcategory/comparison?region_name=新兴县&region_level=区县级&parent_category=mountain&min_villages=0

# 查询某个乡镇的数据（过滤小样本噪声）
GET /api/villages/semantic/subcategory/comparison?region_name=簕竹镇&region_level=乡镇级&parent_category=mountain&min_villages=5
```

**响应示例**：
```json
{
  "region_name": "新兴县",
  "region_level": "区县级",
  "parent_category": "mountain",
  "min_villages": 0,
  "subcategories": [
    {
      "subcategory": "mountain_slope",
      "vtf": 234.0,
      "percentage": 5.67,
      "tendency": 5.37,
      "village_count": 234
    },
    {
      "subcategory": "mountain_valley",
      "vtf": 198.0,
      "percentage": 4.80,
      "tendency": 4.85,
      "village_count": 198
    }
  ],
  "total_count": 6
}
```

### 2. `/vtf/regional` 端点更新

**新增参数**：
- `min_villages`: 最小村庄数过滤（默认0）

**请求示例**：
```bash
# 查询所有县级的 mountain 子类别（过滤小样本）
GET /api/villages/semantic/subcategory/vtf/regional?region_level=区县级&parent_category=mountain&min_villages=10&limit=20
```

### 3. `/tendency/top` 端点更新

**新增参数**：
- `min_villages`: 最小村庄数过滤（默认5，自动排除噪声）

**请求示例**：
```bash
# 查询乡镇级倾向值最高的 mountain 子类别（过滤噪声）
GET /api/villages/semantic/subcategory/tendency/top?region_level=乡镇级&parent_category=mountain&min_villages=5&top_n=10

# 查询所有乡镇级数据（包含噪声，不推荐）
GET /api/villages/semantic/subcategory/tendency/top?region_level=乡镇级&parent_category=mountain&min_villages=0&top_n=10
```

## 噪声问题说明

### 问题描述
乡镇级数据存在小样本噪声：某些小乡镇只有1个村庄，且该村庄恰好包含某个子类别字符，导致：
- 占比100%
- 倾向值异常高（最高+99.92）

### 示例
```
中华街道 - agriculture_activity: tendency=+99.92, villages=1
榕华街道 - water_port: tendency=+99.90, villages=1
白洋乡 - clan_liu: tendency=+99.89, villages=1
```

### 解决方案
使用 `min_villages` 参数过滤小样本数据：

| 区域级别 | 推荐 min_villages | 说明 |
|---------|------------------|------|
| 市级 | 0 | 样本量充足，无需过滤 |
| 区县级 | 0-5 | 根据需求选择 |
| 乡镇级 | 5-10 | 强烈建议过滤，避免噪声 |

## 前端调用建议

### JavaScript 示例

```javascript
// 查询县级数据
async function getCountySubcategories(countyName, parentCategory) {
  const params = new URLSearchParams({
    region_name: countyName,
    region_level: '区县级',
    parent_category: parentCategory,
    min_villages: 0  // 县级通常不需要过滤
  });

  const response = await fetch(`/api/villages/semantic/subcategory/comparison?${params}`);
  return response.json();
}

// 查询乡镇级数据（自动过滤噪声）
async function getTownshipSubcategories(townshipName, parentCategory) {
  const params = new URLSearchParams({
    region_name: townshipName,
    region_level: '乡镇级',
    parent_category: parentCategory,
    min_villages: 5  // 乡镇级建议过滤
  });

  const response = await fetch(`/api/villages/semantic/subcategory/comparison?${params}`);
  return response.json();
}

// 查询倾向值最高的区域（带过滤）
async function getTopTendencyRegions(regionLevel, parentCategory, minVillages = 5) {
  const params = new URLSearchParams({
    region_level: regionLevel,
    parent_category: parentCategory,
    min_villages: minVillages,
    top_n: 10
  });

  const response = await fetch(`/api/villages/semantic/subcategory/tendency/top?${params}`);
  return response.json();
}
```

### React Hook 示例

```typescript
import { useState, useEffect } from 'react';

interface SubcategoryData {
  subcategory: string;
  vtf: number;
  percentage: number;
  tendency: number;
  village_count: number;
}

function useSubcategoryComparison(
  regionName: string,
  regionLevel: '市级' | '区县级' | '乡镇级',
  parentCategory: string,
  minVillages: number = 0
) {
  const [data, setData] = useState<SubcategoryData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          region_name: regionName,
          region_level: regionLevel,
          parent_category: parentCategory,
          min_villages: minVillages.toString()
        });

        const response = await fetch(
          `/api/villages/semantic/subcategory/comparison?${params}`
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        setData(result.subcategories);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [regionName, regionLevel, parentCategory, minVillages]);

  return { data, loading, error };
}

// 使用示例
function SubcategoryChart({ regionName, regionLevel, parentCategory }) {
  // 根据区域级别自动设置 minVillages
  const minVillages = regionLevel === '乡镇级' ? 5 : 0;

  const { data, loading, error } = useSubcategoryComparison(
    regionName,
    regionLevel,
    parentCategory,
    minVillages
  );

  if (loading) return <div>加载中...</div>;
  if (error) return <div>错误: {error}</div>;

  return (
    <div>
      <h3>{regionName} 的 {parentCategory} 子类别分布</h3>
      {minVillages > 0 && (
        <p className="note">已过滤村庄数 &lt; {minVillages} 的数据</p>
      )}
      <ul>
        {data.map(item => (
          <li key={item.subcategory}>
            {item.subcategory}:
            倾向值 {item.tendency.toFixed(2)},
            占比 {item.percentage.toFixed(2)}%,
            村庄数 {item.village_count}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## 参数值说明

### region_level 的有效值
- `"市级"` - 21个地级市
- `"区县级"` - 121个县/区
- `"乡镇级"` - 1,439个镇/街道

### parent_category 的有效值
- `"mountain"` - 山地类（6个子类别）
- `"water"` - 水系类（6个子类别）
- `"agriculture"` - 农业类
- `"vegetation"` - 植被类
- `"settlement"` - 聚落类
- `"direction"` - 方位类
- `"clan"` - 宗族类
- `"symbolic"` - 象征类
- `"infrastructure"` - 基础设施类

### min_villages 推荐值
- **市级**：0（样本量充足）
- **区县级**：0-5（根据需求）
- **乡镇级**：5-10（强烈建议，避免噪声）

## 数据验证

### 新兴县数据验证
新兴县的 mountain 子类别数据符合预期：
- `mountain_slope`: tendency = +5.37（山坡地形明显）
- `mountain_valley`: tendency = +4.85（山谷地形明显）

这与新兴县的实际地貌特征一致（位于云雾山脉南麓）。

### 噪声数据示例
未过滤的乡镇级数据（不推荐）：
```json
{
  "region_name": "中华街道",
  "subcategory": "agriculture_activity",
  "tendency": 99.92,
  "village_count": 1  // 仅1个村庄，统计不可靠
}
```

过滤后的乡镇级数据（推荐）：
```json
{
  "region_name": "簕竹镇",
  "subcategory": "mountain_slope",
  "tendency": 8.45,
  "village_count": 23  // 样本量充足，统计可靠
}
```

## 常见问题

### Q1: 为什么乡镇级数据有异常高的倾向值？
**A**: 小样本噪声。某些小乡镇只有1-2个村庄，导致统计不可靠。使用 `min_villages >= 5` 过滤。

### Q2: 如何选择合适的 min_villages 值？
**A**:
- 市级：0（无需过滤）
- 区县级：0-5（可选）
- 乡镇级：5-10（强烈建议）

### Q3: 过滤后没有数据怎么办？
**A**: 说明该区域的村庄数太少，无法进行可靠的统计分析。可以：
1. 降低 min_villages 值
2. 查询上一级区域（如从乡镇级改为区县级）
3. 使用主类别API（9个主类别而非76个子类别）

### Q4: 如何查看所有可用的区域名称？
**A**: 使用 `/vtf/regional` 端点查询：
```bash
# 查看所有县级区域
GET /api/villages/semantic/subcategory/vtf/regional?region_level=区县级&limit=200

# 查看云浮市下的所有乡镇
GET /api/villages/semantic/subcategory/vtf/regional?region_level=乡镇级&region_name=簕竹镇&limit=1
```

## 总结

1. ✅ 数据已完整：支持市/县/镇三级查询
2. ✅ 新增 `min_villages` 参数：自动过滤小样本噪声
3. ✅ 默认值优化：乡镇级默认过滤 villages < 5
4. ✅ 文档更新：所有端点都已更新说明

**推荐做法**：
- 市级和县级查询：`min_villages=0`（无需过滤）
- 乡镇级查询：`min_villages=5`（避免噪声）
- 倾向值排序：`min_villages=5`（默认值，自动过滤）
