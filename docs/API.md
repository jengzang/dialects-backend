# 方言比较小站 - API 接口文档

本文档详细介绍了方言比较小站后端系统的所有 API 接口。

## 📋 目录

1. [接口概览](#接口概览)
2. [认证接口](#认证接口)
3. [方言查询接口](#方言查询接口)
4. [地理信息接口](#地理信息接口)
5. [自定义数据接口](#自定义数据接口)
6. [Praat 声学分析接口](#praat-声学分析接口)
7. [工具接口](#工具接口)
8. [VillagesML 机器学习接口](#villagesml-机器学习接口)
9. [管理员接口](#管理员接口)
10. [错误码说明](#错误码说明)

---

## 接口概览

系统共有 **234 个 API 端点**，按权限和功能分类：

### 按权限分类

- 🔓 **公开接口**：23 个（无需登录）
- 🔑 **用户接口**：53 个（需要登录）
- 👑 **管理员接口**：51 个（需要管理员权限）
- 🏘️ **VillagesML 接口**：107 个（机器学习分析）

### 按功能分类

#### 核心功能
- 认证接口（注册、登录、Token 管理）
- 方言查询接口（查中古、查音位、查字、查调）
- 地理信息接口（地点查询、坐标获取、区域划分）
- 自定义数据接口（用户自定义方言数据）

#### 工具模块
- Praat 声学分析（音频分析、音高检测、共鸣峰提取）
- Check 工具（数据校验、格式检查）
- Jyut2IPA 工具（粤拼转国际音标）
- Merge 工具（数据合并）

#### VillagesML 机器学习
- 搜索探索（关键词搜索、村庄详情）
- 字符分析（频率、倾向性、嵌入向量）
- 语义分析（语义类别、VTF、PMI）
- 空间分析（热点检测、密度聚类）
- 模式分析（N-gram、结构模式）
- 区域分析（三级聚合、相似度）
- ML 计算（聚类、降维、层次分析）

#### 管理员功能
- 用户管理（CRUD、封禁/解封、角色管理）
- 用户行为分析（用户分段、RFM、异常检测）
- 排行榜系统（用户排行、API 排行）
- 会话管理（活跃会话、设备追踪）
- 缓存管理（缓存清理、统计）
- 日志统计（API 使用、关键词统计）

### 基础信息

- **Base URL**：`http://localhost:5000`
- **认证方式**：JWT Bearer Token
- **请求格式**：JSON
- **响应格式**：JSON
- **字符编码**：UTF-8

---

## 认证接口

### 1. 用户注册

**接口路径**：`POST /auth/register`

**权限要求**：公开接口

**功能描述**：注册新用户账号。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | string | 是 | 用户名（3-20 字符，仅限字母数字下划线） |
| password | string | 是 | 密码（最少 6 字符） |
| email | string | 否 | 电子邮箱 |

**请求示例**：

```json
{
  "username": "testuser",
  "password": "password123",
  "email": "test@example.com"
}
```

**响应示例**：

```json
{
  "message": "User registered successfully",
  "user_id": 1,
  "username": "testuser"
}
```

**注册限制**：
- 同一 IP 10 分钟内最多注册 3 次
- 用户名 3-20 字符，仅限字母数字下划线
- 密码最少 6 字符

---

### 2. 用户登录

**接口路径**：`POST /auth/login`

**权限要求**：公开接口

**功能描述**：用户登录获取访问令牌。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**响应示例**：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**登录限制**：
- 同一 IP 每分钟最多登录 10 次
- 失败 5 次后锁定账户 15 分钟

---

## 方言查询接口

### 1. 查中古（ZhongGu）

**接口路径**：`POST /api/new_pho/ZhongGu`

**权限要求**：公开接口

**功能描述**：根据中古音韵条件筛选汉字，并查询其在各方言点的读音。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| characters | string | 否 | 汉字（留空表示根据中古条件筛选） |
| locations | array | 是 | 方言点列表 |
| zhonggu_filters | object | 是 | 中古音韵条件 |
| need_features | boolean | 否 | 是否返回音韵特征 |
| limit | integer | 否 | 返回结果数量限制 |

**请求示例**：

```json
{
  "characters": "",
  "locations": ["广州", "北京"],
  "zhonggu_filters": {
    "声母": ["帮", "滂", "並"],
    "韵部": ["东", "冬"],
    "声调": ["平声"],
    "等呼": ["一等", "三等"]
  },
  "need_features": true,
  "limit": 100
}
```

**响应示例**：

```json
{
  "characters": ["東", "公", "風", "蒙"],
  "locations": ["广州", "北京"],
  "data": [
    {
      "char": "東",
      "广州": {
        "pronunciation": "dung1",
        "ipa": "tʊŋ˥"
      },
      "北京": {
        "pronunciation": "dong1",
        "ipa": "tʊŋ˥"
      }
    }
  ]
}
```

---

## VillagesML 机器学习接口

VillagesML 系统提供 107 个 API 端点，用于分析广东省 285,860 条自然村地名数据。

### 搜索探索模块

#### 1. 搜索村庄

**接口路径**：`GET /api/villages/village/search`

**权限要求**：用户接口

**功能描述**：根据关键词和行政区划搜索村庄。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| keyword | string | 否 | 搜索关键词 |
| city | string | 否 | 市级行政区 |
| county | string | 否 | 县级行政区 |
| township | string | 否 | 乡镇级行政区 |
| limit | integer | 否 | 每页数量（默认 20） |
| offset | integer | 否 | 偏移量 |

**响应示例**：

```json
{
  "total": 1250,
  "limit": 20,
  "offset": 0,
  "villages": [
    {
      "village_id": 1,
      "name": "石岗村",
      "city": "广州市",
      "county": "白云区",
      "township": "石井街道",
      "longitude": 113.2644,
      "latitude": 23.1291
    }
  ]
}
```

---

### 字符分析模块

#### 1. 全局字符频率

**接口路径**：`GET /api/villages/character/frequency/global`

**权限要求**：用户接口

**功能描述**：统计所有字符在全省的使用频率。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| top_k | integer | 否 | 返回前 K 个高频字符（默认 100） |

**响应示例**：

```json
{
  "total_chars": 3067,
  "results": [
    {
      "char": "村",
      "frequency": 285860,
      "village_count": 285860,
      "rank": 1
    },
    {
      "char": "新",
      "frequency": 12450,
      "village_count": 12450,
      "rank": 2
    }
  ]
}
```

---

## 管理员接口

### 用户行为分析

#### 1. 用户分段

**接口路径**：`GET /admin/analytics/user-segments`

**权限要求**：管理员接口

**功能描述**：根据活跃度将用户分为 5 个等级。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| include_users | boolean | 否 | 是否包含用户详情 |

**响应示例**：

```json
{
  "segments": [
    {
      "level": "高度活跃",
      "user_count": 25,
      "criteria": "最近 7 天内访问 >= 10 次"
    },
    {
      "level": "活跃",
      "user_count": 50,
      "criteria": "最近 30 天内访问 >= 5 次"
    }
  ]
}
```

---

#### 2. RFM 分析

**接口路径**：`GET /admin/analytics/rfm-analysis`

**权限要求**：管理员接口

**功能描述**：基于 Recency、Frequency、Monetary 三维分析用户价值。

**响应示例**：

```json
{
  "user_types": [
    {
      "type": "Champions",
      "description": "冠军用户 - 高频高活跃",
      "user_count": 15,
      "avg_api_calls": 500
    },
    {
      "type": "Loyal",
      "description": "忠诚用户 - 长期稳定使用",
      "user_count": 30,
      "avg_api_calls": 200
    }
  ]
}
```

---

## 错误码说明

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（未登录或 Token 无效） |
| 403 | 禁止访问（权限不足） |
| 404 | 资源不存在 |
| 429 | 请求过于频繁（触发限流） |
| 500 | 服务器内部错误 |

### 业务错误码

| 错误码 | 说明 |
|--------|------|
| 1001 | 用户名已存在 |
| 1002 | 密码错误 |
| 1003 | 用户不存在 |
| 1004 | 账户已被锁定 |
| 1005 | Token 已过期 |
| 2001 | 数据库查询失败 |
| 2002 | 数据不存在 |
| 3001 | 文件上传失败 |
| 3002 | 文件格式不支持 |

---

## 附录

### 完整 API 端点列表

详细的 API 端点列表请参考：
- **在线文档**：http://localhost:5000/docs（Swagger UI）
- **备用文档**：http://localhost:5000/redoc（ReDoc）

### 相关文档

- **README.md** - 项目概览和功能介绍
- **docs/FEATURE_OVERVIEW.md** - VillagesML 功能详细说明（93.4KB）

---

**注意**：本文档提供了主要 API 接口的示例。完整的 234 个 API 端点详细信息请访问在线 API 文档（Swagger UI 或 ReDoc）。
