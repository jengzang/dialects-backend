# 管理员自定义区域管理接口实现文档

## 概述

为 `supplements.db` 中的 `user_regions` 表添加了完整的管理员管理接口，使管理员能够查看、创建、更新和删除任意用户的自定义区域。

## 实现内容

### 1. 新增 Schemas（`app/schemas/admin.py`）

添加了 6 个管理员专用 schema：

- `AdminRegionCreate` - 管理员为任意用户创建区域
- `AdminRegionUpdate` - 管理员更新任意用户的区域
- `AdminRegionDelete` - 管理员删除任意用户的区域
- `AdminRegionResponse` - 管理员视图的区域响应
- `AdminRegionListResponse` - 分页区域列表响应
- `UserRegionCount` - 用户区域数量统计

### 2. 新增服务层函数（`app/custom/region_service.py`）

添加了 8 个管理员专用服务函数：

#### 查询函数
- `get_all_regions_admin()` - 获取所有区域（支持分页和搜索）
- `get_regions_by_username_admin()` - 按用户名获取区域
- `get_user_region_counts()` - 获取每个用户的区域数量
- `get_region_statistics()` - 获取详细统计信息（总数、热门地点、最近活动等）

#### 编辑函数
- `create_region_admin()` - 管理员为任意用户创建区域
- `update_region_admin()` - 管理员更新任意用户的区域
- `delete_region_admin()` - 管理员删除任意用户的区域
- `batch_delete_regions_admin()` - 批量删除区域

### 3. 新增路由文件

#### `app/routes/admin/custom_regions.py`（查看接口）

包含 4 个 GET 端点：

- `GET /admin/custom-regions/all` - 获取所有用户的自定义区域（分页）
  - 参数：`skip`, `limit`, `search`（可选）
  - 返回：分页的区域列表

- `GET /admin/custom-regions/user` - 按用户名查询区域
  - 参数：`username`（必需）
  - 返回：该用户的所有区域

- `GET /admin/custom-regions/count` - 获取每个用户的区域数量
  - 返回：用户名和区域数量的列表

- `GET /admin/custom-regions/stats` - 获取区域统计信息
  - 返回：详细统计数据（总数、用户分布、热门地点、最近活动）

#### `app/routes/admin/custom_regions_edit.py`（编辑接口）

包含 4 个编辑端点：

- `POST /admin/custom-regions/create` - 管理员为任意用户创建区域
  - Body: `AdminRegionCreate`
  - 返回：创建的区域信息

- `PUT /admin/custom-regions/update` - 管理员更新任意用户的区域
  - Body: `AdminRegionUpdate`
  - 返回：更新后的区域信息

- `DELETE /admin/custom-regions/delete` - 管理员删除任意用户的区域
  - Body: `AdminRegionDelete`
  - 返回：删除结果

- `POST /admin/custom-regions/batch-delete` - 批量删除区域
  - Body: `List[AdminRegionDelete]`
  - 返回：删除数量和失败列表

### 4. 路由注册（`app/routes/admin/__init__.py`）

在管理员路由集合中注册了新的路由：

```python
router.include_router(custom_regions_router, prefix="/custom-regions",
                      tags=["admin custom-regions"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(custom_regions_edit_router, prefix="/custom-regions",
                      tags=["admin custom-regions"],
                      dependencies=[Depends(get_current_admin_user)])
```

### 5. API 配置（`common/api_config.py`）

添加了 API 路由配置：

```python
"/admin/custom-regions/*": {
    "rate_limit": True,
    "require_login": True,
    "log_params": True,
    "log_body": True,
}
```

## 权限控制

所有管理员接口都通过 `get_current_admin_user` 依赖进行权限验证：
- 只有管理员角色的用户才能访问
- 非管理员用户访问将返回 403 Forbidden

## 统计功能

`/admin/custom-regions/stats` 端点提供以下统计信息：

### 基础统计
- 总区域数
- 总用户数
- 总地点数（去重）
- 平均每个区域的地点数

### 用户统计
- 前 10 名用户的区域数量排行

### 热门地点
- 前 20 个最常用的地点及使用次数

### 最近活动
- 最近 10 条区域创建/更新记录

## 测试

提供了完整的测试脚本 `test_admin_regions.py`，包含：
- 管理员登录
- 查询所有区域
- 按用户查询
- 统计信息查询
- CRUD 操作测试
- 批量删除测试

## API 端点总览

| 方法 | 端点 | 功能 | 权限 |
|------|------|------|------|
| GET | `/admin/custom-regions/all` | 获取所有区域（分页） | 管理员 |
| GET | `/admin/custom-regions/user` | 按用户名查询区域 | 管理员 |
| GET | `/admin/custom-regions/count` | 获取用户区域数量 | 管理员 |
| GET | `/admin/custom-regions/stats` | 获取统计信息 | 管理员 |
| POST | `/admin/custom-regions/create` | 创建区域 | 管理员 |
| PUT | `/admin/custom-regions/update` | 更新区域 | 管理员 |
| DELETE | `/admin/custom-regions/delete` | 删除区域 | 管理员 |
| POST | `/admin/custom-regions/batch-delete` | 批量删除区域 | 管理员 |

## 使用示例

### 获取所有区域（分页）
```bash
curl -X GET "http://localhost:5000/admin/custom-regions/all?skip=0&limit=10" \
  -H "Authorization: Bearer {admin_token}"
```

### 按用户查询
```bash
curl -X GET "http://localhost:5000/admin/custom-regions/user?username=testuser" \
  -H "Authorization: Bearer {admin_token}"
```

### 创建区域
```bash
curl -X POST "http://localhost:5000/admin/custom-regions/create" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "region_name": "测试区域",
    "locations": ["北京", "上海"],
    "description": "测试描述"
  }'
```

### 更新区域
```bash
curl -X PUT "http://localhost:5000/admin/custom-regions/update" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "region_name": "测试区域",
    "new_region_name": "新区域名",
    "locations": ["北京", "上海", "广州"]
  }'
```

### 删除区域
```bash
curl -X DELETE "http://localhost:5000/admin/custom-regions/delete" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "region_name": "测试区域"
  }'
```

## 注意事项

1. 所有接口都需要管理员权限
2. 创建/更新/删除操作会自动验证用户是否存在
3. 统计信息实时计算，数据量大时可能较慢
4. 批量删除操作会返回失败列表，方便排查问题
5. 所有操作都会记录到 API 日志中（用于审计）

## 文件清单

### 新增文件
- `app/routes/admin/custom_regions.py` - 查看接口
- `app/routes/admin/custom_regions_edit.py` - 编辑接口
- `test_admin_regions.py` - 测试脚本

### 修改文件
- `app/schemas/admin.py` - 添加 6 个 schema
- `app/custom/region_service.py` - 添加 8 个服务函数
- `app/routes/admin/__init__.py` - 注册新路由
- `common/api_config.py` - 添加 API 配置

## 实现完成

✅ 所有计划中的功能已实现
✅ 代码通过语法检查
✅ 提供完整的测试脚本
✅ 文档完整
