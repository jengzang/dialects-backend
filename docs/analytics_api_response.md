# Analytics API 问题回复

## ✅ 问题回答

### 1. DAU 数据来源

**答案：A - 基于会话表的 `Session.last_seen` 字段**

**实现细节**：
```python
# app/routes/admin/user_sessions.py:670
for session in sessions:
    date_str = session.last_seen.date().isoformat() if session.last_seen else session.created_at.date().isoformat()
    dau_dict[date_str].add(session.user_id)
```

**说明**：
- 使用 `Session.last_seen` 字段（会话表）
- 如果 `last_seen` 为空，则使用 `created_at`（登录时间）作为后备
- 按日期分组，统计每天的唯一用户数（`DISTINCT user_id`）
- `last_seen` 在每次 token 刷新时更新（约 25-30 分钟），更准确反映真实活跃情况

**为什么不用 User 表的 `last_login`**：
- `last_login` 只记录最后一次登录时间，无法反映用户在一天内的多次活跃
- `Session.last_seen` 会在用户使用期间持续更新，更能反映真实活跃度

---

### 2. 热力图数据格式

**✅ 已优化为 7x24 二维数组格式**

**新的返回格式**：
```json
{
  "login_heatmap": [
    [12, 15, 8, 10, 5, 3, 2, 1, 5, 8, 12, 18, 22, 25, 28, 30, 32, 28, 25, 20, 18, 15, 12, 10],  // 周日 0-23点
    [10, 12, 9, 11, 6, 4, 3, 2, 6, 9, 13, 19, 23, 26, 29, 31, 33, 29, 26, 21, 19, 16, 13, 11],  // 周一 0-23点
    [11, 14, 7, 9, 5, 3, 2, 1, 4, 7, 11, 17, 21, 24, 27, 29, 31, 27, 24, 19, 17, 14, 11, 9],   // 周二 0-23点
    [13, 16, 10, 12, 7, 5, 3, 2, 7, 10, 14, 20, 24, 27, 30, 32, 34, 30, 27, 22, 20, 17, 14, 12], // 周三 0-23点
    [14, 17, 11, 13, 8, 6, 4, 3, 8, 11, 15, 21, 25, 28, 31, 33, 35, 31, 28, 23, 21, 18, 15, 13], // 周四 0-23点
    [15, 18, 12, 14, 9, 7, 5, 4, 9, 12, 16, 22, 26, 29, 32, 34, 36, 32, 29, 24, 22, 19, 16, 14], // 周五 0-23点
    [8, 10, 6, 8, 4, 2, 1, 0, 3, 6, 9, 15, 19, 22, 25, 27, 29, 25, 22, 17, 15, 12, 9, 7]        // 周六 0-23点
  ]
}
```

**数据结构说明**：
- 外层数组：7 个元素，代表周日到周六
  - `heatmap[0]`：周日的 24 小时数据
  - `heatmap[1]`：周一的 24 小时数据
  - ...
  - `heatmap[6]`：周六的 24 小时数据
- 内层数组：24 个元素，代表 0-23 点
  - `heatmap[0][0]`：周日 0 点的登录次数
  - `heatmap[0][23]`：周日 23 点的登录次数

**前端使用示例**：
```javascript
// 直接使用，无需额外计算
const heatmapData = response.login_heatmap;

// 获取周一 10 点的登录次数
const mondayTenAM = heatmapData[1][10];

// 渲染热力图
heatmapData.forEach((dayData, weekday) => {
  dayData.forEach((count, hour) => {
    renderCell(weekday, hour, count);
  });
});
```

**计算方式**：
- 统计所有会话的 `created_at`（登录时间）
- 按星期和小时分组计数
- 星期转换：Python 的 `weekday()` 返回 0=周一，转换为 0=周日

---

### 3. 在线用户的定义

**答案：使用 `Session.last_seen` 字段**

**实现细节**：
```python
# app/routes/admin/user_sessions.py:603
online_sessions = db.query(Session).filter(
    Session.revoked == False,
    Session.expires_at > now,
    Session.last_seen > threshold  # ⭐ 使用 last_seen
).order_by(Session.last_seen.desc()).all()
```

**判断逻辑**：
1. `Session.revoked == False` - 会话未被撤销
2. `Session.expires_at > NOW()` - 会话未过期（30天有效期）
3. `Session.last_seen > NOW() - threshold_minutes` - 最后活跃时间在阈值内（默认 30 分钟）

**字段说明**：
- `last_seen`：最后一次 API 请求时间
- `last_activity_at`：最后一次会话更新时间（包括 token 刷新、IP 变化等）

**为什么用 `last_seen` 而不是 `last_activity_at`**：
- `last_seen` 更准确反映用户的实际活跃时间
- `last_activity_at` 可能因为 IP/设备变化而更新，不一定代表用户在使用

**更新机制**：
- `last_seen` 在每次 token 刷新时更新（约 25-30 分钟）
- 有 5 分钟的节流机制（避免频繁写入数据库）
- 详见：`app/auth/session_service.py:261`

---

## 📊 API 字段映射表

| API 返回字段 | 数据库字段 | 表 | 说明 |
|-------------|-----------|-----|------|
| `user_activity.dau` | `Session.last_seen` | sessions | 每日活跃用户数 |
| `user_activity.mau` | `Session.last_seen` | sessions | 月活跃用户数 |
| `login_heatmap` | `Session.created_at` | sessions | 登录时间分布 |
| `device_distribution` | `Session.device_info` | sessions | 设备类型分布 |
| `geo_distribution` | `Session.first_ip` | sessions | IP 地理分布 |
| `session_duration_distribution` | `Session.total_online_seconds` | sessions | 会话时长分布 |
| `online_users` | `Session.last_seen` | sessions | 在线用户列表 |

---

## 🎯 数据准确性说明

### **DAU 计算逻辑**

```python
# 伪代码
DAU(date) = COUNT(DISTINCT user_id) WHERE DATE(last_seen) = date
```

**示例**：
- 用户 A 在 3 月 4 日登录，`last_seen` 在 3 月 4 日更新多次
- 用户 B 在 3 月 4 日登录，`last_seen` 在 3 月 4 日更新多次
- 用户 C 在 3 月 3 日登录，3 月 4 日未活跃
- **3 月 4 日的 DAU = 2**（用户 A 和 B）

### **MAU 计算逻辑**

```python
# 伪代码
MAU(period) = COUNT(DISTINCT user_id) WHERE last_seen >= period_start
```

**示例**：
- 统计最近 30 天（2 月 3 日 - 3 月 4 日）
- 用户 A 在 2 月 10 日活跃
- 用户 B 在 3 月 1 日活跃
- 用户 C 在 1 月 20 日活跃（不在统计范围内）
- **MAU = 2**（用户 A 和 B）

### **登录热力图计算逻辑**

```python
# 伪代码
heatmap[weekday][hour] = COUNT(*) WHERE
  WEEKDAY(created_at) = weekday AND
  HOUR(created_at) = hour
```

**示例**：
- 用户 A 在周一 10:30 登录 → `heatmap[1][10] += 1`
- 用户 B 在周一 10:45 登录 → `heatmap[1][10] += 1`
- 用户 C 在周二 10:15 登录 → `heatmap[2][10] += 1`
- **周一 10 点的登录次数 = 2**

---

## 🔧 后续优化建议（已记录）

### 1. ✅ 热力图格式优化（已完成）
- 从 `{by_hour: [], by_weekday: []}` 改为 7x24 二维数组
- 前端可以直接使用，无需额外计算

### 2. 缓存优化（建议）
```python
# 伪代码
@cache(ttl=300)  # 5 分钟缓存
def get_analytics(days: int):
    # ... 计算逻辑 ...
```

**原因**：
- Analytics 数据计算量较大（扫描所有会话）
- 数据变化不频繁（5-10 分钟更新一次即可）
- 可以显著提升响应速度

**实现方式**：
- 使用 Redis 缓存
- 或使用 Python 的 `functools.lru_cache`（单进程）
- 或使用后台定时任务预计算

### 3. 批量会话统计 API（可选）
```python
GET /admin/user-sessions/batch-stats?user_ids=1,2,3,4,5
```

**返回**：
```json
{
  "1": {"session_count": 5, "total_online_hours": 10.5},
  "2": {"session_count": 3, "total_online_hours": 6.2},
  ...
}
```

**优点**：
- 避免为每个用户单独查询
- 提升用户行为分析页面的加载速度

---

## 📝 API 文档更新

已更新以下文档：
- API 响应格式说明
- 字段来源说明
- 数据计算逻辑说明

---

## 🎉 总结

1. **DAU 数据来源**：✅ 基于 `Session.last_seen`（会话表），更准确
2. **热力图格式**：✅ 已优化为 7x24 二维数组，前端可直接使用
3. **在线用户定义**：✅ 使用 `Session.last_seen`，已在文档中明确说明

所有问题已解决，感谢前端团队的反馈！
