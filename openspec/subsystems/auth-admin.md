# Auth 与 Admin 规格

> Status: active  
> Scope: `app/routes/auth.py`, `app/routes/admin`, `app/service/auth`, `app/service/admin`

## 1. 负责范围

本子系统负责：

- 用户认证
- JWT / Refresh Token / Session
- 登录日志与会话控制
- 管理员用户管理
- 管理员分析、监控、排行榜、设备与会话管理

主要代码边界：

- `app/routes/auth.py`
- `app/routes/admin/`
- `app/service/auth/`
- `app/service/admin/`

## 2. 认证模型

当前仓库的认证体系不是单一 token 校验，而是：

- Access Token
- Refresh Token
- Session
- 权限与缓存

### 规则

1. 涉及“踢下线、登出、会话数限制、设备管理”的功能，应优先从 Session 语义出发，而不是只看 Refresh Token。
2. 认证逻辑修改应同时考虑：
   - 登录
   - refresh
   - logout
   - admin revoke
   - 权限依赖

## 3. Admin 边界

`admin` 子系统负责管理员可见的后台能力，不应与普通用户接口混杂。

### 规则

1. 管理员接口统一保持在 `app/routes/admin/`。
2. 若只是普通用户可见统计，不应放到 `admin`。
3. 若涉及监控、风控、设备、排行榜、管理视角统计，应优先进入 `admin`。

## 4. 数据依赖

该子系统主要依赖：

- `auth.db`
- `logs.db`

### 规则

1. 修改认证逻辑时，应评估是否影响 `auth.db` 中会话、token、usage、login log 等表。
2. 修改后台统计时，应评估是否影响 `logs.db` 或统计写入管线。

## 5. 缓存与权限

`app/service/auth/security/` 负责权限缓存与安全相关逻辑。

### 规则

1. 权限结果可缓存，但缓存不能改变权限真值来源。
2. 任何涉及身份态的缓存，都必须明确失效条件。

## 6. 变更检查清单

改动本子系统时，至少检查：

- Session 与 Token 语义是否一致
- Admin 行为是否会越权或绕过用户态约束
- 是否影响日志/usage 统计
- 是否需要同步更新认证相关长期规则
