# 村庄搜索 API 空名字过滤 - 修改报告

**日期**: 2026-02-24
**端点**: `GET /api/villages/village/search`
**状态**: ✅ 完成

## 需求

针对村庄搜索 API，如果自然村的名字为空，则：
1. 忽略该记录
2. 不记入总页码（total count）
3. 不返回给前端

## 实现

### 修改文件
`app/tools/VillagesML/village/search.py`

### 修改内容

在 WHERE 条件中添加过滤条件：

```python
# 过滤掉名字为空的记录
where_conditions.append("自然村_规范名 IS NOT NULL AND 自然村_规范名 != ''")
```

### SQL 查询变化

**修改前**：
```sql
SELECT COUNT(*) as total
FROM 广东省自然村_预处理
WHERE 1=1
  AND 市级 = ?
  -- 可能包含名字为空的记录
```

**修改后**：
```sql
SELECT COUNT(*) as total
FROM 广东省自然村_预处理
WHERE 1=1
  AND 自然村_规范名 IS NOT NULL AND 自然村_规范名 != ''  -- ⭐ 新增
  AND 市级 = ?
```

## 测试结果

### 测试用例
```
GET /api/villages/village/search?query=+&city=云浮市&limit=20&offset=0
```

### 结果
- ✅ 状态码: 200
- ✅ 总记录数: 13,142（不包含空名字记录）
- ✅ 返回记录数: 20
- ✅ 所有返回的记录都有有效的村庄名字
- ✅ 没有发现空名字记录

### 验证
```python
# 检查返回的数据
empty_names = [v for v in data['data']
               if not v.get('village_name') or v.get('village_name').strip() == '']

# 结果：empty_names = []（空列表）
```

## 影响范围

### 受影响的查询
1. **COUNT 查询**：总记录数不再包含空名字记录
2. **数据查询**：返回的数据不包含空名字记录
3. **分页计算**：页码基于过滤后的总数计算

### 不受影响的功能
- 其他过滤条件（city, county, township, query）正常工作
- 分页逻辑（limit, offset）正常工作
- 响应格式不变

## 示例

### 请求
```bash
GET /api/villages/village/search?query=+&city=云浮市&limit=20&offset=20
```

### 响应
```json
{
  "total": 13142,
  "page": 2,
  "page_size": 20,
  "data": [
    {
      "village_id": 12345,
      "village_name": "大村",
      "city": "云浮市",
      "county": "云城区",
      "township": "云城街道",
      "longitude": 112.044,
      "latitude": 22.915
    }
    // ... 其他19条记录，所有记录都有有效的 village_name
  ]
}
```

## 注意事项

1. **向后兼容**：此修改不会破坏现有的 API 调用
2. **数据完整性**：只过滤名字为空的记录，不影响其他数据
3. **性能影响**：添加的过滤条件对性能影响微乎其微
4. **前端适配**：前端不需要修改，因为响应格式不变

## 部署

修改已完成，服务器已重启。可以立即使用。

---

**实施人员**: Claude Code
**审核状态**: 待审核
**部署状态**: 已部署
