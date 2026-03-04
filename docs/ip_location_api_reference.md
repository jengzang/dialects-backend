# IP 地理位置功能 - API 响应变化快速参考

## 新增字段总览

### 1. 登录日志接口

#### `/admin/login-logs/success-login-logs`
```json
{
  "id": 123,
  "user_id": 1,
  "path": "/login",
  "ip": "114.114.114.114",
  "ip_location": "中国",  // 新增字段
  "called_at": "2026-03-04T10:00:00"
}
```

#### `/admin/login-logs/failed-login-logs`
```json
{
  "id": 456,
  "user_id": 1,
  "path": "/login",
  "ip": "8.8.8.8",
  "ip_location": "美国",  // 新增字段
  "status_code": 401,
  "called_at": "2026-03-04T10:00:00"
}
```

### 2. API 使用统计接口

#### `/admin/api-usage/api-usage?include_statistics=true`
```json
{
  "total": 1000,
  "data": [...],  // 详细日志列表，不包含 location
  "statistics": {
    "summary": {...},
    "user_stats": [...],
    "ip_stats": [  // 只在统计数据中添加 location
      {
        "ip": "114.114.114.114",
        "location": "中国",  // 新增字段
        "call_count": 100,
        "total_duration": 50.5
      }
    ],
    "path_stats": [...]
  }
}
```

### 3. 会话管理接口

#### `/admin/user-sessions/list`
```json
{
  "total": 50,
  "sessions": [
    {
      "id": 1,
      "session_id": "abc123",
      "user_id": 1,
      "username": "testuser",
      "current_ip": "114.114.114.114",
      "current_ip_location": "中国",  // 新增字段
      "created_at": "2026-03-04T10:00:00"
    }
  ]
}
```

#### `/admin/user-sessions/{session_id}`
```json
{
  "id": 1,
  "session_id": "abc123",
  "user_id": 1,
  "username": "testuser",
  "current_ip": "114.114.114.114",
  "current_ip_location": "中国",  // 新增字段
  "first_ip": "8.8.8.8",
  "first_ip_location": "美国",  // 新增字段
  "ip_history": [
    {
      "ip": "8.8.8.8",
      "location": "美国",  // 新增字段
      "timestamp": "2026-03-04T10:00:00Z"
    },
    {
      "ip": "114.114.114.114",
      "location": "中国",  // 新增字段
      "timestamp": "2026-03-04T11:00:00Z"
    }
  ]
}
```

#### `/admin/user-sessions/online-users`
```json
{
  "online_count": 5,
  "users": [
    {
      "user_id": 1,
      "username": "testuser",
      "current_ip": "114.114.114.114",
      "current_ip_location": "中国",  // 新增字段
      "last_seen": "2026-03-04T10:00:00"
    }
  ]
}
```

#### `/admin/user-sessions/{session_id}/activity`
```json
{
  "session_id": "abc123",
  "user_id": 1,
  "username": "testuser",
  "events": [
    {
      "timestamp": "2026-03-04T10:00:00",
      "event_type": "created",
      "details": "Session created from 8.8.8.8"
    },
    {
      "timestamp": "2026-03-04T11:00:00",
      "event_type": "ip_changed",
      "details": "IP changed to 114.114.114.114 (中国)"  // 包含地理位置
    }
  ]
}
```

#### `/admin/user-sessions/user/{user_id}/history`
```json
{
  "total": 10,
  "sessions": [
    {
      "id": 1,
      "session_id": "abc123",
      "current_ip": "114.114.114.114",
      "current_ip_location": "中国",  // 新增字段
      "created_at": "2026-03-04T10:00:00"
    }
  ]
}
```

## 字段说明

### `ip_location` / `current_ip_location` / `first_ip_location`
- **类型**: `string | null`
- **格式**:
  - City 级别: `"中国 - 北京"` 或 `"美国 - 纽约"`
  - Country 级别: `"中国"` 或 `"美国"`
- **可能的值**:
  - 正常 IP: 返回地理位置字符串
  - 无效 IP / 内网 IP / 查询失败: 返回 `null`
- **默认级别**: City (城市级别)

### `ip_history[].location`
- **类型**: `string | null`
- **说明**: IP 历史记录中每个 IP 的地理位置
- **动态查询**: 不存储在数据库，每次请求时动态查询

## 前端使用建议

### 1. 显示逻辑
```javascript
// 显示 IP 和位置
function displayIpWithLocation(ip, location) {
  if (location) {
    return `${ip} (${location})`;
  }
  return ip;
}

// 示例: "114.114.114.114 (中国)"
```

### 2. 表格展示
```javascript
// 在表格中添加位置列
{
  title: 'IP 地址',
  dataIndex: 'ip',
  key: 'ip',
},
{
  title: '位置',
  dataIndex: 'ip_location',
  key: 'ip_location',
  render: (location) => location || '未知',
}
```

### 3. 地图可视化
```javascript
// 使用位置信息在地图上标注
function parseLocation(location) {
  if (!location) return null;

  // "中国 - 北京" -> { country: "中国", city: "北京" }
  const parts = location.split(' - ');
  return {
    country: parts[0],
    city: parts[1] || null
  };
}
```

## 兼容性说明

### 向后兼容
- ✅ 所有新增字段均为可选 (`Optional`)
- ✅ 旧版前端不使用这些字段也能正常工作
- ✅ 不影响现有 API 的其他字段

### 升级建议
1. 前端可逐步添加位置显示功能
2. 不需要一次性修改所有页面
3. 建议优先在以下页面添加:
   - 会话管理页面
   - 登录日志页面
   - API 使用统计页面

## 性能影响

- **查询速度**: < 1ms (本地 GeoLite2 数据库)
- **额外开销**: 每个 IP 查询约 0.5-1ms
- **缓存**: 当前未启用，如需优化可后续添加
- **数据库**: 无额外数据库查询

## 常见问题

### Q: 为什么某些 IP 的 location 是 null?
A: 可能原因:
- 内网 IP (192.168.x.x, 10.x.x.x)
- 无效 IP (0.0.0.0, null)
- GeoLite2 数据库中不存在该 IP
- IP 地址格式错误

### Q: 地理位置准确吗?
A: GeoLite2 免费版准确率约 95%，对于大部分公网 IP 都能正确识别国家，城市级别可能有偏差。

### Q: 可以修改查询级别吗?
A: 当前默认使用 city 级别，如需修改可在 `lookup_ip_location()` 调用时传入 `level="country"`。

### Q: 会影响 API 性能吗?
A: 影响极小，每个 IP 查询约 0.5-1ms。如果发现性能问题，可以启用 LRU 缓存。
