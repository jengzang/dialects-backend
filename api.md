# API 参考

本文按当前主应用 `app.main:app` 的 OpenAPI 自动生成（2026-10-13），共 345 个 HTTP 操作、282 个 schema。

- [返回项目介绍](README.md)
- [完整 OpenAPI JSON](docs/openapi.json)：可导入 Swagger Editor、Postman 等工具。
- 重新生成：在项目根目录运行 `python scripts/export_api_docs.py`，需要已安装项目依赖。
- 本地启动：`python run.py -r MINE -close`，随后访问 `http://127.0.0.1:5000/docs` 或 `/redoc`；端口冲突时以启动输出为准。
- `WEB` 模式关闭 Swagger/ReDoc 页面；`/openapi.json` 仍由 FastAPI 注册。

## 调用约定

路径已经包含路由装配后的前缀，调用时不要再次添加 `/api`。JSON 请求用 `Content-Type: application/json`；文件上传和登录按各接口列出的媒体类型提交。

登录 `POST /api/auth/login` 使用 `application/x-www-form-urlencoded`，字段为 `username`（用户名或邮箱）和 `password`。获取 token 后，以 `Authorization: Bearer <access_token>` 调用受保护接口；刷新接口使用 JSON：`{"refresh_token": "..."}`。

认证要求以实际依赖和权限检查为准。OpenAPI 的 security 标注仅反映可自动识别的安全依赖；未标注不代表允许匿名访问。词表写入还需要编辑/管理权限，管理员接口需要管理员权限。

响应表列出 OpenAPI 声明的状态与结构。部分接口返回 dict 或动态数据，成功响应 schema 为 `{}`，这表示代码未声明固定响应模型，不能据此推断字段。业务分支、中间件还可能返回未列出的 400/401/403/404/413/429/500/503 等错误；错误内容以实际响应及路由实现为准。

此文档覆盖主应用注册的 HTTP 接口，不包含静态文件挂载或 WebSocket。主应用当前也注册 GIS 和 Cluster；GIS 引擎是否可用需查状态及部署资源，路由存在不等于数据已加载。

已知 OpenAPI 限制：字表检查模块的 analyze_async/progress 存在重复路由声明，生成时会提示 Duplicate Operation ID。本目录按最终 OpenAPI 的方法与路径列出；用于生成客户端前应先处理源代码的重复声明。Pydantic 自定义 validator 中的跨字段规则和动态允许值也不会全部反映在 JSON Schema 中。

## 接口分组

- [query](#group-1)：21 个操作
- [geo](#group-2)：16 个操作
- [User](#group-3)：18 个操作
- [Notes](#group-4)：1 个操作
- [toponyms](#group-5)：5 个操作
- [html](#group-6)：13 个操作
- [其他](#group-7)：1 个操作
- [Authentication](#group-8)：9 个操作
- [Vocabulary](#group-9)：17 个操作
- [Vocabulary SQL](#group-10)：9 个操作
- [admin users](#group-11)：10 个操作
- [admin stats](#group-12)：2 个操作
- [admin user-sessions](#group-13)：11 个操作
- [admin sessions (legacy)](#group-14)：6 个操作
- [admin submissions](#group-15)：14 个操作
- [admin suggestions](#group-16)：2 个操作
- [admin analytics](#group-17)：20 个操作
- [admin system](#group-18)：6 个操作
- [工具-Check](#group-19)：11 个操作
- [工具-Jyut2IPA](#group-20)：4 个操作
- [工具-Merge](#group-21)：5 个操作
- [工具-Praat](#group-22)：9 个操作
- [工具-Cluster](#group-23)：9 个操作
- [sql](#group-24)：12 个操作
- [日誌統計](#group-25)：14 个操作
- [villagesML-Character](#group-26)：11 个操作
- [villagesML-Village](#group-27)：7 个操作
- [villagesML-Subset](#group-28)：1 个操作
- [villagesML-Metadata](#group-29)：3 个操作
- [villagesML-Semantic](#group-30)：18 个操作
- [villagesML-Clustering](#group-31)：5 个操作
- [villagesML-Spatial](#group-32)：11 个操作
- [villagesML-Ngrams](#group-33)：5 个操作
- [villagesML-Patterns](#group-34)：4 个操作
- [villagesML-Regional](#group-35)：13 个操作
- [villagesML-Compute](#group-36)：14 个操作
- [villagesML-Admin](#group-37)：6 个操作
- [villagesML-Statistics](#group-38)：2 个操作

- [Schema 字段与完整定义](#schemas)

<a id="group-1"></a>

## query

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/phonology` | Api Run Phonology Analysis |
| GET | `/api/feature_counts` | Feature Counts |
| POST | `/api/syllable_counts` | Syllable Counts |
| POST | `/api/feature_stats` | Feature Stats |
| GET | `/api/phonology_matrix` | Phonology Matrix |
| POST | `/api/phonology_matrix` | Phonology Matrix Post |
| POST | `/api/phonology_classification_matrix` | Api Phonology Classification Matrix |
| POST | `/api/pho_pie_by_value` | Api Pho Pie By Value |
| POST | `/api/pho_pie_by_status` | Api Pho Pie By Status |
| POST | `/api/charlist` | Generate Combinations And Query |
| POST | `/api/ZhongGu` | Analyze Zhonggu |
| POST | `/api/YinWei` | Analyze Yinwei |
| GET | `/api/search_chars/` | Search Chars |
| GET | `/api/search_tones/` | Search Tones O |
| GET | `/api/compare/chars` | Compare Chars |
| GET | `/api/compare/tones` | Compare Tones Route |
| POST | `/api/compare/ZhongGu` | Compare Zhonggu |
| GET | `/api/yubao/vocabulary/words` | Get Vocabulary Words |
| GET | `/api/yubao/grammar/sentences` | Get Grammar Sentences |
| GET | `/api/yubao/vocabulary/items` | Get Vocabulary Items |
| GET | `/api/yubao/grammar/items` | Get Grammar Items |

### POST `/api/phonology`

Api Run Phonology Analysis

Unified phonology analysis endpoint.

实现：[app/routes/core/phonology.py](app/routes/core/phonology.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [AnalysisPayload](#schema-analysispayload) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/feature_counts`

Feature Counts

实现：[app/routes/core/phonology.py](app/routes/core/phonology.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `locations` | query | 否 | array&lt;string&gt; |  |  |
| `regions` | query | 否 | array&lt;string&gt; |  |  |
| `new_format` | query | 否 | boolean | default=false |  |
| `region_mode` | query | 否 | string | default="yindian" |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/syllable_counts`

Syllable Counts

实现：[app/routes/core/phonology.py](app/routes/core/phonology.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SyllableCountsRequest](#schema-syllablecountsrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/feature_stats`

Feature Stats

Get feature statistics with cache support.

实现：[app/routes/core/phonology.py](app/routes/core/phonology.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FeatureStatsRequest](#schema-featurestatsrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/phonology_matrix`

Phonology Matrix

GET matrix query interface.

实现：[app/routes/core/matrix.py](app/routes/core/matrix.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `locations` | query | 否 | array&lt;string&gt; / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/phonology_matrix`

Phonology Matrix Post

Backward-compatible POST matrix query interface.

实现：[app/routes/core/matrix.py](app/routes/core/matrix.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [PhonologyMatrixRequest](#schema-phonologymatrixrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/phonology_classification_matrix`

Api Phonology Classification Matrix

創建音韻特徵分類矩陣

根據用戶指定的分類維度，組織音韻特徵數據。
結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。

实现：[app/routes/core/matrix.py](app/routes/core/matrix.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [PhonologyClassificationMatrixRequest](#schema-phonologyclassificationmatrixrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/pho_pie_by_value`

Api Pho Pie By Value

音值視角餅圖數據。

固定查詢聲母、韻母、聲調三個 feature。
每個獨特音值對應一個餅圖，扇形 = level1 各類別佔比；
點擊扇形可取得 level2 細分。

实现：[app/routes/core/matrix.py](app/routes/core/matrix.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [PhoPieRequest](#schema-phopierequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/pho_pie_by_status`

Api Pho Pie By Status

地位視角餅圖數據。

固定查詢聲母、韻母、聲調三個 feature。
每個 level1 類別對應一個餅圖，扇形 = 各音值佔比；
點擊扇形可取得該音值在 level2 的細分。

实现：[app/routes/core/matrix.py](app/routes/core/matrix.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [PhoPieRequest](#schema-phopierequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/charlist`

Generate Combinations And Query

实现：[app/routes/core/new_pho.py](app/routes/core/new_pho.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CharListRequest](#schema-charlistrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;object&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/ZhongGu`

Analyze Zhonggu

实现：[app/routes/core/new_pho.py](app/routes/core/new_pho.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ZhongGuAnalysis](#schema-zhongguanalysis) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/YinWei`

Analyze Yinwei

实现：[app/routes/core/new_pho.py](app/routes/core/new_pho.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [YinWeiAnalysis](#schema-yinweianalysis) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/search_chars/`

Search Chars

实现：[app/routes/core/search.py](app/routes/core/search.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `chars` | query | 是 | array&lt;string&gt; |  | 要查询的汉字列表，最多20个字 |
| `locations` | query | 否 | array&lt;string&gt; / null |  | 地点列表 |
| `regions` | query | 否 | array&lt;string&gt; / null |  | 分区列表 |
| `region_mode` | query | 否 | string | default="yindian" | 分区模式: yindian/map |
| `table_name` | query | 否 | string | default="characters" | 字表名称 |
| `response_mode` | query | 否 | string | default="legacy"; enum=["legacy", "compact"] | 响应模式: legacy/compact |
| `include_custom` | query | 否 | boolean | default=false | 是否附带当前用户自定义数据 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/search_tones/`

Search Tones O

实现：[app/routes/core/search.py](app/routes/core/search.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `locations` | query | 否 | array&lt;string&gt; / null |  | 地点列表 |
| `regions` | query | 否 | array&lt;string&gt; / null |  | 分区列表 |
| `region_mode` | query | 否 | string | default="yindian" | 分区模式: yindian/map |
| `include_custom` | query | 否 | boolean | default=false | 是否附带当前用户自定义调值数据 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/compare/chars`

Compare Chars

比较多个汉字在不同地点的音韵特征差异

- chars: 要比较的汉字列表（至少2个）
- features: 要比较的特征列表（聲母/韻母/聲調）
- locations: 要查的地点，可多个
- regions: 要查的分区，可多个
- region_mode: 分区模式，可选 'yindian' 或 'map'

返回：
- results: 按地点分组的比较结果
  - location: 地点名称
  - comparisons: 所有字对的比较结果
    - pair: 比较的字对
    - features: 各特征的比较结果
      - status: same/diff/partial/unknown
        - same: 完全相同
        - diff: 完全不同
        - partial: 部分相同（多音字导致）
        - unknown: 无法判断（有一方数据为空）
      - value: 当 status=same 时的共同值
      - values: 当 status=diff/partial/unknown 时各字的值

实现：[app/routes/core/compare.py](app/routes/core/compare.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `chars` | query | 是 | array&lt;string&gt; |  | 要比较的汉字列表，至少2个 |
| `features` | query | 是 | array&lt;string&gt; |  | 要比较的特征列表：聲母/韻母/聲調 |
| `locations` | query | 否 | array&lt;string&gt; / null |  | 要查的地点，可多个 |
| `regions` | query | 否 | array&lt;string&gt; / null |  | 要查的分区，可多个 |
| `region_mode` | query | 否 | string | default="yindian" | 分区模式，可选 'yindian' 或 'map' |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/compare/tones`

Compare Tones Route

比较同一地点内不同调类的合并关系

- tone_classes: 要比较的调类编号列表（1-10），如 [1,2,3]
- locations: 要查的地点，可多个
- regions: 要查的分区，可多个
- region_mode: 分区模式，可选 'yindian' 或 'map'

返回：
- results: 按地点分组的调类比较结果
  - location: 地点名称
  - comparisons: 所有调类对的比较结果
    - pair: 比较的调类对（如 ["T1", "T3"]）
    - comparison: 比较结果
      - status: same/partial/diff/maybe/unknown
        - same: 两个调类完全合并（match 完全相同）
        - partial: 部分合并（match 或 value 有交集但不完全相同）
        - diff: 不合并（match 和 value 都没有交集）
        - maybe: 可能合并（特殊规则：T6为空且T5为去声，或T8为空且T7为入声）
        - unknown: 无法判断（两方都为空，或一方为空但不满足maybe条件）
      - t1_value: 第一个调类的 value 列表（调值）
      - t2_value: 第二个调类的 value 列表
      - t1_match: 第一个调类的 match 列表（匹配的调类）
      - t2_match: 第二个调类的 match 列表
      - t1_name: 第一个调类的 name 列表（调类名称）
      - t2_name: 第二个调类的 name 列表
      - intersection: 当 status=partial 时的交集 {"match": [...], "value": [...]}
      - reason: 当 status=maybe 时的原因说明

实现：[app/routes/core/compare.py](app/routes/core/compare.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `tone_classes` | query | 是 | array&lt;integer&gt; |  | 要比较的调类编号列表，如 [1,2,3] 表示 T1,T2,T3 |
| `locations` | query | 否 | array&lt;string&gt; / null |  | 要查的地点，可多个 |
| `regions` | query | 否 | array&lt;string&gt; / null |  | 要查的分区，可多个 |
| `region_mode` | query | 否 | string | default="yindian" | 分区模式，可选 'yindian' 或 'map' |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/compare/ZhongGu`

Compare Zhonggu

比较两组中古音条件在方言中的读音差异

性能优化：
- 使用轻量级统计查询（不处理多音字详情）
- 只返回值和占比，不返回具体汉字
- 预计比标准 ZhongGu API 快 3-5 倍

实现：[app/routes/core/compare.py](app/routes/core/compare.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CompareZhongGuAnalysis](#schema-comparezhongguanalysis) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/yubao/vocabulary/words`

Get Vocabulary Words

实现：[app/routes/yubao.py](app/routes/yubao.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  |  |
| `limit` | query | 否 | integer | default=50; minimum=1; maximum=500 |  |
| `all` | query | 否 | boolean | default=false |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [YubaoSuggestionResponse](#schema-yubaosuggestionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/yubao/grammar/sentences`

Get Grammar Sentences

实现：[app/routes/yubao.py](app/routes/yubao.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  |  |
| `limit` | query | 否 | integer | default=50; minimum=1; maximum=500 |  |
| `all` | query | 否 | boolean | default=false |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [YubaoSuggestionResponse](#schema-yubaosuggestionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/yubao/vocabulary/items`

Get Vocabulary Items

实现：[app/routes/yubao.py](app/routes/yubao.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `word` | query | 是 | string | minLength=1 |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=100; minimum=1; maximum=2000 |  |
| `sort_by` | query | 否 | string / null |  |  |
| `sort_desc` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [YubaoVocabularyItemsResponse](#schema-yubaovocabularyitemsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/yubao/grammar/items`

Get Grammar Items

实现：[app/routes/yubao.py](app/routes/yubao.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `sentence` | query | 是 | string | minLength=1 |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=100; minimum=1; maximum=2000 |  |
| `sort_by` | query | 否 | string / null |  |  |
| `sort_desc` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [YubaoGrammarItemsResponse](#schema-yubaogrammaritemsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-2"></a>

## geo

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/partitions` | Api Get Partitions |
| GET | `/api/locations/detail` | Get Location Detail |
| GET | `/api/locations/partitions` | Get Location Partitions |
| GET | `/api/locations/points` | Get Location Points |
| GET | `/api/get_regions` | Get Regions |
| GET | `/api/gis/status` | Geo Status |
| GET | `/api/gis/query/point` | Geo Query Point |
| GET | `/api/gis/query/point-with-tolerance` | Geo Query Point With Tolerance |
| POST | `/api/gis/query/geometry` | Geo Query Geometry |
| GET | `/api/gis/boundary/by-id` | Geo Boundary By Id |
| GET | `/api/gis/search` | Geo Search |
| GET | `/api/gis/resolve` | Geo Resolve |
| GET | `/api/gis/children` | Geo Children |
| GET | `/api/batch_match` | Batch Match |
| GET | `/api/get_coordinates` | Get Coordinates |
| GET | `/api/get_locs/` | Get All Locs |

### GET `/api/partitions`

Api Get Partitions

- 獲取下一級的音典分區。
- 傳入parent-當前分區名（某一級，例如嶺南）；
- 返回下一級所有的音典分區（partitions子數組），以及層級（level）

实现：[app/routes/geo/get_partitions.py](app/routes/geo/get_partitions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `parent` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/locations/detail`

Get Location Detail

实现：[app/routes/geo/locations.py](app/routes/geo/locations.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `name` | query | 是 | string |  | 地點簡稱 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/locations/partitions`

Get Location Partitions

实现：[app/routes/geo/locations.py](app/routes/geo/locations.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/locations/points`

Get Location Points

实现：[app/routes/geo/locations.py](app/routes/geo/locations.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/get_regions`

Get Regions

- :param input_data:地點簡稱
- :return: 對應的音典分區

实现：[app/routes/geo/get_regions.py](app/routes/geo/get_regions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `input_data` | query | 是 | string / array&lt;string&gt; |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/status`

Geo Status

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/query/point`

Geo Query Point

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `lng` | query | 是 | number | minimum=-180; maximum=180 |  |
| `lat` | query | 是 | number | minimum=-90; maximum=90 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/query/point-with-tolerance`

Geo Query Point With Tolerance

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `lng` | query | 是 | number | minimum=-180; maximum=180 |  |
| `lat` | query | 是 | number | minimum=-90; maximum=90 |  |
| `tolerance_metre` | query | 否 | integer | default=2500; minimum=0 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/gis/query/geometry`

Geo Query Geometry

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [GeometryQueryBody](#schema-geometryquerybody) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/boundary/by-id`

Geo Boundary By Id

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `feature_id` | query | 是 | integer | minimum=1 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/search`

Geo Search

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 是 | string | minLength=1 |  |
| `deep` | query | 否 | integer / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/resolve`

Geo Resolve

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `province` | query | 否 | string / null |  |  |
| `city` | query | 否 | string / null |  |  |
| `county` | query | 否 | string / null |  |  |
| `path` | query | 否 | string / null |  | Slash-separated administrative path, for example 北京市/北京市/东城区 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/gis/children`

Geo Children

实现：[app/routes/geo/areacity_query.py](app/routes/geo/areacity_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `parent_id` | query | 否 | integer / null |  |  |
| `deep` | query | 否 | integer / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/batch_match`

Batch Match

用于 /api/batch_match 路由，匹配用戶輸入的地點，並提示正確的地點。
- input_string-用戶輸入的字符串，用於後端匹配正確的地點
- filter_valid_abbrs_only-是否過濾沒有字表的簡稱（若為真則過濾）
- 返回值：
    "success": bool, 代表是否找到完全相同的
    "message": 提示信息
    "items": 所有匹配的地點序列

实现：[app/routes/geo/batch_match.py](app/routes/geo/batch_match.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `input_string` | query | 是 | string |  | 用戶輸入的字符串，用於後端匹配正確的地點 |
| `filter_valid_abbrs_only` | query | 否 | boolean | default=true | 是否過濾沒有字表的簡稱（若為真則過濾） |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/get_coordinates`

Get Coordinates

实现：[app/routes/geo/get_coordinates.py](app/routes/geo/get_coordinates.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `regions` | query | 是 | string |  |  |
| `locations` | query | 是 | string |  |  |
| `region_mode` | query | 否 | string | default="yindian" |  |
| `iscustom` | query | 否 | boolean / null |  |  |
| `flag` | query | 否 | boolean | default=true |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/get_locs/`

Get All Locs

- 用于 /api/get_locs 查匹配的地點（分區+地點），返回地點序列。
- locations-要查的地點，可多個
- regions-要查的分區，可多個（輸入某一級的分區）
- region_mode-使用的分區

实现：[app/routes/geo/get_locs.py](app/routes/geo/get_locs.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `locations` | query | 否 | array&lt;string&gt; / null |  | 要查的地點，可多個 |
| `regions` | query | 否 | array&lt;string&gt; / null |  | 要查的分區，可多個（輸入某一級的分區） |
| `region_mode` | query | 否 | string | default="yindian" | 分區模式，yindian 或 map |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-3"></a>

## User

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/submit_form` | Submit Form |
| DELETE | `/api/delete_form` | Delete Form |
| GET | `/api/get_custom` | Query Location Data |
| GET | `/api/get_custom_feature` | Get Custom Feature |
| POST | `/api/custom_regions` | Create Or Update Custom Region |
| DELETE | `/api/custom_regions` | Delete Custom Region |
| GET | `/api/custom_regions` | Get Custom Regions |
| POST | `/api/suggestions` | Submit Suggestion |
| GET | `/api/suggestions/my` | Get My Suggestions |
| GET | `/user/custom/all` | Get All Own Custom Data |
| GET | `/user/custom/counts` | Get User Custom Counts |
| GET | `/user/custom/points` | Get User Custom Points |
| GET | `/user/custom/features` | Get User Custom Feature Groups |
| GET | `/user/custom/data-by-point` | Get Custom Data By Point |
| GET | `/user/custom/data-by-feature` | Get Custom Data By Feature |
| POST | `/user/custom/batch-create` | Batch Create Custom Data |
| PUT | `/user/custom/edit` | Edit Custom Data |
| DELETE | `/user/custom/batch-delete` | Batch Delete Custom Data |

### POST `/api/submit_form`

Submit Form

Handle user custom form submission.

实现：[app/routes/user/form_submit.py](app/routes/user/form_submit.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FormData](#schema-formdata) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/delete_form`

Delete Form

用于 /api/delete_form 的用户自定义表单删除。

实现：[app/routes/user/form_submit.py](app/routes/user/form_submit.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FormData](#schema-formdata) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/get_custom`

Query Location Data

Query custom records by location/region + 特徵, with optional 聲韻調 filter.
Backward compatible:
- If `phonology` is not provided, behavior is unchanged.
- If `phonology` is provided, apply extra filter on Information.聲韻調.

实现：[app/routes/user/custom_query.py](app/routes/user/custom_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `locations` | query | 是 | array&lt;string&gt; |  | Target locations |
| `regions` | query | 是 | array&lt;string&gt; |  | Target regions |
| `need_features` | query | 是 | string |  | Feature filters, comma-separated |
| `phonology` | query | 否 | string / null |  | Optional 聲韻調 filters (聲母/韻母/聲調), comma-separated |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/get_custom_feature`

Get Custom Feature

Match custom features for the current user by input keyword.

实现：[app/routes/user/custom_query.py](app/routes/user/custom_query.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `locations` | query | 是 | array&lt;string&gt; |  | Target locations |
| `regions` | query | 是 | array&lt;string&gt; |  | Target regions |
| `word` | query | 是 | string |  | Input keyword for feature matching |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/custom_regions`

Create Or Update Custom Region

创建或更新自定义区域

- 如果区域名称已存在，则更新（覆盖）
- 如果区域名称不存在，则创建新区域
- 需要登录认证

实现：[app/routes/user/custom_regions.py](app/routes/user/custom_regions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CustomRegionCreate](#schema-customregioncreate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/custom_regions`

Delete Custom Region

删除自定义区域

- 需要登录认证
- 只能删除自己的区域

实现：[app/routes/user/custom_regions.py](app/routes/user/custom_regions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_name` | query | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/custom_regions`

Get Custom Regions

获取用户的自定义区域列表

- 需要登录认证
- 可选：通过 region_name 参数筛选特定区域
- 未登录用户返回空列表

实现：[app/routes/user/custom_regions.py](app/routes/user/custom_regions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_name` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CustomRegionList](#schema-customregionlist) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/suggestions`

Submit Suggestion

实现：[app/routes/user/suggestions.py](app/routes/user/suggestions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SuggestionCreate](#schema-suggestioncreate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SuggestionCreateResponse](#schema-suggestioncreateresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/suggestions/my`

Get My Suggestions

实现：[app/routes/user/suggestions.py](app/routes/user/suggestions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `status` | query | 否 | string / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=20; minimum=1; maximum=100 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SuggestionListResponse](#schema-suggestionlistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/user/custom/all`

Get All Own Custom Data

獲取用戶自己的所有 custom 數據

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CustomDataAllResponse](#schema-customdataallresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/user/custom/counts`

Get User Custom Counts

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/user/custom/points`

Get User Custom Points

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `keyword` | query | 否 | string / null |  | 可選關鍵詞模糊搜索 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CustomPointGroupListResponse](#schema-custompointgrouplistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/user/custom/features`

Get User Custom Feature Groups

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `keyword` | query | 否 | string / null |  | 可選關鍵詞模糊搜索 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CustomFeatureGroupListResponse](#schema-customfeaturegrouplistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/user/custom/data-by-point`

Get Custom Data By Point

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `location` | query | 否 | string / null |  | 方言點簡稱 |
| `region` | query | 否 | string / null |  | 音典分區 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CustomDataListResponse](#schema-customdatalistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/user/custom/data-by-feature`

Get Custom Data By Feature

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `feature` | query | 是 | string |  | 特徵名稱 |
| `phonology` | query | 是 | string |  | 聲韻調類別 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CustomDataListResponse](#schema-customdatalistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/user/custom/batch-create`

Batch Create Custom Data

批量創建 custom 數據

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | array&lt;[InformationBase](#schema-informationbase)&gt; |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/user/custom/edit`

Edit Custom Data

編輯已有的 custom 數據

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CustomDataEdit](#schema-customdataedit) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/user/custom/batch-delete`

Batch Delete Custom Data

批量刪除 custom 數據

实现：[app/routes/user/custom_data.py](app/routes/user/custom_data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__user__submissions__BatchDeleteRequest](#schema-app__schemas__user__submissions__batchdeleterequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-4"></a>

## Notes

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/notes` | Get Notes |

### GET `/api/notes`

Get Notes

实现：[app/routes/notes.py](app/routes/notes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string | default="" | 搜索 IPA 或注释 |
| `search_fields` | query | 否 | array&lt;string&gt; / null |  |  |
| `locations` | query | 否 | array&lt;string&gt; / null |  | 地点列表 |
| `regions` | query | 否 | array&lt;string&gt; / null |  | 分区列表 |
| `region_mode` | query | 否 | string | default="yindian" | 分区模式: yindian/map |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [NotesSearchResponse](#schema-notessearchresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-5"></a>

## toponyms

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/toponyms/points` | Get Toponym Points |
| GET | `/api/toponyms/search` | Search Toponym Records |
| GET | `/api/toponyms/names` | Get Toponym Names |
| GET | `/api/toponyms/details` | Get Toponym Details |
| GET | `/api/toponyms/divisions` | Get Toponym Divisions |

### GET `/api/toponyms/points`

Get Toponym Points

实现：[app/routes/toponyms.py](app/routes/toponyms.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  | 地名查询文本 |
| `match_mode` | query | 否 | string | default="prefix"; enum=["prefix", "suffix", "exact", "contains"] | prefix, suffix, exact, contains |
| `bbox` | query | 否 | string / null |  | 可选: minLng,minLat,maxLng,maxLat |
| `zoom` | query | 否 | integer / null |  | 可选: 前端地图缩放级别，后端仅校验 |
| `limit` | query | 否 | integer | default=5000; minimum=0; maximum=2000000 | 0 表示不限制 |
| `place_type_code` | query | 否 | array&lt;string&gt; |  | 默认 22200 自然村/农村居民点，可逗号分隔或重复传参 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ToponymPointsResponse](#schema-toponympointsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/toponyms/search`

Search Toponym Records

实现：[app/routes/toponyms.py](app/routes/toponyms.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  | 地名查询文本 |
| `match_mode` | query | 否 | string | default="prefix"; enum=["prefix", "suffix", "exact", "contains"] | prefix, suffix, exact, contains |
| `bbox` | query | 否 | string / null |  | 可选: minLng,minLat,maxLng,maxLat；仅过滤 single 点位 |
| `limit` | query | 否 | integer | default=100; minimum=0; maximum=2000000 | 0 表示不限制 |
| `place_type_code` | query | 否 | array&lt;string&gt; |  | 默认 22200 自然村/农村居民点，可逗号分隔或重复传参 |
| `area_code` | query | 否 | string / null |  | 可选行政区划 code |
| `area_scope` | query | 否 | string | default="descendants"; enum=["descendants", "exact"] | descendants 匹配下级，exact 仅精确匹配 area_code |
| `include_area_code` | query | 否 | boolean | default=false | true 时额外返回 area_code |
| `include_place_type_code` | query | 否 | boolean | default=false | true 时额外返回 place_type_code |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ToponymSearchResponse](#schema-toponymsearchresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/toponyms/names`

Get Toponym Names

实现：[app/routes/toponyms.py](app/routes/toponyms.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 是 | string | minLength=1 |  |
| `match_mode` | query | 否 | string | default="prefix"; enum=["prefix", "suffix", "exact", "contains"] | prefix, suffix, exact, contains |
| `limit` | query | 否 | integer | default=20; minimum=0; maximum=2000000 |  |
| `bbox` | query | 否 | string / null |  | 可选: minLng,minLat,maxLng,maxLat |
| `include_division_tree` | query | 否 | boolean | default=false | true 时返回行政区划层级树 |
| `parent_path` | query | 否 | array&lt;string&gt; / null |  | 懒加载树节点路径，可重复传参 |
| `page` | query | 否 | integer | default=1; minimum=1 | 懒加载叶子名称页码 |
| `page_size` | query | 否 | integer | default=100; minimum=1; maximum=500 | 懒加载叶子名称每页数量 |
| `place_type_code` | query | 否 | array&lt;string&gt; |  | 默认 22200 自然村/农村居民点，可逗号分隔或重复传参 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ToponymNamesResponse](#schema-toponymnamesresponse) / [ToponymNameTreeResponse](#schema-toponymnametreeresponse) / [ToponymNameTreeLazyFallbackResponse](#schema-toponymnametreelazyfallbackresponse) / [ToponymNameTreeLazyChildrenResponse](#schema-toponymnametreelazychildrenresponse) / [ToponymNameTreeLazyNamesResponse](#schema-toponymnametreelazynamesresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/toponyms/details`

Get Toponym Details

实现：[app/routes/toponyms.py](app/routes/toponyms.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `ids` | query | 是 | array&lt;string&gt; | minItems=1 | 逗号分隔或重复传参，最多 10 个 ID |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ToponymDetailsResponse](#schema-toponymdetailsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/toponyms/divisions`

Get Toponym Divisions

实现：[app/routes/toponyms.py](app/routes/toponyms.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `parent_code` | query | 否 | string | default="100000"; minLength=1 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ToponymDivisionsResponse](#schema-toponymdivisionsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-6"></a>

## html

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/` | Root Index |
| GET | `/intro` | Serve Base |
| GET | `/intro/{_}` | Serve Nested |
| GET | `/menu` | Serve Base |
| GET | `/menu/{_}` | Serve Nested |
| GET | `/explore` | Serve Base |
| GET | `/explore/{_}` | Serve Nested |
| GET | `/villagesML` | Serve Base |
| GET | `/villagesML/{_}` | Serve Nested |
| GET | `/auth` | Serve Base |
| GET | `/auth/{_}` | Serve Nested |
| GET | `/detail` | Detail Index |
| GET | `/admin` | Admin Index |

### GET `/`

Root Index

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/intro`

Serve Base

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/intro/{_}`

Serve Nested

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `_` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/menu`

Serve Base

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/menu/{_}`

Serve Nested

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `_` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/explore`

Serve Base

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/explore/{_}`

Serve Nested

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `_` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/villagesML`

Serve Base

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/villagesML/{_}`

Serve Nested

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `_` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/auth`

Serve Base

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/auth/{_}`

Serve Nested

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `_` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/detail`

Detail Index

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin`

Admin Index

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `text/html` / string |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-7"></a>

## 其他

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/__ping` | Ping |

### GET `/__ping`

Ping

实现：[app/routes/index.py](app/routes/index.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-8"></a>

## Authentication

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/refresh` | Refresh |
| GET | `/api/auth/verify-email` | Verify Email |
| GET | `/api/auth/me` | Me |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/report-online-time` | Report Online Time |
| PUT | `/api/auth/updateProfile` | Update Profile |
| GET | `/api/auth/leaderboard` | Get Leaderboard |

### POST `/api/auth/register`

Register

实现：[app/routes/auth.py](app/routes/auth.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [UserCreate](#schema-usercreate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserResponse](#schema-userresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/auth/login`

Login

实现：[app/routes/auth.py](app/routes/auth.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/x-www-form-urlencoded` | [Body_login_api_auth_login_post](#schema-body_login_api_auth_login_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [TokenPair](#schema-tokenpair) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/auth/refresh`

Refresh

Exchange refresh token for new access + refresh token pair.
Implements token rotation for security.

实现：[app/routes/auth.py](app/routes/auth.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [Body_refresh_api_auth_refresh_post](#schema-body_refresh_api_auth_refresh_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [TokenPair](#schema-tokenpair) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/auth/verify-email`

Verify Email

暫時不用這個函數。
:param token:
:param db:
:return:

实现：[app/routes/auth.py](app/routes/auth.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `token` | query | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/auth/me`

Me

实现：[app/routes/auth.py](app/routes/auth.py)。

OpenAPI security：`[{"OAuth2PasswordBearer": []}]`。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserMeResponse](#schema-usermeresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/auth/logout`

Logout

Logout user and revoke tokens

实现：[app/routes/auth.py](app/routes/auth.py)。

OpenAPI security：`[{"OAuth2PasswordBearer": []}]`。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：可选。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [Body_logout_api_auth_logout_post](#schema-body_logout_api_auth_logout_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [LogoutResponse](#schema-logoutresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/auth/report-online-time`

Report Online Time

实现：[app/routes/auth.py](app/routes/auth.py)。

OpenAPI security：`[{"OAuth2PasswordBearer": []}]`。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [Body_report_online_time_api_auth_report_online_time_post](#schema-body_report_online_time_api_auth_report_online_time_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/api/auth/updateProfile`

Update Profile

实现：[app/routes/auth.py](app/routes/auth.py)。

OpenAPI security：`[{"OAuth2PasswordBearer": []}]`。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：可选。

| Content-Type | Schema |
| --- | --- |
| `application/x-www-form-urlencoded` | [Body_update_profile_api_auth_updateProfile_put](#schema-body_update_profile_api_auth_updateprofile_put) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/auth/leaderboard`

Get Leaderboard

实现：[app/routes/auth.py](app/routes/auth.py)。

OpenAPI security：`[{"OAuth2PasswordBearer": []}]`。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [app__schemas__auth__user__LeaderboardResponse](#schema-app__schemas__auth__user__leaderboardresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-9"></a>

## Vocabulary

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/vocabulary/search/entries` | Get Vocabulary Items |
| GET | `/api/vocabulary/search/map-points` | Get Vocabulary Map Points |
| GET | `/api/vocabulary/search/standard-words` | Get Vocabulary Standard Words |
| GET | `/api/vocabulary/search/map-items` | Get Vocabulary Map Items |
| GET | `/api/vocabulary/search/location-options` | Get Vocabulary Location Options |
| GET | `/api/vocabulary/locations` | Get Vocabulary Locations |
| PATCH | `/api/vocabulary/locations/{location_name}` | Update Vocabulary Location |
| DELETE | `/api/vocabulary/locations/{location_name}` | Delete Vocabulary Location |
| POST | `/api/vocabulary/locations/transfer` | Transfer Vocabulary Location |
| GET | `/api/vocabulary/locations/{location_name}/export` | Export Vocabulary Location |
| GET | `/api/vocabulary/logs` | Get Vocabulary Logs |
| POST | `/api/vocabulary/imports` | Upload Vocabulary |
| POST | `/api/vocabulary/imports/preview` | Preview Vocabulary Upload Endpoint |
| GET | `/api/vocabulary/me` | Get My Vocabulary Context |
| GET | `/api/vocabulary/admin/permissions` | Get Vocabulary Permissions |
| GET | `/api/vocabulary/admin/permissions/{user_id}` | Get Vocabulary Permission |
| PUT | `/api/vocabulary/admin/permissions/{user_id}` | Set Vocabulary Permission |

### GET `/api/vocabulary/search/entries`

Get Vocabulary Items

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  |  |
| `search_fields` | query | 否 | array&lt;string&gt; / null |  |  |
| `locations` | query | 否 | array&lt;string&gt; / null |  |  |
| `province` | query | 否 | string / null |  |  |
| `city` | query | 否 | string / null |  |  |
| `standard_words` | query | 否 | array&lt;string&gt; / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyItemsResponse](#schema-vocabularyitemsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/search/map-points`

Get Vocabulary Map Points

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  |  |
| `search_fields` | query | 否 | array&lt;string&gt; / null |  |  |
| `locations` | query | 否 | array&lt;string&gt; / null |  |  |
| `province` | query | 否 | string / null |  |  |
| `city` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyMapPointsResponse](#schema-vocabularymappointsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/search/standard-words`

Get Vocabulary Standard Words

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `q` | query | 否 | string / null |  |  |
| `search_fields` | query | 否 | array&lt;string&gt; / null |  |  |
| `locations` | query | 否 | array&lt;string&gt; / null |  |  |
| `province` | query | 否 | string / null |  |  |
| `city` | query | 否 | string / null |  |  |
| `limit` | query | 否 | integer / null | default=100 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyStandardWordsResponse](#schema-vocabularystandardwordsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/search/map-items`

Get Vocabulary Map Items

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `standard_words` | query | 否 | array&lt;string&gt; / null |  |  |
| `standard_word_key` | query | 否 | string / null |  |  |
| `q` | query | 否 | string / null |  |  |
| `search_fields` | query | 否 | array&lt;string&gt; / null |  |  |
| `locations` | query | 否 | array&lt;string&gt; / null |  |  |
| `province` | query | 否 | string / null |  |  |
| `city` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyMapItemsResponse](#schema-vocabularymapitemsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/search/location-options`

Get Vocabulary Location Options

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyLocationOptionsResponse](#schema-vocabularylocationoptionsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/locations`

Get Vocabulary Locations

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | query | 否 | integer / null |  |  |
| `username` | query | 否 | string / null |  |  |
| `location_name` | query | 否 | string / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyLocationsResponse](#schema-vocabularylocationsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PATCH `/api/vocabulary/locations/{location_name}`

Update Vocabulary Location

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `location_name` | path | 是 | string |  |  |
| `user_id` | query | 否 | integer / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [VocabularyLocationUpdateRequest](#schema-vocabularylocationupdaterequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyLocationResponse](#schema-vocabularylocationresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/vocabulary/locations/{location_name}`

Delete Vocabulary Location

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `location_name` | path | 是 | string |  |  |
| `user_id` | query | 否 | integer / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/locations/transfer`

Transfer Vocabulary Location

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [VocabularyLocationTransferRequest](#schema-vocabularylocationtransferrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyLocationTransferResponse](#schema-vocabularylocationtransferresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/locations/{location_name}/export`

Export Vocabulary Location

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `location_name` | path | 是 | string |  |  |
| `user_id` | query | 否 | integer / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/logs`

Get Vocabulary Logs

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | query | 否 | integer / null |  |  |
| `permission_level` | query | 否 | string / null |  |  |
| `source` | query | 否 | string / null |  |  |
| `action` | query | 否 | string / null |  |  |
| `table_name` | query | 否 | string / null |  |  |
| `status` | query | 否 | string / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyLogsResponse](#schema-vocabularylogsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/imports`

Upload Vocabulary

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_upload_vocabulary_api_vocabulary_imports_post](#schema-body_upload_vocabulary_api_vocabulary_imports_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyUploadResponse](#schema-vocabularyuploadresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/imports/preview`

Preview Vocabulary Upload Endpoint

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_preview_vocabulary_upload_endpoint_api_vocabulary_imports_preview_post](#schema-body_preview_vocabulary_upload_endpoint_api_vocabulary_imports_preview_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyUploadPreviewResponse](#schema-vocabularyuploadpreviewresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/me`

Get My Vocabulary Context

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyMeResponse](#schema-vocabularymeresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/admin/permissions`

Get Vocabulary Permissions

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyPermissionsResponse](#schema-vocabularypermissionsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/admin/permissions/{user_id}`

Get Vocabulary Permission

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyPermissionResponse](#schema-vocabularypermissionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/api/vocabulary/admin/permissions/{user_id}`

Set Vocabulary Permission

实现：[app/routes/vocabulary.py](app/routes/vocabulary.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [VocabularyPermissionUpdateRequest](#schema-vocabularypermissionupdaterequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VocabularyPermissionResponse](#schema-vocabularypermissionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-10"></a>

## Vocabulary SQL

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/vocabulary/sql/query` | Query Table |
| GET | `/api/vocabulary/sql/query/columns` | Get Column Info |
| GET | `/api/vocabulary/sql/query/count` | Get Table Count |
| GET | `/api/vocabulary/sql/distinct/{table_name}/{column}` | Get Distinct Path Values |
| POST | `/api/vocabulary/sql/distinct-query` | Get Distinct Query Values |
| POST | `/api/vocabulary/sql/mutate` | Mutate Table |
| POST | `/api/vocabulary/sql/batch-mutate` | Batch Mutate Table |
| POST | `/api/vocabulary/sql/batch-replace-preview` | Batch Replace Preview |
| POST | `/api/vocabulary/sql/batch-replace-execute` | Batch Replace Execute |

### POST `/api/vocabulary/sql/query`

Query Table

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__vocabulary_sql__QueryParams](#schema-app__schemas__vocabulary_sql__queryparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/sql/query/columns`

Get Column Info

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `table_name` | query | 否 | string | default="vocabulary_entries" |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/sql/query/count`

Get Table Count

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `table_name` | query | 否 | string | default="vocabulary_entries" |  |
| `filter_column` | query | 否 | string / null |  |  |
| `filter_value` | query | 否 | string / null |  |  |
| `distinct_column` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/vocabulary/sql/distinct/{table_name}/{column}`

Get Distinct Path Values

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `table_name` | path | 是 | string |  |  |
| `column` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/sql/distinct-query`

Get Distinct Query Values

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__vocabulary_sql__DistinctQueryRequest](#schema-app__schemas__vocabulary_sql__distinctqueryrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/sql/mutate`

Mutate Table

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__vocabulary_sql__MutationParams](#schema-app__schemas__vocabulary_sql__mutationparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/sql/batch-mutate`

Batch Mutate Table

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__vocabulary_sql__BatchMutationParams](#schema-app__schemas__vocabulary_sql__batchmutationparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/sql/batch-replace-preview`

Batch Replace Preview

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__vocabulary_sql__BatchReplacePreviewParams](#schema-app__schemas__vocabulary_sql__batchreplacepreviewparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/vocabulary/sql/batch-replace-execute`

Batch Replace Execute

实现：[app/routes/vocabulary_sql.py](app/routes/vocabulary_sql.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__schemas__vocabulary_sql__BatchReplaceExecuteParams](#schema-app__schemas__vocabulary_sql__batchreplaceexecuteparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-11"></a>

## admin users

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/users/list` | Get Users List |
| GET | `/admin/users/all` | Get Users |
| GET | `/admin/users/single` | Get User |
| POST | `/admin/users/create` | Create User |
| PUT | `/admin/users/update` | Update User |
| DELETE | `/admin/users/delete` | Delete User |
| PUT | `/admin/users/password` | Update Password |
| PUT | `/admin/users/let_admin` | Let Admin |
| GET | `/admin/permissions/permissions` | Get All Permissions |
| GET | `/admin/permissions/permissions/user/{user_id}` | Get User Permissions |

### GET `/admin/users/list`

Get Users List

获取用户列表（轻量级）
仅返回用户名、邮箱和角色，适合用于下拉列表、表格等场景

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[UserListItem](#schema-userlistitem)&gt; |

### GET `/admin/users/all`

Get Users

获取所有用户（完整信息）

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[UserResponse](#schema-userresponse)&gt; |

### GET `/admin/users/single`

Get User

通过用户名或邮箱查找用户

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserResponse](#schema-userresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/users/create`

Create User

创建新用户

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [AdminCreate](#schema-admincreate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserResponse](#schema-userresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/admin/users/update`

Update User

更新用户信息

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [UserUpdateSchema](#schema-userupdateschema) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserUpdateSchema](#schema-userupdateschema) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/admin/users/delete`

Delete User

删除用户

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserResponse](#schema-userresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/admin/users/password`

Update Password

更新用户密码

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [UpdatePassword](#schema-updatepassword) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserUpdateSchema](#schema-userupdateschema) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/admin/users/let_admin`

Let Admin

更新用户角色

实现：[app/routes/admin/users/crud.py](app/routes/admin/users/crud.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [LetAdmin](#schema-letadmin) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserUpdateSchema](#schema-userupdateschema) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/permissions/permissions`

Get All Permissions

获取所有权限记录

权限要求：管理员

实现：[app/routes/admin/users/permissions.py](app/routes/admin/users/permissions.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[PermissionResponse](#schema-permissionresponse)&gt; |

### GET `/admin/permissions/permissions/user/{user_id}`

Get User Permissions

获取特定用户的所有权限

权限要求：管理员

实现：[app/routes/admin/users/permissions.py](app/routes/admin/users/permissions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[PermissionResponse](#schema-permissionresponse)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-12"></a>

## admin stats

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/stats/login-history` | Get User Login History |
| GET | `/admin/stats/stats` | Get User Stats |

### GET `/admin/stats/login-history`

Get User Login History

实现：[app/routes/admin/users/stats.py](app/routes/admin/users/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/stats/stats`

Get User Stats

实现：[app/routes/admin/users/stats.py](app/routes/admin/users/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-13"></a>

## admin user-sessions

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/user-sessions/list` | List Sessions |
| GET | `/admin/user-sessions/stats` | Get Session Stats |
| POST | `/admin/user-sessions/revoke-bulk` | Revoke Sessions Bulk |
| POST | `/admin/user-sessions/revoke-user/{user_id}` | Revoke User Sessions |
| GET | `/admin/user-sessions/user/{user_id}/history` | Get User Session History |
| GET | `/admin/user-sessions/online-users` | Get Online Users |
| GET | `/admin/user-sessions/analytics` | Get Analytics |
| GET | `/admin/user-sessions/{session_id}` | Get Session Detail |
| GET | `/admin/user-sessions/{session_id}/activity` | Get Session Activity |
| POST | `/admin/user-sessions/{session_id}/revoke` | Revoke Session |
| POST | `/admin/user-sessions/{session_id}/flag` | Flag Session |

### GET `/admin/user-sessions/list`

List Sessions

列出会话（高级过滤）

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | query | 否 | integer / null |  | 按用户 ID 筛选 |
| `username` | query | 否 | string / null |  | 按用户名筛选 |
| `is_suspicious` | query | 否 | boolean / null |  | 筛选可疑会话 |
| `revoked` | query | 否 | boolean / null |  | 筛选撤销状态 |
| `ip_address` | query | 否 | string / null |  | 按当前 IP 筛选 |
| `created_after` | query | 否 | string (date-time) / null |  | 创建时间范围（起） |
| `created_before` | query | 否 | string (date-time) / null |  | 创建时间范围（止） |
| `sort_by` | query | 否 | string | default="created_at" | 排序字段 |
| `sort_order` | query | 否 | string | default="desc" | 排序方向 (asc/desc) |
| `skip` | query | 否 | integer | default=0; minimum=0 | 分页偏移 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=500 | 分页限制 |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SessionListResponse](#schema-sessionlistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/user-sessions/stats`

Get Session Stats

会话统计仪表板

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `start_date` | query | 否 | string (date-time) / null |  | 统计开始时间 |
| `end_date` | query | 否 | string (date-time) / null |  | 统计结束时间 |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SessionStatsResponse](#schema-sessionstatsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/user-sessions/revoke-bulk`

Revoke Sessions Bulk

批量撤销会话

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `reason` | query | 否 | string / null |  |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | array&lt;integer&gt; |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [RevokeBulkResponse](#schema-revokebulkresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/user-sessions/revoke-user/{user_id}`

Revoke User Sessions

撤销用户的所有会话

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |
| `reason` | query | 否 | string / null |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/user-sessions/user/{user_id}/history`

Get User Session History

获取用户的会话历史

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |
| `skip` | query | 否 | integer | default=0; minimum=0 |  |
| `limit` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SessionListResponse](#schema-sessionlistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/user-sessions/online-users`

Get Online Users

获取实时在线用户列表

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `threshold_minutes` | query | 否 | integer | default=5; minimum=1; maximum=120 | 在线判断阈值（分钟） |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [OnlineUsersResponse](#schema-onlineusersresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/user-sessions/analytics`

Get Analytics

会话分析（时间序列、地理分布、设备分布）

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `days` | query | 否 | integer | default=30; minimum=1; maximum=1000 | 分析天数 |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AnalyticsResponse](#schema-analyticsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/user-sessions/{session_id}`

Get Session Detail

获取会话详情

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `session_id` | path | 是 | integer |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SessionDetailResponse](#schema-sessiondetailresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/user-sessions/{session_id}/activity`

Get Session Activity

获取会话活动时间线

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `session_id` | path | 是 | integer |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SessionActivityResponse](#schema-sessionactivityresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/user-sessions/{session_id}/revoke`

Revoke Session

撤销单个会话

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `session_id` | path | 是 | integer |  |  |
| `reason` | query | 否 | string | default="admin_action"; maxLength=100 |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [RevokeSessionResponse](#schema-revokesessionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/user-sessions/{session_id}/flag`

Flag Session

标记会话为可疑/正常

实现：[app/routes/admin/sessions/management.py](app/routes/admin/sessions/management.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `session_id` | path | 是 | integer |  |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FlagSessionRequest](#schema-flagsessionrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SessionDetailResponse](#schema-sessiondetailresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-14"></a>

## admin sessions (legacy)

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/sessions/active` | Get Active Sessions |
| GET | `/admin/sessions/user/{user_id}` | Get User Sessions |
| POST | `/admin/sessions/revoke/{token_id}` | Revoke Session |
| POST | `/admin/sessions/revoke-user/{user_id}` | Revoke All User Sessions |
| POST | `/admin/sessions/cleanup-expired` | Cleanup Expired Tokens |
| GET | `/admin/sessions/stats` | Get Session Stats |

### GET `/admin/sessions/active`

Get Active Sessions

Get all active sessions (refresh tokens that are not revoked and not expired)

Query params:
- user_id: Filter by specific user (optional)
- skip: Pagination offset
- limit: Max results (default 100)

实现：[app/routes/admin/sessions/legacy.py](app/routes/admin/sessions/legacy.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | query | 否 | integer |  |  |
| `skip` | query | 否 | integer | default=0 |  |
| `limit` | query | 否 | integer | default=100 |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/sessions/user/{user_id}`

Get User Sessions

Get all sessions for specific user

实现：[app/routes/admin/sessions/legacy.py](app/routes/admin/sessions/legacy.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/sessions/revoke/{token_id}`

Revoke Session

此操作已在 OpenAPI 标记为 deprecated。

Legacy endpoint: revoke a refresh token only.

Note: the current access token can still remain valid until its normal
expiry. Prefer /admin/user-sessions/{session_id}/revoke for immediate
session-level revocation.

实现：[app/routes/admin/sessions/legacy.py](app/routes/admin/sessions/legacy.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `token_id` | path | 是 | integer |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/sessions/revoke-user/{user_id}`

Revoke All User Sessions

Legacy endpoint: revoke all refresh tokens for a user.

Existing access tokens can still remain valid until they expire naturally.
Prefer /admin/user-sessions/revoke-user/{user_id} for immediate
session-level revocation.

实现：[app/routes/admin/sessions/legacy.py](app/routes/admin/sessions/legacy.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_id` | path | 是 | integer |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/sessions/cleanup-expired`

Cleanup Expired Tokens

Delete expired and revoked tokens from database (cleanup task)

实现：[app/routes/admin/sessions/legacy.py](app/routes/admin/sessions/legacy.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### GET `/admin/sessions/stats`

Get Session Stats

Get overall session statistics

实现：[app/routes/admin/sessions/legacy.py](app/routes/admin/sessions/legacy.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

<a id="group-15"></a>

## admin submissions

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/custom/all` | Get Informations |
| GET | `/admin/custom/num` | Get User Data Count |
| GET | `/admin/custom/user` | Get Custom Peruser |
| POST | `/admin/custom/selected` | Selected Custom |
| DELETE | `/admin/custom/delete` | Delete Custom By Admin |
| POST | `/admin/custom/create` | Create Custom By Admin |
| GET | `/admin/custom-regions/all` | Get All Regions |
| GET | `/admin/custom-regions/user` | Get Regions By User |
| GET | `/admin/custom-regions/count` | Get Region Counts |
| GET | `/admin/custom-regions/stats` | Get Statistics |
| POST | `/admin/custom-regions/create` | Create Region |
| PUT | `/admin/custom-regions/update` | Update Region |
| DELETE | `/admin/custom-regions/delete` | Delete Region |
| POST | `/admin/custom-regions/batch-delete` | Batch Delete Regions |

### GET `/admin/custom/all`

Get Informations

获取所有用户的custom数据

实现：[app/routes/admin/submissions/data.py](app/routes/admin/submissions/data.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[InformationBase](#schema-informationbase)&gt; |

### GET `/admin/custom/num`

Get User Data Count

获取每个用户的数据数量

实现：[app/routes/admin/submissions/data.py](app/routes/admin/submissions/data.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### GET `/admin/custom/user`

Get Custom Peruser

根据用户名查询用户数据

实现：[app/routes/admin/submissions/data.py](app/routes/admin/submissions/data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  | 用戶名 |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[InformationBase](#schema-informationbase)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/custom/selected`

Selected Custom

根据条件查询custom数据

实现：[app/routes/admin/submissions/data.py](app/routes/admin/submissions/data.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | array&lt;[EditRequest](#schema-editrequest)&gt; |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[InformationBase](#schema-informationbase)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/admin/custom/delete`

Delete Custom By Admin

管理员删除custom数据

实现：[app/routes/admin/submissions/data.py](app/routes/admin/submissions/data.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | array&lt;[EditRequest](#schema-editrequest)&gt; |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[InformationBase](#schema-informationbase)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/custom/create`

Create Custom By Admin

管理员创建custom数据

实现：[app/routes/admin/submissions/data.py](app/routes/admin/submissions/data.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | array&lt;[InformationBase](#schema-informationbase)&gt; |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[InformationBase](#schema-informationbase)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/custom-regions/all`

Get All Regions

获取所有用户的自定义区域（分页）

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `skip` | query | 否 | integer | default=0; minimum=0 |  |
| `limit` | query | 否 | integer | default=50; minimum=1; maximum=500 |  |
| `search` | query | 否 | string / null |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/custom-regions/user`

Get Regions By User

按用户名查询区域

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `username` | query | 是 | string |  | 用户名 |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/custom-regions/count`

Get Region Counts

获取每个用户的区域数量

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### GET `/admin/custom-regions/stats`

Get Statistics

获取区域统计信息

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### POST `/admin/custom-regions/create`

Create Region

管理员为任意用户创建区域

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [AdminRegionCreate](#schema-adminregioncreate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/admin/custom-regions/update`

Update Region

管理员更新任意用户的区域

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [AdminRegionUpdate](#schema-adminregionupdate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/admin/custom-regions/delete`

Delete Region

管理员删除任意用户的区域

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [AdminRegionDelete](#schema-adminregiondelete) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/custom-regions/batch-delete`

Batch Delete Regions

批量删除区域

实现：[app/routes/admin/submissions/regions.py](app/routes/admin/submissions/regions.py)。

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | array&lt;[AdminRegionDelete](#schema-adminregiondelete)&gt; |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-16"></a>

## admin suggestions

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/suggestions` | List Suggestions |
| PATCH | `/admin/suggestions/{suggestion_id}` | Update Suggestion |

### GET `/admin/suggestions`

List Suggestions

实现：[app/routes/admin/suggestions.py](app/routes/admin/suggestions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `status` | query | 否 | string / null |  |  |
| `category` | query | 否 | string / null |  |  |
| `user_id` | query | 否 | integer / null |  |  |
| `q` | query | 否 | string / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AdminSuggestionListResponse](#schema-adminsuggestionlistresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PATCH `/admin/suggestions/{suggestion_id}`

Update Suggestion

实现：[app/routes/admin/suggestions.py](app/routes/admin/suggestions.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `suggestion_id` | path | 是 | integer |  |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [AdminSuggestionUpdate](#schema-adminsuggestionupdate) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AdminSuggestionItem](#schema-adminsuggestionitem) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-17"></a>

## admin analytics

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/admin/analytics/user-segments` | Api User Segments |
| GET | `/admin/analytics/rfm-analysis` | Api Rfm Analysis |
| GET | `/admin/analytics/anomaly-detection` | Api Anomaly Detection |
| GET | `/admin/analytics/api-diversity` | Api Diversity Analysis |
| GET | `/admin/analytics/user-preferences` | Api User Preferences |
| GET | `/admin/analytics/user-growth` | Api User Growth |
| GET | `/admin/analytics/dashboard` | Api Dashboard |
| GET | `/admin/analytics/recent-trends` | Api Recent Trends |
| GET | `/admin/analytics/api-performance` | Api Performance Analysis |
| GET | `/admin/analytics/geo-distribution` | Api Geo Distribution |
| GET | `/admin/analytics/device-distribution` | Api Device Distribution |
| GET | `/admin/analytics/user-api-matrix` | Api User Api Matrix |
| GET | `/admin/analytics/export` | Api Export Data |
| GET | `/admin/api-usage/api-summary` | Get Api Usage Summary |
| GET | `/admin/api-usage/api-detail` | Get User Api Usage |
| GET | `/admin/api-usage/api-usage` | Get All Api Usage |
| GET | `/admin/leaderboard/rankings` | Get Rankings |
| GET | `/admin/leaderboard/available-apis` | Get Available Apis |
| GET | `/admin/login-logs/success-login-logs` | Get Login Logs |
| GET | `/admin/login-logs/failed-login-logs` | Get Failed Login Logs |

### GET `/admin/analytics/user-segments`

Api User Segments

Get user activity segmentation.

Segments users into: super_active, active, regular, low_active, dormant

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `include_users` | query | 否 | boolean | default=false | Include user details |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserSegmentsResponse](#schema-usersegmentsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/rfm-analysis`

Api Rfm Analysis

Perform RFM (Recency, Frequency, Monetary) user value analysis.

Segments users into: VIP, Potential, New, Dormant High Value, Low Value, Others

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `include_users` | query | 否 | boolean | default=false | Include user details |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [RFMAnalysisResponse](#schema-rfmanalysisresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/anomaly-detection`

Api Anomaly Detection

Detect anomalous user behavior patterns.

Detection types:
- high_frequency: Users with calls > mean + 3*std
- high_traffic: Users with traffic > mean + 3*std
- single_api: Users with 90%+ calls on single API
- new_user_spike: Users registered < 7 days with > 100 calls
- all: All detection types

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `detection_type` | query | 否 | string | default="all" | Type: all, high_frequency, high_traffic, single_api, new_user_spike |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AnomalyDetectionResponse](#schema-anomalydetectionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/api-diversity`

Api Diversity Analysis

Analyze API usage diversity for each user.

Returns diversity scores and classifies users as explorers or focused users.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `sort_by` | query | 否 | string | default="diversity" | Sort by: diversity or calls |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [APIDiversityResponse](#schema-apidiversityresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/user-preferences`

Api User Preferences

Analyze user preferences based on API usage patterns.

Returns detailed data for frontend to generate labels.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `user_ids` | query | 否 | string / null |  | Comma-separated user IDs |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserPreferencesResponse](#schema-userpreferencesresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/user-growth`

Api User Growth

Analyze user growth statistics by month.

Returns monthly new users, cumulative users, and growth rates.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `months` | query | 否 | integer | default=12 | Number of recent months to analyze |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserGrowthResponse](#schema-usergrowthresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/dashboard`

Api Dashboard

Get comprehensive system overview dashboard.

Includes:
- Total users, active users (7d/30d)
- Total calls and traffic
- Top APIs
- User distribution by activity level
- Monthly new users trend

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [DashboardResponse](#schema-dashboardresponse) |

### GET `/admin/analytics/recent-trends`

Api Recent Trends

Analyze recent API usage trends (last 7 days).

Returns daily/hourly call counts, active users, and performance metrics.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `granularity` | query | 否 | string | default="day" | Granularity: day or hour |
| `days` | query | 否 | integer | default=7 | Number of days to analyze (max 7) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [RecentTrendsResponse](#schema-recenttrendsresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/api-performance`

Api Performance Analysis

Analyze API performance metrics.

Returns average response time, percentiles (P50/P95/P99), and slow request ratios.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `api_path` | query | 否 | string / null |  | Specific API path to analyze |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [APIPerformanceResponse](#schema-apiperformanceresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/geo-distribution`

Api Geo Distribution

Analyze geographic distribution of users.

Uses GeoLite2 database to resolve IP addresses to locations.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `level` | query | 否 | string | default="country" | Level: country or city |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [GeoDistributionResponse](#schema-geodistributionresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/device-distribution`

Api Device Distribution

Analyze user device distribution.

Returns device types (desktop/mobile/tablet), browsers, and operating systems.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [DeviceDistributionResponse](#schema-devicedistributionresponse) |

### GET `/admin/analytics/user-api-matrix`

Api User Api Matrix

Get user x API path matrix for clustering analysis.

Reads from the pre-aggregated api_usage_summary table (cumulative totals).
Returns users[], paths[], and matrix[] with index-based references.
Use for heatmap and scatter-plot visualizations of user/API usage patterns.

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `min_calls` | query | 否 | integer | default=1; minimum=1 | Filter out (user, path) pairs below this call count |
| `exclude_paths` | query | 否 | string / null |  | Comma-separated paths to exclude, trailing * for prefix match |
| `max_users` | query | 否 | integer | default=500; minimum=1; maximum=2000 | Max top users to return |
| `max_paths` | query | 否 | integer | default=100; minimum=1; maximum=500 | Max top paths to return |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UserApiMatrixResponse](#schema-userapimatrixresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/analytics/export`

Api Export Data

Export analytics data in various formats.

Supported formats: CSV, Excel (XLSX), JSON

实现：[app/routes/admin/analytics/overview.py](app/routes/admin/analytics/overview.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `export_type` | query | 是 | string |  | Type: user-segments, rfm, anomalies, diversity, preferences, growth, dashboard, trends, performance, geo, devices |
| `format` | query | 否 | string | default="csv" | Format: csv, xlsx, json |
| `flatten` | query | 否 | boolean | default=false | Flatten nested structures for CSV/Excel |
| `include_users` | query | 否 | boolean | default=false | Include user details (where applicable) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/api-usage/api-summary`

Get Api Usage Summary

获取用户的API使用摘要

实现：[app/routes/admin/analytics/api_usage.py](app/routes/admin/analytics/api_usage.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/api-usage/api-detail`

Get User Api Usage

获取用户的API使用详情

实现：[app/routes/admin/analytics/api_usage.py](app/routes/admin/analytics/api_usage.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/api-usage/api-usage`

Get All Api Usage

获取 API 使用日志（增强版）

支持功能：
- 分页：skip, limit
- 搜索：search（匹配 user/ip/path/os/browser）
- 排序：sort_by, sort_order
- 统计：include_stats（返回全局统计信息）

实现：[app/routes/admin/analytics/api_usage.py](app/routes/admin/analytics/api_usage.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `skip` | query | 否 | integer | default=0; minimum=0 | 分页偏移 |
| `limit` | query | 否 | integer | default=50; minimum=1; maximum=500 | 分页限制 |
| `search` | query | 否 | string / null |  | 搜索关键词（匹配 user/ip/path/os/browser） |
| `sort_by` | query | 否 | string / null |  | 排序字段 |
| `sort_order` | query | 否 | string / null | default="desc" | 排序方向 |
| `include_stats` | query | 否 | boolean | default=false | 是否返回全局统计信息 |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/leaderboard/rankings`

Get Rankings

获取排行榜数据

- **ranking_type**: 排行类型
  - user_global: 用户全局排行（所有API汇总）
  - user_by_api: 单个API的用户排行
  - api: API端点排行
  - online_time: 在线时长排行
- **metric**: 指标（online_time类型不需要）
  - count: 调用次数
  - duration: 使用时长
  - upload: 上行流量
  - download: 下行流量
- **api_path**: API路径（仅user_by_api类型需要）
- **page**: 页码
- **page_size**: 每页数量

实现：[app/routes/admin/analytics/leaderboard.py](app/routes/admin/analytics/leaderboard.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `ranking_type` | query | 是 | string | enum=["user_global", "user_by_api", "api", "online_time"] |  |
| `metric` | query | 否 | string / null |  |  |
| `api_path` | query | 否 | string / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=20; minimum=1; maximum=500 |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [app__schemas__admin__analytics__LeaderboardResponse](#schema-app__schemas__admin__analytics__leaderboardresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/leaderboard/available-apis`

Get Available Apis

获取所有可用的API路径列表

返回系统中所有有使用记录的API路径，供前端构建下拉菜单使用。

实现：[app/routes/admin/analytics/leaderboard.py](app/routes/admin/analytics/leaderboard.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AvailableApisResponse](#schema-availableapisresponse) |

### GET `/admin/login-logs/success-login-logs`

Get Login Logs

获取成功登录日志

实现：[app/routes/admin/analytics/login_logs.py](app/routes/admin/analytics/login_logs.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/admin/login-logs/failed-login-logs`

Get Failed Login Logs

获取失败登录日志

实现：[app/routes/admin/analytics/login_logs.py](app/routes/admin/analytics/login_logs.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-18"></a>

## admin system

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/admin/cache/clear_dialect_cache` | Clear Dialect Cache Endpoint |
| POST | `/admin/cache/clear_redis_cache` | Clear Redis Cache Endpoint |
| POST | `/admin/cache/clear_all_cache` | Clear All Cache Endpoint |
| GET | `/admin/cache/cache_stats` | Cache Stats Endpoint |
| GET | `/admin/cache/cache_status` | Cache Status Endpoint |
| GET | `/admin/ip/{api_name}/{ip}` | Proxy Lookup |

### POST `/admin/cache/clear_dialect_cache`

Clear Dialect Cache Endpoint

清除方言数据缓存（仅管理员可用）

Args:
    db_path: 指定数据库路径，如果为None则清除所有缓存

Returns:
    清除结果

实现：[app/routes/admin/system/cache.py](app/routes/admin/system/cache.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `db_path` | query | 否 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/cache/clear_redis_cache`

Clear Redis Cache Endpoint

清除Redis缓存（仅管理员可用）

Args:
    pattern: 匹配模式，默认为 "*"（所有键）

Returns:
    清除结果

实现：[app/routes/admin/system/cache.py](app/routes/admin/system/cache.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `pattern` | query | 否 | string | default="*" |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/admin/cache/clear_all_cache`

Clear All Cache Endpoint

清除所有缓存（仅管理员可用）

Returns:
    清除结果

实现：[app/routes/admin/system/cache.py](app/routes/admin/system/cache.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### GET `/admin/cache/cache_stats`

Cache Stats Endpoint

查看所有缓存统计信息（仅管理员可用）

Returns:
    缓存统计信息（数量、内存占用）

实现：[app/routes/admin/system/cache.py](app/routes/admin/system/cache.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### GET `/admin/cache/cache_status`

Cache Status Endpoint

查看缓存状态（仅管理员可用）- 简化版本

Returns:
    缓存统计信息

实现：[app/routes/admin/system/cache.py](app/routes/admin/system/cache.py)。

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |

### GET `/admin/ip/{api_name}/{ip}`

Proxy Lookup

实现：[app/routes/admin/system/ip_lookup.py](app/routes/admin/system/ip_lookup.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `api_name` | path | 是 | string |  |  |
| `ip` | path | 是 | string |  |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-19"></a>

## 工具-Check

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/tools/check/upload` | Upload File |
| POST | `/api/tools/check/analyze` | Analyze File |
| POST | `/api/tools/check/analyze_async` | Start Analyze Async |
| GET | `/api/tools/check/progress/{task_id}` | Get Check Progress |
| POST | `/api/tools/check/execute` | Execute Commands |
| POST | `/api/tools/check/save` | Save Changes |
| GET | `/api/tools/check/download/{task_id}` | Download File |
| POST | `/api/tools/check/get_data` | Get Data |
| POST | `/api/tools/check/get_tone_stats` | Get Tone Stats |
| POST | `/api/tools/check/update_row` | Update Row |
| POST | `/api/tools/check/batch_delete` | Batch Delete |

### POST `/api/tools/check/upload`

Upload File

上传文件并创建任务

支持格式：
- Excel (.xlsx, .xls) - 标准音典格式或特殊格式
- Word (.doc, .docx) - 县志格式
- TSV (.tsv) - 制表符分隔文件

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_upload_file_api_tools_check_upload_post](#schema-body_upload_file_api_tools_check_upload_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UploadResponse](#schema-uploadresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/analyze`

Analyze File

分析文件并返回错误列表（使用原有的檢查資料格式函数）

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | query | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AnalysisResult](#schema-analysisresult) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/analyze_async`

Start Analyze Async

异步启动分析任务，供前端轮询进度使用。

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | query | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AnalyzeTaskResponse](#schema-analyzetaskresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/check/progress/{task_id}`

Get Check Progress

获取异步分析任务进度。

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [AnalyzeTaskResponse](#schema-analyzetaskresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/execute`

Execute Commands

統一執行指令 API
支持單個指令 (str) 或多個指令 (List[str])

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CommandRequest](#schema-commandrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CommandResponse](#schema-commandresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/save`

Save Changes

保存批量修改

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SaveChangesRequest](#schema-savechangesrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/check/download/{task_id}`

Download File

下载结果文件

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/get_data`

Get Data

获取表格数据（可选择只获取错误行或所有行）

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [GetDataRequest](#schema-getdatarequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/get_tone_stats`

Get Tone Stats

获取调值统计信息

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [GetDataRequest](#schema-getdatarequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/update_row`

Update Row

更新单行数据

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [UpdateRowRequest](#schema-updaterowrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/check/batch_delete`

Batch Delete

批量删除行

Args:
    request: 包含task_id和要删除的行号列表

Returns:
    删除结果

实现：[app/tools/check/check_routes.py](app/tools/check/check_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__tools__check__check_routes__BatchDeleteRequest](#schema-app__tools__check__check_routes__batchdeleterequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-20"></a>

## 工具-Jyut2IPA

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/tools/jyut2ipa/upload` | Upload File |
| POST | `/api/tools/jyut2ipa/process` | Process File |
| GET | `/api/tools/jyut2ipa/progress/{task_id}` | Get Progress |
| GET | `/api/tools/jyut2ipa/download/{task_id}` | Download Result |

### POST `/api/tools/jyut2ipa/upload`

Upload File

上传Excel文件

Args:
    file: 上传的Excel文件

Returns:
    任务ID和文件信息

实现：[app/tools/jyut2ipa/jyut2ipa_routes.py](app/tools/jyut2ipa/jyut2ipa_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_upload_file_api_tools_jyut2ipa_upload_post](#schema-body_upload_file_api_tools_jyut2ipa_upload_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/jyut2ipa/process`

Process File

开始处理文件（异步）

Args:
    request: 处理请求（包含task_id和可选的custom_rules）
    background_tasks: 后台任务

Returns:
    ProcessResponse: 处理状态

实现：[app/tools/jyut2ipa/jyut2ipa_routes.py](app/tools/jyut2ipa/jyut2ipa_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ProcessRequest](#schema-processrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ProcessResponse](#schema-processresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/jyut2ipa/progress/{task_id}`

Get Progress

获取处理进度

Args:
    task_id: 任务ID

Returns:
    ProcessResponse: 处理进度

实现：[app/tools/jyut2ipa/jyut2ipa_routes.py](app/tools/jyut2ipa/jyut2ipa_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ProcessResponse](#schema-processresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/jyut2ipa/download/{task_id}`

Download Result

下载结果文件 (使用流式传输)

实现：[app/tools/jyut2ipa/jyut2ipa_routes.py](app/tools/jyut2ipa/jyut2ipa_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-21"></a>

## 工具-Merge

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/tools/merge/upload_reference` | Upload Reference |
| POST | `/api/tools/merge/upload_files` | Upload Merge Files |
| POST | `/api/tools/merge/execute` | Execute Merge |
| GET | `/api/tools/merge/progress/{task_id}` | Get Merge Progress |
| GET | `/api/tools/merge/download/{task_id}` | Download Merge Result |

### POST `/api/tools/merge/upload_reference`

Upload Reference

上传参考表（使用原有的load_reference_file函数）

Args:
    file: 参考表文件

Returns:
    UploadReferenceResponse: 参考表信息

实现：[app/tools/merge/merge_routes.py](app/tools/merge/merge_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_upload_reference_api_tools_merge_upload_reference_post](#schema-body_upload_reference_api_tools_merge_upload_reference_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UploadReferenceResponse](#schema-uploadreferenceresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/merge/upload_files`

Upload Merge Files

上传待合并文件（可多选）

Args:
    task_id: 任务ID
    files: 待合并文件列表

Returns:
    UploadFilesResponse: 文件列表信息

实现：[app/tools/merge/merge_routes.py](app/tools/merge/merge_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_upload_merge_files_api_tools_merge_upload_files_post](#schema-body_upload_merge_files_api_tools_merge_upload_files_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [UploadFilesResponse](#schema-uploadfilesresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/merge/execute`

Execute Merge

开始合并（异步）- 使用原有的merge逻辑

Args:
    request: 合并请求
    background_tasks: 后台任务

Returns:
    MergeResponse: 合并状态

实现：[app/tools/merge/merge_routes.py](app/tools/merge/merge_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [MergeRequest](#schema-mergerequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [MergeResponse](#schema-mergeresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/merge/progress/{task_id}`

Get Merge Progress

获取合并进度

Args:
    task_id: 任务ID

Returns:
    MergeResponse: 合并进度

实现：[app/tools/merge/merge_routes.py](app/tools/merge/merge_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [MergeResponse](#schema-mergeresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/merge/download/{task_id}`

Download Merge Result

下载结果 (使用流式传输)

实现：[app/tools/merge/merge_routes.py](app/tools/merge/merge_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-22"></a>

## 工具-Praat

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/tools/praat/capabilities` | Get Capabilities |
| POST | `/api/tools/praat/uploads` | Create Upload |
| GET | `/api/tools/praat/uploads/progress/{task_id}` | Get Upload |
| DELETE | `/api/tools/praat/uploads/progress/{task_id}` | Delete Upload |
| GET | `/api/tools/praat/uploads/progress/{task_id}/audio` | Get Upload Audio |
| POST | `/api/tools/praat/jobs` | Create Job |
| GET | `/api/tools/praat/jobs/progress/{job_id}` | Get Job Status |
| DELETE | `/api/tools/praat/jobs/progress/{job_id}` | Cancel Job |
| GET | `/api/tools/praat/jobs/progress/{job_id}/result` | Get Job Result |

### GET `/api/tools/praat/capabilities`

Get Capabilities

Get backend capabilities.

Returns supported formats, modules, modes, and limits.

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/praat/uploads`

Create Upload

Upload and normalize audio file.

Note: Normalization is mandatory for Praat analysis.
All audio files are automatically normalized to 16kHz mono WAV.

Args:
    file: Audio file (any format)
    retain_original: Whether to keep original file (default: False)
    user: Current user (from ApiLimiter)

Returns:
    Task metadata with task_id

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `multipart/form-data` | [Body_create_upload_api_tools_praat_uploads_post](#schema-body_create_upload_api_tools_praat_uploads_post) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/praat/uploads/progress/{task_id}`

Get Upload

Get upload information.

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/tools/praat/uploads/progress/{task_id}`

Delete Upload

Delete task and associated files.

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/praat/uploads/progress/{task_id}/audio`

Get Upload Audio

Download normalized audio file.

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/praat/jobs`

Create Job

Create analysis job.

Args:
    request: Job creation request
    background_tasks: FastAPI background tasks
    user: Current user

Returns:
    Job ID and status

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [JobCreateRequest](#schema-jobcreaterequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [JobCreateResponse](#schema-jobcreateresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/praat/jobs/progress/{job_id}`

Get Job Status

Get job status.

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `job_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [JobStatusResponse](#schema-jobstatusresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/tools/praat/jobs/progress/{job_id}`

Cancel Job

Cancel job (best-effort).

Note: Already running jobs may not be immediately canceled.

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `job_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/praat/jobs/progress/{job_id}/result`

Get Job Result

Get job result.

Args:
    job_id: Job ID
    view: Result view (full, summary, timeseries)
    user: Current user

Returns:
    Analysis result JSON

实现：[app/tools/praat/routes.py](app/tools/praat/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `job_id` | path | 是 | string |  |  |
| `view` | query | 否 | string | default="full"; enum=["full", "summary", "timeseries"] |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-23"></a>

## 工具-Cluster

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/tools/cluster/jobs` | Create Cluster Job |
| POST | `/api/tools/cluster/staged/preview` | Create Cluster Staged Preview |
| POST | `/api/tools/cluster/staged/prepare` | Start Cluster Staged Prepare |
| POST | `/api/tools/cluster/staged/distances` | Start Cluster Staged Distance |
| POST | `/api/tools/cluster/staged/clusters` | Start Cluster Staged Cluster |
| GET | `/api/tools/cluster/staged/results/{result_hash}` | Get Cluster Staged Result |
| GET | `/api/tools/cluster/jobs/{task_id}` | Get Cluster Job Status |
| DELETE | `/api/tools/cluster/jobs/{task_id}` | Delete Cluster Job |
| GET | `/api/tools/cluster/jobs/{task_id}/result` | Get Cluster Job Result |

### POST `/api/tools/cluster/jobs`

Create Cluster Job

创建一个新的聚类任务。

处理顺序是：
1. 先把前端输入的地点做标准化匹配；
2. 再把 group 和地点解析成稳定的 snapshot；
3. 用 snapshot 生成 job_hash，优先查结果缓存；
4. 若已有完全相同的任务在跑，则直接复用已有 task_id；
5. 否则创建后台任务，由 `run_cluster_job()` 真正执行聚类。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusterJobCreateRequest](#schema-clusterjobcreaterequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterJobCreateResponse](#schema-clusterjobcreateresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/cluster/staged/preview`

Create Cluster Staged Preview

解析输入并返回 preview + prepare_hash。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusterStagePreviewRequest](#schema-clusterstagepreviewrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterStagePreviewResponse](#schema-clusterstagepreviewresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/cluster/staged/prepare`

Start Cluster Staged Prepare

启动或复用 prepare 阶段。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusterStagePrepareRequest](#schema-clusterstagepreparerequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterStageTaskResponse](#schema-clusterstagetaskresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/cluster/staged/distances`

Start Cluster Staged Distance

启动或复用某个 phoneme_mode 的 distance 阶段。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusterStageDistanceRequest](#schema-clusterstagedistancerequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterStageTaskResponse](#schema-clusterstagetaskresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/tools/cluster/staged/clusters`

Start Cluster Staged Cluster

启动或复用 cluster 阶段。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusterStageClusterRequest](#schema-clusterstageclusterrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterStageTaskResponse](#schema-clusterstagetaskresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/cluster/staged/results/{result_hash}`

Get Cluster Staged Result

读取 staged 最终结果。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `result_hash` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/cluster/jobs/{task_id}`

Get Cluster Job Status

查询聚类任务状态。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterJobStatusResponse](#schema-clusterjobstatusresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/tools/cluster/jobs/{task_id}`

Delete Cluster Job

删除聚类任务及其结果缓存。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/tools/cluster/jobs/{task_id}/result`

Get Cluster Job Result

读取聚类任务结果。

实现：[app/tools/cluster/routes.py](app/tools/cluster/routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `task_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-24"></a>

## sql

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/sql/query` | Query Table |
| GET | `/sql/query/columns` | Get Column Info |
| GET | `/sql/query/count` | Get Table Count |
| GET | `/sql/distinct/{db_key}/{table_name}/{column}` | Get Distinct Values |
| POST | `/sql/distinct-query` | Get Distinct Values |
| GET | `/sql/permissions/me` | Get My Sql Permissions |
| POST | `/sql/mutate` | Mutate Table |
| POST | `/sql/batch-mutate` | Batch Mutate Table |
| POST | `/sql/batch-replace-preview` | Batch Replace Preview |
| POST | `/sql/batch-replace-execute` | Batch Replace Execute |
| POST | `/sql/tree/full` | Get Full Tree |
| POST | `/sql/tree/lazy` | Get Tree Children |

### POST `/sql/query`

Query Table

实现：[app/sql/sql_routes.py](app/sql/sql_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__sql__sql_schemas__QueryParams](#schema-app__sql__sql_schemas__queryparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/sql/query/columns`

Get Column Info

实现：[app/sql/sql_routes.py](app/sql/sql_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `db_key` | query | 是 | string |  |  |
| `table_name` | query | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/sql/query/count`

Get Table Count

获取指定表的行数 - 轻量级接口

实现：[app/sql/sql_routes.py](app/sql/sql_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `db_key` | query | 是 | string |  |  |
| `table_name` | query | 是 | string |  |  |
| `filter_column` | query | 否 | string / null |  |  |
| `filter_value` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/sql/distinct/{db_key}/{table_name}/{column}`

Get Distinct Values

用于前端表头筛选弹窗，获取该列所有不重复的值

实现：[app/sql/sql_routes.py](app/sql/sql_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `db_key` | path | 是 | string |  |  |
| `table_name` | path | 是 | string |  |  |
| `column` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/distinct-query`

Get Distinct Values

实现：[app/sql/sql_routes.py](app/sql/sql_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__sql__sql_schemas__DistinctQueryRequest](#schema-app__sql__sql_schemas__distinctqueryrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/sql/permissions/me`

Get My Sql Permissions

获取当前用户可以编辑的 SQL 数据库。

权限粒度是 db_key，不是 table_name。

实现：[app/sql/sql_admin_routes.py](app/sql/sql_admin_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/mutate`

Mutate Table

单个记录操作（创建/更新/删除）- 需要数据库写权限

支持的操作：
- create: 插入单条记录
- update: 更新单条记录（基于主键）
- delete: 删除单条记录（基于主键）

权限要求：管理员，或在 user_db_permissions 中拥有对应 db_key 的写权限

实现：[app/sql/sql_admin_routes.py](app/sql/sql_admin_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__sql__sql_schemas__MutationParams](#schema-app__sql__sql_schemas__mutationparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/batch-mutate`

Batch Mutate Table

批量操作（批量创建/更新/删除）- 需要数据库写权限

支持的操作：
- batch_create: 批量插入多条记录
- batch_update: 批量更新多条记录（每条记录必须包含主键）
- batch_delete: 批量删除多条记录（通过主键列表）

权限要求：管理员，或在 user_db_permissions 中拥有对应 db_key 的写权限

示例请求：

1. 批量创建：
{
    "db_key": "dialects",
    "table_name": "dialects",
    "action": "batch_create",
    "create_data": [
        {"漢字": "我", "簡稱": "北京", "聲母": "w"},
        {"漢字": "你", "簡稱": "北京", "聲母": "n"}
    ]
}

2. 批量更新：
{
    "db_key": "dialects",
    "table_name": "dialects",
    "action": "batch_update",
    "pk_column": "id",
    "update_data": [
        {"id": 1, "漢字": "我", "聲母": "w"},
        {"id": 2, "漢字": "你", "聲母": "n"}
    ]
}

3. 批量删除：
{
    "db_key": "dialects",
    "table_name": "dialects",
    "action": "batch_delete",
    "pk_column": "id",
    "delete_ids": [1, 2, 3, 4, 5]
}

实现：[app/sql/sql_admin_routes.py](app/sql/sql_admin_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__sql__sql_schemas__BatchMutationParams](#schema-app__sql__sql_schemas__batchmutationparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/batch-replace-preview`

Batch Replace Preview

批量替换预览统计 - 需要管理员权限

统计全表中匹配指定条件的记录数量，不执行实际替换操作。
用于给用户展示将要被替换的记录数量。

权限要求：管理员

实现：[app/sql/sql_admin_routes.py](app/sql/sql_admin_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__sql__sql_schemas__BatchReplacePreviewParams](#schema-app__sql__sql_schemas__batchreplacepreviewparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/batch-replace-execute`

Batch Replace Execute

批量替换执行 - 需要数据库写权限

执行全表批量替换操作，直接在数据库层面更新符合条件的记录。

权限要求：管理员，或在 user_db_permissions 中拥有对应 db_key 的写权限

实现：[app/sql/sql_admin_routes.py](app/sql/sql_admin_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [app__sql__sql_schemas__BatchReplaceExecuteParams](#schema-app__sql__sql_schemas__batchreplaceexecuteparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/tree/full`

Get Full Tree

实现：[app/sql/sql_tree_routes.py](app/sql/sql_tree_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FullTreeParams](#schema-fulltreeparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/sql/tree/lazy`

Get Tree Children

实现：[app/sql/sql_tree_routes.py](app/sql/sql_tree_routes.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [LazyTreeParams](#schema-lazytreeparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-25"></a>

## 日誌統計

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/logs/keyword/top` | Get Top Keywords Route |
| GET | `/logs/keyword/search` | Search Keyword Logs Route |
| GET | `/logs/api/usage` | Get Api Usage Route |
| GET | `/logs/stats/summary` | Get Stats Summary Route |
| GET | `/logs/stats/fields` | Get Field Stats Route |
| GET | `/logs/visits/total` | Get Total Visits Route |
| GET | `/logs/visits/today` | Get Today Visits Route |
| GET | `/logs/visits/history` | Get Visit History Route |
| GET | `/logs/visits/by-path` | Get Visits By Path Route |
| GET | `/logs/database/size` | Get Database Size Route |
| GET | `/logs/stats/hourly` | Get Hourly Trend Route |
| GET | `/logs/stats/daily` | Get Daily Trend Route |
| GET | `/logs/stats/ranking` | Get Api Ranking Route |
| GET | `/logs/stats/api-history` | Get Api History Route |

### GET `/logs/keyword/top`

Get Top Keywords Route

获取热门关键词

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `limit` | query | 否 | integer | default=10; minimum=1; maximum=500 |  |
| `days` | query | 否 | integer / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/keyword/search`

Search Keyword Logs Route

搜索关键词日志

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `keyword` | query | 否 | string / null |  |  |
| `user_id` | query | 否 | integer / null |  |  |
| `start_time` | query | 否 | string (date-time) / null |  |  |
| `end_time` | query | 否 | string (date-time) / null |  |  |
| `page` | query | 否 | integer | default=1; minimum=1 |  |
| `page_size` | query | 否 | integer | default=50; minimum=1; maximum=200 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/api/usage`

Get Api Usage Route

获取 API 使用统计

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `start_time` | query | 否 | string (date-time) / null |  |  |
| `end_time` | query | 否 | string (date-time) / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/stats/summary`

Get Stats Summary Route

获取统计概览

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/stats/fields`

Get Field Stats Route

获取指定字段的统计信息

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `field` | query | 是 | string |  | 字段名：path, method, user_id, ip_address, status_code |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/visits/total`

Get Total Visits Route

获取总访问量

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/visits/today`

Get Today Visits Route

获取今日访问量

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/visits/history`

Get Visit History Route

获取历史访问记录（按日期聚合）

返回每日的访问统计数据，支持分页和筛选

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `path` | query | 否 | string / null |  | 筛选特定路径，如 '/', '/admin' |
| `start_date` | query | 否 | string / null |  | 开始日期 YYYY-MM-DD |
| `end_date` | query | 否 | string / null |  | 结束日期 YYYY-MM-DD |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=10000 | 返回数量 |
| `offset` | query | 否 | integer | default=0; minimum=0 | 分页偏移 |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/visits/by-path`

Get Visits By Path Route

按路径统计访问量

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `days` | query | 否 | integer / null |  |  |
| `limit` | query | 否 | integer | default=20; minimum=1; maximum=500 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/database/size`

Get Database Size Route

获取数据库大小（仅管理员）

实现：[app/routes/logging/stats.py](app/routes/logging/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/stats/hourly`

Get Hourly Trend Route

获取小时级调用趋势

Args:
    hours: 最近N小时，默认24小时，最多7天（168小时）

实现：[app/routes/logging/hourly_daily.py](app/routes/logging/hourly_daily.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `hours` | query | 否 | integer | default=24; minimum=1; maximum=10000 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/stats/daily`

Get Daily Trend Route

获取每日调用趋势

Args:
    days: 最近N天，默认30天，最多365天
    path: 指定API路径（可选），不指定则返回所有API的总和

实现：[app/routes/logging/hourly_daily.py](app/routes/logging/hourly_daily.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `days` | query | 否 | integer | default=30; minimum=1; maximum=1000 |  |
| `path` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/stats/ranking`

Get Api Ranking Route

获取 API 排行榜

Args:
    date: 指定日期（YYYY-MM-DD），与 days 互斥
    days: 最近N天的排行榜，与 date 互斥
    limit: 返回前N个，默认10个，最多100个

实现：[app/routes/logging/hourly_daily.py](app/routes/logging/hourly_daily.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `date` | query | 否 | string / null |  |  |
| `days` | query | 否 | integer / null |  |  |
| `limit` | query | 否 | integer | default=10; minimum=1; maximum=500 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/logs/stats/api-history`

Get Api History Route

获取指定 API 的历史趋势

Args:
    path: API路径（必填）
    days: 最近N天，默认30天，最多365天

实现：[app/routes/logging/hourly_daily.py](app/routes/logging/hourly_daily.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `path` | query | 是 | string |  |  |
| `days` | query | 否 | integer | default=30; minimum=1; maximum=1000 |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-26"></a>

## villagesML-Character

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/character/frequency/global` | Get Global Character Frequency |
| GET | `/api/villages/character/frequency/regional` | Get Regional Character Frequency |
| GET | `/api/villages/character/tendency/by-region` | Get Character Tendency By Region |
| GET | `/api/villages/character/tendency/by-char` | Get Character Tendency By Char |
| GET | `/api/villages/character/embeddings/vector` | Get Character Embedding |
| GET | `/api/villages/character/embeddings/similarities` | Get Similar Characters |
| GET | `/api/villages/character/embeddings/list` | List Character Embeddings |
| POST | `/api/villages/character/network` | Get Character Network |
| GET | `/api/villages/character/significance/by-character` | Get Character Significance |
| GET | `/api/villages/character/significance/by-region` | Get Significant Characters By Region |
| GET | `/api/villages/character/significance/summary` | Get Significance Summary |

### GET `/api/villages/character/frequency/global`

Get Global Character Frequency

获取全局字符频率
Get global character frequency statistics

Args:
    top_n: 返回前N个高频字符
    min_frequency: 最小频次阈值（现场过滤）

Returns:
    List[CharFrequency]: 字符频率列表

实现：[app/villagesML/character/frequency.py](app/villagesML/character/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `top_n` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回前N个字符 |
| `min_frequency` | query | 否 | integer / null |  | 最小频次过滤 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[CharFrequency](#schema-charfrequency)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/frequency/regional`

Get Regional Character Frequency

获取区域字符频率
Get regional character frequency statistics

Args:
    region_level: 区域级别 (city/county/township)
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    top_n: 每个区域返回前N个字符

Returns:
    List[RegionalCharFrequency]: 区域字符频率列表

实现：[app/villagesML/character/frequency.py](app/villagesML/character/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `top_n` | query | 否 | integer | default=50; minimum=1; maximum=500 | 每个区域返回前N个字符 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[RegionalCharFrequency](#schema-regionalcharfrequency)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/tendency/by-region`

Get Character Tendency By Region

获取指定区域的字符倾向性
Get character tendency for a specific region

Args:
    region_level: 区域级别 (city/county/township)
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    top_n: 返回前N个高倾向字符
    sort_by: 排序字段 (z_score/lift/log_odds)

Returns:
    List[CharTendency]: 字符倾向性列表

实现：[app/villagesML/character/tendency.py](app/villagesML/character/tendency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `top_n` | query | 否 | integer | default=50; minimum=1; maximum=500 | 返回前N个字符 |
| `sort_by` | query | 否 | string | default="z_score"; pattern="^(z_score&#124;lift&#124;log_odds)$" | 排序字段 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[CharTendency](#schema-chartendency)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/tendency/by-char`

Get Character Tendency By Char

获取指定字符在各区域的倾向性
Get tendency of a specific character across regions

Args:
    character: 字符
    region_level: 区域级别 (city/county/township)
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）

Returns:
    List[CharTendencyByRegion]: 各区域倾向性列表（包含区域中心点坐标）

实现：[app/villagesML/character/tendency.py](app/villagesML/character/tendency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `character` | query | 是 | string | minLength=1; maxLength=1 | 字符 |
| `region_level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[CharTendencyByRegion](#schema-chartendencybyregion)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/embeddings/vector`

Get Character Embedding

获取字符的Word2Vec嵌入向量
Get Word2Vec embedding vector for a character

Args:
    char: 字符

Returns:
    dict: 字符嵌入信息（包含向量）

实现：[app/villagesML/character/embeddings.py](app/villagesML/character/embeddings.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `char` | query | 是 | string | minLength=1; maxLength=1 | 字符 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/embeddings/similarities`

Get Similar Characters

获取与指定字符最相似的字符
Get most similar characters to a given character

Args:
    char: 字符
    top_k: 返回前K个相似字符
    min_similarity: 最小相似度阈值（可选）

Returns:
    dict: 包含查询信息和相似字符列表

实现：[app/villagesML/character/embeddings.py](app/villagesML/character/embeddings.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `char` | query | 是 | string | minLength=1; maxLength=1 | 字符 |
| `top_k` | query | 否 | integer | default=10; minimum=1; maximum=50 | 返回前K个相似字符 |
| `min_similarity` | query | 否 | number / null |  | 最小相似度阈值 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/embeddings/list`

List Character Embeddings

列出所有字符嵌入（不包含向量，仅元数据）
List all character embeddings (metadata only, no vectors)

Args:
    limit: 返回记录数
    offset: 偏移量

Returns:
    dict: 包含分页信息和字符嵌入元数据列表

实现：[app/villagesML/character/embeddings.py](app/villagesML/character/embeddings.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `offset` | query | 否 | integer | default=0; minimum=0 | 偏移量 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/character/network`

Get Character Network

BFS 扩展字符相似性网络，返回完整图数据（节点 + 边）。

实现：[app/villagesML/character/network.py](app/villagesML/character/network.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CharacterNetworkRequest](#schema-characternetworkrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [CharacterNetworkResponse](#schema-characternetworkresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/significance/by-character`

Get Character Significance

获取字符在各区域的统计显著性
Get statistical significance of a character across regions

Args:
    char: 字符
    run_id: 分析运行ID
    region_level: 区域级别
    min_zscore: 最小Z分数阈值（可选）

Returns:
    List[dict]: 区域显著性列表

实现：[app/villagesML/character/significance.py](app/villagesML/character/significance.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `char` | query | 是 | string | minLength=1; maxLength=1 | 字符 |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `region_level` | query | 否 | string | default="city"; pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `min_zscore` | query | 否 | number / null |  | 最小Z分数阈值 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/significance/by-region`

Get Significant Characters By Region

获取指定区域的显著字符
Get significant characters for a specific region

Args:
    region_name: 区域名称（模糊匹配，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    run_id: 分析运行ID
    region_level: 区域级别
    significance_only: 仅返回显著字符（p < 0.05）
    top_k: 返回前K个字符

Returns:
    List[dict]: 显著字符列表

实现：[app/villagesML/character/significance.py](app/villagesML/character/significance.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `region_level` | query | 否 | string | default="city"; pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `significance_only` | query | 否 | boolean | default=true | 仅返回显著字符 |
| `top_k` | query | 否 | integer | default=20; minimum=1; maximum=500 | 返回前K个字符 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/character/significance/summary`

Get Significance Summary

获取显著性分析汇总统计
Get significance analysis summary statistics

Args:
    run_id: 分析运行ID
    region_level: 区域级别

Returns:
    dict: 汇总统计信息

实现：[app/villagesML/character/significance.py](app/villagesML/character/significance.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `region_level` | query | 否 | string | default="city"; pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-27"></a>

## villagesML-Village

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/village/search` | Search Villages |
| GET | `/api/villages/village/search/detail` | Get Village Detail |
| GET | `/api/villages/village/ngrams/{village_id}` | Get Village Ngrams |
| GET | `/api/villages/village/semantic-structure/{village_id}` | Get Village Semantic Structure |
| GET | `/api/villages/village/features/{village_id}` | Get Village Features |
| GET | `/api/villages/village/spatial-features/{village_id}` | Get Village Spatial Features |
| GET | `/api/villages/village/complete/{village_id}` | Get Village Complete Profile |

### GET `/api/villages/village/search`

Search Villages

搜索村庄
Search villages by keyword

Args:
    query: 村名关键词（传空字符串或空格查询所有）
    city: 城市过滤（可选）
    county: 区县过滤（可选）
    township: 乡镇过滤（可选）
    limit: 返回数量
    offset: 偏移量

Returns:
    PaginatedResponse: 分页响应，包含总数和数据列表

实现：[app/villagesML/village/search.py](app/villagesML/village/search.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `query` | query | 是 | string |  | 村名关键词（传空字符串或空格查询所有） |
| `city` | query | 否 | string / null |  | 城市过滤 |
| `county` | query | 否 | string / null |  | 区县过滤 |
| `township` | query | 否 | string / null |  | 乡镇过滤 |
| `limit` | query | 否 | integer | default=20; minimum=1; maximum=50 | 返回数量 |
| `offset` | query | 否 | integer | default=0; minimum=0 | 偏移量 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [PaginatedResponse](#schema-paginatedresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/village/search/detail`

Get Village Detail

获取村庄详情
Get village detail information

Args:
    village_name: 村名
    city: 城市
    county: 区县
    run_id: 分析运行ID（留空使用活跃版本）

Returns:
    VillageDetail: 村庄详情

实现：[app/villagesML/village/search.py](app/villagesML/village/search.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | query | 否 | integer / null |  | 村庄ROWID |
| `village_name` | query | 否 | string / null |  | 村名 |
| `city` | query | 否 | string / null |  | 城市 |
| `county` | query | 否 | string / null |  | 区县 |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VillageDetail](#schema-villagedetail) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/village/ngrams/{village_id}`

Get Village Ngrams

获取特定村庄的N-gram
Get n-grams for a specific village

Args:
    village_id: 村庄ID (ROWID from main table)
    n: N-gram长度（2-4）

Returns:
    dict: 村庄N-gram信息

实现：[app/villagesML/village/data.py](app/villagesML/village/data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `village_id` | path | 是 | integer |  |  |
| `n` | query | 否 | integer / null |  | N-gram长度 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/village/semantic-structure/{village_id}`

Get Village Semantic Structure

获取特定村庄的语义结构
Get semantic structure for a specific village

Args:
    village_id: 村庄ID (ROWID from main table)

Returns:
    dict: 村庄语义结构

实现：[app/villagesML/village/data.py](app/villagesML/village/data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `village_id` | path | 是 | integer |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/village/features/{village_id}`

Get Village Features

获取特定村庄的特征向量
Get feature vector for a specific village

Args:
    village_id: 村庄ID (ROWID from main table)

Returns:
    dict: 村庄特征

实现：[app/villagesML/village/data.py](app/villagesML/village/data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `village_id` | path | 是 | integer |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/village/spatial-features/{village_id}`

Get Village Spatial Features

获取特定村庄的空间特征
Get spatial features for a specific village

Args:
    village_id: 村庄ID (ROWID from main table)
    clustering_version: 聚类版本ID，默认使用活跃版本

Returns:
    dict: 村庄空间特征

实现：[app/villagesML/village/data.py](app/villagesML/village/data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `village_id` | path | 是 | integer |  |  |
| `clustering_version` | query | 否 | string / null |  | 聚类版本ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/village/complete/{village_id}`

Get Village Complete Profile

获取村庄的完整档案（所有数据）
Get complete profile for a village (all available data)

Args:
    village_id: 村庄ID (ROWID from main table)

Returns:
    dict: 村庄完整档案

实现：[app/villagesML/village/data.py](app/villagesML/village/data.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `village_id` | path | 是 | integer |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-28"></a>

## villagesML-Subset

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/villages/subset/filter` | Filter Villages |

### POST `/api/villages/subset/filter`

Filter Villages

筛选村庄，一次返回全部匹配结果。所有条件 AND 关系，同组内 OR。

实现：[app/villagesML/village/subset_filter.py](app/villagesML/village/subset_filter.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SubsetFilterRequest](#schema-subsetfilterrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SubsetFilterResponse](#schema-subsetfilterresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-29"></a>

## villagesML-Metadata

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/metadata/stats/overview` | Get System Overview |
| GET | `/api/villages/metadata/stats/tables` | Get Table Info |
| GET | `/api/villages/metadata/stats/regions` | Get Regions |

### GET `/api/villages/metadata/stats/overview`

Get System Overview

获取系统概览统计
Get system overview statistics

Returns:
    SystemOverview: 系统概览信息

实现：[app/villagesML/metadata/stats.py](app/villagesML/metadata/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [SystemOverview](#schema-systemoverview) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/metadata/stats/tables`

Get Table Info

获取数据库表信息
Get database table information

Returns:
    List[TableInfo]: 表信息列表

实现：[app/villagesML/cache_utils.py](app/villagesML/cache_utils.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[TableInfo](#schema-tableinfo)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/metadata/stats/regions`

Get Regions

获取区域列表
Get list of regions at specified level

Args:
    level: 区域级别 ('city', 'county', 'township')
    parent: 父区域名称（可选，用于层级过滤）
        - level=county时，parent为城市名称
        - level=township时，parent为县区名称

Returns:
    List[RegionInfo]: 区域信息列表

Examples:
    - GET /metadata/stats/regions?level=city
      返回所有城市
    - GET /metadata/stats/regions?level=county&parent=广州市
      返回广州市下的所有县区
    - GET /metadata/stats/regions?level=township&parent=番禺区
      返回番禺区下的所有乡镇

实现：[app/villagesML/metadata/stats.py](app/villagesML/metadata/stats.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `level` | query | 是 | string |  |  |
| `parent` | query | 否 | string / null |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[RegionInfo](#schema-regioninfo)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-30"></a>

## villagesML-Semantic

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/semantic/category/list` | Get Semantic Categories |
| GET | `/api/villages/semantic/category/vtf/global` | Get Global Semantic Vtf |
| GET | `/api/villages/semantic/category/vtf/regional` | Get Regional Semantic Vtf |
| GET | `/api/villages/semantic/category/tendency` | Get Semantic Tendency |
| GET | `/api/villages/semantic/labels/by-character` | Get Semantic Label By Character |
| GET | `/api/villages/semantic/labels/by-category` | Get Characters By Semantic Category |
| GET | `/api/villages/semantic/labels/categories` | List Semantic Categories |
| GET | `/api/villages/semantic/composition/bigrams` | Get Semantic Bigrams |
| GET | `/api/villages/semantic/composition/trigrams` | Get Semantic Trigrams |
| GET | `/api/villages/semantic/composition/pmi` | Get Semantic Pmi |
| GET | `/api/villages/semantic/composition/patterns` | Get Composition Patterns |
| GET | `/api/villages/semantic/indices` | Get Semantic Indices |
| GET | `/api/villages/semantic/subcategory/list` | Get Subcategories |
| GET | `/api/villages/semantic/subcategory/chars/{subcategory}` | Get Subcategory Chars |
| GET | `/api/villages/semantic/subcategory/vtf/global` | Get Global Subcategory Vtf |
| GET | `/api/villages/semantic/subcategory/vtf/regional` | Get Regional Subcategory Vtf |
| GET | `/api/villages/semantic/subcategory/tendency/top` | Get Top Tendency Subcategories |
| GET | `/api/villages/semantic/subcategory/comparison` | Compare Subcategories |

### GET `/api/villages/semantic/category/list`

Get Semantic Categories

获取所有语义类别
Get all semantic categories

Returns:
    List[SemanticCategory]: 语义类别列表

实现：[app/villagesML/semantic/category.py](app/villagesML/semantic/category.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[SemanticCategory](#schema-semanticcategory)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/category/vtf/global`

Get Global Semantic Vtf

获取全局语义虚拟词频
Get global semantic VTF (Virtual Term Frequency)

Args:
    category: 语义类别（可选）
    detail: 是否使用子类别表（53子类别，v4词典），默认False（9大类别）

Returns:
    List[dict]: 语义VTF列表

实现：[app/villagesML/semantic/category.py](app/villagesML/semantic/category.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `category` | query | 否 | string / null |  | 语义类别过滤（detail=false按大类，detail=true按父类） |
| `detail` | query | 否 | boolean | default=false | 是否使用子类别表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/category/vtf/regional`

Get Regional Semantic Vtf

获取区域语义虚拟词频
Get regional semantic VTF

Args:
    region_level: 区域级别 (city/county/township)
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    category: 语义类别（可选）
    detail: 是否使用子类别表（53子类别，v4词典），默认False（9大类别）

Returns:
    List[dict]: 区域语义VTF列表

实现：[app/villagesML/semantic/category.py](app/villagesML/semantic/category.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `category` | query | 否 | string / null |  | 语义类别（detail=false按大类，detail=true按父类） |
| `detail` | query | 否 | boolean | default=false | 是否使用子类别表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/category/tendency`

Get Semantic Tendency

获取区域语义倾向性
Get semantic tendency for a region

Args:
    region_level: 区域级别
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    top_n: 返回前N个类别

Returns:
    List[SemanticTendency]: 语义倾向性列表

实现：[app/villagesML/semantic/category.py](app/villagesML/semantic/category.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `top_n` | query | 否 | integer | default=9; minimum=1; maximum=20 | 返回前N个类别 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[SemanticTendency](#schema-semantictendency)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/labels/by-character`

Get Semantic Label By Character

Get semantic label for one character.

实现：[app/villagesML/semantic/labels.py](app/villagesML/semantic/labels.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `char` | query | 是 | string | minLength=1; maxLength=1 | Character |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/labels/by-category`

Get Characters By Semantic Category

Get characters in a semantic category.

实现：[app/villagesML/semantic/labels.py](app/villagesML/semantic/labels.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `category` | query | 是 | string |  | Semantic category |
| `min_confidence` | query | 否 | number / null |  | Minimum confidence |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=500 | Max records |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/labels/categories`

List Semantic Categories

List semantic categories and their counts.

实现：[app/villagesML/semantic/labels.py](app/villagesML/semantic/labels.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/composition/bigrams`

Get Semantic Bigrams

获取语义二元组（bigram）
Get semantic bigrams (two semantic categories co-occurring)

Args:
    min_frequency: 最小频率（可选）
    min_pmi: 最小点互信息值（可选）
    limit: 返回记录数
    detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

Returns:
    List[dict]: 语义二元组列表

实现：[app/villagesML/semantic/composition.py](app/villagesML/semantic/composition.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `min_frequency` | query | 否 | integer / null |  | 最小频率 |
| `min_pmi` | query | 否 | number / null | default=0.3 | 最小PMI值（默认0.3，过滤无意义组合） |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `detail` | query | 否 | boolean | default=false | 是否使用详细表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/composition/trigrams`

Get Semantic Trigrams

获取语义三元组（trigram）
Get semantic trigrams (three semantic categories co-occurring)

Args:
    min_frequency: 最小频率（可选）
    limit: 返回记录数
    detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

Returns:
    List[dict]: 语义三元组列表

实现：[app/villagesML/semantic/composition.py](app/villagesML/semantic/composition.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `min_frequency` | query | 否 | integer / null |  | 最小频率 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `detail` | query | 否 | boolean | default=false | 是否使用详细表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/composition/pmi`

Get Semantic Pmi

获取语义点互信息（PMI）
Get semantic pointwise mutual information scores

Args:
    category1: 第一个语义类别（可选）
    category2: 第二个语义类别（可选）
    min_pmi: 最小PMI值（可选）
    limit: 返回记录数
    detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

Returns:
    List[dict]: PMI分数列表

实现：[app/villagesML/semantic/composition.py](app/villagesML/semantic/composition.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `category1` | query | 否 | string / null |  | 第一个语义类别 |
| `category2` | query | 否 | string / null |  | 第二个语义类别 |
| `min_pmi` | query | 否 | number / null |  | 最小PMI值 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `detail` | query | 否 | boolean | default=false | 是否使用详细表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/composition/patterns`

Get Composition Patterns

获取语义组合模式
Get semantic composition patterns

Args:
    pattern_type: 模式类型（可选）
    min_frequency: 最小频率（可选）
    limit: 返回记录数
    detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

Returns:
    List[dict]: 组合模式列表

实现：[app/villagesML/semantic/composition.py](app/villagesML/semantic/composition.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `pattern_type` | query | 否 | string / null |  | 模式类型 |
| `min_frequency` | query | 否 | integer / null |  | 最小频率 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `detail` | query | 否 | boolean | default=false | 是否使用详细表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/indices`

Get Semantic Indices

获取语义强度指数
Get semantic intensity indices

Args:
    category: 语义类别（可选）
    region_level: 区域级别（可选）
    region_name: 区域名称（模糊匹配，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    min_villages: 最小村庄数，过滤村庄数少的区域（可选）
    limit: 返回记录数
    detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

Returns:
    List[dict]: 语义指数列表

实现：[app/villagesML/semantic/composition.py](app/villagesML/semantic/composition.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `category` | query | 否 | string / null |  | 语义类别 |
| `region_level` | query | 否 | string / null |  | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `min_villages` | query | 否 | integer / null |  | 最小村庄数（过滤小样本区域） |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `detail` | query | 否 | boolean | default=false | 是否使用详细表（53子类别，v4词典） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/subcategory/list`

Get Subcategories

Get all subcategories, optionally filtered by parent category.

实现：[app/villagesML/semantic/subcategories.py](app/villagesML/semantic/subcategories.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `parent_category` | query | 否 | string / null |  | Parent category filter (terrain/water) |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/subcategory/chars/{subcategory}`

Get Subcategory Chars

Get characters under a specific semantic subcategory (parent_sub format, e.g. terrain_peak_ridge).

实现：[app/villagesML/semantic/subcategories.py](app/villagesML/semantic/subcategories.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `subcategory` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/subcategory/vtf/global`

Get Global Subcategory Vtf

Get global subcategory VTF metrics.

实现：[app/villagesML/semantic/subcategories.py](app/villagesML/semantic/subcategories.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `parent_category` | query | 否 | string / null |  | Parent category filter |
| `subcategory` | query | 否 | string / null |  | Subcategory filter |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | Max records |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/subcategory/vtf/regional`

Get Regional Subcategory Vtf

Get regional subcategory VTF metrics.

实现：[app/villagesML/semantic/subcategories.py](app/villagesML/semantic/subcategories.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 否 | string | default="city" | Region level (city/county/township) |
| `region_name` | query | 否 | string / null |  | Region name |
| `parent_category` | query | 否 | string / null |  | Parent category filter |
| `subcategory` | query | 否 | string / null |  | Subcategory filter |
| `min_tendency` | query | 否 | number / null |  | Minimum tendency |
| `min_villages` | query | 否 | integer | default=0; minimum=0; maximum=500 | Minimum village count |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | Max records |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/subcategory/tendency/top`

Get Top Tendency Subcategories

Get top-N subcategories by tendency.

实现：[app/villagesML/semantic/subcategories.py](app/villagesML/semantic/subcategories.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 否 | string | default="city" | Region level (city/county/township) |
| `parent_category` | query | 否 | string / null |  | Parent category filter |
| `min_villages` | query | 否 | integer | default=5; minimum=0; maximum=500 | Minimum village count |
| `top_n` | query | 否 | integer | default=10; minimum=1; maximum=500 | Top N records |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/semantic/subcategory/comparison`

Compare Subcategories

Compare subcategory distribution for a specific region and parent category.

实现：[app/villagesML/semantic/subcategories.py](app/villagesML/semantic/subcategories.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_name` | query | 是 | string |  | Region name |
| `region_level` | query | 否 | string | default="city" | Region level (city/county/township) |
| `parent_category` | query | 是 | string |  | Parent category |
| `min_villages` | query | 否 | integer | default=0; minimum=0; maximum=500 | Minimum village count |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-31"></a>

## villagesML-Clustering

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/clustering/assignments` | Get Cluster Assignments |
| GET | `/api/villages/clustering/assignments/by-region` | Get Cluster Assignment By Region |
| GET | `/api/villages/clustering/profiles` | Get Cluster Profiles |
| GET | `/api/villages/clustering/metrics` | Get Clustering Metrics |
| GET | `/api/villages/clustering/metrics/best` | Get Best Clustering |

### GET `/api/villages/clustering/assignments`

Get Cluster Assignments

获取聚类分配结果
Get cluster assignments

Args:
    run_id: 分析运行ID
    algorithm: 聚类算法 (kmeans/dbscan/gmm)
    region_level: 区域级别
    cluster_id: 聚类ID（可选）

Returns:
    List[ClusterAssignment]: 聚类分配列表

实现：[app/villagesML/clustering/assignments.py](app/villagesML/clustering/assignments.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `algorithm` | query | 否 | string | default="kmeans"; pattern="^(kmeans&#124;dbscan&#124;gmm)$" | 聚类算法 |
| `region_level` | query | 否 | string | default="county"; pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `cluster_id` | query | 否 | integer / null |  | 聚类ID过滤 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[ClusterAssignment](#schema-clusterassignment)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/clustering/assignments/by-region`

Get Cluster Assignment By Region

获取指定区域的聚类分配
Get cluster assignment for a specific region

Args:
    run_id: 分析运行ID
    region_name: 区域名称
    algorithm: 聚类算法
    region_level: 区域级别

Returns:
    ClusterAssignment: 聚类分配

实现：[app/villagesML/clustering/assignments.py](app/villagesML/clustering/assignments.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `region_name` | query | 是 | string |  | 区域名称 |
| `algorithm` | query | 否 | string | default="kmeans"; pattern="^(kmeans&#124;dbscan&#124;gmm)$" | 聚类算法 |
| `region_level` | query | 否 | string | default="county" | 区域级别 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterAssignment](#schema-clusterassignment) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/clustering/profiles`

Get Cluster Profiles

获取聚类画像
Get cluster profiles

Args:
    run_id: 分析运行ID
    algorithm: 聚类算法
    cluster_id: 聚类ID（可选）

Returns:
    List[ClusterProfile]: 聚类画像列表

实现：[app/villagesML/clustering/assignments.py](app/villagesML/clustering/assignments.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 聚类运行ID（留空使用活跃版本） |
| `algorithm` | query | 否 | string | default="kmeans"; pattern="^(kmeans&#124;dbscan&#124;gmm)$" | 聚类算法 |
| `cluster_id` | query | 否 | integer / null |  | 聚类ID |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/clustering/metrics`

Get Clustering Metrics

获取聚类质量指标
Get clustering quality metrics

Args:
    run_id: 分析运行ID
    algorithm: 聚类算法（可选）

Returns:
    List[ClusteringMetrics]: 聚类指标列表

实现：[app/villagesML/clustering/assignments.py](app/villagesML/clustering/assignments.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `algorithm` | query | 否 | string / null |  | 聚类算法 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / array&lt;[ClusteringMetrics](#schema-clusteringmetrics)&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/clustering/metrics/best`

Get Best Clustering

获取最优聚类配置
Get best clustering configuration

Args:
    run_id: 分析运行ID
    algorithm: 聚类算法
    metric: 优化指标

Returns:
    ClusteringMetrics: 最优聚类指标

实现：[app/villagesML/clustering/assignments.py](app/villagesML/clustering/assignments.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `algorithm` | query | 否 | string | default="kmeans"; pattern="^(kmeans&#124;dbscan&#124;gmm)$" | 聚类算法 |
| `metric` | query | 否 | string | default="silhouette_score" | 优化指标 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusteringMetrics](#schema-clusteringmetrics) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-32"></a>

## villagesML-Spatial

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/spatial/hotspots` | Get Spatial Hotspots |
| GET | `/api/villages/spatial/hotspots/{hotspot_id}` | Get Hotspot Detail |
| GET | `/api/villages/spatial/clusters` | Get Spatial Clusters |
| GET | `/api/villages/spatial/clusters/summary` | Get Cluster Summary |
| GET | `/api/villages/spatial/clusters/available-runs` | Get Available Cluster Runs |
| GET | `/api/villages/spatial/integration` | Get Spatial Tendency Integration |
| GET | `/api/villages/spatial/integration/by-character/{character}` | Get Integration By Character |
| GET | `/api/villages/spatial/integration/by-cluster/{cluster_id}` | Get Integration By Cluster |
| GET | `/api/villages/spatial/integration/summary` | Get Integration Summary |
| GET | `/api/villages/spatial/integration/available-characters` | Get Available Characters |
| GET | `/api/villages/spatial/integration/clusterlist` | Get Cluster List |

### GET `/api/villages/spatial/hotspots`

Get Spatial Hotspots

Get spatial density hotspots.

实现：[app/villagesML/spatial/hotspots.py](app/villagesML/spatial/hotspots.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | Spatial analysis run id |
| `min_density` | query | 否 | number / null |  | Minimum density score |
| `min_village_count` | query | 否 | integer / null |  | Minimum village count |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/hotspots/{hotspot_id}`

Get Hotspot Detail

Get one hotspot detail.

实现：[app/villagesML/spatial/hotspots.py](app/villagesML/spatial/hotspots.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `hotspot_id` | path | 是 | integer |  |  |
| `run_id` | query | 否 | string / null |  | Spatial analysis run id |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/clusters`

Get Spatial Clusters

Get DBSCAN cluster summaries.

实现：[app/villagesML/spatial/hotspots.py](app/villagesML/spatial/hotspots.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | Spatial clustering run id |
| `cluster_id` | query | 否 | integer / null |  | Cluster id filter |
| `min_size` | query | 否 | integer / null |  | Minimum cluster size |
| `limit` | query | 否 | integer | default=100; minimum=0 | Max records, 0 for all |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/clusters/summary`

Get Cluster Summary

Get cluster summary statistics.

实现：[app/villagesML/spatial/hotspots.py](app/villagesML/spatial/hotspots.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | Spatial clustering run id |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/clusters/available-runs`

Get Available Cluster Runs

Get available cluster run ids.

实现：[app/villagesML/spatial/hotspots.py](app/villagesML/spatial/hotspots.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/integration`

Get Spatial Tendency Integration

获取空间-倾向性整合分析结果
Get spatial-tendency integration analysis results

This endpoint combines spatial clustering with character tendency analysis,
showing how character usage patterns correlate with geographic clusters.

Args:
    run_id: 整合分析运行ID
    character: 字符过滤（可选）
    cluster_id: 聚类ID过滤（可选）
    min_cluster_size: 最小聚类大小（可选）
    min_spatial_coherence: 最小空间一致性（可选，0-1）
    is_significant: 仅显示统计显著结果（可选）
    limit: 返回记录数

Returns:
    List[dict]: 整合分析结果列表

实现：[app/villagesML/spatial/integration.py](app/villagesML/spatial/integration.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 整合分析运行ID（留空使用活跃版本） |
| `character` | query | 否 | string / null |  | 字符过滤 |
| `cluster_id` | query | 否 | integer / null |  | 聚类ID过滤 |
| `min_cluster_size` | query | 否 | integer / null |  | 最小聚类大小 |
| `min_spatial_coherence` | query | 否 | number / null |  | 最小空间一致性 |
| `is_significant` | query | 否 | boolean / null |  | 仅显示显著结果 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/integration/by-character/{character}`

Get Integration By Character

获取特定字符的空间-倾向性整合结果
Get spatial-tendency integration results for a specific character

Args:
    character: 目标字符
    run_id: 整合分析运行ID
    min_spatial_coherence: 最小空间一致性（可选）

Returns:
    List[dict]: 该字符在各聚类中的表现

实现：[app/villagesML/spatial/integration.py](app/villagesML/spatial/integration.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `character` | path | 是 | string |  |  |
| `run_id` | query | 否 | string / null |  | 整合分析运行ID（留空使用活跃版本） |
| `min_spatial_coherence` | query | 否 | number / null |  | 最小空间一致性 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/integration/by-cluster/{cluster_id}`

Get Integration By Cluster

获取特定聚类的空间-倾向性整合结果
Get spatial-tendency integration results for a specific cluster

Args:
    cluster_id: 聚类ID
    run_id: 整合分析运行ID
    min_tendency: 最小倾向值（可选）

Returns:
    dict: 该聚类中各字符的表现

实现：[app/villagesML/spatial/integration.py](app/villagesML/spatial/integration.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `cluster_id` | path | 是 | integer |  |  |
| `run_id` | query | 否 | string / null |  | 整合分析运行ID（留空使用活跃版本） |
| `min_tendency` | query | 否 | number / null |  | 最小倾向值 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/integration/summary`

Get Integration Summary

获取空间-倾向性整合分析汇总统计
Get spatial-tendency integration summary statistics

Args:
    run_id: 整合分析运行ID

Returns:
    dict: 汇总统计信息

实现：[app/villagesML/spatial/integration.py](app/villagesML/spatial/integration.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 整合分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/integration/available-characters`

Get Available Characters

获取可用字符列表
Get list of available characters for spatial-tendency integration

Returns all characters that have spatial-tendency integration data,
along with their statistics to help frontend avoid querying non-existent characters.

Args:
    run_id: 整合分析运行ID（留空使用活跃版本）

Returns:
    dict: 包含可用字符列表及其统计信息

实现：[app/villagesML/spatial/integration.py](app/villagesML/spatial/integration.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 整合分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/spatial/integration/clusterlist`

Get Cluster List

获取聚类列表（含地区信息）
Get cluster list with geographic information

Returns a list of all clusters with their basic information including
dominant city/county, size, location, and character count.

Args:
    run_id: 整合分析运行ID（留空使用活跃版本）
    min_cluster_size: 最小聚类大小（可选）

Returns:
    dict: 包含聚类列表

实现：[app/villagesML/spatial/integration.py](app/villagesML/spatial/integration.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | query | 否 | string / null |  | 整合分析运行ID（留空使用活跃版本） |
| `min_cluster_size` | query | 否 | integer / null |  | 最小聚类大小 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-33"></a>

## villagesML-Ngrams

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/ngrams/frequency` | Get Ngram Frequency |
| GET | `/api/villages/ngrams/regional` | Get Regional Ngram Frequency |
| GET | `/api/villages/ngrams/patterns` | Get Structural Patterns |
| GET | `/api/villages/ngrams/tendency` | Get Ngram Tendency |
| GET | `/api/villages/ngrams/significance` | Get Ngram Significance |

### GET `/api/villages/ngrams/frequency`

Get Ngram Frequency

获取全局N-gram频率
Get global n-gram frequencies

Args:
    n: N-gram大小 (2, 3, 或 4)
    position: N-gram位置 (all=所有位置, prefix=前缀, middle=中间, suffix=后缀)
    top_k: 返回前K个高频n-grams
    min_frequency: 最小频次阈值（可选）

Returns:
    List[dict]: N-gram频率列表

实现：[app/villagesML/ngrams/frequency.py](app/villagesML/ngrams/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `n` | query | 是 | integer | minimum=2; maximum=4 | N-gram大小 (2=bigram, 3=trigram) |
| `position` | query | 否 | string | default="all"; pattern="^(all&#124;prefix&#124;middle&#124;suffix)$" | N-gram位置 (all=所有位置, prefix=前缀, middle=中间, suffix=后缀) |
| `top_k` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回前K个n-grams |
| `min_frequency` | query | 否 | integer / null |  | 最小频次过滤 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/ngrams/regional`

Get Regional Ngram Frequency

获取区域N-gram频率
Get regional n-gram frequencies

支持三种级别：
- township: 直接查询乡镇级数据（原始数据）
- county: 从乡镇数据动态聚合到区县级
- city: 从乡镇数据动态聚合到市级

Args:
    n: N-gram大小
    region_level: 区域级别 (city/county/township)
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    top_k: 每个区域返回前K个n-grams
    return_metadata: 是否返回元数据

Returns:
    List[dict] 或 dict: N-gram频率列表，或包含data和metadata的字典

实现：[app/villagesML/ngrams/frequency.py](app/villagesML/ngrams/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `n` | query | 是 | integer | minimum=2; maximum=4 | N-gram大小 |
| `region_level` | query | 否 | string | default="township"; pattern="^(city&#124;county&#124;township)$" | 区域级别（支持动态聚合） |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `top_k` | query | 否 | integer | default=50; minimum=1; maximum=500 | 每个区域返回前K个n-grams |
| `return_metadata` | query | 否 | boolean | default=false | 是否返回元数据（包含数据说明） |
| `allow_broad_scan` | query | 否 | boolean | default=false | 显式允许跨全部区域的探索型宽查询 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/ngrams/patterns`

Get Structural Patterns

获取结构化命名模式
Get structural naming patterns

Args:
    pattern: 模式过滤（*或X表示占位符；支持SQL LIKE语法）
    pattern_type: 模式类型（可选）
    n: N-gram大小（可选）
    position: 位置过滤（可选）
    min_frequency: 最小频次（可选）
    limit: 返回记录数

Returns:
    List[dict]: 结构化模式列表

实现：[app/villagesML/ngrams/frequency.py](app/villagesML/ngrams/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `pattern` | query | 否 | string / null |  | 模式过滤（*或X表示占位符，如'山*'或'山X'；支持SQL LIKE语法，如'山%'表示以山开头） |
| `pattern_type` | query | 否 | string / null |  | 模式类型过滤 |
| `n` | query | 否 | integer / null |  | N-gram大小过滤 |
| `position` | query | 否 | string / null |  | 位置过滤 |
| `min_frequency` | query | 否 | integer / null |  | 最小频次过滤 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=500 | 返回记录数 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/ngrams/tendency`

Get Ngram Tendency

获取N-gram倾向性分析
Get n-gram tendency scores

支持三种级别：
- township: 直接查询乡镇级数据（原始数据）
- county: 从乡镇数据动态聚合到区县级
- city: 从乡镇数据动态聚合到市级

注意：
- ngram 必须是 2-4 字符的组合（如"新村"、"山村"），不支持单字符
- 倾向值 (lift) > 1 表示该区域偏好使用该 n-gram
- 倾向值 (lift) < 1 表示该区域较少使用该 n-gram
- 聚合级别的 lift 值会重新计算

Args:
    ngram: N-gram内容（2-4字符）
    region_level: 区域级别（city/county/township）
    region_name: 区域名称（模糊匹配）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    min_tendency: 最小倾向值（lift值）
    limit: 返回记录数

Returns:
    List[dict]: N-gram倾向性列表（包含区域中心点坐标）

实现：[app/villagesML/ngrams/frequency.py](app/villagesML/ngrams/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `ngram` | query | 否 | string / null |  | N-gram（2-4字符，如'新村'、'村村'） |
| `region_level` | query | 否 | string | default="township"; pattern="^(city&#124;county&#124;township)$" | 区域级别（支持动态聚合） |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `min_tendency` | query | 否 | number / null |  | 最小倾向值（lift值） |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `allow_broad_scan` | query | 否 | boolean | default=false | 显式允许跨全部区域的探索型宽查询 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/ngrams/significance`

Get Ngram Significance

获取N-gram显著性（支持动态聚合）
Get n-gram significance test results with dynamic aggregation

- township: 直接查询 Township 级别数据
- county: 从 Township 聚合到 County 级别
- city: 从 Township 聚合到 City 级别

实现：[app/villagesML/ngrams/frequency.py](app/villagesML/ngrams/frequency.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `ngram` | query | 否 | string / null |  | N-gram |
| `region_level` | query | 否 | string | default="county" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称 |
| `city` | query | 否 | string / null |  | 城市 |
| `county` | query | 否 | string / null |  | 区县 |
| `is_significant` | query | 否 | boolean / null |  | 仅显示显著结果 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-34"></a>

## villagesML-Patterns

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/patterns/frequency/global` | Get Global Pattern Frequency |
| GET | `/api/villages/patterns/frequency/regional` | Get Regional Pattern Frequency |
| GET | `/api/villages/patterns/tendency` | Get Pattern Tendency |
| GET | `/api/villages/patterns/structural` | Get Structural Patterns |

### GET `/api/villages/patterns/frequency/global`

Get Global Pattern Frequency

获取全局模式频率
Get global pattern frequencies

Args:
    pattern_type: 模式类型（prefix/suffix/infix）
    min_frequency: 最小频率
    top_k: 返回Top K

Returns:
    List[dict]: 模式频率列表

实现：[app/villagesML/patterns/__init__.py](app/villagesML/patterns/__init__.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `pattern_type` | query | 否 | string / null |  | 模式类型 |
| `min_frequency` | query | 否 | number / null |  | 最小频率（0-1之间的小数，如0.05表示5%） |
| `top_k` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回Top K |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/patterns/frequency/regional`

Get Regional Pattern Frequency

获取区域模式频率
Get regional pattern frequencies

Args:
    region_level: 区域级别（city/county/town）
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    pattern_type: 模式类型（可选）
    top_k: 返回Top K

Returns:
    List[dict]: 区域模式频率列表

实现：[app/villagesML/patterns/__init__.py](app/villagesML/patterns/__init__.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string |  | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `pattern_type` | query | 否 | string / null |  | 模式类型 |
| `top_k` | query | 否 | integer | default=50; minimum=1; maximum=500 | 返回Top K |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/patterns/tendency`

Get Pattern Tendency

获取模式倾向性
Get pattern tendency scores

Args:
    pattern: 模式（可选）
    region_level: 区域级别
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    min_tendency: 最小倾向值
    limit: 返回记录数

Returns:
    List[dict]: 模式倾向性列表

实现：[app/villagesML/patterns/__init__.py](app/villagesML/patterns/__init__.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `pattern` | query | 否 | string / null |  | 模式 |
| `region_level` | query | 否 | string | default="county" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `min_tendency` | query | 否 | number / null |  | 最小倾向值 |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/patterns/structural`

Get Structural Patterns

获取结构化模式
Get structural naming patterns

Args:
    pattern_type: 模式类型（可选）
    min_frequency: 最小频率（可选）

Returns:
    List[dict]: 结构化模式列表

实现：[app/villagesML/patterns/__init__.py](app/villagesML/patterns/__init__.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `pattern_type` | query | 否 | string / null |  | 模式类型 |
| `min_frequency` | query | 否 | integer / null |  | 最小频率 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-35"></a>

## villagesML-Regional

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/regional/aggregates/city` | Get City Aggregates |
| GET | `/api/villages/regional/aggregates/county` | Get County Aggregates |
| GET | `/api/villages/regional/aggregates/town` | Get Town Aggregates |
| GET | `/api/villages/regional/spatial-aggregates` | Get Region Spatial Aggregates |
| GET | `/api/villages/regional/vectors` | Get Region Vectors |
| POST | `/api/villages/regional/vectors/compare` | Compare Regional Vectors |
| POST | `/api/villages/regional/vectors/compare/batch` | Batch Compare Vectors |
| POST | `/api/villages/regional/vectors/reduce` | Reduce Vectors |
| POST | `/api/villages/regional/vectors/cluster` | Cluster Vectors |
| GET | `/api/villages/regions/similarity/search` | Search Similar Regions |
| GET | `/api/villages/regions/similarity/pair` | Get Pair Similarity |
| GET | `/api/villages/regions/similarity/matrix` | Get Similarity Matrix |
| GET | `/api/villages/regions/list` | List Regions |

### GET `/api/villages/regional/aggregates/city`

Get City Aggregates

获取城市级别聚合数据（实时计算）
Get city-level aggregate statistics (computed in real-time)

Args:
    city: 城市名称（可选）
    run_id: 分析运行ID（可选）

Returns:
    List[dict]: 城市聚合数据

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `city` | query | 否 | string / null |  | 城市名称 |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regional/aggregates/county`

Get County Aggregates

获取县区级别聚合数据（实时计算）
Get county-level aggregate statistics (computed in real-time)

Args:
    county_name: 县区名称（向后兼容）
    city_name: 所属城市（向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    run_id: 分析运行ID（可选）

Returns:
    List[dict]: 县区聚合数据

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `county_name` | query | 否 | string / null |  | 县区名称（向后兼容） |
| `city_name` | query | 否 | string / null |  | 所属城市（向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regional/aggregates/town`

Get Town Aggregates

获取乡镇级别聚合数据（实时计算）
Get town-level aggregate statistics (computed in real-time)

Args:
    town_name: 乡镇名称（向后兼容，模糊匹配）
    county_name: 所属县区（向后兼容）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    limit: 返回记录数（不传则返回全部）
    run_id: 分析运行ID（可选）

Returns:
    List[dict]: 乡镇聚合数据

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `town_name` | query | 否 | string / null |  | 乡镇名称（向后兼容） |
| `county_name` | query | 否 | string / null |  | 所属县区（向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `limit` | query | 否 | integer / null |  | 返回记录数（不传则返回全部） |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regional/spatial-aggregates`

Get Region Spatial Aggregates

获取区域空间聚合数据（查询预计算表，毫秒级响应）
Get regional spatial aggregate statistics from pre-computed table.

Args:
    region_level: 区域级别（city/county/town）
    region_name: 区域名称（向后兼容，模糊匹配）
    city: 市级过滤（精确匹配）
    county: 区县级过滤（精确匹配）
    town: 乡镇级过滤（精确匹配）
    limit: 返回记录数（不传则返回全部）

Returns:
    List[dict]: 区域空间聚合数据

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string |  | 区域级别（city/county/town） |
| `region_name` | query | 否 | string / null |  | 区域名称（向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 区县级过滤 |
| `town` | query | 否 | string / null |  | 乡镇级过滤 |
| `limit` | query | 否 | integer / null |  | 返回记录数（不传则返回全部） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regional/vectors`

Get Region Vectors

获取区域语义特征向量（支持层级路径参数以避免重名）
Get regional semantic feature vectors (supports hierarchical path parameters to avoid duplicates)

返回区域的9维语义向量和详细的语义类别数据。
Returns 9-dimensional semantic vectors and detailed semantic category data.

Args:
    level: 区域层级（必填，city/county/township）
    city: 市级名称（可选，用于精确定位）
    county: 县级名称（可选，用于精确定位）
    township: 乡镇级名称（可选，用于精确定位）
    limit: 返回记录数
    run_id: 分析运行ID（可选）

Returns:
    List[dict]: 区域特征向量列表，包含：
        - region_name: 区域名称
        - city: 市级名称
        - county: 县级名称（如适用）
        - township: 乡镇级名称（如适用）
        - feature_vector: 9维语义向量
        - village_count: 村庄数量
        - semantic_categories: 语义类别详情（对象）

Examples:
    # 获取所有市级区域
    GET /api/villages/regional/vectors?level=city&limit=10

    # 获取广州市的数据
    GET /api/villages/regional/vectors?level=city&city=广州市

    # 获取广州市天河区的数据
    GET /api/villages/regional/vectors?level=county&city=广州市&county=天河区

    # 获取广州市天河区龙洞街道的数据（避免与深圳龙岗区龙洞街道混淆）
    GET /api/villages/regional/vectors?level=township&city=广州市&county=天河区&township=龙洞街道

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域层级（city/county/township） |
| `city` | query | 否 | string / null |  | 市级名称（精确匹配） |
| `county` | query | 否 | string / null |  | 县级名称（精确匹配） |
| `township` | query | 否 | string / null |  | 乡镇级名称（精确匹配） |
| `limit` | query | 否 | integer | default=100; minimum=1; maximum=1000 | 返回记录数 |
| `run_id` | query | 否 | string / null |  | 分析运行ID（留空使用活跃版本） |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/regional/vectors/compare`

Compare Regional Vectors

比较两个区域的语义特征向量（支持层级路径参数）
Compare semantic feature vectors between two regions (supports hierarchical path parameters)

支持同层级和跨层级比较，使用层级路径参数避免重名问题。
Supports both same-level and cross-level comparison, uses hierarchical path parameters to avoid duplicates.

Args:
    request: 比较请求参数
    db: 数据库连接

Returns:
    VectorCompareResponse: 包含相似度指标和原始向量的比较结果

Examples:
    ```json
    // 同层级比较：广州市 vs 深圳市
    {
        "level1": "city",
        "city1": "广州市",
        "level2": "city",
        "city2": "深圳市"
    }

    // 跨层级比较：广州市 vs 天河区
    {
        "level1": "city",
        "city1": "广州市",
        "level2": "county",
        "city2": "广州市",
        "county2": "天河区"
    }

    // 避免重名：广州天河区龙洞街道 vs 深圳龙岗区龙洞街道
    {
        "level1": "township",
        "city1": "广州市",
        "county1": "天河区",
        "township1": "龙洞街道",
        "level2": "township",
        "city2": "深圳市",
        "county2": "龙岗区",
        "township2": "龙洞街道"
    }
    ```

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [VectorCompareRequest](#schema-vectorcomparerequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [VectorCompareResponse](#schema-vectorcompareresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/regional/vectors/compare/batch`

Batch Compare Vectors

批量比较多个区域的向量，返回相似度矩阵
Batch compare multiple region vectors, returns similarity matrix

用于热力图可视化。
Used for heatmap visualization.

Args:
    request: 批量比较请求参数
    db: 数据库连接

Returns:
    BatchCompareResponse: 包含相似度矩阵和距离矩阵

Example:
    {
        "regions": [
            {"level": "city", "city": "广州市"},
            {"level": "city", "city": "深圳市"},
            {"level": "city", "city": "佛山市"}
        ]
    }

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [BatchCompareRequest](#schema-batchcomparerequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [BatchCompareResponse](#schema-batchcompareresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/regional/vectors/reduce`

Reduce Vectors

向量降维（PCA 或 t-SNE）
Dimensionality reduction (PCA or t-SNE)

用于散点图可视化。
Used for scatter plot visualization.

Args:
    request: 降维请求参数
    db: 数据库连接

Returns:
    ReduceResponse: 包含降维后的坐标

Example:
    {
        "regions": [
            {"level": "city", "city": "广州市"},
            {"level": "city", "city": "深圳市"},
            {"level": "city", "city": "佛山市"}
        ],
        "method": "pca",
        "n_components": 2
    }

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ReduceRequest](#schema-reducerequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ReduceResponse](#schema-reduceresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/regional/vectors/cluster`

Cluster Vectors

向量聚类（KMeans、DBSCAN 或 GMM）
Vector clustering (KMeans, DBSCAN, or GMM)

发现语义相似的区域群组。
Discover semantically similar region groups.

Args:
    request: 聚类请求参数
    db: 数据库连接

Returns:
    ClusterResponse: 包含聚类标签和中心点

Examples:
    // KMeans
    {
        "regions": [...],
        "method": "kmeans",
        "n_clusters": 3
    }

    // DBSCAN
    {
        "regions": [...],
        "method": "dbscan",
        "eps": 0.5,
        "min_samples": 2
    }

    // GMM
    {
        "regions": [...],
        "method": "gmm",
        "n_clusters": 3
    }

实现：[app/villagesML/regional/aggregates_realtime.py](app/villagesML/regional/aggregates_realtime.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusterRequest](#schema-clusterrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / [ClusterResponse](#schema-clusterresponse) |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regions/similarity/search`

Search Similar Regions

查找与目标区域相似的其他区域

Find regions similar to a target region.

Args:
    region_level: 区域级别 (city/county/township)
    region_name: 区域名称（模糊匹配，可选，向后兼容）
    city: 市级过滤（精确匹配）
    county: 县级过滤（精确匹配）
    township: 乡镇级过滤（精确匹配）
    top_k: Number of similar regions to return (1-50)
    metric: Similarity metric ('cosine' or 'jaccard')
    min_similarity: Minimum similarity threshold (0.0-1.0)

Returns:
    List of similar regions with scores and common characters

实现：[app/villagesML/regional/similarity.py](app/villagesML/regional/similarity.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 是 | string | pattern="^(city&#124;county&#124;township)$" | 区域级别 |
| `region_name` | query | 否 | string / null |  | 区域名称（模糊匹配，向后兼容） |
| `city` | query | 否 | string / null |  | 市级过滤 |
| `county` | query | 否 | string / null |  | 县级过滤 |
| `township` | query | 否 | string / null |  | 乡镇级过滤 |
| `top_k` | query | 否 | integer | default=10; minimum=1; maximum=50 | 返回相似区域数量 |
| `metric` | query | 否 | string | default="cosine"; pattern="^(cosine&#124;jaccard)$" | 相似度指标 |
| `min_similarity` | query | 否 | number | default=0.0; minimum=0.0; maximum=1.0 | 最小相似度阈值 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regions/similarity/pair`

Get Pair Similarity

获取两个区域之间的相似度指标(支持跨层级比较)

Get similarity metrics between two specific regions (supports cross-level comparison).

Args:
    region1: First region name
    region2: Second region name

Returns:
    All similarity metrics, common chars, and distinctive chars

实现：[app/villagesML/regional/similarity.py](app/villagesML/regional/similarity.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region1` | query | 是 | string |  | 区域1名称 |
| `region2` | query | 是 | string |  | 区域2名称 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regions/similarity/matrix`

Get Similarity Matrix

获取多个区域的相似度矩阵（支持跨层级）

Get similarity matrix for multiple regions (supports cross-level comparison).

Args:
    regions: Comma-separated region names (optional, default: top 20 by village count)
    metric: Similarity metric ('cosine' or 'jaccard')

Returns:
    Similarity matrix as 2D array with region labels

实现：[app/villagesML/regional/similarity.py](app/villagesML/regional/similarity.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `regions` | query | 否 | string / null |  | 逗号分隔的区域名称列表 |
| `metric` | query | 否 | string | default="cosine"; pattern="^(cosine&#124;jaccard)$" | 相似度指标 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/regions/list`

List Regions

获取所有可用区域列表

Get list of all available regions.

Args:
    region_level: Region level (default: 'county')

Returns:
    List of region names with village counts

实现：[app/villagesML/regional/similarity.py](app/villagesML/regional/similarity.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `region_level` | query | 否 | string | default="county" | 区域级别 |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-36"></a>

## villagesML-Compute

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| POST | `/api/villages/compute/clustering/run` | Run Clustering |
| POST | `/api/villages/compute/clustering/scan` | Scan Clustering Params |
| GET | `/api/villages/compute/clustering/cache-stats` | Get Cache Stats |
| DELETE | `/api/villages/compute/clustering/cache` | Clear Cache |
| POST | `/api/villages/compute/clustering/character-tendency` | Run Character Tendency Clustering |
| POST | `/api/villages/compute/clustering/sampled-villages` | Run Sampled Village Clustering |
| POST | `/api/villages/compute/clustering/spatial-aware` | Run Spatial Aware Clustering |
| POST | `/api/villages/compute/clustering/hierarchical` | Run Hierarchical Clustering |
| POST | `/api/villages/compute/semantic/cooccurrence` | Analyze Cooccurrence |
| POST | `/api/villages/compute/semantic/network` | Build Semantic Network |
| POST | `/api/villages/compute/features/extract` | Extract Features |
| POST | `/api/villages/compute/features/aggregate` | Aggregate Features |
| POST | `/api/villages/compute/subset/cluster` | Cluster Subset |
| POST | `/api/villages/compute/subset/compare` | Compare Subsets |

### POST `/api/villages/compute/clustering/run`

Run Clustering

执行聚类分析（需要登录）

Args:
    params: 聚类参数
Returns:
    聚类结果

Raises:
    HTTPException: 如果计算失败或超时

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusteringParams](#schema-clusteringparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/clustering/scan`

Scan Clustering Params

扫描聚类参数（多个k值）（需要登录）

Args:
    params: 扫描参数
Returns:
    扫描结果

Raises:
    HTTPException: 如果计算失败或超时

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [ClusteringScanParams](#schema-clusteringscanparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/compute/clustering/cache-stats`

Get Cache Stats

获取缓存统计信息

Returns:
    缓存统计

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### DELETE `/api/villages/compute/clustering/cache`

Clear Cache

清除缓存

Returns:
    操作结果

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object&lt;string&gt; |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/clustering/character-tendency`

Run Character Tendency Clustering

执行字符倾向性聚类（需要登录）

基于字符使用模式（lift/z_score）对区域进行聚类

Args:
    params: 字符倾向性聚类参数
Returns:
    聚类结果

Raises:
    HTTPException: 如果计算失败或超时

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [CharacterTendencyClusteringParams](#schema-charactertendencyclusteringparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/clustering/sampled-villages`

Run Sampled Village Clustering

执行采样村庄聚类（需要登录）

对28.5万村庄进行智能采样后聚类

Args:
    params: 采样村庄聚类参数
Returns:
    聚类结果

Raises:
    HTTPException: 如果计算失败或超时

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SampledVillageClusteringParams](#schema-sampledvillageclusteringparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/clustering/spatial-aware`

Run Spatial Aware Clustering

执行空间感知聚类（需要登录）

对已有的空间聚类结果进行二次聚类

Args:
    params: 空间感知聚类参数
Returns:
    聚类结果

Raises:
    HTTPException: 如果计算失败或超时

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SpatialAwareClusteringParams](#schema-spatialawareclusteringparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/clustering/hierarchical`

Run Hierarchical Clustering

执行层次聚类（需要登录）

展示市→县→镇的嵌套聚类结构

Args:
    params: 层次聚类参数
Returns:
    层次聚类结果

Raises:
    HTTPException: 如果计算失败或超时

实现：[app/villagesML/compute/clustering.py](app/villagesML/compute/clustering.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [HierarchicalClusteringParams](#schema-hierarchicalclusteringparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/semantic/cooccurrence`

Analyze Cooccurrence

分析语义共现（需要登录）

Args:
    params: 分析参数
Returns:
    共现分析结果

Raises:
    HTTPException: 如果分析失败或超时

实现：[app/villagesML/compute/semantic.py](app/villagesML/compute/semantic.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SemanticAnalysisParams](#schema-semanticanalysisparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/semantic/network`

Build Semantic Network

构建语义网络（需要登录）

Args:
    params: 网络参数
Returns:
    语义网络结果

Raises:
    HTTPException: 如果构建失败或超时

实现：[app/villagesML/compute/semantic.py](app/villagesML/compute/semantic.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SemanticNetworkParams](#schema-semanticnetworkparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/features/extract`

Extract Features

批量提取村庄特征（需要登录）

Args:
    params: 提取参数
Returns:
    特征提取结果

Raises:
    HTTPException: 如果提取失败或超时

实现：[app/villagesML/compute/features.py](app/villagesML/compute/features.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FeatureExtractionParams](#schema-featureextractionparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/features/aggregate`

Aggregate Features

聚合区域特征（需要登录）

Args:
    params: 聚合参数
Returns:
    特征聚合结果

Raises:
    HTTPException: 如果聚合失败或超时

实现：[app/villagesML/compute/features.py](app/villagesML/compute/features.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [FeatureAggregationParams](#schema-featureaggregationparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/subset/cluster`

Cluster Subset

对自定义子集进行聚类（需要登录）

Args:
    params: 子集聚类参数
Returns:
    聚类结果

Raises:
    HTTPException: 如果聚类失败或超时

实现：[app/villagesML/compute/subset.py](app/villagesML/compute/subset.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SubsetClusteringParams](#schema-subsetclusteringparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/compute/subset/compare`

Compare Subsets

对比两个子集（需要登录）

Args:
    params: 对比参数
Returns:
    对比结果

Raises:
    HTTPException: 如果对比失败或超时

实现：[app/villagesML/compute/subset.py](app/villagesML/compute/subset.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |
| `require_admin` | query | 否 | boolean | default=false |  |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SubsetComparisonParams](#schema-subsetcomparisonparams) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-37"></a>

## villagesML-Admin

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/admin/run-ids/active` | Get All Active Run Ids |
| GET | `/api/villages/admin/run-ids/active/{analysis_type}` | Get Active Run Id |
| PUT | `/api/villages/admin/run-ids/active/{analysis_type}` | Set Active Run Id |
| GET | `/api/villages/admin/run-ids/available/{analysis_type}` | List Available Run Ids |
| GET | `/api/villages/admin/run-ids/metadata/{run_id}` | Get Run Id Metadata |
| POST | `/api/villages/admin/run-ids/refresh` | Refresh Cache |

### GET `/api/villages/admin/run-ids/active`

Get All Active Run Ids

获取所有分析类型当前激活的 run_id。

Returns:
    所有分析类型对应的当前激活 run_id。

实现：[app/villagesML/admin/run_ids.py](app/villagesML/admin/run_ids.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/admin/run-ids/active/{analysis_type}`

Get Active Run Id

获取指定分析类型当前激活的 run_id。

Args:
    analysis_type: 分析类型名称。

Returns:
    当前激活的 run_id 信息。

实现：[app/villagesML/admin/run_ids.py](app/villagesML/admin/run_ids.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `analysis_type` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### PUT `/api/villages/admin/run-ids/active/{analysis_type}`

Set Active Run Id

设置指定分析类型的激活 run_id。

Args:
    analysis_type: 分析类型名称。
    request: 包含 `run_id`、`updated_by` 和 `notes` 的请求体。
    admin: 当前管理员用户。

Returns:
    更新结果。

实现：[app/villagesML/admin/run_ids.py](app/villagesML/admin/run_ids.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `analysis_type` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

请求体：必填。

| Content-Type | Schema |
| --- | --- |
| `application/json` | [SetActiveRunIDRequest](#schema-setactiverunidrequest) |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/admin/run-ids/available/{analysis_type}`

List Available Run Ids

列出指定分析类型下可用的 run_id。

Args:
    analysis_type: 分析类型名称。

Returns:
    可用 run_id 列表。

实现：[app/villagesML/admin/run_ids.py](app/villagesML/admin/run_ids.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `analysis_type` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/admin/run-ids/metadata/{run_id}`

Get Run Id Metadata

获取 run_id 的元数据。

Args:
    run_id: run_id 名称。

Returns:
    run_id 元数据。

实现：[app/villagesML/admin/run_ids.py](app/villagesML/admin/run_ids.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `run_id` | path | 是 | string |  |  |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### POST `/api/villages/admin/run-ids/refresh`

Refresh Cache

刷新 run_id 缓存。

Returns:
    刷新结果。

实现：[app/villagesML/admin/run_ids.py](app/villagesML/admin/run_ids.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / 未声明结构 |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="group-38"></a>

## villagesML-Statistics

| 方法 | 路径 | 概要 |
| --- | --- | --- |
| GET | `/api/villages/statistics/ngrams` | Get Ngram Statistics |
| GET | `/api/villages/statistics/database` | Get Database Statistics |

### GET `/api/villages/statistics/ngrams`

Get Ngram Statistics

获取 N-gram 统计信息
Get N-gram statistics

Returns:
    dict: N-gram 统计数据

实现：[app/villagesML/cache_utils.py](app/villagesML/cache_utils.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

### GET `/api/villages/statistics/database`

Get Database Statistics

获取数据库统计信息
Get database statistics

Returns:
    dict: 数据库统计数据

实现：[app/villagesML/statistics/__init__.py](app/villagesML/statistics/__init__.py)。

| 参数 | 位置 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `require_admin` | query | 否 | boolean | default=false |  |
| `dbpath` | query | 否 | string | default="village" | VillagesML database mapping key, not a filesystem path |

| 状态码 | 说明 | Content-Type / Schema |
| --- | --- | --- |
| 200 | Successful Response | `application/json` / object |
| 422 | Validation Error | `application/json` / [HTTPValidationError](#schema-httpvalidationerror) |

<a id="schemas"></a>

## Schema

下列字段表用于快速查阅；每个模型的 JSON 定义保留嵌套字段、引用、组合类型、约束和示例。`必填` 与 `允许 null` 是不同概念；具体以 required、anyOf/type 为准。

<a id="schema-apidiversityresponse"></a>

### `APIDiversityResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `users` | 是 | array&lt;[DiversityUserItem](#schema-diversityuseritem)&gt; |  |  |
| `summary` | 是 | [DiversitySummary](#schema-diversitysummary) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "users": {
      "items": {
        "$ref": "#/components/schemas/DiversityUserItem"
      },
      "type": "array",
      "title": "Users"
    },
    "summary": {
      "$ref": "#/components/schemas/DiversitySummary"
    }
  },
  "type": "object",
  "required": [
    "users",
    "summary"
  ],
  "title": "APIDiversityResponse"
}
```

</details>

<a id="schema-apiperformanceitem"></a>

### `APIPerformanceItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | 是 | string |  |  |
| `avg_duration` | 是 | number |  |  |
| `p50` | 是 | number |  |  |
| `p95` | 是 | number |  |  |
| `p99` | 是 | number |  |  |
| `slow_request_ratio` | 是 | number |  |  |
| `total_calls` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path": {
      "type": "string",
      "title": "Path"
    },
    "avg_duration": {
      "type": "number",
      "title": "Avg Duration"
    },
    "p50": {
      "type": "number",
      "title": "P50"
    },
    "p95": {
      "type": "number",
      "title": "P95"
    },
    "p99": {
      "type": "number",
      "title": "P99"
    },
    "slow_request_ratio": {
      "type": "number",
      "title": "Slow Request Ratio"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    }
  },
  "type": "object",
  "required": [
    "path",
    "avg_duration",
    "p50",
    "p95",
    "p99",
    "slow_request_ratio",
    "total_calls"
  ],
  "title": "APIPerformanceItem"
}
```

</details>

<a id="schema-apiperformanceresponse"></a>

### `APIPerformanceResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `apis` | 是 | array&lt;[APIPerformanceItem](#schema-apiperformanceitem)&gt; |  |  |
| `summary` | 是 | [PerformanceSummary](#schema-performancesummary) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "apis": {
      "items": {
        "$ref": "#/components/schemas/APIPerformanceItem"
      },
      "type": "array",
      "title": "Apis"
    },
    "summary": {
      "$ref": "#/components/schemas/PerformanceSummary"
    }
  },
  "type": "object",
  "required": [
    "apis",
    "summary"
  ],
  "title": "APIPerformanceResponse"
}
```

</details>

<a id="schema-admincreate"></a>

### `AdminCreate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `email` | 是 | string (email) |  |  |
| `password` | 是 | string / null |  |  |
| `role` | 否 | string / null | default="user" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email"
    },
    "password": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Password"
    },
    "role": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Role",
      "default": "user"
    }
  },
  "type": "object",
  "required": [
    "username",
    "email",
    "password"
  ],
  "title": "AdminCreate"
}
```

</details>

<a id="schema-adminregioncreate"></a>

### `AdminRegionCreate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `region_name` | 是 | string | minLength=1; maxLength=200 |  |
| `locations` | 是 | array&lt;string&gt; | minItems=1 |  |
| `description` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "region_name": {
      "type": "string",
      "maxLength": 200,
      "minLength": 1,
      "title": "Region Name"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "minItems": 1,
      "title": "Locations"
    },
    "description": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 1000
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    }
  },
  "type": "object",
  "required": [
    "username",
    "region_name",
    "locations"
  ],
  "title": "AdminRegionCreate",
  "description": "管理员为任意用户创建区域"
}
```

</details>

<a id="schema-adminregiondelete"></a>

### `AdminRegionDelete`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `created_at` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "created_at": {
      "type": "string",
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "username",
    "created_at"
  ],
  "title": "AdminRegionDelete",
  "description": "管理员删除任意用户的区域"
}
```

</details>

<a id="schema-adminregionupdate"></a>

### `AdminRegionUpdate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `region_name` | 是 | string |  |  |
| `new_region_name` | 否 | string / null |  |  |
| `locations` | 否 | array&lt;string&gt; / null |  |  |
| `description` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "region_name": {
      "type": "string",
      "title": "Region Name"
    },
    "new_region_name": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 200,
          "minLength": 1
        },
        {
          "type": "null"
        }
      ],
      "title": "New Region Name"
    },
    "locations": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array",
          "minItems": 1
        },
        {
          "type": "null"
        }
      ],
      "title": "Locations"
    },
    "description": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 1000
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    }
  },
  "type": "object",
  "required": [
    "username",
    "region_name"
  ],
  "title": "AdminRegionUpdate",
  "description": "管理员更新任意用户的区域"
}
```

</details>

<a id="schema-adminsuggestionitem"></a>

### `AdminSuggestionItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `user_id` | 否 | integer / null |  |  |
| `username` | 否 | string / null |  |  |
| `title` | 是 | string |  |  |
| `content` | 是 | string |  |  |
| `category` | 是 | string |  |  |
| `source_path` | 否 | string / null |  |  |
| `context` | 否 | object / null |  |  |
| `contact` | 否 | string / null |  |  |
| `recent_api` | 否 | array&lt;object&gt; |  |  |
| `status` | 是 | string |  |  |
| `priority` | 是 | string |  |  |
| `admin_note` | 否 | string / null |  |  |
| `handled_at` | 否 | string (date-time) / null |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `updated_at` | 是 | string (date-time) |  |  |
| `image_base64` | 否 | string / null |  |  |
| `submitter_ip` | 否 | string / null |  |  |
| `user_agent` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "user_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "User Id"
    },
    "username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Username"
    },
    "title": {
      "type": "string",
      "title": "Title"
    },
    "content": {
      "type": "string",
      "title": "Content"
    },
    "category": {
      "type": "string",
      "title": "Category"
    },
    "source_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Source Path"
    },
    "context": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Context"
    },
    "contact": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Contact"
    },
    "recent_api": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Recent Api"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "priority": {
      "type": "string",
      "title": "Priority"
    },
    "admin_note": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Admin Note"
    },
    "handled_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Handled At"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "title": "Updated At"
    },
    "image_base64": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Image Base64"
    },
    "submitter_ip": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Submitter Ip"
    },
    "user_agent": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "User Agent"
    }
  },
  "type": "object",
  "required": [
    "id",
    "title",
    "content",
    "category",
    "status",
    "priority",
    "created_at",
    "updated_at"
  ],
  "title": "AdminSuggestionItem"
}
```

</details>

<a id="schema-adminsuggestionlistresponse"></a>

### `AdminSuggestionListResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |
| `items` | 是 | array&lt;[AdminSuggestionItem](#schema-adminsuggestionitem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    },
    "items": {
      "items": {
        "$ref": "#/components/schemas/AdminSuggestionItem"
      },
      "type": "array",
      "title": "Items"
    }
  },
  "type": "object",
  "required": [
    "total",
    "page",
    "page_size",
    "items"
  ],
  "title": "AdminSuggestionListResponse"
}
```

</details>

<a id="schema-adminsuggestionupdate"></a>

### `AdminSuggestionUpdate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | 否 | string / null |  |  |
| `priority` | 否 | string / null |  |  |
| `admin_note` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "status": {
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "open",
            "reviewing",
            "accepted",
            "rejected",
            "done"
          ]
        },
        {
          "type": "null"
        }
      ],
      "title": "Status"
    },
    "priority": {
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "low",
            "normal",
            "high"
          ]
        },
        {
          "type": "null"
        }
      ],
      "title": "Priority"
    },
    "admin_note": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 5000
        },
        {
          "type": "null"
        }
      ],
      "title": "Admin Note"
    }
  },
  "type": "object",
  "title": "AdminSuggestionUpdate"
}
```

</details>

<a id="schema-agglomerativelinkage"></a>

### `AgglomerativeLinkage`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "average",
    "complete",
    "single"
  ],
  "title": "AgglomerativeLinkage",
  "description": "层次聚类允许的 linkage 类型。"
}
```

</details>

<a id="schema-algorithmtype"></a>

### `AlgorithmType`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "kmeans",
    "dbscan",
    "gmm"
  ],
  "title": "AlgorithmType",
  "description": "聚类算法类型"
}
```

</details>

<a id="schema-analysispayload"></a>

### `AnalysisPayload`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | 是 | string |  |  |
| `locations` | 否 | array&lt;string&gt; |  |  |
| `regions` | 否 | array&lt;string&gt; |  |  |
| `features` | 否 | array&lt;string&gt; |  |  |
| `status_inputs` | 否 | string / array&lt;string&gt; / null |  |  |
| `group_inputs` | 否 | array&lt;string&gt; / null |  |  |
| `pho_values` | 否 | string / array&lt;string&gt; / null |  |  |
| `region_mode` | 否 | string | default="yindian" |  |
| `table_name` | 否 | string | default="characters" | 字符數據庫表名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "mode": {
      "type": "string",
      "title": "Mode"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations"
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions"
    },
    "features": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Features"
    },
    "status_inputs": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Status Inputs"
    },
    "group_inputs": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Group Inputs"
    },
    "pho_values": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Pho Values"
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "default": "yindian"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "字符數據庫表名",
      "default": "characters"
    }
  },
  "type": "object",
  "required": [
    "mode"
  ],
  "title": "AnalysisPayload",
  "description": "- 用于 /api/phonology 路由的輸入特徵，分析聲韻。\n- mode: p2s-查詢音位查詢的中古來源 s2p-按中古地位查詢音值\n- locations: 輸入地點（可多個）\n- regions: 輸入分區（某一級分區，例如嶺南，可多個）\n- features: 要查詢的特徵（聲母/韻母/聲調）必須完全匹配，用繁體字\n- status_inputs: 要查詢的中古地位，可帶類名（例如莊組），也可不帶（例如來）；\n              並且支持-全匹配（例如宕-等，會自動匹配宕一、宕三）；後端會進行簡繁轉換，可輸入簡體\n              s2p模式需要的輸入，若留空，則韻母查所有攝，聲母查三十六母，聲調查清濁+調\n- group_inputs: p2s 模式下的中古分組欄位列表；所有 feature 共用同一組欄位，\n               例如 ['攝', '組'] 表示對每個 feature 都按 攝+組 聯合分組\n- pho_values: 要查詢的具體音值，p2s模式下的輸入，若留空，則查所有音值\n- 若為s2p,返回一個帶有地點、特徵（聲韻調）、分類值（中古地位）、值（具體音值）、對應字（所有查到的字）、\n        字數、佔比（在所有查得的值中佔比）、多音字 的數組。p2s也是類似"
}
```

</details>

<a id="schema-analysisresult"></a>

### `AnalysisResult`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `total_rows` | 是 | integer |  |  |
| `error_count` | 是 | integer |  |  |
| `errors` | 是 | array&lt;[ErrorItem](#schema-erroritem)&gt; |  |  |
| `error_stats` | 是 | object&lt;integer&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "total_rows": {
      "type": "integer",
      "title": "Total Rows"
    },
    "error_count": {
      "type": "integer",
      "title": "Error Count"
    },
    "errors": {
      "items": {
        "$ref": "#/components/schemas/ErrorItem"
      },
      "type": "array",
      "title": "Errors"
    },
    "error_stats": {
      "additionalProperties": {
        "type": "integer"
      },
      "type": "object",
      "title": "Error Stats"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "total_rows",
    "error_count",
    "errors",
    "error_stats"
  ],
  "title": "AnalysisResult",
  "description": "分析结果"
}
```

</details>

<a id="schema-analyticsresponse"></a>

### `AnalyticsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `login_heatmap` | 是 | array&lt;array&lt;integer&gt;&gt; |  | 7x24 login heatmap |
| `user_activity` | 是 | [UserActivityData](#schema-useractivitydata) |  |  |
| `device_distribution` | 是 | [DeviceDistribution](#schema-devicedistribution) |  |  |
| `geo_distribution` | 是 | array&lt;[app__schemas__auth__session__GeoDistributionItem](#schema-app__schemas__auth__session__geodistributionitem)&gt; |  |  |
| `session_duration_distribution` | 是 | [SessionDurationDistribution](#schema-sessiondurationdistribution) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "login_heatmap": {
      "items": {
        "items": {
          "type": "integer"
        },
        "type": "array"
      },
      "type": "array",
      "title": "Login Heatmap",
      "description": "7x24 login heatmap"
    },
    "user_activity": {
      "$ref": "#/components/schemas/UserActivityData"
    },
    "device_distribution": {
      "$ref": "#/components/schemas/DeviceDistribution"
    },
    "geo_distribution": {
      "items": {
        "$ref": "#/components/schemas/app__schemas__auth__session__GeoDistributionItem"
      },
      "type": "array",
      "title": "Geo Distribution"
    },
    "session_duration_distribution": {
      "$ref": "#/components/schemas/SessionDurationDistribution"
    }
  },
  "type": "object",
  "required": [
    "login_heatmap",
    "user_activity",
    "device_distribution",
    "geo_distribution",
    "session_duration_distribution"
  ],
  "title": "AnalyticsResponse"
}
```

</details>

<a id="schema-analyzetaskresponse"></a>

### `AnalyzeTaskResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `progress` | 是 | number |  |  |
| `message` | 是 | string |  |  |
| `stage` | 否 | string / null |  |  |
| `updated_at` | 否 | string (date-time) / null |  |  |
| `analysis_result` | 否 | [AnalysisResult](#schema-analysisresult) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "title": "Progress"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "stage": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Stage"
    },
    "updated_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Updated At"
    },
    "analysis_result": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/AnalysisResult"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "status",
    "progress",
    "message"
  ],
  "title": "AnalyzeTaskResponse",
  "description": "异步分析任务响应"
}
```

</details>

<a id="schema-anomalydetectionresponse"></a>

### `AnomalyDetectionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `anomalies` | 是 | array&lt;[AnomalyItem](#schema-anomalyitem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "anomalies": {
      "items": {
        "$ref": "#/components/schemas/AnomalyItem"
      },
      "type": "array",
      "title": "Anomalies"
    }
  },
  "type": "object",
  "required": [
    "anomalies"
  ],
  "title": "AnomalyDetectionResponse"
}
```

</details>

<a id="schema-anomalyitem"></a>

### `AnomalyItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | 是 | string |  |  |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `value` | 是 | number |  |  |
| `severity` | 是 | string |  |  |
| `avg_value` | 否 | number / null |  |  |
| `z_score` | 否 | number / null |  |  |
| `top_api` | 否 | string / null |  |  |
| `api_calls` | 否 | integer / null |  |  |
| `total_calls` | 否 | integer / null |  |  |
| `days_since_registration` | 否 | integer / null |  |  |
| `calls_per_day` | 否 | number / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "type": {
      "type": "string",
      "title": "Type"
    },
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "value": {
      "type": "number",
      "title": "Value"
    },
    "severity": {
      "type": "string",
      "title": "Severity"
    },
    "avg_value": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Avg Value"
    },
    "z_score": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Z Score"
    },
    "top_api": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Top Api"
    },
    "api_calls": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Api Calls"
    },
    "total_calls": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Total Calls"
    },
    "days_since_registration": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Days Since Registration"
    },
    "calls_per_day": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Calls Per Day"
    }
  },
  "type": "object",
  "required": [
    "type",
    "user_id",
    "username",
    "value",
    "severity"
  ],
  "title": "AnomalyItem"
}
```

</details>

<a id="schema-apiusagestat"></a>

### `ApiUsageStat`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | 是 | string |  |  |
| `count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path": {
      "type": "string",
      "title": "Path"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    }
  },
  "type": "object",
  "required": [
    "path",
    "count"
  ],
  "title": "ApiUsageStat"
}
```

</details>

<a id="schema-availableapisresponse"></a>

### `AvailableApisResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `apis` | 是 | array&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "apis": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Apis"
    }
  },
  "type": "object",
  "required": [
    "apis"
  ],
  "title": "AvailableApisResponse",
  "description": "可用API列表响应"
}
```

</details>

<a id="schema-batchcomparerequest"></a>

### `BatchCompareRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `regions` | 是 | array&lt;[RegionSpec](#schema-regionspec)&gt; |  |  |
| `run_id` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "regions": {
      "items": {
        "$ref": "#/components/schemas/RegionSpec"
      },
      "type": "array",
      "title": "Regions"
    },
    "run_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "regions"
  ],
  "title": "BatchCompareRequest",
  "description": "批量向量比较请求模型"
}
```

</details>

<a id="schema-batchcompareresponse"></a>

### `BatchCompareResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `regions` | 是 | array&lt;object&gt; |  |  |
| `similarity_matrix` | 是 | array&lt;array&lt;number&gt;&gt; |  |  |
| `distance_matrix` | 是 | array&lt;array&lt;number&gt;&gt; |  |  |
| `feature_dimension` | 是 | integer |  |  |
| `categories` | 是 | array&lt;string&gt; |  |  |
| `run_id` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "regions": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Regions"
    },
    "similarity_matrix": {
      "items": {
        "items": {
          "type": "number"
        },
        "type": "array"
      },
      "type": "array",
      "title": "Similarity Matrix"
    },
    "distance_matrix": {
      "items": {
        "items": {
          "type": "number"
        },
        "type": "array"
      },
      "type": "array",
      "title": "Distance Matrix"
    },
    "feature_dimension": {
      "type": "integer",
      "title": "Feature Dimension"
    },
    "categories": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Categories"
    },
    "run_id": {
      "type": "string",
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "regions",
    "similarity_matrix",
    "distance_matrix",
    "feature_dimension",
    "categories",
    "run_id"
  ],
  "title": "BatchCompareResponse",
  "description": "批量向量比较响应模型"
}
```

</details>

<a id="schema-body_create_upload_api_tools_praat_uploads_post"></a>

### `Body_create_upload_api_tools_praat_uploads_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | 是 | string (binary) |  |  |
| `retain_original` | 否 | boolean | default=false |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "file": {
      "type": "string",
      "format": "binary",
      "title": "File"
    },
    "retain_original": {
      "type": "boolean",
      "title": "Retain Original",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "file"
  ],
  "title": "Body_create_upload_api_tools_praat_uploads_post"
}
```

</details>

<a id="schema-body_login_api_auth_login_post"></a>

### `Body_login_api_auth_login_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `grant_type` | 否 | string / null |  |  |
| `username` | 是 | string |  |  |
| `password` | 是 | string (password) |  |  |
| `scope` | 否 | string | default="" |  |
| `client_id` | 否 | string / null |  |  |
| `client_secret` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "grant_type": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^password$"
        },
        {
          "type": "null"
        }
      ],
      "title": "Grant Type"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "password": {
      "type": "string",
      "format": "password",
      "title": "Password"
    },
    "scope": {
      "type": "string",
      "title": "Scope",
      "default": ""
    },
    "client_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Client Id"
    },
    "client_secret": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "password",
      "title": "Client Secret"
    }
  },
  "type": "object",
  "required": [
    "username",
    "password"
  ],
  "title": "Body_login_api_auth_login_post"
}
```

</details>

<a id="schema-body_logout_api_auth_logout_post"></a>

### `Body_logout_api_auth_logout_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `refresh_token` | 否 | string / null |  |  |
| `logout_all` | 否 | boolean | default=false |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "refresh_token": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Refresh Token"
    },
    "logout_all": {
      "type": "boolean",
      "title": "Logout All",
      "default": false
    }
  },
  "type": "object",
  "title": "Body_logout_api_auth_logout_post"
}
```

</details>

<a id="schema-body_preview_vocabulary_upload_endpoint_api_vocabulary_imports_preview_post"></a>

### `Body_preview_vocabulary_upload_endpoint_api_vocabulary_imports_preview_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | 是 | string (binary) |  |  |
| `location` | 是 | string |  |  |
| `parser_mode` | 否 | string | default="auto" |  |
| `fill_standard_from_local` | 否 | boolean | default=false |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "file": {
      "type": "string",
      "format": "binary",
      "title": "File"
    },
    "location": {
      "type": "string",
      "title": "Location"
    },
    "parser_mode": {
      "type": "string",
      "title": "Parser Mode",
      "default": "auto"
    },
    "fill_standard_from_local": {
      "type": "boolean",
      "title": "Fill Standard From Local",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "file",
    "location"
  ],
  "title": "Body_preview_vocabulary_upload_endpoint_api_vocabulary_imports_preview_post"
}
```

</details>

<a id="schema-body_refresh_api_auth_refresh_post"></a>

### `Body_refresh_api_auth_refresh_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `refresh_token` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "refresh_token": {
      "type": "string",
      "title": "Refresh Token"
    }
  },
  "type": "object",
  "required": [
    "refresh_token"
  ],
  "title": "Body_refresh_api_auth_refresh_post"
}
```

</details>

<a id="schema-body_report_online_time_api_auth_report_online_time_post"></a>

### `Body_report_online_time_api_auth_report_online_time_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `seconds` | 是 | integer | minimum=1.0; maximum=3600.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "seconds": {
      "type": "integer",
      "maximum": 3600.0,
      "minimum": 1.0,
      "title": "Seconds"
    }
  },
  "type": "object",
  "required": [
    "seconds"
  ],
  "title": "Body_report_online_time_api_auth_report_online_time_post"
}
```

</details>

<a id="schema-body_update_profile_api_auth_updateprofile_put"></a>

### `Body_update_profile_api_auth_updateProfile_put`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 否 | string |  |  |
| `email` | 否 | string |  |  |
| `password` | 否 | string |  |  |
| `new_password` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "title": "Email"
    },
    "password": {
      "type": "string",
      "title": "Password"
    },
    "new_password": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "New Password"
    }
  },
  "type": "object",
  "title": "Body_update_profile_api_auth_updateProfile_put"
}
```

</details>

<a id="schema-body_upload_file_api_tools_check_upload_post"></a>

### `Body_upload_file_api_tools_check_upload_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | 是 | string (binary) |  |  |
| `format_type` | 否 | string / null |  |  |
| `level` | 否 | integer | default=0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "file": {
      "type": "string",
      "format": "binary",
      "title": "File"
    },
    "format_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Format Type"
    },
    "level": {
      "type": "integer",
      "title": "Level",
      "default": 0
    }
  },
  "type": "object",
  "required": [
    "file"
  ],
  "title": "Body_upload_file_api_tools_check_upload_post"
}
```

</details>

<a id="schema-body_upload_file_api_tools_jyut2ipa_upload_post"></a>

### `Body_upload_file_api_tools_jyut2ipa_upload_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | 是 | string (binary) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "file": {
      "type": "string",
      "format": "binary",
      "title": "File"
    }
  },
  "type": "object",
  "required": [
    "file"
  ],
  "title": "Body_upload_file_api_tools_jyut2ipa_upload_post"
}
```

</details>

<a id="schema-body_upload_merge_files_api_tools_merge_upload_files_post"></a>

### `Body_upload_merge_files_api_tools_merge_upload_files_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `files` | 是 | array&lt;string (binary)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "files": {
      "items": {
        "type": "string",
        "format": "binary"
      },
      "type": "array",
      "title": "Files"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "files"
  ],
  "title": "Body_upload_merge_files_api_tools_merge_upload_files_post"
}
```

</details>

<a id="schema-body_upload_reference_api_tools_merge_upload_reference_post"></a>

### `Body_upload_reference_api_tools_merge_upload_reference_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | 是 | string (binary) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "file": {
      "type": "string",
      "format": "binary",
      "title": "File"
    }
  },
  "type": "object",
  "required": [
    "file"
  ],
  "title": "Body_upload_reference_api_tools_merge_upload_reference_post"
}
```

</details>

<a id="schema-body_upload_vocabulary_api_vocabulary_imports_post"></a>

### `Body_upload_vocabulary_api_vocabulary_imports_post`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | 是 | string (binary) |  |  |
| `location` | 是 | string |  |  |
| `parser_mode` | 否 | string | default="auto" |  |
| `overwrite` | 否 | boolean | default=false |  |
| `fill_standard_from_local` | 否 | boolean | default=false |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "file": {
      "type": "string",
      "format": "binary",
      "title": "File"
    },
    "location": {
      "type": "string",
      "title": "Location"
    },
    "parser_mode": {
      "type": "string",
      "title": "Parser Mode",
      "default": "auto"
    },
    "overwrite": {
      "type": "boolean",
      "title": "Overwrite",
      "default": false
    },
    "fill_standard_from_local": {
      "type": "boolean",
      "title": "Fill Standard From Local",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "file",
    "location"
  ],
  "title": "Body_upload_vocabulary_api_vocabulary_imports_post"
}
```

</details>

<a id="schema-charfrequency"></a>

### `CharFrequency`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `character` | 是 | string |  | 字符 |
| `frequency` | 是 | number |  | 出现频次 |
| `village_count` | 是 | integer |  | 村庄数量 |
| `rank` | 是 | integer |  | 排名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "character": {
      "type": "string",
      "title": "Character",
      "description": "字符"
    },
    "frequency": {
      "type": "number",
      "title": "Frequency",
      "description": "出现频次"
    },
    "village_count": {
      "type": "integer",
      "title": "Village Count",
      "description": "村庄数量"
    },
    "rank": {
      "type": "integer",
      "title": "Rank",
      "description": "排名"
    }
  },
  "type": "object",
  "required": [
    "character",
    "frequency",
    "village_count",
    "rank"
  ],
  "title": "CharFrequency",
  "description": "字符频率模型"
}
```

</details>

<a id="schema-charlistrequest"></a>

### `CharListRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path_strings` | 否 | array&lt;string&gt; / null |  |  |
| `column` | 否 | array&lt;string&gt; / null |  |  |
| `combine_query` | 否 | boolean | default=false |  |
| `exclude_columns` | 否 | array&lt;string&gt; / null |  | 要排除的列名列表，如 ['多地位標記', '多等'] |
| `table_name` | 否 | string | default="characters" | 字符數據庫表名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path_strings": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Path Strings"
    },
    "column": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Column"
    },
    "combine_query": {
      "type": "boolean",
      "title": "Combine Query",
      "default": false
    },
    "exclude_columns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Columns",
      "description": "要排除的列名列表，如 ['多地位標記', '多等']"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "字符數據庫表名",
      "default": "characters"
    }
  },
  "type": "object",
  "title": "CharListRequest"
}
```

</details>

<a id="schema-chartendency"></a>

### `CharTendency`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `character` | 是 | string |  | 字符 |
| `lift` | 是 | number |  | Lift值 |
| `log_odds` | 是 | number |  | Log-odds值 |
| `z_score` | 是 | number |  | Z-score值 |
| `rank` | 是 | integer |  | 排名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "character": {
      "type": "string",
      "title": "Character",
      "description": "字符"
    },
    "lift": {
      "type": "number",
      "title": "Lift",
      "description": "Lift值"
    },
    "log_odds": {
      "type": "number",
      "title": "Log Odds",
      "description": "Log-odds值"
    },
    "z_score": {
      "type": "number",
      "title": "Z Score",
      "description": "Z-score值"
    },
    "rank": {
      "type": "integer",
      "title": "Rank",
      "description": "排名"
    }
  },
  "type": "object",
  "required": [
    "character",
    "lift",
    "log_odds",
    "z_score",
    "rank"
  ],
  "title": "CharTendency",
  "description": "字符倾向性模型"
}
```

</details>

<a id="schema-chartendencybyregion"></a>

### `CharTendencyByRegion`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_level` | 是 | string |  | 区域级别 |
| `region_name` | 是 | string |  | 区域名称 |
| `city` | 否 | string / null |  | 市级 |
| `county` | 否 | string / null |  | 区县级 |
| `township` | 否 | string / null |  | 乡镇级 |
| `lift` | 是 | number |  | Lift值 |
| `z_score` | 是 | number |  | Z-score值 |
| `centroid_lon` | 否 | number / null |  | 区域中心点经度 |
| `centroid_lat` | 否 | number / null |  | 区域中心点纬度 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_level": {
      "type": "string",
      "title": "Region Level",
      "description": "区域级别"
    },
    "region_name": {
      "type": "string",
      "title": "Region Name",
      "description": "区域名称"
    },
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City",
      "description": "市级"
    },
    "county": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County",
      "description": "区县级"
    },
    "township": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township",
      "description": "乡镇级"
    },
    "lift": {
      "type": "number",
      "title": "Lift",
      "description": "Lift值"
    },
    "z_score": {
      "type": "number",
      "title": "Z Score",
      "description": "Z-score值"
    },
    "centroid_lon": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Centroid Lon",
      "description": "区域中心点经度"
    },
    "centroid_lat": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Centroid Lat",
      "description": "区域中心点纬度"
    }
  },
  "type": "object",
  "required": [
    "region_level",
    "region_name",
    "lift",
    "z_score"
  ],
  "title": "CharTendencyByRegion",
  "description": "按字符查询的区域倾向性"
}
```

</details>

<a id="schema-characternetworkedge"></a>

### `CharacterNetworkEdge`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `source` | 是 | string |  | 源字符 |
| `target` | 是 | string |  | 目标字符 |
| `similarity` | 是 | number |  | 相似度 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "source": {
      "type": "string",
      "title": "Source",
      "description": "源字符"
    },
    "target": {
      "type": "string",
      "title": "Target",
      "description": "目标字符"
    },
    "similarity": {
      "type": "number",
      "title": "Similarity",
      "description": "相似度"
    }
  },
  "type": "object",
  "required": [
    "source",
    "target",
    "similarity"
  ],
  "title": "CharacterNetworkEdge",
  "description": "字符网络边模型"
}
```

</details>

<a id="schema-characternetworkrequest"></a>

### `CharacterNetworkRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `root_char` | 是 | string | minLength=1; maxLength=1 | 根字符 |
| `depth` | 否 | integer | default=2; minimum=1.0; maximum=4.0 | BFS 扩展深度 |
| `top_k` | 否 | integer | default=5; minimum=1.0; maximum=10.0 | 每节点保留前 K 个相似字 |
| `min_similarity` | 否 | number | default=0.3; minimum=0.0; maximum=1.0 | 相似度阈值 |
| `max_nodes` | 否 | integer | default=50; minimum=10.0; maximum=1000.0 | 最大节点数上限 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "root_char": {
      "type": "string",
      "maxLength": 1,
      "minLength": 1,
      "title": "Root Char",
      "description": "根字符"
    },
    "depth": {
      "type": "integer",
      "maximum": 4.0,
      "minimum": 1.0,
      "title": "Depth",
      "description": "BFS 扩展深度",
      "default": 2
    },
    "top_k": {
      "type": "integer",
      "maximum": 10.0,
      "minimum": 1.0,
      "title": "Top K",
      "description": "每节点保留前 K 个相似字",
      "default": 5
    },
    "min_similarity": {
      "type": "number",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Min Similarity",
      "description": "相似度阈值",
      "default": 0.3
    },
    "max_nodes": {
      "type": "integer",
      "maximum": 1000.0,
      "minimum": 10.0,
      "title": "Max Nodes",
      "description": "最大节点数上限",
      "default": 50
    }
  },
  "type": "object",
  "required": [
    "root_char"
  ],
  "title": "CharacterNetworkRequest",
  "description": "字符网络请求模型"
}
```

</details>

<a id="schema-characternetworkresponse"></a>

### `CharacterNetworkResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `nodes` | 是 | array&lt;[NetworkNode](#schema-networknode)&gt; |  | 节点列表 |
| `edges` | 是 | array&lt;[CharacterNetworkEdge](#schema-characternetworkedge)&gt; |  | 边列表 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "nodes": {
      "items": {
        "$ref": "#/components/schemas/NetworkNode"
      },
      "type": "array",
      "title": "Nodes",
      "description": "节点列表"
    },
    "edges": {
      "items": {
        "$ref": "#/components/schemas/CharacterNetworkEdge"
      },
      "type": "array",
      "title": "Edges",
      "description": "边列表"
    }
  },
  "type": "object",
  "required": [
    "nodes",
    "edges"
  ],
  "title": "CharacterNetworkResponse",
  "description": "字符网络响应模型"
}
```

</details>

<a id="schema-charactertendencyclusteringparams"></a>

### `CharacterTendencyClusteringParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [AlgorithmType](#schema-algorithmtype) |  |  |
| `k` | 否 | integer / null |  |  |
| `region_level` | 是 | [RegionLevel](#schema-regionlevel) |  |  |
| `region_filter` | 否 | array&lt;string&gt; / null |  |  |
| `top_n_chars` | 否 | integer | default=100; minimum=10.0; maximum=500.0 | 每个区域选择top N字符 |
| `tendency_metric` | 否 | [TendencyMetric](#schema-tendencymetric) | default="z_score" |  |
| `preprocessing` | 否 | [PreprocessingConfig](#schema-preprocessingconfig) |  |  |
| `dbscan_config` | 否 | [DBSCANConfig](#schema-dbscanconfig) |  |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/AlgorithmType"
    },
    "k": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 20.0,
          "minimum": 2.0
        },
        {
          "type": "null"
        }
      ],
      "title": "K"
    },
    "region_level": {
      "$ref": "#/components/schemas/RegionLevel"
    },
    "region_filter": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region Filter"
    },
    "top_n_chars": {
      "type": "integer",
      "maximum": 500.0,
      "minimum": 10.0,
      "title": "Top N Chars",
      "description": "每个区域选择top N字符",
      "default": 100
    },
    "tendency_metric": {
      "$ref": "#/components/schemas/TendencyMetric",
      "default": "z_score"
    },
    "preprocessing": {
      "$ref": "#/components/schemas/PreprocessingConfig"
    },
    "dbscan_config": {
      "$ref": "#/components/schemas/DBSCANConfig"
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    }
  },
  "type": "object",
  "required": [
    "algorithm",
    "region_level"
  ],
  "title": "CharacterTendencyClusteringParams",
  "description": "字符倾向性聚类参数"
}
```

</details>

<a id="schema-clusteralgorithm"></a>

### `ClusterAlgorithm`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "agglomerative",
    "dbscan",
    "kmeans",
    "gmm"
  ],
  "title": "ClusterAlgorithm",
  "description": "当前支持的四种聚类器。"
}
```

</details>

<a id="schema-clusteralgorithmconfigrequest"></a>

### `ClusterAlgorithmConfigRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [ClusterAlgorithm](#schema-clusteralgorithm) |  |  |
| `n_clusters` | 否 | integer / null |  |  |
| `linkage` | 否 | [AgglomerativeLinkage](#schema-agglomerativelinkage) | default="average" |  |
| `eps` | 否 | number | default=0.5; maximum=10.0; exclusiveMinimum=0.0 |  |
| `min_samples` | 否 | integer | default=5; minimum=1.0; maximum=100.0 |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/ClusterAlgorithm"
    },
    "n_clusters": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 100.0,
          "minimum": 2.0
        },
        {
          "type": "null"
        }
      ],
      "title": "N Clusters"
    },
    "linkage": {
      "$ref": "#/components/schemas/AgglomerativeLinkage",
      "default": "average"
    },
    "eps": {
      "type": "number",
      "maximum": 10.0,
      "exclusiveMinimum": 0.0,
      "title": "Eps",
      "default": 0.5
    },
    "min_samples": {
      "type": "integer",
      "maximum": 100.0,
      "minimum": 1.0,
      "title": "Min Samples",
      "default": 5
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    }
  },
  "type": "object",
  "required": [
    "algorithm"
  ],
  "title": "ClusterAlgorithmConfigRequest",
  "description": "纯聚类器配置；staged API 的最后一步只需要这部分参数。"
}
```

</details>

<a id="schema-clusterassignment"></a>

### `ClusterAssignment`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_name` | 是 | string |  | 区域名称 |
| `cluster_id` | 是 | integer |  | 聚类ID |
| `distance_to_centroid` | 否 | number / null |  | 到中心距离 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_name": {
      "type": "string",
      "title": "Region Name",
      "description": "区域名称"
    },
    "cluster_id": {
      "type": "integer",
      "title": "Cluster Id",
      "description": "聚类ID"
    },
    "distance_to_centroid": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Distance To Centroid",
      "description": "到中心距离"
    }
  },
  "type": "object",
  "required": [
    "region_name",
    "cluster_id"
  ],
  "title": "ClusterAssignment",
  "description": "聚类分配模型"
}
```

</details>

<a id="schema-clustercomparedimension"></a>

### `ClusterCompareDimension`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "initial",
    "final",
    "tone"
  ],
  "title": "ClusterCompareDimension",
  "description": "当前 group 比较的是声母、韵母还是声调。"
}
```

</details>

<a id="schema-clusterconfigrequest"></a>

### `ClusterConfigRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [ClusterAlgorithm](#schema-clusteralgorithm) |  |  |
| `n_clusters` | 否 | integer / null |  |  |
| `linkage` | 否 | [AgglomerativeLinkage](#schema-agglomerativelinkage) | default="average" |  |
| `eps` | 否 | number | default=0.5; maximum=10.0; exclusiveMinimum=0.0 |  |
| `min_samples` | 否 | integer | default=5; minimum=1.0; maximum=100.0 |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |
| `phoneme_mode` | 否 | [ClusterPhonemeMode](#schema-clusterphonememode) | default="intra_group" |  |
| `metric_mode` | 否 | [ClusterMetricMode](#schema-clustermetricmode) / null |  | Deprecated legacy field. Use phoneme_mode instead. |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/ClusterAlgorithm"
    },
    "n_clusters": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 100.0,
          "minimum": 2.0
        },
        {
          "type": "null"
        }
      ],
      "title": "N Clusters"
    },
    "linkage": {
      "$ref": "#/components/schemas/AgglomerativeLinkage",
      "default": "average"
    },
    "eps": {
      "type": "number",
      "maximum": 10.0,
      "exclusiveMinimum": 0.0,
      "title": "Eps",
      "default": 0.5
    },
    "min_samples": {
      "type": "integer",
      "maximum": 100.0,
      "minimum": 1.0,
      "title": "Min Samples",
      "default": 5
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    },
    "phoneme_mode": {
      "$ref": "#/components/schemas/ClusterPhonemeMode",
      "default": "intra_group"
    },
    "metric_mode": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/ClusterMetricMode"
        },
        {
          "type": "null"
        }
      ],
      "description": "Deprecated legacy field. Use phoneme_mode instead."
    }
  },
  "type": "object",
  "required": [
    "algorithm"
  ],
  "title": "ClusterConfigRequest",
  "description": "旧 one-shot API 使用的完整配置，包含 phoneme_mode。"
}
```

</details>

<a id="schema-clustergrouprequest"></a>

### `ClusterGroupRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `label` | 否 | string / null |  |  |
| `source_mode` | 是 | [ClusterSourceMode](#schema-clustersourcemode) |  |  |
| `table_name` | 否 | string | default="characters" |  |
| `path_strings` | 否 | array&lt;string&gt; / null |  | Optional charlist-compatible query payload. |
| `column` | 否 | array&lt;string&gt; / null |  |  |
| `combine_query` | 否 | boolean | default=false |  |
| `filters` | 否 | object&lt;array&lt;string&gt;&gt; / null |  | Structured preset filters: OR within field, AND across fields. |
| `exclude_columns` | 否 | array&lt;string&gt; / null |  |  |
| `custom_chars` | 否 | string / array&lt;string&gt; / null |  |  |
| `resolved_chars` | 否 | string / array&lt;string&gt; / null |  | Optional already-resolved character list shortcut. |
| `compare_dimension` | 是 | [ClusterCompareDimension](#schema-clustercomparedimension) |  |  |
| `group_weight` | 否 | number | default=1.0; exclusiveMinimum=0.0 |  |
| `use_phonetic_values` | 否 | boolean | default=false |  |
| `phonetic_value_weight` | 否 | number | default=0.2; minimum=0.0; maximum=1.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "label": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 100
        },
        {
          "type": "null"
        }
      ],
      "title": "Label"
    },
    "source_mode": {
      "$ref": "#/components/schemas/ClusterSourceMode"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "characters"
    },
    "path_strings": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Path Strings",
      "description": "Optional charlist-compatible query payload."
    },
    "column": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Column"
    },
    "combine_query": {
      "type": "boolean",
      "title": "Combine Query",
      "default": false
    },
    "filters": {
      "anyOf": [
        {
          "additionalProperties": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Filters",
      "description": "Structured preset filters: OR within field, AND across fields."
    },
    "exclude_columns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Columns"
    },
    "custom_chars": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Custom Chars"
    },
    "resolved_chars": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Resolved Chars",
      "description": "Optional already-resolved character list shortcut."
    },
    "compare_dimension": {
      "$ref": "#/components/schemas/ClusterCompareDimension"
    },
    "group_weight": {
      "type": "number",
      "exclusiveMinimum": 0.0,
      "title": "Group Weight",
      "default": 1.0
    },
    "use_phonetic_values": {
      "type": "boolean",
      "title": "Use Phonetic Values",
      "default": false
    },
    "phonetic_value_weight": {
      "type": "number",
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Phonetic Value Weight",
      "default": 0.2
    }
  },
  "type": "object",
  "required": [
    "source_mode",
    "compare_dimension"
  ],
  "title": "ClusterGroupRequest",
  "description": "单个 group 的请求结构。\n\n可以把一个 group 理解为：\n“从某个来源解析出一组汉字，然后在某个音系维度上比较所有地点。”\n\n例如 16 摄聚韵母时，通常就是 16 个 group，每个 group 对应一个摄。"
}
```

</details>

<a id="schema-clusterjobcreaterequest"></a>

### `ClusterJobCreateRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `groups` | 是 | array&lt;[ClusterGroupRequest](#schema-clustergrouprequest)&gt; | minItems=1 |  |
| `locations` | 否 | array&lt;string&gt; |  |  |
| `regions` | 否 | array&lt;string&gt; |  |  |
| `region_mode` | 否 | string | default="yindian" | yindian or map |
| `include_special_locations` | 否 | boolean | default=false | 是否保留域外方音/歷史音/標準語/民語漢字音等特殊點；默認 false 會過濾 |
| `clustering` | 是 | [ClusterConfigRequest](#schema-clusterconfigrequest) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "groups": {
      "items": {
        "$ref": "#/components/schemas/ClusterGroupRequest"
      },
      "type": "array",
      "minItems": 1,
      "title": "Groups"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations"
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions"
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "description": "yindian or map",
      "default": "yindian"
    },
    "include_special_locations": {
      "type": "boolean",
      "title": "Include Special Locations",
      "description": "是否保留域外方音/歷史音/標準語/民語漢字音等特殊點；默認 false 會過濾",
      "default": false
    },
    "clustering": {
      "$ref": "#/components/schemas/ClusterConfigRequest"
    }
  },
  "type": "object",
  "required": [
    "groups",
    "clustering"
  ],
  "title": "ClusterJobCreateRequest",
  "description": "旧 one-shot cluster API 的请求结构。"
}
```

</details>

<a id="schema-clusterjobcreateresponse"></a>

### `ClusterJobCreateResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `progress` | 是 | number |  |  |
| `message` | 是 | string |  |  |
| `summary` | 否 | object / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "title": "Progress"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "summary": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Summary"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "status",
    "progress",
    "message"
  ],
  "title": "ClusterJobCreateResponse",
  "description": "创建任务后返回给前端的最小任务摘要。"
}
```

</details>

<a id="schema-clusterjobstatusresponse"></a>

### `ClusterJobStatusResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `progress` | 是 | number |  |  |
| `message` | 是 | string |  |  |
| `created_at` | 是 | number |  |  |
| `updated_at` | 是 | number |  |  |
| `summary` | 否 | object / null |  |  |
| `execution_time_ms` | 否 | integer / null |  |  |
| `performance` | 否 | object / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "title": "Progress"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "created_at": {
      "type": "number",
      "title": "Created At"
    },
    "updated_at": {
      "type": "number",
      "title": "Updated At"
    },
    "summary": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Summary"
    },
    "execution_time_ms": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Execution Time Ms"
    },
    "performance": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Performance"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "status",
    "progress",
    "message",
    "created_at",
    "updated_at"
  ],
  "title": "ClusterJobStatusResponse",
  "description": "任务轮询响应，包含进度、耗时与性能分段信息。"
}
```

</details>

<a id="schema-clustermetricmode"></a>

### `ClusterMetricMode`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "correspondence",
    "system_profile",
    "homophony_embedding",
    "hybrid_phonology"
  ],
  "title": "ClusterMetricMode",
  "description": "旧字段，保留兼容；当前计算主线已经改为 phoneme_mode。"
}
```

</details>

<a id="schema-clusterphonememode"></a>

### `ClusterPhonemeMode`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "intra_group",
    "anchored_inventory",
    "shared_request_identity"
  ],
  "title": "ClusterPhonemeMode",
  "description": "三种音系距离模式。"
}
```

</details>

<a id="schema-clusterrequest"></a>

### `ClusterRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `regions` | 是 | array&lt;[RegionSpec](#schema-regionspec)&gt; |  |  |
| `method` | 否 | string | default="kmeans" |  |
| `n_clusters` | 否 | integer / null |  |  |
| `eps` | 否 | number / null |  |  |
| `min_samples` | 否 | integer / null |  |  |
| `run_id` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "regions": {
      "items": {
        "$ref": "#/components/schemas/RegionSpec"
      },
      "type": "array",
      "title": "Regions"
    },
    "method": {
      "type": "string",
      "title": "Method",
      "default": "kmeans"
    },
    "n_clusters": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "N Clusters"
    },
    "eps": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Eps"
    },
    "min_samples": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Min Samples"
    },
    "run_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "regions"
  ],
  "title": "ClusterRequest",
  "description": "向量聚类请求模型"
}
```

</details>

<a id="schema-clusterresponse"></a>

### `ClusterResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `regions` | 是 | array&lt;object&gt; |  |  |
| `labels` | 是 | array&lt;integer&gt; |  |  |
| `n_clusters` | 是 | integer |  |  |
| `cluster_centers` | 否 | array&lt;array&lt;number&gt;&gt; / null |  |  |
| `method` | 是 | string |  |  |
| `run_id` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "regions": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Regions"
    },
    "labels": {
      "items": {
        "type": "integer"
      },
      "type": "array",
      "title": "Labels"
    },
    "n_clusters": {
      "type": "integer",
      "title": "N Clusters"
    },
    "cluster_centers": {
      "anyOf": [
        {
          "items": {
            "items": {
              "type": "number"
            },
            "type": "array"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Cluster Centers"
    },
    "method": {
      "type": "string",
      "title": "Method"
    },
    "run_id": {
      "type": "string",
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "regions",
    "labels",
    "n_clusters",
    "method",
    "run_id"
  ],
  "title": "ClusterResponse",
  "description": "向量聚类响应模型"
}
```

</details>

<a id="schema-clustersourcemode"></a>

### `ClusterSourceMode`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "preset",
    "custom"
  ],
  "title": "ClusterSourceMode",
  "description": "group 字集来源：预设字表查询或直接自定义字串。"
}
```

</details>

<a id="schema-clusterstageclusterrequest"></a>

### `ClusterStageClusterRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `distance_hash` | 是 | string | minLength=1; maxLength=128 |  |
| `clustering` | 是 | [ClusterAlgorithmConfigRequest](#schema-clusteralgorithmconfigrequest) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "distance_hash": {
      "type": "string",
      "maxLength": 128,
      "minLength": 1,
      "title": "Distance Hash"
    },
    "clustering": {
      "$ref": "#/components/schemas/ClusterAlgorithmConfigRequest"
    }
  },
  "type": "object",
  "required": [
    "distance_hash",
    "clustering"
  ],
  "title": "ClusterStageClusterRequest",
  "description": "staged API 的 cluster 阶段请求。"
}
```

</details>

<a id="schema-clusterstagedistancerequest"></a>

### `ClusterStageDistanceRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `prepare_hash` | 是 | string | minLength=1; maxLength=128 |  |
| `phoneme_mode` | 是 | [ClusterPhonemeMode](#schema-clusterphonememode) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "prepare_hash": {
      "type": "string",
      "maxLength": 128,
      "minLength": 1,
      "title": "Prepare Hash"
    },
    "phoneme_mode": {
      "$ref": "#/components/schemas/ClusterPhonemeMode"
    }
  },
  "type": "object",
  "required": [
    "prepare_hash",
    "phoneme_mode"
  ],
  "title": "ClusterStageDistanceRequest",
  "description": "staged API 的 distance 阶段请求。"
}
```

</details>

<a id="schema-clusterstagepreparerequest"></a>

### `ClusterStagePrepareRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `prepare_hash` | 是 | string | minLength=1; maxLength=128 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "prepare_hash": {
      "type": "string",
      "maxLength": 128,
      "minLength": 1,
      "title": "Prepare Hash"
    }
  },
  "type": "object",
  "required": [
    "prepare_hash"
  ],
  "title": "ClusterStagePrepareRequest",
  "description": "staged prepare 阶段请求。"
}
```

</details>

<a id="schema-clusterstagepreviewrequest"></a>

### `ClusterStagePreviewRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `groups` | 是 | array&lt;[ClusterGroupRequest](#schema-clustergrouprequest)&gt; | minItems=1 |  |
| `locations` | 否 | array&lt;string&gt; |  |  |
| `regions` | 否 | array&lt;string&gt; |  |  |
| `region_mode` | 否 | string | default="yindian" | yindian or map |
| `include_special_locations` | 否 | boolean | default=false | 是否保留域外方音/歷史音/標準語/民語漢字音等特殊點；默認 false 會過濾 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "groups": {
      "items": {
        "$ref": "#/components/schemas/ClusterGroupRequest"
      },
      "type": "array",
      "minItems": 1,
      "title": "Groups"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations"
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions"
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "description": "yindian or map",
      "default": "yindian"
    },
    "include_special_locations": {
      "type": "boolean",
      "title": "Include Special Locations",
      "description": "是否保留域外方音/歷史音/標準語/民語漢字音等特殊點；默認 false 會過濾",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "groups"
  ],
  "title": "ClusterStagePreviewRequest",
  "description": "staged preview/prepare 的完整输入请求。"
}
```

</details>

<a id="schema-clusterstagepreviewresponse"></a>

### `ClusterStagePreviewResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `prepare_hash` | 是 | string |  |  |
| `preview` | 是 | object |  |  |
| `prepare_ready` | 否 | boolean | default=false |  |
| `preview_expires_at` | 否 | number / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "prepare_hash": {
      "type": "string",
      "title": "Prepare Hash"
    },
    "preview": {
      "additionalProperties": true,
      "type": "object",
      "title": "Preview"
    },
    "prepare_ready": {
      "type": "boolean",
      "title": "Prepare Ready",
      "default": false
    },
    "preview_expires_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Preview Expires At"
    }
  },
  "type": "object",
  "required": [
    "prepare_hash",
    "preview"
  ],
  "title": "ClusterStagePreviewResponse",
  "description": "staged preview 返回的轻量摘要。"
}
```

</details>

<a id="schema-clusterstagetaskresponse"></a>

### `ClusterStageTaskResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `stage` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `progress` | 是 | number |  |  |
| `message` | 是 | string |  |  |
| `summary` | 否 | object / null |  |  |
| `execution_time_ms` | 否 | integer / null |  |  |
| `performance` | 否 | object / null |  |  |
| `prepare_hash` | 否 | string / null |  |  |
| `distance_hash` | 否 | string / null |  |  |
| `result_hash` | 否 | string / null |  |  |
| `cache_hit` | 否 | boolean | default=false |  |
| `cache_source` | 否 | string | default="none" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "stage": {
      "type": "string",
      "title": "Stage"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "title": "Progress"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "summary": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Summary"
    },
    "execution_time_ms": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Execution Time Ms"
    },
    "performance": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Performance"
    },
    "prepare_hash": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Prepare Hash"
    },
    "distance_hash": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Distance Hash"
    },
    "result_hash": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Result Hash"
    },
    "cache_hit": {
      "type": "boolean",
      "title": "Cache Hit",
      "default": false
    },
    "cache_source": {
      "type": "string",
      "title": "Cache Source",
      "default": "none"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "stage",
    "status",
    "progress",
    "message"
  ],
  "title": "ClusterStageTaskResponse",
  "description": "staged prepare/distance/cluster 三个阶段的统一即时回执。"
}
```

</details>

<a id="schema-clusteringmetrics"></a>

### `ClusteringMetrics`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | string |  | 算法名称 |
| `k` | 是 | integer |  | 聚类数 |
| `silhouette_score` | 是 | number |  | 轮廓系数 |
| `davies_bouldin_index` | 是 | number |  | DB指数 |
| `calinski_harabasz_score` | 是 | number |  | CH分数 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "type": "string",
      "title": "Algorithm",
      "description": "算法名称"
    },
    "k": {
      "type": "integer",
      "title": "K",
      "description": "聚类数"
    },
    "silhouette_score": {
      "type": "number",
      "title": "Silhouette Score",
      "description": "轮廓系数"
    },
    "davies_bouldin_index": {
      "type": "number",
      "title": "Davies Bouldin Index",
      "description": "DB指数"
    },
    "calinski_harabasz_score": {
      "type": "number",
      "title": "Calinski Harabasz Score",
      "description": "CH分数"
    }
  },
  "type": "object",
  "required": [
    "algorithm",
    "k",
    "silhouette_score",
    "davies_bouldin_index",
    "calinski_harabasz_score"
  ],
  "title": "ClusteringMetrics",
  "description": "聚类指标模型"
}
```

</details>

<a id="schema-clusteringparams"></a>

### `ClusteringParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [AlgorithmType](#schema-algorithmtype) |  |  |
| `k` | 否 | integer / null |  |  |
| `region_level` | 是 | [RegionLevel](#schema-regionlevel) |  |  |
| `region_filter` | 否 | array&lt;string&gt; / null |  |  |
| `features` | 否 | [FeatureConfig](#schema-featureconfig) |  |  |
| `preprocessing` | 否 | [PreprocessingConfig](#schema-preprocessingconfig) |  |  |
| `dbscan_config` | 否 | [DBSCANConfig](#schema-dbscanconfig) / null |  |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/AlgorithmType"
    },
    "k": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 20.0,
          "minimum": 2.0
        },
        {
          "type": "null"
        }
      ],
      "title": "K"
    },
    "region_level": {
      "$ref": "#/components/schemas/RegionLevel"
    },
    "region_filter": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region Filter"
    },
    "features": {
      "$ref": "#/components/schemas/FeatureConfig"
    },
    "preprocessing": {
      "$ref": "#/components/schemas/PreprocessingConfig"
    },
    "dbscan_config": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/DBSCANConfig"
        },
        {
          "type": "null"
        }
      ]
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    }
  },
  "type": "object",
  "required": [
    "algorithm",
    "region_level"
  ],
  "title": "ClusteringParams",
  "description": "聚类参数验证"
}
```

</details>

<a id="schema-clusteringscanparams"></a>

### `ClusteringScanParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [AlgorithmType](#schema-algorithmtype) |  |  |
| `k_range` | 是 | array&lt;integer&gt; | minItems=2; maxItems=10 |  |
| `region_level` | 是 | [RegionLevel](#schema-regionlevel) |  |  |
| `features` | 否 | [FeatureConfig](#schema-featureconfig) |  |  |
| `metric` | 否 | string | default="silhouette_score"; pattern="^(silhouette_score&#124;davies_bouldin_index&#124;calinski_harabasz_score)$" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/AlgorithmType"
    },
    "k_range": {
      "items": {
        "type": "integer"
      },
      "type": "array",
      "maxItems": 10,
      "minItems": 2,
      "title": "K Range"
    },
    "region_level": {
      "$ref": "#/components/schemas/RegionLevel"
    },
    "features": {
      "$ref": "#/components/schemas/FeatureConfig"
    },
    "metric": {
      "type": "string",
      "pattern": "^(silhouette_score|davies_bouldin_index|calinski_harabasz_score)$",
      "title": "Metric",
      "default": "silhouette_score"
    }
  },
  "type": "object",
  "required": [
    "algorithm",
    "k_range",
    "region_level"
  ],
  "title": "ClusteringScanParams",
  "description": "聚类参数扫描"
}
```

</details>

<a id="schema-commandrequest"></a>

### `CommandRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `commands` | 是 | string / array&lt;string&gt; |  |  |
| `overwrite` | 否 | boolean / null | default=true |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "commands": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      ],
      "title": "Commands"
    },
    "overwrite": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "title": "Overwrite",
      "default": true
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "commands"
  ],
  "title": "CommandRequest"
}
```

</details>

<a id="schema-commandresponse"></a>

### `CommandResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 是 | boolean |  |  |
| `affected_rows` | 是 | integer |  |  |
| `message` | 是 | string |  |  |
| `logs` | 是 | array&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success"
    },
    "affected_rows": {
      "type": "integer",
      "title": "Affected Rows"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "logs": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Logs"
    }
  },
  "type": "object",
  "required": [
    "success",
    "affected_rows",
    "message",
    "logs"
  ],
  "title": "CommandResponse",
  "description": "命令执行响应"
}
```

</details>

<a id="schema-comparezhongguanalysis"></a>

### `CompareZhongGuAnalysis`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path_strings1` | 否 | array&lt;string&gt; / null |  | 第一组语音条件列表 |
| `chars1` | 否 | array&lt;string&gt; / null |  | 第一组可直接输入的汉字集合；每个元素若为多字串会自动拆字 |
| `column1` | 否 | array&lt;string&gt; / null |  | 第一组的额外排列组合字段 |
| `combine_query1` | 否 | boolean | default=false | 第一组是否开启交叉组合查询 |
| `exclude_columns1` | 否 | array&lt;string&gt; / null |  | 第一组要排除的列名列表 |
| `path_strings2` | 否 | array&lt;string&gt; / null |  | 第二组语音条件列表 |
| `chars2` | 否 | array&lt;string&gt; / null |  | 第二组可直接输入的汉字集合；每个元素若为多字串会自动拆字 |
| `column2` | 否 | array&lt;string&gt; / null |  | 第二组的额外排列组合字段 |
| `combine_query2` | 否 | boolean | default=false | 第二组是否开启交叉组合查询 |
| `exclude_columns2` | 否 | array&lt;string&gt; / null |  | 第二组要排除的列名列表 |
| `locations` | 否 | array&lt;string&gt; |  | 目标地点列表 |
| `regions` | 否 | array&lt;string&gt; |  | 目标区域列表 |
| `features` | 否 | array&lt;string&gt; | default=["韻母"] | 需要比较的语音特征 |
| `region_mode` | 否 | string | default="yindian" | 地区匹配模式 |
| `table_name` | 否 | string | default="characters" | 字符數據庫表名（兩組使用相同表） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path_strings1": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Path Strings1",
      "description": "第一组语音条件列表",
      "example": [
        "[知]{組}"
      ]
    },
    "chars1": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Chars1",
      "description": "第一组可直接输入的汉字集合；每个元素若为多字串会自动拆字",
      "example": [
        "笨",
        "蛋"
      ]
    },
    "column1": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Column1",
      "description": "第一组的额外排列组合字段",
      "example": [
        "等"
      ]
    },
    "combine_query1": {
      "type": "boolean",
      "title": "Combine Query1",
      "description": "第一组是否开启交叉组合查询",
      "default": false
    },
    "exclude_columns1": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Columns1",
      "description": "第一组要排除的列名列表",
      "example": [
        "多地位標記",
        "多等"
      ]
    },
    "path_strings2": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Path Strings2",
      "description": "第二组语音条件列表",
      "example": [
        "[莊]{組}"
      ]
    },
    "chars2": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Chars2",
      "description": "第二组可直接输入的汉字集合；每个元素若为多字串会自动拆字",
      "example": [
        "知",
        "庄"
      ]
    },
    "column2": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Column2",
      "description": "第二组的额外排列组合字段",
      "example": [
        "等"
      ]
    },
    "combine_query2": {
      "type": "boolean",
      "title": "Combine Query2",
      "description": "第二组是否开启交叉组合查询",
      "default": false
    },
    "exclude_columns2": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Columns2",
      "description": "第二组要排除的列名列表",
      "example": [
        "多地位標記",
        "多等"
      ]
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations",
      "description": "目标地点列表",
      "example": [
        "广州",
        "香港"
      ]
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions",
      "description": "目标区域列表",
      "example": []
    },
    "features": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Features",
      "description": "需要比较的语音特征",
      "default": [
        "韻母"
      ],
      "example": [
        "聲母",
        "韻母"
      ]
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "description": "地区匹配模式",
      "default": "yindian"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "字符數據庫表名（兩組使用相同表）",
      "default": "characters"
    }
  },
  "type": "object",
  "title": "CompareZhongGuAnalysis",
  "description": "比较两组中古音条件在方言中的读音差异"
}
```

</details>

<a id="schema-comparisongroup"></a>

### `ComparisonGroup`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `label` | 是 | string | minLength=1; maxLength=50 |  |
| `village_ids` | 否 | array&lt;integer&gt; / null |  | 村庄ID列表（推荐使用） |
| `filter` | 否 | [SubsetFilter](#schema-subsetfilter) / null |  | 过滤条件（向后兼容） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "label": {
      "type": "string",
      "maxLength": 50,
      "minLength": 1,
      "title": "Label"
    },
    "village_ids": {
      "anyOf": [
        {
          "items": {
            "type": "integer"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Village Ids",
      "description": "村庄ID列表（推荐使用）"
    },
    "filter": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/SubsetFilter"
        },
        {
          "type": "null"
        }
      ],
      "description": "过滤条件（向后兼容）"
    }
  },
  "type": "object",
  "required": [
    "label"
  ],
  "title": "ComparisonGroup",
  "description": "对比组（支持两种模式：village_ids 或 filter）"
}
```

</details>

<a id="schema-customdataallresponse"></a>

### `CustomDataAllResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `total` | 是 | integer |  |  |
| `data` | 是 | array&lt;[CustomDataRecord](#schema-customdatarecord)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "data": {
      "items": {
        "$ref": "#/components/schemas/CustomDataRecord"
      },
      "type": "array",
      "title": "Data"
    }
  },
  "type": "object",
  "required": [
    "username",
    "total",
    "data"
  ],
  "title": "CustomDataAllResponse"
}
```

</details>

<a id="schema-customdataedit"></a>

### `CustomDataEdit`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `created_at` | 是 | string (date-time) |  |  |
| `簡稱` | 否 | string / null |  |  |
| `音典分區` | 否 | string / null |  |  |
| `經緯度` | 否 | string / null |  |  |
| `聲韻調` | 否 | string / null |  |  |
| `特徵` | 否 | string / null |  |  |
| `值` | 否 | string / null |  |  |
| `說明` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "簡稱": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "簡稱"
    },
    "音典分區": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "音典分區"
    },
    "經緯度": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "經緯度"
    },
    "聲韻調": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "聲韻調"
    },
    "特徵": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "特徵"
    },
    "值": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "值"
    },
    "說明": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "說明"
    }
  },
  "type": "object",
  "required": [
    "created_at"
  ],
  "title": "CustomDataEdit",
  "description": "編輯 custom 數據請求"
}
```

</details>

<a id="schema-customdatalistresponse"></a>

### `CustomDataListResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `data` | 是 | array&lt;[CustomDataRecord](#schema-customdatarecord)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "data": {
      "items": {
        "$ref": "#/components/schemas/CustomDataRecord"
      },
      "type": "array",
      "title": "Data"
    }
  },
  "type": "object",
  "required": [
    "data"
  ],
  "title": "CustomDataListResponse"
}
```

</details>

<a id="schema-customdatarecord"></a>

### `CustomDataRecord`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `簡稱` | 是 | string |  |  |
| `音典分區` | 是 | string |  |  |
| `經緯度` | 是 | string |  |  |
| `聲韻調` | 否 | string / null |  |  |
| `特徵` | 是 | string |  |  |
| `值` | 是 | string |  |  |
| `說明` | 否 | string / null |  |  |
| `created_at` | 是 | string (date-time) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "簡稱": {
      "type": "string",
      "title": "簡稱"
    },
    "音典分區": {
      "type": "string",
      "title": "音典分區"
    },
    "經緯度": {
      "type": "string",
      "title": "經緯度"
    },
    "聲韻調": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "聲韻調"
    },
    "特徵": {
      "type": "string",
      "title": "特徵"
    },
    "值": {
      "type": "string",
      "title": "值"
    },
    "說明": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "說明"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "簡稱",
    "音典分區",
    "經緯度",
    "特徵",
    "值",
    "created_at"
  ],
  "title": "CustomDataRecord"
}
```

</details>

<a id="schema-customfeaturegrouplistresponse"></a>

### `CustomFeatureGroupListResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `data` | 是 | array&lt;[CustomFeatureGroupResponse](#schema-customfeaturegroupresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "data": {
      "items": {
        "$ref": "#/components/schemas/CustomFeatureGroupResponse"
      },
      "type": "array",
      "title": "Data"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    }
  },
  "type": "object",
  "required": [
    "data",
    "total"
  ],
  "title": "CustomFeatureGroupListResponse"
}
```

</details>

<a id="schema-customfeaturegroupresponse"></a>

### `CustomFeatureGroupResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `feature_key` | 是 | string |  |  |
| `特徵` | 是 | string |  |  |
| `聲韻調` | 是 | string |  |  |
| `location_count` | 是 | integer |  |  |
| `updated_at` | 是 | string (date-time) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "feature_key": {
      "type": "string",
      "title": "Feature Key"
    },
    "特徵": {
      "type": "string",
      "title": "特徵"
    },
    "聲韻調": {
      "type": "string",
      "title": "聲韻調"
    },
    "location_count": {
      "type": "integer",
      "title": "Location Count"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "feature_key",
    "特徵",
    "聲韻調",
    "location_count",
    "updated_at"
  ],
  "title": "CustomFeatureGroupResponse"
}
```

</details>

<a id="schema-custompointgrouplistresponse"></a>

### `CustomPointGroupListResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `data` | 是 | array&lt;[CustomPointGroupResponse](#schema-custompointgroupresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "data": {
      "items": {
        "$ref": "#/components/schemas/CustomPointGroupResponse"
      },
      "type": "array",
      "title": "Data"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    }
  },
  "type": "object",
  "required": [
    "data",
    "total"
  ],
  "title": "CustomPointGroupListResponse"
}
```

</details>

<a id="schema-custompointgroupresponse"></a>

### `CustomPointGroupResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `point_key` | 是 | string |  |  |
| `簡稱` | 是 | string |  |  |
| `音典分區` | 是 | string |  |  |
| `經緯度` | 是 | string |  |  |
| `feature_count` | 是 | integer |  |  |
| `updated_at` | 是 | string (date-time) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "point_key": {
      "type": "string",
      "title": "Point Key"
    },
    "簡稱": {
      "type": "string",
      "title": "簡稱"
    },
    "音典分區": {
      "type": "string",
      "title": "音典分區"
    },
    "經緯度": {
      "type": "string",
      "title": "經緯度"
    },
    "feature_count": {
      "type": "integer",
      "title": "Feature Count"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "point_key",
    "簡稱",
    "音典分區",
    "經緯度",
    "feature_count",
    "updated_at"
  ],
  "title": "CustomPointGroupResponse"
}
```

</details>

<a id="schema-customregioncreate"></a>

### `CustomRegionCreate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_name` | 是 | string | minLength=1; maxLength=200 | 区域名称 |
| `locations` | 是 | array&lt;string&gt; | minItems=1 | 地点简称列表 |
| `description` | 否 | string / null |  | 区域描述 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_name": {
      "type": "string",
      "maxLength": 200,
      "minLength": 1,
      "title": "Region Name",
      "description": "区域名称"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "minItems": 1,
      "title": "Locations",
      "description": "地点简称列表"
    },
    "description": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 1000
        },
        {
          "type": "null"
        }
      ],
      "title": "Description",
      "description": "区域描述"
    }
  },
  "type": "object",
  "required": [
    "region_name",
    "locations"
  ],
  "title": "CustomRegionCreate",
  "description": "创建或更新自定义区域的请求模型"
}
```

</details>

<a id="schema-customregionlist"></a>

### `CustomRegionList`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `regions` | 是 | array&lt;[CustomRegionResponse](#schema-customregionresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "regions": {
      "items": {
        "$ref": "#/components/schemas/CustomRegionResponse"
      },
      "type": "array",
      "title": "Regions"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    }
  },
  "type": "object",
  "required": [
    "regions",
    "total"
  ],
  "title": "CustomRegionList",
  "description": "自定义区域列表响应模型"
}
```

</details>

<a id="schema-customregionresponse"></a>

### `CustomRegionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `region_name` | 是 | string |  |  |
| `locations` | 是 | array&lt;string&gt; |  |  |
| `location_count` | 是 | integer |  |  |
| `description` | 是 | string / null |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `updated_at` | 是 | string (date-time) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "region_name": {
      "type": "string",
      "title": "Region Name"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations"
    },
    "location_count": {
      "type": "integer",
      "title": "Location Count"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "id",
    "region_name",
    "locations",
    "location_count",
    "description",
    "created_at",
    "updated_at"
  ],
  "title": "CustomRegionResponse",
  "description": "自定义区域响应模型"
}
```

</details>

<a id="schema-dbscanconfig"></a>

### `DBSCANConfig`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `eps` | 否 | number | default=0.5; maximum=10.0; exclusiveMinimum=0.0 | 邻域半径 |
| `min_samples` | 否 | integer | default=5; minimum=1.0; maximum=20.0 | 最小样本数 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "eps": {
      "type": "number",
      "maximum": 10.0,
      "exclusiveMinimum": 0.0,
      "title": "Eps",
      "description": "邻域半径",
      "default": 0.5
    },
    "min_samples": {
      "type": "integer",
      "maximum": 20.0,
      "minimum": 1.0,
      "title": "Min Samples",
      "description": "最小样本数",
      "default": 5
    }
  },
  "type": "object",
  "title": "DBSCANConfig",
  "description": "DBSCAN算法配置"
}
```

</details>

<a id="schema-dailyactivityitem"></a>

### `DailyActivityItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `date` | 是 | string |  |  |
| `count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "date": {
      "type": "string",
      "title": "Date"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    }
  },
  "type": "object",
  "required": [
    "date",
    "count"
  ],
  "title": "DailyActivityItem"
}
```

</details>

<a id="schema-dashboardoverview"></a>

### `DashboardOverview`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_users` | 是 | integer |  |  |
| `active_users_7d` | 是 | integer |  |  |
| `active_users_30d` | 是 | integer |  |  |
| `total_calls` | 是 | integer |  |  |
| `total_traffic_mb` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total_users": {
      "type": "integer",
      "title": "Total Users"
    },
    "active_users_7d": {
      "type": "integer",
      "title": "Active Users 7D"
    },
    "active_users_30d": {
      "type": "integer",
      "title": "Active Users 30D"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "total_traffic_mb": {
      "type": "number",
      "title": "Total Traffic Mb"
    }
  },
  "type": "object",
  "required": [
    "total_users",
    "active_users_7d",
    "active_users_30d",
    "total_calls",
    "total_traffic_mb"
  ],
  "title": "DashboardOverview"
}
```

</details>

<a id="schema-dashboardresponse"></a>

### `DashboardResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `overview` | 是 | [DashboardOverview](#schema-dashboardoverview) |  |  |
| `top_apis` | 是 | array&lt;[app__schemas__admin__analytics__TopAPIItem__2](#schema-app__schemas__admin__analytics__topapiitem__2)&gt; |  |  |
| `user_distribution` | 是 | object&lt;integer&gt; |  |  |
| `monthly_new_users` | 是 | array&lt;[MonthlyNewUsersItem](#schema-monthlynewusersitem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "overview": {
      "$ref": "#/components/schemas/DashboardOverview"
    },
    "top_apis": {
      "items": {
        "$ref": "#/components/schemas/app__schemas__admin__analytics__TopAPIItem__2"
      },
      "type": "array",
      "title": "Top Apis"
    },
    "user_distribution": {
      "additionalProperties": {
        "type": "integer"
      },
      "type": "object",
      "title": "User Distribution"
    },
    "monthly_new_users": {
      "items": {
        "$ref": "#/components/schemas/MonthlyNewUsersItem"
      },
      "type": "array",
      "title": "Monthly New Users"
    }
  },
  "type": "object",
  "required": [
    "overview",
    "top_apis",
    "user_distribution",
    "monthly_new_users"
  ],
  "title": "DashboardResponse"
}
```

</details>

<a id="schema-devicedistribution"></a>

### `DeviceDistribution`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `desktop` | 是 | integer |  |  |
| `mobile` | 是 | integer |  |  |
| `tablet` | 是 | integer |  |  |
| `unknown` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "desktop": {
      "type": "integer",
      "title": "Desktop"
    },
    "mobile": {
      "type": "integer",
      "title": "Mobile"
    },
    "tablet": {
      "type": "integer",
      "title": "Tablet"
    },
    "unknown": {
      "type": "integer",
      "title": "Unknown"
    }
  },
  "type": "object",
  "required": [
    "desktop",
    "mobile",
    "tablet",
    "unknown"
  ],
  "title": "DeviceDistribution"
}
```

</details>

<a id="schema-devicedistributionresponse"></a>

### `DeviceDistributionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_types` | 是 | array&lt;[DeviceTypeItem](#schema-devicetypeitem)&gt; |  |  |
| `browsers` | 是 | array&lt;[DeviceTypeItem](#schema-devicetypeitem)&gt; |  |  |
| `os` | 是 | array&lt;[DeviceTypeItem](#schema-devicetypeitem)&gt; |  |  |
| `total_users` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "device_types": {
      "items": {
        "$ref": "#/components/schemas/DeviceTypeItem"
      },
      "type": "array",
      "title": "Device Types"
    },
    "browsers": {
      "items": {
        "$ref": "#/components/schemas/DeviceTypeItem"
      },
      "type": "array",
      "title": "Browsers"
    },
    "os": {
      "items": {
        "$ref": "#/components/schemas/DeviceTypeItem"
      },
      "type": "array",
      "title": "Os"
    },
    "total_users": {
      "type": "integer",
      "title": "Total Users"
    }
  },
  "type": "object",
  "required": [
    "device_types",
    "browsers",
    "os",
    "total_users"
  ],
  "title": "DeviceDistributionResponse"
}
```

</details>

<a id="schema-devicetypeitem"></a>

### `DeviceTypeItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  |  |
| `count` | 是 | integer |  |  |
| `percentage` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    },
    "percentage": {
      "type": "number",
      "title": "Percentage"
    }
  },
  "type": "object",
  "required": [
    "name",
    "count",
    "percentage"
  ],
  "title": "DeviceTypeItem"
}
```

</details>

<a id="schema-diversitysummary"></a>

### `DiversitySummary`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_users` | 是 | integer |  |  |
| `avg_diversity` | 是 | number |  |  |
| `explorer_count` | 是 | integer |  |  |
| `focused_count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total_users": {
      "type": "integer",
      "title": "Total Users"
    },
    "avg_diversity": {
      "type": "number",
      "title": "Avg Diversity"
    },
    "explorer_count": {
      "type": "integer",
      "title": "Explorer Count"
    },
    "focused_count": {
      "type": "integer",
      "title": "Focused Count"
    }
  },
  "type": "object",
  "required": [
    "total_users",
    "avg_diversity",
    "explorer_count",
    "focused_count"
  ],
  "title": "DiversitySummary"
}
```

</details>

<a id="schema-diversityuseritem"></a>

### `DiversityUserItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `api_count` | 是 | integer |  |  |
| `total_calls` | 是 | integer |  |  |
| `diversity_score` | 是 | number |  |  |
| `user_type` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "api_count": {
      "type": "integer",
      "title": "Api Count"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "diversity_score": {
      "type": "number",
      "title": "Diversity Score"
    },
    "user_type": {
      "type": "string",
      "title": "User Type"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "api_count",
    "total_calls",
    "diversity_score",
    "user_type"
  ],
  "title": "DiversityUserItem"
}
```

</details>

<a id="schema-editrequest"></a>

### `EditRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `created_at` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "created_at": {
      "type": "string",
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "username",
    "created_at"
  ],
  "title": "EditRequest"
}
```

</details>

<a id="schema-errordetail"></a>

### `ErrorDetail`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | 是 | string |  |  |
| `message` | 是 | string |  |  |
| `detail` | 否 | object / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "code": {
      "type": "string",
      "title": "Code"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "detail": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Detail"
    }
  },
  "type": "object",
  "required": [
    "code",
    "message"
  ],
  "title": "ErrorDetail",
  "description": "Error details."
}
```

</details>

<a id="schema-erroritem"></a>

### `ErrorItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `row` | 是 | integer |  |  |
| `error_type` | 是 | string |  |  |
| `field` | 是 | string |  |  |
| `value` | 是 | string |  |  |
| `message` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "row": {
      "type": "integer",
      "title": "Row"
    },
    "error_type": {
      "type": "string",
      "title": "Error Type"
    },
    "field": {
      "type": "string",
      "title": "Field"
    },
    "value": {
      "type": "string",
      "title": "Value"
    },
    "message": {
      "type": "string",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "row",
    "error_type",
    "field",
    "value",
    "message"
  ],
  "title": "ErrorItem",
  "description": "错误项"
}
```

</details>

<a id="schema-featureaggregationparams"></a>

### `FeatureAggregationParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_level` | 是 | [RegionLevel](#schema-regionlevel) |  |  |
| `region_names` | 是 | array&lt;string&gt; | minItems=1; maxItems=50 |  |
| `features` | 否 | object |  |  |
| `top_n` | 否 | integer | default=100; minimum=10.0; maximum=500.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_level": {
      "$ref": "#/components/schemas/RegionLevel"
    },
    "region_names": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "maxItems": 50,
      "minItems": 1,
      "title": "Region Names"
    },
    "features": {
      "additionalProperties": true,
      "type": "object",
      "title": "Features"
    },
    "top_n": {
      "type": "integer",
      "maximum": 500.0,
      "minimum": 10.0,
      "title": "Top N",
      "default": 100
    }
  },
  "type": "object",
  "required": [
    "region_level",
    "region_names"
  ],
  "title": "FeatureAggregationParams",
  "description": "特征聚合参数"
}
```

</details>

<a id="schema-featureconfig"></a>

### `FeatureConfig`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `use_semantic` | 否 | boolean | default=true |  |
| `use_morphology` | 否 | boolean | default=true |  |
| `use_diversity` | 否 | boolean | default=true |  |
| `top_n_suffix2` | 否 | integer | default=100; minimum=10.0; maximum=500.0 |  |
| `top_n_suffix3` | 否 | integer | default=100; minimum=10.0; maximum=500.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "use_semantic": {
      "type": "boolean",
      "title": "Use Semantic",
      "default": true
    },
    "use_morphology": {
      "type": "boolean",
      "title": "Use Morphology",
      "default": true
    },
    "use_diversity": {
      "type": "boolean",
      "title": "Use Diversity",
      "default": true
    },
    "top_n_suffix2": {
      "type": "integer",
      "maximum": 500.0,
      "minimum": 10.0,
      "title": "Top N Suffix2",
      "default": 100
    },
    "top_n_suffix3": {
      "type": "integer",
      "maximum": 500.0,
      "minimum": 10.0,
      "title": "Top N Suffix3",
      "default": 100
    }
  },
  "type": "object",
  "title": "FeatureConfig",
  "description": "特征配置"
}
```

</details>

<a id="schema-featureextractionparams"></a>

### `FeatureExtractionParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `villages` | 是 | array&lt;[VillageInput](#schema-villageinput)&gt; | minItems=1; maxItems=100000 |  |
| `features` | 否 | object |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "villages": {
      "items": {
        "$ref": "#/components/schemas/VillageInput"
      },
      "type": "array",
      "maxItems": 100000,
      "minItems": 1,
      "title": "Villages"
    },
    "features": {
      "additionalProperties": true,
      "type": "object",
      "title": "Features"
    }
  },
  "type": "object",
  "required": [
    "villages"
  ],
  "title": "FeatureExtractionParams",
  "description": "特征提取参数"
}
```

</details>

<a id="schema-featurestatsrequest"></a>

### `FeatureStatsRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 是 | array&lt;string&gt; | minItems=1 | 地點簡稱列表（必需） |
| `chars` | 否 | array&lt;string&gt; / null |  | 要查詢的漢字列表（可選，為空則查該地點所有漢字） |
| `features` | 否 | array&lt;string&gt; | default=["聲母", "韻母", "聲調"] | 要統計的特徵列表 |
| `filters` | 否 | object&lt;array&lt;string&gt;&gt; / null |  | 篩選條件（可選），用於篩選特定的特徵值 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "minItems": 1,
      "title": "Locations",
      "description": "地點簡稱列表（必需）",
      "example": [
        "廣州",
        "東莞"
      ]
    },
    "chars": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Chars",
      "description": "要查詢的漢字列表（可選，為空則查該地點所有漢字）",
      "example": [
        "東",
        "西",
        "南",
        "北"
      ]
    },
    "features": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Features",
      "description": "要統計的特徵列表",
      "default": [
        "聲母",
        "韻母",
        "聲調"
      ],
      "example": [
        "聲母",
        "韻母"
      ]
    },
    "filters": {
      "anyOf": [
        {
          "additionalProperties": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Filters",
      "description": "篩選條件（可選），用於篩選特定的特徵值",
      "example": {
        "聲母": [
          "p",
          "b"
        ],
        "韻母": [
          "a",
          "ɐ"
        ]
      }
    }
  },
  "type": "object",
  "required": [
    "locations"
  ],
  "title": "FeatureStatsRequest",
  "description": "特徵統計請求模型\n\n用於 /api/feature_stats 接口，提供音韻特徵的詳細統計分析。\n支持漢字篩選、特徵篩選，並返回索引優化格式的數據。"
}
```

</details>

<a id="schema-flagsessionrequest"></a>

### `FlagSessionRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `is_suspicious` | 是 | boolean |  |  |
| `reason` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "is_suspicious": {
      "type": "boolean",
      "title": "Is Suspicious"
    },
    "reason": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 255
        },
        {
          "type": "null"
        }
      ],
      "title": "Reason"
    }
  },
  "type": "object",
  "required": [
    "is_suspicious"
  ],
  "title": "FlagSessionRequest"
}
```

</details>

<a id="schema-formdata"></a>

### `FormData`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `location` | 是 | string |  |  |
| `region` | 否 | string |  |  |
| `coordinates` | 否 | string |  |  |
| `phonology` | 否 | string |  |  |
| `feature` | 是 | string |  |  |
| `value` | 是 | string |  |  |
| `description` | 否 | string / null |  |  |
| `created_at` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "location": {
      "type": "string",
      "title": "Location"
    },
    "region": {
      "type": "string",
      "title": "Region"
    },
    "coordinates": {
      "type": "string",
      "title": "Coordinates"
    },
    "phonology": {
      "type": "string",
      "title": "Phonology"
    },
    "feature": {
      "type": "string",
      "title": "Feature"
    },
    "value": {
      "type": "string",
      "title": "Value"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "created_at": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "location",
    "feature",
    "value"
  ],
  "title": "FormData",
  "description": "用于 /api/submit_form 的用戶自定表單提交，寫入數據庫supplements.db。\n- locations-寫入的地點\n- region-寫入的音典分區（輸入完整的音典分區，例如嶺南-珠江-莞寶）\n- coordinates-寫入的經緯度坐標\n- phonology-寫入的聲韻調\n- feature-寫入的特徵（例如流攝等）\n- value-寫入的值（例如iu等）\n- description-寫入的具體說明\n- created_at：創建時間，submit沒有，delete必填\n- 無返回值"
}
```

</details>

<a id="schema-formantoptions"></a>

### `FormantOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `max_formants` | 否 | integer | default=5 |  |
| `max_freq_hz` | 否 | number | default=5500.0 | Maximum formant frequency in Hz. Use 5000 for males, 5500 for females, 8000 for children. |
| `window_length` | 否 | number | default=0.025 |  |
| `time_step` | 否 | number | default=0.002 |  |
| `pre_emphasis_from` | 否 | number | default=50.0 | Pre-emphasis frequency in Hz. Standard value is 50 Hz for high-pass filtering. |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "max_formants": {
      "type": "integer",
      "title": "Max Formants",
      "default": 5
    },
    "max_freq_hz": {
      "type": "number",
      "title": "Max Freq Hz",
      "description": "Maximum formant frequency in Hz. Use 5000 for males, 5500 for females, 8000 for children.",
      "default": 5500.0
    },
    "window_length": {
      "type": "number",
      "title": "Window Length",
      "default": 0.025
    },
    "time_step": {
      "type": "number",
      "title": "Time Step",
      "default": 0.002
    },
    "pre_emphasis_from": {
      "type": "number",
      "title": "Pre Emphasis From",
      "description": "Pre-emphasis frequency in Hz. Standard value is 50 Hz for high-pass filtering.",
      "default": 50.0
    }
  },
  "type": "object",
  "title": "FormantOptions",
  "description": "Formant extraction options.\n\nRecommended max_freq_hz values by speaker type:\n- Adult males: 5000 Hz\n- Adult females: 5500 Hz (default)\n- Children: 8000 Hz\n\nUsing incorrect max_freq_hz can cause tracking errors and\nsystematically biased formant values."
}
```

</details>

<a id="schema-fulltreeparams"></a>

### `FullTreeParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `level_columns` | 是 | array&lt;integer&gt; |  |  |
| `data_columns` | 否 | array&lt;integer&gt; | default=[] |  |
| `filters` | 否 | object&lt;array&lt;string&gt;&gt; / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "level_columns": {
      "items": {
        "type": "integer"
      },
      "type": "array",
      "title": "Level Columns"
    },
    "data_columns": {
      "items": {
        "type": "integer"
      },
      "type": "array",
      "title": "Data Columns",
      "default": []
    },
    "filters": {
      "anyOf": [
        {
          "additionalProperties": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Filters"
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "level_columns"
  ],
  "title": "FullTreeParams",
  "description": "完整树模式参数"
}
```

</details>

<a id="schema-geodistributionresponse"></a>

### `GeoDistributionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `level` | 是 | string |  |  |
| `distribution` | 是 | array&lt;[app__schemas__admin__analytics__GeoDistributionItem](#schema-app__schemas__admin__analytics__geodistributionitem)&gt; |  |  |
| `total_locations` | 是 | integer |  |  |
| `error` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "level": {
      "type": "string",
      "title": "Level"
    },
    "distribution": {
      "items": {
        "$ref": "#/components/schemas/app__schemas__admin__analytics__GeoDistributionItem"
      },
      "type": "array",
      "title": "Distribution"
    },
    "total_locations": {
      "type": "integer",
      "title": "Total Locations"
    },
    "error": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Error"
    }
  },
  "type": "object",
  "required": [
    "level",
    "distribution",
    "total_locations"
  ],
  "title": "GeoDistributionResponse"
}
```

</details>

<a id="schema-geometryquerybody"></a>

### `GeometryQueryBody`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `geometry` | 是 | object |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "geometry": {
      "additionalProperties": true,
      "type": "object",
      "title": "Geometry"
    }
  },
  "type": "object",
  "required": [
    "geometry"
  ],
  "title": "GeometryQueryBody"
}
```

</details>

<a id="schema-getdatarequest"></a>

### `GetDataRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `include_all` | 否 | boolean | default=false |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "include_all": {
      "type": "boolean",
      "title": "Include All",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "task_id"
  ],
  "title": "GetDataRequest",
  "description": "获取数据请求"
}
```

</details>

<a id="schema-growthsummary"></a>

### `GrowthSummary`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_users` | 是 | integer |  |  |
| `avg_monthly_growth` | 是 | number |  |  |
| `months_analyzed` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total_users": {
      "type": "integer",
      "title": "Total Users"
    },
    "avg_monthly_growth": {
      "type": "number",
      "title": "Avg Monthly Growth"
    },
    "months_analyzed": {
      "type": "integer",
      "title": "Months Analyzed"
    }
  },
  "type": "object",
  "required": [
    "total_users",
    "avg_monthly_growth",
    "months_analyzed"
  ],
  "title": "GrowthSummary"
}
```

</details>

<a id="schema-httpvalidationerror"></a>

### `HTTPValidationError`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `detail` | 否 | array&lt;[ValidationError](#schema-validationerror)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "type": "array",
      "title": "Detail"
    }
  },
  "type": "object",
  "title": "HTTPValidationError"
}
```

</details>

<a id="schema-hierarchicalclusteringparams"></a>

### `HierarchicalClusteringParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [AlgorithmType](#schema-algorithmtype) |  |  |
| `k_city` | 否 | integer | default=3; minimum=2.0; maximum=10.0 | 市级聚类数 |
| `k_county` | 否 | integer | default=8; minimum=2.0; maximum=15.0 | 县级聚类数 |
| `k_township` | 否 | integer | default=15; minimum=2.0; maximum=30.0 | 镇级聚类数 |
| `features` | 否 | [FeatureConfig](#schema-featureconfig) |  |  |
| `preprocessing` | 否 | [PreprocessingConfig](#schema-preprocessingconfig) |  |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/AlgorithmType"
    },
    "k_city": {
      "type": "integer",
      "maximum": 10.0,
      "minimum": 2.0,
      "title": "K City",
      "description": "市级聚类数",
      "default": 3
    },
    "k_county": {
      "type": "integer",
      "maximum": 15.0,
      "minimum": 2.0,
      "title": "K County",
      "description": "县级聚类数",
      "default": 8
    },
    "k_township": {
      "type": "integer",
      "maximum": 30.0,
      "minimum": 2.0,
      "title": "K Township",
      "description": "镇级聚类数",
      "default": 15
    },
    "features": {
      "$ref": "#/components/schemas/FeatureConfig"
    },
    "preprocessing": {
      "$ref": "#/components/schemas/PreprocessingConfig"
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    }
  },
  "type": "object",
  "required": [
    "algorithm"
  ],
  "title": "HierarchicalClusteringParams",
  "description": "层次聚类参数"
}
```

</details>

<a id="schema-iphistoryitem"></a>

### `IPHistoryItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `ip` | 是 | string |  |  |
| `location` | 否 | string / null |  |  |
| `timestamp` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "ip": {
      "type": "string",
      "title": "Ip"
    },
    "location": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Location"
    },
    "timestamp": {
      "type": "string",
      "title": "Timestamp"
    }
  },
  "type": "object",
  "required": [
    "ip",
    "timestamp"
  ],
  "title": "IPHistoryItem"
}
```

</details>

<a id="schema-informationbase"></a>

### `InformationBase`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `簡稱` | 是 | string |  |  |
| `音典分區` | 是 | string |  |  |
| `經緯度` | 是 | string |  |  |
| `聲韻調` | 是 | string |  |  |
| `特徵` | 是 | string |  |  |
| `值` | 是 | string |  |  |
| `說明` | 是 | string / null |  |  |
| `username` | 是 | string |  |  |
| `user_id` | 否 | integer / null |  |  |
| `created_at` | 否 | string (date-time) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "簡稱": {
      "type": "string",
      "title": "簡稱"
    },
    "音典分區": {
      "type": "string",
      "title": "音典分區"
    },
    "經緯度": {
      "type": "string",
      "title": "經緯度"
    },
    "聲韻調": {
      "type": "string",
      "title": "聲韻調"
    },
    "特徵": {
      "type": "string",
      "title": "特徵"
    },
    "值": {
      "type": "string",
      "title": "值"
    },
    "說明": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "說明"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "user_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "User Id"
    },
    "created_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "簡稱",
    "音典分區",
    "經緯度",
    "聲韻調",
    "特徵",
    "值",
    "說明",
    "username"
  ],
  "title": "InformationBase"
}
```

</details>

<a id="schema-jobcreaterequest"></a>

### `JobCreateRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `upload_id` | 是 | string |  |  |
| `mode` | 是 | string | enum=["single", "continuous"] |  |
| `modules` | 否 | array&lt;string&gt; | default=["basic", "pitch", "intensity", "segments"] | Modules to run: basic, pitch, intensity, formant, voice_quality, segments, spectrogram |
| `options` | 否 | [JobOptions](#schema-joboptions) |  |  |
| `output` | 否 | [OutputOptions](#schema-outputoptions) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "upload_id": {
      "type": "string",
      "title": "Upload Id"
    },
    "mode": {
      "type": "string",
      "enum": [
        "single",
        "continuous"
      ],
      "title": "Mode"
    },
    "modules": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Modules",
      "description": "Modules to run: basic, pitch, intensity, formant, voice_quality, segments, spectrogram",
      "default": [
        "basic",
        "pitch",
        "intensity",
        "segments"
      ]
    },
    "options": {
      "$ref": "#/components/schemas/JobOptions"
    },
    "output": {
      "$ref": "#/components/schemas/OutputOptions"
    }
  },
  "type": "object",
  "required": [
    "upload_id",
    "mode"
  ],
  "title": "JobCreateRequest",
  "description": "Request to create analysis job."
}
```

</details>

<a id="schema-jobcreateresponse"></a>

### `JobCreateResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `job_id` | 是 | string |  |  |
| `status` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "job_id": {
      "type": "string",
      "title": "Job Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    }
  },
  "type": "object",
  "required": [
    "job_id",
    "status"
  ],
  "title": "JobCreateResponse",
  "description": "Response for job creation."
}
```

</details>

<a id="schema-joboptions"></a>

### `JobOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `normalize` | 否 | [NormalizeOptions](#schema-normalizeoptions) / null |  |  |
| `pitch` | 否 | [PitchOptions](#schema-pitchoptions) / null |  |  |
| `formant` | 否 | [FormantOptions](#schema-formantoptions) / null |  |  |
| `spectrogram` | 否 | [SpectrogramOptions](#schema-spectrogramoptions) / null |  |  |
| `voice_quality` | 否 | [VoiceQualityOptions](#schema-voicequalityoptions) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "normalize": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/NormalizeOptions"
        },
        {
          "type": "null"
        }
      ]
    },
    "pitch": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/PitchOptions"
        },
        {
          "type": "null"
        }
      ]
    },
    "formant": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/FormantOptions"
        },
        {
          "type": "null"
        }
      ]
    },
    "spectrogram": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/SpectrogramOptions"
        },
        {
          "type": "null"
        }
      ]
    },
    "voice_quality": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/VoiceQualityOptions"
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "type": "object",
  "title": "JobOptions",
  "description": "Analysis options."
}
```

</details>

<a id="schema-jobstatusresponse"></a>

### `JobStatusResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `job_id` | 是 | string |  |  |
| `status` | 是 | string | enum=["queued", "running", "done", "error", "canceled"] |  |
| `progress` | 是 | number | minimum=0.0; maximum=100.0 |  |
| `stage` | 否 | string / null |  |  |
| `error` | 否 | [ErrorDetail](#schema-errordetail) / null |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `updated_at` | 是 | string (date-time) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "job_id": {
      "type": "string",
      "title": "Job Id"
    },
    "status": {
      "type": "string",
      "enum": [
        "queued",
        "running",
        "done",
        "error",
        "canceled"
      ],
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "maximum": 100.0,
      "minimum": 0.0,
      "title": "Progress"
    },
    "stage": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Stage"
    },
    "error": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/ErrorDetail"
        },
        {
          "type": "null"
        }
      ]
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "job_id",
    "status",
    "progress",
    "created_at",
    "updated_at"
  ],
  "title": "JobStatusResponse",
  "description": "Job status response."
}
```

</details>

<a id="schema-lazytreeparams"></a>

### `LazyTreeParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `level_columns` | 是 | array&lt;integer&gt; |  |  |
| `parent_path` | 否 | array&lt;string&gt; / null |  |  |
| `filters` | 否 | object&lt;array&lt;string&gt;&gt; / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "level_columns": {
      "items": {
        "type": "integer"
      },
      "type": "array",
      "title": "Level Columns"
    },
    "parent_path": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Parent Path"
    },
    "filters": {
      "anyOf": [
        {
          "additionalProperties": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Filters"
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "level_columns"
  ],
  "title": "LazyTreeParams",
  "description": "懒加载模式参数"
}
```

</details>

<a id="schema-letadmin"></a>

### `LetAdmin`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `role` | 否 | string | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "role": {
      "type": "string",
      "title": "Role",
      "default": ""
    }
  },
  "type": "object",
  "required": [
    "username"
  ],
  "title": "LetAdmin"
}
```

</details>

<a id="schema-logoutresponse"></a>

### `LogoutResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | 是 | string |  |  |
| `session_seconds` | 是 | integer |  |  |
| `total_online_seconds` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "message": {
      "type": "string",
      "title": "Message"
    },
    "session_seconds": {
      "type": "integer",
      "title": "Session Seconds"
    },
    "total_online_seconds": {
      "type": "integer",
      "title": "Total Online Seconds"
    }
  },
  "type": "object",
  "required": [
    "message",
    "session_seconds",
    "total_online_seconds"
  ],
  "title": "LogoutResponse"
}
```

</details>

<a id="schema-mergerequest"></a>

### `MergeRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    }
  },
  "type": "object",
  "required": [
    "task_id"
  ],
  "title": "MergeRequest",
  "description": "合并请求"
}
```

</details>

<a id="schema-mergeresponse"></a>

### `MergeResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `progress` | 是 | number |  |  |
| `message` | 是 | string |  |  |
| `stage` | 否 | string / null |  |  |
| `updated_at` | 否 | string (date-time) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "title": "Progress"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "stage": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Stage"
    },
    "updated_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "status",
    "progress",
    "message"
  ],
  "title": "MergeResponse",
  "description": "合并响应"
}
```

</details>

<a id="schema-monthlygrowthitem"></a>

### `MonthlyGrowthItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `month` | 是 | string |  |  |
| `new_users` | 是 | integer |  |  |
| `cumulative_users` | 是 | integer |  |  |
| `growth_rate` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "month": {
      "type": "string",
      "title": "Month"
    },
    "new_users": {
      "type": "integer",
      "title": "New Users"
    },
    "cumulative_users": {
      "type": "integer",
      "title": "Cumulative Users"
    },
    "growth_rate": {
      "type": "number",
      "title": "Growth Rate"
    }
  },
  "type": "object",
  "required": [
    "month",
    "new_users",
    "cumulative_users",
    "growth_rate"
  ],
  "title": "MonthlyGrowthItem"
}
```

</details>

<a id="schema-monthlynewusersitem"></a>

### `MonthlyNewUsersItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `month` | 是 | string |  |  |
| `new_users` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "month": {
      "type": "string",
      "title": "Month"
    },
    "new_users": {
      "type": "integer",
      "title": "New Users"
    }
  },
  "type": "object",
  "required": [
    "month",
    "new_users"
  ],
  "title": "MonthlyNewUsersItem"
}
```

</details>

<a id="schema-networknode"></a>

### `NetworkNode`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `character` | 是 | string |  | 字符 |
| `depth` | 是 | integer |  | BFS深度 |
| `similarity` | 是 | number |  | 与父节点的相似度 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "character": {
      "type": "string",
      "title": "Character",
      "description": "字符"
    },
    "depth": {
      "type": "integer",
      "title": "Depth",
      "description": "BFS深度"
    },
    "similarity": {
      "type": "number",
      "title": "Similarity",
      "description": "与父节点的相似度"
    }
  },
  "type": "object",
  "required": [
    "character",
    "depth",
    "similarity"
  ],
  "title": "NetworkNode",
  "description": "字符网络节点模型"
}
```

</details>

<a id="schema-normalizeoptions"></a>

### `NormalizeOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sample_rate` | 否 | integer | default=16000 |  |
| `channels` | 否 | integer | default=1 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "sample_rate": {
      "type": "integer",
      "title": "Sample Rate",
      "default": 16000
    },
    "channels": {
      "type": "integer",
      "title": "Channels",
      "default": 1
    }
  },
  "type": "object",
  "title": "NormalizeOptions",
  "description": "Audio normalization options."
}
```

</details>

<a id="schema-notesitemresponse"></a>

### `NotesItemResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `location_name` | 是 | string |  |  |
| `character` | 是 | string |  |  |
| `ipa` | 是 | string |  |  |
| `notes` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "character": {
      "type": "string",
      "title": "Character"
    },
    "ipa": {
      "type": "string",
      "title": "Ipa"
    },
    "notes": {
      "type": "string",
      "title": "Notes"
    }
  },
  "type": "object",
  "required": [
    "id",
    "location_name",
    "character",
    "ipa",
    "notes"
  ],
  "title": "NotesItemResponse"
}
```

</details>

<a id="schema-notessearchresponse"></a>

### `NotesSearchResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[NotesItemResponse](#schema-notesitemresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/NotesItemResponse"
      },
      "type": "array",
      "title": "Items"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "items",
    "total",
    "page",
    "page_size"
  ],
  "title": "NotesSearchResponse"
}
```

</details>

<a id="schema-onlineuseritem"></a>

### `OnlineUserItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `last_seen` | 是 | string (date-time) |  |  |
| `current_ip` | 是 | string |  |  |
| `current_ip_location` | 否 | string / null |  |  |
| `device_info` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "last_seen": {
      "type": "string",
      "format": "date-time",
      "title": "Last Seen"
    },
    "current_ip": {
      "type": "string",
      "title": "Current Ip"
    },
    "current_ip_location": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Current Ip Location"
    },
    "device_info": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Device Info"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "last_seen",
    "current_ip"
  ],
  "title": "OnlineUserItem"
}
```

</details>

<a id="schema-onlineusersresponse"></a>

### `OnlineUsersResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `online_count` | 是 | integer |  |  |
| `users` | 是 | array&lt;[OnlineUserItem](#schema-onlineuseritem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "online_count": {
      "type": "integer",
      "title": "Online Count"
    },
    "users": {
      "items": {
        "$ref": "#/components/schemas/OnlineUserItem"
      },
      "type": "array",
      "title": "Users"
    }
  },
  "type": "object",
  "required": [
    "online_count",
    "users"
  ],
  "title": "OnlineUsersResponse"
}
```

</details>

<a id="schema-outputoptions"></a>

### `OutputOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `downsample_hz` | 否 | integer / null | default=100 |  |
| `include_timeseries` | 否 | boolean | default=true |  |
| `include_summary` | 否 | boolean | default=true |  |
| `include_debug` | 否 | boolean | default=false |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "downsample_hz": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Downsample Hz",
      "default": 100
    },
    "include_timeseries": {
      "type": "boolean",
      "title": "Include Timeseries",
      "default": true
    },
    "include_summary": {
      "type": "boolean",
      "title": "Include Summary",
      "default": true
    },
    "include_debug": {
      "type": "boolean",
      "title": "Include Debug",
      "default": false
    }
  },
  "type": "object",
  "title": "OutputOptions",
  "description": "Output configuration."
}
```

</details>

<a id="schema-paginatedresponse"></a>

### `PaginatedResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total` | 是 | integer |  | 总记录数 |
| `page` | 是 | integer |  | 当前页码 |
| `page_size` | 是 | integer |  | 每页大小 |
| `data` | 是 | array&lt;未声明结构&gt; |  | 数据列表 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total": {
      "type": "integer",
      "title": "Total",
      "description": "总记录数"
    },
    "page": {
      "type": "integer",
      "title": "Page",
      "description": "当前页码"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size",
      "description": "每页大小"
    },
    "data": {
      "items": {},
      "type": "array",
      "title": "Data",
      "description": "数据列表"
    }
  },
  "type": "object",
  "required": [
    "total",
    "page",
    "page_size",
    "data"
  ],
  "title": "PaginatedResponse",
  "description": "分页响应模型"
}
```

</details>

<a id="schema-performancesummary"></a>

### `PerformanceSummary`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `overall_avg` | 是 | number |  |  |
| `slowest_api` | 是 | string / null |  |  |
| `total_apis` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "overall_avg": {
      "type": "number",
      "title": "Overall Avg"
    },
    "slowest_api": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Slowest Api"
    },
    "total_apis": {
      "type": "integer",
      "title": "Total Apis"
    }
  },
  "type": "object",
  "required": [
    "overall_avg",
    "slowest_api",
    "total_apis"
  ],
  "title": "PerformanceSummary"
}
```

</details>

<a id="schema-permissionresponse"></a>

### `PermissionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `db_key` | 是 | string |  |  |
| `can_write` | 否 | boolean | default=false |  |
| `id` | 是 | integer |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `updated_at` | 否 | string (date-time) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "can_write": {
      "type": "boolean",
      "title": "Can Write",
      "default": false
    },
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "updated_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "db_key",
    "id",
    "created_at"
  ],
  "title": "PermissionResponse",
  "description": "权限响应模型"
}
```

</details>

<a id="schema-phopierequest"></a>

### `PhoPieRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 是 | array&lt;string&gt; |  | 地點簡稱列表（必填） |
| `level1_column` | 是 | string |  | 第一級分類欄位（來自 characters.db），如 攝、系、組 |
| `level2_column` | 是 | string |  | 第二級分類欄位（來自 characters.db），如 韻、母 |
| `table_name` | 否 | string | default="characters" | characters.db 的表名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations",
      "description": "地點簡稱列表（必填）",
      "example": [
        "東莞莞城",
        "廣州"
      ]
    },
    "level1_column": {
      "type": "string",
      "title": "Level1 Column",
      "description": "第一級分類欄位（來自 characters.db），如 攝、系、組",
      "example": "攝"
    },
    "level2_column": {
      "type": "string",
      "title": "Level2 Column",
      "description": "第二級分類欄位（來自 characters.db），如 韻、母",
      "example": "韻"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "characters.db 的表名",
      "default": "characters"
    }
  },
  "type": "object",
  "required": [
    "locations",
    "level1_column",
    "level2_column"
  ],
  "title": "PhoPieRequest",
  "description": "音韻餅圖 API 請求模型（音值視角 + 地位視角共用）\n\n固定查詢聲母、韻母、聲調三個 feature。\nlevel1_column / level2_column 來自 characters.db 的分類欄位。"
}
```

</details>

<a id="schema-phonologyclassificationmatrixrequest"></a>

### `PhonologyClassificationMatrixRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 是 | array&lt;string&gt; |  | 地點簡稱列表 |
| `feature` | 是 | string |  | 音韻特徵：聲母、韻母、聲調 |
| `horizontal_column` | 是 | string |  | 橫向分類欄位（來自 characters.db） |
| `vertical_column` | 是 | string |  | 縱向分類欄位（來自 characters.db） |
| `cell_row_column` | 是 | string |  | 單元格內分行欄位（來自 characters.db） |
| `table_name` | 否 | string | default="characters" | 字符數據庫表名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations",
      "description": "地點簡稱列表",
      "example": [
        "東莞莞城",
        "雲浮富林"
      ]
    },
    "feature": {
      "type": "string",
      "title": "Feature",
      "description": "音韻特徵：聲母、韻母、聲調",
      "example": "聲母"
    },
    "horizontal_column": {
      "type": "string",
      "title": "Horizontal Column",
      "description": "橫向分類欄位（來自 characters.db）",
      "example": "母"
    },
    "vertical_column": {
      "type": "string",
      "title": "Vertical Column",
      "description": "縱向分類欄位（來自 characters.db）",
      "example": "攝"
    },
    "cell_row_column": {
      "type": "string",
      "title": "Cell Row Column",
      "description": "單元格內分行欄位（來自 characters.db）",
      "example": "部位"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "字符數據庫表名",
      "default": "characters"
    }
  },
  "type": "object",
  "required": [
    "locations",
    "feature",
    "horizontal_column",
    "vertical_column",
    "cell_row_column"
  ],
  "title": "PhonologyClassificationMatrixRequest",
  "description": "音韻特徵分類矩陣請求模型\n\n根據用戶指定的分類維度，創建音韻特徵的分類矩陣。\n結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。"
}
```

</details>

<a id="schema-phonologymatrixrequest"></a>

### `PhonologyMatrixRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 否 | array&lt;string&gt; / null |  | 地點簡稱列表，不傳則獲取所有地點 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Locations",
      "description": "地點簡稱列表，不傳則獲取所有地點",
      "example": [
        "東莞莞城",
        "雲浮富林"
      ]
    }
  },
  "type": "object",
  "title": "PhonologyMatrixRequest",
  "description": "聲母-韻母-聲調矩陣請求模型"
}
```

</details>

<a id="schema-pitchoptions"></a>

### `PitchOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `f0_min` | 否 | number | default=75.0 |  |
| `f0_max` | 否 | number | default=600.0 |  |
| `time_step` | 否 | number | default=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "f0_min": {
      "type": "number",
      "title": "F0 Min",
      "default": 75.0
    },
    "f0_max": {
      "type": "number",
      "title": "F0 Max",
      "default": 600.0
    },
    "time_step": {
      "type": "number",
      "title": "Time Step",
      "default": 0.0
    }
  },
  "type": "object",
  "title": "PitchOptions",
  "description": "Pitch extraction options."
}
```

</details>

<a id="schema-preprocessingconfig"></a>

### `PreprocessingConfig`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `use_pca` | 否 | boolean | default=true |  |
| `pca_n_components` | 否 | integer | default=50; minimum=10.0; maximum=200.0 |  |
| `standardize` | 否 | boolean | default=true |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "use_pca": {
      "type": "boolean",
      "title": "Use Pca",
      "default": true
    },
    "pca_n_components": {
      "type": "integer",
      "maximum": 200.0,
      "minimum": 10.0,
      "title": "Pca N Components",
      "default": 50
    },
    "standardize": {
      "type": "boolean",
      "title": "Standardize",
      "default": true
    }
  },
  "type": "object",
  "title": "PreprocessingConfig",
  "description": "预处理配置"
}
```

</details>

<a id="schema-processrequest"></a>

### `ProcessRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `custom_rules` | 否 | array&lt;object&gt; / null |  |  |
| `mode` | 否 | string / null | default="single" |  |
| `column` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "custom_rules": {
      "anyOf": [
        {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Custom Rules"
    },
    "mode": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Mode",
      "default": "single"
    },
    "column": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Column"
    }
  },
  "type": "object",
  "required": [
    "task_id"
  ],
  "title": "ProcessRequest",
  "description": "处理请求"
}
```

</details>

<a id="schema-processresponse"></a>

### `ProcessResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `progress` | 是 | number |  |  |
| `message` | 是 | string |  |  |
| `stage` | 否 | string / null |  |  |
| `updated_at` | 否 | string (date-time) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "progress": {
      "type": "number",
      "title": "Progress"
    },
    "message": {
      "type": "string",
      "title": "Message"
    },
    "stage": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Stage"
    },
    "updated_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "status",
    "progress",
    "message"
  ],
  "title": "ProcessResponse",
  "description": "处理响应"
}
```

</details>

<a id="schema-rfmanalysisresponse"></a>

### `RFMAnalysisResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `segments` | 是 | array&lt;[RFMSegmentInfo](#schema-rfmsegmentinfo)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "segments": {
      "items": {
        "$ref": "#/components/schemas/RFMSegmentInfo"
      },
      "type": "array",
      "title": "Segments"
    }
  },
  "type": "object",
  "required": [
    "segments"
  ],
  "title": "RFMAnalysisResponse"
}
```

</details>

<a id="schema-rfmsegmentinfo"></a>

### `RFMSegmentInfo`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `segment` | 是 | string |  |  |
| `count` | 是 | integer |  |  |
| `avg_recency_days` | 是 | number |  |  |
| `avg_frequency` | 是 | number |  |  |
| `avg_monetary` | 是 | number |  |  |
| `users` | 否 | array&lt;[RFMUserItem](#schema-rfmuseritem)&gt; / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "segment": {
      "type": "string",
      "title": "Segment"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    },
    "avg_recency_days": {
      "type": "number",
      "title": "Avg Recency Days"
    },
    "avg_frequency": {
      "type": "number",
      "title": "Avg Frequency"
    },
    "avg_monetary": {
      "type": "number",
      "title": "Avg Monetary"
    },
    "users": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/RFMUserItem"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Users"
    }
  },
  "type": "object",
  "required": [
    "segment",
    "count",
    "avg_recency_days",
    "avg_frequency",
    "avg_monetary"
  ],
  "title": "RFMSegmentInfo"
}
```

</details>

<a id="schema-rfmuseritem"></a>

### `RFMUserItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `recency_days` | 是 | integer |  |  |
| `frequency` | 是 | integer |  |  |
| `monetary` | 是 | number |  |  |
| `last_seen` | 是 | string / null |  |  |
| `r_score` | 是 | integer |  |  |
| `f_score` | 是 | integer |  |  |
| `m_score` | 是 | integer |  |  |
| `segment` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "recency_days": {
      "type": "integer",
      "title": "Recency Days"
    },
    "frequency": {
      "type": "integer",
      "title": "Frequency"
    },
    "monetary": {
      "type": "number",
      "title": "Monetary"
    },
    "last_seen": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Seen"
    },
    "r_score": {
      "type": "integer",
      "title": "R Score"
    },
    "f_score": {
      "type": "integer",
      "title": "F Score"
    },
    "m_score": {
      "type": "integer",
      "title": "M Score"
    },
    "segment": {
      "type": "string",
      "title": "Segment"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "recency_days",
    "frequency",
    "monetary",
    "last_seen",
    "r_score",
    "f_score",
    "m_score",
    "segment"
  ],
  "title": "RFMUserItem"
}
```

</details>

<a id="schema-rankingdetail"></a>

### `RankingDetail`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `rank` | 是 | integer / null |  | User's rank (null if no activity) |
| `value` | 是 | integer |  | User's value for this metric |
| `gap_to_prev` | 是 | integer / null |  | Gap to previous rank (null for rank 1) |
| `first_place_value` | 是 | integer |  | First place user's value |
| `percentile` | 是 | number |  | Percentage of participants surpassed (0-100) |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "rank": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Rank",
      "description": "User's rank (null if no activity)"
    },
    "value": {
      "type": "integer",
      "title": "Value",
      "description": "User's value for this metric"
    },
    "gap_to_prev": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Gap To Prev",
      "description": "Gap to previous rank (null for rank 1)"
    },
    "first_place_value": {
      "type": "integer",
      "title": "First Place Value",
      "description": "First place user's value"
    },
    "percentile": {
      "type": "number",
      "title": "Percentile",
      "description": "Percentage of participants surpassed (0-100)"
    }
  },
  "type": "object",
  "required": [
    "rank",
    "value",
    "gap_to_prev",
    "first_place_value",
    "percentile"
  ],
  "title": "RankingDetail",
  "description": "Individual ranking detail"
}
```

</details>

<a id="schema-recenttrendsresponse"></a>

### `RecentTrendsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `period` | 是 | string |  |  |
| `granularity` | 是 | string |  |  |
| `trends` | 是 | array&lt;[TrendItem](#schema-trenditem)&gt; |  |  |
| `summary` | 是 | [TrendsSummary](#schema-trendssummary) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "period": {
      "type": "string",
      "title": "Period"
    },
    "granularity": {
      "type": "string",
      "title": "Granularity"
    },
    "trends": {
      "items": {
        "$ref": "#/components/schemas/TrendItem"
      },
      "type": "array",
      "title": "Trends"
    },
    "summary": {
      "$ref": "#/components/schemas/TrendsSummary"
    }
  },
  "type": "object",
  "required": [
    "period",
    "granularity",
    "trends",
    "summary"
  ],
  "title": "RecentTrendsResponse"
}
```

</details>

<a id="schema-reducerequest"></a>

### `ReduceRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `regions` | 是 | array&lt;[RegionSpec](#schema-regionspec)&gt; |  |  |
| `method` | 否 | string | default="pca" |  |
| `n_components` | 否 | integer | default=2 |  |
| `run_id` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "regions": {
      "items": {
        "$ref": "#/components/schemas/RegionSpec"
      },
      "type": "array",
      "title": "Regions"
    },
    "method": {
      "type": "string",
      "title": "Method",
      "default": "pca"
    },
    "n_components": {
      "type": "integer",
      "title": "N Components",
      "default": 2
    },
    "run_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "regions"
  ],
  "title": "ReduceRequest",
  "description": "向量降维请求模型"
}
```

</details>

<a id="schema-reduceresponse"></a>

### `ReduceResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `regions` | 是 | array&lt;object&gt; |  |  |
| `coordinates` | 是 | array&lt;array&lt;number&gt;&gt; |  |  |
| `method` | 是 | string |  |  |
| `n_components` | 是 | integer |  |  |
| `explained_variance` | 否 | array&lt;number&gt; / null |  |  |
| `run_id` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "regions": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Regions"
    },
    "coordinates": {
      "items": {
        "items": {
          "type": "number"
        },
        "type": "array"
      },
      "type": "array",
      "title": "Coordinates"
    },
    "method": {
      "type": "string",
      "title": "Method"
    },
    "n_components": {
      "type": "integer",
      "title": "N Components"
    },
    "explained_variance": {
      "anyOf": [
        {
          "items": {
            "type": "number"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Explained Variance"
    },
    "run_id": {
      "type": "string",
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "regions",
    "coordinates",
    "method",
    "n_components",
    "run_id"
  ],
  "title": "ReduceResponse",
  "description": "向量降维响应模型"
}
```

</details>

<a id="schema-regioninfo"></a>

### `RegionInfo`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  | 区域名称 |
| `level` | 是 | string |  | 区域级别 (city/county/township) |
| `city` | 否 | string / null |  | 市级 |
| `county` | 否 | string / null |  | 区县级 |
| `township` | 否 | string / null |  | 乡镇级 |
| `village_count` | 是 | integer |  | 村庄数量 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name",
      "description": "区域名称"
    },
    "level": {
      "type": "string",
      "title": "Level",
      "description": "区域级别 (city/county/township)"
    },
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City",
      "description": "市级"
    },
    "county": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County",
      "description": "区县级"
    },
    "township": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township",
      "description": "乡镇级"
    },
    "village_count": {
      "type": "integer",
      "title": "Village Count",
      "description": "村庄数量"
    }
  },
  "type": "object",
  "required": [
    "name",
    "level",
    "village_count"
  ],
  "title": "RegionInfo",
  "description": "区域信息模型"
}
```

</details>

<a id="schema-regionlevel"></a>

### `RegionLevel`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "city",
    "county",
    "township"
  ],
  "title": "RegionLevel",
  "description": "区域级别"
}
```

</details>

<a id="schema-regionspec"></a>

### `RegionSpec`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `level` | 是 | string |  |  |
| `city` | 否 | string / null |  |  |
| `county` | 否 | string / null |  |  |
| `township` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "level": {
      "type": "string",
      "title": "Level"
    },
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City"
    },
    "county": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County"
    },
    "township": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township"
    }
  },
  "type": "object",
  "required": [
    "level"
  ],
  "title": "RegionSpec",
  "description": "区域规格（层级路径参数）"
}
```

</details>

<a id="schema-regionalcharfrequency"></a>

### `RegionalCharFrequency`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_name` | 是 | string |  | 区域名称 |
| `character` | 是 | string |  | 字符 |
| `frequency` | 是 | number |  | 频次 |
| `rank` | 是 | integer |  | 区域内排名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_name": {
      "type": "string",
      "title": "Region Name",
      "description": "区域名称"
    },
    "character": {
      "type": "string",
      "title": "Character",
      "description": "字符"
    },
    "frequency": {
      "type": "number",
      "title": "Frequency",
      "description": "频次"
    },
    "rank": {
      "type": "integer",
      "title": "Rank",
      "description": "区域内排名"
    }
  },
  "type": "object",
  "required": [
    "region_name",
    "character",
    "frequency",
    "rank"
  ],
  "title": "RegionalCharFrequency",
  "description": "区域字符频率模型"
}
```

</details>

<a id="schema-revokebulkresponse"></a>

### `RevokeBulkResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `revoked_count` | 是 | integer |  |  |
| `failed_count` | 否 | integer | default=0 |  |
| `details` | 否 | array&lt;object&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "revoked_count": {
      "type": "integer",
      "title": "Revoked Count"
    },
    "failed_count": {
      "type": "integer",
      "title": "Failed Count",
      "default": 0
    },
    "details": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Details"
    }
  },
  "type": "object",
  "required": [
    "revoked_count"
  ],
  "title": "RevokeBulkResponse"
}
```

</details>

<a id="schema-revokesessionresponse"></a>

### `RevokeSessionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | 是 | string |  |  |
| `revoked_tokens` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "message": {
      "type": "string",
      "title": "Message"
    },
    "revoked_tokens": {
      "type": "integer",
      "title": "Revoked Tokens"
    }
  },
  "type": "object",
  "required": [
    "message",
    "revoked_tokens"
  ],
  "title": "RevokeSessionResponse"
}
```

</details>

<a id="schema-sampledvillageclusteringparams"></a>

### `SampledVillageClusteringParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [AlgorithmType](#schema-algorithmtype) |  |  |
| `k` | 否 | integer / null |  |  |
| `sampling_strategy` | 否 | [SamplingStrategy](#schema-samplingstrategy) | default="random" |  |
| `sample_size` | 否 | integer | default=5000; minimum=100.0; maximum=10000.0 | 采样大小 |
| `filter` | 否 | [SubsetFilter](#schema-subsetfilter) / null |  |  |
| `features` | 否 | [FeatureConfig](#schema-featureconfig) |  |  |
| `preprocessing` | 否 | [PreprocessingConfig](#schema-preprocessingconfig) |  |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/AlgorithmType"
    },
    "k": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 20.0,
          "minimum": 2.0
        },
        {
          "type": "null"
        }
      ],
      "title": "K"
    },
    "sampling_strategy": {
      "$ref": "#/components/schemas/SamplingStrategy",
      "default": "random"
    },
    "sample_size": {
      "type": "integer",
      "maximum": 10000.0,
      "minimum": 100.0,
      "title": "Sample Size",
      "description": "采样大小",
      "default": 5000
    },
    "filter": {
      "anyOf": [
        {
          "$ref": "#/components/schemas/SubsetFilter"
        },
        {
          "type": "null"
        }
      ]
    },
    "features": {
      "$ref": "#/components/schemas/FeatureConfig"
    },
    "preprocessing": {
      "$ref": "#/components/schemas/PreprocessingConfig"
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    }
  },
  "type": "object",
  "required": [
    "algorithm"
  ],
  "title": "SampledVillageClusteringParams",
  "description": "采样村庄聚类参数"
}
```

</details>

<a id="schema-samplingstrategy"></a>

### `SamplingStrategy`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "random",
    "stratified",
    "spatial"
  ],
  "title": "SamplingStrategy",
  "description": "采样策略"
}
```

</details>

<a id="schema-savechangesrequest"></a>

### `SaveChangesRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `modified_rows` | 是 | array&lt;object&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "modified_rows": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Modified Rows"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "modified_rows"
  ],
  "title": "SaveChangesRequest",
  "description": "保存更改请求"
}
```

</details>

<a id="schema-segmentinfo"></a>

### `SegmentInfo`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `level` | 是 | string |  |  |
| `count` | 是 | integer |  |  |
| `percentage` | 是 | number |  |  |
| `avg_calls` | 是 | number |  |  |
| `avg_duration` | 是 | number |  |  |
| `users` | 否 | array&lt;[UserSegmentItem](#schema-usersegmentitem)&gt; / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "level": {
      "type": "string",
      "title": "Level"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    },
    "percentage": {
      "type": "number",
      "title": "Percentage"
    },
    "avg_calls": {
      "type": "number",
      "title": "Avg Calls"
    },
    "avg_duration": {
      "type": "number",
      "title": "Avg Duration"
    },
    "users": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/UserSegmentItem"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Users"
    }
  },
  "type": "object",
  "required": [
    "level",
    "count",
    "percentage",
    "avg_calls",
    "avg_duration"
  ],
  "title": "SegmentInfo"
}
```

</details>

<a id="schema-semanticanalysisparams"></a>

### `SemanticAnalysisParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_level` | 是 | [RegionLevel](#schema-regionlevel) |  |  |
| `region_name` | 否 | string / null |  |  |
| `min_support` | 否 | integer | default=10; minimum=1.0; maximum=1000.0 |  |
| `min_cooccurrence` | 否 | integer | default=5; minimum=1.0; maximum=100.0 |  |
| `alpha` | 否 | number | default=0.05; exclusiveMinimum=0.0; exclusiveMaximum=1.0 |  |
| `categories` | 否 | array&lt;string&gt; / null |  |  |
| `detail` | 否 | boolean | default=false | 是否使用详细表（53子类别） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_level": {
      "$ref": "#/components/schemas/RegionLevel"
    },
    "region_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region Name"
    },
    "min_support": {
      "type": "integer",
      "maximum": 1000.0,
      "minimum": 1.0,
      "title": "Min Support",
      "default": 10
    },
    "min_cooccurrence": {
      "type": "integer",
      "maximum": 100.0,
      "minimum": 1.0,
      "title": "Min Cooccurrence",
      "default": 5
    },
    "alpha": {
      "type": "number",
      "exclusiveMaximum": 1.0,
      "exclusiveMinimum": 0.0,
      "title": "Alpha",
      "default": 0.05
    },
    "categories": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Categories"
    },
    "detail": {
      "type": "boolean",
      "title": "Detail",
      "description": "是否使用详细表（53子类别）",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "region_level"
  ],
  "title": "SemanticAnalysisParams",
  "description": "语义分析参数验证"
}
```

</details>

<a id="schema-semanticcategory"></a>

### `SemanticCategory`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `category` | 是 | string |  | 类别名称 |
| `description` | 是 | string |  | 类别描述 |
| `character_count` | 是 | integer |  | 字符数量 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "category": {
      "type": "string",
      "title": "Category",
      "description": "类别名称"
    },
    "description": {
      "type": "string",
      "title": "Description",
      "description": "类别描述"
    },
    "character_count": {
      "type": "integer",
      "title": "Character Count",
      "description": "字符数量"
    }
  },
  "type": "object",
  "required": [
    "category",
    "description",
    "character_count"
  ],
  "title": "SemanticCategory",
  "description": "语义类别模型"
}
```

</details>

<a id="schema-semanticnetworkparams"></a>

### `SemanticNetworkParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region_level` | 是 | [RegionLevel](#schema-regionlevel) |  |  |
| `region_name` | 否 | string / null |  |  |
| `min_edge_weight` | 否 | number | default=0.5; minimum=0.0; maximum=10.0 |  |
| `centrality_metrics` | 否 | array&lt;string&gt; | default=["degree", "betweenness"] |  |
| `detail` | 否 | boolean | default=false | 是否使用详细表（53子类别） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region_level": {
      "$ref": "#/components/schemas/RegionLevel"
    },
    "region_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Region Name"
    },
    "min_edge_weight": {
      "type": "number",
      "maximum": 10.0,
      "minimum": 0.0,
      "title": "Min Edge Weight",
      "default": 0.5
    },
    "centrality_metrics": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Centrality Metrics",
      "default": [
        "degree",
        "betweenness"
      ]
    },
    "detail": {
      "type": "boolean",
      "title": "Detail",
      "description": "是否使用详细表（53子类别）",
      "default": false
    }
  },
  "type": "object",
  "required": [
    "region_level"
  ],
  "title": "SemanticNetworkParams",
  "description": "语义网络参数"
}
```

</details>

<a id="schema-semantictendency"></a>

### `SemanticTendency`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `category` | 是 | string |  | 语义类别 |
| `lift` | 是 | number |  | Lift值 |
| `z_score` | 是 | number |  | Z-score值 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "category": {
      "type": "string",
      "title": "Category",
      "description": "语义类别"
    },
    "lift": {
      "type": "number",
      "title": "Lift",
      "description": "Lift值"
    },
    "z_score": {
      "type": "number",
      "title": "Z Score",
      "description": "Z-score值"
    }
  },
  "type": "object",
  "required": [
    "category",
    "lift",
    "z_score"
  ],
  "title": "SemanticTendency",
  "description": "语义倾向性模型"
}
```

</details>

<a id="schema-sessionactivityitem"></a>

### `SessionActivityItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `timestamp` | 是 | string (date-time) |  |  |
| `event_type` | 是 | string |  | Event type: created, refreshed, ip_changed, device_changed, flagged_suspicious, revoked |
| `details` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "title": "Timestamp"
    },
    "event_type": {
      "type": "string",
      "title": "Event Type",
      "description": "Event type: created, refreshed, ip_changed, device_changed, flagged_suspicious, revoked"
    },
    "details": {
      "type": "string",
      "title": "Details"
    }
  },
  "type": "object",
  "required": [
    "timestamp",
    "event_type",
    "details"
  ],
  "title": "SessionActivityItem"
}
```

</details>

<a id="schema-sessionactivityresponse"></a>

### `SessionActivityResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | 是 | string |  |  |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `events` | 是 | array&lt;[SessionActivityItem](#schema-sessionactivityitem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "session_id": {
      "type": "string",
      "title": "Session Id"
    },
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "events": {
      "items": {
        "$ref": "#/components/schemas/SessionActivityItem"
      },
      "type": "array",
      "title": "Events"
    }
  },
  "type": "object",
  "required": [
    "session_id",
    "user_id",
    "username",
    "events"
  ],
  "title": "SessionActivityResponse"
}
```

</details>

<a id="schema-sessiondetailresponse"></a>

### `SessionDetailResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `session_id` | 是 | string |  |  |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `expires_at` | 是 | string (date-time) |  |  |
| `last_activity_at` | 是 | string (date-time) |  |  |
| `revoked` | 是 | boolean |  |  |
| `revoked_at` | 否 | string (date-time) / null |  |  |
| `revoked_reason` | 否 | string / null |  |  |
| `device_info` | 否 | string / null |  |  |
| `first_device_info` | 否 | string / null |  |  |
| `device_fingerprint` | 否 | string / null |  |  |
| `device_change_count` | 是 | integer |  |  |
| `device_changed` | 是 | boolean |  |  |
| `current_ip` | 是 | string |  |  |
| `current_ip_location` | 否 | string / null |  |  |
| `first_ip` | 是 | string |  |  |
| `first_ip_location` | 否 | string / null |  |  |
| `ip_change_count` | 是 | integer |  |  |
| `ip_history` | 否 | array&lt;[IPHistoryItem](#schema-iphistoryitem)&gt; |  |  |
| `refresh_count` | 是 | integer |  |  |
| `total_online_seconds` | 是 | integer |  |  |
| `current_session_started_at` | 否 | string (date-time) / null |  |  |
| `last_seen` | 否 | string (date-time) / null |  |  |
| `is_suspicious` | 是 | boolean |  |  |
| `suspicious_reason` | 否 | string / null |  |  |
| `active_token_count` | 否 | integer | default=0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "session_id": {
      "type": "string",
      "title": "Session Id"
    },
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time",
      "title": "Expires At"
    },
    "last_activity_at": {
      "type": "string",
      "format": "date-time",
      "title": "Last Activity At"
    },
    "revoked": {
      "type": "boolean",
      "title": "Revoked"
    },
    "revoked_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Revoked At"
    },
    "revoked_reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Revoked Reason"
    },
    "device_info": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Device Info"
    },
    "first_device_info": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "First Device Info"
    },
    "device_fingerprint": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Device Fingerprint"
    },
    "device_change_count": {
      "type": "integer",
      "title": "Device Change Count"
    },
    "device_changed": {
      "type": "boolean",
      "title": "Device Changed"
    },
    "current_ip": {
      "type": "string",
      "title": "Current Ip"
    },
    "current_ip_location": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Current Ip Location"
    },
    "first_ip": {
      "type": "string",
      "title": "First Ip"
    },
    "first_ip_location": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "First Ip Location"
    },
    "ip_change_count": {
      "type": "integer",
      "title": "Ip Change Count"
    },
    "ip_history": {
      "items": {
        "$ref": "#/components/schemas/IPHistoryItem"
      },
      "type": "array",
      "title": "Ip History"
    },
    "refresh_count": {
      "type": "integer",
      "title": "Refresh Count"
    },
    "total_online_seconds": {
      "type": "integer",
      "title": "Total Online Seconds"
    },
    "current_session_started_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Current Session Started At"
    },
    "last_seen": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Seen"
    },
    "is_suspicious": {
      "type": "boolean",
      "title": "Is Suspicious"
    },
    "suspicious_reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Suspicious Reason"
    },
    "active_token_count": {
      "type": "integer",
      "title": "Active Token Count",
      "default": 0
    }
  },
  "type": "object",
  "required": [
    "id",
    "session_id",
    "user_id",
    "username",
    "created_at",
    "expires_at",
    "last_activity_at",
    "revoked",
    "device_change_count",
    "device_changed",
    "current_ip",
    "first_ip",
    "ip_change_count",
    "refresh_count",
    "total_online_seconds",
    "is_suspicious"
  ],
  "title": "SessionDetailResponse"
}
```

</details>

<a id="schema-sessiondurationdistribution"></a>

### `SessionDurationDistribution`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `0-5min` | 是 | integer |  |  |
| `5-30min` | 是 | integer |  |  |
| `30-60min` | 是 | integer |  |  |
| `1-2h` | 是 | integer |  |  |
| `2h+` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "0-5min": {
      "type": "integer",
      "title": "0-5Min"
    },
    "5-30min": {
      "type": "integer",
      "title": "5-30Min"
    },
    "30-60min": {
      "type": "integer",
      "title": "30-60Min"
    },
    "1-2h": {
      "type": "integer",
      "title": "1-2H"
    },
    "2h+": {
      "type": "integer",
      "title": "2H+"
    }
  },
  "type": "object",
  "required": [
    "0-5min",
    "5-30min",
    "30-60min",
    "1-2h",
    "2h+"
  ],
  "title": "SessionDurationDistribution"
}
```

</details>

<a id="schema-sessionlistresponse"></a>

### `SessionListResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total` | 是 | integer |  |  |
| `skip` | 是 | integer |  |  |
| `limit` | 是 | integer |  |  |
| `sessions` | 是 | array&lt;[SessionSummaryResponse](#schema-sessionsummaryresponse)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "skip": {
      "type": "integer",
      "title": "Skip"
    },
    "limit": {
      "type": "integer",
      "title": "Limit"
    },
    "sessions": {
      "items": {
        "$ref": "#/components/schemas/SessionSummaryResponse"
      },
      "type": "array",
      "title": "Sessions"
    }
  },
  "type": "object",
  "required": [
    "total",
    "skip",
    "limit",
    "sessions"
  ],
  "title": "SessionListResponse"
}
```

</details>

<a id="schema-sessionstatsresponse"></a>

### `SessionStatsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_sessions` | 是 | integer |  |  |
| `valid_sessions` | 是 | integer |  |  |
| `online_sessions_30m` | 是 | integer |  |  |
| `online_users_30m` | 是 | integer |  |  |
| `revoked_sessions` | 是 | integer |  |  |
| `expired_sessions` | 是 | integer |  |  |
| `expired_revoked_sessions` | 是 | integer |  |  |
| `expired_unrevoked_sessions` | 是 | integer |  |  |
| `suspicious_sessions` | 是 | integer |  |  |
| `active_suspicious_sessions` | 是 | integer |  |  |
| `revoked_suspicious_sessions` | 是 | integer |  |  |
| `unique_users_with_sessions` | 是 | integer |  |  |
| `total_online_hours` | 是 | number |  |  |
| `avg_online_hours_per_session` | 是 | number |  |  |
| `top_ip_changes` | 否 | array&lt;object&gt; |  |  |
| `top_device_changes` | 否 | array&lt;object&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total_sessions": {
      "type": "integer",
      "title": "Total Sessions"
    },
    "valid_sessions": {
      "type": "integer",
      "title": "Valid Sessions"
    },
    "online_sessions_30m": {
      "type": "integer",
      "title": "Online Sessions 30M"
    },
    "online_users_30m": {
      "type": "integer",
      "title": "Online Users 30M"
    },
    "revoked_sessions": {
      "type": "integer",
      "title": "Revoked Sessions"
    },
    "expired_sessions": {
      "type": "integer",
      "title": "Expired Sessions"
    },
    "expired_revoked_sessions": {
      "type": "integer",
      "title": "Expired Revoked Sessions"
    },
    "expired_unrevoked_sessions": {
      "type": "integer",
      "title": "Expired Unrevoked Sessions"
    },
    "suspicious_sessions": {
      "type": "integer",
      "title": "Suspicious Sessions"
    },
    "active_suspicious_sessions": {
      "type": "integer",
      "title": "Active Suspicious Sessions"
    },
    "revoked_suspicious_sessions": {
      "type": "integer",
      "title": "Revoked Suspicious Sessions"
    },
    "unique_users_with_sessions": {
      "type": "integer",
      "title": "Unique Users With Sessions"
    },
    "total_online_hours": {
      "type": "number",
      "title": "Total Online Hours"
    },
    "avg_online_hours_per_session": {
      "type": "number",
      "title": "Avg Online Hours Per Session"
    },
    "top_ip_changes": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Top Ip Changes"
    },
    "top_device_changes": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Top Device Changes"
    }
  },
  "type": "object",
  "required": [
    "total_sessions",
    "valid_sessions",
    "online_sessions_30m",
    "online_users_30m",
    "revoked_sessions",
    "expired_sessions",
    "expired_revoked_sessions",
    "expired_unrevoked_sessions",
    "suspicious_sessions",
    "active_suspicious_sessions",
    "revoked_suspicious_sessions",
    "unique_users_with_sessions",
    "total_online_hours",
    "avg_online_hours_per_session"
  ],
  "title": "SessionStatsResponse"
}
```

</details>

<a id="schema-sessionsummaryresponse"></a>

### `SessionSummaryResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `session_id` | 是 | string |  |  |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `expires_at` | 是 | string (date-time) |  |  |
| `last_activity_at` | 是 | string (date-time) |  |  |
| `revoked` | 是 | boolean |  |  |
| `current_ip` | 是 | string |  |  |
| `current_ip_location` | 否 | string / null |  |  |
| `device_info` | 否 | string / null |  |  |
| `is_suspicious` | 是 | boolean |  |  |
| `refresh_count` | 是 | integer |  |  |
| `active_token_count` | 否 | integer | default=0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "session_id": {
      "type": "string",
      "title": "Session Id"
    },
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time",
      "title": "Expires At"
    },
    "last_activity_at": {
      "type": "string",
      "format": "date-time",
      "title": "Last Activity At"
    },
    "revoked": {
      "type": "boolean",
      "title": "Revoked"
    },
    "current_ip": {
      "type": "string",
      "title": "Current Ip"
    },
    "current_ip_location": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Current Ip Location"
    },
    "device_info": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Device Info"
    },
    "is_suspicious": {
      "type": "boolean",
      "title": "Is Suspicious"
    },
    "refresh_count": {
      "type": "integer",
      "title": "Refresh Count"
    },
    "active_token_count": {
      "type": "integer",
      "title": "Active Token Count",
      "default": 0
    }
  },
  "type": "object",
  "required": [
    "id",
    "session_id",
    "user_id",
    "username",
    "created_at",
    "expires_at",
    "last_activity_at",
    "revoked",
    "current_ip",
    "is_suspicious",
    "refresh_count"
  ],
  "title": "SessionSummaryResponse"
}
```

</details>

<a id="schema-setactiverunidrequest"></a>

### `SetActiveRunIDRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | 是 | string |  |  |
| `updated_by` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "run_id": {
      "type": "string",
      "title": "Run Id"
    },
    "updated_by": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Updated By"
    }
  },
  "type": "object",
  "required": [
    "run_id"
  ],
  "title": "SetActiveRunIDRequest",
  "description": "设置激活 run_id 的请求体。"
}
```

</details>

<a id="schema-spatialawareclusteringparams"></a>

### `SpatialAwareClusteringParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `algorithm` | 是 | [AlgorithmType](#schema-algorithmtype) |  |  |
| `k` | 否 | integer / null |  |  |
| `spatial_run_id` | 是 | string |  | 空间聚类运行ID |
| `features` | 否 | object&lt;boolean&gt; |  |  |
| `preprocessing` | 否 | [PreprocessingConfig](#schema-preprocessingconfig) |  |  |
| `random_state` | 否 | integer | default=42; minimum=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "algorithm": {
      "$ref": "#/components/schemas/AlgorithmType"
    },
    "k": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 20.0,
          "minimum": 2.0
        },
        {
          "type": "null"
        }
      ],
      "title": "K"
    },
    "spatial_run_id": {
      "type": "string",
      "title": "Spatial Run Id",
      "description": "空间聚类运行ID"
    },
    "features": {
      "additionalProperties": {
        "type": "boolean"
      },
      "type": "object",
      "title": "Features"
    },
    "preprocessing": {
      "$ref": "#/components/schemas/PreprocessingConfig"
    },
    "random_state": {
      "type": "integer",
      "minimum": 0.0,
      "title": "Random State",
      "default": 42
    }
  },
  "type": "object",
  "required": [
    "algorithm",
    "spatial_run_id"
  ],
  "title": "SpatialAwareClusteringParams",
  "description": "空间感知聚类参数"
}
```

</details>

<a id="schema-spectrogramoptions"></a>

### `SpectrogramOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `window_length` | 否 | number | default=0.005 |  |
| `time_step` | 否 | number | default=0.002 |  |
| `frequency_step` | 否 | number | default=20.0 |  |
| `max_frequency` | 否 | number | default=8000.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "window_length": {
      "type": "number",
      "title": "Window Length",
      "default": 0.005
    },
    "time_step": {
      "type": "number",
      "title": "Time Step",
      "default": 0.002
    },
    "frequency_step": {
      "type": "number",
      "title": "Frequency Step",
      "default": 20.0
    },
    "max_frequency": {
      "type": "number",
      "title": "Max Frequency",
      "default": 8000.0
    }
  },
  "type": "object",
  "title": "SpectrogramOptions",
  "description": "Spectrogram extraction options."
}
```

</details>

<a id="schema-subsetclusteringparams"></a>

### `SubsetClusteringParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `filter` | 是 | [SubsetFilter](#schema-subsetfilter) |  |  |
| `clustering` | 是 | object |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "filter": {
      "$ref": "#/components/schemas/SubsetFilter"
    },
    "clustering": {
      "additionalProperties": true,
      "type": "object",
      "title": "Clustering"
    }
  },
  "type": "object",
  "required": [
    "filter",
    "clustering"
  ],
  "title": "SubsetClusteringParams",
  "description": "子集聚类参数"
}
```

</details>

<a id="schema-subsetcomparisonparams"></a>

### `SubsetComparisonParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `group_a` | 是 | [ComparisonGroup](#schema-comparisongroup) |  |  |
| `group_b` | 是 | [ComparisonGroup](#schema-comparisongroup) |  |  |
| `analysis` | 否 | object |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "group_a": {
      "$ref": "#/components/schemas/ComparisonGroup"
    },
    "group_b": {
      "$ref": "#/components/schemas/ComparisonGroup"
    },
    "analysis": {
      "additionalProperties": true,
      "type": "object",
      "title": "Analysis"
    }
  },
  "type": "object",
  "required": [
    "group_a",
    "group_b"
  ],
  "title": "SubsetComparisonParams",
  "description": "子集对比参数"
}
```

</details>

<a id="schema-subsetfilter"></a>

### `SubsetFilter`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `cities` | 否 | array&lt;string&gt; / null |  |  |
| `counties` | 否 | array&lt;string&gt; / null |  |  |
| `semantic_tags` | 否 | array&lt;string&gt; / null |  |  |
| `name_pattern` | 否 | string / null |  |  |
| `sample_size` | 否 | integer / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "cities": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Cities"
    },
    "counties": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Counties"
    },
    "semantic_tags": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Semantic Tags"
    },
    "name_pattern": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Name Pattern"
    },
    "sample_size": {
      "anyOf": [
        {
          "type": "integer",
          "maximum": 10000.0,
          "minimum": 100.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Sample Size"
    }
  },
  "type": "object",
  "title": "SubsetFilter",
  "description": "子集过滤器"
}
```

</details>

<a id="schema-subsetfilterrequest"></a>

### `SubsetFilterRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `city` | 否 | string / null |  | 城市精确筛选 |
| `county` | 否 | string / null |  | 区县精确筛选 |
| `township` | 否 | string / null |  | 乡镇精确筛选 |
| `keyword` | 否 | string / null |  | 村名模糊匹配 |
| `name_match_mode` | 否 | string | default="contains" | 名称匹配模式: contains &#124; startsWith &#124; endsWith &#124; equals |
| `length` | 否 | integer / null |  | 精确名称长度，与 min_length/max_length 互斥 |
| `min_length` | 否 | integer / null |  | 最小名称长度 |
| `max_length` | 否 | integer / null |  | 最大名称长度 |
| `semantic_categories` | 否 | array&lt;string&gt; / null |  | 语义大类，OR关系 |
| `semantic_match` | 否 | string | default="any" | 多类别逻辑: any &#124; all |
| `structure_patterns` | 否 | array&lt;string&gt; / null |  | 结构模式: modifier_head, modifier_only, head_only, settlement |
| `suffix` | 否 | string / null |  | 后缀字符 |
| `prefix` | 否 | string / null |  | 前缀字符 |
| `char_at_position` | 否 | integer / null |  | 指定位置 |
| `char_at_value` | 否 | string / null |  | 指定位置字符 |
| `lat_min` | 否 | number / null |  | 最小纬度 |
| `lat_max` | 否 | number / null |  | 最大纬度 |
| `lon_min` | 否 | number / null |  | 最小经度 |
| `lon_max` | 否 | number / null |  | 最大经度 |
| `max_results` | 否 | integer | default=5000; minimum=1.0; maximum=50000.0 | 返回上限 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City",
      "description": "城市精确筛选"
    },
    "county": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County",
      "description": "区县精确筛选"
    },
    "township": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township",
      "description": "乡镇精确筛选"
    },
    "keyword": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Keyword",
      "description": "村名模糊匹配"
    },
    "name_match_mode": {
      "type": "string",
      "title": "Name Match Mode",
      "description": "名称匹配模式: contains | startsWith | endsWith | equals",
      "default": "contains"
    },
    "length": {
      "anyOf": [
        {
          "type": "integer",
          "minimum": 1.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Length",
      "description": "精确名称长度，与 min_length/max_length 互斥"
    },
    "min_length": {
      "anyOf": [
        {
          "type": "integer",
          "minimum": 1.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Min Length",
      "description": "最小名称长度"
    },
    "max_length": {
      "anyOf": [
        {
          "type": "integer",
          "minimum": 1.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Max Length",
      "description": "最大名称长度"
    },
    "semantic_categories": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Semantic Categories",
      "description": "语义大类，OR关系"
    },
    "semantic_match": {
      "type": "string",
      "title": "Semantic Match",
      "description": "多类别逻辑: any | all",
      "default": "any"
    },
    "structure_patterns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Structure Patterns",
      "description": "结构模式: modifier_head, modifier_only, head_only, settlement"
    },
    "suffix": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 1,
          "minLength": 1
        },
        {
          "type": "null"
        }
      ],
      "title": "Suffix",
      "description": "后缀字符"
    },
    "prefix": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 1,
          "minLength": 1
        },
        {
          "type": "null"
        }
      ],
      "title": "Prefix",
      "description": "前缀字符"
    },
    "char_at_position": {
      "anyOf": [
        {
          "type": "integer",
          "minimum": 1.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Char At Position",
      "description": "指定位置"
    },
    "char_at_value": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 1,
          "minLength": 1
        },
        {
          "type": "null"
        }
      ],
      "title": "Char At Value",
      "description": "指定位置字符"
    },
    "lat_min": {
      "anyOf": [
        {
          "type": "number",
          "maximum": 90.0,
          "minimum": -90.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Lat Min",
      "description": "最小纬度"
    },
    "lat_max": {
      "anyOf": [
        {
          "type": "number",
          "maximum": 90.0,
          "minimum": -90.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Lat Max",
      "description": "最大纬度"
    },
    "lon_min": {
      "anyOf": [
        {
          "type": "number",
          "maximum": 180.0,
          "minimum": -180.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Lon Min",
      "description": "最小经度"
    },
    "lon_max": {
      "anyOf": [
        {
          "type": "number",
          "maximum": 180.0,
          "minimum": -180.0
        },
        {
          "type": "null"
        }
      ],
      "title": "Lon Max",
      "description": "最大经度"
    },
    "max_results": {
      "type": "integer",
      "maximum": 50000.0,
      "minimum": 1.0,
      "title": "Max Results",
      "description": "返回上限",
      "default": 5000
    }
  },
  "type": "object",
  "title": "SubsetFilterRequest",
  "description": "子集筛选请求模型"
}
```

</details>

<a id="schema-subsetfilterresponse"></a>

### `SubsetFilterResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `villages` | 是 | array&lt;[SubsetVillageItem](#schema-subsetvillageitem)&gt; |  | 村庄列表 |
| `total` | 是 | integer |  | 匹配总数 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "villages": {
      "items": {
        "$ref": "#/components/schemas/SubsetVillageItem"
      },
      "type": "array",
      "title": "Villages",
      "description": "村庄列表"
    },
    "total": {
      "type": "integer",
      "title": "Total",
      "description": "匹配总数"
    }
  },
  "type": "object",
  "required": [
    "villages",
    "total"
  ],
  "title": "SubsetFilterResponse",
  "description": "子集筛选响应模型"
}
```

</details>

<a id="schema-subsetvillageitem"></a>

### `SubsetVillageItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  | 村庄ID |
| `name` | 是 | string |  | 村庄名称 |
| `city` | 是 | string |  | 城市 |
| `county` | 是 | string |  | 区县 |
| `name_length` | 是 | integer |  | 名称长度 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id",
      "description": "村庄ID"
    },
    "name": {
      "type": "string",
      "title": "Name",
      "description": "村庄名称"
    },
    "city": {
      "type": "string",
      "title": "City",
      "description": "城市"
    },
    "county": {
      "type": "string",
      "title": "County",
      "description": "区县"
    },
    "name_length": {
      "type": "integer",
      "title": "Name Length",
      "description": "名称长度"
    }
  },
  "type": "object",
  "required": [
    "id",
    "name",
    "city",
    "county",
    "name_length"
  ],
  "title": "SubsetVillageItem",
  "description": "子集村庄条目模型"
}
```

</details>

<a id="schema-suggestioncreate"></a>

### `SuggestionCreate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | 是 | string | minLength=1; maxLength=200 |  |
| `content` | 是 | string | minLength=1; maxLength=5000 |  |
| `category` | 否 | string | default="general"; minLength=1; maxLength=50 |  |
| `source_path` | 否 | string / null |  |  |
| `context` | 否 | object / null |  |  |
| `contact` | 否 | string / null |  |  |
| `image_base64` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "title": {
      "type": "string",
      "maxLength": 200,
      "minLength": 1,
      "title": "Title"
    },
    "content": {
      "type": "string",
      "maxLength": 5000,
      "minLength": 1,
      "title": "Content"
    },
    "category": {
      "type": "string",
      "maxLength": 50,
      "minLength": 1,
      "title": "Category",
      "default": "general"
    },
    "source_path": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 300
        },
        {
          "type": "null"
        }
      ],
      "title": "Source Path"
    },
    "context": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Context"
    },
    "contact": {
      "anyOf": [
        {
          "type": "string",
          "maxLength": 200
        },
        {
          "type": "null"
        }
      ],
      "title": "Contact"
    },
    "image_base64": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Image Base64"
    }
  },
  "type": "object",
  "required": [
    "title",
    "content"
  ],
  "title": "SuggestionCreate"
}
```

</details>

<a id="schema-suggestioncreateresponse"></a>

### `SuggestionCreateResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `id` | 是 | integer |  |  |
| `message` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "message": {
      "type": "string",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "id",
    "message"
  ],
  "title": "SuggestionCreateResponse"
}
```

</details>

<a id="schema-suggestionitem"></a>

### `SuggestionItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `user_id` | 否 | integer / null |  |  |
| `username` | 否 | string / null |  |  |
| `title` | 是 | string |  |  |
| `content` | 是 | string |  |  |
| `category` | 是 | string |  |  |
| `source_path` | 否 | string / null |  |  |
| `context` | 否 | object / null |  |  |
| `contact` | 否 | string / null |  |  |
| `recent_api` | 否 | array&lt;object&gt; |  |  |
| `status` | 是 | string |  |  |
| `priority` | 是 | string |  |  |
| `admin_note` | 否 | string / null |  |  |
| `handled_at` | 否 | string (date-time) / null |  |  |
| `created_at` | 是 | string (date-time) |  |  |
| `updated_at` | 是 | string (date-time) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "user_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "User Id"
    },
    "username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Username"
    },
    "title": {
      "type": "string",
      "title": "Title"
    },
    "content": {
      "type": "string",
      "title": "Content"
    },
    "category": {
      "type": "string",
      "title": "Category"
    },
    "source_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Source Path"
    },
    "context": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Context"
    },
    "contact": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Contact"
    },
    "recent_api": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Recent Api"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "priority": {
      "type": "string",
      "title": "Priority"
    },
    "admin_note": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Admin Note"
    },
    "handled_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Handled At"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "title": "Updated At"
    }
  },
  "type": "object",
  "required": [
    "id",
    "title",
    "content",
    "category",
    "status",
    "priority",
    "created_at",
    "updated_at"
  ],
  "title": "SuggestionItem"
}
```

</details>

<a id="schema-suggestionlistresponse"></a>

### `SuggestionListResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 否 | boolean | default=true |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |
| `items` | 是 | array&lt;[SuggestionItem](#schema-suggestionitem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "default": true
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    },
    "items": {
      "items": {
        "$ref": "#/components/schemas/SuggestionItem"
      },
      "type": "array",
      "title": "Items"
    }
  },
  "type": "object",
  "required": [
    "total",
    "page",
    "page_size",
    "items"
  ],
  "title": "SuggestionListResponse"
}
```

</details>

<a id="schema-syllablecountsrequest"></a>

### `SyllableCountsRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 否 | array&lt;string&gt; |  | 地點簡稱列表 |
| `regions` | 否 | array&lt;string&gt; |  | 分區名稱列表 |
| `region_mode` | 否 | string | default="yindian" | 地區匹配模式 |
| `variant` | 否 | string | default="both" | 返回哪一檔：both（帶調+不帶調）、toneless（不帶調）、toned（帶調） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations",
      "description": "地點簡稱列表"
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions",
      "description": "分區名稱列表"
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "description": "地區匹配模式",
      "default": "yindian"
    },
    "variant": {
      "type": "string",
      "title": "Variant",
      "description": "返回哪一檔：both（帶調+不帶調）、toneless（不帶調）、toned（帶調）",
      "default": "both"
    }
  },
  "type": "object",
  "title": "SyllableCountsRequest",
  "description": "音節統計請求模型。\n\nlocations 和 regions 至少提供其一；regions 會按 region_mode 解析成地點簡稱。"
}
```

</details>

<a id="schema-systemoverview"></a>

### `SystemOverview`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_villages` | 是 | integer |  | 村庄总数 |
| `total_cities` | 是 | integer |  | 城市总数 |
| `total_counties` | 是 | integer |  | 区县总数 |
| `total_townships` | 是 | integer |  | 乡镇总数 |
| `unique_characters` | 是 | integer |  | 唯一字符数 |
| `database_size_mb` | 是 | number |  | 数据库大小(MB) |
| `last_updated` | 是 | string (date-time) |  | 最后更新时间 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total_villages": {
      "type": "integer",
      "title": "Total Villages",
      "description": "村庄总数"
    },
    "total_cities": {
      "type": "integer",
      "title": "Total Cities",
      "description": "城市总数"
    },
    "total_counties": {
      "type": "integer",
      "title": "Total Counties",
      "description": "区县总数"
    },
    "total_townships": {
      "type": "integer",
      "title": "Total Townships",
      "description": "乡镇总数"
    },
    "unique_characters": {
      "type": "integer",
      "title": "Unique Characters",
      "description": "唯一字符数"
    },
    "database_size_mb": {
      "type": "number",
      "title": "Database Size Mb",
      "description": "数据库大小(MB)"
    },
    "last_updated": {
      "type": "string",
      "format": "date-time",
      "title": "Last Updated",
      "description": "最后更新时间"
    }
  },
  "type": "object",
  "required": [
    "total_villages",
    "total_cities",
    "total_counties",
    "total_townships",
    "unique_characters",
    "database_size_mb",
    "last_updated"
  ],
  "title": "SystemOverview",
  "description": "系统概览模型"
}
```

</details>

<a id="schema-tablecolumn"></a>

### `TableColumn`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  | 列名 |
| `type` | 是 | string |  | 数据类型 |
| `not_null` | 是 | boolean |  | 是否非空 |
| `has_index` | 是 | boolean |  | 是否有索引 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name",
      "description": "列名"
    },
    "type": {
      "type": "string",
      "title": "Type",
      "description": "数据类型"
    },
    "not_null": {
      "type": "boolean",
      "title": "Not Null",
      "description": "是否非空"
    },
    "has_index": {
      "type": "boolean",
      "title": "Has Index",
      "description": "是否有索引"
    }
  },
  "type": "object",
  "required": [
    "name",
    "type",
    "not_null",
    "has_index"
  ],
  "title": "TableColumn",
  "description": "表列信息模型"
}
```

</details>

<a id="schema-tableinfo"></a>

### `TableInfo`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 是 | string |  | 表名 |
| `row_count` | 是 | integer |  | 行数 |
| `size_mb` | 是 | number |  | 总大小(MB) = 数据大小 + 索引大小 |
| `data_size_mb` | 否 | number / null |  | 表数据大小(MB) |
| `index_size_mb` | 否 | number / null |  | 表索引大小(MB) |
| `index_count` | 否 | integer | default=0 | 索引数量 |
| `last_modified` | 否 | string / null |  | 最后修改时间 |
| `columns` | 否 | array&lt;[TableColumn](#schema-tablecolumn)&gt; / null |  | 列信息 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "表名"
    },
    "row_count": {
      "type": "integer",
      "title": "Row Count",
      "description": "行数"
    },
    "size_mb": {
      "type": "number",
      "title": "Size Mb",
      "description": "总大小(MB) = 数据大小 + 索引大小"
    },
    "data_size_mb": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Data Size Mb",
      "description": "表数据大小(MB)"
    },
    "index_size_mb": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Index Size Mb",
      "description": "表索引大小(MB)"
    },
    "index_count": {
      "type": "integer",
      "title": "Index Count",
      "description": "索引数量",
      "default": 0
    },
    "last_modified": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Modified",
      "description": "最后修改时间"
    },
    "columns": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/components/schemas/TableColumn"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Columns",
      "description": "列信息"
    }
  },
  "type": "object",
  "required": [
    "table_name",
    "row_count",
    "size_mb"
  ],
  "title": "TableInfo",
  "description": "表信息模型"
}
```

</details>

<a id="schema-tendencymetric"></a>

### `TendencyMetric`

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "type": "string",
  "enum": [
    "z_score",
    "lift",
    "log_odds"
  ],
  "title": "TendencyMetric",
  "description": "倾向性指标类型"
}
```

</details>

<a id="schema-tokenpair"></a>

### `TokenPair`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `access_token` | 是 | string |  |  |
| `refresh_token` | 是 | string |  |  |
| `token_type` | 否 | string | default="bearer" |  |
| `expires_in` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "access_token": {
      "type": "string",
      "title": "Access Token"
    },
    "refresh_token": {
      "type": "string",
      "title": "Refresh Token"
    },
    "token_type": {
      "type": "string",
      "title": "Token Type",
      "default": "bearer"
    },
    "expires_in": {
      "type": "integer",
      "title": "Expires In"
    }
  },
  "type": "object",
  "required": [
    "access_token",
    "refresh_token",
    "expires_in"
  ],
  "title": "TokenPair"
}
```

</details>

<a id="schema-toponymdetail"></a>

### `ToponymDetail`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | string |  |  |
| `name` | 是 | string |  |  |
| `place_type` | 是 | string / null |  |  |
| `place_type_code` | 是 | string / null |  |  |
| `longitude` | 是 | number / null |  |  |
| `latitude` | 是 | number / null |  |  |
| `division_path` | 是 | array&lt;[ToponymDetailDivision](#schema-toponymdetaildivision)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "place_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Place Type"
    },
    "place_type_code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Place Type Code"
    },
    "longitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Longitude"
    },
    "latitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Latitude"
    },
    "division_path": {
      "items": {
        "$ref": "#/components/schemas/ToponymDetailDivision"
      },
      "type": "array",
      "title": "Division Path"
    }
  },
  "type": "object",
  "required": [
    "id",
    "name",
    "place_type",
    "place_type_code",
    "longitude",
    "latitude",
    "division_path"
  ],
  "title": "ToponymDetail"
}
```

</details>

<a id="schema-toponymdetaildivision"></a>

### `ToponymDetailDivision`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  |  |
| `level` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    }
  },
  "type": "object",
  "required": [
    "name",
    "level"
  ],
  "title": "ToponymDetailDivision"
}
```

</details>

<a id="schema-toponymdetailsresponse"></a>

### `ToponymDetailsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[ToponymDetail](#schema-toponymdetail)&gt; |  |  |
| `count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/ToponymDetail"
      },
      "type": "array",
      "title": "Items"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    }
  },
  "type": "object",
  "required": [
    "items",
    "count"
  ],
  "title": "ToponymDetailsResponse"
}
```

</details>

<a id="schema-toponymdivision"></a>

### `ToponymDivision`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | 是 | string |  |  |
| `name` | 是 | string |  |  |
| `level` | 是 | integer |  |  |
| `single_count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "code": {
      "type": "string",
      "title": "Code"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    },
    "single_count": {
      "type": "integer",
      "title": "Single Count"
    }
  },
  "type": "object",
  "required": [
    "code",
    "name",
    "level",
    "single_count"
  ],
  "title": "ToponymDivision"
}
```

</details>

<a id="schema-toponymdivisionsresponse"></a>

### `ToponymDivisionsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[ToponymDivision](#schema-toponymdivision)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/ToponymDivision"
      },
      "type": "array",
      "title": "Items"
    }
  },
  "type": "object",
  "required": [
    "items"
  ],
  "title": "ToponymDivisionsResponse"
}
```

</details>

<a id="schema-toponymnamedivisionnode"></a>

### `ToponymNameDivisionNode`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  |  |
| `level` | 是 | integer |  |  |
| `names` | 是 | array&lt;string&gt; |  |  |
| `children` | 是 | array&lt;[ToponymNameDivisionNode](#schema-toponymnamedivisionnode)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    },
    "names": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Names"
    },
    "children": {
      "items": {
        "$ref": "#/components/schemas/ToponymNameDivisionNode"
      },
      "type": "array",
      "title": "Children"
    }
  },
  "type": "object",
  "required": [
    "name",
    "level",
    "names",
    "children"
  ],
  "title": "ToponymNameDivisionNode"
}
```

</details>

<a id="schema-toponymnametreebootstrapchild"></a>

### `ToponymNameTreeBootstrapChild`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  |  |
| `level` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    }
  },
  "type": "object",
  "required": [
    "name",
    "level"
  ],
  "title": "ToponymNameTreeBootstrapChild"
}
```

</details>

<a id="schema-toponymnametreebootstrapnode"></a>

### `ToponymNameTreeBootstrapNode`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string |  |  |
| `level` | 是 | integer |  |  |
| `children` | 是 | array&lt;[ToponymNameTreeBootstrapChild](#schema-toponymnametreebootstrapchild)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    },
    "children": {
      "items": {
        "$ref": "#/components/schemas/ToponymNameTreeBootstrapChild"
      },
      "type": "array",
      "title": "Children"
    }
  },
  "type": "object",
  "required": [
    "name",
    "level",
    "children"
  ],
  "title": "ToponymNameTreeBootstrapNode"
}
```

</details>

<a id="schema-toponymnametreelazychildrenresponse"></a>

### `ToponymNameTreeLazyChildrenResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | 是 | string |  |  |
| `level` | 是 | integer |  |  |
| `parent_path` | 是 | array&lt;string&gt; |  |  |
| `children` | 是 | array&lt;[ToponymNameTreeBootstrapChild](#schema-toponymnametreebootstrapchild)&gt; |  |  |
| `has_more` | 是 | boolean |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "mode": {
      "type": "string",
      "title": "Mode"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    },
    "parent_path": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Parent Path"
    },
    "children": {
      "items": {
        "$ref": "#/components/schemas/ToponymNameTreeBootstrapChild"
      },
      "type": "array",
      "title": "Children"
    },
    "has_more": {
      "type": "boolean",
      "title": "Has More"
    }
  },
  "type": "object",
  "required": [
    "mode",
    "level",
    "parent_path",
    "children",
    "has_more"
  ],
  "title": "ToponymNameTreeLazyChildrenResponse"
}
```

</details>

<a id="schema-toponymnametreelazyfallbackresponse"></a>

### `ToponymNameTreeLazyFallbackResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | 是 | string |  |  |
| `reason` | 是 | string |  |  |
| `threshold` | 是 | integer |  |  |
| `filtered_count` | 是 | integer |  |  |
| `levels` | 是 | integer |  |  |
| `lazy_bootstrap` | 是 | array&lt;[ToponymNameTreeBootstrapNode](#schema-toponymnametreebootstrapnode)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "mode": {
      "type": "string",
      "title": "Mode"
    },
    "reason": {
      "type": "string",
      "title": "Reason"
    },
    "threshold": {
      "type": "integer",
      "title": "Threshold"
    },
    "filtered_count": {
      "type": "integer",
      "title": "Filtered Count"
    },
    "levels": {
      "type": "integer",
      "title": "Levels"
    },
    "lazy_bootstrap": {
      "items": {
        "$ref": "#/components/schemas/ToponymNameTreeBootstrapNode"
      },
      "type": "array",
      "title": "Lazy Bootstrap"
    }
  },
  "type": "object",
  "required": [
    "mode",
    "reason",
    "threshold",
    "filtered_count",
    "levels",
    "lazy_bootstrap"
  ],
  "title": "ToponymNameTreeLazyFallbackResponse"
}
```

</details>

<a id="schema-toponymnametreelazynamesresponse"></a>

### `ToponymNameTreeLazyNamesResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | 是 | string |  |  |
| `level` | 是 | integer |  |  |
| `parent_path` | 是 | array&lt;string&gt; |  |  |
| `names` | 是 | array&lt;string&gt; |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |
| `has_more` | 是 | boolean |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "mode": {
      "type": "string",
      "title": "Mode"
    },
    "level": {
      "type": "integer",
      "title": "Level"
    },
    "parent_path": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Parent Path"
    },
    "names": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Names"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    },
    "has_more": {
      "type": "boolean",
      "title": "Has More"
    }
  },
  "type": "object",
  "required": [
    "mode",
    "level",
    "parent_path",
    "names",
    "page",
    "page_size",
    "has_more"
  ],
  "title": "ToponymNameTreeLazyNamesResponse"
}
```

</details>

<a id="schema-toponymnametreeresponse"></a>

### `ToponymNameTreeResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | 否 | string | default="full" |  |
| `items` | 是 | array&lt;[ToponymNameDivisionNode](#schema-toponymnamedivisionnode)&gt; |  |  |
| `levels` | 否 | integer | default=4 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "mode": {
      "type": "string",
      "title": "Mode",
      "default": "full"
    },
    "items": {
      "items": {
        "$ref": "#/components/schemas/ToponymNameDivisionNode"
      },
      "type": "array",
      "title": "Items"
    },
    "levels": {
      "type": "integer",
      "title": "Levels",
      "default": 4
    }
  },
  "type": "object",
  "required": [
    "items"
  ],
  "title": "ToponymNameTreeResponse"
}
```

</details>

<a id="schema-toponymnamesresponse"></a>

### `ToponymNamesResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Items"
    }
  },
  "type": "object",
  "required": [
    "items"
  ],
  "title": "ToponymNamesResponse"
}
```

</details>

<a id="schema-toponympoint"></a>

### `ToponymPoint`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | string |  |  |
| `longitude` | 是 | number |  |  |
| `latitude` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "longitude": {
      "type": "number",
      "title": "Longitude"
    },
    "latitude": {
      "type": "number",
      "title": "Latitude"
    }
  },
  "type": "object",
  "required": [
    "id",
    "longitude",
    "latitude"
  ],
  "title": "ToponymPoint"
}
```

</details>

<a id="schema-toponympointsresponse"></a>

### `ToponymPointsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[ToponymPoint](#schema-toponympoint)&gt; |  |  |
| `count` | 是 | integer |  |  |
| `truncated` | 是 | boolean |  |  |
| `next` | 否 | null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/ToponymPoint"
      },
      "type": "array",
      "title": "Items"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    },
    "truncated": {
      "type": "boolean",
      "title": "Truncated"
    },
    "next": {
      "type": "null",
      "title": "Next"
    }
  },
  "type": "object",
  "required": [
    "items",
    "count",
    "truncated"
  ],
  "title": "ToponymPointsResponse"
}
```

</details>

<a id="schema-toponymsearchitem"></a>

### `ToponymSearchItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | string |  |  |
| `name` | 是 | string |  |  |
| `area_code` | 否 | string / null |  |  |
| `place_type_code` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "string",
      "title": "Id"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "area_code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Area Code"
    },
    "place_type_code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Place Type Code"
    }
  },
  "type": "object",
  "required": [
    "id",
    "name"
  ],
  "title": "ToponymSearchItem"
}
```

</details>

<a id="schema-toponymsearchresponse"></a>

### `ToponymSearchResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[ToponymSearchItem](#schema-toponymsearchitem)&gt; |  |  |
| `count` | 是 | integer |  |  |
| `truncated` | 是 | boolean |  |  |
| `next` | 否 | null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/ToponymSearchItem"
      },
      "type": "array",
      "title": "Items"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    },
    "truncated": {
      "type": "boolean",
      "title": "Truncated"
    },
    "next": {
      "type": "null",
      "title": "Next"
    }
  },
  "type": "object",
  "required": [
    "items",
    "count",
    "truncated"
  ],
  "title": "ToponymSearchResponse"
}
```

</details>

<a id="schema-trafficpattern"></a>

### `TrafficPattern`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `upload_ratio` | 是 | number |  |  |
| `download_ratio` | 是 | number |  |  |
| `total_traffic_kb` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "upload_ratio": {
      "type": "number",
      "title": "Upload Ratio"
    },
    "download_ratio": {
      "type": "number",
      "title": "Download Ratio"
    },
    "total_traffic_kb": {
      "type": "number",
      "title": "Total Traffic Kb"
    }
  },
  "type": "object",
  "required": [
    "upload_ratio",
    "download_ratio",
    "total_traffic_kb"
  ],
  "title": "TrafficPattern"
}
```

</details>

<a id="schema-trenditem"></a>

### `TrendItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `time` | 是 | string |  |  |
| `total_calls` | 是 | integer |  |  |
| `active_users` | 是 | integer |  |  |
| `avg_duration` | 是 | number |  |  |
| `top_api` | 是 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "time": {
      "type": "string",
      "title": "Time"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "active_users": {
      "type": "integer",
      "title": "Active Users"
    },
    "avg_duration": {
      "type": "number",
      "title": "Avg Duration"
    },
    "top_api": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Top Api"
    }
  },
  "type": "object",
  "required": [
    "time",
    "total_calls",
    "active_users",
    "avg_duration",
    "top_api"
  ],
  "title": "TrendItem"
}
```

</details>

<a id="schema-trendssummary"></a>

### `TrendsSummary`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `total_calls` | 是 | integer |  |  |
| `avg_daily_calls` | 是 | number |  |  |
| `peak_time` | 是 | string / null |  |  |
| `peak_calls` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "avg_daily_calls": {
      "type": "number",
      "title": "Avg Daily Calls"
    },
    "peak_time": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Peak Time"
    },
    "peak_calls": {
      "type": "integer",
      "title": "Peak Calls"
    }
  },
  "type": "object",
  "required": [
    "total_calls",
    "avg_daily_calls",
    "peak_time",
    "peak_calls"
  ],
  "title": "TrendsSummary"
}
```

</details>

<a id="schema-updatepassword"></a>

### `UpdatePassword`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string |  |  |
| `password` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "title": "Username"
    },
    "password": {
      "type": "string",
      "title": "Password"
    }
  },
  "type": "object",
  "required": [
    "username",
    "password"
  ],
  "title": "UpdatePassword"
}
```

</details>

<a id="schema-updaterowrequest"></a>

### `UpdateRowRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `row` | 是 | integer |  |  |
| `data` | 是 | object&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "row": {
      "type": "integer",
      "title": "Row"
    },
    "data": {
      "additionalProperties": {
        "type": "string"
      },
      "type": "object",
      "title": "Data"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "row",
    "data"
  ],
  "title": "UpdateRowRequest",
  "description": "更新行请求"
}
```

</details>

<a id="schema-uploadfilesresponse"></a>

### `UploadFilesResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `file_count` | 是 | integer |  |  |
| `files` | 是 | array&lt;string&gt; |  |  |
| `message` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "file_count": {
      "type": "integer",
      "title": "File Count"
    },
    "files": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Files"
    },
    "message": {
      "type": "string",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "file_count",
    "files",
    "message"
  ],
  "title": "UploadFilesResponse",
  "description": "上传待合并文件响应"
}
```

</details>

<a id="schema-uploadreferenceresponse"></a>

### `UploadReferenceResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `filename` | 是 | string |  |  |
| `char_count` | 是 | integer |  |  |
| `message` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "filename": {
      "type": "string",
      "title": "Filename"
    },
    "char_count": {
      "type": "integer",
      "title": "Char Count"
    },
    "message": {
      "type": "string",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "filename",
    "char_count",
    "message"
  ],
  "title": "UploadReferenceResponse",
  "description": "上传参考表响应"
}
```

</details>

<a id="schema-uploadresponse"></a>

### `UploadResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `filename` | 是 | string |  |  |
| `total_rows` | 是 | integer |  |  |
| `message` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "filename": {
      "type": "string",
      "title": "Filename"
    },
    "total_rows": {
      "type": "integer",
      "title": "Total Rows"
    },
    "message": {
      "type": "string",
      "title": "Message"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "filename",
    "total_rows",
    "message"
  ],
  "title": "UploadResponse",
  "description": "文件上传响应"
}
```

</details>

<a id="schema-useractivitydata"></a>

### `UserActivityData`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `dau` | 是 | array&lt;[DailyActivityItem](#schema-dailyactivityitem)&gt; |  | Daily active users for recent days |
| `wau` | 是 | integer |  | Weekly active users |
| `mau` | 是 | integer |  | Monthly active users |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "dau": {
      "items": {
        "$ref": "#/components/schemas/DailyActivityItem"
      },
      "type": "array",
      "title": "Dau",
      "description": "Daily active users for recent days"
    },
    "wau": {
      "type": "integer",
      "title": "Wau",
      "description": "Weekly active users"
    },
    "mau": {
      "type": "integer",
      "title": "Mau",
      "description": "Monthly active users"
    }
  },
  "type": "object",
  "required": [
    "dau",
    "wau",
    "mau"
  ],
  "title": "UserActivityData"
}
```

</details>

<a id="schema-userapimatrixcell"></a>

### `UserApiMatrixCell`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_index` | 是 | integer |  |  |
| `path_index` | 是 | integer |  |  |
| `count` | 是 | integer |  |  |
| `total_upload` | 否 | number | default=0.0 |  |
| `total_download` | 否 | number | default=0.0 |  |
| `total_duration` | 否 | number | default=0.0 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_index": {
      "type": "integer",
      "title": "User Index"
    },
    "path_index": {
      "type": "integer",
      "title": "Path Index"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    },
    "total_upload": {
      "type": "number",
      "title": "Total Upload",
      "default": 0.0
    },
    "total_download": {
      "type": "number",
      "title": "Total Download",
      "default": 0.0
    },
    "total_duration": {
      "type": "number",
      "title": "Total Duration",
      "default": 0.0
    }
  },
  "type": "object",
  "required": [
    "user_index",
    "path_index",
    "count"
  ],
  "title": "UserApiMatrixCell"
}
```

</details>

<a id="schema-userapimatrixmeta"></a>

### `UserApiMatrixMeta`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `min_calls` | 是 | integer |  |  |
| `max_users` | 是 | integer |  |  |
| `max_paths` | 是 | integer |  |  |
| `returned_users` | 是 | integer |  |  |
| `returned_paths` | 是 | integer |  |  |
| `returned_cells` | 是 | integer |  |  |
| `users_truncated` | 是 | boolean |  |  |
| `paths_truncated` | 是 | boolean |  |  |
| `exclude_paths` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "min_calls": {
      "type": "integer",
      "title": "Min Calls"
    },
    "max_users": {
      "type": "integer",
      "title": "Max Users"
    },
    "max_paths": {
      "type": "integer",
      "title": "Max Paths"
    },
    "returned_users": {
      "type": "integer",
      "title": "Returned Users"
    },
    "returned_paths": {
      "type": "integer",
      "title": "Returned Paths"
    },
    "returned_cells": {
      "type": "integer",
      "title": "Returned Cells"
    },
    "users_truncated": {
      "type": "boolean",
      "title": "Users Truncated"
    },
    "paths_truncated": {
      "type": "boolean",
      "title": "Paths Truncated"
    },
    "exclude_paths": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Paths"
    }
  },
  "type": "object",
  "required": [
    "min_calls",
    "max_users",
    "max_paths",
    "returned_users",
    "returned_paths",
    "returned_cells",
    "users_truncated",
    "paths_truncated"
  ],
  "title": "UserApiMatrixMeta"
}
```

</details>

<a id="schema-userapimatrixpath"></a>

### `UserApiMatrixPath`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | 是 | string |  |  |
| `total_calls` | 是 | integer |  |  |
| `unique_users` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path": {
      "type": "string",
      "title": "Path"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "unique_users": {
      "type": "integer",
      "title": "Unique Users"
    }
  },
  "type": "object",
  "required": [
    "path",
    "total_calls",
    "unique_users"
  ],
  "title": "UserApiMatrixPath"
}
```

</details>

<a id="schema-userapimatrixresponse"></a>

### `UserApiMatrixResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `meta` | 是 | [UserApiMatrixMeta](#schema-userapimatrixmeta) |  |  |
| `users` | 是 | array&lt;[UserApiMatrixUser](#schema-userapimatrixuser)&gt; |  |  |
| `paths` | 是 | array&lt;[UserApiMatrixPath](#schema-userapimatrixpath)&gt; |  |  |
| `matrix` | 是 | array&lt;[UserApiMatrixCell](#schema-userapimatrixcell)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "meta": {
      "$ref": "#/components/schemas/UserApiMatrixMeta"
    },
    "users": {
      "items": {
        "$ref": "#/components/schemas/UserApiMatrixUser"
      },
      "type": "array",
      "title": "Users"
    },
    "paths": {
      "items": {
        "$ref": "#/components/schemas/UserApiMatrixPath"
      },
      "type": "array",
      "title": "Paths"
    },
    "matrix": {
      "items": {
        "$ref": "#/components/schemas/UserApiMatrixCell"
      },
      "type": "array",
      "title": "Matrix"
    }
  },
  "type": "object",
  "required": [
    "meta",
    "users",
    "paths",
    "matrix"
  ],
  "title": "UserApiMatrixResponse"
}
```

</details>

<a id="schema-userapimatrixuser"></a>

### `UserApiMatrixUser`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `total_calls` | 是 | integer |  |  |
| `unique_apis` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "unique_apis": {
      "type": "integer",
      "title": "Unique Apis"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "total_calls",
    "unique_apis"
  ],
  "title": "UserApiMatrixUser"
}
```

</details>

<a id="schema-usercreate"></a>

### `UserCreate`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 是 | string | minLength=1; maxLength=50 |  |
| `email` | 是 | string (email) |  |  |
| `password` | 是 | string | minLength=6; maxLength=128 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "type": "string",
      "maxLength": 50,
      "minLength": 1,
      "title": "Username"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email"
    },
    "password": {
      "type": "string",
      "maxLength": 128,
      "minLength": 6,
      "title": "Password"
    }
  },
  "type": "object",
  "required": [
    "username",
    "email",
    "password"
  ],
  "title": "UserCreate"
}
```

</details>

<a id="schema-usergrowthresponse"></a>

### `UserGrowthResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `monthly_growth` | 是 | array&lt;[MonthlyGrowthItem](#schema-monthlygrowthitem)&gt; |  |  |
| `summary` | 是 | [GrowthSummary](#schema-growthsummary) |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "monthly_growth": {
      "items": {
        "$ref": "#/components/schemas/MonthlyGrowthItem"
      },
      "type": "array",
      "title": "Monthly Growth"
    },
    "summary": {
      "$ref": "#/components/schemas/GrowthSummary"
    }
  },
  "type": "object",
  "required": [
    "monthly_growth",
    "summary"
  ],
  "title": "UserGrowthResponse"
}
```

</details>

<a id="schema-userlistitem"></a>

### `UserListItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `email` | 是 | string (email) |  |  |
| `role` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email"
    },
    "role": {
      "type": "string",
      "title": "Role"
    }
  },
  "type": "object",
  "required": [
    "id",
    "username",
    "email",
    "role"
  ],
  "title": "UserListItem",
  "description": "轻量级用户列表项（仅包含基本信息）"
}
```

</details>

<a id="schema-usermeresponse"></a>

### `UserMeResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `email` | 是 | string (email) |  |  |
| `role` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `is_verified` | 是 | boolean |  |  |
| `created_at` | 否 | string (date-time) / null |  |  |
| `profile_picture` | 否 | string / null |  |  |
| `total_online_seconds` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email"
    },
    "role": {
      "type": "string",
      "title": "Role"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "is_verified": {
      "type": "boolean",
      "title": "Is Verified"
    },
    "created_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Created At"
    },
    "profile_picture": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Profile Picture"
    },
    "total_online_seconds": {
      "type": "integer",
      "title": "Total Online Seconds"
    }
  },
  "type": "object",
  "required": [
    "id",
    "username",
    "email",
    "role",
    "status",
    "is_verified",
    "total_online_seconds"
  ],
  "title": "UserMeResponse"
}
```

</details>

<a id="schema-userpreferenceitem"></a>

### `UserPreferenceItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `category_distribution` | 是 | object&lt;number&gt; |  |  |
| `total_calls` | 是 | integer |  |  |
| `api_diversity` | 是 | integer |  |  |
| `diversity_score` | 是 | number |  |  |
| `traffic_pattern` | 是 | [TrafficPattern](#schema-trafficpattern) |  |  |
| `top_apis` | 是 | array&lt;[app__schemas__admin__analytics__TopAPIItem__1](#schema-app__schemas__admin__analytics__topapiitem__1)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "category_distribution": {
      "additionalProperties": {
        "type": "number"
      },
      "type": "object",
      "title": "Category Distribution"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "api_diversity": {
      "type": "integer",
      "title": "Api Diversity"
    },
    "diversity_score": {
      "type": "number",
      "title": "Diversity Score"
    },
    "traffic_pattern": {
      "$ref": "#/components/schemas/TrafficPattern"
    },
    "top_apis": {
      "items": {
        "$ref": "#/components/schemas/app__schemas__admin__analytics__TopAPIItem__1"
      },
      "type": "array",
      "title": "Top Apis"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "category_distribution",
    "total_calls",
    "api_diversity",
    "diversity_score",
    "traffic_pattern",
    "top_apis"
  ],
  "title": "UserPreferenceItem"
}
```

</details>

<a id="schema-userpreferencesresponse"></a>

### `UserPreferencesResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `users` | 是 | array&lt;[UserPreferenceItem](#schema-userpreferenceitem)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "users": {
      "items": {
        "$ref": "#/components/schemas/UserPreferenceItem"
      },
      "type": "array",
      "title": "Users"
    }
  },
  "type": "object",
  "required": [
    "users"
  ],
  "title": "UserPreferencesResponse"
}
```

</details>

<a id="schema-userresponse"></a>

### `UserResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `email` | 是 | string (email) |  |  |
| `role` | 是 | string |  |  |
| `status` | 是 | string |  |  |
| `is_verified` | 是 | boolean |  |  |
| `created_at` | 否 | string (date-time) / null |  |  |
| `last_login` | 否 | string (date-time) / null |  |  |
| `last_login_ip` | 否 | string / null |  |  |
| `register_ip` | 否 | string / null |  |  |
| `login_count` | 是 | integer |  |  |
| `failed_attempts` | 是 | integer |  |  |
| `last_failed_login` | 否 | string (date-time) / null |  |  |
| `total_online_seconds` | 是 | integer |  |  |
| `current_session_started_at` | 否 | string (date-time) / null |  |  |
| `last_seen` | 否 | string (date-time) / null |  |  |
| `usage_summary` | 否 | array&lt;[ApiUsageStat](#schema-apiusagestat)&gt; | default=[] |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email"
    },
    "role": {
      "type": "string",
      "title": "Role"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "is_verified": {
      "type": "boolean",
      "title": "Is Verified"
    },
    "created_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Created At"
    },
    "last_login": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Login"
    },
    "last_login_ip": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Login Ip"
    },
    "register_ip": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Register Ip"
    },
    "login_count": {
      "type": "integer",
      "title": "Login Count"
    },
    "failed_attempts": {
      "type": "integer",
      "title": "Failed Attempts"
    },
    "last_failed_login": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Failed Login"
    },
    "total_online_seconds": {
      "type": "integer",
      "title": "Total Online Seconds"
    },
    "current_session_started_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Current Session Started At"
    },
    "last_seen": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Seen"
    },
    "usage_summary": {
      "items": {
        "$ref": "#/components/schemas/ApiUsageStat"
      },
      "type": "array",
      "title": "Usage Summary",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "id",
    "username",
    "email",
    "role",
    "status",
    "is_verified",
    "login_count",
    "failed_attempts",
    "total_online_seconds"
  ],
  "title": "UserResponse"
}
```

</details>

<a id="schema-usersegmentitem"></a>

### `UserSegmentItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 是 | string |  |  |
| `total_calls` | 是 | integer |  |  |
| `total_duration` | 是 | number |  |  |
| `days_inactive` | 是 | integer |  |  |
| `last_seen` | 是 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "total_calls": {
      "type": "integer",
      "title": "Total Calls"
    },
    "total_duration": {
      "type": "number",
      "title": "Total Duration"
    },
    "days_inactive": {
      "type": "integer",
      "title": "Days Inactive"
    },
    "last_seen": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Last Seen"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "username",
    "total_calls",
    "total_duration",
    "days_inactive",
    "last_seen"
  ],
  "title": "UserSegmentItem"
}
```

</details>

<a id="schema-usersegmentsresponse"></a>

### `UserSegmentsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `segments` | 是 | array&lt;[SegmentInfo](#schema-segmentinfo)&gt; |  |  |
| `total_users` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "segments": {
      "items": {
        "$ref": "#/components/schemas/SegmentInfo"
      },
      "type": "array",
      "title": "Segments"
    },
    "total_users": {
      "type": "integer",
      "title": "Total Users"
    }
  },
  "type": "object",
  "required": [
    "segments",
    "total_users"
  ],
  "title": "UserSegmentsResponse"
}
```

</details>

<a id="schema-userupdateschema"></a>

### `UserUpdateSchema`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | 否 | string / null |  |  |
| `email` | 否 | string (email) / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Username"
    },
    "email": {
      "anyOf": [
        {
          "type": "string",
          "format": "email"
        },
        {
          "type": "null"
        }
      ],
      "title": "Email"
    }
  },
  "type": "object",
  "title": "UserUpdateSchema"
}
```

</details>

<a id="schema-validationerror"></a>

### `ValidationError`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `loc` | 是 | array&lt;string / integer&gt; |  |  |
| `msg` | 是 | string |  |  |
| `type` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "loc": {
      "items": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "integer"
          }
        ]
      },
      "type": "array",
      "title": "Location"
    },
    "msg": {
      "type": "string",
      "title": "Message"
    },
    "type": {
      "type": "string",
      "title": "Error Type"
    }
  },
  "type": "object",
  "required": [
    "loc",
    "msg",
    "type"
  ],
  "title": "ValidationError"
}
```

</details>

<a id="schema-vectorcomparerequest"></a>

### `VectorCompareRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `level1` | 是 | string |  |  |
| `city1` | 否 | string / null |  |  |
| `county1` | 否 | string / null |  |  |
| `township1` | 否 | string / null |  |  |
| `level2` | 是 | string |  |  |
| `city2` | 否 | string / null |  |  |
| `county2` | 否 | string / null |  |  |
| `township2` | 否 | string / null |  |  |
| `run_id` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "level1": {
      "type": "string",
      "title": "Level1"
    },
    "city1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City1"
    },
    "county1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County1"
    },
    "township1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township1"
    },
    "level2": {
      "type": "string",
      "title": "Level2"
    },
    "city2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City2"
    },
    "county2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County2"
    },
    "township2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township2"
    },
    "run_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "level1",
    "level2"
  ],
  "title": "VectorCompareRequest",
  "description": "区域向量比较请求模型（支持层级路径参数）"
}
```

</details>

<a id="schema-vectorcompareresponse"></a>

### `VectorCompareResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `region1_name` | 是 | string |  |  |
| `level1` | 是 | string |  |  |
| `city1` | 否 | string / null |  |  |
| `county1` | 否 | string / null |  |  |
| `township1` | 否 | string / null |  |  |
| `region2_name` | 是 | string |  |  |
| `level2` | 是 | string |  |  |
| `city2` | 否 | string / null |  |  |
| `county2` | 否 | string / null |  |  |
| `township2` | 否 | string / null |  |  |
| `feature_dimension` | 是 | integer |  |  |
| `categories` | 是 | array&lt;string&gt; |  |  |
| `cosine_similarity` | 是 | number |  |  |
| `euclidean_distance` | 是 | number |  |  |
| `manhattan_distance` | 是 | number |  |  |
| `vector_diff` | 是 | array&lt;number&gt; |  |  |
| `region1_vector` | 是 | array&lt;number&gt; |  |  |
| `region2_vector` | 是 | array&lt;number&gt; |  |  |
| `run_id` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "region1_name": {
      "type": "string",
      "title": "Region1 Name"
    },
    "level1": {
      "type": "string",
      "title": "Level1"
    },
    "city1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City1"
    },
    "county1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County1"
    },
    "township1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township1"
    },
    "region2_name": {
      "type": "string",
      "title": "Region2 Name"
    },
    "level2": {
      "type": "string",
      "title": "Level2"
    },
    "city2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City2"
    },
    "county2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County2"
    },
    "township2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Township2"
    },
    "feature_dimension": {
      "type": "integer",
      "title": "Feature Dimension"
    },
    "categories": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Categories"
    },
    "cosine_similarity": {
      "type": "number",
      "title": "Cosine Similarity"
    },
    "euclidean_distance": {
      "type": "number",
      "title": "Euclidean Distance"
    },
    "manhattan_distance": {
      "type": "number",
      "title": "Manhattan Distance"
    },
    "vector_diff": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "title": "Vector Diff"
    },
    "region1_vector": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "title": "Region1 Vector"
    },
    "region2_vector": {
      "items": {
        "type": "number"
      },
      "type": "array",
      "title": "Region2 Vector"
    },
    "run_id": {
      "type": "string",
      "title": "Run Id"
    }
  },
  "type": "object",
  "required": [
    "region1_name",
    "level1",
    "region2_name",
    "level2",
    "feature_dimension",
    "categories",
    "cosine_similarity",
    "euclidean_distance",
    "manhattan_distance",
    "vector_diff",
    "region1_vector",
    "region2_vector",
    "run_id"
  ],
  "title": "VectorCompareResponse",
  "description": "区域向量比较响应模型"
}
```

</details>

<a id="schema-villagebasic"></a>

### `VillageBasic`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `village_id` | 是 | integer |  | 村庄ID |
| `village_name` | 是 | string |  | 村名 |
| `city` | 是 | string |  | 城市 |
| `county` | 是 | string |  | 区县 |
| `township` | 是 | string |  | 乡镇 |
| `longitude` | 否 | number / null |  | 经度 |
| `latitude` | 否 | number / null |  | 纬度 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "village_id": {
      "type": "integer",
      "title": "Village Id",
      "description": "村庄ID"
    },
    "village_name": {
      "type": "string",
      "title": "Village Name",
      "description": "村名"
    },
    "city": {
      "type": "string",
      "title": "City",
      "description": "城市"
    },
    "county": {
      "type": "string",
      "title": "County",
      "description": "区县"
    },
    "township": {
      "type": "string",
      "title": "Township",
      "description": "乡镇"
    },
    "longitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Longitude",
      "description": "经度"
    },
    "latitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Latitude",
      "description": "纬度"
    }
  },
  "type": "object",
  "required": [
    "village_id",
    "village_name",
    "city",
    "county",
    "township"
  ],
  "title": "VillageBasic",
  "description": "村庄基础信息模型"
}
```

</details>

<a id="schema-villagedetail"></a>

### `VillageDetail`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `basic_info` | 是 | [VillageBasic](#schema-villagebasic) |  | 基础信息 |
| `semantic_tags` | 是 | array&lt;string&gt; |  | 语义标签 |
| `suffix` | 是 | string |  | 后缀 |
| `cluster_id` | 否 | integer / null |  | 聚类ID |
| `spatial_features` | 否 | object / null |  | 空间特征 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "basic_info": {
      "$ref": "#/components/schemas/VillageBasic",
      "description": "基础信息"
    },
    "semantic_tags": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Semantic Tags",
      "description": "语义标签"
    },
    "suffix": {
      "type": "string",
      "title": "Suffix",
      "description": "后缀"
    },
    "cluster_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Cluster Id",
      "description": "聚类ID"
    },
    "spatial_features": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Spatial Features",
      "description": "空间特征"
    }
  },
  "type": "object",
  "required": [
    "basic_info",
    "semantic_tags",
    "suffix"
  ],
  "title": "VillageDetail",
  "description": "村庄详情模型"
}
```

</details>

<a id="schema-villageinput"></a>

### `VillageInput`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `village_id` | 是 | string | minLength=1; maxLength=50 | 村庄唯一标识符 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "village_id": {
      "type": "string",
      "maxLength": 50,
      "minLength": 1,
      "title": "Village Id",
      "description": "村庄唯一标识符"
    }
  },
  "type": "object",
  "required": [
    "village_id"
  ],
  "title": "VillageInput",
  "description": "村庄输入（仅支持 ID）"
}
```

</details>

<a id="schema-vocabularyitemresponse"></a>

### `VocabularyItemResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `standard_word` | 是 | string |  |  |
| `local_expression` | 是 | string |  |  |
| `ipa` | 是 | string |  |  |
| `notes` | 是 | string |  |  |
| `informations` | 是 | string |  |  |
| `location_name` | 是 | string |  |  |
| `location_label` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "standard_word": {
      "type": "string",
      "title": "Standard Word"
    },
    "local_expression": {
      "type": "string",
      "title": "Local Expression"
    },
    "ipa": {
      "type": "string",
      "title": "Ipa"
    },
    "notes": {
      "type": "string",
      "title": "Notes"
    },
    "informations": {
      "type": "string",
      "title": "Informations"
    },
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "location_label": {
      "type": "string",
      "title": "Location Label"
    }
  },
  "type": "object",
  "required": [
    "id",
    "standard_word",
    "local_expression",
    "ipa",
    "notes",
    "informations",
    "location_name",
    "location_label"
  ],
  "title": "VocabularyItemResponse"
}
```

</details>

<a id="schema-vocabularyitemsresponse"></a>

### `VocabularyItemsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[VocabularyItemResponse](#schema-vocabularyitemresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/VocabularyItemResponse"
      },
      "type": "array",
      "title": "Items"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "items",
    "total",
    "page",
    "page_size"
  ],
  "title": "VocabularyItemsResponse"
}
```

</details>

<a id="schema-vocabularylocationoptionresponse"></a>

### `VocabularyLocationOptionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `location_name` | 是 | string |  |  |
| `location_label` | 是 | string |  |  |
| `province` | 否 | string | default="" |  |
| `city` | 否 | string | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "location_label": {
      "type": "string",
      "title": "Location Label"
    },
    "province": {
      "type": "string",
      "title": "Province",
      "default": ""
    },
    "city": {
      "type": "string",
      "title": "City",
      "default": ""
    }
  },
  "type": "object",
  "required": [
    "location_name",
    "location_label"
  ],
  "title": "VocabularyLocationOptionResponse"
}
```

</details>

<a id="schema-vocabularylocationoptionsresponse"></a>

### `VocabularyLocationOptionsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 是 | array&lt;[VocabularyLocationOptionResponse](#schema-vocabularylocationoptionresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "$ref": "#/components/schemas/VocabularyLocationOptionResponse"
      },
      "type": "array",
      "title": "Locations"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    }
  },
  "type": "object",
  "required": [
    "locations",
    "total"
  ],
  "title": "VocabularyLocationOptionsResponse"
}
```

</details>

<a id="schema-vocabularylocationresponse"></a>

### `VocabularyLocationResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `username` | 否 | string | default="" |  |
| `location_name` | 是 | string |  |  |
| `coordinates` | 是 | string |  |  |
| `province` | 是 | string |  |  |
| `city` | 是 | string |  |  |
| `county` | 是 | string |  |  |
| `town` | 是 | string |  |  |
| `administrative_village` | 是 | string |  |  |
| `natural_village` | 是 | string |  |  |
| `yindian_region` | 是 | string |  |  |
| `atlas_region` | 是 | string |  |  |
| `vocabulary_source` | 否 | string | default="" |  |
| `description` | 否 | string | default="" |  |
| `other` | 否 | string | default="" |  |
| `location_label` | 是 | string |  |  |
| `t1` | 否 | string | default="" |  |
| `t2` | 否 | string | default="" |  |
| `t3` | 否 | string | default="" |  |
| `t4` | 否 | string | default="" |  |
| `t5` | 否 | string | default="" |  |
| `t6` | 否 | string | default="" |  |
| `t7` | 否 | string | default="" |  |
| `t8` | 否 | string | default="" |  |
| `t9` | 否 | string | default="" |  |
| `t10` | 否 | string | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "username": {
      "type": "string",
      "title": "Username",
      "default": ""
    },
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "coordinates": {
      "type": "string",
      "title": "Coordinates"
    },
    "province": {
      "type": "string",
      "title": "Province"
    },
    "city": {
      "type": "string",
      "title": "City"
    },
    "county": {
      "type": "string",
      "title": "County"
    },
    "town": {
      "type": "string",
      "title": "Town"
    },
    "administrative_village": {
      "type": "string",
      "title": "Administrative Village"
    },
    "natural_village": {
      "type": "string",
      "title": "Natural Village"
    },
    "yindian_region": {
      "type": "string",
      "title": "Yindian Region"
    },
    "atlas_region": {
      "type": "string",
      "title": "Atlas Region"
    },
    "vocabulary_source": {
      "type": "string",
      "title": "Vocabulary Source",
      "default": ""
    },
    "description": {
      "type": "string",
      "title": "Description",
      "default": ""
    },
    "other": {
      "type": "string",
      "title": "Other",
      "default": ""
    },
    "location_label": {
      "type": "string",
      "title": "Location Label"
    },
    "t1": {
      "type": "string",
      "title": "T1",
      "default": ""
    },
    "t2": {
      "type": "string",
      "title": "T2",
      "default": ""
    },
    "t3": {
      "type": "string",
      "title": "T3",
      "default": ""
    },
    "t4": {
      "type": "string",
      "title": "T4",
      "default": ""
    },
    "t5": {
      "type": "string",
      "title": "T5",
      "default": ""
    },
    "t6": {
      "type": "string",
      "title": "T6",
      "default": ""
    },
    "t7": {
      "type": "string",
      "title": "T7",
      "default": ""
    },
    "t8": {
      "type": "string",
      "title": "T8",
      "default": ""
    },
    "t9": {
      "type": "string",
      "title": "T9",
      "default": ""
    },
    "t10": {
      "type": "string",
      "title": "T10",
      "default": ""
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "location_name",
    "coordinates",
    "province",
    "city",
    "county",
    "town",
    "administrative_village",
    "natural_village",
    "yindian_region",
    "atlas_region",
    "location_label"
  ],
  "title": "VocabularyLocationResponse"
}
```

</details>

<a id="schema-vocabularylocationtransferrequest"></a>

### `VocabularyLocationTransferRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `location_name` | 是 | string |  |  |
| `user_id` | 否 | integer / null |  |  |
| `username` | 否 | string / null |  |  |
| `target_user_id` | 否 | integer / null |  |  |
| `target_username` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "user_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "User Id"
    },
    "username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Username"
    },
    "target_user_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Target User Id"
    },
    "target_username": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Target Username"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "location_name"
  ],
  "title": "VocabularyLocationTransferRequest"
}
```

</details>

<a id="schema-vocabularylocationtransferresponse"></a>

### `VocabularyLocationTransferResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 是 | boolean |  |  |
| `location_name` | 是 | string |  |  |
| `permission_level` | 是 | string |  |  |
| `source_user_id` | 是 | integer |  |  |
| `source_username` | 否 | string | default="" |  |
| `target_user_id` | 是 | integer |  |  |
| `target_username` | 否 | string | default="" |  |
| `transferred_entries_count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success"
    },
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "permission_level": {
      "type": "string",
      "title": "Permission Level"
    },
    "source_user_id": {
      "type": "integer",
      "title": "Source User Id"
    },
    "source_username": {
      "type": "string",
      "title": "Source Username",
      "default": ""
    },
    "target_user_id": {
      "type": "integer",
      "title": "Target User Id"
    },
    "target_username": {
      "type": "string",
      "title": "Target Username",
      "default": ""
    },
    "transferred_entries_count": {
      "type": "integer",
      "title": "Transferred Entries Count"
    }
  },
  "type": "object",
  "required": [
    "success",
    "location_name",
    "permission_level",
    "source_user_id",
    "target_user_id",
    "transferred_entries_count"
  ],
  "title": "VocabularyLocationTransferResponse"
}
```

</details>

<a id="schema-vocabularylocationupdaterequest"></a>

### `VocabularyLocationUpdateRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `new_location_name` | 否 | string / null |  |  |
| `coordinates` | 否 | string / null |  |  |
| `province` | 否 | string / null |  |  |
| `city` | 否 | string / null |  |  |
| `county` | 否 | string / null |  |  |
| `town` | 否 | string / null |  |  |
| `administrative_village` | 否 | string / null |  |  |
| `natural_village` | 否 | string / null |  |  |
| `yindian_region` | 否 | string / null |  |  |
| `atlas_region` | 否 | string / null |  |  |
| `vocabulary_source` | 否 | string / null |  |  |
| `description` | 否 | string / null |  |  |
| `other` | 否 | string / null |  |  |
| `t1` | 否 | string / null |  |  |
| `t2` | 否 | string / null |  |  |
| `t3` | 否 | string / null |  |  |
| `t4` | 否 | string / null |  |  |
| `t5` | 否 | string / null |  |  |
| `t6` | 否 | string / null |  |  |
| `t7` | 否 | string / null |  |  |
| `t8` | 否 | string / null |  |  |
| `t9` | 否 | string / null |  |  |
| `t10` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "new_location_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "New Location Name"
    },
    "coordinates": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Coordinates"
    },
    "province": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Province"
    },
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City"
    },
    "county": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County"
    },
    "town": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Town"
    },
    "administrative_village": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Administrative Village"
    },
    "natural_village": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Natural Village"
    },
    "yindian_region": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Yindian Region"
    },
    "atlas_region": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Atlas Region"
    },
    "vocabulary_source": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Vocabulary Source"
    },
    "description": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Description"
    },
    "other": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Other"
    },
    "t1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T1"
    },
    "t2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T2"
    },
    "t3": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T3"
    },
    "t4": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T4"
    },
    "t5": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T5"
    },
    "t6": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T6"
    },
    "t7": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T7"
    },
    "t8": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T8"
    },
    "t9": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T9"
    },
    "t10": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "T10"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "VocabularyLocationUpdateRequest"
}
```

</details>

<a id="schema-vocabularylocationsresponse"></a>

### `VocabularyLocationsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 是 | array&lt;[VocabularyLocationResponse](#schema-vocabularylocationresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "$ref": "#/components/schemas/VocabularyLocationResponse"
      },
      "type": "array",
      "title": "Locations"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "locations",
    "total",
    "page",
    "page_size"
  ],
  "title": "VocabularyLocationsResponse"
}
```

</details>

<a id="schema-vocabularylogresponse"></a>

### `VocabularyLogResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `operation_id` | 是 | string |  |  |
| `user_id` | 是 | integer |  |  |
| `permission_level` | 是 | string |  |  |
| `source` | 是 | string |  |  |
| `action` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `target_scope` | 是 | string |  |  |
| `affected_rows` | 是 | integer |  |  |
| `status` | 是 | string |  |  |
| `payload_json` | 是 | string |  |  |
| `created_at` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "operation_id": {
      "type": "string",
      "title": "Operation Id"
    },
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "permission_level": {
      "type": "string",
      "title": "Permission Level"
    },
    "source": {
      "type": "string",
      "title": "Source"
    },
    "action": {
      "type": "string",
      "title": "Action"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "target_scope": {
      "type": "string",
      "title": "Target Scope"
    },
    "affected_rows": {
      "type": "integer",
      "title": "Affected Rows"
    },
    "status": {
      "type": "string",
      "title": "Status"
    },
    "payload_json": {
      "type": "string",
      "title": "Payload Json"
    },
    "created_at": {
      "type": "string",
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "id",
    "operation_id",
    "user_id",
    "permission_level",
    "source",
    "action",
    "table_name",
    "target_scope",
    "affected_rows",
    "status",
    "payload_json",
    "created_at"
  ],
  "title": "VocabularyLogResponse"
}
```

</details>

<a id="schema-vocabularylogsresponse"></a>

### `VocabularyLogsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `logs` | 是 | array&lt;[VocabularyLogResponse](#schema-vocabularylogresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "logs": {
      "items": {
        "$ref": "#/components/schemas/VocabularyLogResponse"
      },
      "type": "array",
      "title": "Logs"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "logs",
    "total",
    "page",
    "page_size"
  ],
  "title": "VocabularyLogsResponse"
}
```

</details>

<a id="schema-vocabularymapitempointresponse"></a>

### `VocabularyMapItemPointResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `location_name` | 是 | string |  |  |
| `province` | 否 | string | default="" |  |
| `city` | 否 | string | default="" |  |
| `county` | 否 | string | default="" |  |
| `town` | 否 | string | default="" |  |
| `administrative_village` | 否 | string | default="" |  |
| `natural_village` | 否 | string | default="" |  |
| `yindian_region` | 否 | string | default="" |  |
| `atlas_region` | 否 | string | default="" |  |
| `longitude` | 是 | number |  |  |
| `latitude` | 是 | number |  |  |
| `entry_count` | 是 | integer |  |  |
| `items` | 是 | array&lt;[VocabularyMapItemResponse](#schema-vocabularymapitemresponse)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "province": {
      "type": "string",
      "title": "Province",
      "default": ""
    },
    "city": {
      "type": "string",
      "title": "City",
      "default": ""
    },
    "county": {
      "type": "string",
      "title": "County",
      "default": ""
    },
    "town": {
      "type": "string",
      "title": "Town",
      "default": ""
    },
    "administrative_village": {
      "type": "string",
      "title": "Administrative Village",
      "default": ""
    },
    "natural_village": {
      "type": "string",
      "title": "Natural Village",
      "default": ""
    },
    "yindian_region": {
      "type": "string",
      "title": "Yindian Region",
      "default": ""
    },
    "atlas_region": {
      "type": "string",
      "title": "Atlas Region",
      "default": ""
    },
    "longitude": {
      "type": "number",
      "title": "Longitude"
    },
    "latitude": {
      "type": "number",
      "title": "Latitude"
    },
    "entry_count": {
      "type": "integer",
      "title": "Entry Count"
    },
    "items": {
      "items": {
        "$ref": "#/components/schemas/VocabularyMapItemResponse"
      },
      "type": "array",
      "title": "Items"
    }
  },
  "type": "object",
  "required": [
    "location_name",
    "longitude",
    "latitude",
    "entry_count",
    "items"
  ],
  "title": "VocabularyMapItemPointResponse"
}
```

</details>

<a id="schema-vocabularymapitemresponse"></a>

### `VocabularyMapItemResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `standard_word` | 是 | string |  |  |
| `local_expression` | 是 | string |  |  |
| `ipa` | 是 | string |  |  |
| `notes` | 是 | string |  |  |
| `informations` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "standard_word": {
      "type": "string",
      "title": "Standard Word"
    },
    "local_expression": {
      "type": "string",
      "title": "Local Expression"
    },
    "ipa": {
      "type": "string",
      "title": "Ipa"
    },
    "notes": {
      "type": "string",
      "title": "Notes"
    },
    "informations": {
      "type": "string",
      "title": "Informations"
    }
  },
  "type": "object",
  "required": [
    "id",
    "standard_word",
    "local_expression",
    "ipa",
    "notes",
    "informations"
  ],
  "title": "VocabularyMapItemResponse"
}
```

</details>

<a id="schema-vocabularymapitemsresponse"></a>

### `VocabularyMapItemsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `points` | 是 | array&lt;[VocabularyMapItemPointResponse](#schema-vocabularymapitempointresponse)&gt; |  |  |
| `total_entries` | 是 | integer |  |  |
| `total_points` | 是 | integer |  |  |
| `omitted_without_coordinates` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "points": {
      "items": {
        "$ref": "#/components/schemas/VocabularyMapItemPointResponse"
      },
      "type": "array",
      "title": "Points"
    },
    "total_entries": {
      "type": "integer",
      "title": "Total Entries"
    },
    "total_points": {
      "type": "integer",
      "title": "Total Points"
    },
    "omitted_without_coordinates": {
      "type": "integer",
      "title": "Omitted Without Coordinates"
    }
  },
  "type": "object",
  "required": [
    "points",
    "total_entries",
    "total_points",
    "omitted_without_coordinates"
  ],
  "title": "VocabularyMapItemsResponse"
}
```

</details>

<a id="schema-vocabularymappointresponse"></a>

### `VocabularyMapPointResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `location_name` | 是 | string |  |  |
| `province` | 否 | string | default="" |  |
| `city` | 否 | string | default="" |  |
| `county` | 否 | string | default="" |  |
| `town` | 否 | string | default="" |  |
| `administrative_village` | 否 | string | default="" |  |
| `natural_village` | 否 | string | default="" |  |
| `yindian_region` | 否 | string | default="" |  |
| `atlas_region` | 否 | string | default="" |  |
| `vocabulary_source` | 否 | string | default="" |  |
| `description` | 否 | string | default="" |  |
| `other` | 否 | string | default="" |  |
| `longitude` | 是 | number |  |  |
| `latitude` | 是 | number |  |  |
| `entry_count` | 是 | integer |  |  |
| `t1` | 否 | string | default="" |  |
| `t2` | 否 | string | default="" |  |
| `t3` | 否 | string | default="" |  |
| `t4` | 否 | string | default="" |  |
| `t5` | 否 | string | default="" |  |
| `t6` | 否 | string | default="" |  |
| `t7` | 否 | string | default="" |  |
| `t8` | 否 | string | default="" |  |
| `t9` | 否 | string | default="" |  |
| `t10` | 否 | string | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "province": {
      "type": "string",
      "title": "Province",
      "default": ""
    },
    "city": {
      "type": "string",
      "title": "City",
      "default": ""
    },
    "county": {
      "type": "string",
      "title": "County",
      "default": ""
    },
    "town": {
      "type": "string",
      "title": "Town",
      "default": ""
    },
    "administrative_village": {
      "type": "string",
      "title": "Administrative Village",
      "default": ""
    },
    "natural_village": {
      "type": "string",
      "title": "Natural Village",
      "default": ""
    },
    "yindian_region": {
      "type": "string",
      "title": "Yindian Region",
      "default": ""
    },
    "atlas_region": {
      "type": "string",
      "title": "Atlas Region",
      "default": ""
    },
    "vocabulary_source": {
      "type": "string",
      "title": "Vocabulary Source",
      "default": ""
    },
    "description": {
      "type": "string",
      "title": "Description",
      "default": ""
    },
    "other": {
      "type": "string",
      "title": "Other",
      "default": ""
    },
    "longitude": {
      "type": "number",
      "title": "Longitude"
    },
    "latitude": {
      "type": "number",
      "title": "Latitude"
    },
    "entry_count": {
      "type": "integer",
      "title": "Entry Count"
    },
    "t1": {
      "type": "string",
      "title": "T1",
      "default": ""
    },
    "t2": {
      "type": "string",
      "title": "T2",
      "default": ""
    },
    "t3": {
      "type": "string",
      "title": "T3",
      "default": ""
    },
    "t4": {
      "type": "string",
      "title": "T4",
      "default": ""
    },
    "t5": {
      "type": "string",
      "title": "T5",
      "default": ""
    },
    "t6": {
      "type": "string",
      "title": "T6",
      "default": ""
    },
    "t7": {
      "type": "string",
      "title": "T7",
      "default": ""
    },
    "t8": {
      "type": "string",
      "title": "T8",
      "default": ""
    },
    "t9": {
      "type": "string",
      "title": "T9",
      "default": ""
    },
    "t10": {
      "type": "string",
      "title": "T10",
      "default": ""
    }
  },
  "type": "object",
  "required": [
    "location_name",
    "longitude",
    "latitude",
    "entry_count"
  ],
  "title": "VocabularyMapPointResponse"
}
```

</details>

<a id="schema-vocabularymappointsresponse"></a>

### `VocabularyMapPointsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `points` | 是 | array&lt;[VocabularyMapPointResponse](#schema-vocabularymappointresponse)&gt; |  |  |
| `total_entries` | 是 | integer |  |  |
| `total_points` | 是 | integer |  |  |
| `omitted_without_coordinates` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "points": {
      "items": {
        "$ref": "#/components/schemas/VocabularyMapPointResponse"
      },
      "type": "array",
      "title": "Points"
    },
    "total_entries": {
      "type": "integer",
      "title": "Total Entries"
    },
    "total_points": {
      "type": "integer",
      "title": "Total Points"
    },
    "omitted_without_coordinates": {
      "type": "integer",
      "title": "Omitted Without Coordinates"
    }
  },
  "type": "object",
  "required": [
    "points",
    "total_entries",
    "total_points",
    "omitted_without_coordinates"
  ],
  "title": "VocabularyMapPointsResponse"
}
```

</details>

<a id="schema-vocabularymeresponse"></a>

### `VocabularyMeResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `permission_level` | 是 | string / null |  |  |
| `can_upload` | 是 | boolean |  |  |
| `can_manage_entries` | 是 | boolean |  |  |
| `can_view_logs` | 是 | boolean |  |  |
| `can_delete_locations` | 是 | boolean |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "permission_level": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Permission Level"
    },
    "can_upload": {
      "type": "boolean",
      "title": "Can Upload"
    },
    "can_manage_entries": {
      "type": "boolean",
      "title": "Can Manage Entries"
    },
    "can_view_logs": {
      "type": "boolean",
      "title": "Can View Logs"
    },
    "can_delete_locations": {
      "type": "boolean",
      "title": "Can Delete Locations"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "permission_level",
    "can_upload",
    "can_manage_entries",
    "can_view_logs",
    "can_delete_locations"
  ],
  "title": "VocabularyMeResponse"
}
```

</details>

<a id="schema-vocabularypermissionresponse"></a>

### `VocabularyPermissionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | 是 | integer |  |  |
| `permission_level` | 是 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "user_id": {
      "type": "integer",
      "title": "User Id"
    },
    "permission_level": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Permission Level"
    }
  },
  "type": "object",
  "required": [
    "user_id",
    "permission_level"
  ],
  "title": "VocabularyPermissionResponse"
}
```

</details>

<a id="schema-vocabularypermissionupdaterequest"></a>

### `VocabularyPermissionUpdateRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `permission_level` | 是 | string | enum=["none", "edit", "manage", "one", "two", "three"] |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "permission_level": {
      "type": "string",
      "enum": [
        "none",
        "edit",
        "manage",
        "one",
        "two",
        "three"
      ],
      "title": "Permission Level"
    }
  },
  "type": "object",
  "required": [
    "permission_level"
  ],
  "title": "VocabularyPermissionUpdateRequest"
}
```

</details>

<a id="schema-vocabularypermissionsresponse"></a>

### `VocabularyPermissionsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `permissions` | 是 | array&lt;[VocabularyPermissionResponse](#schema-vocabularypermissionresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "permissions": {
      "items": {
        "$ref": "#/components/schemas/VocabularyPermissionResponse"
      },
      "type": "array",
      "title": "Permissions"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "permissions",
    "total",
    "page",
    "page_size"
  ],
  "title": "VocabularyPermissionsResponse"
}
```

</details>

<a id="schema-vocabularystandardwordresponse"></a>

### `VocabularyStandardWordResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `key` | 是 | string |  |  |
| `standard_word` | 是 | string |  |  |
| `variants` | 是 | array&lt;string&gt; |  |  |
| `entry_count` | 是 | integer |  |  |
| `location_count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "key": {
      "type": "string",
      "title": "Key"
    },
    "standard_word": {
      "type": "string",
      "title": "Standard Word"
    },
    "variants": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Variants"
    },
    "entry_count": {
      "type": "integer",
      "title": "Entry Count"
    },
    "location_count": {
      "type": "integer",
      "title": "Location Count"
    }
  },
  "type": "object",
  "required": [
    "key",
    "standard_word",
    "variants",
    "entry_count",
    "location_count"
  ],
  "title": "VocabularyStandardWordResponse"
}
```

</details>

<a id="schema-vocabularystandardwordsresponse"></a>

### `VocabularyStandardWordsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `standard_words` | 是 | array&lt;[VocabularyStandardWordResponse](#schema-vocabularystandardwordresponse)&gt; |  |  |
| `total` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "standard_words": {
      "items": {
        "$ref": "#/components/schemas/VocabularyStandardWordResponse"
      },
      "type": "array",
      "title": "Standard Words"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    }
  },
  "type": "object",
  "required": [
    "standard_words",
    "total"
  ],
  "title": "VocabularyStandardWordsResponse"
}
```

</details>

<a id="schema-vocabularyuploadpreviewresponse"></a>

### `VocabularyUploadPreviewResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 是 | boolean |  | 是否存在可导入的行 |
| `location_name` | 是 | string |  |  |
| `permission_level` | 是 | string |  |  |
| `parsed_count` | 是 | integer |  | 可成功解析、将被导入的行数 |
| `would_delete_existing_count` | 是 | integer |  |  |
| `skipped_count` | 是 | integer |  | 空行数（标准词、方言词、音标均为空），未导入 |
| `errors` | 是 | array&lt;string&gt; |  | 错误行明细（行号 + 原因），这些行在导入时会被跳过 |
| `parser_mode` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success",
      "description": "是否存在可导入的行"
    },
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "permission_level": {
      "type": "string",
      "title": "Permission Level"
    },
    "parsed_count": {
      "type": "integer",
      "title": "Parsed Count",
      "description": "可成功解析、将被导入的行数"
    },
    "would_delete_existing_count": {
      "type": "integer",
      "title": "Would Delete Existing Count"
    },
    "skipped_count": {
      "type": "integer",
      "title": "Skipped Count",
      "description": "空行数（标准词、方言词、音标均为空），未导入"
    },
    "errors": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Errors",
      "description": "错误行明细（行号 + 原因），这些行在导入时会被跳过"
    },
    "parser_mode": {
      "type": "string",
      "title": "Parser Mode"
    }
  },
  "type": "object",
  "required": [
    "success",
    "location_name",
    "permission_level",
    "parsed_count",
    "would_delete_existing_count",
    "skipped_count",
    "errors",
    "parser_mode"
  ],
  "title": "VocabularyUploadPreviewResponse"
}
```

</details>

<a id="schema-vocabularyuploadresponse"></a>

### `VocabularyUploadResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | 是 | boolean |  |  |
| `location_id` | 是 | integer |  |  |
| `location_name` | 是 | string |  |  |
| `permission_level` | 是 | string |  |  |
| `imported_count` | 是 | integer |  |  |
| `deleted_existing_count` | 是 | integer |  |  |
| `skipped_count` | 是 | integer |  | 空行数（标准词、方言词、音标均为空），未导入 |
| `errors` | 是 | array&lt;string&gt; |  | 错误行明细（行号 + 原因），这些行已被跳过、未导入 |
| `parser_mode` | 是 | string |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "success": {
      "type": "boolean",
      "title": "Success"
    },
    "location_id": {
      "type": "integer",
      "title": "Location Id"
    },
    "location_name": {
      "type": "string",
      "title": "Location Name"
    },
    "permission_level": {
      "type": "string",
      "title": "Permission Level"
    },
    "imported_count": {
      "type": "integer",
      "title": "Imported Count"
    },
    "deleted_existing_count": {
      "type": "integer",
      "title": "Deleted Existing Count"
    },
    "skipped_count": {
      "type": "integer",
      "title": "Skipped Count",
      "description": "空行数（标准词、方言词、音标均为空），未导入"
    },
    "errors": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Errors",
      "description": "错误行明细（行号 + 原因），这些行已被跳过、未导入"
    },
    "parser_mode": {
      "type": "string",
      "title": "Parser Mode"
    }
  },
  "type": "object",
  "required": [
    "success",
    "location_id",
    "location_name",
    "permission_level",
    "imported_count",
    "deleted_existing_count",
    "skipped_count",
    "errors",
    "parser_mode"
  ],
  "title": "VocabularyUploadResponse"
}
```

</details>

<a id="schema-voicequalityoptions"></a>

### `VoiceQualityOptions`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `f0_min` | 否 | number | default=75.0 |  |
| `f0_max` | 否 | number | default=600.0 |  |
| `min_voiced_frames` | 否 | integer | default=10 |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "f0_min": {
      "type": "number",
      "title": "F0 Min",
      "default": 75.0
    },
    "f0_max": {
      "type": "number",
      "title": "F0 Max",
      "default": 600.0
    },
    "min_voiced_frames": {
      "type": "integer",
      "title": "Min Voiced Frames",
      "default": 10
    }
  },
  "type": "object",
  "title": "VoiceQualityOptions",
  "description": "Voice quality analysis options."
}
```

</details>

<a id="schema-yinweianalysis"></a>

### `YinWeiAnalysis`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `locations` | 否 | array&lt;string&gt; |  |  |
| `regions` | 否 | array&lt;string&gt; |  |  |
| `features` | 否 | array&lt;string&gt; |  |  |
| `group_inputs` | 否 | array&lt;string&gt; / null |  |  |
| `pho_values` | 否 | string / array&lt;string&gt; / null |  |  |
| `region_mode` | 否 | string | default="yindian" |  |
| `exclude_columns` | 否 | array&lt;string&gt; / null |  | 要排除的列名列表，如 ['多地位標記', '多等'] |
| `table_name` | 否 | string | default="characters" | 字符數據庫表名 |
| `include_custom` | 否 | boolean | default=false | 是否附帶查詢當前用戶的自定義數據（需登錄，匿名用戶返回空數組） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations"
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions"
    },
    "features": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Features"
    },
    "group_inputs": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Group Inputs"
    },
    "pho_values": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Pho Values"
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "default": "yindian"
    },
    "exclude_columns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Columns",
      "description": "要排除的列名列表，如 ['多地位標記', '多等']"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "字符數據庫表名",
      "default": "characters"
    },
    "include_custom": {
      "type": "boolean",
      "title": "Include Custom",
      "description": "是否附帶查詢當前用戶的自定義數據（需登錄，匿名用戶返回空數組）",
      "default": false
    }
  },
  "type": "object",
  "title": "YinWeiAnalysis"
}
```

</details>

<a id="schema-yubaogrammaritem"></a>

### `YubaoGrammarItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `iid` | 否 | integer / null |  |  |
| `city_code` | 否 | string / null |  |  |
| `city_name` | 否 | string / null |  |  |
| `form_a` | 否 | string / null |  |  |
| `form_b` | 否 | string / null |  |  |
| `form_c` | 否 | string / null |  |  |
| `form_d` | 否 | string / null |  |  |
| `form_e` | 否 | string / null |  |  |
| `longitude` | 否 | number / null |  |  |
| `latitude` | 否 | number / null |  |  |
| `phonetic` | 否 | string / null |  |  |
| `sentence` | 否 | string / null |  |  |
| `memo` | 否 | string / null |  |  |
| `lang_cat1` | 否 | string / null |  |  |
| `lang_cat2` | 否 | string / null |  |  |
| `lang_cat3` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "iid": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Iid"
    },
    "city_code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City Code"
    },
    "city_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City Name"
    },
    "form_a": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Form A"
    },
    "form_b": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Form B"
    },
    "form_c": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Form C"
    },
    "form_d": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Form D"
    },
    "form_e": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Form E"
    },
    "longitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Longitude"
    },
    "latitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Latitude"
    },
    "phonetic": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Phonetic"
    },
    "sentence": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Sentence"
    },
    "memo": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Memo"
    },
    "lang_cat1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lang Cat1"
    },
    "lang_cat2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lang Cat2"
    },
    "lang_cat3": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lang Cat3"
    }
  },
  "type": "object",
  "required": [
    "id"
  ],
  "title": "YubaoGrammarItem"
}
```

</details>

<a id="schema-yubaogrammaritemsresponse"></a>

### `YubaoGrammarItemsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[YubaoGrammarItem](#schema-yubaogrammaritem)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/YubaoGrammarItem"
      },
      "type": "array",
      "title": "Items"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "items",
    "total",
    "page",
    "page_size"
  ],
  "title": "YubaoGrammarItemsResponse"
}
```

</details>

<a id="schema-yubaosuggestionresponse"></a>

### `YubaoSuggestionResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;string&gt; |  |  |
| `total` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Items"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    }
  },
  "type": "object",
  "required": [
    "items",
    "total"
  ],
  "title": "YubaoSuggestionResponse"
}
```

</details>

<a id="schema-yubaovocabularyitem"></a>

### `YubaoVocabularyItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 是 | integer |  |  |
| `no` | 否 | integer / number / string / null |  |  |
| `province` | 否 | string / null |  |  |
| `city` | 否 | string / null |  |  |
| `county` | 否 | string / null |  |  |
| `village` | 否 | string / null |  |  |
| `location` | 否 | string / null |  |  |
| `longitude` | 否 | number / null |  |  |
| `latitude` | 否 | number / null |  |  |
| `word` | 否 | string / null |  |  |
| `pronunciation` | 否 | string / null |  |  |
| `note1` | 否 | string / null |  |  |
| `note2` | 否 | string / null |  |  |
| `lang_cat1` | 否 | string / null |  |  |
| `lang_cat2` | 否 | string / null |  |  |
| `lang_cat3` | 否 | string / null |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "no": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "number"
        },
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "No"
    },
    "province": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Province"
    },
    "city": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "City"
    },
    "county": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "County"
    },
    "village": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Village"
    },
    "location": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Location"
    },
    "longitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Longitude"
    },
    "latitude": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Latitude"
    },
    "word": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Word"
    },
    "pronunciation": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Pronunciation"
    },
    "note1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Note1"
    },
    "note2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Note2"
    },
    "lang_cat1": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lang Cat1"
    },
    "lang_cat2": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lang Cat2"
    },
    "lang_cat3": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Lang Cat3"
    }
  },
  "type": "object",
  "required": [
    "id"
  ],
  "title": "YubaoVocabularyItem"
}
```

</details>

<a id="schema-yubaovocabularyitemsresponse"></a>

### `YubaoVocabularyItemsResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | 是 | array&lt;[YubaoVocabularyItem](#schema-yubaovocabularyitem)&gt; |  |  |
| `total` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "items": {
      "items": {
        "$ref": "#/components/schemas/YubaoVocabularyItem"
      },
      "type": "array",
      "title": "Items"
    },
    "total": {
      "type": "integer",
      "title": "Total"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    }
  },
  "type": "object",
  "required": [
    "items",
    "total",
    "page",
    "page_size"
  ],
  "title": "YubaoVocabularyItemsResponse"
}
```

</details>

<a id="schema-zhongguanalysis"></a>

### `ZhongGuAnalysis`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path_strings` | 否 | array&lt;string&gt; / null |  | 語音條件列表，例如 ['知組', '蟹攝'] 或 ['[知]{組}'] |
| `chars` | 否 | array&lt;string&gt; / null |  | 可直接輸入的漢字集合；每個元素若為多字串會自動拆字，例如 ['笨蛋'] -> ['笨', '蛋'] |
| `column` | 否 | array&lt;string&gt; / null |  | 需要進行排列組合的額外欄位，例如 ['等'] |
| `combine_query` | 否 | boolean | default=false | 是否開啟 path_strings 與 column 的交叉組合查詢 |
| `exclude_columns` | 否 | array&lt;string&gt; / null |  | 要排除的列名列表，如 ['多地位標記', '多等'] |
| `locations` | 否 | array&lt;string&gt; |  | 目標地點列表，例如 ['北京', '上海'] |
| `regions` | 否 | array&lt;string&gt; |  | 目標區域列表（用於輔助查找地點），可留空 |
| `features` | 否 | array&lt;string&gt; | default=["韻母"] | 需要分析的語音特徵 |
| `region_mode` | 否 | string | default="yindian" | 地區匹配模式 |
| `include_custom` | 否 | boolean | default=false | 是否附帶查詢當前用戶的自定義數據（需登錄，匿名用戶返回空數組） |
| `table_name` | 否 | string | default="characters" | 字符數據庫表名 |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path_strings": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Path Strings",
      "description": "語音條件列表，例如 ['知組', '蟹攝'] 或 ['[知]{組}']",
      "example": [
        "[知]{組}",
        "[莊]{組}"
      ]
    },
    "chars": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Chars",
      "description": "可直接輸入的漢字集合；每個元素若為多字串會自動拆字，例如 ['笨蛋'] -> ['笨', '蛋']",
      "example": [
        "笨",
        "蛋"
      ]
    },
    "column": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Column",
      "description": "需要進行排列組合的額外欄位，例如 ['等']",
      "example": []
    },
    "combine_query": {
      "type": "boolean",
      "title": "Combine Query",
      "description": "是否開啟 path_strings 與 column 的交叉組合查詢",
      "default": false
    },
    "exclude_columns": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Exclude Columns",
      "description": "要排除的列名列表，如 ['多地位標記', '多等']"
    },
    "locations": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Locations",
      "description": "目標地點列表，例如 ['北京', '上海']",
      "example": [
        "北京",
        "广州"
      ]
    },
    "regions": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Regions",
      "description": "目標區域列表（用於輔助查找地點），可留空",
      "example": []
    },
    "features": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Features",
      "description": "需要分析的語音特徵",
      "default": [
        "韻母"
      ],
      "example": [
        "聲母",
        "韻母"
      ]
    },
    "region_mode": {
      "type": "string",
      "title": "Region Mode",
      "description": "地區匹配模式",
      "default": "yindian"
    },
    "include_custom": {
      "type": "boolean",
      "title": "Include Custom",
      "description": "是否附帶查詢當前用戶的自定義數據（需登錄，匿名用戶返回空數組）",
      "default": false
    },
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "description": "字符數據庫表名",
      "default": "characters"
    }
  },
  "type": "object",
  "title": "ZhongGuAnalysis"
}
```

</details>

<a id="schema-app__schemas__admin__analytics__geodistributionitem"></a>

### `app__schemas__admin__analytics__GeoDistributionItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `location` | 是 | string |  |  |
| `user_count` | 是 | integer |  |  |
| `call_count` | 是 | integer |  |  |
| `percentage` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "location": {
      "type": "string",
      "title": "Location"
    },
    "user_count": {
      "type": "integer",
      "title": "User Count"
    },
    "call_count": {
      "type": "integer",
      "title": "Call Count"
    },
    "percentage": {
      "type": "number",
      "title": "Percentage"
    }
  },
  "type": "object",
  "required": [
    "location",
    "user_count",
    "call_count",
    "percentage"
  ],
  "title": "GeoDistributionItem"
}
```

</details>

<a id="schema-app__schemas__admin__analytics__leaderboardresponse"></a>

### `app__schemas__admin__analytics__LeaderboardResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `ranking_type` | 是 | string |  |  |
| `metric` | 是 | string / null |  |  |
| `api_path` | 是 | string / null |  |  |
| `total_count` | 是 | integer |  |  |
| `page` | 是 | integer |  |  |
| `page_size` | 是 | integer |  |  |
| `total_pages` | 是 | integer |  |  |
| `rankings` | 是 | array&lt;未声明结构&gt; |  |  |
| `total_value` | 否 | number / null |  | 所有排名项目的累计总量（不受分页限制） |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "ranking_type": {
      "type": "string",
      "title": "Ranking Type"
    },
    "metric": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Metric"
    },
    "api_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Api Path"
    },
    "total_count": {
      "type": "integer",
      "title": "Total Count"
    },
    "page": {
      "type": "integer",
      "title": "Page"
    },
    "page_size": {
      "type": "integer",
      "title": "Page Size"
    },
    "total_pages": {
      "type": "integer",
      "title": "Total Pages"
    },
    "rankings": {
      "items": {},
      "type": "array",
      "title": "Rankings"
    },
    "total_value": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Total Value",
      "description": "所有排名项目的累计总量（不受分页限制）"
    }
  },
  "type": "object",
  "required": [
    "ranking_type",
    "metric",
    "api_path",
    "total_count",
    "page",
    "page_size",
    "total_pages",
    "rankings"
  ],
  "title": "LeaderboardResponse",
  "description": "排行榜响应"
}
```

</details>

<a id="schema-app__schemas__admin__analytics__topapiitem__1"></a>

### `app__schemas__admin__analytics__TopAPIItem__1`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | 是 | string |  |  |
| `calls` | 是 | integer |  |  |
| `percentage` | 是 | number |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path": {
      "type": "string",
      "title": "Path"
    },
    "calls": {
      "type": "integer",
      "title": "Calls"
    },
    "percentage": {
      "type": "number",
      "title": "Percentage"
    }
  },
  "type": "object",
  "required": [
    "path",
    "calls",
    "percentage"
  ],
  "title": "TopAPIItem"
}
```

</details>

<a id="schema-app__schemas__admin__analytics__topapiitem__2"></a>

### `app__schemas__admin__analytics__TopAPIItem__2`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | 是 | string |  |  |
| `calls` | 是 | integer |  |  |
| `users` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "path": {
      "type": "string",
      "title": "Path"
    },
    "calls": {
      "type": "integer",
      "title": "Calls"
    },
    "users": {
      "type": "integer",
      "title": "Users"
    }
  },
  "type": "object",
  "required": [
    "path",
    "calls",
    "users"
  ],
  "title": "TopAPIItem"
}
```

</details>

<a id="schema-app__schemas__auth__session__geodistributionitem"></a>

### `app__schemas__auth__session__GeoDistributionItem`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `country` | 是 | string |  |  |
| `count` | 是 | integer |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "country": {
      "type": "string",
      "title": "Country"
    },
    "count": {
      "type": "integer",
      "title": "Count"
    }
  },
  "type": "object",
  "required": [
    "country",
    "count"
  ],
  "title": "GeoDistributionItem"
}
```

</details>

<a id="schema-app__schemas__auth__user__leaderboardresponse"></a>

### `app__schemas__auth__user__LeaderboardResponse`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `rankings` | 是 | object&lt;[RankingDetail](#schema-rankingdetail)&gt; |  | Dictionary of all rankings (online_time, total_queries, categories, grouped aggregates, endpoints) |
| `total_users` | 是 | integer |  | Total number of active users |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "rankings": {
      "additionalProperties": {
        "$ref": "#/components/schemas/RankingDetail"
      },
      "type": "object",
      "title": "Rankings",
      "description": "Dictionary of all rankings (online_time, total_queries, categories, grouped aggregates, endpoints)"
    },
    "total_users": {
      "type": "integer",
      "title": "Total Users",
      "description": "Total number of active users"
    }
  },
  "type": "object",
  "required": [
    "rankings",
    "total_users"
  ],
  "title": "LeaderboardResponse",
  "description": "Complete leaderboard response with category, grouped, and endpoint rankings."
}
```

</details>

<a id="schema-app__schemas__user__submissions__batchdeleterequest"></a>

### `app__schemas__user__submissions__BatchDeleteRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `created_at_list` | 是 | array&lt;string (date-time)&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "created_at_list": {
      "items": {
        "type": "string",
        "format": "date-time"
      },
      "type": "array",
      "title": "Created At List"
    }
  },
  "type": "object",
  "required": [
    "created_at_list"
  ],
  "title": "BatchDeleteRequest",
  "description": "批量刪除請求"
}
```

</details>

<a id="schema-app__schemas__vocabulary_sql__batchmutationparams"></a>

### `app__schemas__vocabulary_sql__BatchMutationParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 否 | string | default="vocabulary_entries" |  |
| `action` | 是 | string | enum=["batch_create", "batch_update", "batch_delete"] |  |
| `pk_column` | 否 | string | default="id" |  |
| `create_data` | 否 | array&lt;object&gt; |  |  |
| `update_data` | 否 | array&lt;object&gt; |  |  |
| `delete_ids` | 否 | array&lt;未声明结构&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "vocabulary_entries"
    },
    "action": {
      "type": "string",
      "enum": [
        "batch_create",
        "batch_update",
        "batch_delete"
      ],
      "title": "Action"
    },
    "pk_column": {
      "type": "string",
      "title": "Pk Column",
      "default": "id"
    },
    "create_data": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Create Data"
    },
    "update_data": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Update Data"
    },
    "delete_ids": {
      "items": {},
      "type": "array",
      "title": "Delete Ids"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "action"
  ],
  "title": "BatchMutationParams"
}
```

</details>

<a id="schema-app__schemas__vocabulary_sql__batchreplaceexecuteparams"></a>

### `app__schemas__vocabulary_sql__BatchReplaceExecuteParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 否 | string | default="vocabulary_entries" |  |
| `columns` | 是 | array&lt;string&gt; |  |  |
| `find_text` | 否 | string | default="" |  |
| `match_mode` | 否 | string | default="contains"; enum=["exact", "contains"] |  |
| `is_empty_search` | 否 | boolean | default=false |  |
| `filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; |  |  |
| `search_text` | 否 | string / null | default="" |  |
| `search_columns` | 否 | array&lt;string&gt; |  |  |
| `replace_text` | 否 | string | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "vocabulary_entries"
    },
    "columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Columns"
    },
    "find_text": {
      "type": "string",
      "title": "Find Text",
      "default": ""
    },
    "match_mode": {
      "type": "string",
      "enum": [
        "exact",
        "contains"
      ],
      "title": "Match Mode",
      "default": "contains"
    },
    "is_empty_search": {
      "type": "boolean",
      "title": "Is Empty Search",
      "default": false
    },
    "filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Filters"
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text",
      "default": ""
    },
    "search_columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Search Columns"
    },
    "replace_text": {
      "type": "string",
      "title": "Replace Text",
      "default": ""
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "columns"
  ],
  "title": "BatchReplaceExecuteParams"
}
```

</details>

<a id="schema-app__schemas__vocabulary_sql__batchreplacepreviewparams"></a>

### `app__schemas__vocabulary_sql__BatchReplacePreviewParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 否 | string | default="vocabulary_entries" |  |
| `columns` | 是 | array&lt;string&gt; |  |  |
| `find_text` | 否 | string | default="" |  |
| `match_mode` | 否 | string | default="contains"; enum=["exact", "contains"] |  |
| `is_empty_search` | 否 | boolean | default=false |  |
| `filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; |  |  |
| `search_text` | 否 | string / null | default="" |  |
| `search_columns` | 否 | array&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "vocabulary_entries"
    },
    "columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Columns"
    },
    "find_text": {
      "type": "string",
      "title": "Find Text",
      "default": ""
    },
    "match_mode": {
      "type": "string",
      "enum": [
        "exact",
        "contains"
      ],
      "title": "Match Mode",
      "default": "contains"
    },
    "is_empty_search": {
      "type": "boolean",
      "title": "Is Empty Search",
      "default": false
    },
    "filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Filters"
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text",
      "default": ""
    },
    "search_columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Search Columns"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "columns"
  ],
  "title": "BatchReplacePreviewParams"
}
```

</details>

<a id="schema-app__schemas__vocabulary_sql__distinctqueryrequest"></a>

### `app__schemas__vocabulary_sql__DistinctQueryRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 否 | string | default="vocabulary_entries" |  |
| `target_column` | 是 | string |  |  |
| `current_filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; |  |  |
| `search_text` | 否 | string / null | default="" |  |
| `search_columns` | 否 | array&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "vocabulary_entries"
    },
    "target_column": {
      "type": "string",
      "title": "Target Column"
    },
    "current_filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Current Filters"
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text",
      "default": ""
    },
    "search_columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Search Columns"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "target_column"
  ],
  "title": "DistinctQueryRequest"
}
```

</details>

<a id="schema-app__schemas__vocabulary_sql__mutationparams"></a>

### `app__schemas__vocabulary_sql__MutationParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 否 | string | default="vocabulary_entries" |  |
| `action` | 是 | string | enum=["create", "update", "delete"] |  |
| `pk_column` | 否 | string | default="id" |  |
| `pk_value` | 否 | 未声明结构 |  |  |
| `data` | 否 | object |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "vocabulary_entries"
    },
    "action": {
      "type": "string",
      "enum": [
        "create",
        "update",
        "delete"
      ],
      "title": "Action"
    },
    "pk_column": {
      "type": "string",
      "title": "Pk Column",
      "default": "id"
    },
    "pk_value": {
      "title": "Pk Value"
    },
    "data": {
      "additionalProperties": true,
      "type": "object",
      "title": "Data"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "required": [
    "action"
  ],
  "title": "MutationParams"
}
```

</details>

<a id="schema-app__schemas__vocabulary_sql__queryparams"></a>

### `app__schemas__vocabulary_sql__QueryParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `table_name` | 否 | string | default="vocabulary_entries" |  |
| `page` | 否 | integer | default=1 |  |
| `page_size` | 否 | integer | default=20; maximum=5000.0 |  |
| `sort_by` | 否 | string / null |  |  |
| `sort_desc` | 否 | boolean | default=false |  |
| `filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; |  |  |
| `search_text` | 否 | string / null |  |  |
| `search_columns` | 否 | array&lt;string&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "table_name": {
      "type": "string",
      "title": "Table Name",
      "default": "vocabulary_entries"
    },
    "page": {
      "type": "integer",
      "title": "Page",
      "default": 1
    },
    "page_size": {
      "type": "integer",
      "maximum": 5000.0,
      "title": "Page Size",
      "default": 20
    },
    "sort_by": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Sort By"
    },
    "sort_desc": {
      "type": "boolean",
      "title": "Sort Desc",
      "default": false
    },
    "filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Filters"
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text"
    },
    "search_columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Search Columns"
    }
  },
  "additionalProperties": false,
  "type": "object",
  "title": "QueryParams"
}
```

</details>

<a id="schema-app__sql__sql_schemas__batchmutationparams"></a>

### `app__sql__sql_schemas__BatchMutationParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `action` | 是 | string |  |  |
| `pk_column` | 否 | string | default="rowid" |  |
| `create_data` | 否 | array&lt;object&gt; | default=[] |  |
| `update_data` | 否 | array&lt;object&gt; | default=[] |  |
| `delete_ids` | 否 | array&lt;未声明结构&gt; | default=[] |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "action": {
      "type": "string",
      "title": "Action"
    },
    "pk_column": {
      "type": "string",
      "title": "Pk Column",
      "default": "rowid"
    },
    "create_data": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Create Data",
      "default": []
    },
    "update_data": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "array",
      "title": "Update Data",
      "default": []
    },
    "delete_ids": {
      "items": {},
      "type": "array",
      "title": "Delete Ids",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "action"
  ],
  "title": "BatchMutationParams",
  "description": "批量操作参数"
}
```

</details>

<a id="schema-app__sql__sql_schemas__batchreplaceexecuteparams"></a>

### `app__sql__sql_schemas__BatchReplaceExecuteParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `pk_column` | 否 | string | default="rowid" |  |
| `columns` | 是 | array&lt;string&gt; |  |  |
| `find_text` | 是 | string |  |  |
| `replace_text` | 是 | string |  |  |
| `match_mode` | 是 | string |  |  |
| `is_empty_search` | 是 | boolean |  |  |
| `filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; | default={} |  |
| `search_text` | 否 | string / null | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "pk_column": {
      "type": "string",
      "title": "Pk Column",
      "default": "rowid"
    },
    "columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Columns"
    },
    "find_text": {
      "type": "string",
      "title": "Find Text"
    },
    "replace_text": {
      "type": "string",
      "title": "Replace Text"
    },
    "match_mode": {
      "type": "string",
      "title": "Match Mode"
    },
    "is_empty_search": {
      "type": "boolean",
      "title": "Is Empty Search"
    },
    "filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Filters",
      "default": {}
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text",
      "default": ""
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "columns",
    "find_text",
    "replace_text",
    "match_mode",
    "is_empty_search"
  ],
  "title": "BatchReplaceExecuteParams",
  "description": "批量替换执行参数"
}
```

</details>

<a id="schema-app__sql__sql_schemas__batchreplacepreviewparams"></a>

### `app__sql__sql_schemas__BatchReplacePreviewParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `columns` | 是 | array&lt;string&gt; |  |  |
| `find_text` | 是 | string |  |  |
| `match_mode` | 是 | string |  |  |
| `is_empty_search` | 是 | boolean |  |  |
| `filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; | default={} |  |
| `search_text` | 否 | string / null | default="" |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Columns"
    },
    "find_text": {
      "type": "string",
      "title": "Find Text"
    },
    "match_mode": {
      "type": "string",
      "title": "Match Mode"
    },
    "is_empty_search": {
      "type": "boolean",
      "title": "Is Empty Search"
    },
    "filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Filters",
      "default": {}
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text",
      "default": ""
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "columns",
    "find_text",
    "match_mode",
    "is_empty_search"
  ],
  "title": "BatchReplacePreviewParams",
  "description": "批量替换预览参数"
}
```

</details>

<a id="schema-app__sql__sql_schemas__distinctqueryrequest"></a>

### `app__sql__sql_schemas__DistinctQueryRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `target_column` | 是 | string |  |  |
| `current_filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; | default={} |  |
| `search_text` | 否 | string / null | default="" |  |
| `search_columns` | 否 | array&lt;string&gt; | default=[] |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "target_column": {
      "type": "string",
      "title": "Target Column"
    },
    "current_filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Current Filters",
      "default": {}
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text",
      "default": ""
    },
    "search_columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Search Columns",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "target_column"
  ],
  "title": "DistinctQueryRequest"
}
```

</details>

<a id="schema-app__sql__sql_schemas__mutationparams"></a>

### `app__sql__sql_schemas__MutationParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `action` | 是 | string |  |  |
| `pk_column` | 否 | string | default="rowid" |  |
| `pk_value` | 否 | 未声明结构 |  |  |
| `data` | 否 | object | default={} |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "action": {
      "type": "string",
      "title": "Action"
    },
    "pk_column": {
      "type": "string",
      "title": "Pk Column",
      "default": "rowid"
    },
    "pk_value": {
      "title": "Pk Value"
    },
    "data": {
      "additionalProperties": true,
      "type": "object",
      "title": "Data",
      "default": {}
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name",
    "action"
  ],
  "title": "MutationParams"
}
```

</details>

<a id="schema-app__sql__sql_schemas__queryparams"></a>

### `app__sql__sql_schemas__QueryParams`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `db_key` | 是 | string |  |  |
| `table_name` | 是 | string |  |  |
| `page` | 否 | integer | default=1 |  |
| `page_size` | 否 | integer | default=20; maximum=5000.0 | 每页数量 |
| `sort_by` | 否 | string / null |  |  |
| `sort_desc` | 否 | boolean | default=false |  |
| `filters` | 否 | object&lt;array&lt;未声明结构&gt;&gt; | default={} |  |
| `search_text` | 否 | string / null |  |  |
| `search_columns` | 否 | array&lt;string&gt; | default=[] |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "db_key": {
      "type": "string",
      "title": "Db Key"
    },
    "table_name": {
      "type": "string",
      "title": "Table Name"
    },
    "page": {
      "type": "integer",
      "title": "Page",
      "default": 1
    },
    "page_size": {
      "type": "integer",
      "maximum": 5000.0,
      "title": "Page Size",
      "description": "每页数量",
      "default": 20
    },
    "sort_by": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Sort By"
    },
    "sort_desc": {
      "type": "boolean",
      "title": "Sort Desc",
      "default": false
    },
    "filters": {
      "additionalProperties": {
        "items": {},
        "type": "array"
      },
      "type": "object",
      "title": "Filters",
      "default": {}
    },
    "search_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Search Text"
    },
    "search_columns": {
      "items": {
        "type": "string"
      },
      "type": "array",
      "title": "Search Columns",
      "default": []
    }
  },
  "type": "object",
  "required": [
    "db_key",
    "table_name"
  ],
  "title": "QueryParams"
}
```

</details>

<a id="schema-app__tools__check__check_routes__batchdeleterequest"></a>

### `app__tools__check__check_routes__BatchDeleteRequest`

| 字段 | 必填 | 类型 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_id` | 是 | string |  |  |
| `rows` | 是 | array&lt;integer&gt; |  |  |

<details>
<summary>完整 JSON Schema</summary>

```json
{
  "properties": {
    "task_id": {
      "type": "string",
      "title": "Task Id"
    },
    "rows": {
      "items": {
        "type": "integer"
      },
      "type": "array",
      "title": "Rows"
    }
  },
  "type": "object",
  "required": [
    "task_id",
    "rows"
  ],
  "title": "BatchDeleteRequest",
  "description": "批量删除请求"
}
```

</details>
