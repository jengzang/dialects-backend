# VillagesML Frontend Development Guide
# 广东省自然村分析系统前端开发指南

**Last Updated:** 2026-02-23
**API Version:** 1.0.0 (Integrated)
**Base URL:** `http://localhost:5000/api/villages`

---

## 📋 目录 Table of Contents

1. [系统概述 System Overview](#系统概述-system-overview)
2. [推荐页面结构 Recommended Page Structure](#推荐页面结构-recommended-page-structure)
3. [API 端点分类 API Endpoint Categories](#api-端点分类-api-endpoint-categories)
4. [数据返回格式 Data Response Formats](#数据返回格式-data-response-formats)
5. [认证要求 Authentication Requirements](#认证要求-authentication-requirements)
6. [前端技术栈建议 Frontend Tech Stack Recommendations](#前端技术栈建议-frontend-tech-stack-recommendations)
7. [参考文档 Reference Documents](#参考文档-reference-documents)

---

## 系统概述 System Overview

VillagesML 是一个基于机器学习的广东省自然村名称分析系统，提供以下核心功能：

### 核心功能 Core Features

1. **字符分析 Character Analysis**
   - 字符频率统计（全局/区域）
   - 字符倾向性分析（Z-score）
   - 字符显著性分析（卡方检验）
   - Word2Vec 字符嵌入向量

2. **语义分析 Semantic Analysis**
   - 9 大语义类别（山、水、聚落、方位、宗族、象征、农业、植被、基建）
   - 语义组合模式（bigrams, trigrams）
   - PMI（点互信息）分析
   - 语义强度指数

3. **空间分析 Spatial Analysis**
   - KDE 密度热点分析
   - DBSCAN 空间聚类
   - 空间-倾向性整合分析

4. **N-gram 分析 N-gram Analysis**
   - Bigram/Trigram 频率统计
   - N-gram 倾向性与显著性
   - 结构模式识别

5. **聚类分析 Clustering Analysis**
   - 预计算聚类结果查询
   - 实时聚类计算（KMeans, DBSCAN, GMM）
   - 聚类画像与特征分析

6. **村庄搜索 Village Search**
   - 关键词搜索（支持模糊匹配）
   - 区域筛选（市/县/镇）
   - 村庄详情查询

### 数据规模 Data Scale

- **村庄数量**: 285,860+ 个自然村
- **覆盖范围**: 广东省全省
- **数据库大小**: 124MB (45 张表)
- **分析维度**: 字符、语义、空间、N-gram、聚类

---

## 推荐页面结构 Recommended Page Structure

### 1. 首页 / 概览页 Home / Overview Page

**功能 Features:**
- 系统介绍与数据概览
- 快速搜索入口
- 数据统计可视化（村庄总数、覆盖区域、分析维度）

**推荐 API:**
```
GET /api/villages/metadata/stats/overview
```

**返回数据 Response:**
```json
{
  "total_villages": 285860,
  "total_cities": 21,
  "total_counties": 122,
  "total_characters": 3500,
  "analysis_runs": 15
}
```

**UI 建议:**
- 大数字展示（村庄总数、覆盖区域）
- 地图可视化（广东省行政区划）
- 快速搜索框（跳转到搜索页）

---

### 2. 村庄搜索页 Village Search Page

**功能 Features:**
- 关键词搜索村名
- 区域筛选（市/县/镇）
- 分页展示结果
- 点击查看村庄详情

**推荐 API:**
```
GET /api/villages/village/search?query={keyword}&city={city}&county={county}&limit=20&offset=0
```

**返回数据 Response:**
```json
[
  {
    "village_name": "水口村",
    "city": "广州市",
    "county": "番禺区",
    "town": "石楼镇",
    "longitude": 113.456,
    "latitude": 23.123
  }
]
```

**UI 建议:**
- 搜索框 + 筛选器（市/县下拉菜单）
- 结果列表（卡片式布局）
- 分页控件（上一页/下一页）
- 防抖搜索（300ms）

**交互流程:**
1. 用户输入关键词 → 自动搜索（防抖）
2. 选择筛选条件 → 重新搜索
3. 点击村庄 → 跳转到详情页

---

### 3. 村庄详情页 Village Detail Page

**功能 Features:**
- 显示村庄基本信息（名称、位置、坐标）
- 显示村名字符分析
- 显示语义标签
- 显示所属聚类

**推荐 API:**
```
GET /api/villages/village/search/detail?village_name={name}&city={city}&county={county}
GET /api/villages/semantic/labels/by-character?character={char}
GET /api/villages/clustering/assignments?village_name={name}
```

**返回数据 Response:**
```json
{
  "village_name": "水口村",
  "city": "广州市",
  "county": "番禺区",
  "town": "石楼镇",
  "longitude": 113.456,
  "latitude": 23.123,
  "characters": ["水", "口", "村"],
  "semantic_labels": {
    "水": "水系",
    "口": "地形",
    "村": "聚落"
  },
  "cluster_id": 3
}
```

**UI 建议:**
- 村庄名称（大标题）
- 位置信息（市/县/镇）
- 地图标注（经纬度）
- 字符分析表格（字符、语义类别、频率）
- 相似村庄推荐

---

### 4. 字符分析页 Character Analysis Page

**功能 Features:**
- 全局字符频率排行榜（Top 50）
- 区域字符频率对比
- 字符倾向性热力图
- 字符相似度查询（Word2Vec）

**推荐 API:**
```
GET /api/villages/character/frequency/global?top_n=50
GET /api/villages/character/frequency/regional?region_level=city&region_name={city}&top_n=50
GET /api/villages/character/tendency/by-char?character={char}&region_level=city
GET /api/villages/character/embeddings/similarities?character={char}&top_n=10
```

**返回数据 Response:**
```json
// Global frequency
[
  {"character": "村", "frequency": 285860, "percentage": 100.0},
  {"character": "新", "frequency": 12345, "percentage": 4.32}
]

// Tendency by character
[
  {"region_name": "广州市", "z_score": 2.5, "frequency": 1234},
  {"region_name": "深圳市", "z_score": -1.2, "frequency": 567}
]

// Similar characters
[
  {"character": "河", "similarity": 0.85},
  {"character": "江", "similarity": 0.78}
]
```

**UI 建议:**
- **Tab 1: 频率排行**
  - 柱状图（Top 50 字符）
  - 区域选择器（全局/市/县）

- **Tab 2: 倾向性分析**
  - 字符输入框
  - 热力地图（各区域 Z-score）
  - 颜色编码：红色（高倾向）→ 黄色（中等）→ 绿色（低倾向）

- **Tab 3: 字符相似度**
  - 字符输入框
  - 相似字符列表（相似度分数）
  - 点击跳转到该字符分析

---

### 5. 语义分析页 Semantic Analysis Page

**功能 Features:**
- 语义类别分布（9 大类别）
- 语义组合模式（bigrams, trigrams）
- PMI 分析（字符共现强度）
- 语义强度指数

**推荐 API:**
```
GET /api/villages/semantic/category/vtf/global
GET /api/villages/semantic/composition/bigrams?top_n=50
GET /api/villages/semantic/composition/pmi?char1={char1}&char2={char2}
GET /api/villages/semantic/indices?region_level=city&region_name={city}
```

**返回数据 Response:**
```json
// Category VTF
[
  {"category": "水系", "vtf": 0.35, "village_count": 98765},
  {"category": "山地", "vtf": 0.28, "village_count": 78901}
]

// Bigrams
[
  {"bigram": "水-口", "frequency": 5678, "pmi_score": 3.45},
  {"bigram": "新-村", "frequency": 4321, "pmi_score": 2.10}
]

// PMI
{
  "char1": "水",
  "char2": "口",
  "pmi_score": 3.45,
  "co_occurrence": 5678,
  "interpretation": "strong_association"
}
```

**UI 建议:**
- **Tab 1: 类别分布**
  - 饼图（9 大语义类别占比）
  - 区域选择器（全局/市/县）

- **Tab 2: 组合模式**
  - Bigram/Trigram 排行榜
  - PMI 分数可视化
  - 点击查看详细共现信息

- **Tab 3: 语义强度**
  - 区域选择器
  - 雷达图（9 个维度的语义强度）

---

### 6. 空间分析页 Spatial Analysis Page

**功能 Features:**
- KDE 密度热点地图
- DBSCAN 聚类地图
- 空间-倾向性整合分析

**推荐 API:**
```
GET /api/villages/spatial/hotspots?character={char}&bandwidth=0.1
GET /api/villages/spatial/clusters?character={char}&eps=0.05&min_samples=5
GET /api/villages/spatial/integration?character={char}
```

**返回数据 Response:**
```json
// Hotspots
[
  {
    "hotspot_id": 1,
    "character": "水",
    "center_lon": 113.456,
    "center_lat": 23.123,
    "density": 0.85,
    "village_count": 234
  }
]

// Clusters
[
  {
    "cluster_id": 0,
    "character": "水",
    "village_count": 156,
    "center_lon": 113.456,
    "center_lat": 23.123,
    "villages": ["水口村", "水头村", ...]
  }
]
```

**UI 建议:**
- 地图组件（推荐 Leaflet 或 Mapbox）
- 字符选择器
- 图层切换（热点/聚类）
- 点击热点/聚类 → 显示详情弹窗

---

### 7. 聚类分析页 Clustering Analysis Page

**功能 Features:**
- 查看预计算聚类结果
- 实时聚类计算（高级功能，需登录）
- 聚类画像与特征对比

**推荐 API:**
```
GET /api/villages/clustering/assignments?region_level=county&run_id={run_id}
POST /api/villages/compute/clustering/run (需登录)
GET /api/villages/regional/aggregates/realtime?region_level=county&region_name={region}
```

**返回数据 Response:**
```json
// Clustering assignments
[
  {
    "region_name": "番禺区",
    "cluster_id": 2,
    "village_count": 1234
  }
]

// Clustering result (compute)
{
  "run_id": "kmeans_k4_20260223",
  "algorithm": "kmeans",
  "k": 4,
  "execution_time_ms": 2345,
  "metrics": {
    "silhouette_score": 0.65,
    "davies_bouldin_score": 0.85
  },
  "cluster_profiles": [
    {
      "cluster_id": 0,
      "region_count": 30,
      "regions": ["番禺区", "南沙区", ...],
      "top_features": {
        "semantic_water": 0.45,
        "semantic_mountain": 0.12
      }
    }
  ]
}
```

**UI 建议:**
- **Tab 1: 预计算结果**
  - Run ID 选择器
  - 聚类分布地图（各区域着色）
  - 聚类画像表格

- **Tab 2: 实时计算**（需登录）
  - 参数配置面板（算法、K 值、特征选择）
  - 运行按钮 + 进度条
  - 结果可视化（聚类地图 + 评估指标）

---

### 8. N-gram 分析页 N-gram Analysis Page

**功能 Features:**
- Bigram/Trigram 频率排行
- N-gram 倾向性分析
- 结构模式识别

**推荐 API:**
```
GET /api/villages/ngrams/frequency?n=2&top_n=50
GET /api/villages/ngrams/tendency?ngram={ngram}&region_level=city
GET /api/villages/patterns?pattern_type=prefix&top_n=30
```

**返回数据 Response:**
```json
// N-gram frequency
[
  {"ngram": "新村", "frequency": 12345, "percentage": 4.32},
  {"ngram": "水口", "frequency": 5678, "percentage": 1.99}
]

// N-gram tendency
[
  {"region_name": "广州市", "z_score": 2.1, "frequency": 234},
  {"region_name": "深圳市", "z_score": -0.8, "frequency": 89}
]

// Patterns
[
  {
    "pattern": "新*",
    "pattern_type": "prefix",
    "frequency": 12345,
    "examples": ["新村", "新屋", "新围"]
  }
]
```

**UI 建议:**
- **Tab 1: 频率排行**
  - N 值选择器（2/3）
  - 柱状图（Top 50）

- **Tab 2: 倾向性分析**
  - N-gram 输入框
  - 热力地图（各区域 Z-score）

- **Tab 3: 结构模式**
  - 模式类型选择器（前缀/后缀/中缀）
  - 模式列表 + 示例

---

## API 端点分类 API Endpoint Categories

### 公开端点 Public Endpoints (无需登录)

**查询类 Query APIs (快速, <100ms):**
- 字符频率: `/api/villages/character/frequency/*`
- 字符倾向性: `/api/villages/character/tendency/*`
- 字符嵌入: `/api/villages/character/embeddings/*`
- 村庄搜索: `/api/villages/village/search`
- 语义分析: `/api/villages/semantic/*`
- 空间分析: `/api/villages/spatial/*`
- N-gram 分析: `/api/villages/ngrams/*`
- 聚类结果: `/api/villages/clustering/assignments`
- 元数据: `/api/villages/metadata/*`

### 需登录端点 Authenticated Endpoints

**计算类 Compute APIs (慢速, 1-30s):**
- 实时聚类: `POST /api/villages/compute/clustering/run`
- 聚类扫描: `POST /api/villages/compute/clustering/scan`
- 语义网络: `POST /api/villages/compute/semantic/network`
- 特征提取: `POST /api/villages/compute/features/extract`

**管理类 Admin APIs:**
- Run ID 管理: `/api/villages/admin/run-ids/*`

---

## 数据返回格式 Data Response Formats

### 成功响应 Success Response

**状态码:** 200 OK

**格式:** JSON 数组或对象

```json
// 数组格式（列表查询）
[
  {"field1": "value1", "field2": "value2"},
  {"field1": "value3", "field2": "value4"}
]

// 对象格式（单条查询）
{
  "field1": "value1",
  "field2": "value2",
  "nested": {
    "field3": "value3"
  }
}
```

### 错误响应 Error Response

**状态码:** 400/404/422/500

**格式:**
```json
{
  "detail": "错误描述信息"
}
```

**常见错误:**
- `400 Bad Request`: 参数错误
- `404 Not Found`: 资源不存在
- `422 Unprocessable Entity`: 参数验证失败
- `500 Internal Server Error`: 服务器错误
- `408 Request Timeout`: 计算超时（compute 端点）

### 分页响应 Pagination

**参数:**
- `limit`: 每页数量（默认 20，最大 1000）
- `offset`: 偏移量（默认 0）

**示例:**
```
GET /api/villages/village/search?query=水&limit=20&offset=40
```

**返回:** 数组（不包含总数，需前端判断是否还有下一页）

---

## 认证要求 Authentication Requirements

### 公开端点 Public Endpoints

**无需认证，直接访问:**
- 所有查询类 API（字符、语义、空间、N-gram、村庄搜索）
- 元数据 API
- 预计算聚类结果

### 需登录端点 Authenticated Endpoints

**需要 JWT Token:**
- 所有 `/api/villages/compute/*` 端点
- 所有 `/api/villages/admin/*` 端点

**认证方式:**
```javascript
// 登录获取 token
POST /api/auth/login
Body: {"username": "user", "password": "pass"}
Response: {"access_token": "eyJ...", "token_type": "bearer"}

// 使用 token 调用 API
fetch('/api/villages/compute/clustering/run', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer eyJ...',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({...})
})
```

### 速率限制 Rate Limiting

- **已登录用户**: 2000 请求/小时
- **未登录用户**: 300 请求/小时
- **超限响应**: 429 Too Many Requests

---

## 前端技术栈建议 Frontend Tech Stack Recommendations

### 核心框架 Core Framework

**推荐: Vue 3 + Vite**
```bash
npm create vite@latest villagesml-frontend -- --template vue
cd villagesml-frontend
npm install
```

### UI 组件库 UI Component Library

**推荐: Element Plus**
```bash
npm install element-plus
```

**功能:**
- 表格、分页、筛选器
- 表单、输入框、选择器
- 加载动画、消息提示

### 图表库 Chart Library

**推荐: ECharts**
```bash
npm install echarts vue-echarts
```

**用途:**
- 柱状图（字符频率）
- 饼图（语义类别分布）
- 热力图（倾向性分析）
- 雷达图（语义强度）

### 地图库 Map Library

**推荐: Leaflet**
```bash
npm install leaflet vue-leaflet
```

**用途:**
- 村庄位置标注
- KDE 热点可视化
- DBSCAN 聚类地图
- 区域着色（聚类结果）

### HTTP 客户端 HTTP Client

**推荐: Axios**
```bash
npm install axios
```

**配置:**
```javascript
// src/api/client.js
import axios from 'axios';

const client = axios.create({
  baseURL: 'http://localhost:5000/api/villages',
  timeout: 30000, // 30s for compute endpoints
});

// Add auth token
client.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default client;
```

### 状态管理 State Management

**推荐: Pinia**
```bash
npm install pinia
```

**用途:**
- 用户认证状态
- 搜索结果缓存
- 全局配置（区域选择、参数设置）

### 工具库 Utility Libraries

```bash
npm install lodash-es  # 防抖、节流
npm install dayjs      # 日期格式化
```

---

## 参考文档 Reference Documents

### 必读文档 Must-Read Documents

**给前端开发者的文档:**

1. **FRONTEND_INTEGRATION_GUIDE.md** ⭐⭐⭐⭐⭐
   - 路径: `app/tools/VillagesML/docs/FRONTEND_INTEGRATION_GUIDE.md`
   - 内容: Vue 3 集成示例、API 客户端设置、常见用例、错误处理
   - 适合: 前端开发者快速上手

2. **API_COMPLETE_REFERENCE.md** ⭐⭐⭐⭐⭐
   - 路径: `app/tools/VillagesML/docs/API_COMPLETE_REFERENCE.md`
   - 内容: 完整的 API 端点列表（50+ 端点）、参数说明、返回格式
   - 适合: 查阅具体 API 用法

3. **API_QUICK_REFERENCE.md** ⭐⭐⭐⭐
   - 路径: `app/tools/VillagesML/docs/API_QUICK_REFERENCE.md`
   - 内容: 常用 API 速查表、curl 示例
   - 适合: 快速查找 API

4. **本文档 (VILLAGESML_FRONTEND_GUIDE.md)** ⭐⭐⭐⭐⭐
   - 路径: `docs/VILLAGESML_FRONTEND_GUIDE.md`
   - 内容: 页面结构建议、UI 设计指南、技术栈推荐
   - 适合: 前端架构设计

### 可选文档 Optional Documents

5. **API_DEPLOYMENT_GUIDE.md**
   - 路径: `app/tools/VillagesML/docs/API_DEPLOYMENT_GUIDE.md`
   - 内容: API 部署指南（Docker、生产环境配置）
   - 适合: 运维人员

6. **API_STATUS_REPORT.md**
   - 路径: `app/tools/VillagesML/docs/API_STATUS_REPORT.md`
   - 内容: API 开发状态、已知问题
   - 适合: 了解系统现状

### 在线文档 Online Documentation

**Swagger UI (推荐):**
```
http://localhost:5000/docs
```

**功能:**
- 交互式 API 测试
- 自动生成的参数说明
- 实时测试请求/响应

---

## 重要提示 Important Notes

### URL 变更 URL Changes

**⚠️ 注意:** 集成后的 API 前缀已从 `/api` 变更为 `/api/villages`

**旧版 URL (standalone):**
```
http://localhost:8000/api/character/frequency/global
```

**新版 URL (integrated):**
```
http://localhost:5000/api/villages/character/frequency/global
```

**文档中的示例需要更新 URL 前缀！**

### 性能建议 Performance Tips

1. **防抖搜索**: 搜索框输入使用 300ms 防抖
2. **缓存结果**: 相同查询缓存 5 分钟
3. **分页加载**: 避免一次加载所有数据
4. **懒加载**: 图表和地图组件按需加载
5. **进度提示**: Compute 端点显示加载动画

### 错误处理 Error Handling

1. **网络错误**: 显示"网络连接失败"
2. **超时错误**: 显示"请求超时，请稍后重试"
3. **404 错误**: 显示"未找到相关数据"
4. **429 错误**: 显示"请求过于频繁，请稍后再试"
5. **500 错误**: 显示"服务器错误，请联系管理员"

### 开发流程 Development Workflow

1. **启动后端 API**:
   ```bash
   cd C:\Users\joengzaang\myfiles\server\fastapi
   uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
   ```

2. **访问 Swagger UI**:
   ```
   http://localhost:5000/docs
   ```

3. **测试 API**:
   ```bash
   curl http://localhost:5000/api/villages/metadata/stats/overview
   ```

4. **开发前端**:
   ```bash
   npm run dev
   ```

---

## 联系方式 Contact

如有问题，请查阅:
- Swagger UI: http://localhost:5000/docs
- 项目文档: `docs/` 目录
- API 文档: `app/tools/VillagesML/docs/` 目录

---

**祝开发顺利！Good luck with development!** 🚀
