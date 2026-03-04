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

**接口路径**：`POST /api/ZhongGu`

**权限要求**：公开接口

**功能描述**：根据中古音韵条件筛选汉字，并查询其在各方言点的读音。

**请求体**：

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

**请求参数说明**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| characters | string | 否 | 汉字（留空表示根据中古条件筛选） |
| locations | array | 是 | 方言点列表 |
| zhonggu_filters | object | 是 | 中古音韵条件（声母、韵部、声调、等呼） |
| need_features | boolean | 否 | 是否返回音韵特征 |
| limit | integer | 否 | 返回结果数量限制 |

**响应体**：

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
        "features": {
          "声母": "d",
          "韵母": "ung",
          "声调": "1"
        }
      },
      "北京": {
        "pronunciation": "dong1",
        "ipa": "tʊŋ˥",
        "features": {
          "声母": "d",
          "韵母": "ong",
          "声调": "1"
        }
      }
    }
  ],
  "total": 4
}
```

---

### 2. 查音位（YinWei）

**接口路径**：`POST /api/YinWei`

**权限要求**：公开接口

**功能描述**：根据现代方言音位条件反查中古来源。

**请求体**：

```json
{
  "locations": ["广州"],
  "phonology_filters": {
    "声母": ["d", "t"],
    "韵母": ["ung", "ing"],
    "声调": ["1", "2"]
  },
  "limit": 50
}
```

**响应体**：

```json
{
  "results": [
    {
      "char": "東",
      "广州": {
        "pronunciation": "dung1",
        "ipa": "tʊŋ˥"
      },
      "中古来源": {
        "声母": "端",
        "韵部": "东",
        "声调": "平声",
        "等呼": "一等"
      }
    }
  ],
  "total": 15
}
```

---

### 3. 查字

**接口路径**：`GET /api/search_chars/`

**权限要求**：公开接口

**功能描述**：根据汉字查询各方言点读音。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| char | string | 是 | 要查询的汉字 |
| locations | string | 否 | 方言点列表（逗号分隔） |
| need_features | boolean | 否 | 是否返回音韵特征 |

**请求示例**：

```
GET /api/search_chars/?char=東&locations=广州,北京&need_features=true
```

**响应体**：

```json
{
  "char": "東",
  "pronunciations": {
    "广州": {
      "pronunciation": "dung1",
      "ipa": "tʊŋ˥",
      "features": {
        "声母": "d",
        "韵母": "ung",
        "声调": "1"
      }
    },
    "北京": {
      "pronunciation": "dong1",
      "ipa": "tʊŋ˥",
      "features": {
        "声母": "d",
        "韵母": "ong",
        "声调": "1"
      }
    }
  }
}
```

---

### 4. 查调

**接口路径**：`GET /api/search_tones/`

**权限要求**：公开接口

**功能描述**：根据声调查询汉字。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| tone | string | 是 | 声调（如 "1", "2", "3", "4"） |
| locations | string | 是 | 方言点列表（逗号分隔） |
| category | string | 否 | 声调类别（平、上、去、入） |
| limit | integer | 否 | 返回数量限制 |

**请求示例**：

```
GET /api/search_tones/?tone=1&locations=广州&category=平&limit=20
```

**响应体**：

```json
{
  "tone": "1",
  "location": "广州",
  "category": "平",
  "characters": [
    {
      "char": "東",
      "pronunciation": "dung1",
      "ipa": "tʊŋ˥"
    },
    {
      "char": "公",
      "pronunciation": "gung1",
      "ipa": "kʊŋ˥"
    }
  ],
  "total": 2
}
```

---

### 5. 音韵矩阵

**接口路径**：`POST /api/phonology_matrix`

**权限要求**：公开接口

**功能描述**：生成声母-韵母-汉字交叉表。

**请求体**：

```json
{
  "location": "广州",
  "tone_filter": ["1", "2"],
  "include_ipa": true
}
```

**响应体**：

```json
{
  "location": "广州",
  "matrix": {
    "d": {
      "ung": [
        {
          "char": "東",
          "pronunciation": "dung1",
          "ipa": "tʊŋ˥"
        }
      ],
      "ing": [
        {
          "char": "丁",
          "pronunciation": "ding1",
          "ipa": "tɪŋ˥"
        }
      ]
    },
    "g": {
      "ung": [
        {
          "char": "公",
          "pronunciation": "gung1",
          "ipa": "kʊŋ˥"
        }
      ]
    }
  },
  "statistics": {
    "total_chars": 150,
    "initials_count": 20,
    "finals_count": 35
  }
}
```

---

### 6. 音素分类矩阵

**接口路径**：`POST /api/phonology_classification_matrix`

**权限要求**：公开接口

**功能描述**：按音韵特征分类生成矩阵。

**请求体**：

```json
{
  "location": "广州",
  "classification": {
    "type": "声母",
    "categories": ["塞音", "擦音", "鼻音"]
  }
}
```

**响应体**：

```json
{
  "location": "广州",
  "classification_type": "声母",
  "matrix": {
    "塞音": {
      "b": ["巴", "爸", "把"],
      "p": ["趴", "怕", "帕"],
      "d": ["打", "大", "搭"],
      "t": ["他", "踏", "塔"]
    },
    "擦音": {
      "f": ["发", "法", "罚"],
      "s": ["沙", "傻", "杀"]
    },
    "鼻音": {
      "m": ["妈", "马", "骂"],
      "n": ["那", "拿", "哪"]
    }
  },
  "statistics": {
    "total_categories": 3,
    "total_initials": 8,
    "total_chars": 24
  }
}
```

---

## 地理信息接口

### 1. 获取地点列表

**接口路径**：`GET /api/get_locs/`

**权限要求**：公开接口

**功能描述**：获取方言点列表，支持按区域过滤和分页。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| region | string | 否 | 区域名称（如"广东"、"福建"） |
| limit | integer | 否 | 每页数量（默认 50） |
| offset | integer | 否 | 偏移量（默认 0） |

**请求示例**：

```
GET /api/get_locs/?region=广东&limit=20&offset=0
```

**响应体**：

```json
{
  "total": 150,
  "limit": 20,
  "offset": 0,
  "locations": [
    {
      "name": "广州",
      "region": "广东",
      "latitude": 23.1291,
      "longitude": 113.2644,
      "dialect_group": "粤语"
    },
    {
      "name": "深圳",
      "region": "广东",
      "latitude": 22.5431,
      "longitude": 114.0579,
      "dialect_group": "粤语"
    }
  ]
}
```

---

### 2. 获取坐标

**接口路径**：`GET /api/get_coordinates`

**权限要求**：公开接口

**功能描述**：获取方言点的地理坐标。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| location | string | 是 | 方言点名称 |
| char | string | 否 | 汉字（用于获取该字在该地点的读音） |

**请求示例**：

```
GET /api/get_coordinates?location=广州&char=東
```

**响应体**：

```json
{
  "location": "广州",
  "latitude": 23.1291,
  "longitude": 113.2644,
  "region": "广东",
  "dialect_group": "粤语",
  "pronunciation": {
    "char": "東",
    "pronunciation": "dung1",
    "ipa": "tʊŋ˥"
  }
}
```

---

### 3. 批量匹配地点

**接口路径**：`POST /api/batch_match`

**权限要求**：公开接口

**功能描述**：批量匹配地点名称，返回标准化的方言点信息。

**请求体**：

```json
{
  "names": ["广州", "广州市", "Canton", "穗", "羊城"]
}
```

**响应体**：

```json
{
  "results": [
    {
      "input": "广州",
      "matched": true,
      "standard_name": "广州",
      "confidence": 1.0
    },
    {
      "input": "广州市",
      "matched": true,
      "standard_name": "广州",
      "confidence": 0.95
    },
    {
      "input": "Canton",
      "matched": true,
      "standard_name": "广州",
      "confidence": 0.9
    },
    {
      "input": "穗",
      "matched": true,
      "standard_name": "广州",
      "confidence": 0.85
    },
    {
      "input": "羊城",
      "matched": true,
      "standard_name": "广州",
      "confidence": 0.85
    }
  ],
  "total": 5,
  "matched_count": 5
}
```

---

## 工具接口

### Check 工具 - 数据校验

#### 1. 上传文件

**接口路径**：`POST /api/tools/check/upload`

**权限要求**：用户接口

**功能描述**：上传待检查的方言数据文件。

**请求体**：`multipart/form-data`

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | file | 是 | Excel 或 CSV 文件 |
| file_type | string | 是 | 文件类型（"excel" 或 "csv"） |

**响应体**：

```json
{
  "task_id": "check_20260304_123456",
  "filename": "dialect_data.xlsx",
  "file_size": 102400,
  "rows_count": 500,
  "columns": ["地点", "汉字", "读音", "IPA", "声调"],
  "status": "uploaded"
}
```

---

#### 2. 执行校验

**接口路径**：`POST /api/tools/check/execute`

**权限要求**：用户接口

**功能描述**：对上传的数据执行校验。

**请求体**：

```json
{
  "task_id": "check_20260304_123456",
  "validation_rules": {
    "check_location": true,
    "check_pronunciation": true,
    "check_ipa": true,
    "check_tone": true,
    "check_duplicates": true
  }
}
```

**响应体**：

```json
{
  "task_id": "check_20260304_123456",
  "status": "completed",
  "validation_results": {
    "total_rows": 500,
    "valid_rows": 485,
    "error_rows": 15,
    "errors": [
      {
        "row": 10,
        "column": "地点",
        "error_type": "invalid_location",
        "message": "地点名称不存在"
      },
      {
        "row": 25,
        "column": "IPA",
        "error_type": "invalid_ipa",
        "message": "IPA 格式错误"
      }
    ],
    "warnings": [
      {
        "row": 50,
        "column": "声调",
        "warning_type": "unusual_tone",
        "message": "声调值不常见"
      }
    ]
  }
}
```

---

### Praat 声学分析工具

#### 1. 上传音频

**接口路径**：`POST /api/tools/praat/uploads`

**权限要求**：用户接口

**功能描述**：上传音频文件进行声学分析。

**请求体**：`multipart/form-data`

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | file | 是 | 音频文件（WAV、MP3 等） |
| normalize | boolean | 否 | 是否标准化音频（默认 true） |

**响应体**：

```json
{
  "task_id": "praat_upload_20260304_123456",
  "filename": "audio.wav",
  "file_size": 2048000,
  "duration": 5.2,
  "sample_rate": 44100,
  "channels": 1,
  "status": "uploaded"
}
```

---

#### 2. 创建分析任务

**接口路径**：`POST /api/tools/praat/jobs`

**权限要求**：用户接口

**功能描述**：创建声学分析任务。

**请求体**：

```json
{
  "task_id": "praat_upload_20260304_123456",
  "mode": "single",
  "modules": ["basic", "pitch", "formant", "intensity"],
  "parameters": {
    "pitch": {
      "min_pitch": 75,
      "max_pitch": 500,
      "time_step": 0.01
    },
    "formant": {
      "max_formant": 5500,
      "num_formants": 5
    }
  }
}
```

**响应体**：

```json
{
  "job_id": "praat_job_20260304_123456",
  "task_id": "praat_upload_20260304_123456",
  "status": "processing",
  "estimated_time": 10,
  "modules": ["basic", "pitch", "formant", "intensity"]
}
```

---

#### 3. 获取分析结果

**接口路径**：`GET /api/tools/praat/jobs/progress/{job_id}/result`

**权限要求**：用户接口

**功能描述**：获取声学分析结果。

**响应体**：

```json
{
  "job_id": "praat_job_20260304_123456",
  "status": "completed",
  "mode": "single",
  "results": {
    "basic": {
      "duration_s": 5.2,
      "energy_mean": -12.5,
      "energy_std": 3.2
    },
    "pitch": {
      "f0_mean": 195.3,
      "f0_std": 25.6,
      "f0_min": 150.2,
      "f0_max": 245.8,
      "five_point_contour": [180, 195, 210, 205, 185]
    },
    "formant": {
      "F1": 750,
      "F2": 1450,
      "F3": 2500,
      "F4": 3500,
      "F5": 4500,
      "F1_bandwidth": 80,
      "F2_bandwidth": 120
    },
    "intensity": {
      "mean": 65.5,
      "max": 75.2,
      "min": 55.8
    }
  }
}
```

---

### Jyut2IPA 工具 - 粤拼转 IPA

#### 1. 处理转换

**接口路径**：`POST /api/tools/jyut2ipa/process`

**权限要求**：用户接口

**功能描述**：将粤拼转换为国际音标（IPA）。

**请求体**：

```json
{
  "input_type": "text",
  "data": [
    {"char": "東", "jyutping": "dung1"},
    {"char": "公", "jyutping": "gung1"},
    {"char": "風", "jyutping": "fung1"}
  ],
  "output_format": "ipa"
}
```

**响应体**：

```json
{
  "task_id": "jyut2ipa_20260304_123456",
  "status": "completed",
  "results": [
    {
      "char": "東",
      "jyutping": "dung1",
      "ipa": "tʊŋ˥",
      "tone": "1",
      "tone_name": "阴平"
    },
    {
      "char": "公",
      "jyutping": "gung1",
      "ipa": "kʊŋ˥",
      "tone": "1",
      "tone_name": "阴平"
    },
    {
      "char": "風",
      "jyutping": "fung1",
      "ipa": "fʊŋ˥",
      "tone": "1",
      "tone_name": "阴平"
    }
  ],
  "total": 3,
  "success_count": 3,
  "error_count": 0
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

#### 2. 字符倾向性分析

**接口路径**：`GET /api/villages/character/tendency/by-char`

**权限要求**：用户接口

**功能描述**：分析特定字符在各地区的使用倾向性。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| char | string | 是 | 要分析的字符 |
| region_level | string | 是 | 区域层级（city/county/township） |

**请求示例**：

```
GET /api/villages/character/tendency/by-char?char=水&region_level=city
```

**响应体**：

```json
{
  "char": "水",
  "region_level": "city",
  "results": [
    {
      "region_name": "广州市",
      "frequency": 850,
      "expected_frequency": 500,
      "z_score": 2.5,
      "lift": 1.7,
      "log_odds": 0.53,
      "is_significant": true
    },
    {
      "region_name": "深圳市",
      "frequency": 320,
      "expected_frequency": 400,
      "z_score": -1.2,
      "lift": 0.8,
      "log_odds": -0.22,
      "is_significant": false
    }
  ],
  "total_regions": 21
}
```

---

#### 3. 字符嵌入相似度

**接口路径**：`GET /api/villages/character/embeddings/similarities`

**权限要求**：用户接口

**功能描述**：查询与指定字符语义最相似的字符。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| char | string | 是 | 查询字符 |
| top_k | integer | 否 | 返回数量（默认 10） |
| min_similarity | float | 否 | 最小相似度阈值（0-1） |

**请求示例**：

```
GET /api/villages/character/embeddings/similarities?char=水&top_k=5&min_similarity=0.7
```

**响应体**：

```json
{
  "char": "水",
  "similarities": [
    {
      "char": "河",
      "cosine_similarity": 0.92,
      "rank": 1
    },
    {
      "char": "江",
      "cosine_similarity": 0.89,
      "rank": 2
    },
    {
      "char": "溪",
      "cosine_similarity": 0.85,
      "rank": 3
    },
    {
      "char": "湖",
      "cosine_similarity": 0.82,
      "rank": 4
    },
    {
      "char": "塘",
      "cosine_similarity": 0.78,
      "rank": 5
    }
  ],
  "total": 5
}
```

---

### 语义分析模块

#### 1. 语义类别 VTF 分析

**接口路径**：`GET /api/villages/semantic/category/vtf/regional`

**权限要求**：用户接口

**功能描述**：查询特定区域的语义类别 VTF（Virtual Term Frequency）分布。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| region_level | string | 是 | 区域层级（city/county/township） |
| city | string | 否 | 市级行政区 |
| county | string | 否 | 县级行政区 |
| township | string | 否 | 乡镇级行政区 |
| top_k | integer | 否 | 返回前 K 个类别 |

**请求示例**：

```
GET /api/villages/semantic/category/vtf/regional?region_level=city&city=广州市&top_k=5
```

**响应体**：

```json
{
  "region_level": "city",
  "region_name": "广州市",
  "results": [
    {
      "category": "地理特征",
      "vtf": 15680,
      "lift": 1.25,
      "z_score": 3.2,
      "rank": 1
    },
    {
      "category": "植物",
      "vtf": 8920,
      "lift": 1.15,
      "z_score": 2.1,
      "rank": 2
    },
    {
      "category": "建筑",
      "vtf": 7450,
      "lift": 0.95,
      "z_score": -0.5,
      "rank": 3
    },
    {
      "category": "姓氏",
      "vtf": 6230,
      "lift": 1.05,
      "z_score": 0.8,
      "rank": 4
    },
    {
      "category": "数字方位",
      "vtf": 5890,
      "lift": 1.10,
      "z_score": 1.2,
      "rank": 5
    }
  ],
  "total_categories": 9
}
```

---

#### 2. 语义组合模式（Bigrams）

**接口路径**：`GET /api/villages/semantic/composition/bigrams`

**权限要求**：用户接口

**功能描述**：分析语义类别的二元组合模式。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| min_frequency | integer | 否 | 最小频率阈值 |
| top_k | integer | 否 | 返回前 K 个模式 |

**请求示例**：

```
GET /api/villages/semantic/composition/bigrams?min_frequency=100&top_k=10
```

**响应体**：

```json
{
  "total_bigrams": 156,
  "results": [
    {
      "bigram": ["数字方位", "地理特征"],
      "frequency": 8520,
      "percentage": 2.98,
      "pmi": 2.35,
      "examples": ["东江", "南山", "西湖", "北河"]
    },
    {
      "bigram": ["姓氏", "建筑"],
      "frequency": 7890,
      "percentage": 2.76,
      "pmi": 1.98,
      "examples": ["陈屋", "李宅", "王府", "张庄"]
    },
    {
      "bigram": ["植物", "地理特征"],
      "frequency": 6750,
      "percentage": 2.36,
      "pmi": 2.12,
      "examples": ["竹林", "松岗", "柳塘", "梅溪"]
    }
  ]
}
```

---

### 空间分析模块

#### 1. 空间聚类查询

**接口路径**：`GET /api/villages/spatial/clusters`

**权限要求**：用户接口

**功能描述**：获取空间聚类结果。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| run_id | string | 否 | 聚类运行 ID（默认使用活跃运行） |
| min_cluster_size | integer | 否 | 最小聚类大小 |

**请求示例**：

```
GET /api/villages/spatial/clusters?run_id=spatial_eps_20&min_cluster_size=10
```

**响应体**：

```json
{
  "run_id": "spatial_eps_20",
  "algorithm": "DBSCAN",
  "parameters": {
    "eps": 20,
    "min_samples": 5
  },
  "clusters": [
    {
      "cluster_id": 1,
      "size": 1250,
      "centroid_lon": 113.2644,
      "centroid_lat": 23.1291,
      "region": "珠江三角洲",
      "density": 0.85
    },
    {
      "cluster_id": 2,
      "size": 890,
      "centroid_lon": 114.0579,
      "centroid_lat": 22.5431,
      "region": "深圳-东莞",
      "density": 0.78
    }
  ],
  "total_clusters": 15,
  "noise_points": 320
}
```

---

#### 2. 空间热点检测

**接口路径**：`GET /api/villages/spatial/hotspots`

**权限要求**：用户接口

**功能描述**：检测特定字符的空间热点区域。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| char | string | 否 | 字符（不指定则返回全局热点） |
| bandwidth | float | 否 | KDE 带宽参数 |
| threshold | float | 否 | 密度阈值 |

**请求示例**：

```
GET /api/villages/spatial/hotspots?char=水&bandwidth=0.5&threshold=0.01
```

**响应体**：

```json
{
  "char": "水",
  "hotspots": [
    {
      "hotspot_id": 1,
      "center_lon": 113.3,
      "center_lat": 23.2,
      "density": 0.085,
      "village_count": 450,
      "radius_km": 15.5,
      "region_name": "广州北部"
    },
    {
      "hotspot_id": 2,
      "center_lon": 113.8,
      "center_lat": 22.9,
      "density": 0.062,
      "village_count": 320,
      "radius_km": 12.3,
      "region_name": "东莞水乡"
    }
  ],
  "total_hotspots": 8
}
```

---

### ML 计算模块

#### 1. 运行聚类分析

**接口路径**：`POST /api/villages/compute/clustering/run`

**权限要求**：用户接口

**功能描述**：对村庄数据执行聚类分析。

**请求体**：

```json
{
  "algorithm": "kmeans",
  "n_clusters": 5,
  "features": ["semantic", "morphology", "spatial"],
  "region_filter": {
    "city": "广州市"
  },
  "random_state": 42
}
```

**响应体**：

```json
{
  "task_id": "clustering_20260304_123456",
  "status": "completed",
  "algorithm": "kmeans",
  "n_clusters": 5,
  "results": {
    "cluster_assignments": [
      {
        "cluster_id": 0,
        "village_count": 1250,
        "centroid": [0.25, 0.35, 0.15],
        "characteristics": {
          "dominant_semantic": "地理特征",
          "avg_name_length": 3.2,
          "spatial_density": 0.85
        }
      },
      {
        "cluster_id": 1,
        "village_count": 980,
        "centroid": [0.45, 0.25, 0.30],
        "characteristics": {
          "dominant_semantic": "姓氏",
          "avg_name_length": 2.8,
          "spatial_density": 0.72
        }
      }
    ],
    "metrics": {
      "silhouette_score": 0.65,
      "calinski_harabasz_score": 1250.5,
      "davies_bouldin_score": 0.85
    }
  }
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

**请求示例**：

```
GET /admin/analytics/user-segments?include_users=true
```

**响应体**：

```json
{
  "segments": [
    {
      "level": "高度活跃",
      "user_count": 25,
      "criteria": "最近 7 天内访问 >= 10 次",
      "avg_api_calls": 150,
      "users": [
        {
          "user_id": 1,
          "username": "user001",
          "api_calls_7d": 180,
          "last_seen": "2026-03-04T10:30:00Z"
        }
      ]
    },
    {
      "level": "活跃",
      "user_count": 50,
      "criteria": "最近 30 天内访问 >= 5 次",
      "avg_api_calls": 80
    },
    {
      "level": "一般",
      "user_count": 120,
      "criteria": "最近 90 天内访问 >= 1 次",
      "avg_api_calls": 25
    },
    {
      "level": "不活跃",
      "user_count": 80,
      "criteria": "90 天以上未访问",
      "avg_api_calls": 5
    },
    {
      "level": "流失",
      "user_count": 45,
      "criteria": "180 天以上未访问",
      "avg_api_calls": 0
    }
  ],
  "total_users": 320
}
```

---

#### 2. RFM 分析

**接口路径**：`GET /admin/analytics/rfm-analysis`

**权限要求**：管理员接口

**功能描述**：基于 Recency、Frequency、Monetary 三维分析用户价值。

**响应体**：

```json
{
  "analysis_date": "2026-03-04",
  "user_types": [
    {
      "type": "Champions",
      "description": "冠军用户 - 高频高活跃",
      "user_count": 15,
      "avg_api_calls": 500,
      "avg_recency_days": 1.5,
      "avg_frequency": 50,
      "characteristics": {
        "rfm_score": "555",
        "retention_rate": 0.95
      }
    },
    {
      "type": "Loyal",
      "description": "忠诚用户 - 长期稳定使用",
      "user_count": 30,
      "avg_api_calls": 200,
      "avg_recency_days": 5,
      "avg_frequency": 25,
      "characteristics": {
        "rfm_score": "445",
        "retention_rate": 0.85
      }
    },
    {
      "type": "Potential",
      "description": "潜力用户 - 有增长潜力",
      "user_count": 45,
      "avg_api_calls": 100,
      "avg_recency_days": 10,
      "avg_frequency": 15,
      "characteristics": {
        "rfm_score": "335",
        "retention_rate": 0.70
      }
    },
    {
      "type": "At Risk",
      "description": "需要关注 - 活跃度下降",
      "user_count": 35,
      "avg_api_calls": 50,
      "avg_recency_days": 30,
      "avg_frequency": 8,
      "characteristics": {
        "rfm_score": "225",
        "retention_rate": 0.45
      }
    },
    {
      "type": "Churned",
      "description": "流失用户 - 长期未使用",
      "user_count": 25,
      "avg_api_calls": 10,
      "avg_recency_days": 90,
      "avg_frequency": 2,
      "characteristics": {
        "rfm_score": "115",
        "retention_rate": 0.10
      }
    }
  ],
  "total_users": 150
}
```

---

#### 3. 异常检测

**接口路径**：`GET /admin/analytics/anomaly-detection`

**权限要求**：管理员接口

**功能描述**：检测用户异常行为。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| time_range | string | 否 | 时间范围（7d/30d/90d） |
| anomaly_types | string | 否 | 异常类型（逗号分隔） |

**请求示例**：

```
GET /admin/analytics/anomaly-detection?time_range=7d&anomaly_types=traffic,error_rate
```

**响应体**：

```json
{
  "time_range": "7d",
  "anomalies": [
    {
      "anomaly_type": "traffic",
      "user_id": 15,
      "username": "user015",
      "description": "短时间内大量请求",
      "details": {
        "api_calls_1h": 500,
        "normal_avg": 50,
        "deviation": 10.0,
        "timestamp": "2026-03-04T08:30:00Z"
      },
      "severity": "high"
    },
    {
      "anomaly_type": "error_rate",
      "user_id": 28,
      "username": "user028",
      "description": "高错误率",
      "details": {
        "error_rate": 0.45,
        "normal_avg": 0.05,
        "total_requests": 200,
        "error_requests": 90
      },
      "severity": "medium"
    },
    {
      "anomaly_type": "usage_pattern",
      "user_id": 42,
      "username": "user042",
      "description": "不寻常的 API 调用模式",
      "details": {
        "unusual_apis": ["/admin/users/all", "/admin/sessions/active"],
        "access_time": "03:00-04:00",
        "frequency": 50
      },
      "severity": "high"
    }
  ],
  "total_anomalies": 3
}
```

---

### 排行榜系统

#### 1. 获取排行榜

**接口路径**：`GET /admin/leaderboard/rankings`

**权限要求**：管理员接口

**功能描述**：获取用户或 API 排行榜。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| ranking_type | string | 是 | 排行类型（user_global/user_by_api/api/online_time） |
| metric | string | 否 | 指标（count/duration/upload/download） |
| api_path | string | 否 | API 路径（user_by_api 类型需要） |
| page | integer | 否 | 页码（默认 1） |
| page_size | integer | 否 | 每页数量（默认 20） |

**请求示例**：

```
GET /admin/leaderboard/rankings?ranking_type=user_global&metric=count&page=1&page_size=10
```

**响应体**：

```json
{
  "ranking_type": "user_global",
  "metric": "count",
  "page": 1,
  "page_size": 10,
  "total": 320,
  "rankings": [
    {
      "rank": 1,
      "user_id": 5,
      "username": "user005",
      "value": 15680,
      "percentage": 4.5,
      "last_active": "2026-03-04T10:30:00Z"
    },
    {
      "rank": 2,
      "user_id": 12,
      "username": "user012",
      "value": 12450,
      "percentage": 3.6,
      "last_active": "2026-03-04T09:15:00Z"
    },
    {
      "rank": 3,
      "user_id": 28,
      "username": "user028",
      "value": 10230,
      "percentage": 2.9,
      "last_active": "2026-03-03T18:45:00Z"
    }
  ]
}
```

---

### 会话管理

#### 1. 活跃会话列表

**接口路径**：`GET /admin/user-sessions/online-users`

**权限要求**：管理员接口

**功能描述**：获取当前在线用户列表。

**响应体**：

```json
{
  "online_count": 15,
  "sessions": [
    {
      "session_id": "sess_20260304_001",
      "user_id": 5,
      "username": "user005",
      "device_info": {
        "device_type": "desktop",
        "os": "Windows 10",
        "browser": "Chrome 120"
      },
      "ip_address": "192.168.1.100",
      "location": {
        "country": "中国",
        "city": "广州"
      },
      "login_time": "2026-03-04T08:30:00Z",
      "last_activity": "2026-03-04T10:25:00Z",
      "duration_seconds": 6900,
      "api_calls": 150
    }
  ]
}
```

---

## 日志统计接口

### 1. API 使用统计

**接口路径**：`GET /logs/api/usage`

**权限要求**：用户接口

**功能描述**：获取 API 使用统计信息。

**请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| start_date | string | 否 | 开始日期（YYYY-MM-DD） |
| end_date | string | 否 | 结束日期（YYYY-MM-DD） |
| api_path | string | 否 | 特定 API 路径 |

**请求示例**：

```
GET /logs/api/usage?start_date=2026-03-01&end_date=2026-03-04
```

**响应体**：

```json
{
  "start_date": "2026-03-01",
  "end_date": "2026-03-04",
  "total_calls": 125680,
  "unique_users": 280,
  "api_breakdown": [
    {
      "api_path": "/api/search_chars/",
      "calls": 25680,
      "percentage": 20.4,
      "unique_users": 180,
      "avg_response_time_ms": 45
    },
    {
      "api_path": "/api/villages/village/search",
      "calls": 18920,
      "percentage": 15.1,
      "unique_users": 150,
      "avg_response_time_ms": 120
    }
  ]
}
```

---

## SQL 查询接口

### 1. 执行 SQL 查询

**接口路径**：`POST /sql/query`

**权限要求**：用户接口

**功能描述**：执行 SQL 查询语句。

**请求体**：

```json
{
  "db_key": "dialects",
  "query": "SELECT location, pronunciation FROM phonology WHERE char = '東' LIMIT 10",
  "params": []
}
```

**响应体**：

```json
{
  "columns": ["location", "pronunciation"],
  "rows": [
    ["广州", "dung1"],
    ["深圳", "dung1"],
    ["香港", "dung1"],
    ["澳门", "dung1"]
  ],
  "row_count": 4,
  "execution_time_ms": 15
}
```

---
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

**注意**：本文档提供了主要 API 接口的示例。完整的 254 个 API 端点详细信息请访问在线 API 文档（Swagger UI 或 ReDoc）。

---

## 完整 API 端点分类列表

### 认证接口（Authentication）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/auth/register` | POST | 用户注册 |
| `/auth/login` | POST | 用户登录 |
| `/auth/logout` | POST | 用户登出 |
| `/auth/refresh` | POST | 刷新 Token |
| `/auth/me` | GET | 获取当前用户信息 |
| `/auth/updateProfile` | PUT | 更新用户资料 |
| `/auth/verify-email` | POST | 验证电子邮箱 |
| `/auth/report-online-time` | POST | 报告在线时长 |
| `/auth/leaderboard` | GET | 用户排行榜 |

---

### 方言查询接口（Query）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/ZhongGu` | POST | 查中古音韵 |
| `/api/YinWei` | POST | 查音位 |
| `/api/search_chars/` | GET | 查字 |
| `/api/search_tones/` | GET | 查调 |
| `/api/phonology` | POST | 传统音韵查询 |
| `/api/phonology_matrix` | POST | 音韵矩阵 |
| `/api/phonology_classification_matrix` | POST | 音素分类矩阵 |
| `/api/charlist` | GET | 字符列表 |

---

### 地理信息接口（Geo）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/get_locs/` | GET | 获取地点列表 |
| `/api/get_coordinates` | GET | 获取坐标 |
| `/api/get_regions` | GET | 获取区域列表 |
| `/api/partitions` | GET | 获取分区 |
| `/api/batch_match` | POST | 批量匹配地点 |

---

### 自定义数据接口（Custom）

#### 用户接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/submit_form` | POST | 提交自定义数据 |
| `/api/delete_form` | DELETE | 删除自定义数据 |
| `/api/get_custom` | GET | 获取自定义数据 |
| `/api/get_custom_feature` | GET | 获取自定义特征 |
| `/api/feature_counts` | GET | 特征计数 |
| `/api/feature_stats` | GET | 特征统计 |
| `/api/custom_regions` | GET | 自定义区域 |
| `/user/custom/all` | GET | 获取所有自定义数据 |
| `/user/custom/batch-create` | POST | 批量创建 |
| `/user/custom/batch-delete` | DELETE | 批量删除 |
| `/user/custom/edit` | PUT | 编辑自定义数据 |

#### 管理员接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/custom/all` | GET | 获取所有用户的自定义数据 |
| `/admin/custom/create` | POST | 创建自定义数据 |
| `/admin/custom/delete` | DELETE | 删除自定义数据 |
| `/admin/custom/num` | GET | 统计数量 |
| `/admin/custom/selected` | GET | 获取选中的数据 |
| `/admin/custom/user` | GET | 按用户查询 |

---

### 工具接口（Tools）

#### Check 工具（数据校验）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/tools/check/upload` | POST | 上传待检查文件 |
| `/api/tools/check/analyze` | POST | 分析数据 |
| `/api/tools/check/execute` | POST | 执行校验 |
| `/api/tools/check/get_data` | GET | 获取数据 |
| `/api/tools/check/get_tone_stats` | GET | 获取声调统计 |
| `/api/tools/check/save` | POST | 保存结果 |
| `/api/tools/check/update_row` | PUT | 更新行数据 |
| `/api/tools/check/batch_delete` | DELETE | 批量删除 |
| `/api/tools/check/download/{task_id}` | GET | 下载结果 |

#### Jyut2IPA 工具（粤拼转 IPA）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/tools/jyut2ipa/upload` | POST | 上传文件 |
| `/api/tools/jyut2ipa/process` | POST | 处理转换 |
| `/api/tools/jyut2ipa/progress/{task_id}` | GET | 查询进度 |
| `/api/tools/jyut2ipa/download/{task_id}` | GET | 下载结果 |

#### Merge 工具（数据合并）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/tools/merge/upload_files` | POST | 上传待合并文件 |
| `/api/tools/merge/upload_reference` | POST | 上传参考文件 |
| `/api/tools/merge/execute` | POST | 执行合并 |
| `/api/tools/merge/progress/{task_id}` | GET | 查询进度 |
| `/api/tools/merge/download/{task_id}` | GET | 下载结果 |

#### Praat 声学分析工具

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/tools/praat/capabilities` | GET | 获取后端能力 |
| `/api/tools/praat/uploads` | POST | 上传音频文件 |
| `/api/tools/praat/uploads/progress/{task_id}` | GET | 获取上传进度 |
| `/api/tools/praat/uploads/progress/{task_id}/audio` | GET | 下载标准化音频 |
| `/api/tools/praat/jobs` | POST | 创建分析任务 |
| `/api/tools/praat/jobs/progress/{job_id}` | GET | 获取分析进度 |
| `/api/tools/praat/jobs/progress/{job_id}/result` | GET | 获取分析结果 |

---

### VillagesML 机器学习接口（107 个端点）

#### 村庄搜索与详情

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/village/search` | GET | 搜索村庄 |
| `/api/villages/village/search/detail` | GET | 村庄详情 |
| `/api/villages/village/complete/{village_id}` | GET | 完整村庄信息 |
| `/api/villages/village/features/{village_id}` | GET | 村庄特征向量 |
| `/api/villages/village/spatial-features/{village_id}` | GET | 空间特征 |
| `/api/villages/village/semantic-structure/{village_id}` | GET | 语义结构 |
| `/api/villages/village/ngrams/{village_id}` | GET | N-gram 分解 |

#### 字符分析（Character）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/character/frequency/global` | GET | 全局字符频率 |
| `/api/villages/character/frequency/regional` | GET | 区域字符频率 |
| `/api/villages/character/tendency/by-char` | GET | 按字符查询倾向性 |
| `/api/villages/character/tendency/by-region` | GET | 按区域查询倾向性 |
| `/api/villages/character/significance/by-character` | GET | 字符显著性（按字符） |
| `/api/villages/character/significance/by-region` | GET | 字符显著性（按区域） |
| `/api/villages/character/significance/summary` | GET | 显著性摘要 |
| `/api/villages/character/embeddings/list` | GET | 嵌入向量列表 |
| `/api/villages/character/embeddings/vector` | GET | 获取字符向量 |
| `/api/villages/character/embeddings/similarities` | GET | 字符相似度 |

#### 语义分析（Semantic）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/semantic/category/list` | GET | 语义类别列表 |
| `/api/villages/semantic/category/vtf/global` | GET | 全局 VTF |
| `/api/villages/semantic/category/vtf/regional` | GET | 区域 VTF |
| `/api/villages/semantic/category/tendency` | GET | 类别倾向性 |
| `/api/villages/semantic/labels/categories` | GET | 标签类别 |
| `/api/villages/semantic/labels/by-category` | GET | 按类别查询标签 |
| `/api/villages/semantic/labels/by-character` | GET | 按字符查询标签 |
| `/api/villages/semantic/composition/bigrams` | GET | 二元组合 |
| `/api/villages/semantic/composition/trigrams` | GET | 三元组合 |
| `/api/villages/semantic/composition/patterns` | GET | 组合模式 |
| `/api/villages/semantic/composition/pmi` | GET | PMI 分析 |
| `/api/villages/semantic/subcategory/list` | GET | 子类别列表 |
| `/api/villages/semantic/subcategory/vtf/global` | GET | 子类别全局 VTF |
| `/api/villages/semantic/subcategory/vtf/regional` | GET | 子类别区域 VTF |
| `/api/villages/semantic/subcategory/tendency/top` | GET | 子类别倾向性 Top |
| `/api/villages/semantic/subcategory/chars/{subcategory}` | GET | 子类别字符 |
| `/api/villages/semantic/subcategory/comparison` | GET | 子类别比较 |
| `/api/villages/semantic/indices` | GET | 语义索引 |

#### 空间分析（Spatial）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/spatial/clusters` | GET | 空间聚类 |
| `/api/villages/spatial/clusters/available-runs` | GET | 可用聚类运行 |
| `/api/villages/spatial/clusters/summary` | GET | 聚类摘要 |
| `/api/villages/spatial/hotspots` | GET | 热点列表 |
| `/api/villages/spatial/hotspots/{hotspot_id}` | GET | 热点详情 |
| `/api/villages/spatial/integration` | GET | 空间整合分析 |
| `/api/villages/spatial/integration/summary` | GET | 整合摘要 |
| `/api/villages/spatial/integration/available-characters` | GET | 可用字符 |
| `/api/villages/spatial/integration/by-character/{character}` | GET | 按字符查询 |
| `/api/villages/spatial/integration/by-cluster/{cluster_id}` | GET | 按聚类查询 |
| `/api/villages/spatial/integration/clusterlist` | GET | 聚类列表 |

#### 模式分析（Patterns & Ngrams）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/ngrams/frequency` | GET | N-gram 频率 |
| `/api/villages/ngrams/regional` | GET | 区域 N-gram |
| `/api/villages/ngrams/patterns` | GET | N-gram 模式 |
| `/api/villages/ngrams/tendency` | GET | N-gram 倾向性 |
| `/api/villages/ngrams/significance` | GET | N-gram 显著性 |
| `/api/villages/patterns/frequency/global` | GET | 全局模式频率 |
| `/api/villages/patterns/frequency/regional` | GET | 区域模式频率 |
| `/api/villages/patterns/structural` | GET | 结构模式 |
| `/api/villages/patterns/tendency` | GET | 模式倾向性 |

#### 区域分析（Regional）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/regional/aggregates/city` | GET | 市级聚合 |
| `/api/villages/regional/aggregates/county` | GET | 县级聚合 |
| `/api/villages/regional/aggregates/town` | GET | 镇级聚合 |
| `/api/villages/regional/spatial-aggregates` | GET | 空间聚合 |
| `/api/villages/regional/vectors` | GET | 区域特征向量 |
| `/api/villages/regional/vectors/cluster` | POST | 向量聚类 |
| `/api/villages/regional/vectors/compare` | POST | 向量比较 |
| `/api/villages/regional/vectors/compare/batch` | POST | 批量比较 |
| `/api/villages/regional/vectors/reduce` | POST | 降维 |
| `/api/villages/regions/list` | GET | 区域列表 |
| `/api/villages/regions/similarity/pair` | GET | 区域相似度（成对） |
| `/api/villages/regions/similarity/matrix` | GET | 相似度矩阵 |
| `/api/villages/regions/similarity/search` | GET | 相似度搜索 |

#### ML 计算（Compute & Clustering）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/compute/clustering/run` | POST | 运行聚类 |
| `/api/villages/compute/clustering/scan` | POST | 扫描聚类参数 |
| `/api/villages/compute/clustering/hierarchical` | POST | 层次聚类 |
| `/api/villages/compute/clustering/spatial-aware` | POST | 空间感知聚类 |
| `/api/villages/compute/clustering/character-tendency` | POST | 字符倾向性聚类 |
| `/api/villages/compute/clustering/sampled-villages` | GET | 采样村庄 |
| `/api/villages/compute/clustering/cache` | GET | 聚类缓存 |
| `/api/villages/compute/clustering/cache-stats` | GET | 缓存统计 |
| `/api/villages/compute/features/extract` | POST | 特征提取 |
| `/api/villages/compute/features/aggregate` | POST | 特征聚合 |
| `/api/villages/compute/semantic/cooccurrence` | POST | 语义共现 |
| `/api/villages/compute/semantic/network` | POST | 语义网络 |
| `/api/villages/compute/subset/cluster` | POST | 子集聚类 |
| `/api/villages/compute/subset/compare` | POST | 子集比较 |
| `/api/villages/clustering/assignments` | GET | 聚类分配 |
| `/api/villages/clustering/assignments/by-region` | GET | 按区域聚类分配 |
| `/api/villages/clustering/metrics` | GET | 聚类指标 |
| `/api/villages/clustering/metrics/best` | GET | 最佳聚类指标 |
| `/api/villages/clustering/profiles` | GET | 聚类轮廓 |

#### 元数据与统计（Metadata & Statistics）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/metadata/stats/overview` | GET | 统计概览 |
| `/api/villages/metadata/stats/regions` | GET | 区域统计 |
| `/api/villages/metadata/stats/tables` | GET | 表统计 |
| `/api/villages/statistics/database` | GET | 数据库统计 |
| `/api/villages/statistics/ngrams` | GET | N-gram 统计 |

#### VillagesML 管理接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/villages/admin/run-ids/active` | GET | 活跃运行 ID |
| `/api/villages/admin/run-ids/active/{analysis_type}` | GET | 按类型查询活跃运行 |
| `/api/villages/admin/run-ids/available/{analysis_type}` | GET | 可用运行 ID |
| `/api/villages/admin/run-ids/metadata/{run_id}` | GET | 运行元数据 |
| `/api/villages/admin/run-ids/refresh` | POST | 刷新运行 ID |

---

### 管理员接口（Admin）

#### 用户管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/users/all` | GET | 获取所有用户 |
| `/admin/users/list` | GET | 用户列表 |
| `/admin/users/single` | GET | 单个用户详情 |
| `/admin/users/create` | POST | 创建用户 |
| `/admin/users/update` | PUT | 更新用户 |
| `/admin/users/delete` | DELETE | 删除用户 |
| `/admin/users/password` | PUT | 修改密码 |
| `/admin/users/let_admin` | PUT | 设置管理员权限 |

#### 用户行为分析

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/analytics/user-segments` | GET | 用户分段 |
| `/admin/analytics/rfm-analysis` | GET | RFM 分析 |
| `/admin/analytics/anomaly-detection` | GET | 异常检测 |
| `/admin/analytics/user-preferences` | GET | 用户偏好 |
| `/admin/analytics/api-diversity` | GET | API 多样性 |
| `/admin/analytics/user-growth` | GET | 用户增长 |
| `/admin/analytics/dashboard` | GET | 分析仪表板 |
| `/admin/analytics/recent-trends` | GET | 近期趋势 |
| `/admin/analytics/api-performance` | GET | API 性能 |
| `/admin/analytics/geo-distribution` | GET | 地理分布 |
| `/admin/analytics/device-distribution` | GET | 设备分布 |
| `/admin/analytics/export` | GET | 导出分析数据 |

#### 排行榜

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/leaderboard/rankings` | GET | 获取排行榜 |
| `/admin/leaderboard/available-apis` | GET | 可用 API 列表 |

#### API 使用统计

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/api-usage/api-summary` | GET | API 使用概览 |
| `/admin/api-usage/api-detail` | GET | API 详细统计 |
| `/admin/api-usage/api-usage` | GET | API 使用情况 |

#### 会话管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/sessions/active` | GET | 活跃会话 |
| `/admin/sessions/stats` | GET | 会话统计 |
| `/admin/sessions/user/{user_id}` | GET | 用户会话 |
| `/admin/sessions/revoke/{token_id}` | DELETE | 撤销会话 |
| `/admin/sessions/revoke-user/{user_id}` | DELETE | 撤销用户所有会话 |
| `/admin/sessions/cleanup-expired` | POST | 清理过期会话 |

#### 用户会话（增强版）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/user-sessions/list` | GET | 会话列表 |
| `/admin/user-sessions/online-users` | GET | 在线用户 |
| `/admin/user-sessions/stats` | GET | 会话统计 |
| `/admin/user-sessions/analytics` | GET | 会话分析 |
| `/admin/user-sessions/{session_id}` | GET | 会话详情 |
| `/admin/user-sessions/{session_id}/activity` | GET | 会话活动 |
| `/admin/user-sessions/{session_id}/revoke` | DELETE | 撤销会话 |
| `/admin/user-sessions/{session_id}/flag` | PUT | 标记会话 |
| `/admin/user-sessions/user/{user_id}/history` | GET | 用户历史 |
| `/admin/user-sessions/revoke-user/{user_id}` | DELETE | 撤销用户会话 |
| `/admin/user-sessions/revoke-bulk` | DELETE | 批量撤销 |

#### 登录日志

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/login-logs/success-login-logs` | GET | 成功登录日志 |
| `/admin/login-logs/failed-login-logs` | GET | 失败登录日志 |

#### 统计信息

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/stats/stats` | GET | 统计概览 |
| `/admin/stats/login-history` | GET | 登录历史 |

#### 缓存管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/cache/clear_dialect_cache` | POST | 清理方言缓存 |
| `/admin/cache/clear_redis_cache` | POST | 清理 Redis 缓存 |
| `/admin/cache/clear_all_cache` | POST | 清理所有缓存 |
| `/admin/cache/cache_stats` | GET | 缓存统计 |
| `/admin/cache/cache_status` | GET | 缓存状态 |

#### 自定义区域管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/custom-regions/all` | GET | 所有自定义区域 |
| `/admin/custom-regions/user` | GET | 用户自定义区域 |
| `/admin/custom-regions/create` | POST | 创建区域 |
| `/admin/custom-regions/update` | PUT | 更新区域 |
| `/admin/custom-regions/delete` | DELETE | 删除区域 |
| `/admin/custom-regions/batch-delete` | DELETE | 批量删除 |
| `/admin/custom-regions/count` | GET | 统计数量 |
| `/admin/custom-regions/stats` | GET | 区域统计 |

#### IP 查询

| 端点 | 方法 | 功能 |
|------|------|------|
| `/admin/ip/{api_name}/{ip}` | GET | 查询 IP 信息 |

---

### 日志统计接口（Logs）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/logs/keyword/top` | GET | Top 关键词 |
| `/logs/keyword/search` | GET | 关键词搜索 |
| `/logs/api/usage` | GET | API 使用统计 |
| `/logs/stats/summary` | GET | 统计摘要 |
| `/logs/stats/fields` | GET | 字段分布 |
| `/logs/stats/daily` | GET | 每日统计 |
| `/logs/stats/hourly` | GET | 每小时统计 |
| `/logs/stats/ranking` | GET | 排行统计 |
| `/logs/stats/api-history` | GET | API 历史 |
| `/logs/visits/total` | GET | 总访问量 |
| `/logs/visits/today` | GET | 今日访问 |
| `/logs/visits/history` | GET | 访问历史 |
| `/logs/visits/by-path` | GET | 按路径统计 |
| `/logs/database/size` | GET | 数据库大小 |

---

### SQL 查询接口（SQL）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/sql/query` | POST | 执行 SQL 查询 |
| `/sql/query/columns` | GET | 获取列信息 |
| `/sql/mutate` | POST | 执行修改操作 |
| `/sql/batch-mutate` | POST | 批量修改 |
| `/sql/batch-replace-preview` | POST | 批量替换预览 |
| `/sql/batch-replace-execute` | POST | 执行批量替换 |
| `/sql/distinct-query` | POST | 去重查询 |
| `/sql/distinct/{db_key}/{table_name}/{column}` | GET | 获取唯一值 |
| `/sql/tree/full` | GET | 完整数据库树 |
| `/sql/tree/lazy` | GET | 懒加载数据库树 |

---

### HTML 页面路由

| 端点 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 首页 |
| `/auth` | GET | 登录页面 |
| `/admin` | GET | 管理员页面 |
| `/explore` | GET | 探索页面 |
| `/menu` | GET | 菜单页面 |
| `/detail` | GET | 详情页面 |
| `/intro` | GET | 介绍页面 |
| `/villagesML` | GET | VillagesML 页面 |
| `/__ping` | GET | 健康检查 |

---

## 总结

本系统共提供 **254 个 API 端点**，涵盖：

- **认证与用户管理**：9 个端点
- **方言查询**：8 个端点
- **地理信息**：5 个端点
- **自定义数据**：17 个端点
- **工具模块**：26 个端点（Check、Jyut2IPA、Merge、Praat）
- **VillagesML 机器学习**：107 个端点
- **管理员功能**：62 个端点
- **日志统计**：14 个端点
- **SQL 查询**：10 个端点
- **HTML 页面**：9 个端点

详细的请求参数、响应格式和使用示例，请访问：
- **Swagger UI**：http://localhost:5000/docs
- **ReDoc**：http://localhost:5000/redoc
