# 在线用户 vs 活跃会话 - 概念区分

## 📊 核心概念对比

### 1. **活跃会话（Active Session）**

**定义**：会话未被撤销且未过期

**判断条件**：
```python
Session.revoked == False AND Session.expires_at > NOW()
```

**特点**：
- ✅ 用户已登录
- ✅ Token 未过期（30天有效期）
- ❌ **不代表用户正在使用系统**

**使用场景**：
- 统计有多少个有效登录会话
- 管理会话生命周期
- 安全审计（查看所有未撤销的会话）

**API 示例**：
```bash
GET /admin/user-sessions/stats
# 返回 active_sessions: 150
```

---

### 2. **在线用户（Online User）**

**定义**：最近 N 分钟内有 API 请求的用户

**判断条件**：
```python
Session.revoked == False
AND Session.expires_at > NOW()
AND Session.last_seen > NOW() - INTERVAL '30 minutes'  # 默认 30 分钟
```

**特点**：
- ✅ 用户已登录
- ✅ Token 未过期
- ✅ **用户正在活跃使用系统**（最近30分钟内有操作）

**使用场景**：
- 实时监控当前在线人数
- 显示"谁在线"列表
- 实时客服/聊天功能

**API 示例**：
```bash
GET /admin/user-sessions/online-users?threshold_minutes=30
# 返回 online_count: 45
```

**⚠️ 重要说明**：
- `last_seen` 在 token 刷新时更新（约每 25-30 分钟）
- 默认阈值设为 30 分钟，确保正常使用的用户都能被识别为在线
- 如果设置过短（如 5 分钟），会导致大量正在使用的用户被误判为"不在线"

---

## 🔄 `last_seen` 字段的更新机制

### **更新时机**

`Session.last_seen` 字段在以下情况下更新：

#### 1. **Token 刷新时（主要更新机制）**

**触发条件**：
- 前端调用 `POST /auth/refresh` 刷新 access token
- 通常每 30 分钟刷新一次（access token 过期前）

**更新逻辑**（`app/auth/session_service.py:261`）：
```python
def refresh_access_token(...):
    # ... 验证逻辑 ...

    # 判断是否需要更新（节流机制）
    needs_update = (
        ip_changed or
        device_changed or
        should_update_session(session)  # 距离上次更新 > 5分钟
    )

    if needs_update:
        session.last_seen = datetime.utcnow()  # ⭐ 更新 last_seen
        session.last_activity_at = datetime.utcnow()
        session.refresh_count += 1
        db.commit()
```

#### 2. **节流机制（Throttling）**

为了减少数据库写入压力，`last_seen` 不是每次 API 请求都更新，而是：

**更新条件**（`app/auth/session_service.py:62-72`）：
```python
def should_update_session(session: Session) -> bool:
    """
    只有距离上次更新超过 5 分钟，才更新 session
    """
    if not session.last_activity_at:
        return True

    time_since_update = datetime.utcnow() - session.last_activity_at
    return time_since_update.total_seconds() > 300  # 5分钟
```

**节流策略**：
- 如果距离上次更新 < 5 分钟：跳过更新
- 如果距离上次更新 ≥ 5 分钟：更新 `last_seen`
- 如果 IP 或设备变化：立即更新（安全考虑）

---

## 📈 实际场景示例

### **场景 1：用户持续使用系统**

```
时间线：
10:00 - 用户登录，创建 Session
10:30 - Token 刷新，last_seen 更新为 10:30
11:00 - Token 刷新，last_seen 更新为 11:00
11:30 - Token 刷新，last_seen 更新为 11:30

查询时间：11:32
- 活跃会话：✅ 是（expires_at = 3月4日 10:00）
- 在线用户：✅ 是（last_seen = 11:30，距今 2 分钟）
```

---

### **场景 2：用户登录后关闭浏览器**

```
时间线：
10:00 - 用户登录，创建 Session
10:30 - Token 刷新，last_seen 更新为 10:30
10:35 - 用户关闭浏览器，不再有 API 请求

查询时间：10:45
- 活跃会话：✅ 是（expires_at = 3月4日 10:00，未过期）
- 在线用户：✅ 是（last_seen = 10:30，距今 15 分钟，< 30分钟阈值）

查询时间：11:05
- 活跃会话：✅ 是
- 在线用户：❌ 否（last_seen = 10:30，距今 35 分钟，> 30分钟阈值）
```

**说明**：
- 会话仍然有效（30天内可以继续使用）
- 用户关闭浏览器后 30 分钟内仍被视为"在线"（合理的缓冲期）
- 超过 30 分钟后才被判定为"不在线"

---

### **场景 3：用户长时间挂机**

```
时间线：
10:00 - 用户登录，创建 Session
10:30 - Token 刷新，last_seen 更新为 10:30
10:35 - 用户离开电脑，浏览器保持打开
11:00 - Token 自动刷新（前端定时器），last_seen 更新为 11:00
11:30 - Token 自动刷新，last_seen 更新为 11:30

查询时间：11:32
- 活跃会话：✅ 是
- 在线用户：✅ 是（last_seen = 11:30，距今 2 分钟）
```

**说明**：
- 即使用户没有实际操作，只要前端定时刷新 token，就会被判定为"在线"
- 这是合理的，因为浏览器标签页仍然打开

---

### **场景 4：用户在两次 token 刷新之间**

```
时间线：
10:00 - 用户登录，Token 刷新，last_seen 更新为 10:00
10:15 - 用户正在使用系统（浏览、点击等）
10:20 - 用户仍在使用，但 token 还没到刷新时间

查询时间：10:20
- 活跃会话：✅ 是
- 在线用户：✅ 是（last_seen = 10:00，距今 20 分钟，< 30分钟阈值）

查询时间：10:35
- 活跃会话：✅ 是
- 在线用户：❌ 否（last_seen = 10:00，距今 35 分钟，> 30分钟阈值）
  但如果此时 token 刷新，last_seen 会更新，又变为在线
```

**说明**：
- 30 分钟阈值与 token 刷新周期（25-30分钟）匹配
- 正常使用的用户不会被误判为"不在线"

---

### **场景 5：用户主动登出**

```
时间线：
10:00 - 用户登录，创建 Session
10:30 - Token 刷新，last_seen 更新为 10:30
10:35 - 用户点击"登出"，Session.revoked = True

查询时间：10:36
- 活跃会话：❌ 否（revoked = True）
- 在线用户：❌ 否（revoked = True）
```

---

## 🎯 两者的关系

```
┌─────────────────────────────────────────┐
│         所有 Session 记录               │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │      活跃会话（Active Sessions）   │  │
│  │  (revoked=False, not expired)    │  │
│  │                                   │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │   在线用户（Online Users）   │  │  │
│  │  │  (last_seen < 5 min ago)   │  │  │
│  │  │                             │  │  │
│  │  │   实际正在使用系统的用户      │  │  │
│  │  └─────────────────────────────┘  │  │
│  │                                   │  │
│  │   已登录但暂时不活跃的用户          │  │
│  └───────────────────────────────────┘  │
│                                         │
│   已撤销或过期的会话                     │
└─────────────────────────────────────────┘
```

**包含关系**：
- 在线用户 ⊆ 活跃会话 ⊆ 所有会话
- 在线用户一定是活跃会话
- 活跃会话不一定是在线用户

---

## 📊 数据对比示例

假设系统有以下数据：

| 用户 | Session 状态 | last_seen | 活跃会话 | 在线用户 (30分钟阈值) |
|------|-------------|-----------|---------|---------------------|
| Alice | revoked=False, expires_at=3月10日 | 11:58 | ✅ | ✅ (2分钟前) |
| Bob | revoked=False, expires_at=3月10日 | 11:30 | ✅ | ❌ (30分钟前，刚好到阈值) |
| Carol | revoked=False, expires_at=3月10日 | 11:45 | ✅ | ✅ (15分钟前) |
| Dave | revoked=True | 11:55 | ❌ | ❌ (已登出) |
| Eve | revoked=False, expires_at=2月28日 | 11:50 | ❌ | ❌ (已过期) |

**统计结果**（查询时间：12:00）：
- 总会话数：5
- 活跃会话数：3（Alice, Bob, Carol）
- 在线用户数：2（Alice, Carol）

---

## 🔧 配置参数

### **在线判断阈值**

可以通过 API 参数调整：

```bash
# 30分钟内有活动 = 在线（默认，推荐）
GET /admin/user-sessions/online-users?threshold_minutes=30

# 60分钟内有活动 = 在线（更宽松）
GET /admin/user-sessions/online-users?threshold_minutes=60

# 15分钟内有活动 = 在线（更严格）
GET /admin/user-sessions/online-users?threshold_minutes=15

# 5分钟内有活动 = 在线（非常严格，不推荐）
GET /admin/user-sessions/online-users?threshold_minutes=5
```

**⚠️ 重要提示**：
- Token 刷新周期约为 25-30 分钟
- 阈值应 ≥ 30 分钟，否则会漏掉正在使用的用户
- 推荐值：30-60 分钟

### **Session 更新节流**

在 `app/auth/session_service.py` 中配置：

```python
def should_update_session(session: Session) -> bool:
    # 当前设置：5分钟
    return time_since_update.total_seconds() > 300

    # 可以调整为其他值：
    # 1分钟：> 60
    # 10分钟：> 600
```

---

## 💡 最佳实践建议

### **1. 前端实现**

**推荐**：使用定时器定期刷新 token

```javascript
// 每 25 分钟刷新一次 token（access token 30分钟过期）
setInterval(async () => {
  await refreshToken();
}, 25 * 60 * 1000);
```

**效果**：
- 保持用户"在线"状态
- 避免 token 过期导致的登出

---

### **2. 在线用户监控**

**推荐阈值**：
- **一般监控**：30 分钟（默认，推荐）⭐
- **宽松统计**：60 分钟
- **严格监控**：15 分钟
- ~~**实时聊天/客服**：5 分钟（不推荐，会漏掉很多用户）~~

**说明**：
- 由于 `last_seen` 更新频率为 25-30 分钟
- 阈值 < 30 分钟会导致误判
- 如需更精确的在线判断，需要修改 `last_seen` 更新机制（增加数据库压力）

---

### **3. 性能优化**

**问题**：频繁更新 `last_seen` 会增加数据库写入压力

**解决方案**：
1. ✅ 已实现节流机制（5分钟更新一次）
2. ✅ 只在 IP/设备变化时强制更新
3. 可选：使用 Redis 缓存在线用户列表

---

## 🎯 总结

| 维度 | 活跃会话 | 在线用户 |
|------|---------|---------|
| **定义** | 未撤销且未过期的会话 | 最近 N 分钟有活动的会话 |
| **判断依据** | revoked, expires_at | revoked, expires_at, last_seen |
| **默认阈值** | - | 30 分钟 |
| **更新频率** | 每次 token 刷新（约30分钟） | 每次 token 刷新（节流5分钟） |
| **数量关系** | 较多 | 较少（活跃会话的子集） |
| **使用场景** | 会话管理、安全审计 | 实时监控、在线状态 |
| **API** | `/stats` | `/online-users` |

**关键区别**：
- **活跃会话**：用户"可以"使用系统（有有效 token）
- **在线用户**：用户"正在"使用系统（最近有操作）

**⚠️ 重要提醒**：
- 在线判断阈值应与 token 刷新周期匹配
- 默认 30 分钟阈值确保正常使用的用户不会被误判
- 如需更精确的在线判断（如 5 分钟），需要修改 `last_seen` 更新机制
