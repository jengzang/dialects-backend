# 方言比较工具 - FastAPI 后端

<div align="center">

**Dialect Compare Tool — FastAPI Backend**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org)
[![Redis](https://img.shields.io/badge/Redis-5.0-DC382D.svg?style=flat&logo=redis&logoColor=white)](https://redis.io)

*一个专业的地理语言学数据分析与可视化平台*

[功能特性](#功能特性) • [快速开始](#快速开始) • [API文档](#api文档) • [项目结构](#项目结构) • [部署指南](#部署指南)

</div>

---

## 📖 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [API文档](#api文档)
- [数据库设计](#数据库设计)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [性能优化](#性能优化)
- [部署指南](#部署指南)
- [开发指南](#开发指南)
- [常见问题](#常见问题)
- [更新日志](#更新日志)
- [贡献指南](#贡献指南)
- [许可证](#许可证)
- [联系方式](#联系方式)

---

## 项目简介

**方言比较工具**是一个基于 FastAPI 的现代化 Web 应用后端系统，专为地理语言学研究设计。该系统提供了强大的方言音韵数据查询、分析和可视化功能，支持学术研究人员进行汉语方言的系统性研究。

### 核心价值

- 🗺️ **地理分布可视化** - 直观展示方言地理分布特征
- 🔊 **音韵特征分析** - 声母、韵母、声调系统化分析
- 📊 **数据统计分析** - 多维度数据统计与对比
- 👥 **用户协作平台** - 支持研究人员提交和分享数据
- 🔒 **安全可靠** - 完善的认证授权和数据保护机制

### 适用场景

- 汉语方言音韵学研究
- 地理语言学数据分析
- 方言地图绘制
- 语音数据库建设
- 教学演示与展示

---

## 功能特性

### 🎯 核心功能

#### 1. 音韵查询与分析

- **字音查询** - 查询汉字在不同方言点的读音
- **音位分析** - 音位到中古音、中古音到音位的双向转换
- **声调查询** - 查询特定地点的声调系统
- **特征统计** - 统计声母、韵母、声调的分布特征

#### 2. 地理信息功能

- **地点查询** - 获取方言点列表和详细信息
- **坐标查询** - 获取地点的经纬度坐标
- **分区管理** - 支持音典分区层级结构（一级/二级/三级）
- **地点匹配** - 智能模糊匹配地点名称

#### 3. 用户数据管理

- **自定义提交** - 用户可以提交自己的语音数据
- **数据审核** - 管理员审核和管理用户提交的数据
- **数据查询** - 查询和检索自定义数据
- **批量操作** - 支持批量创建、修改、删除

#### 4. 认证与授权

- **用户注册/登录** - JWT 令牌认证机制
- **角色管理** - 管理员/普通用户/匿名用户三级权限
- **邮箱验证** - 可选的邮箱验证功能
- **密码安全** - bcrypt 加密，安全可靠

#### 5. 日志与统计

- **API 调用统计** - 详细的 API 使用情况统计
- **关键词热度** - 热门查询关键词分析
- **用户行为** - 用户活跃度和行为追踪
- **访问统计** - 页面访问量统计

### 🚀 高级特性

- **实时缓存** - Redis 缓存提升查询性能
- **异步处理** - 异步日志记录和后台任务
- **数据压缩** - 自动 gzip 压缩大型响应
- **速率限制** - 防止 API 滥用
- **定时任务** - 自动数据清理和维护
- **多模式运行** - 支持本地、开发、生产三种模式

---

## 技术栈

### 后端框架

- **FastAPI 0.116.1** - 现代化的 Python Web 框架
- **Uvicorn 0.35.0** - ASGI 服务器
- **Starlette 0.47.3** - 异步 Web 框架核心

### 数据处理

- **SQLAlchemy 2.0.43** - ORM 数据库工具
- **Pandas 2.3.2** - 数据分析库
- **NumPy 2.3.2** - 科学计算库

### 数据库

- **SQLite3** - 主数据库（8个独立数据库文件）
- **Redis 5.0** - 缓存和会话管理

### 认证与安全

- **python-jose 3.3.0** - JWT 令牌处理
- **passlib 1.7.4** - 密码哈希
- **cryptography 45.0.3** - 加密库
- **bcrypt** - 密码加密算法

### 中文处理

- **OpenCC 1.1.9** - 繁简转换
- **pypinyin 0.55.0** - 汉字拼音处理

### 其他工具

- **Pydantic 2.11.7** - 数据验证
- **APScheduler 3.10.4** - 定时任务调度
- **PyInstaller 6.7.0** - 打包为可执行文件

---

## 快速开始

### 环境要求

- Python 3.12 或更高版本
- Redis 服务器（生产环境）
- 8GB+ RAM（推荐）
- 2GB+ 磁盘空间

### 安装步骤

#### 1. 克隆项目

```bash
git clone <repository-url>
cd fastapi
```

#### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 配置环境

编辑 `common/config.py`，根据需要修改配置：

```python
# 运行模式（选择一个）
python run.py -r WEB # 本地部署到服务器
python run.py -r EXE # 本地可执行模式
python run.py -r MINE # 开发环境模式

# Redis 配置（WEB 模式需要）
REDIS_HOST = "172.28.199.1"
REDIS_PORT = 6379

# 认证配置
SECRET_KEY = "your-secret-key-here"
REQUIRE_LOGIN = False  # 是否强制登录
```

#### 5. 初始化数据库

首次启动会自动创建数据库索引：

```bash
python app/sql/index_manager.py
```

#### 6. 启动服务

```bash
# 开发模式（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers 4
```

#### 7. 访问应用

- 主页：http://localhost:5000
- 管理面板：http://localhost:5000/admin
- 健康检查：http://localhost:5000/__ping

---

## API文档

### 认证接口

#### POST `/auth/register`
用户注册

**请求体：**
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```

**响应：**
```json
{
  "message": "注册成功",
  "user_id": 1
}
```

#### POST `/auth/login`
用户登录

**请求体：**
```json
{
  "username": "testuser",
  "password": "password123"
}
```

**响应：**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "role": "user"
  }
}
```

---

### 查询接口

#### POST `/api/phonology`
音韵分析（音位↔中古音转换）

**请求体：**
```json
{
  "locations": ["北京", "上海"],
  "regions": null,
  "features": ["聲母", "韻母", "聲調"],
  "group_inputs": ["組", "攝等"],
  "pho_value": ["p", "t", "k"],
  "mode": "p2s",
  "region_mode": "yindian"
}
```

**响应：**
```json
{
  "results": [
    {
      "location": "北京",
      "feature": "聲母",
      "value": "p",
      "chars": ["不", "波", "包"],
      "count": 3,
      "groups": {...}
    }
  ]
}
```

#### GET `/api/search_chars/`
查询汉字读音

**查询参数：**
- `chars`: 汉字（如："我你他"）
- `locations`: 地点列表（如："北京,上海"）
- `regions`: 分区列表（可选）

**响应：**
```json
[
  {
    "char": "我",
    "音节": ["wo3"],
    "location": "北京",
    "positions": ["蟹開一戈上,見·見•舌根·塞音"],
    "notes": ["_"]
  }
]
```

#### GET `/api/get_locs/`
获取地点列表

**查询参数：**
- `regions`: 分区（可选）
- `region_mode`: 模式（yindian/drc）

**响应：**
```json
{
  "locations": ["北京", "上海", "广州", ...],
  "count": 150
}
```

#### GET `/api/get_coordinates`
获取地点坐标

**查询参数：**
- `locations`: 地点列表
- `regions`: 分区列表

**响应：**
```json
{
  "coordinates": [
    {
      "location": "北京",
      "latitude": 39.9042,
      "longitude": 116.4074
    }
  ],
  "center": [39.9042, 116.4074],
  "zoom": 10
}
```

---

### 自定义数据接口

#### POST `/api/submit_form`
提交自定义数据（需要登录）

**请求体：**
```json
{
  "简称": "北京",
  "音典分区": "华北官话",
  "经纬度": "39.9042,116.4074",
  "声韵调": "声母",
  "特征": "塞音",
  "值": "p",
  "说明": "不送气清塞音"
}
```

#### GET `/api/get_custom`
查询自定义数据

**查询参数：**
- `locations`: 地点
- `regions`: 分区
- `features`: 特征（可选）

**响应：**
```json
[
  {
    "id": 1,
    "简称": "北京",
    "音典分区": "华北官话",
    "声韵调": "声母",
    "特征": "塞音",
    "值": "p",
    "说明": "不送气清塞音",
    "user_id": 1,
    "created_at": "2026-01-22T10:00:00"
  }
]
```

#### DELETE `/api/delete_form`
删除自定义数据（需要登录）

**查询参数：**
- `id`: 数据ID

---

### 管理员接口

#### GET `/admin/users/all`
获取所有用户（需要管理员权限）

**响应：**
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin",
      "status": "active",
      "login_count": 100,
      "created_at": "2026-01-01T00:00:00"
    }
  ]
}
```

#### GET `/admin/api-usage/api-summary`
API 使用统计摘要

**响应：**
```json
{
  "total_calls": 10000,
  "total_users": 50,
  "avg_response_time": 150.5,
  "top_apis": [
    {
      "path": "/api/search_chars/",
      "calls": 5000,
      "avg_time": 120.3
    }
  ]
}
```

---

### 日志统计接口

#### GET `/logs/keyword/top`
获取热门关键词

**查询参数：**
- `limit`: 返回数量（默认10）
- `date`: 日期（YYYY-MM-DD，可选）

**响应：**
```json
{
  "keywords": [
    {
      "keyword": "北京",
      "count": 1000,
      "date": "2026-01-22"
    }
  ]
}
```

#### GET `/logs/visits/today`
今日访问量

**响应：**
```json
{
  "today": "2026-01-22",
  "visits": 500,
  "pages": [
    {
      "path": "/",
      "visits": 300
    }
  ]
}
```

---

### SQL查询接口

#### POST `/sql/query`
通用SQL查询接口

**请求体：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "filters": {
    "簡稱": "北京"
  },
  "order_by": "漢字",
  "limit": 100,
  "offset": 0
}
```

**响应：**
```json
{
  "data": [...],
  "total": 1000,
  "page": 1,
  "pages": 10
}
```

---

### SQL数据操作接口

⚠️ **权限要求**: 以下接口仅限**管理员**使用，需要在请求Header中携带管理员Token。

#### POST `/sql/mutate`
单个记录操作（创建/更新/删除）- 🔒 管理员

**支持的操作**：
- `create` - 插入单条记录
- `update` - 更新单条记录
- `delete` - 删除单条记录

**认证**:
```
Header: Authorization: Bearer <admin_token>
```

**创建示例：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "action": "create",
  "data": {
    "漢字": "我",
    "簡稱": "北京",
    "聲母": "w",
    "音節": "wo3"
  }
}
```

**更新示例：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "action": "update",
  "pk_column": "id",
  "pk_value": 1,
  "data": {
    "聲母": "w",
    "音節": "wo3"
  }
}
```

**删除示例：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "action": "delete",
  "pk_column": "id",
  "pk_value": 1
}
```

#### POST `/sql/batch-mutate` ✨ 新功能
批量操作（批量创建/更新/删除）- 🔒 管理员

**支持的操作**：
- `batch_create` - 批量插入多条记录
- `batch_update` - 批量更新多条记录
- `batch_delete` - 批量删除多条记录

**批量创建示例：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "action": "batch_create",
  "create_data": [
    {"漢字": "我", "簡稱": "北京", "聲母": "w"},
    {"漢字": "你", "簡稱": "北京", "聲母": "n"},
    {"漢字": "他", "簡稱": "北京", "聲母": "t"}
  ]
}
```

**批量更新示例：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "action": "batch_update",
  "pk_column": "id",
  "update_data": [
    {"id": 1, "聲母": "w", "音節": "wo3"},
    {"id": 2, "聲母": "n", "音節": "ni3"}
  ]
}
```

**批量删除示例：**
```json
{
  "db_key": "dialects",
  "table_name": "dialects",
  "action": "batch_delete",
  "pk_column": "id",
  "delete_ids": [1, 2, 3, 4, 5]
}
```

**响应示例：**
```json
{
  "status": "completed",
  "action": "batch_create",
  "success_count": 3,
  "error_count": 0,
  "total": 3,
  "errors": null,
  "message": "批量操作完成: 成功 3 条, 失败 0 条"
}
```


## 数据库设计

### 数据库文件结构

```
data/
├── auth.db                 # 用户认证和授权（256KB）
├── logs.db                 # API日志和统计（变动）
├── supplements.db          # 用户自定义数据（256KB）
├── dialects_user.db        # 方言数据-用户版（489MB）
├── dialects_admin.db       # 方言数据-管理员版（503MB）
├── query_user.db           # 查询索引-用户版（1.2MB）
├── query_admin.db          # 查询索引-管理员版（1.2MB）
├── characters.db           # 汉字中古音数据（6.2MB）
└── villages.db             # 地点坐标数据（34MB）
```

### 主要数据表

#### `auth.db`

**users 表**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'user',           -- admin/user
    status TEXT DEFAULT 'active',        -- active/inactive/banned
    email_verified BOOLEAN DEFAULT 0,
    login_count INTEGER DEFAULT 0,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**api_usage_log 表**
```sql
CREATE TABLE api_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    ip_address TEXT,
    request_path TEXT,
    request_method TEXT,
    status_code INTEGER,
    response_time_ms REAL,
    request_size INTEGER,
    response_size INTEGER,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `supplements.db`

**information 表**
```sql
CREATE TABLE information (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    简称 TEXT NOT NULL,
    音典分区 TEXT,
    经纬度 TEXT,
    声韵调 TEXT NOT NULL,
    特征 TEXT NOT NULL,
    值 TEXT NOT NULL,
    说明 TEXT,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### `logs.db`

**api_keyword_log 表**
```sql
CREATE TABLE api_keyword_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    keyword TEXT NOT NULL,
    user_id INTEGER,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**api_visit_log 表**
```sql
CREATE TABLE api_visit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    visit_count INTEGER DEFAULT 1,
    date TEXT NOT NULL,
    UNIQUE(path, date)
);
```

#### `dialects_*.db`

**dialects 表**
```sql
CREATE TABLE dialects (
    id INTEGER PRIMARY KEY,
    漢字 TEXT NOT NULL,
    簡稱 TEXT NOT NULL,
    聲母 TEXT,
    韻母 TEXT,
    聲調 TEXT,
    音節 TEXT,
    多音字 INTEGER DEFAULT 0,
    註釋 TEXT
);

-- 性能优化索引
CREATE INDEX idx_dialects_char_abbr ON dialects(漢字, 簡稱);
CREATE INDEX idx_dialects_abbr ON dialects(簡稱);
CREATE INDEX idx_dialects_polyphonic ON dialects(多音字, 漢字);
CREATE INDEX idx_dialects_features ON dialects(簡稱, 聲母, 韻母, 聲調);
```

#### `characters.db`

**characters 表**
```sql
CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    漢字 TEXT NOT NULL,
    攝 TEXT,
    呼 TEXT,
    等 TEXT,
    韻 TEXT,
    調 TEXT,
    組 TEXT,
    母 TEXT,
    部位 TEXT,
    方式 TEXT,
    多地位標記 INTEGER DEFAULT 0,
    反切 TEXT
);

CREATE INDEX idx_characters_char ON characters(漢字);
CREATE INDEX idx_characters_multi ON characters(多地位標記, 漢字);
```

---

## 项目结构

```
fastapi/
├── app/                            # 应用主目录
│   ├── main.py                     # 应用入口和配置
│   │
│   ├── auth/                       # 认证授权模块
│   │   ├── __init__.py
│   │   ├── models.py               # 用户和日志模型
│   │   ├── database.py             # 数据库配置
│   │   ├── service.py              # 认证业务逻辑
│   │   ├── dependencies.py         # 依赖注入（权限验证）
│   │   └── utils.py                # JWT、密码、IP工具
│   │
│   ├── custom/                     # 自定义数据模块
│   │   ├── __init__.py
│   │   ├── models.py               # 自定义数据模型
│   │   ├── database.py             # supplements.db配置
│   │   ├── write_submit.py         # 数据提交处理
│   │   ├── read_custom.py          # 数据读取处理
│   │   └── delete.py               # 数据删除处理
│   │
│   ├── logs/                       # 日志统计模块
│   │   ├── __init__.py
│   │   ├── models.py               # 日志数据模型
│   │   ├── database.py             # logs.db配置
│   │   ├── scheduler.py            # 定时任务调度
│   │   └── migrate_from_txt.py     # 历史数据迁移
│   │
│   ├── db/                         # 数据库管理模块
│   │   ├── __init__.py
│   │   └── index_manager.py        # 自动索引管理
│   │
│   ├── routes/                     # 路由模块
│   │   ├── __init__.py
│   │   ├── index.py                # 页面路由
│   │   ├── auth.py                 # 认证接口
│   │   ├── phonology.py            # 音韵分析接口
│   │   ├── search.py               # 字符/声调查询
│   │   ├── custom_query.py         # 自定义数据查询
│   │   ├── form_submit.py          # 表单提交
│   │   ├── batch_match.py          # 地点匹配
│   │   ├── get_coordinates.py      # 坐标查询
│   │   ├── get_locs.py             # 地点列表
│   │   ├── get_regions.py          # 分区查询
│   │   ├── get_partitions.py       # 分区层级
│   │   ├── sql.py                  # SQL查询接口
│   │   ├── logs_stats.py           # 日志统计接口
│   │   ├── new_pho.py              # 新音韵接口
│   │   └── admin/                  # 管理员接口
│   │       ├── __init__.py
│   │       ├── users.py            # 用户管理
│   │       ├── custom.py           # 自定义数据管理
│   │       ├── custom_edit.py      # 数据编辑
│   │       ├── api_usage.py        # API使用统计
│   │       ├── login_logs.py       # 登录日志
│   │       ├── user_stats.py       # 用户统计
│   │       └── get_ip.py           # IP查询代理
│   │
│   ├── service/                    # 业务服务层
│   │   ├── __init__.py
│   │   ├── api_logger.py           # 异步日志记录
│   │   ├── match_input_tip.py      # 地点智能匹配
│   │   ├── search_chars.py         # 字符搜索服务
│   │   ├── phonology2status.py     # 音韵转换服务
│   │   ├── status_arrange_pho.py   # 中古地位查询
│   │   ├── locs_regions.py         # 地点分区关联
│   │   ├── process_sp_input.py     # 输入处理
│   │   ├── search_tones.py         # 声调搜索
│   │   └── new_pho.py              # 新音韵系统
│   │
│   ├── schemas/                    # Pydantic Schema
│   │   ├── __init__.py
│   │   ├── auth.py                 # 认证Schema
│   │   ├── form.py                 # 表单Schema
│   │   ├── phonology.py            # 音韵Schema
│   │   ├── coordinates.py          # 坐标Schema
│   │   ├── admin.py                # 管理员Schema
│   │   ├── query_custom.py         # 自定义查询Schema
│   │   └── sql.py                  # SQL查询Schema
│   │
│   ├── statics/                    # 前端静态资源
│   │   ├── index.html              # 主页
│   │   ├── config.js               # 前端配置
│   │   ├── assets/                 # Vite编译资源
│   │   │   ├── main.*.js
│   │   │   └── main.*.css
│   │   ├── admin/                  # 管理后台页面
│   │   │   └── index.html
│   │   ├── auth/                   # 认证页面
│   │   │   └── index.html
│   │   ├── detail/                 # 详情页
│   │   │   └── index.html
│   │   ├── intro/                  # 介绍页
│   │   │   └── index.html
│   │   ├── menu/                   # 菜单页
│   │   │   └── index.html
│   │   └── [Leaflet地图资源]
│   │
│   └── redis_client.py             # Redis客户端封装
│
├── common/                         # 公共工具模块
│   ├── __init__.py
│   ├── config.py                   # 全局配置管理
│   ├── constants.py                # 常量定义
│   ├── s2t.py                      # 简繁转换工具
│   ├── getloc_by_name_region.py    # 地点查询工具
│   └── search_tones.py             # 声调查询工具
│
├── data/                           # 数据库文件目录
│   ├── auth.db                     # 用户认证数据库
│   ├── logs.db                     # 日志统计数据库
│   ├── supplements.db              # 自定义数据数据库
│   ├── dialects_user.db            # 方言数据-用户版
│   ├── dialects_admin.db           # 方言数据-管理员版
│   ├── query_user.db               # 查询索引-用户版
│   ├── query_admin.db              # 查询索引-管理员版
│   ├── characters.db               # 汉字中古音数据
│   ├── villages.db                 # 地点坐标数据
│   └── dependency/                 # 依赖数据文件
│       ├── 正字.tsv
│       └── mulcodechar.dt
│
├── logs/                           # 日志文件目录
│   ├── api_keywords_log.txt        # API关键词日志
│   ├── api_keywords_summary.txt    # 关键词汇总
│   ├── api_usage_stats.txt         # API使用统计
│   └── api_detailed_stats.json     # 详细统计JSON
│
├── requirements.txt                # Python依赖列表
├── README.md                       # 本文档
├── OPTIMIZATION_SUMMARY.md         # 性能优化文档
├── OPTIMIZATION_QUICKREF.md        # 优化快速参考
├── SQL_MUTATE_API_GUIDE.md         # SQL操作API详细指南
├── test_optimizations.py           # 优化测试脚本
├── test_batch_mutate.py            # 批量操作测试脚本
└── .gitignore                      # Git忽略配置
```

---

## 配置说明

### 主配置文件：`common/config.py`

#### 运行模式配置

```python
# 选择运行模式
_RUN_TYPE = 'WEB'   # 生产环境（使用真实Redis）
# _RUN_TYPE = 'MINE'  # 开发环境（本地IP）
# _RUN_TYPE = 'EXE'   # 打包可执行文件
```

#### 数据库路径配置

```python
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 方言数据库
DIALECTS_DB_USER = os.path.join(BASE_DIR, "data", "dialects_user.sql")
DIALECTS_DB_ADMIN = os.path.join(BASE_DIR, "data", "dialects_admin.sql")

# 字符数据库
CHARACTERS_DB_PATH = os.path.join(BASE_DIR, "data", "characters.sql")

# 用户数据库
USER_DATABASE_PATH = os.path.join(BASE_DIR, "data", "auth.sql")

# 日志数据库
LOGS_DATABASE_PATH = os.path.join(BASE_DIR, "data", "logs.sql")

# 自定义数据库
SUPPLE_DB_PATH = os.path.join(BASE_DIR, "data", "supplements.sql")
```

#### 认证配置

```python
# JWT配置
SECRET_KEY = "super-secret-key"              # ⚠️ 生产环境必须修改
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 100000         # 令牌有效期

# 认证要求
REQUIRE_LOGIN = False                        # 是否强制登录
REQUIRE_EMAIL_VERIFICATION = False           # 是否需要邮箱验证

# 注册限制
MAX_REGISTRATIONS_PER_IP = 3                 # 单IP注册次数限制
REGISTRATION_WINDOW_MINUTES = 10             # 时间窗口（分钟）

# 登录限制
MAX_LOGIN_PER_MINUTE = 10                    # 每分钟最多登录次数
```

#### API限制配置

```python
# 使用配额（秒/小时）
MAX_USER_USAGE_PER_HOUR = 2000               # 认证用户配额
MAX_IP_USAGE_PER_HOUR = 300                  # 匿名IP配额

# 响应大小限制
MAX_ANONYMOUS_SIZE = 1024 * 1024             # 匿名用户：1MB
MAX_USER_SIZE = 6 * 1024 * 1024              # 认证用户：6MB

# 压缩阈值
SIZE_THRESHOLD = 10 * 1024                   # 10KB以上自动压缩
```

#### 日志配置

```python
# 日志记录配置
BATCH_SIZE = 20                              # 批量写入大小
CACHE_EXPIRATION_TIME = 3600                 # 缓存过期时间（秒）
CLEAR_WEEK = True                            # 是否清理旧日志

# 记录的API路径
RECORD_API = [
    "phonology",
    "get_coordinates",
    "search_tones",
    "search_chars",
    "submit_form",
    "delete_form",
    "ZhongGu",
    "YinWei",
    "charlist",
    "sql/query"
]
```

#### Redis配置（WEB模式）

```python
if _RUN_TYPE == 'WEB':
    REDIS_HOST = "172.28.199.1"
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_DECODE_RESPONSES = True
```

---

## 性能优化

本项目经过系统性能优化，查询性能提升显著。详见 

### 优化措施

#### 1. 数据库索引自动管理 ⚡

**实施文件**: `app/db/index_manager.py`

应用启动时自动创建7个关键索引：

```python
# 复合索引（最重要）
CREATE INDEX idx_dialects_char_abbr ON dialects(漢字, 簡稱);

# 单列索引
CREATE INDEX idx_dialects_abbr ON dialects(簡稱);
CREATE INDEX idx_dialects_polyphonic ON dialects(多音字, 漢字);
CREATE INDEX idx_dialects_features ON dialects(簡稱, 聲母, 韻母, 聲調);
CREATE INDEX idx_dialects_char ON dialects(漢字);

# 字符表索引
CREATE INDEX idx_characters_char ON characters(漢字);
CREATE INDEX idx_characters_multi ON characters(多地位標記, 漢字);
```

**效果**: 查询性能提升 40-50%

#### 2. 消除N+1查询问题 ⚡⚡

**实施文件**: `app/service/search_chars.py`

**优化前**: 嵌套循环导致 5000+ 次查询（100字 × 50地点）
**优化后**: 3次批量查询

```python
# 批量查询示例
WHERE (漢字, 簡稱) IN (
    ('我', '北京'), ('我', '上海'), ('你', '北京'), ...
)
```

**效果**:
- 查询次数减少 99.9%（5000+ → 3次）
- 响应时间提升 92%（2500ms → 150ms）

#### 3. 合并重复表扫描 ⚡⚡

**实施文件**: `app/service/phonology2status.py`

**优化前**: 3次独立查询（声母、韵母、声调）
**优化后**: 1次UNION ALL查询

```sql
SELECT 簡稱, '聲母' as type, 聲母, COUNT(DISTINCT 漢字)
FROM dialects WHERE 簡稱 IN (...)
UNION ALL
SELECT 簡稱, '韻母' as type, 韻母, COUNT(DISTINCT 漢字)
FROM dialects WHERE 簡稱 IN (...)
UNION ALL
SELECT 簡稱, '聲調' as type, 聲調, COUNT(DISTINCT 漢字)
FROM dialects WHERE 簡稱 IN (...)
```

**效果**:
- 查询次数减少 66%（3次 → 1次）
- 响应时间提升 66%（300ms → 100ms）

#### 4. Redis缓存策略

```python
# 用户信息缓存（1小时）
@lru_cache(maxsize=1000)
def get_user_from_cache(user_id: int):
    return redis_client.get(f"user:{user_id}")

# 查询结果缓存（10分钟）
@cache(expire=600)
def get_phonology_result(params):
    return execute_query(params)
```

#### 5. 异步处理

```python
# API日志异步写入
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_api_logger_workers(db)  # 启动后台线程
    yield
    stop_api_logger_workers()     # 停止后台线程

# CPU密集任务异步化
from starlette.concurrency import run_in_threadpool
result = await run_in_threadpool(cpu_intensive_task, params)
```

#### 6. 响应压缩

```python
# 自动gzip压缩（10KB阈值）
class TrafficLoggingMiddleware:
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if len(response.body) > SIZE_THRESHOLD:
            response.body = gzip.compress(response.body)
            response.headers["content-encoding"] = "gzip"
        return response
```

### 性能对比

| 指标 | 优化前 | 优化后 | 提升幅度 |
|------|--------|--------|---------|
| `/search_chars/` 响应时间 | ~2500ms | ~150ms | **92% ⬇️** |
| `/phonology` 响应时间 | ~300ms | ~100ms | **66% ⬇️** |
| 每请求数据库查询次数 | 5000+ | 3-4 | **99.9% ⬇️** |
| 数据库总负载 | 高 | 低 | **90%+ ⬇️** |

---

## 部署指南

### 开发环境部署

```bash
# 1. 克隆项目
git clone <repository-url>
cd fastapi

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置开发模式
# 编辑 common/config.py
_RUN_TYPE = 'MINE'

# 4. 启动开发服务器（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### 生产环境部署

#### 方案1：使用 Uvicorn + Supervisor

**1. 安装Supervisor**

```bash
pip install supervisor
```

**2. 创建配置文件** `supervisord.conf`

```ini
[program:fastapi]
command=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers 4
directory=/path/to/fastapi
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/fastapi.log
```

**3. 启动服务**

```bash
supervisord -c supervisord.conf
supervisorctl status
```

#### 方案2：使用 Gunicorn + Nginx

**1. 安装Gunicorn**

```bash
pip install gunicorn
```

**2. 启动Gunicorn**

```bash
gunicorn app.main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --access-logfile /var/log/gunicorn-access.log \
    --error-logfile /var/log/gunicorn-error.log
```

**3. 配置Nginx反向代理** `/etc/nginx/sites-available/fastapi`

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /statics {
        alias /path/to/fastapi/app/statics;
    }
}
```

**4. 启用配置并重启Nginx**

```bash
ln -s /etc/nginx/sites-available/fastapi /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

#### 方案3：Docker部署

**1. 创建 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4"]
```

**2. 创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  fastapi:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - RUN_TYPE=WEB
      - REDIS_HOST=redis
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

**3. 启动容器**

```bash
docker-compose up -d
docker-compose logs -f
```

### 打包为可执行文件（EXE模式）

```bash
# 1. 安装PyInstaller
pip install pyinstaller

# 2. 配置EXE模式
# 编辑 common/config.py
_RUN_TYPE = 'EXE'

# 3. 打包
pyinstaller --onefile \
    --add-data "data:data" \
    --add-data "app/statics:app/statics" \
    --hidden-import uvicorn \
    --hidden-import fastapi \
    app/main.py

# 4. 运行
./dist/main.exe
```

---

## 开发指南

### 环境设置

```bash
# 1. 创建开发分支
git checkout -b feature/your-feature

# 2. 安装开发依赖
pip install -r requirements-dev.txt

# 3. 配置pre-commit hooks
pre-commit install
```

### 代码规范

#### Python代码风格

遵循 PEP 8 规范：

```python
# 使用black格式化
black app/

# 使用flake8检查
flake8 app/

# 使用mypy类型检查
mypy app/
```

#### 命名规范

- **文件名**: 小写+下划线（`search_chars.py`）
- **类名**: 大驼峰（`UserModel`）
- **函数名**: 小写+下划线（`get_user_info`）
- **常量**: 大写+下划线（`MAX_LOGIN_ATTEMPTS`）

### 添加新接口

#### 1. 创建Schema（`app/schemas/`）

```python
# app/schemas/my_feature.py
from pydantic import BaseModel

class MyRequest(BaseModel):
    param1: str
    param2: int

class MyResponse(BaseModel):
    result: str
    data: list
```

#### 2. 实现业务逻辑（`app/service/`）

```python
# app/service/my_service.py
def process_my_feature(param1: str, param2: int):
    # 业务逻辑
    result = do_something(param1, param2)
    return result
```

#### 3. 创建路由（`app/routes/`）

```python
# app/routes/my_feature.py
from fastapi import APIRouter, Depends
from app.schemas.my_feature import MyRequest, MyResponse
from app.service.my_service import process_my_feature
from app.auth.dependencies import get_current_user

router = APIRouter()

@router.post("/my-feature", response_model=MyResponse)
async def my_feature_endpoint(
    request: MyRequest,
    current_user = Depends(get_current_user)
):
    result = process_my_feature(request.param1, request.param2)
    return MyResponse(result=result, data=[])
```

#### 4. 注册路由（`app/routes/__init__.py`）

```python
from app.routes.my_feature import router as my_feature_router

def setup_routes(app):
    # ... 其他路由
    app.include_router(my_feature_router, prefix="/api", tags=["my-feature"])
```

### 数据库迁移

添加新表或修改表结构：

```python
# 1. 修改models.py
class NewModel(Base):
    __tablename__ = "new_table"
    id = Column(Integer, primary_key=True)
    name = Column(String)

# 2. 创建迁移脚本
# app/migrations/create_new_table.py
def upgrade(conn):
    conn.execute("""
        CREATE TABLE new_table (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

def downgrade(conn):
    conn.execute("DROP TABLE new_table")
```

### 测试

#### 单元测试

```python
# tests/test_my_feature.py
import pytest
from app.service.my_service import process_my_feature

def test_process_my_feature():
    result = process_my_feature("test", 123)
    assert result is not None
    assert result["status"] == "success"
```

#### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_my_feature.py

# 查看覆盖率
pytest --cov=app tests/
```

### 调试技巧

#### 1. 使用日志

```python
import logging

logger = logging.getLogger(__name__)

@router.get("/debug")
async def debug_endpoint():
    logger.info("处理请求")
    logger.debug(f"参数: {params}")
    logger.error("发生错误")
```

#### 2. 使用断点调试

```python
# 在VSCode中设置断点，然后启动调试配置

# .vscode/launch.json
{
    "configurations": [
        {
            "name": "FastAPI Debug",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "app.main:app",
                "--reload"
            ]
        }
    ]
}
```

#### 3. 使用FastAPI文档

启用Swagger UI进行API测试：

```python
# app/main.py
app = FastAPI(
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc"     # ReDoc
)
```

访问 http://localhost:5000/docs

---

## 常见问题

### Q1: 启动时提示 "数据库文件不存在"

**A:** 确保 `data/` 目录下有所有必需的数据库文件。首次部署需要从备份恢复数据库。

```bash
# 检查数据库文件
ls -lh data/*.sql

# 如果缺少文件，从备份恢复
cp backup/*.sql data/
```

### Q2: Redis连接失败

**A:** 检查Redis服务是否运行，以及配置是否正确。

```bash
# 检查Redis状态
redis-cli ping

# 如果使用Docker
docker ps | grep redis

# 测试连接
redis-cli -h 172.28.199.1 -p 6379 ping
```

如果是开发环境，可以切换到 `MINE` 模式使用虚拟Redis。

### Q3: API响应慢

**A:** 检查以下几点：

1. **数据库索引是否创建**
```python
python app/db/index_manager.py
```

2. **Redis缓存是否工作**
```python
# 检查缓存命中率
redis-cli INFO stats | grep keyspace
```

3. **数据库大小是否过大**
```bash
# 清理旧日志
sqlite3 data/logs.sql "DELETE FROM api_keyword_log WHERE created_at < datetime('now', '-30 days')"
```

### Q4: 用户无法注册

**A:** 检查注册限制配置：

```python
# common/config.py
MAX_REGISTRATIONS_PER_IP = 3          # 增加限制
REGISTRATION_WINDOW_MINUTES = 10      # 增加时间窗口

# 或者检查数据库
sqlite3 data/auth.db "SELECT * FROM users WHERE username='testuser'"
```

### Q5: JWT令牌验证失败

**A:** 检查令牌配置和有效期：

```python
# 生成新的SECRET_KEY
import secrets
print(secrets.token_urlsafe(32))

# 更新config.py
SECRET_KEY = "新生成的密钥"

# 检查令牌有效期
ACCESS_TOKEN_EXPIRE_MINUTES = 100000
```

### Q6: 查询结果为空

**A:** 检查数据库选择和权限：

```python
# 确认用户角色
current_user.role  # 'admin' 或 'user'

# 管理员使用admin数据库
db_path = DIALECTS_DB_ADMIN if current_user.role == 'admin' else DIALECTS_DB_USER

# 检查数据库内容
sqlite3 data/dialects_user.db "SELECT COUNT(*) FROM dialects WHERE 簡稱='北京'"
```

### Q7: 打包EXE后无法运行

**A:** 检查资源文件是否正确打包：

```bash
# 确保添加所有数据文件
pyinstaller --onefile \
    --add-data "data:data" \
    --add-data "app/statics:app/statics" \
    --add-data "common:common" \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops.auto \
    app/main.py
```

### Q8: CORS错误

**A:** 检查CORS配置：

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 更新日志

### v1.0.1 (2026-01-22)

#### 🚀 性能优化
- 实现自动数据库索引管理（提升40-50%性能）
- 优化N+1查询问题（查询次数减少99.9%）
- 合并重复表扫描（响应时间提升66%）
- 整体API响应速度提升5-10倍

#### ✨ 新增功能
- 添加日志统计接口（`/logs/*`）
- 添加SQL通用查询接口（`/sql/query`）
- 添加SQL批量操作接口（`/sql/batch-mutate`）✨
  - 支持批量创建记录
  - 支持批量更新记录
  - 支持批量删除记录
  - 详细的错误追踪和统计
- 添加新音韵分析系统（`/api/new_pho`）
- 支持批量地点匹配（`/api/batch_match`）

#### 🐛 Bug修复
- 修复多音字查询不完整的问题
- 修复自定义数据删除权限检查
- 修复Redis连接异常处理
- 修复日志记录重复写入

#### 🔧 改进
- 改进异步日志写入机制
- 优化Redis缓存策略
- 增强错误处理和日志记录
- 改进API限流逻辑

### v1.0.0 (2025-08-18)

#### 🎉 初始版本
- 完整的方言查询功能
- 用户认证和授权系统
- 管理员后台
- 自定义数据提交
- 基础日志记录

---

## 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **Fork本项目**
2. **创建特性分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **开启Pull Request**

### 贡献类型

- 🐛 报告Bug
- ✨ 提出新功能建议
- 📝 改进文档
- 💻 提交代码
- 🎨 改进UI/UX
- 🌐 翻译

### 代码审查标准

- 遵循PEP 8代码规范
- 添加适当的注释和文档
- 包含单元测试
- 通过所有现有测试
- 更新相关文档

### 报告Bug

提交Issue时请包含：

- 详细的问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（操作系统、Python版本等）
- 相关日志或截图

---

## 许可证

本项目采用 **MIT License** 许可证。

```
MIT License

Copyright (c) 2025 不羈 (JengZang)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 联系方式

### 开发者

**不羈 (JengZang)**

- 📧 Email: [jengzang@outlook.com]
- 🌐 Website: [dialects.yzup.top]
- 💬 GitHub: [[jengzang](https://github.com/jengzang)]

### 项目链接

- 📦 项目仓库: [[fastapi](https://github.com/jengzang/fastapi)]
- 📖 文档: [Documentation URL]
- 🐛 问题追踪: [[Issue](https://github.com/jengzang/fastapi/issues)s]
- 💡 讨论区: [Discussions URL]

---

## 致谢

感谢以下开源项目和工具：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的Python Web框架
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL工具包
- [Pandas](https://pandas.pydata.org/) - 数据分析库
- [Redis](https://redis.io/) - 内存数据库
- [OpenCC](https://github.com/BYVoid/OpenCC) - 中文简繁转换
- [Leaflet](https://leafletjs.com/) - 开源地图库

特别感谢所有为本项目做出贡献的开发者和研究人员！


---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个Star！⭐**

Made with ❤️ by 不羈 (JengZang) | © 2025

[返回顶部](#方言比较工具---fastapi-后端)

</div>
