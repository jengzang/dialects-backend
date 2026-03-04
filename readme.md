# 方言比较小站 - 后端 API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.1-brightgreen.svg)](CHANGELOG.md)

访问网站：[方音圖鑒 - dialects.yzup.top](https://dialects.yzup.top/)

---

## 📖 项目概述

**方言比较小站** 是一个基于 **FastAPI** 的高性能后端系统，专注于汉语方言数据的查询、分析和可视化。该项目为方言学术研究、语言学习和文化传承提供强大的数据支持平台。

### 🎯 核心特性

- 🔍 **中古音韵查询系统** - 按中古地位整理汉字读音，支持音位反查中古来源
- 📊 **音韵分类矩阵** - 声母-韵母-汉字交叉表，支持多维度音韵特征分类
- 🔎 **查字查调功能** - 根据汉字查询各方言点读音，支持声调查询和对比
- 🗺️ **地理信息服务** - 方言点坐标查询、区域划分、批量匹配
- 🎙️ **Praat 声学分析** - 音频声学参数提取、音高分析、共鸣峰检测、声调轮廓
- 👤 **完整用户系统** - JWT 认证、权限管理、活动追踪、多数据库权限隔离
- 🛠️ **专业工具集** - 粤拼转 IPA、数据校验、文件合并等实用工具
- 💾 **自定义数据管理** - 用户可添加和管理自己的方言数据
- 📈 **三层缓存架构** - Redis 缓存（用户、权限）+ 内存缓存（方言数据）
- 🔐 **安全可靠** - bcrypt 密码加密、Token 刷新、API 限流、权限控制
- 🏘️ **VillagesML 机器学习系统** ⭐ - 广东省 285,860 条自然村地名分析，7 大模块（字符、语义、空间、模式、区域、ML 计算），50+ API 端点，100% 数据库覆盖
- 📊 **管理员分析系统** ⭐ - 用户行为分析、RFM 分析、异常检测、排行榜系统、会话监控、设备追踪

---

## 📊 项目统计

| 指标 | 数值 |
|------|------|
| **代码总行数** | ~40,600 行 |
| **Python 文件数** | 231 个 |
| **API 端点数量** | 234 个（公开 23 + 用户 53 + 管理员 39 + VillagesML 107 + 其他 12）|
| **依赖包数量** | 64 个 |
| **数据库数量** | 9 个 SQLite 数据库 |
| **数据库表数** | 65+ 个表（含 VillagesML 45 张预计算表）|
| **当前版本** | 2.0.1 |
| **最后更新** | 2026-03-04 |

---

## 🔗 相关仓库

- **[预处理字表](https://github.com/jengzang/dialects-build)**
  [![dialects-build](https://img.shields.io/badge/Repo-dialects--build-ff69b4?logo=github&logoColor=white&style=for-the-badge)](https://github.com/jengzang/dialects-build)
  方言数据预处理仓库，负责原始数据的清洗、转换和优化。

- **[前端代码](https://github.com/jengzang/dialects-js-frontend)**
  [![dialects-vue-frontend](https://img.shields.io/badge/Repo-dialects--js--frontend-0088ff?logo=github&logoColor=white&style=for-the-badge)](https://github.com/jengzang/dialects-js-frontend)
  前端界面，基于 Vue 框架和原生 JavaScript。

---

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Redis 7.0+ (可选，用于缓存)
- SQLite 3.35+ (内置)
- FFmpeg (Praat 声学分析必需)

### 1. 克隆项目

```bash
git clone https://github.com/jengzang/backend-fastapi.git
cd backend-fastapi
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）

创建 `.env` 文件：

```env
# 运行模式
RUN_TYPE=MINE  # MINE(开发) / EXE(打包) / WEB(生产)

# Redis 配置（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# JWT 配置
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
```

### 4. 启动服务

```bash
# 开发模式（单进程，自动重载）
python run.py

# 生产模式（多进程，推荐）
gunicorn -c gunicorn_config.py app.main:app
```

| 短參數 | 長參數 | 類型 | 可選值 | 默認值 | 功能描述                                      |
| :--- | :--- | :--- | :--- | :--- |:------------------------------------------|
| `-r` | `--run` | `string` | `WEB`, `EXE`, `MINE` | `WEB` | 指定運行模式，WEB为部署模式；MINE是跑在局域网的；EXE是打包为独立程序的。 |
| `-close` | `--close-browser` | `flag` | - | `False` | 禁止自動打開瀏覽器。如果不加此參數，程序啟動後會嘗試調用系統默認瀏覽器。      |

服务启动后访问：
- **API 文档**：http://localhost:5000/docs
- **备用文档**：http://localhost:5000/redoc
- **主页**：http://localhost:5000/

---

## 🏗️ 系统架构

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│              FastAPI 应用入口（main.py）                 │
│         Uvicorn ASGI Server / Gunicorn Workers          │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────┴─────────┐
    │                  │
    V                  V
┌──────────────┐  ┌─────────────────────────────────────┐
│  认证系统     │  │       业务逻辑模块                   │
│ JWT + bcrypt │  │  - 音韵查询 (phonology)              │
│ Token 刷新   │  │  - 地理信息 (geo)                    │
│ 权限管理     │  │  - 自定义数据 (custom)               │
│ 会话追踪 ⭐  │  │  - 工具模块 (tools)                  │
└──────────────┘  │  - 管理员功能 (admin)                │
                  │  - VillagesML 机器学习 ⭐            │
                  └─────────────────────────────────────┘
    │
    V
┌─────────────────────────────────────────────────────────┐
│                    中间件层                              │
│  - TrafficLoggingMiddleware (流量统计)                  │
│  - ApiLoggingMiddleware (API 日志)                      │
│  - GZipMiddleware (响应压缩)                            │
│  - CORSMiddleware (跨域支持)                            │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────┴─────────┐
    │                  │
    V                  V
┌──────────────┐  ┌─────────────────────────────────────┐
│ SQLite 数据库 │  │         Redis 缓存层                 │
│ (9个数据库)⭐ │  │  - 用户信息缓存 (1小时)              │
│ - auth.db    │  │  - 权限缓存 (10分钟)                 │
│ - logs.db    │  │  - 方言数据缓存 (内存)               │
│ - dialects.db│  │  - 会话管理                          │
│ - villages.db⭐│  │  - 设备追踪 ⭐                      │
│ - ...        │  └─────────────────────────────────────┘
└──────────────┘
    │
    V
┌─────────────────────────────────────────────────────────┐
│              后台异步处理系统                            │
│  - 6 个日志队列（批量写入）                              │
│  - APScheduler 定时任务（统计聚合、日志清理）            │
│  - 分析数据聚合（用户行为、RFM、异常检测）⭐             │
│  - 文件清理线程（临时文件、过期数据）                     │
│  - 连接池管理（5-10个连接）                              │
└─────────────────────────────────────────────────────────┘
```

### 应用生命周期

#### 启动流程
1. **初始化数据库连接池**（5-10 个连接，WAL 模式）
2. **清理旧临时文件**（12 小时前的 Praat 临时文件）
3. **预热方言数据缓存**（加载常用方言数据到内存）
4. **启动后台线程**（单进程模式：6 个日志队列写入线程）
5. **启动定时任务**（APScheduler：统计聚合、日志清理）

#### 关闭流程
1. **停止后台线程**（停止日志队列处理）
2. **刷新待处理数据**（将队列中剩余数据写入数据库）
3. **关闭数据库连接池**
4. **关闭 Redis 连接**

---

## 🎯 核心功能详解

### 1. 查中古（ZhongGu）功能 ⭐

根据中古音韵条件（声母、韵母、声调、等呼）筛选汉字，并分析其在各方言点的读音。

#### API 端点
- `POST /api/new_pho/ZhongGu`

#### 功能描述
该功能分为两个步骤：
1. **获取汉字**：根据中古音韵地位条件筛选符合的汉字
2. **方言分析**：查询这些汉字在指定方言点的读音

#### 请求参数

```json
{
  "characters": "",           // 留空表示根据中古条件筛选
  "locations": ["广州", "北京"],
  "zhonggu_filters": {
    "声母": ["帮", "滂", "並"],
    "韵部": ["东", "冬"],
    "声调": ["平声"],
    "等呼": ["一等", "三等"]
  },
  "need_features": true,      // 是否返回音韵特征
  "limit": 100
}
```

#### 响应格式

```json
{
  "characters": ["東", "公", "風", "蒙"],
  "locations": ["广州", "北京"],
  "data": [
    {
      "char": "東",
      "广州": {
        "pronunciation": "dung1",
        "ipa": "tʊŋ˥",
        "声母": "d",
        "韵母": "ung",
        "声调": "1"
      },
      "北京": {
        "pronunciation": "dong1",
        "ipa": "tʊŋ˥˥",
        "声母": "d",
        "韵母": "ong",
        "声调": "1"
      }
    }
  ],
  "total_chars": 4
}
```

#### 使用场景
- **声调演变研究**：查询中古平声字在现代方言中的调值分化
- **音韵对应关系**：研究中古 "东韵一等" 在各方言的规律演变
- **方言比较**：对比不同方言点对相同中古音的处理方式

---

### 2. 查音位（YinWei）功能 ⭐

根据现代方言的音位特征（声母、韵母、声调）反查其中古来源。

#### API 端点
- `POST /api/new_pho/YinWei`

#### 功能描述
该功能采用 **p2s 模式**（Phonology to Status），即从现代音位推导中古地位。

#### 请求参数

```json
{
  "locations": ["广州"],
  "phonology_filters": {
    "声母": ["d", "t"],
    "韵母": ["ung", "uk"],
    "声调": ["1", "3"]
  },
  "need_zhonggu": true,       // 返回中古来源信息
  "limit": 50
}
```

#### 响应格式

```json
{
  "location": "广州",
  "results": [
    {
      "pronunciation": "dung1",
      "characters": ["東", "冬", "蟲"],
      "zhonggu_sources": [
        {
          "声母": "端",
          "韵部": "东",
          "声调": "平声",
          "等呼": "一等",
          "count": 25
        }
      ]
    }
  ],
  "total": 3
}
```

#### 使用场景
- **音韵层次分析**：查找广州话 "ung1" 韵的中古来源分布
- **白读文读研究**：分析同一音位的不同中古来源
- **历史语音学**：追溯现代音韵系统的历史渊源

---

### 3. 查字功能 ⭐

根据汉字查询其在各方言点的读音，支持繁简体自动转换。

#### API 端点
- `GET /api/search_chars/`

#### 请求参数

```bash
GET /api/search_chars/?char=東&locations=广州,北京,上海&need_features=true
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `char` | string | 查询的汉字（支持繁简体） |
| `locations` | string | 方言点列表（逗号分隔） |
| `need_features` | boolean | 是否返回音韵特征 |
| `limit` | integer | 返回结果数量限制 |

#### 响应格式

```json
{
  "char": "東",
  "simplified": "东",
  "data": [
    {
      "location": "广州",
      "pronunciation": "dung1",
      "ipa": "tʊŋ˥",
      "features": {
        "声母": "d",
        "韵母": "ung",
        "声调": "1",
        "调值": "55"
      }
    },
    {
      "location": "北京",
      "pronunciation": "dong1",
      "ipa": "tʊŋ˥˥",
      "features": {
        "声母": "d",
        "韵母": "ong",
        "声调": "1",
        "调值": "55"
      }
    }
  ]
}
```

#### 功能特性
- ✅ 繁简体自动转换（使用 OpenCC）
- ✅ 支持多方言点同时查询
- ✅ 返回 IPA 音标
- ✅ 音韵特征详细标注
- ✅ 支持未登录用户访问

---

### 4. 查调功能 ⭐

查询特定声调在各方言点的表现形式，支持声调对比分析。

#### API 端点
- `GET /api/search_tones/`

#### 请求参数

```bash
GET /api/search_tones/?tone=平声&locations=广州,厦门,福州
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `tone` | string | 声调名称（如 "平声"、"去声"） |
| `locations` | string | 方言点列表 |
| `category` | string | 调类（阴平、阳平等） |

#### 响应格式

```json
{
  "tone": "平声",
  "data": [
    {
      "location": "广州",
      "categories": {
        "阴平": {
          "tone_value": "55",
          "examples": ["東", "天", "詩"],
          "count": 1523
        },
        "阳平": {
          "tone_value": "21",
          "examples": ["同", "田", "時"],
          "count": 1432
        }
      }
    },
    {
      "location": "厦门",
      "categories": {
        "阴平": {
          "tone_value": "44",
          "examples": ["東", "天", "詩"],
          "count": 1598
        }
      }
    }
  ]
}
```

#### 使用场景
- **声调系统对比**：比较不同方言的声调分化
- **调类研究**：分析阴平、阳平的调值差异
- **声调演变**：研究中古声调在现代方言中的表现

---

### 5. 查音系（phonology_matrix）功能 ⭐

生成声母-韵母-汉字交叉矩阵表，用于可视化音韵系统。

#### API 端点
- `POST /api/phonology_matrix`

#### 功能描述
生成类似传统韵图的声韵母交叉表，每个单元格包含该声韵组合的所有汉字。

#### 请求参数

```json
{
  "location": "广州",
  "tone_filter": "1",         // 可选：只显示特定声调
  "group_by": "韵母",         // 分组方式
  "include_empty": false      // 是否包含空单元格
}
```

#### 响应格式

```json
{
  "location": "广州",
  "matrix": {
    "headers": {
      "rows": ["b", "p", "m", "f", "d", "t", "n", "l"],  // 声母
      "cols": ["aa", "aai", "aau", "aam", "aan", "aang"] // 韵母
    },
    "cells": {
      "b-aa": {
        "characters": ["巴", "爸", "芭"],
        "count": 3
      },
      "b-aai": {
        "characters": ["擺", "败"],
        "count": 2
      }
    }
  },
  "statistics": {
    "total_cells": 320,
    "filled_cells": 256,
    "total_characters": 4521
  }
}
```

#### 缓存策略
- Redis 缓存，TTL：1 小时
- 键格式：`phonology_matrix:{location}:{hash(filters)}`
- 大幅提升重复查询性能

#### 前端渲染说明
前端使用该数据生成交互式韵图表格，用户可点击单元格查看详细信息。

---

### 6. 音素分类（phonology_matrix_classify）功能 ⭐

按音韵特征分类的交叉矩阵，支持多维度分类。

#### API 端点
- `POST /api/phonology_classification_matrix`

#### 功能描述
将音韵数据按照声母发音部位、韵母开合等特征进行分类统计。

#### 请求参数

```json
{
  "location": "广州",
  "classification": {
    "horizontal": "声母发音部位",  // 横轴分类
    "vertical": "韵母开合",        // 纵轴分类
    "cell_row": "声调"             // 单元格内分类
  }
}
```

#### 响应格式

```json
{
  "location": "广州",
  "classification_matrix": {
    "rows": ["唇音", "舌尖音", "舌根音"],
    "cols": ["开口呼", "齐齿呼", "合口呼", "撮口呼"],
    "cells": {
      "唇音-开口呼": {
        "声调分布": {
          "阴平": 245,
          "阳平": 198,
          "阴上": 167
        },
        "example_chars": ["巴", "波", "婆"]
      }
    }
  }
}
```

#### 使用场景
- **音韵系统可视化**：清晰展示方言音韵结构
- **特征对比研究**：分析不同方言的音韵特征分布
- **教学演示**：用于语言学课程的直观教学

---

### 7. 自定义绘图功能 ⭐

用户自定义数据查询，用于生成可视化图表。

#### API 端点
- `GET /api/get_custom`

#### 请求参数

```bash
GET /api/get_custom?locations=广州,北京,上海&regions=粤语,官话&need_features=true
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `locations` | string | 指定方言点（逗号分隔） |
| `regions` | string | 指定区域（逗号分隔） |
| `need_features` | boolean | 是否返回音韵特征 |
| `format` | string | 输出格式（json/csv/excel） |

#### 响应格式

```json
{
  "query": {
    "locations": ["广州", "北京", "上海"],
    "regions": ["粤语", "官话"]
  },
  "data": [
    {
      "location": "广州",
      "region": "粤语",
      "coordinates": [113.264, 23.129],
      "phonology_system": {
        "声母数": 19,
        "韵母数": 56,
        "声调数": 9
      }
    }
  ],
  "export_url": "/api/export/custom/abc123.csv"
}
```

#### 绘图应用场景
1. **地图分布图**：将方言点标注在地图上
2. **音韵系统对比图**：柱状图对比声韵母数量
3. **声调等值线图**：根据调值绘制等高线
4. **演变路径图**：时间序列展示音韵演变

---

### 8. 传统音韵分析

传统的音韵查询接口，支持双向查询。

#### API 端点
- `POST /api/phonology`

#### 模式说明

**s2p 模式（Status to Phonology）**
- 中古地位 → 现代音值
- 输入中古音韵条件，输出方言读音

**p2s 模式（Phonology to Status）**
- 现代音值 → 中古地位
- 输入方言音位，推导中古来源

#### 与新版接口的区别

| 特性 | `/api/phonology` (传统) | `/api/new_pho/ZhongGu` (新版) |
|------|-------------------------|-------------------------------|
| 缓存优化 | 基础缓存 | Redis 多层缓存 |
| 响应格式 | 简单 JSON | 结构化 + 元数据 |
| 批量查询 | 支持 | 优化支持 |

---

## 🏘️ VillagesML 机器学习系统 ⭐

**VillagesML** 是一个专门针对广东省自然村地名的大规模机器学习分析系统，提供字符、语义、空间、模式、区域和 ML 计算等多维度分析能力。

### 系统概述

- **数据规模**：285,860 条自然村地名
- **覆盖范围**：广东省 21 个地级市、121 个县级行政区、1,500+ 乡镇
- **系统定位**：预计算架构，提供轻量级查询服务
- **API 端点**：107 个端点（50+ 预计算查询 + 实时计算）
- **数据库覆盖**：100%（45/45 表全部有 API 端点）
- **查询性能**：预计算查询响应 < 100ms

### 核心功能模块

#### 1. 搜索探索（Module 1）

提供关键词搜索入口，支持三级行政区（市/县/镇）逐层过滤，搜索结果分页展示。

**主要功能**：
- 关键词搜索（支持汉字/拼音）
- 三级行政区（市/县/镇）逐层过滤
- 分页浏览（默认每页 20 条）
- 单个自然村完整多维分析

**使用场景**：快速定位特定村庄，查看村庄的字符组成、语义特征、空间位置、N-gram 分解等多维度信息。

#### 2. 字符分析（Module 2）

分析地名中字符的使用频率、区域分布、语义相似性和统计显著性。

**主要功能**：
- **全局字符频率统计**（12 个端点）- 统计所有字符在全省的使用频率
- **区域字符频率分布** - 按市/县/镇统计字符使用情况
- **字符倾向性分析** - 使用 Z-score、lift、log-odds 衡量字符在特定区域的偏好程度
- **字符显著性检测** - 卡方检验判断字符分布是否统计显著
- **字符嵌入向量** - Word2Vec（100 维）训练的字符语义向量
- **字符相似度计算** - 基于 Cosine 相似度的字符语义关联分析

**使用场景**：分析"水"、"沙"、"石"等地理特征字的区域分布，识别不同地区的命名偏好。

#### 3. 语义分析（Module 3）

基于 9 大语义类别（地理特征、植物、建筑、姓氏、数字方位等）进行语义标注和分析。

**主要功能**：
- **9 大语义类别统计**（13 个端点）- 地理特征、植物、建筑、姓氏、数字方位、动物、颜色、材料、其他
- **40+ 精细子类别分类** - 更细粒度的语义分类
- **语义共现模式分析** - Bigrams、Trigrams 语义组合模式
- **PMI 分析** - Pointwise Mutual Information 衡量语义关联强度
- **VTF 分析** - Virtual Term Frequency 加权语义频率
- **语义类别倾向性** - 各地区对不同语义类别的偏好分析

**使用场景**：识别村庄命名的文化特征和地理特征，如"水系村庄"、"植物村庄"、"姓氏村庄"等。

#### 4. 空间分析（Module 4）

基于地理坐标进行空间聚类、热点检测和密度分析。

**主要功能**：
- **空间热点检测**（8 个端点）- KDE（核密度估计）分析
- **空间密度聚类** - DBSCAN 算法识别空间聚集区域
- **地理分布可视化** - MapLibre GL 地图渲染
- **空间-倾向性整合分析** - 结合字符倾向性和空间分布

**使用场景**：识别特定字符的空间聚集区域，如"沙"字在珠江三角洲的密集分布。

#### 5. 模式分析（Module 5）

挖掘地名的命名模式和结构规律。

**主要功能**：
- **N-gram 模式挖掘**（7 个端点）- 2-gram、3-gram、4-gram 频率统计
- **位置感知分析** - 前缀、中缀、后缀模式识别
- **结构命名模式**（4 个端点）- 识别"XX村"、"上XX"、"下XX"等结构
- **模式频率和倾向性** - 统计各模式的使用频率和区域偏好
- **模式显著性检验** - 判断模式是否统计显著

**使用场景**：发现常见命名模式，如"XX围"、"XX坊"、"XX岗"等地域特色命名。

#### 6. 区域分析（Module 6）

比较不同区域的命名特征相似性。

**主要功能**：
- **三级聚合**（6 个端点）- 市/县/镇三级统计聚合
- **区域相似度分析** - Cosine/Jaccard 相似度计算
- **区域特征向量** - 提取区域的字符/语义特征向量
- **区域空间聚合** - 按地理区域聚合统计
- **跨层级区域比较** - 比较不同行政层级的命名特征
- **共同特征和差异特征识别** - 识别区域间的相似性和差异性

**使用场景**：比较不同区域的命名特征相似性，如珠三角与粤东地区的命名差异。

#### 7. ML 计算（Module 7）

提供实时机器学习计算能力，支持聚类、降维、层次分析等。

**主要功能**：
- **聚类分析**（8+ 个端点）- K-means、DBSCAN、GMM（高斯混合模型）
- **降维可视化** - PCA、t-SNE 降维投影
- **层次聚类** - 树状图展示聚类层次结构
- **自定义特征提取** - 用户自定义特征组合
- **子集专项分析** - 对特定区域或村庄子集进行深度分析
- **语义共现网络** - 构建字符/语义共现网络图

**使用场景**：对特定区域或村庄子集进行深度分析，发现隐藏的命名规律。

### 技术特点

- **预计算架构** - 45 张预计算结果表，查询响应 < 100ms
- **大规模数据** - 支持 285,860 条村庄高效查询
- **灵活过滤** - 支持市/县/镇三级行政区划过滤
- **实时计算** - 提供按需的 ML 计算功能
- **批量操作** - 支持批量查询和批量计算
- **100% 数据库覆盖** - 45/45 表全部有 API 端点

### 前端技术栈

- **UI 框架**：Vue 3.5 + Composition API
- **构建工具**：Vite 7.1 (MPA 多入口点构建)
- **地图渲染**：MapLibre GL 5.16（GPU 加速）
- **图表库**：ECharts 5.6（热图、柱状图、网络图）
- **API 中心**：14 个子模块统一管理

### 数据库结构

- **数据库**：villages.db
- **数据表**：45 张预计算结果表
- **索引优化**：多字段复合索引、全文搜索索引、空间索引
- **数据来源**：广东省自然村地名数据（285,860 条）

### 相关文档

- **docs/FEATURE_OVERVIEW.md** - VillagesML 功能总览（93.4KB，非常详细）
- **docs/API.md** - 完整 API 接口文档

---

## 📊 管理员分析系统 ⭐

**管理员分析系统** 提供全面的用户行为分析、异常检测、排行榜和会话监控功能，帮助管理员深入了解用户使用情况。

### 1. 用户行为分析

深度分析用户的使用模式和行为特征。

**主要功能**：
- **用户分段**（5 个级别）- 根据活跃度将用户分为 5 个等级
- **RFM 分析**（5 种用户类型）- Recency（最近访问）、Frequency（访问频率）、Monetary（使用量）三维分析
  - 冠军用户（Champions）- 高频高活跃
  - 忠诚用户（Loyal）- 长期稳定使用
  - 潜力用户（Potential）- 有增长潜力
  - 需要关注（At Risk）- 活跃度下降
  - 流失用户（Churned）- 长期未使用
- **异常检测**（4 种异常类型）
  - 流量异常 - 短时间内大量请求
  - 错误率异常 - 高错误率用户
  - 使用模式异常 - 不寻常的 API 调用模式
  - 时间异常 - 异常时段访问
- **用户偏好分析** - 分析用户最常使用的 API 端点和功能模块

**使用场景**：识别高价值用户、发现潜在问题用户、优化产品功能。

### 2. 排行榜系统

多维度的用户和 API 排行榜。

**主要功能**：
- **用户全局排行** - 按调用次数、使用时长、流量等指标排名
- **单 API 用户排行** - 查看特定 API 的使用排行
- **API 端点排行** - 最受欢迎的 API 端点统计
- **在线时长排行** - 用户在线时长统计

**使用场景**：了解最活跃用户、最受欢迎的功能、用户使用习惯。

### 3. 会话管理增强

全面的会话追踪和监控。

**主要功能**：
- **设备信息追踪** - 记录用户设备类型、操作系统、浏览器
- **IP 地址和地理位置追踪** - 记录用户访问来源
- **可疑活动检测** - 识别异常登录、多设备登录等可疑行为
- **会话时长统计** - 统计用户每次会话的时长
- **在线状态实时监控** - 实时查看当前在线用户

**使用场景**：安全监控、用户行为分析、异常检测。

### 4. 自定义区域管理

用户可以创建和管理自己的方言区域。

**主要功能**：
- **用户自定义方言区域** - 创建自定义的方言区域分类
- **区域 CRUD 操作** - 创建、读取、更新、删除区域
- **区域地点管理** - 为区域添加和管理方言点

**使用场景**：研究人员创建自定义的方言区域分类，进行专项研究。

---

## 🛠️ 工具模块

### 1. Check 工具 - 数据校验

检查方言数据的完整性和一致性。

#### API 端点（9 个）

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/tools/check/upload` | POST | 上传待检查文件 | 🔑 用户 |
| `/api/tools/check/validate` | POST | 执行数据验证 | 🔑 用户 |
| `/api/tools/check/report` | GET | 获取校验报告 | 🔑 用户 |
| `/api/tools/check/errors` | GET | 获取错误列表 | 🔑 用户 |
| `/api/tools/check/warnings` | GET | 获取警告列表 | 🔑 用户 |
| `/api/tools/check/statistics` | GET | 获取数据统计 | 🔑 用户 |
| `/api/tools/check/export` | GET | 导出校验结果 | 🔑 用户 |
| `/api/tools/check/history` | GET | 查看历史记录 | 🔑 用户 |
| `/api/tools/check/delete/{task_id}` | DELETE | 删除校验任务 | 🔑 用户 |

#### 功能特性
- ✅ 数据格式验证（Excel/CSV/JSON）
- ✅ 音韵系统完整性检查
- ✅ 重复数据检测
- ✅ 异常值识别（非法音节、声调）
- ✅ 批量校验报告（HTML/PDF）

#### 使用场景
- 数据导入前的质量检查
- 数据库维护和清理
- 协作数据收集的质量控制

---

### 2. Jyut2IPA 工具 - 粤拼转国际音标

将粤语拼音（Jyutping）转换为国际音标（IPA）。

#### API 端点（4 个）

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/tools/jyut2ipa/convert` | POST | 单个转换 | 🔑 用户 |
| `/api/tools/jyut2ipa/batch` | POST | 批量转换 | 🔑 用户 |
| `/api/tools/jyut2ipa/export` | GET | 导出转换结果 | 🔑 用户 |
| `/api/tools/jyut2ipa/history` | GET | 查看转换历史 | 🔑 用户 |

#### 请求示例

```json
POST /api/tools/jyut2ipa/convert
{
  "text": "gwong2 zau1 waa2",
  "tone_notation": "diacritics"  // 声调标注方式
}
```

#### 响应示例

```json
{
  "input": "gwong2 zau1 waa2",
  "output": "kʷɔːŋ˨˩ tsɐu˥˥ waː˨˩",
  "syllables": [
    {
      "jyutping": "gwong2",
      "ipa": "kʷɔːŋ˨˩",
      "initial": "gw",
      "final": "ong",
      "tone": "2"
    }
  ]
}
```

#### 功能特性
- ✅ 支持多种粤拼方案
- ✅ 声调符号标注（IPA 符号/数字）
- ✅ 音节分析（声母、韵母、声调）
- ✅ 批量转换（支持文本文件）
- ✅ 转换历史记录

---

### 3. Merge 工具 - 数据合并

合并多个方言数据文件，支持智能去重和冲突处理。

#### API 端点（5 个）

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/tools/merge/upload` | POST | 上传待合并文件 | 🔑 用户 |
| `/api/tools/merge/preview` | POST | 预览合并结果 | 🔑 用户 |
| `/api/tools/merge/execute` | POST | 执行合并操作 | 🔑 用户 |
| `/api/tools/merge/conflicts` | GET | 查看冲突列表 | 🔑 用户 |
| `/api/tools/merge/download` | GET | 下载合并文件 | 🔑 用户 |

#### 合并策略

| 策略 | 说明 |
|------|------|
| `keep_first` | 保留第一个文件的数据 |
| `keep_last` | 保留最后一个文件的数据 |
| `keep_all` | 保留所有数据（标注来源） |
| `manual` | 手动选择保留哪个 |

#### 请求示例

```json
POST /api/tools/merge/execute
{
  "file_ids": ["file1", "file2", "file3"],
  "strategy": "keep_last",
  "deduplication": true,
  "output_format": "excel"
}
```

#### 功能特性
- ✅ 支持多种文件格式（Excel、CSV、JSON）
- ✅ 智能去重（基于字+方言点）
- ✅ 冲突检测和处理
- ✅ 合并预览
- ✅ 撤销和回滚

---

### 4. Praat 声学分析工具 ⭐ 新增

专业的语音声学分析工具，支持音频上传、声学参数提取、音高分析等功能。

#### API 端点（9 个）

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/tools/praat/capabilities` | GET | 获取后端能力 | 🔓 公开 |
| `/api/tools/praat/uploads` | POST | 上传音频文件 | 🔑 用户 |
| `/api/tools/praat/uploads/progress/{task_id}` | GET | 获取上传进度 | 🔑 用户 |
| `/api/tools/praat/uploads/progress/{task_id}/audio` | GET | 下载标准化音频 | 🔑 用户 |
| `/api/tools/praat/uploads/progress/{task_id}` | DELETE | 删除上传任务 | 🔑 用户 |
| `/api/tools/praat/jobs` | POST | 创建分析任务 | 🔑 用户 |
| `/api/tools/praat/jobs/progress/{job_id}` | GET | 获取分析进度 | 🔑 用户 |
| `/api/tools/praat/jobs/progress/{job_id}/result` | GET | 获取分析结果 | 🔑 用户 |
| `/api/tools/praat/jobs/progress/{job_id}` | DELETE | 取消分析任务 | 🔑 用户 |

#### 支持的音频格式
- **wav** - 标准 WAV 格式
- **mp3** - MPEG Audio Layer 3
- **m4a** - MPEG-4 Audio
- **webm** - WebM Audio
- **ogg** - Ogg Vorbis
- **flac** - Free Lossless Audio Codec
- **aac** - Advanced Audio Coding

#### 文件限制
- **最大文件大小**：50 MB
- **最大时长**：20 秒
- **自动预处理**：所有音频自动转换为 16kHz 单声道 WAV

#### 分析模块详解

##### 1. basic - 基础声学参数
```json
{
  "module": "basic",
  "parameters": {}
}
```
**输出参数：**
- `duration_s` - 音频总时长（秒）
- `energy_mean` - 平均能量（dB）
- `silence_ratio` - 静音比例

##### 2. pitch - 音高分析
```json
{
  "module": "pitch",
  "parameters": {
    "f0_min": 75,
    "f0_max": 600,
    "five_point": true  // 5点音高轮廓
  }
}
```
**输出参数：**
- `f0_mean` - 平均基频（Hz）
- `f0_min` / `f0_max` - 最小/最大基频
- `f0_range` - 基频范围
- `five_point_contour` - 5点轮廓 [起点, 1/4, 中点, 3/4, 终点]
- `slope` - 音高斜率（Hz/s）

**使用场景：**
- 方言声调分析（声调曲拱提取）
- 语调研究
- 音高变化模式

##### 3. intensity - 能量分析
```json
{
  "module": "intensity",
  "parameters": {
    "min_intensity": 50
  }
}
```
**输出参数：**
- `intensity_mean` - 平均强度（dB）
- `intensity_max` - 最大强度
- `intensity_std` - 强度标准差

##### 4. formant - 共鸣峰提取
```json
{
  "module": "formant",
  "parameters": {
    "max_formants": 5,
    "max_frequency": 5500
  }
}
```
**输出参数：**
- `F1`, `F2`, `F3`, `F4`, `F5` - 前五个共鸣峰频率（Hz）
- `F1_bandwidth` 等 - 共鸣峰带宽

**使用场景：**
- 元音分析
- 发音人识别
- 语音合成

##### 5. voice_quality - 嗓音质量
```json
{
  "module": "voice_quality",
  "parameters": {}
}
```
**输出参数：**
- `HNR` - 谐噪比（Harmonics-to-Noise Ratio）
- `jitter` - 基频微扰
- `shimmer` - 振幅微扰

**使用场景：**
- 嗓音疾病诊断
- 语音质量评估

##### 6. segments - 自动分段
```json
{
  "module": "segments",
  "parameters": {
    "silence_threshold": -25,
    "min_silence_duration": 0.1,
    "min_sound_duration": 0.1
  }
}
```
**输出参数：**
- `segments` - 分段列表 [{start, end, type, duration}]
- `type` 类型：`silence` / `voiced` / `nucleus`（韵核）

#### 分析模式

##### single 模式 - 单点分析
整段音频提取一组参数。

```json
{
  "mode": "single",
  "modules": ["basic", "pitch", "formant"]
}
```

**响应示例：**
```json
{
  "mode": "single",
  "results": {
    "basic": {
      "duration_s": 1.25,
      "energy_mean": -12.5
    },
    "pitch": {
      "f0_mean": 195.3,
      "five_point_contour": [180, 195, 210, 205, 185]
    },
    "formant": {
      "F1": 750,
      "F2": 1450,
      "F3": 2500
    }
  }
}
```

##### continuous 模式 - 连续分析
生成时间序列数据。

```json
{
  "mode": "continuous",
  "modules": ["pitch", "intensity"],
  "time_step": 0.01  // 10ms 步长
}
```

**响应示例：**
```json
{
  "mode": "continuous",
  "timeseries": {
    "time": [0.00, 0.01, 0.02, ...],
    "pitch": {
      "f0": [180, 182, 185, 190, ...]
    },
    "intensity": {
      "value": [-15, -14, -13, ...]
    }
  }
}
```

#### 完整请求示例

```json
POST /api/tools/praat/jobs
{
  "upload_id": "task_abc123",
  "mode": "single",
  "modules": [
    {
      "name": "basic"
    },
    {
      "name": "pitch",
      "parameters": {
        "f0_min": 75,
        "f0_max": 300,
        "five_point": true
      }
    },
    {
      "name": "formant",
      "parameters": {
        "max_formants": 5
      }
    },
    {
      "name": "segments"
    }
  ],
  "options": {
    "time_step": 0.01
  },
  "output": {
    "format": "json",
    "include_metadata": true
  }
}
```

#### 使用流程

1. **上传音频文件**
```bash
curl -X POST http://localhost:5000/api/tools/praat/uploads \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@recording.wav"
```

2. **创建分析任务**
```bash
curl -X POST http://localhost:5000/api/tools/praat/jobs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"upload_id": "task_abc123", "mode": "single", "modules": [...]}'
```

3. **获取分析结果**
```bash
curl http://localhost:5000/api/tools/praat/jobs/progress/task_abc123_job_1/result \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 典型应用场景

1. **方言声调分析**
   - 提取 5 点音高轮廓
   - 对比不同方言点的声调曲线
   - 生成声调可视化图表

2. **元音分析**
   - 提取共鸣峰 F1、F2
   - 绘制元音三角图
   - 分析元音空间分布

3. **语音质量评估**
   - 计算 HNR、jitter、shimmer
   - 评估录音质量
   - 筛选高质量语料

4. **韵律特征研究**
   - 自动分段检测
   - 音高变化率分析
   - 重音模式识别

#### FFmpeg 预处理

所有上传的音频文件都会自动通过 FFmpeg 进行标准化：
```bash
ffmpeg -i input.mp3 -ar 16000 -ac 1 -f wav output.wav
```
- **采样率**：16000 Hz
- **声道**：单声道
- **格式**：WAV（16-bit PCM）

这确保了 Praat 分析的一致性和准确性。

---

## 📡 API 接口文档

系统共有 **234 个 API 端点**，按权限和功能分类：

- 🔓 **公开接口**：23 个（无需登录）
- 🔑 **用户接口**：53 个（需要登录）
- 👑 **管理员接口**：51 个（需要管理员权限）
- 🏘️ **VillagesML 接口**：107 个（机器学习分析）

### 接口分类概览

#### 核心功能接口
- **认证接口** - 用户注册、登录、Token 管理
- **方言查询接口** - 查中古、查音位、查字、查调、音韵矩阵
- **地理信息接口** - 地点查询、坐标获取、区域划分、批量匹配
- **自定义数据接口** - 用户自定义方言数据管理

#### 工具接口
- **Praat 声学分析** - 音频上传、声学参数提取、音高分析、共鸣峰检测
- **Check 工具** - 数据校验、格式检查、错误报告
- **Jyut2IPA 工具** - 粤拼转国际音标
- **Merge 工具** - 数据合并、冲突处理

#### VillagesML 机器学习接口
- **搜索探索** - 关键词搜索、三级行政区过滤、村庄详情
- **字符分析** - 频率统计、倾向性分析、嵌入向量、相似度计算
- **语义分析** - 语义类别统计、VTF 分析、PMI 分析、共现模式
- **空间分析** - 热点检测、密度聚类、地理分布可视化
- **模式分析** - N-gram 挖掘、结构模式识别、位置感知分析
- **区域分析** - 三级聚合、相似度计算、特征向量提取
- **ML 计算** - 聚类分析、降维可视化、层次聚类

#### 管理员接口
- **用户管理** - 用户 CRUD、封禁/解封、角色管理
- **用户行为分析** - 用户分段、RFM 分析、异常检测
- **排行榜系统** - 用户排行、API 排行、在线时长排行
- **会话管理** - 活跃会话、设备追踪、可疑活动检测
- **缓存管理** - 缓存清理、缓存统计、状态检查
- **日志统计** - API 使用统计、关键词统计、趋势分析

### 完整 API 文档

详细的 API 接口文档（包含请求参数、响应格式、使用示例）请查看：

📄 **[docs/API.md](docs/API.md)** - 完整 API 接口文档

或访问在线 API 文档：
- **Swagger UI**：http://localhost:5000/docs
- **ReDoc**：http://localhost:5000/redoc

---

## 🗄️ 数据库结构

### 数据库文件说明

系统使用 **9 个 SQLite 数据库**，分为管理员数据库、用户数据库和机器学习数据库。

| 数据库文件 | 用途 | 访问权限 | 主要表 |
|-----------|------|----------|--------|
| `auth.db` | 用户认证系统 | 管理员 | users, refresh_tokens, api_usage_logs |
| `logs.db` | API 日志统计 | 管理员 | api_visit_log, api_keyword_log, api_statistics |
| `dialects_admin.db` | 方言数据（管理员） | 管理员 | dialect_points, phonology_data |
| `dialects.db` | 方言数据（用户） | 用户 | dialect_points, phonology_data |
| `characters_admin.db` | 字符数据库（管理员） | 管理员 | characters, pronunciations |
| `characters.db` | 字符数据库（用户） | 用户 | characters, pronunciations |
| `custom_admin.db` | 自定义数据（管理员） | 管理员 | custom_data, metadata |
| `custom.db` | 自定义数据（用户） | 用户 | user_queries, custom_data |
| `villages.db` ⭐ | VillagesML 机器学习 | 用户 | 45 张预计算表（字符、语义、空间、模式等） |

### 核心表结构

#### users 表（用户表）

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    email TEXT UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    is_admin BOOLEAN DEFAULT 0,

    -- 审计字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    register_ip TEXT,

    -- 活动追踪
    last_seen TIMESTAMP,
    login_count INTEGER DEFAULT 0,
    total_online_seconds INTEGER DEFAULT 0,

    -- 安全字段
    failed_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP,
    locked_until TIMESTAMP
);
```

#### refresh_tokens 表（Token 管理）

```sql
CREATE TABLE refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_id TEXT UNIQUE NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    is_revoked BOOLEAN DEFAULT 0,
    user_agent TEXT,
    ip_address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Token 管理策略：**
- 每个用户最多 10 个活跃 Refresh Token
- Access Token 过期时间：30 分钟
- Refresh Token 过期时间：30 天
- 自动清理过期 Token

#### api_usage_logs 表（API 使用日志）

```sql
CREATE TABLE api_usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    duration_ms REAL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### api_usage_summary 表（使用摘要）

```sql
CREATE TABLE api_usage_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_duration_seconds REAL DEFAULT 0,
    unique_endpoints INTEGER DEFAULT 0,
    UNIQUE(user_id, date)
);
```

#### user_db_permissions 表（数据库权限）⭐ 新增

```sql
CREATE TABLE user_db_permissions (
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    db_key TEXT NOT NULL,
    can_write BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, db_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**权限键（db_key）：**
- `dialects` - 方言数据库访问权限
- `characters` - 字符数据库访问权限
- `custom` - 自定义数据库访问权限
- `admin` - 管理员数据库访问权限（特殊）

#### 日志系统表结构

**api_visit_log 表（HTML 页面访问）**

```sql
CREATE TABLE api_visit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name TEXT NOT NULL,
    visit_count INTEGER DEFAULT 1,
    last_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**api_keyword_log 表（API 参数关键词）**

```sql
CREATE TABLE api_keyword_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_name TEXT NOT NULL,
    keyword TEXT NOT NULL,
    usage_count INTEGER DEFAULT 1,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(field_name, keyword)
);
```

**api_statistics 表（聚合统计）**

```sql
CREATE TABLE api_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    date DATE NOT NULL,
    total_requests INTEGER DEFAULT 0,
    avg_duration_ms REAL,
    error_count INTEGER DEFAULT 0,
    UNIQUE(endpoint, date)
);
```

### 数据库优化配置

所有数据库都启用了以下优化：

```sql
-- WAL 模式（Write-Ahead Logging）
PRAGMA journal_mode=WAL;

-- 64MB 缓存
PRAGMA cache_size=-64000;

-- 完整性检查
PRAGMA foreign_keys=ON;

-- 自动 VACUUM
PRAGMA auto_vacuum=INCREMENTAL;
```

**性能提升：**
- WAL 模式：读写并发，无阻塞
- 大缓存：减少磁盘 I/O
- 连接池：5-10 个连接复用

---

## ⚙️ 配置参数详解

### JWT 配置

```python
# JWT Token 配置
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
MAX_ACTIVE_REFRESH_TOKENS = 10
```

### 注册和登录限制

```python
# 注册限制
MAX_REGISTRATIONS_PER_IP = 3  # 10 分钟内
REGISTRATION_WINDOW_MINUTES = 10

# 登录限制
MAX_LOGIN_PER_MINUTE = 10
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
```

### API 限流配置

```python
# 用户每小时 API 使用时长限制（秒）
MAX_USER_USAGE_PER_HOUR = 2000

# 匿名 IP 每小时 API 使用时长限制（秒）
MAX_IP_USAGE_PER_HOUR = 300

# 单次请求最长时长（秒）
MAX_REQUEST_DURATION = 30
```

### 响应大小限制

```python
# 匿名用户响应大小限制（字节）
MAX_ANONYMOUS_SIZE = 1 * 1024 * 1024  # 1 MB

# 登录用户响应大小限制（字节）
MAX_USER_SIZE = 6 * 1024 * 1024  # 6 MB

# GZip 压缩阈值（字节）
SIZE_THRESHOLD = 10 * 1024  # 10 KB
```

### 日志批处理配置

系统使用 **6 个异步队列** 进行日志批量写入：

```python
# 队列 1: ApiUsageLog（auth.db）
LOG_QUEUE_BATCH_SIZE = 50
LOG_QUEUE_FLUSH_INTERVAL = 10  # 秒

# 队列 2: ApiKeywordLog（logs.db）
KEYWORD_LOG_BATCH_SIZE = 100
KEYWORD_LOG_FLUSH_INTERVAL = 30

# 队列 3: ApiStatistics（logs.db）
STATISTICS_BATCH_SIZE = 20
STATISTICS_FLUSH_INTERVAL = 60

# 队列 4: HTML 访问统计（logs.db）
HTML_VISIT_BATCH_SIZE = 50
HTML_VISIT_FLUSH_INTERVAL = 30

# 队列 5: ApiUsageSummary（auth.db）
SUMMARY_BATCH_SIZE = 20
SUMMARY_FLUSH_INTERVAL = 60

# 队列 6: 用户活动（跨进程）
USER_ACTIVITY_BATCH_SIZE = 30
USER_ACTIVITY_FLUSH_INTERVAL = 15
```

### Praat 工具配置

```python
# 文件上传限制
MAX_UPLOAD_MB = 50
MAX_DURATION_S = 20

# 音频预处理
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1

# 文件清理
CLEANUP_AGE_HOURS = 1  # 清理 1 小时前的临时文件
CLEANUP_SCHEDULE_MINUTES = 30  # 每 30 分钟清理一次
```

### 缓存配置

```python
# Redis 缓存配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# 缓存 TTL（秒）
USER_CACHE_TTL = 3600  # 1 小时
PERMISSION_CACHE_TTL = 600  # 10 分钟
PHONOLOGY_MATRIX_TTL = 3600  # 1 小时

# 方言数据内存缓存
DIALECT_CACHE_SIZE = 100  # 最多缓存 100 个方言点
```

---

## 📦 部署和测试

### Docker 部署（推荐）⭐

完整的 Docker 配置，包含 FFmpeg 支持。

#### Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000 \
    _RUN_TYPE=WEB \
    MPLCONFIGDIR=/tmp \
    FORWARDED_ALLOW_IPS=127.0.0.1,172.17.0.1

WORKDIR /app

# 安装 FFmpeg 系统依赖（Praat 声学分析必需）
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码
COPY app/ /app/app/
COPY common/ /app/common/
COPY data/dependency/ /app/data/dependency/
COPY serve.py /app/serve.py
COPY gunicorn_config.py /app/gunicorn_config.py

# 非 root 用户运行（安全性）
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn_config.py", "serve:app"]
```

#### 构建镜像

```bash
docker build -t dialects-backend:2.0.1 .
```

#### 运行容器

```bash
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e REDIS_HOST=redis \
  -e SECRET_KEY=your-secret-key \
  --name dialects-backend \
  dialects-backend:2.0.1
```

**卷挂载说明：**
- `-v $(pwd)/data:/app/data` - 数据持久化（SQLite 数据库）
- `-v $(pwd)/logs:/app/logs` - 日志持久化

#### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - REDIS_HOST=redis
      - SECRET_KEY=your-secret-key-here
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

启动：
```bash
docker-compose up -d
```

---

### 传统部署

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
cp .env.example .env
nano .env
```

#### 3. 启动服务（生产模式）

```bash
gunicorn -c gunicorn_config.py app.main:app
```

#### 4. systemd 服务配置

创建 `/etc/systemd/system/dialects-backend.service`：

```ini
[Unit]
Description=Dialects Backend API
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/backend-fastapi
Environment="PATH=/var/www/backend-fastapi/venv/bin"
ExecStart=/var/www/backend-fastapi/venv/bin/gunicorn -c gunicorn_config.py app.main:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
KillSignal=SIGQUIT
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable dialects-backend
sudo systemctl start dialects-backend
sudo systemctl status dialects-backend
```

---

### Gunicorn 生产配置

`gunicorn_config.py` 详细配置：

```python
import multiprocessing
import os

# 服务器绑定
bind = "0.0.0.0:5000"

# 工作进程数（建议：CPU 核心数 * 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"

# 超时设置
timeout = 120
keepalive = 5
graceful_timeout = 30

# 进程管理
max_requests = 1000  # 处理 1000 个请求后自动重启
max_requests_jitter = 100  # 添加随机抖动避免同时重启

# 日志配置
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "dialects-backend"

# 预加载应用（节省内存）
preload_app = True

# 工作目录
chdir = os.getcwd()

# 守护进程
daemon = False

# PID 文件
pidfile = "logs/gunicorn.pid"

# 环境变量
raw_env = [
    "RUN_TYPE=PRODUCTION",
]
```

---

### StressTest 压力测试工具 ⭐ 新增

基于 Locust 的压力测试框架，模拟真实用户行为。

#### 工具概述

- **框架**：Locust 2.0+
- **位置**：`StressTest/` 目录
- **配置文件**：`locustfile.py`, `config.py`
- **监控脚本**：`monitor.py`

#### 目录结构

```
StressTest/
├── locustfile.py       # 主测试脚本
├── config.py           # 配置文件
├── monitor.py          # 性能监控脚本
└── README.md           # 使用说明
```

#### 测试用户类型

系统模拟三种用户类型，按比例分配：

| 用户类型 | 比例 | 行为特征 |
|---------|------|----------|
| **DialectAPIUser** | 60% | 已登录用户，访问所有用户功能 |
| **AnonymousUser** | 30% | 匿名用户，仅访问公开接口 |
| **AdminUser** | 10% | 管理员，访问管理功能 |

#### 测试端点

**DialectAPIUser 测试端点（权重）：**
- `search_chars` (50) - 查字功能
- `phonology` (30) - 音韵分析
- `get_locs` (15) - 地点列表
- `get_coordinates` (10) - 坐标查询
- `get_regions` (8) - 区域查询
- `custom_query` (5) - 自定义查询

**AnonymousUser 测试端点：**
- `search_chars` (50) - 查字（匿名）
- `get_locs` (30) - 地点列表（匿名）
- `homepage` (20) - 访问首页

**AdminUser 测试端点：**
- `api_usage` (40) - API 使用统计
- `users` (30) - 用户列表
- `login_logs` (20) - 登录日志
- `user_stats` (10) - 用户统计

#### 运行方式

##### 1. Web UI 模式（推荐）

```bash
locust -f StressTest/locustfile.py --host http://localhost:5000
```

浏览器访问：http://localhost:8089

##### 2. 无头模式（命令行）

```bash
# 50 个并发用户，每秒增加 5 个，持续 5 分钟
locust -f StressTest/locustfile.py \
  --host http://localhost:5000 \
  --headless \
  -u 50 \
  -r 5 \
  -t 5m
```

参数说明：
- `-u` / `--users` - 总用户数
- `-r` / `--spawn-rate` - 每秒生成用户数
- `-t` / `--run-time` - 测试时长

##### 3. 性能监控模式

```bash
# 自动模式（持续监控）
python StressTest/monitor.py --auto

# 手动模式（单次检查）
python StressTest/monitor.py
```

#### 关键指标

测试报告包含以下关键性能指标：

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **RPS** | 每秒请求数 | > 100 |
| **平均响应时间** | 所有请求的平均时长 | < 200ms |
| **中位数响应时间** | 50% 请求的响应时间 | < 100ms |
| **95% 响应时间** | 95% 请求的响应时间 | < 500ms |
| **99% 响应时间** | 99% 请求的响应时间 | < 1000ms |
| **错误率** | 失败请求百分比 | < 1% |

#### 使用示例

**基础压力测试：**
```bash
locust -f StressTest/locustfile.py --host http://localhost:5000 --headless -u 50 -r 5 -t 5m
```

**高并发测试：**
```bash
locust -f StressTest/locustfile.py --host http://localhost:5000 --headless -u 200 -r 10 -t 10m
```

**长时间稳定性测试：**
```bash
locust -f StressTest/locustfile.py --host http://localhost:5000 --headless -u 100 -r 5 -t 1h
```

#### 测试报告

测试完成后，Locust 会生成 HTML 报告，包含：
- 📊 请求统计表（端点、请求数、失败数、响应时间）
- 📈 响应时间分布图
- 📉 RPS 时间序列图
- ❌ 错误统计

---

## 🚀 性能优化

### 1. 数据库优化

- ✅ **WAL 模式**：读写并发，无阻塞
- ✅ **64MB 缓存**：减少磁盘 I/O
- ✅ **连接池**：5-10 个连接复用
- ✅ **索引优化**：自动创建和管理索引
- ✅ **定期 VACUUM**：回收碎片空间

### 2. 三层缓存架构

#### 第一层：Redis 用户缓存（1 小时）
```python
# 缓存用户信息
redis_client.setex(f"user:{user_id}", 3600, user_json)
```

#### 第二层：Redis 权限缓存（10 分钟）
```python
# 缓存权限信息
redis_client.setex(f"permission:{user_id}:{db_key}", 600, permission_json)
```

#### 第三层：内存方言数据缓存
```python
# LRU 缓存，最多 100 个方言点
@lru_cache(maxsize=100)
def get_dialect_data(location: str):
    return load_from_database(location)
```

### 3. 批量处理（6 个异步队列）

所有日志数据都通过队列异步批量写入，避免阻塞主线程：

```python
# 队列 1: API 使用日志
log_queue.put(log_entry)  # 批次大小：50

# 队列 2: 关键词日志
keyword_log_queue.put(keyword_entry)  # 批次大小：100

# 队列 3: 统计聚合
statistics_queue.put(stat_entry)  # 批次大小：20

# 队列 4: HTML 访问
html_visit_queue.put(visit_entry)  # 批次大小：50

# 队列 5: 使用摘要
summary_queue.put(summary_entry)  # 批次大小：20

# 队列 6: 用户活动
user_activity_queue.put(activity_entry)  # 批次大小：30
```

### 4. 响应压缩

自动 GZip 压缩大于 10KB 的响应：
```python
app.add_middleware(
    GZipMiddleware,
    minimum_size=10240,  # 10 KB
    compresslevel=6
)
```

### 5. 并发处理

- ✅ **异步 I/O**：FastAPI + Uvicorn 异步处理
- ✅ **多进程部署**：Gunicorn 多 Worker
- ✅ **连接池管理**：SQLAlchemy 连接池

---

## 🔐 安全性

### 认证和授权

- ✅ **JWT Token 认证**：无状态认证
- ✅ **bcrypt 密码加密**：强哈希算法
- ✅ **Token 自动刷新**：无感续期
- ✅ **权限分级控制**：用户/管理员分离
- ✅ **多数据库权限隔离**：user_db_permissions 表

### Token 管理

```python
# Access Token（短期）
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Refresh Token（长期）
REFRESH_TOKEN_EXPIRE_DAYS = 30

# 每用户最多活跃 Token 数
MAX_ACTIVE_REFRESH_TOKENS = 10
```

### 数据安全

- ✅ **SQL 注入防护**：参数化查询
- ✅ **XSS 防护**：输入验证和转义
- ✅ **CORS 配置**：跨域请求控制
- ✅ **敏感数据加密**：密码、Token 加密存储

### API 安全

- ✅ **API 限流**：用户每小时 2000 秒，IP 每小时 300 秒
- ✅ **响应大小限制**：匿名 1MB，用户 6MB
- ✅ **请求超时控制**：最长 30 秒
- ✅ **失败登录锁定**：5 次失败锁定 15 分钟

---

## 📈 监控和维护

### 日志系统

#### 6 个异步队列设计

1. **log_queue** - ApiUsageLog（auth.db）
2. **keyword_log_queue** - ApiKeywordLog（logs.db）
3. **statistics_queue** - ApiStatistics（logs.db）
4. **html_visit_queue** - HTML 访问统计（logs.db）
5. **summary_queue** - ApiUsageSummary（auth.db）
6. **user_activity_queue** - 用户活动（跨进程）

#### 后台写入线程

每个队列都有一个专用的后台写入线程：
```python
def log_writer_thread():
    while True:
        batch = []
        # 收集批次
        for _ in range(BATCH_SIZE):
            try:
                item = log_queue.get(timeout=FLUSH_INTERVAL)
                batch.append(item)
            except Empty:
                break
        # 批量写入
        if batch:
            write_to_database(batch)
```

#### TrafficLoggingMiddleware 流程

```
请求进入
   │
   ├─> 记录开始时间
   │
   ├─> 处理请求
   │
   ├─> 记录结束时间
   │
   ├─> 计算时长
   │
   ├─> 提取参数（char, location 等）
   │
   ├─> 日志入队
   │   ├─> log_queue（用户日志）
   │   ├─> keyword_log_queue（关键词）
   │   ├─> statistics_queue（统计）
   │   └─> user_activity_queue（活动）
   │
   └─> 返回响应
```

### 自动化任务

使用 APScheduler 定时执行：

```python
# 每小时第 5 分钟：统计聚合
scheduler.add_job(
    aggregate_statistics,
    trigger="cron",
    minute=5
)

# 每周日凌晨 3:00：清理旧日志
scheduler.add_job(
    cleanup_old_logs,
    trigger="cron",
    day_of_week="sun",
    hour=3
)

# 每 30 分钟：清理临时文件
scheduler.add_job(
    cleanup_temp_files,
    trigger="interval",
    minutes=30
)
```

### 数据库维护命令

```bash
# 查看数据库大小
curl http://localhost:5000/api/logs/database/size \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 清理旧日志（试运行）
curl -X DELETE "http://localhost:5000/api/logs/cleanup?days=30&dry_run=true" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 手动触发统计聚合
curl -X POST "http://localhost:5000/api/logs/aggregate" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 优化数据库
curl -X POST "http://localhost:5000/admin/sql/optimize" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 执行 VACUUM
curl -X POST "http://localhost:5000/admin/sql/vacuum" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

## ⚡ 技术栈

### 核心框架
- **FastAPI 0.116.1** - 现代化的 Python Web 框架
- **Uvicorn 0.35.0** - 高性能 ASGI 服务器
- **Pydantic 2.11.7** - 数据验证和序列化

### 数据库
- **SQLite 3** - 轻量级关系型数据库（8 个数据库）
- **SQLAlchemy 2.0.43** - Python SQL 工具包和 ORM
- **Redis 7.1.0** - 内存数据库（缓存和会话）

### 数据处理
- **Pandas 2.3.2** - 数据分析和处理
- **NumPy 2.3.2** - 科学计算
- **OpenCC 1.1.9** - 简繁体转换

### 认证和安全
- **python-jose 3.5.0** - JWT Token 处理
- **passlib 1.7.4** - 密码哈希
- **bcrypt 3.2.0** - 密码加密算法

### 任务调度
- **APScheduler 3.11.2** - 定时任务调度器

### 文件处理
- **openpyxl 3.1.5** - Excel 文件读写
- **python-docx 1.2.0** - Word 文档处理
- **xlrd 2.0.1** - Excel 读取
- **lxml 5.2.2** - XML/HTML 处理

### 声学分析
- **praat-parselmouth 0.4.3** - Praat 声学分析（Python 绑定）
- **scipy >= 1.10.0** - 科学计算（Praat 依赖）
- **FFmpeg** - 音视频处理（系统依赖）

### 生产部署
- **Gunicorn 21.2.0** - WSGI HTTP 服务器
- **GZip Middleware** - 响应压缩

---

## 🏗️ 项目结构

```plaintext
backend-fastapi/
├── app/                          # 应用主目录
│   ├── __init__.py
│   ├── main.py                   # FastAPI 应用入口
│   │
│   ├── auth/                     # 用户认证模块
│   │   ├── database.py           # 认证数据库操作
│   │   ├── dependencies.py       # 认证依赖注入
│   │   ├── models.py             # 用户数据模型
│   │   ├── service.py            # 认证业务逻辑
│   │   ├── permission_cache.py   # 权限缓存 ⭐ 新增
│   │   └── utils.py              # 认证工具函数
│   │
│   ├── custom/                   # 自定义数据模块
│   │   ├── database.py           # 自定义数据库操作
│   │   ├── delete.py             # 删除操作
│   │   ├── models.py             # 数据模型
│   │   ├── read_custom.py        # 读取操作
│   │   └── write_submit.py       # 写入操作
│   │
│   ├── logs/                     # 日志统计系统
│   │   ├── __init__.py
│   │   ├── API_USAGE.md          # 日志系统文档
│   │   ├── api_logger.py         # API 日志记录器
│   │   ├── database.py           # 日志数据库操作
│   │   ├── logs_stats.py         # 统计路由
│   │   ├── models.py             # 日志数据模型
│   │   ├── scheduler.py          # 定时任务调度器
│   │   └── service/              # 日志服务 ⭐ 新增
│   │       ├── api_limiter.py    # API 限流
│   │       └── ...
│   │
│   ├── routes/                   # 路由模块
│   │   ├── __init__.py           # 路由注册
│   │   ├── admin/                # 管理员路由 
│   │   │   ├── cache_manager.py  # 缓存管理
│   │   │   ├── permissions.py    # 权限管理
│   │   │   └── ...
│   │   ├── admin.py              # 管理员主路由
│   │   ├── auth.py               # 认证路由
│   │   ├── batch_match.py        # 批量匹配
│   │   ├── custom_query.py       # 自定义查询
│   │   ├── form_submit.py        # 表单提交
│   │   ├── get_coordinates.py    # 坐标查询
│   │   ├── get_locs.py           # 地点列表
│   │   ├── get_partitions.py     # 分区查询
│   │   ├── get_regions.py        # 区域查询
│   │   ├── index.py              # 首页路由
│   │   ├── new_pho.py            # 新音韵查询
│   │   ├── phonology.py          # 传统音韵查询
│   │   ├── search.py             # 搜索功能
│   │   └── user.py               # 用户路由
│   │
│   ├── schemas/                  # 数据模型/模式
│   │   ├── __init__.py
│   │   ├── admin.py              # 管理员模式
│   │   ├── auth.py               # 认证模式
│   │   ├── form.py               # 表单模式
│   │   ├── phonology.py          # 音韵模式
│   │   └── user.py               # 用户模式
│   │
│   ├── service/                  # 服务逻辑层
│   │   ├── locs_regions.py       # 地理信息服务
│   │   ├── match_input_tip.py    # 输入提示匹配
│   │   ├── new_pho.py            # 新音韵服务
│   │   ├── phonology2status.py   # 音韵状态转换
│   │   ├── phonology_classification_matrix.py  # 音韵分类矩阵
│   │   ├── process_sp_input.py   # 特殊输入处理
│   │   ├── search_chars.py       # 字符搜索
│   │   ├── search_tones.py       # 声调搜索
│   │   └── status_arrange_pho.py # 音韵状态排列
│   │
│   ├── sql/                      # SQL 管理模块
│   │   ├── __init__.py
│   │   ├── choose_db.py          # 数据库选择器
│   │   ├── db_pool.py            # 数据库连接池
│   │   ├── index_manager.py      # 索引管理器
│   │   ├── sql_routes.py         # SQL 查询路由
│   │   ├── sql_schemas.py        # SQL 数据模式
│   │   └── sql_tree_routes.py    # 数据库树结构路由
│   │
│   ├── tools/                    # 工具模块
│   │   ├── __init__.py
│   │   ├── check_core.py         # 检查工具核心
│   │   ├── check_routes.py       # 检查工具路由
│   │   ├── file_manager.py       # 文件管理器
│   │   ├── format_convert.py     # 格式转换工具
│   │   ├── jyut2ipa_core.py      # 粤拼转IPA核心
│   │   ├── jyut2ipa_routes.py    # 粤拼转IPA路由
│   │   ├── merge_core.py         # 合并工具核心
│   │   ├── merge_routes.py       # 合并工具路由
│   │   ├── task_manager.py       # 任务管理器
│   │   └── praat/                # Praat 声学分析 ⭐ 新增
│   │       ├── routes.py         # Praat API 路由
│   │       ├── core/             # 核心分析模块
│   │       ├── schemas/          # 数据模型
│   │       └── utils/            # 工具函数
│   │
│   ├── redis_client.py           # Redis 客户端
│   └── statics/                  # 静态文件
│
├── common/                       # 通用工具类
│   ├── __init__.py
│   ├── config.py                 # 配置文件
│   ├── constants.py              # 常量定义
│   ├── api_config.py             # API 配置 ⭐ 新增
│   ├── path.py                   # 路径工具 ⭐ 新增
│   ├── getloc_by_name_region.py  # 地名查询工具
│   └── s2t.py                    # 简繁转换工具
│
├── data/                         # 数据文件
│   ├── auth.db                   # 用户认证数据库
│   ├── logs.db                   # 日志数据库
│   ├── characters.db             # 汉字数据库（用户）
│   ├── characters_admin.db       # 汉字数据库（管理员）
│   ├── dialects.db               # 方言数据库（用户）
│   ├── dialects_admin.db         # 方言数据库（管理员）
│   ├── custom.db                 # 自定义数据库（用户）
│   ├── custom_admin.db           # 自定义数据库（管理员）
│   └── dependency/               # 依赖数据文件
│
├── logs/                         # 日志文件目录
│   ├── access.log                # 访问日志
│   ├── error.log                 # 错误日志
│   └── gunicorn.pid              # Gunicorn PID
│
├── StressTest/                   # 压力测试工具 ⭐ 新增
│   ├── locustfile.py             # Locust 测试脚本
│   ├── config.py                 # 测试配置
│   ├── monitor.py                # 性能监控
│   └── README.md                 # 测试文档
│
├── .dockerignore                 # Docker 忽略文件
├── .env                          # 环境变量配置
├── .gitignore                    # Git 忽略文件
├── CHANGELOG.md                  # 更新日志
├── Dockerfile                    # Docker 配置
├── LICENSE                       # 许可证
├── README.md                     # 项目文档
├── requirements.txt              # Python 依赖
├── run.py                        # 开发启动脚本
├── serve.py                      # 生产启动脚本
└── gunicorn_config.py            # Gunicorn 配置
```

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- 遵循 **PEP 8** Python 代码规范
- 使用**类型注解**（Type Hints）
- 编写清晰的**文档字符串**（Docstring）
- 添加必要的**单元测试**
- 使用有意义的**提交消息**

### 测试要求

```bash
# 运行单元测试
pytest tests/

# 运行集成测试
pytest tests/integration/

# 生成测试覆盖率报告
pytest --cov=app tests/
```

---

## 📄 许可证

本项目采用 **MIT 许可证**。详见 [LICENSE](LICENSE) 文件。

---

## 👨‍💻 开发者

**不羈 (jengzang)**

- GitHub: [@jengzang](https://github.com/jengzang)
- 网站: [方音圖鑒](https://dialects.yzup.top/)
- Email: jengzang@outlook.com

---

## 🙏 致谢

感谢所有为本项目做出贡献的开发者和研究者。

特别感谢：
- **FastAPI** 框架团队
- **語保**、**音典**、**泛粵大典** - 数据来源
- 所有数据贡献者和测试用户

---

## 📞 联系方式

- **项目主页**：https://dialects.yzup.top/
- **GitHub Issues**：https://github.com/jengzang/backend-fastapi/issues
- **邮箱**：jengzang@outlook.com
- **前端仓库**：https://github.com/jengzang/dialects-js-frontend
- **数据预处理仓库**：https://github.com/jengzang/dialects-build

---

## 🔗 相关链接

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [API 使用文档](app/logs/API_USAGE.md)
- [更新日志](CHANGELOG.md)
- [Praat 官网](https://www.fon.hum.uva.nl/praat/)
- [Locust 官方文档](https://docs.locust.io/)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

---

**版本**: 2.0.1
**最后更新**: 2026-02-10
**文档行数**: 2000+

