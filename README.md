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

> [!NOTE]
> 本节中的数量型统计更适合视为历史快照，而不是严格实时值。  
> 如果与当前代码、当前数据库结构或本文后半部分的 2026-03 维护附录冲突，请以后者与实际代码实现为准。


| 指标 | 数值 |
|------|------|
| **代码总行数** | ~40,600 行 |
| **Python 文件数** | 231 个 |
| **API 端点数量** | 234 个（公开 23 + 用户 53 + 管理员 39 + VillagesML 107 + 其他 12）|
| **依赖包数量** | 64 个 |
| **数据库数量** | 9 个 SQLite 数据库 |
| **数据库表数** | 65+ 个表（含 VillagesML 45 张预计算表）|
| **当前版本** | 2.0.1 |
| **最后更新** | 2026-03-27 |

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

系统当前主要使用 **7 个异步队列** 进行日志批量写入：

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

# 队列 7: 诊断日志（logs.db）
# 默认只记录 error / slow；仅 MINE 显式开启时才全量记录
DIAGNOSTIC_QUEUE_MAXSIZE = 1000  # all 模式下会提升
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

### 3. 批量处理（7 个主要异步队列）

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

# 队列 7: 诊断日志
diagnostic_queue.put(diagnostic_event)  # 默认 issues_only，MINE 可切 all
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

#### 7 个主要异步队列设计

1. **log_queue** - ApiUsageLog（auth.db）
2. **keyword_log_queue** - ApiKeywordLog（logs.db）
3. **statistics_queue** - ApiStatistics（logs.db）
4. **html_visit_queue** - HTML 访问统计（logs.db）
5. **summary_queue** - ApiUsageSummary（auth.db）
6. **user_activity_queue** - 用户活动（跨进程）
7. **diagnostic_queue** - API 诊断事件（logs.db）

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

#### RequestLogMiddleware 流程（当前）

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
   ├─> 条件化采集上下文（usage / diagnostics / keyword）
   │
   ├─> 日志入队
   │   ├─> log_queue（用户日志）
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
**最后更新**: 2026-03-27
**文档行数**: 3000+

> [!IMPORTANT]
> 以下内容是 **2026-03 当前维护补充附录**。  
> 这部分用于覆盖旧 README 中已经过时、缺失或最近发生明显变化的内容。  
> 旧正文不删除，继续保留在后面，供历史背景和旧模块说明参考。  
> 若本附录与旧正文冲突，以本附录、当前代码实现、`docs/README.md` 和仓库中的真实文件为准。

---

## 2026-03 当前维护补充附录

### 目录导航

1. 当前文档分层说明
2. 当前仓库入口文件与角色
3. 当前启动与生命周期行为
4. 当前运行模式说明
5. 当前核心数据库文件说明
6. 当前路由装配总览
7. 当前日志、统计与诊断体系
8. 当前 auth usage 记录规则
9. 当前 SQL 家族接口维护口径
10. 当前地点业务接口补充说明
11. 当前 `search_chars` 紧凑响应模式说明
12. 当前 `docs/` 目录整理结果
13. 当前维护建议与排查建议

---

## 1. 当前文档分层说明

当前仓库的文档已经分成三层：

### 1.1 根目录 `README.md`

职责：

- 提供项目总体说明
- 提供当前维护补充
- 告诉接手者应先看哪些文档
- 解释当前运行方式、数据文件、日志体系、最近关键变化

不承担的职责：

- 不承载所有构建细节
- 不承载所有阶段性报告
- 不承载所有历史 review 记录

### 1.2 `docs/`

职责：

- 保留仍然适合作为“现行参考”的文档
- 面向后续维护者、联调者、排查者
- 分类保留 API、架构、实现说明、最终结论文档

当前保留在 `docs/` 中的文档应当尽量满足至少一条：

- 仍然描述当前有效接口
- 仍然描述当前有效架构
- 仍然描述当前仍在使用的实现方案
- 是最终结论性质的迁移/优化结果

### 1.3 `docs/archive/`

职责：

- 保存历史过程文档
- 保存阶段性讨论、实现记录、Checklist、Quickstart、Review、CR、Report
- 不再作为优先阅读入口，但保留检索价值

这意味着：

- 归档不是删除
- 归档也不是“无价值”
- 只是降低当前维护视角下的噪音

### 1.4 `HowToBuild.txt`

当前明确保留在仓库根目录。

理由：

- 它更像构建/部署补充说明
- 不必强行并入 `docs/`
- 当前你已经明确要求不要把它整理进 `docs/`

因此当前文档分工应该理解为：

- `README.md`：当前总入口
- `docs/`：现行参考文档
- `docs/archive/`：历史过程文档
- `HowToBuild.txt`：根目录构建/部署补充说明

---

## 2. 当前仓库入口文件与角色

### 2.1 运行入口

当前本地开发最常用入口仍然是：

```bash
python run.py
```

这个入口负责：

- 解析运行参数
- 设置 `_RUN_TYPE`
- 在 `MINE` / `EXE` 模式下控制浏览器是否自动打开
- 启动 `uvicorn` 或配合其他模式运行

### 2.2 应用入口

真正的 FastAPI 应用入口在：

- `app/main.py`

这个文件负责：

- 创建 FastAPI app
- 配置 middleware
- 启动和关闭时的生命周期逻辑
- 连接池初始化
- 日志 worker 启动
- scheduler 启动
- 启动期迁移和缓存预热

### 2.3 路由总装配入口

统一装配路由的文件是：

- `app/routes/__init__.py`

它负责挂载：

- 核心查询路由
- 地理路由
- 用户与自定义路由
- 认证路由
- 管理后台路由
- logs 路由
- SQL 路由
- 工具路由
- VillagesML 路由

### 2.4 当前日志相关关键入口

当前日志相关关键文件包括：

- `app/service/logging/middleware/traffic_logging.py`
- `app/service/logging/config/__init__.py`
- `app/service/logging/config/diagnostics.py`
- `app/service/logging/core/models.py`
- `app/service/logging/core/database.py`

这些文件共同负责：

- auth.db usage detail/summary 写入
- logs.db hourly/daily 统计
- HTML 访问统计
- API 诊断日志
- keyword logging（当前默认关闭）

### 2.5 当前 SQL 相关关键入口

主要包括：

- `app/sql/sql_routes.py`
- `app/sql/sql_schemas.py`
- `app/sql/index_manager.py`

最近与 README 相关、需要强调的一点是：

- `/sql/query` 的 `page_size` 上限已从旧的 `9999` 收紧到 `2000`

### 2.6 当前新地理业务接口入口

这次新增的地点业务接口在：

- `app/routes/geo/locations.py`
- `app/service/geo/locations.py`

提供：

- `GET /api/locations/detail?name=<簡稱>`
- `GET /api/locations/partitions`

---

## 3. 当前启动与生命周期行为

当前应用在 startup 阶段会做一批明确的初始化动作。下面这部分不是泛泛而谈，而是对应到 `app/main.py` 当前真实存在的行为。

### 3.1 数据库连接池初始化

应用启动时会初始化多组连接池，主要面向这些库：

- `QUERY_DB_ADMIN`
- `QUERY_DB_USER`
- `DIALECTS_DB_ADMIN`
- `DIALECTS_DB_USER`
- `CHARACTERS_DB_PATH`

这一步的意义：

- 提前把高频数据库连接准备好
- 避免第一次请求时才懒初始化导致尖峰抖动

### 3.2 `supplements.db` 迁移

当前 startup 会迁移：

- `supplements.db`

相关逻辑主要用于：

- 用户补充数据表
- 例如 user regions 一类补充型结构

### 3.3 `logs.db` 迁移

当前 startup 会处理 `logs.db` 中两类重要结构：

1. hourly/daily 统计表
2. API 诊断日志表

这意味着如果你的 `logs.db` 里原本没有诊断表，应用启动后会自动补齐。

这也是为什么后续接入新的诊断链路时，不需要手工先建表。

### 3.4 方言缓存预热

startup 当前还会预热一部分方言缓存。

这一步的意义：

- 避免首个查询请求时才做全量加载
- 让部分高频功能在首次访问时更稳定

### 3.5 工具临时文件清理

应用启动后还会做：

- 工具临时文件清理

主要目的是：

- 避免历史任务文件不断累积
- 控制本地/服务器存储占用

### 3.6 非 Gunicorn worker 场景的后台线程

在非 Gunicorn worker 场景下，startup 还会启动：

- API logger workers
- scheduler
- 周期性 cleanup thread

这部分对本地开发尤其重要，因为：

- 你在本地 `python run.py` 启动时，很多日志与统计行为就是靠这些后台线程落库

### 3.7 shutdown 行为

关闭阶段会做：

- 停止 logger workers
- 停止 scheduler
- 关闭 Redis
- 关闭数据库连接池

这一点值得写进 README，是因为很多“为什么停服务后有些日志没完全刷完”之类的问题，都和这条链路有关。

---

## 4. 当前运行模式说明

### 4.1 `MINE`

这是当前最适合个人开发和排查问题的模式。

特点：

- 适合本地调试
- 适合打开浏览器联调
- 适合观察日志
- 适合在需要时开启更强的诊断能力

和最近改动最相关的一点是：

- 只有在 `MINE` 下，才允许显式开启“全量 API 诊断日志”

默认并不会自动开启。

### 4.2 `WEB`

这是常规服务模式。

特点：

- 适合正常对外服务
- 文档和日志行为更保守
- 不建议在生产环境直接打开全量诊断

### 4.3 `EXE`

这是打包/桌面相关模式。

特点：

- 更偏向单机工具或桌面分发
- 行为与 `MINE`、`WEB` 不完全相同

### 4.4 当前推荐组合

如果你的目标是：

- 开发新接口
- 观察最近新增的诊断日志
- 调试 `search_chars`
- 调试地点业务接口

推荐：

```bash
python run.py -r MINE
```

如果只是常规联调和保守调试：

- 使用 `MINE`
- 保持诊断日志为默认 `issues_only`
- 不主动打开全量诊断

---

## 5. 当前核心数据库文件说明

下面这部分是对当前维护者真正重要的数据库清单，而不是泛泛的“我们有很多 SQLite 数据库”。

### 5.1 `data/auth.db`

主要职责：

- 用户
- 权限
- refresh token
- usage 明细
- usage summary
- leaderboard 相关统计

最近与它相关的关键变化：

- usage 路径记录规则已收紧
- `/sql/query/count`、`/sql/query/columns`、`/sql/distinct/*` 不再进入 auth usage
- `api_usage_summary` 历史归并改为一次性脚本方案

### 5.2 `data/logs.db`

主要职责：

- API hourly/daily 统计
- 页面访问统计
- API 诊断日志
- 历史参数关键词日志

最近与它相关的关键变化：

- 新增 `api_diagnostic_events`
- 诊断日志默认只记录 error/slow
- `MINE` 模式下可选开启全量诊断
- `api_keyword_log` 默认关闭

### 5.3 `data/query_user.db`

主要职责：

- 业务查询数据
- `/sql/query` 等 SQL 家族接口常用数据源之一

### 5.4 `data/dialects_user.db`

主要职责：

- 方言主数据
- 地点/读音/地点树等地理与读音相关接口的重要来源

### 5.5 `data/characters.db`

主要职责：

- 字书、字位、古音相关数据
- `search_chars` 等能力依赖它来构造字级信息

### 5.6 `data/villages.db`

主要职责：

- VillagesML 数据
- 自然村、空间、语义、模式、区域、ML 计算等模块

### 5.7 `data/supplements.db`

主要职责：

- 用户补充数据
- 非核心大表，但对个别用户/地区类能力仍有作用

### 5.8 当前数据库维护建议

如果你在本地遇到功能异常，优先确认：

1. 这些数据库文件是否存在
2. 是否路径正确
3. 是否是 user/admin 库混用导致的
4. 是否是当前 `path.py` / 环境路径配置差异导致的

---

## 6. 当前路由装配总览

下面这部分不是完整 API 文档，而是帮助维护者理解“哪些大类能力是从哪里挂进来的”。

### 6.1 核心查询路由

来自：

- `app.routes.core.phonology`
- `app.routes.core.matrix`
- `app.routes.core.new_pho`
- `app.routes.core.search`
- `app.routes.core.compare`

主要覆盖：

- 查中古
- 查音位
- 查字
- 查调
- 音系矩阵
- 对比分析

### 6.2 地理路由

来自：

- `app.routes.geo.get_regions`
- `app.routes.geo.get_partitions`
- `app.routes.geo.locations`
- `app.routes.geo.batch_match`
- `app.routes.geo.get_coordinates`
- `app.routes.geo.get_locs`

这里面近期最值得注意的是 `locations`：

- `/api/locations/detail`
- `/api/locations/partitions`

这两个接口是最近为前端收口 `/sql/query` 依赖而新增的。

### 6.3 用户与自定义路由

来自：

- `form_submit`
- `custom_query`
- `custom_regions`

这些路由对应：

- 用户自定义查询
- 自定义分区
- 表单数据

### 6.4 认证路由

来自：

- `app.routes.auth`

以 `/auth` 为前缀挂载。

这部分和最近改动最相关的点包括：

- `/auth/login` 的 usage/detail/diagnostic 行为调整
- 用户排行榜仍从这里暴露

### 6.5 管理后台路由

来自：

- `app.routes.admin`

主要包括：

- analytics
- leaderboard
- users
- sessions
- submissions

### 6.6 工具路由

包括：

- `app.tools`
- `app.tools.praat.routes`

覆盖：

- Check
- Jyut2IPA
- Merge
- Praat

### 6.7 SQL 路由

通过：

- `setup_sql_routes(app)`

统一挂载。

这部分不是近期被删，而是被“业务场景逐步收口”。

也就是说：

- `/sql/*` 仍然保留
- 但普通业务组件正在逐步改用语义更明确的业务接口

### 6.8 日志路由

通过：

- `setup_logs_routes(app)`

统一挂载。

### 6.9 VillagesML 路由

通过：

- `setup_villages_routes(app)`

统一挂载。

这是一个相对独立、模块化较强的子系统。

---

## 7. 当前日志、统计与诊断体系

这一段是最近变化最大的部分，也是最需要在 README 里补充的。

### 7.1 `auth.db` 与 `logs.db` 已经分工

当前原则很明确：

- `auth.db`：服务用户 usage、summary、leaderboard
- `logs.db`：服务 logs 统计、诊断、页面访问等

不要再把这两套职责混在一起理解。

### 7.2 `auth.db` 相关

当前 usage 链路主要写入：

- `api_usage_logs`
- `api_usage_summary`

主要用途：

- 用户个人排行榜
- 后台排行榜
- usage 汇总

### 7.3 `logs.db` 相关

当前重点表包括：

- hourly/daily API 统计表
- 页面访问统计表
- `api_diagnostic_events`
- `api_keyword_log`（当前默认关闭实时入口）

### 7.4 当前日志队列概览

在 `traffic_logging.py` 中，当前仍然存在多条队列：

- `log_queue`
- `keyword_log_queue`
- `statistics_queue`
- `html_visit_queue`
- `summary_queue`
- `online_time_queue`
- `diagnostic_queue`

这意味着：

- 当前系统不是单一路径同步写库
- 很多日志行为依赖后台 queue + worker
- 本地调试时如果你只看请求返回，不一定能立刻看到所有数据已落库

### 7.5 `diagnostic_queue`

这是最近新增或强化的一条链路。

职责：

- 把错误 API
- 超时 API
- 以及 `MINE + 全量模式` 下的普通 API 请求

写入：

- `logs.db.api_diagnostic_events`

### 7.6 当前诊断日志的路径判断

当前诊断日志**不复用**：

- `RECORD_API / IGNORE_API`
- `API_WHITELIST`

诊断范围使用自己的规则：

- include prefixes
- exclude patterns

当前 include prefixes：

- `/api/`
- `/auth/`
- `/sql/`
- `/admin/`

当前 exclude patterns：

- `/__ping`
- `/docs`
- `/docs/*`
- `/openapi.json`
- `/statics/*`

### 7.7 诊断日志默认记录什么

当前默认 capture mode：

- `issues_only`

意味着默认只记录：

- `error`
- `slow`
- `error_and_slow`

### 7.8 什么时候才会全量记录

必须同时满足：

1. `_RUN_TYPE == "MINE"`
2. `ENABLE_FULL_API_DIAGNOSTICS_IN_MINE = True`

才会切到：

- `DIAGNOSTIC_CAPTURE_MODE = "all"`

这时诊断范围内所有 API 都会记一条事件，正常请求会落：

- `event_type = "normal"`

### 7.9 当前诊断日志阈值

当前慢请求阈值固定为：

- `10_000 ms`

也就是：

- 超过 `10s`

才会被默认 slow 模式抓进诊断表。

### 7.10 当前诊断日志记录的内容

当前设计上会记录：

- path
- route template
- method
- status code
- duration_ms
- user_id / username
- ip / user_agent / referer
- 脱敏后的 headers
- query params
- request body 摘要
- response size
- response preview
- exception type / message / stack

这套设计的原则不是“猜原因”，而是“保留足够复现的证据”。

### 7.11 当前 keyword logging

当前：

- `ENABLE_API_KEYWORD_LOGGING = False`

也就是说默认不再做：

- route config 匹配
- query/body 参数采集
- request body 主动读取
- `ApiKeywordLog` 入队

原因：

- 当前还没有明确消费这些统计
- 但请求期成本较高
- 所以先默认关闭，保留未来按需开启的能力

### 7.12 当前 HTML 访问统计

这条链路仍然保留在 `logs.db`：

- 主要针对页面访问
- 不和新的 API 诊断日志混用

### 7.13 当前 auth usage 与 logs diagnostics 的差异

需要明确区分：

#### auth usage

目的：

- 统计用户用了哪些 API
- 做 summary
- 做排行榜

#### logs diagnostics

目的：

- 复现错误
- 复现超时
- 本地调试时分析 API 行为

两者不应该混淆。

---

## 8. 当前 auth usage 记录规则

### 8.1 当前匹配语义

这次已经正式落地为：

- 带 `*` 才通配
- 不带 `*` 就精确匹配

这是一个很重要的维护约定，因为它直接影响：

- `api_usage_logs.path`
- `api_usage_summary.path`
- leaderboard 统计口径

### 8.2 当前会进入 auth usage 的主要路径模式

当前 `RECORD_API` 中比较值得关注的包括：

- `/auth/login`
- `/api/phonology*`
- `/api/get_coordinates`
- `/api/search_tones/`
- `/api/search_chars/`
- `/api/compare/*`
- `/api/submit_form`
- `/api/delete_form`
- `/api/ZhongGu`
- `/api/YinWei`
- `/api/charlist`
- `/sql/query`
- `/sql/distinct-query`
- `/sql/mutate`
- `/sql/batch-mutate`
- `/sql/batch-replace-preview`
- `/sql/batch-replace-execute`
- `/sql/tree/full`
- `/sql/tree/lazy`
- `/api/tools/*`
- `/api/feature_counts`
- `/api/feature_stats`
- `/api/pho_pie*`
- `/user/custom/*`
- `/api/custom_regions`
- `/api/villages/*`

### 8.3 当前明确不进入 auth usage 的路径

当前 `IGNORE_API` 中已经明确包括：

- `/sql/query/columns`
- `/sql/query/count`
- `/api/tools/*/download/*`
- `/api/tools/*/progress/*`

另外还有一类虽然不在 `IGNORE_API` 里，但现在也已经不再纳入 auth usage 视角的路径：

- `/sql/distinct/*`

### 8.4 当前这样收口的原因

这些路径不进入 auth usage 的主要原因包括：

- 只是辅助元数据请求
- 不代表真实业务使用
- 容易污染排行榜和 summary
- 动态参数太多时会把统计打散

### 8.5 当前历史 summary 的处理原则

已经改成：

- 未来写入直接规范化
- 历史 `api_usage_summary` 通过一次性脚本迁移
- 不在主应用里自动做历史重写

这部分对维护者最重要的理解是：

- 运行时修正未来写入
- 历史数据通过一次性迁移脚本处理
- 不是在 startup 里做强行归并

---

## 9. 当前 SQL 家族接口维护口径

### 9.1 `/sql/query`

仍然保留。

用途：

- 通用查询
- 某些后台/浏览器式页面依然需要

当前关键变化：

- `page_size` 上限已收紧到 `2000`

### 9.2 `/sql/query/count`

当前：

- 仍有接口
- 但不进入 auth usage

原因：

- 更像辅助统计
- 不代表真实业务操作

### 9.3 `/sql/query/columns`

用途：

- 查表字段结构
- 返回列名、类型、主键等元数据

当前：

- 不进入 auth usage

原因：

- 它是元数据探测接口
- 更像前端初始化或管理页辅助能力

### 9.4 `/sql/distinct/*`

用途：

- 整列 distinct 枚举

当前：

- 不进入 auth usage

### 9.5 `/sql/distinct-query`

用途：

- 带筛选上下文的 distinct 联动枚举

当前：

- 继续进入 auth usage

原因：

- 它比 `distinct/*` 更接近真实用户筛选行为

### 9.6 当前 SQL 家族接口的总体方向

不是“一次性删除 SQL 家族接口”，而是：

- 继续保留通用能力
- 但把普通业务组件逐步从 `/sql/query` 上收走

最近落地的就是这类收口：

- 地点详情
- 地点/分区数据

---

## 10. 当前地点业务接口补充说明

这部分是最近新加的正式业务接口，README 里必须补充，否则旧正文里不会体现。

### 10.1 `GET /api/locations/detail?name=<簡稱>`

用途：

- 替换普通业务组件里“按地点简称查 `query.dialects`”的 `/sql/query`

返回格式当前是：

- `{"data": [row]}`

不是语义化的 `location/admin/tones` 结构。

这是故意的，目的是：

- 第一阶段先收敛业务入口
- 尽量不重写前端现有展示层

### 10.2 `GET /api/locations/partitions`

用途：

- 替换前端为建树而整表扫 `query.dialects` 的 `/sql/query`

返回格式当前也是：

- `{"data": [row, ...]}`

而不是后端直接返回三棵树。

### 10.3 为什么第一阶段不直接语义化

原因是：

- 前端现有组件已经有大量 row-shaped 解析逻辑
- 先改入口、后改数据形态，风险更低
- 先把普通业务组件从 `/sql/query` 收走，是第一阶段的核心目标

### 10.4 当前 detail 接口字段口径

当前仍以繁体原始字段为主，例如：

- `簡稱`
- `語言`
- `地圖集二分區`
- `音典分區`
- `字表來源（母本）`
- `經緯度`
- `省`
- `市`
- `縣`
- `鎮`
- `行政村`
- `自然村`
- `T1陰平` 到 `T10輕聲`

### 10.5 当前 partitions 接口字段口径

当前主要返回前端建树所需最小字段，例如：

- `簡稱`
- `語言`
- `存儲標記`
- `地圖集二分區`
- `音典分區`
- `省`
- `市`
- `縣`
- `鎮`
- `行政村`
- `自然村`

### 10.6 当前接口替换意义

维护上应理解为：

- 后端开始提供语义更明确的入口
- 前端短期内仍可沿用旧数据形态处理逻辑
- 第二阶段再考虑彻底改造成更语义化的数据结构

---

## 11. 当前 `search_chars` 紧凑响应模式说明

### 11.1 背景

原本 `search_chars` 的问题不是单纯 SQL 慢，而是：

- `positions`
- `old_position`

这两块字级元数据被重复塞进每一条 `char × location` 行里。

一旦地点很多、字很多，响应体会膨胀得非常快。

### 11.2 当前新增的响应模式

新增：

- `response_mode=compact`

### 11.3 当前 compact 的核心变化

在 compact 模式下：

- `result` 行里不再重复带 `positions`
- `result` 行里不再重复带 `old_position`
- 新增 `char_meta`
- 把这两部分按字聚合到 `char_meta[char]`

### 11.4 为什么这很重要

这是当前 README 里必须补充的真实行为，因为它直接影响：

- 网络体积
- 前端适配
- 性能排查

### 11.5 当前兼容策略

默认旧模式没有删：

- 不传 `response_mode=compact` 时，旧格式仍保留

也就是说：

- compact 是可选增强
- 不是强制破坏式变更

---

## 12. 当前 `docs/` 目录整理结果

### 12.1 当前 `docs/` 中保留的活跃文档

当前活跃文档已经收敛到 30 个左右，重点包括：

#### 根目录活跃文档

- `docs/admin_analytics_api.md`
- `docs/admin_leaderboard_api.md`
- `docs/api_stats_write_mechanism.md`
- `docs/ip_location_api_reference.md`
- `docs/session_online_vs_active.md`
- `docs/README.md`

#### `docs/api/`

- `docs/api/admin/custom_regions.md`
- `docs/api/custom_regions/frontend_guide.md`
- `docs/api/villagesml/api_reference.md`
- `docs/api/villagesml/auth_guide.md`
- `docs/api/villagesml/frontend_guide.md`

#### `docs/architecture/`

- `docs/architecture/project_architecture.md`
- `docs/architecture/feature_overview.md`
- `docs/architecture/app_structure_analysis.md`
- `docs/architecture/db_selector_final_summary.md`
- `docs/architecture/multi_auth_account_linking_plan.md`

#### `docs/migration/`

- `docs/migration/migration_complete_report.md`

#### `docs/implementation/`

- clustering:
  - `endpoints_implementation.md`
  - `endpoints_usage.md`
  - `spatial_workflow.md`
- regions:
  - `endpoint_implementation.md`
  - `api_hierarchy_status.md`
- semantic:
  - `subcategory_api_update.md`
- subset:
  - `compare_api_update.md`
- township:
  - `filter_guide.md`
  - `full_path_support.md`
- vectors:
  - `api_complete.md`

#### `docs/optimization/`

- `summary.md`

#### `docs/issues/`

- `database_issues.md`
- `regional_vectors_api_issues.md`

### 12.2 当前 `docs/archive/` 中归档的内容类型

归档的内容主要包括：

- Quickstart
- Checklist
- Review
- Code Review
- Progress
- Summary
- Bugfix 报告
- 过程性实现文档
- 中间态迁移与优化分析

### 12.3 为什么这么整理

原因很明确：

- 原来的 `docs/` 顶层过于拥挤
- 现行参考文档和历史过程文档混在一起
- 接手者很难判断“现在哪些文档仍然有效”

### 12.4 当前 README 与 `docs/README.md` 的分工

建议理解为：

- 根目录 `README.md`
  - 项目总入口
  - 当前维护补充
  - 面向新接手者
- `docs/README.md`
  - 现行文档索引
  - 面向后续查具体文档的人

---

## 13. 当前维护建议与排查建议

### 13.1 如果你在排查接口问题

优先看：

1. 路由是否挂载正确
2. 数据库文件是否齐全
3. 当前 `_RUN_TYPE`
4. 是否命中了限流/usage/diagnostic 的哪一套逻辑
5. 该行为属于 `auth.db` 还是 `logs.db`

### 13.2 如果你在排查排行榜或 usage 问题

优先看：

1. `app/common/api_config.py`
2. `app/service/logging/utils/usage_paths.py`
3. `app/service/user/leaderboard_service.py`
4. `auth.db` 中的 `api_usage_logs` / `api_usage_summary`

### 13.3 如果你在排查慢接口或报错接口

优先看：

1. `logs.db.api_diagnostic_events`
2. `app/service/logging/config/diagnostics.py`
3. `traffic_logging.py`
4. 当前是否是 `issues_only` 还是 `all`

### 13.4 如果你在排查前端联调问题

优先看：

1. 地点业务接口是否已经切到：
   - `/api/locations/detail`
   - `/api/locations/partitions`
2. `search_chars` 是否需要切到 `response_mode=compact`
3. 是否还在误用 `/sql/query/columns` 或 `/sql/distinct/*` 来代表真实业务行为

### 13.5 当前 README 后续还应继续补的方向

这份附录已经补充了当前最关键的变化，但后续还可以继续增强：

- 更系统地补充 admin analytics 和 leaderboard 的维护视角
- 更系统地补充 VillagesML 的运行依赖与数据流
- 更系统地补充各数据库表之间的关系
- 更系统地补充本地调试 runbook

---

## 14. 当前本地开发、联调与排查 Runbook

### 14.1 开发前建议先确认的事项

在当前仓库里，本地开发最容易踩坑的不是 Python 语法层，而是：

- 运行模式不一致
- 数据库文件缺失
- 某些数据库路径被本地改动影响
- 误把 `auth.db` 统计问题当成 `logs.db` 问题
- 误把 `logs.db` 的诊断日志当成 usage 排行数据
- 忽略了中间件与后台线程对日志行为的影响

因此，建议任何一次正式调试之前，先确认：

1. 当前 `RUN_TYPE` 是什么
2. 本地启动入口是 `run.py` 还是 Gunicorn
3. `data/` 目录中的核心数据库文件是否齐全
4. `logs.db` 是否已经自动迁移出诊断表
5. 是否存在本地未提交改动，尤其是 `path.py`、配置文件、数据库文件路径选择器
6. 当前是不是在 `MINE` 模式下打开了全量诊断日志
7. 当前是否还保留着前端联调时用的临时本地配置

### 14.2 建议的最小启动核对步骤

建议按下面顺序核对，而不要一上来就怀疑 API 本身：

1. 先确认 Python 环境和依赖是否完整
2. 再确认数据库文件是否存在
3. 再确认启动模式是否符合预期
4. 再确认应用启动时自动迁移是否通过
5. 最后才去看具体接口行为

如果只是想确认后端是否能起来，最小核对路径通常是：

- 启动服务
- 打开 `/docs`
- 检查 `locations/detail`
- 检查 `locations/partitions`
- 检查 `/auth/login`
- 检查一个核心只读 API

### 14.3 本地开发时最值得优先确认的数据库

如果你看到的是“启动能起来，但接口行为不对”，优先核对：

#### `auth.db`

主要影响：

- 登录
- refresh token
- usage 统计
- leaderboard
- 用户权限
- 登录限流

如果这个库有问题，常见表象包括：

- 登录失败但前端无明确解释
- `/auth/leaderboard` 数据异常
- 某些用户明明调用过 API，但排行榜没有变化
- 登录限流的 `Retry-After` 不合理

#### `logs.db`

主要影响：

- hourly/daily 路径访问统计
- HTML 页面访问统计
- 诊断日志
- 历史 keyword 统计相关逻辑

如果这个库有问题，常见表象包括：

- 管理后台的 API 表现分析异常
- 错误 API 没写到诊断表
- 超时 API 没留下诊断记录
- 文本日志还在，但库表里没有事件

#### `query_user.db`

主要影响：

- SQL 查询
- `locations/detail`
- `locations/partitions`
- 多数传统数据查询

如果这个库缺表、缺字段或路径错误，最常见的就是：

- `/sql/query` 失败
- 地点详情查不到
- 分区 rows 内容异常
- 前端说字段全空，但其实是连错库或查错库

#### `dialects_user.db`

主要影响：

- `search_chars`
- `search_tones`
- 音韵矩阵
- 地点维度的方言读音

如果这个库状态不对，通常会表现成：

- 字能查到，但地点读音不对
- 结果数量异常
- 某些地点全空
- `search_chars` 耗时异常

#### `characters.db`

主要影响：

- `search_chars` 中字级元数据
- `positions`
- `old_position`

如果这个库缺失或结构不对，通常表现为：

- `search_chars` 有行结果，但 `positions` / `old_position` 异常
- compact 模式下 `char_meta` 不完整

### 14.4 本地联调 `locations` 两个接口时的建议顺序

当前前端第一阶段应该优先切到：

- `GET /api/locations/detail`
- `GET /api/locations/partitions`

建议联调步骤如下：

1. 先拿一个已知存在的地点简称，例如 `廣州`
2. 调 `GET /api/locations/detail?name=廣州`
3. 确认返回仍然是 `data: [row]`
4. 确认 row 使用繁体原始字段
5. 再调 `GET /api/locations/partitions`
6. 直接看 `data` 是否为最小 rows
7. 核对：
   - `簡稱`
   - `語言`
   - `存儲標記`
   - `地圖集二分區`
   - `音典分區`
   - `省`
   - `市`
   - `縣`
   - `鎮`
   - `行政村`
   - `自然村`

联调时常见误区有：

- 误以为 `partitions` 已经直接返回树
- 误以为 `detail` 已经改成 `location/admin/tones`
- 误把前端适配层问题当成后端字段缺失
- 误把某几条历史音数据的空字段当成“全量数据都空”

### 14.5 本地联调 `search_chars` 时的建议顺序

当前 `search_chars` 最关键的是要先确认你到底在联调哪种模式：

- `legacy`
- `compact`

建议顺序：

1. 先用旧参数调一次默认模式
2. 看 `result` 中是否仍有 `positions` / `old_position`
3. 再加 `response_mode=compact`
4. 看 `result` 中是否移除了这两个字段
5. 看 `char_meta` 是否出现
6. 再核对前端是否已经做过兼容适配

目前不应该误解为：

- compact 是默认值
- compact 会减少结果行数
- compact 会改变 `tones_result`

当前真实含义是：

- compact 只是把字级元数据从重复行里拆出去
- 它不改变主要 `char × location` 结果行数量
- 它是可选增强，不是强制破坏式变更

### 14.6 本地联调 SQL 家族接口时的建议顺序

当前 SQL 家族接口的维护口径已经收紧，所以联调时建议明确区分：

#### 仍然代表业务数据读取的

- `/sql/query`
- `/sql/distinct-query`

#### 仅代表辅助能力或元数据探测的

- `/sql/query/columns`
- `/sql/distinct/*`
- `/sql/query/count`

联调时不要再用以下接口来代表“真实业务使用”：

- `/sql/query/columns`
- `/sql/query/count`
- `/sql/distinct/*`

因为这些接口已经明确不再进入 `auth.db` usage 统计口径。

### 14.7 当前 `/sql/query` 最值得注意的限制

当前对 `/sql/query` 的一个重要收口是：

- `page_size` 上限已经从旧的 `9999` 收紧到 `2000`

这意味着：

- 再拿 `9999` 当“全表读取默认值”已经不合理
- 如果前端还在拼 `9999`，应该改为新的业务接口
- 如果业务上真的需要更多数据，应重新设计接口，而不是继续放大通用查询口径

### 14.8 当前本地调试最推荐的观察顺序

遇到后端问题时，不建议直接从最深层的 service 开始看。更稳的顺序是：

1. 路由是否挂载
2. 请求参数是否符合 contract
3. 配置是否影响日志/usage/限流
4. 数据库文件是否正确
5. 中间件是否改变了请求行为
6. 后台队列是否导致写入延迟
7. 最后再看具体 SQL 或 service 逻辑

### 14.9 Windows 环境下当前最容易遇到的问题

当前仓库在 Windows 下已知容易碰到的点包括：

- PowerShell profile 执行策略提示
- `multiprocessing.Queue` 相关权限/环境问题
- `__pycache__` 文件锁
- Git Bash / hook 环境偶发 Win32 error 5
- 某些测试在 Windows 下冷导入时更容易暴露并发初始化问题

这些问题不一定是业务 bug，但很容易影响你对“接口本身有问题”的判断。

### 14.10 当前本地排查时的经验性建议

如果只是快速判断一个问题属于哪一层，经验上可以这样看：

- 返回结构不对：先看 route / schema / contract
- 字段全空：先看数据库与字段映射
- 排行榜不对：先看 `auth.db`
- 诊断日志没写：先看 `logs.db` 与诊断配置
- 某接口明显慢：先看诊断事件和响应体大小
- 某接口偶发 500：先看诊断表中的 stack trace

---

## 15. 当前 `auth.db` 与 `logs.db` 主要表的维护视角

### 15.1 为什么这里必须分库理解

当前维护时最容易犯的错误之一，是把 `auth.db` 和 `logs.db` 的职责混在一起。

但当前代码实际上已经把这两套职责分得很明确：

- `auth.db`
  - 用户
  - token
  - 权限
  - usage 统计
  - 排行榜
- `logs.db`
  - HTML 访问统计
  - 路径 hourly/daily
  - 诊断日志
  - 历史 keyword 统计体系

所以排查时第一步应该先判断：

- 这是“用户使用统计”问题
- 还是“开发诊断与运行日志”问题

### 15.2 `auth.db` 当前最关键的表

#### `users`

主要承载：

- 用户基本信息
- 在线时长累计
- 排行榜相关用户维度数据

#### `refresh_tokens`

主要承载：

- refresh token 生命周期
- token 失效与撤销
- 登录态续签

#### `api_usage_logs`

主要承载：

- 单次 usage 明细
- 真实时长
- 真实路径或规范化路径
- 用户维度调用历史

当前要特别注意：

- 它不是 `logs.db` 的诊断表
- 它也不是 `api_keyword_log`
- 它的定位是 usage detail，不是错误复现场景

#### `api_usage_summary`

主要承载：

- usage 聚合值
- leaderboard 统计基础
- 每用户、每 API 路径的聚合时长和流量

当前要特别注意：

- 这张表是排行榜与 usage 画像的重要基础
- 所以对它的历史迁移必须非常保守
- 当前采用的是一次性脚本方案，而不是主应用启动自动改历史

#### `user_db_permissions`

主要承载：

- 用户与数据库的访问权限
- 不同数据域的隔离

### 15.3 `logs.db` 当前最关键的表

#### `api_visit_log`

当前作用：

- 记录 HTML 页面访问统计
- 存总量和按日统计

它不等于 API 请求统计，也不等于 usage 统计。

#### `api_keyword_log`

当前作用（历史设计上）：

- 记录 API 参数级别的关键字明细
- 支持后续统计 query/body 中出现过什么值

但当前维护口径已经变了：

- 默认已经关闭实时采集
- 不是删表
- 也不是删历史数据
- 而是默认不再让请求线程付出 body 解析成本

也就是说：

- 表还在
- 聚合逻辑还在
- 但默认不会继续积极写新数据

#### `api_statistics`

当前作用：

- 聚合 `api_keyword_log` 和 usage 类统计
- 供某些后台统计能力读取

这类表更偏“批处理统计结果”，不是单次请求明细。

#### `api_diagnostic_events`

当前作用：

- 记录错误 API
- 记录超时 API
- 在 `MINE + 全量诊断模式` 下，记录所有诊断范围内 API

它当前是：

- 新诊断体系核心表
- 面向复现错误与分析慢请求
- 不参与 leaderboard
- 不复用 `auth.db` usage 逻辑

### 15.4 当前 `api_diagnostic_events` 的字段理解方式

维护时建议从“复现场景”去理解，而不是只看字段名字：

- `event_type`
  - 事件类别
- `path`
  - 原始请求路径
- `route_template`
  - 规范化后的模板路径
- `method`
  - 请求方法
- `status_code`
  - 最终状态码，或异常 fallback 500
- `duration_ms`
  - 真实时长
- `user_id` / `username`
  - 当前用户上下文
- `ip`
  - 来源地址
- `request_headers_json`
  - 关键请求头快照
- `query_params_json`
  - 查询参数快照
- `request_body_text`
  - 截断后的请求体
- `request_body_truncated`
  - 是否截断
- `request_size`
  - 请求大小
- `response_size`
  - 响应大小
- `response_started`
  - 是否已经发送 response start
- `response_completed`
  - 是否完整写完 body
- `phase_hint`
  - 失败/慢请求所处阶段
- `exception_type`
  - 异常类型
- `exception_message`
  - 异常消息
- `stack_trace_text`
  - 截断后的调用栈
- `response_preview_text`
  - 可选错误响应预览
- `notes_json`
  - 补充元数据

### 15.5 当前 `api_diagnostic_events` 里的 `event_type` 如何理解

当前可能出现：

- `error`
- `slow`
- `error_and_slow`
- `normal`

其中：

- `normal`
  - 只会在 `MINE + 全量诊断模式` 下出现
- `error`
  - 错误但未超过慢阈值
- `slow`
  - 成功但耗时超过阈值
- `error_and_slow`
  - 同一个请求同时满足两者

### 15.6 为什么 `api_keyword_log` 和 `api_diagnostic_events` 必须拆开

当前维护上必须明确：

- `api_keyword_log`
  - 面向参数统计
  - 按字段拆散
  - 不适合做单次请求复现
- `api_diagnostic_events`
  - 面向错误和慢请求复现
  - 一次请求一条事件
  - 保留请求级上下文

如果把两者混起来，会导致：

- 表语义混乱
- 写入成本和读取方式互相牵制
- 既不适合统计，也不适合排障

### 15.7 当前 auth usage 与诊断日志最容易混淆的点

维护时最容易混淆的是下面几组：

#### `api_usage_logs` vs `api_diagnostic_events`

前者：

- 面向 usage
- 主要服务排行榜和聚合
- 不追求完整复现场景

后者：

- 面向错误/慢请求排障
- 追求保留足够上下文
- 不服务排行榜

#### `api_usage_summary` vs `api_statistics`

前者：

- 在 `auth.db`
- 是用户 usage 聚合
- 服务 leaderboard

后者：

- 在 `logs.db`
- 是日志统计侧的聚合结果
- 不等同于用户 usage 排名

#### `update_count(path)` vs `should_record_auth_usage(path)`

前者：

- 走 `logs.db`
- 是 path hourly/daily 统计

后者：

- 走 `auth.db`
- 是 usage 记录范围判定

这两者不是一套逻辑，不能拿一边去推另一边。

### 15.8 当前最适合拿来排问题的表

如果你在排查：

- 登录与 token：看 `auth.db`
- usage 排行：看 `api_usage_summary`
- 某用户到底调过哪些 API：看 `api_usage_logs`
- 某个 500 为何出现：看 `logs.db.api_diagnostic_events`
- 某页面访问量：看 `api_visit_log`
- 某路径访问次数趋势：看 hourly/daily usage 统计

---

## 16. 当前后台队列、写入链路与性能敏感点

### 16.1 当前为什么必须理解“请求路径”和“后台写入路径”

在这个项目里，很多日志并不是请求线程直接写库，而是：

- 请求线程先收集最小必要信息
- 丢进队列
- 后台线程批量写入

这意味着：

- 你看到的请求成功，不等于相关日志已经立刻落库
- 队列积压时，问题可能表现为“请求没事，但后台统计延迟”
- 调优时必须区分：
  - 请求线程开销
  - 后台 writer 开销

### 16.2 当前最主要的日志相关队列

当前维护上最需要知道的队列包括：

#### usage detail 队列

主要去向：

- `auth.db.api_usage_logs`

主要作用：

- 保留单次 usage 事件
- 为 summary 聚合与排行榜提供基础明细

#### summary 队列

主要去向：

- `auth.db.api_usage_summary`

主要作用：

- 保留聚合 usage 数据

#### statistics 队列

主要去向：

- `logs.db` 的 hourly/daily 路径统计

主要作用：

- 维护 API 路径访问统计

#### html visit 队列

主要去向：

- `logs.db.api_visit_log`

主要作用：

- 维护 HTML 页面访问统计

#### diagnostic 队列

主要去向：

- `logs.db.api_diagnostic_events`

主要作用：

- 维护错误与慢请求诊断事件

#### keyword 队列

主要去向：

- `logs.db.api_keyword_log`

当前维护口径：

- 默认关闭实时采集
- 因此默认也不再启动对应 writer

### 16.3 当前最敏感的请求期开销点

当前如果只看请求线程本身，最敏感的开销点依次通常是：

1. 读取并解析 request body
2. 大响应体的生成与传输
3. `search_chars` 这类可能产生大量结果的查询
4. 诊断模式下对 query/body/headers 的序列化
5. 老的 keyword logging 参数采集链路

这也是为什么当前默认要把 keyword logging 关掉。

### 16.4 当前队列满了时应该怎么理解

如果某个队列满了，通常说明的是：

- 写入速度跟不上
- 事件量突然增多
- 或本地处于特殊调试模式，比如 `MINE + all`

不要第一时间认为：

- 业务逻辑一定坏了
- 数据库一定损坏了

而应该先确认：

1. 当前是不是在全量诊断模式
2. 当前是不是短时间错误风暴
3. 当前日志 writer 是否正常启动
4. 当前数据库文件是否可写

### 16.5 当前全量诊断模式为什么只建议在 `MINE`

全量诊断模式的定位不是线上默认监控，而是：

- 本地调试
- 行为排查
- 开发期间观察各 API 真实路径、耗时和状态

之所以只建议在 `MINE` 使用，是因为：

- 写入量明显上升
- 队列压力明显增大
- `logs.db` 体积增长更快
- 会记录大量正常请求

因此当前的设计是：

- 默认：`issues_only`
- 仅 `MINE + 显式开关`：`all`

### 16.6 当前慢请求阈值为什么设为 10 秒

这个值当前不是路由级自适应阈值，而是固定阈值：

- `10_000 ms`

这样做的原因是：

- 简单
- 可预测
- 先把极端慢请求抓出来
- 不引入每个 API 独立阈值配置复杂度

当前如果未来确实需要，可以再做：

- 按路由阈值
- 按模块阈值
- 或按模式阈值

但当前版本先不做。

### 16.7 当前为什么不自动推断“慢的原因”

这是当前诊断系统一个很重要的维护原则：

- 记录证据
- 不轻易记录推测结论

也就是说：

- 会记录 duration
- 会记录 query/body
- 会记录 response size
- 会记录是否已开始响应
- 会记录异常与 stack trace

但不会直接写：

- “因为数据库慢”
- “因为网络慢”
- “因为 Redis 慢”

因为这些结论如果自动猜错，反而会误导维护者。

### 16.8 当前如果要优化日志性能，应优先看哪里

当前如果单看收益，建议的优化优先级是：

1. `api_keyword_log` 相关采集链路
2. 全量诊断模式下的事件量
3. `search_chars` 这类高返回体接口
4. 某些页面访问统计的写法
5. 最后才是 hourly/daily usage 统计

也就是说，不应该优先怀疑 `update_count(path)`，因为这条链路当前已经很轻。

### 16.9 当前如果只想观察 API 行为，应该开哪套日志

如果目标是：

- 看 API 是否报错
- 看 API 是否慢
- 看请求带了什么关键参数
- 看某个请求是否能复现

更应该用的是：

- `api_diagnostic_events`

而不是：

- `api_usage_logs`
- `api_keyword_log`

因为前两者不是为这个目的设计的。

---

## 17. 当前新增或修改接口时的维护清单

### 17.1 如果你新增了一个普通业务接口

建议至少检查下面几件事：

1. 路由是否挂在正确模块下
2. OpenAPI 是否正常暴露
3. 是否需要进入 `auth.db` usage
4. 是否需要进入排行榜分类
5. 是否需要路径规范化
6. 是否需要前端联调文档
7. 是否需要补到 README 或 `docs/README.md`

### 17.2 如果你新增的是动态 path 接口

除了常规事项外，还要额外判断：

1. 这个 path 是否应该进入 `auth.db` usage
2. 如果要进，是否需要模板化
3. 如果要进排行榜，模板路径应该是什么
4. 管理后台展示时，是看原始 path 还是模板 path
5. 诊断日志是否需要 route template

### 17.3 如果你新增的是 SQL 家族辅助接口

当前建议先问自己：

1. 它代表的是业务行为，还是元数据探测
2. 它应不应该进入 `auth.db` usage
3. 它会不会误导排行榜
4. 它会不会被前端误当成真实业务接口

因为目前已经有明确口径：

- 并不是所有 `/sql/*` 都值得进 usage

### 17.4 如果你新增的是前端替代型业务接口

例如当前的：

- `/api/locations/detail`
- `/api/locations/partitions`

这种接口的维护原则是：

1. 先收掉前端对通用 SQL 的直接依赖
2. 第一阶段不强推全新语义结构
3. 尽量沿用前端现有字段处理逻辑
4. 先保证联调成本低
5. 第二阶段再考虑进一步语义化

### 17.5 如果你新增的是需要进排行榜的接口

维护顺序建议是：

1. 先确定是否进入 `auth.db` usage
2. 再确定路径匹配规则
3. 再确定是否需要模板化
4. 再看是否需要加到 leaderboard 分类或 endpoint 规则

不要反过来先改 leaderboard_service，再回头想 usage 有没有记录。

### 17.6 如果你新增的是调试型或内部接口

建议先判断：

- 它是否真的应该进入 usage
- 它是否只应该留在 logs diagnostics
- 它是否只适合本地调试，不适合线上口径

当前最重要的原则是：

- usage 统计要收口
- 诊断日志可以更宽
- 二者不要混

### 17.7 如果你修改了登录相关逻辑

当前必须注意：

- `/auth/login` 已经去掉了旧的 `duration=0` 手工 usage 日志
- 登录限流仍依赖 `ApiUsageLog` 的历史记录
- `Retry-After` 计算同时兼容旧 `/login` 和当前 `/auth/login`

所以如果你再动登录逻辑，应该优先核对：

1. 登录成功是否仍有真实 detail log
2. 登录失败是否仍有真实 detail log
3. 登录 usage 是否不会污染 summary
4. 登录限流查询口径是否仍正确

### 17.8 如果你修改了诊断日志逻辑

当前必须优先核对：

1. 是否误复用了 `API_WHITELIST`
2. 是否误复用了 `RECORD_API / IGNORE_API`
3. 默认模式是否仍是 `issues_only`
4. `MINE + 显式开关` 之外是否不会全量记录
5. `logs.db` 表结构迁移是否仍能自动建表
6. 队列是否仍独立

### 17.9 如果你修改了 keyword logging

当前必须牢记：

- 这套逻辑默认已经关闭
- 不是删掉
- 也不是彻底移除表结构
- 只是默认不再让请求线程付出采集成本

因此如果你未来要恢复它：

1. 必须有明确消费场景
2. 必须先评估请求期开销
3. 最好不要再回到“全量 body 解析”旧逻辑

### 17.10 如果你修改了 README 或 docs

当前建议遵守：

1. 根目录 `README.md` 继续做总入口和长期补充附录
2. `docs/README.md` 只做现行文档索引
3. `docs/archive/` 放过程性资料
4. 不要随意删旧内容，优先增补和归档
5. 任何会影响接手者理解的结构变动，都应该在 README 里补一句

---

## 18. 当前维护边界、已知限制与后续补充方向

### 18.1 当前 README 补充的边界

这份附录当前已经尽量把最近一轮关键变化写清楚，但它不是：

- 全部代码的逐文件说明
- 全部数据库表的完整数据字典
- 全部 API 的逐一联调脚本
- 全部前端改造说明的全集

它现在的定位仍然是：

- 帮维护者快速建立当前口径
- 帮接手者避免走老坑
- 帮排障者快速找到入口

### 18.2 当前最容易失真的信息

README 里最容易随着时间失真的内容包括：

- API 数量统计
- 文件数量统计
- 数据量规模描述
- 最近更新时间
- 某些“推荐流程”的默认值

因此维护时建议：

- 原理和边界写在 README
- 高频变化的枚举值尽量少写死

### 18.3 当前最适合继续补充的方向

后续如果继续增强 README，最值得继续补的是：

1. admin analytics / leaderboard 的维护视角
2. VillagesML 模块的运行依赖说明
3. 数据库之间的数据流和读写边界
4. 常见线上问题与对应排查路径
5. 开发者日常 runbook

### 18.4 当前不建议继续堆进 README 的内容

不建议再把下面这些直接堆进主 README 正文：

- 一次性测试报告
- 阶段性 CR 文档
- 快速开始检查清单
- 临时 bugfix 报告
- 一次性迁移过程记录

这些更适合：

- `docs/`
- 或 `docs/archive/`

### 18.5 当前维护时应优先保留的历史信息

虽然不建议让旧过程文档继续占据 `docs/` 主位置，但下面这些历史信息仍然有价值：

- 迁移为什么发生
- 某次大收口的原因是什么
- 为什么 auth usage 与 logs diagnostics 要彻底分开
- 为什么 `search_chars` 引入 compact
- 为什么 `locations` 第一阶段先不语义化

所以当前的处理原则应是：

- 不删历史
- 但把历史放到正确层级

### 18.6 当前文档整理的推荐长期原则

建议长期维持：

#### 根目录 `README.md`

负责：

- 总入口
- 当前维护口径
- 当前运行和排障说明
- 新接手者必读内容

#### `docs/README.md`

负责：

- 活跃文档索引
- 按主题导航到现行说明

#### `docs/archive/`

负责：

- 历史过程资料
- 阶段性报告
- review、summary、quickstart、checklist 等

#### `HowToBuild.txt`

负责：

- 保留现有构建/部署操作文档
- 不强行并入 `docs/`

### 18.7 当前如果只想快速接手项目，最短阅读路径建议

建议阅读顺序：

1. 根目录 `README.md`
2. `docs/README.md`
3. `app/main.py`
4. `app/routes/__init__.py`
5. `app/common/api_config.py`
6. `app/service/logging/middleware/traffic_logging.py`
7. `app/service/logging/config/diagnostics.py`
8. `app/service/geo/locations.py`
9. `app/service/core/search_chars.py`

这条路径能够先把：

- 应用入口
- 路由入口
- usage 规则
- 诊断规则
- 最近新增业务接口
- 核心查询热点

都建立起来。

### 18.8 当前如果只想排查排行榜问题，最短阅读路径建议

建议阅读顺序：

1. `app/routes/auth.py`
2. `app/service/user/leaderboard_service.py`
3. `app/common/api_config.py`
4. `app/service/logging/utils/usage_paths.py`
5. `auth.db` 中的 `api_usage_logs`
6. `auth.db` 中的 `api_usage_summary`

### 18.9 当前如果只想排查报错与慢请求问题，最短阅读路径建议

建议阅读顺序：

1. `app/service/logging/config/diagnostics.py`
2. `app/service/logging/middleware/traffic_logging.py`
3. `logs.db.api_diagnostic_events`
4. 对应业务路由文件
5. 对应 service 文件

### 18.10 当前如果只想排查 SQL 家族接口问题，最短阅读路径建议

建议阅读顺序：

1. `app/sql/sql_routes.py`
2. `app/sql/sql_schemas.py`
3. `app/common/api_config.py`
4. 前端是否仍在误用 `/sql/query/columns` 或 `/sql/distinct/*`

### 18.11 当前如果只想排查 docs 结构问题，最短阅读路径建议

建议阅读顺序：

1. `docs/README.md`
2. `docs/`
3. `docs/archive/`
4. 根目录 `README.md` 中本附录的文档分层说明

### 18.12 当前 README 继续补充时的写法建议

建议继续遵守：

- 不轻易删旧内容
- 优先增加“当前维护补充附录”
- 新增说明尽量围绕“当前口径”而不是复制代码
- 先写边界和职责，再写细节
- 先讲为什么，再讲怎么做

### 18.13 当前 README 到这里为止的补充目标

当前这份附录的目标，不是把 README 变成 API 参考手册，而是：

- 在旧主体仍然保留的情况下
- 明确补上 2026-03 当前真实维护状态
- 帮你和后续维护者快速区分：
  - 哪些是旧设计
  - 哪些是当前口径
  - 哪些是已经收紧的边界
  - 哪些是新增但默认关闭或默认保守的能力

### 18.14 当前这份附录最重要的四个维护结论

如果只记四句话，当前最重要的是：

1. `auth.db` 和 `logs.db` 是两套不同职责，不能混着理解
2. SQL 家族接口已经收口，不应再拿辅助接口代表真实业务使用
3. 诊断日志默认只记错误与慢请求，只有 `MINE` 才允许全量
4. keyword logging 默认关闭，是一次明确的性能优化取舍

### 18.15 后续补充建议

如果后面你还希望 README 继续长到更完整的“项目维护手册”，建议下一轮继续补：

- admin analytics 全量说明
- leaderboard 的指标口径矩阵
- 各数据库表之间的关系图
- VillagesML 的模块、接口、表之间对应关系
- 典型线上问题排查清单
- 本地调试脚本、命令和观察点

---





