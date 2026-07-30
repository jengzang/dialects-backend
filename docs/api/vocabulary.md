# Vocabulary API Reference

本文档总结当前已经实现的 `/api/vocabulary/*` 接口、请求体、响应体、权限边界，以及最初需求的完成度。

当前 vocabulary 功能使用独立数据库 `data/vocabulary.db`。所有项目登录态沿用现有 JWT 逻辑：需要登录的接口都通过项目统一的 `get_current_user` 或 `get_current_admin_user` 依赖获取用户，不从请求体接收用户信息。

## 当前实现概览

已实现功能：

- 创建并迁移 `data/vocabulary.db`。
- 创建四张表：`vocabulary_entries`、`vocabulary_locations`、`vocabulary_permissions`、`vocabulary_logs`。
- 上传前预览接口和正式导入接口。
- 支持 `.xlsx`、`.xls`、`.csv`、`.tsv` 表格文件。
- 支持 `.docx`、`.doc` 文档文件的两种解析模式：空白分隔和括号识别。
- 上传时自动填入当前 JWT 用户的 `user_id`。
- 上传时按 `(user_id, location_name)` 删除旧 entries 后重新插入新 entries。
- `edit`、`manage` 两级 vocabulary 权限。
- 项目 `admin` 用户始终被视为 vocabulary `manage`，不需要额外权限行。
- 公共搜索展示接口：entries 列表、地图点、地点选项。
- 用户自己的 vocabulary 权限上下文接口 `/api/vocabulary/me`。
- 地点元数据读取和编辑接口。
- manage/admin 可查看操作日志。
- 项目 admin 可管理 `vocabulary_permissions`。
- 表格编辑用 `/api/vocabulary/sql/*` 接口，固定访问 `vocabulary.db`，且只开放 `vocabulary_entries`。
- 删除了旧兼容路径：`/api/vocabulary/items`、`/api/vocabulary/map-points`、`/api/vocabulary/location-options`、`/api/vocabulary/upload`、`/api/vocabulary/upload/preview`、`/api/vocabulary/me/permission`。

## 权限模型

Vocabulary 权限只有两级：

| permission_level | 含义 |
| --- | --- |
| `edit` | 可以上传词表，可以读取和编辑自己的 `vocabulary_entries`，可以读取和编辑自己的 `vocabulary_locations`。 |
| `manage` | 可以上传词表，可以管理整张 `vocabulary_entries`，可以读取和编辑所有 `vocabulary_locations`，可以查看 logs。 |

项目 `admin` 用户的有效 vocabulary 权限恒等于 `manage`。这意味着 admin 即使没有 `vocabulary_permissions` 行，也不会被 vocabulary 权限拦截。

重要边界：

- 未登录用户只能使用公开搜索展示接口。
- 已登录但没有 vocabulary 权限行的普通用户不能上传、不能编辑、不能读取 locations、不能读取 logs、不能使用 vocabulary SQL。
- `edit` 用户只能管理自己的数据，服务端自动加 `user_id = current_user.id` 限制。
- `manage` 和项目 `admin` 可以管理所有 `vocabulary_entries` 和 `vocabulary_locations`。
- `/api/vocabulary/admin/permissions*` 是项目 admin 专用接口，不是 vocabulary `manage` 专用接口。

## 数据库结构

### `vocabulary_entries`

真实词表数据表。

| 字段 | 类型 | DB NOT NULL | 说明 |
| --- | --- | --- | --- |
| `id` | integer | 是，主键 | 自增主键。 |
| `user_id` | integer | 是 | 上传者用户 id，来自 JWT。 |
| `location_name` | string | 是 | 地点简称，来自上传时的 location JSON。 |
| `standard_word` | string | 是 | 书面词条或释义。最初讨论里的 `written` 已改为这个名字。 |
| `local_expression` | text | 是 | 当地讲法。 |
| `ipa` | text | 是 | IPA。 |
| `notes` | text | 否 | 注释，应用层默认写空字符串。 |
| `informations` | text | 否 | 预留字段，当前上传时写空字符串。 |
| `source_filename` | string | 否 | 原始上传文件名。 |

索引：

- `user_id`
- `location_name`
- `standard_word`
- `(user_id, location_name)`

### `vocabulary_locations`

地点元数据表。每个用户的每个地点简称最多一条。

| 字段 | 类型 | DB NOT NULL | 说明 |
| --- | --- | --- | --- |
| `id` | integer | 是，主键 | 内部主键，当前 API 不对前端暴露。 |
| `user_id` | integer | 是 | 上传者用户 id。 |
| `location_name` | string | 是 | 地点简称，不允许通过 PATCH 改名。 |
| `coordinates` | string | 是 | 经纬度字符串，当前仅要求非空；地图接口按 `longitude,latitude` 解析。 |
| `province` | string | 否 | 省。 |
| `city` | string | 否 | 市。 |
| `county` | string | 否 | 县或区县。 |
| `town` | string | 否 | 镇或乡镇。 |
| `administrative_village` | string | 否 | 行政村。 |
| `natural_village` | string | 否 | 自然村。 |
| `yindian_region` | string | 否 | 音典分区。 |
| `atlas_region` | string | 否 | 地图集/方音图鉴分区。 |

约束和索引：

- 唯一约束：`(user_id, location_name)`。
- 索引：`user_id`、`location_name`、`(user_id, location_name)`。
- 已删除旧字段 `raw_location_json`。

### `vocabulary_permissions`

Vocabulary 权限表。

| 字段 | 类型 | DB NOT NULL | 说明 |
| --- | --- | --- | --- |
| `id` | integer | 是，主键 | 内部主键。 |
| `user_id` | integer | 是 | 用户 id，唯一。 |
| `permission_level` | string | 是 | 只能是 `edit` 或 `manage`。 |

索引：

- `user_id`，且唯一。

### `vocabulary_logs`

操作级日志表。不是逐行日志，一次用户操作通常只写一条日志。

| 字段 | 类型 | DB NOT NULL | 说明 |
| --- | --- | --- | --- |
| `id` | integer | 是，主键 | 自增主键。 |
| `operation_id` | string | 是 | UUID，用于标记一次用户操作。 |
| `user_id` | integer | 是 | 操作者用户 id。 |
| `permission_level` | string | 是 | 操作时的有效权限。 |
| `source` | string | 是 | 来源，例如 `upload`、`sql_editor`、`batch_mutate`、`batch_replace`、`location_editor`、`admin`。 |
| `action` | string | 是 | 动作，例如 `import`、`create`、`update`、`delete`、`batch_update`、`replace`、`update_location`、`set_permission`。 |
| `table_name` | string | 是 | 受影响表名。 |
| `target_scope` | text | 否 | 服务端实际作用范围的人类可读描述。 |
| `affected_rows` | integer | 是 | 受影响行数。 |
| `status` | string | 是 | 当前成功写入的日志为 `success`。 |
| `payload_json` | text | 否 | JSON 字符串形式的操作载荷。 |
| `created_at` | datetime | 是 | 日志创建时间。 |

索引：

- `operation_id`
- `user_id`
- `permission_level`
- `source`
- `action`
- `table_name`
- `status`
- `created_at`

## 通用约定

### Base URL

所有接口都挂在：

```text
/api/vocabulary
```

SQL 编辑接口挂在：

```text
/api/vocabulary/sql
```

### 错误响应

FastAPI 默认错误响应格式：

```json
{
  "detail": "错误说明"
}
```

常见状态码：

| 状态码 | 含义 |
| --- | --- |
| `400` | 请求参数、文件、字段、表名、列名、解析内容不合法。 |
| `401` | 需要登录但未登录或 JWT 无效。 |
| `403` | 已登录但没有所需 vocabulary 权限，或 edit 用户试图访问别人数据。 |
| `404` | 目标地点不存在。 |
| `409` | 导入目标地点已有当前用户的数据，且未显式允许覆盖。 |
| `422` | FastAPI/Pydantic 请求体验证失败。 |
| `500` | 非预期服务端错误。 |

## 1. 当前用户 vocabulary 上下文

### `GET /api/vocabulary/me`

用途：前端登录后或进入 vocabulary 管理页面前调用，用于决定显示哪些按钮和页面能力。

权限：需要登录。

请求体：无。

查询参数：无。

响应体：

```json
{
  "user_id": 7,
  "permission_level": "edit",
  "can_upload": true,
  "can_manage_entries": false,
  "can_view_logs": false
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | number | 当前 JWT 用户 id。 |
| `permission_level` | string or null | `edit`、`manage` 或 `null`。项目 admin 返回 `manage`。 |
| `can_upload` | boolean | 是否可以上传词表。 |
| `can_manage_entries` | boolean | 是否可以管理整张 entries 表。`edit` 为 false。 |
| `can_view_logs` | boolean | 是否可以查看 vocabulary logs。 |

无权限普通用户示例：

```json
{
  "user_id": 12,
  "permission_level": null,
  "can_upload": false,
  "can_manage_entries": false,
  "can_view_logs": false
}
```

前端建议：

- `can_upload = true` 时显示上传入口。
- `permission_level = "edit"` 时，表格编辑页面只展示用户自己的 entries。
- `permission_level = "manage"` 时，可以显示全表 entries 管理和 logs 入口。
- 权限管理接口还需要项目 admin，不能只看 `can_manage_entries`。

## 2. 公开搜索展示接口

这一组接口不涉及编辑权限。当前代码没有挂 `get_current_user`，所以前端公开展示页可以直接调用。

### 搜索字段枚举

`search_fields` 支持：

| 值 | 搜索列 |
| --- | --- |
| `definition` | `standard_word` |
| `headword` | `local_expression` |
| `pronunciation` | `ipa` |
| `detail` | `notes`、`informations` |
| `location` | `location_name` 和地点元数据字段 |
| `all` | 当前实现等同默认内容字段：`definition`、`headword`、`pronunciation`、`detail`，不包含 `location`。 |

默认不传 `search_fields` 时，搜索 `definition`、`headword`、`pronunciation`、`detail`。

`search_fields` 和 `locations` 可以重复传参，也可以使用逗号分隔。示例：

```text
?search_fields=definition&search_fields=headword
?search_fields=definition,headword
?locations=息烽&locations=罗田
?locations=息烽,罗田
```

### `GET /api/vocabulary/search/entries`

用途：前台词表结果列表，分页返回 entries。

权限：公开。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 限制 | 说明 |
| --- | --- | --- | --- | --- |
| `q` | string | null | 可选 | 搜索关键词。 |
| `search_fields` | string[] | 默认内容字段 | 可选 | 见上面的搜索字段枚举。 |
| `locations` | string[] | null | 可选 | 地点过滤词，会匹配地点简称和地点元数据。 |
| `standard_words` | string[] | null | 可选 | 精确过滤一个或多个 `standard_word`，适合从标准词列表跳回 entries。 |
| `page` | number | `1` | `>= 1` | 页码。 |
| `page_size` | number | `50` | `1..200` | 每页条数。 |

请求示例：

```text
GET /api/vocabulary/search/entries?q=日头&search_fields=definition&search_fields=headword&locations=息烽&page=1&page_size=20
```

响应体：

```json
{
  "items": [
    {
      "id": 1,
      "standard_word": "太阳",
      "local_expression": "日头",
      "ipa": "ȵiʔ tou",
      "notes": "示例注释",
      "informations": "",
      "location_name": "息烽",
      "location_label": "贵州 / 贵阳 / 息烽"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `items` | array | 当前页结果。 |
| `items[].id` | number | `vocabulary_entries.id`，可作为前端列表稳定 key。 |
| `items[].standard_word` | string | 书面词条/释义。 |
| `items[].local_expression` | string | 当地讲法。 |
| `items[].ipa` | string | IPA。 |
| `items[].notes` | string | 注释。 |
| `items[].informations` | string | 预留信息字段。 |
| `items[].location_name` | string | 地点简称。 |
| `items[].location_label` | string | 用省市县镇村拼出的展示标签；没有元数据时回退为 `location_name`。 |
| `total` | number | 所有匹配结果数。 |
| `page` | number | 当前页。 |
| `page_size` | number | 每页条数。 |

### `GET /api/vocabulary/search/standard-words`

用途：返回按 `standard_word` 聚合的标准词列表，用于地图模式或词条筛选器。

权限：公开。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 限制 | 说明 |
| --- | --- | --- | --- | --- |
| `q` | string | null | 可选 | 搜索关键词。 |
| `search_fields` | string[] | 默认内容字段 | 可选 | 见搜索字段枚举。 |
| `locations` | string[] | null | 可选 | 地点过滤词。 |
| `limit` | number | `100` | `1..1000` | 最多返回多少个标准词。 |

响应体：

```json
{
  "standard_words": [
    {
      "standard_word": "太阳",
      "entry_count": 12,
      "location_count": 3
    }
  ],
  "total": 120
}
```

说明：

- `standard_words.length` 最多等于 `limit`。
- `total` 是过滤条件下的标准词总数，不是当前返回数组长度。

### `GET /api/vocabulary/search/map-points`

用途：地图展示。按地点聚合匹配 entries，返回可画点的经纬度和该点 entries 数量。

权限：公开。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `q` | string | null | 搜索关键词。 |
| `search_fields` | string[] | 默认内容字段 | 见搜索字段枚举。 |
| `locations` | string[] | null | 地点过滤词。 |

请求示例：

```text
GET /api/vocabulary/search/map-points?q=日头&locations=息烽
```

响应体：

```json
{
  "points": [
    {
      "location_name": "息烽",
      "location_label": "贵州 / 贵阳 / 息烽",
      "longitude": 106.7401,
      "latitude": 27.0902,
      "entry_count": 12
    }
  ],
  "total_entries": 12,
  "total_points": 1,
  "omitted_without_coordinates": 0
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points` | array | 可绘制地图点。 |
| `points[].longitude` | number | 经度。由 `coordinates` 第一个数字解析。 |
| `points[].latitude` | number | 纬度。由 `coordinates` 第二个数字解析。 |
| `points[].entry_count` | number | 该地点匹配 entries 数。 |
| `total_entries` | number | 所有匹配 entries 总数，包括坐标无法解析的地点。 |
| `total_points` | number | 成功解析坐标并返回的点数。 |
| `omitted_without_coordinates` | number | 因坐标为空或格式不可解析而省略的地点组数。 |

注意：`coordinates` 当前按 `longitude,latitude` 或中文逗号格式解析，例如 `106.7401,27.0902`。

### `GET /api/vocabulary/search/map-items`

用途：前端选中一个或多个标准词后，按地点返回这些标准词对应的词条详情和地图点。

权限：公开。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 限制 | 说明 |
| --- | --- | --- | --- | --- |
| `standard_words` | string[] | 无 | 必填 | 一个或多个标准词。 |
| `q` | string | null | 可选 | 额外搜索关键词。 |
| `search_fields` | string[] | 默认内容字段 | 可选 | 见搜索字段枚举。 |
| `locations` | string[] | null | 可选 | 地点过滤词。 |

响应体：

```json
{
  "points": [
    {
      "location_name": "息烽",
      "location_label": "贵州 / 贵阳 / 息烽",
      "longitude": 106.7401,
      "latitude": 27.0902,
      "entry_count": 1,
      "items": [
        {
          "id": 1,
          "standard_word": "太阳",
          "local_expression": "日头",
          "ipa": "ȵiʔ tou",
          "notes": "示例注释",
          "informations": ""
        }
      ]
    }
  ],
  "total_entries": 1,
  "total_points": 1,
  "omitted_without_coordinates": 0
}
```

### `GET /api/vocabulary/search/location-options`

用途：搜索页地点筛选器选项。

权限：公开。

请求体：无。

查询参数：无。

响应体：

```json
{
  "locations": [
    {
      "location_name": "息烽",
      "location_label": "贵州 / 贵阳 / 息烽"
    }
  ],
  "total": 1
}
```

说明：

- 返回去重后的 `location_name`。
- 如果不同用户上传了同名地点，当前响应按 `location_name` 去重，前端不会看到内部 `user_id` 或 location `id`。

## 3. 词表导入接口

导入接口用于上传一个地点的一份词表。前端应先调用 preview，再由用户确认后调用正式 imports。

### 上传文件格式

支持表格文件：

| 扩展名 | 解析方式 |
| --- | --- |
| `.xlsx` | `pandas.read_excel` |
| `.xls` | `pandas.read_excel` |
| `.csv` | `pandas.read_csv` |
| `.tsv` | `pandas.read_csv(sep="\t")` |

支持文档文件：

| 扩展名 | 解析方式 |
| --- | --- |
| `.docx` | `python-docx` 读取段落文本。 |
| `.doc` | 优先用 `antiword`，再用 macOS `textutil`，最后尝试按文本编码读取。真正的二进制旧 Word 文件依赖服务器安装转换工具。 |

### `parser_mode`

| 值 | 含义 |
| --- | --- |
| `auto` | 默认。表格扩展名走 table；文档扩展名先尝试括号模式，失败后走空白分隔模式。 |
| `table` | 强制表格模式。 |
| `doc_whitespace` | 强制文档空白分隔模式。 |
| `doc_bracket` | 强制文档括号识别模式。 |

### 表格列名容忍

表格文件会归一化到四个字段：

| 内部字段 | 必填 | 可接受列名 |
| --- | --- | --- |
| `standard_word` | 是 | `standard_word`、`written`、`释义`、`釋義`、`书面`、`書面`、`书面词条`、`書面詞條`、`词条`、`詞條`、`meaning` |
| `local_expression` | 是 | `local_expression`、`vocabulary`、`当地讲法`、`當地講法`、`方言词`、`方言詞`、`方言讲法`、`方言講法`、`local` |
| `ipa` | 是 | `ipa`、`IPA`、`音标`、`音標`、`国际音标`、`國際音標` |
| `notes` | 否 | `notes`、`note`、`注释`、`註釋`、`备注`、`備註`、`说明`、`說明` |

行级规则：

- `standard_word` 和 `local_expression` 都为空的行会被跳过，计入 `skipped_count`。
- `standard_word`、`local_expression`、`ipa` 任一缺失会产生错误。
- `notes` 缺失时写空字符串。

### 文档空白分隔模式

一条记录可以是一段，也可以用空行分隔。记录内部字段用空格、tab 或换行分隔。

目标字段顺序：

```text
standard_word local_expression ipa notes
```

示例：

```text
太阳 日头 ȵiʔ tou 常用词

月亮
月光
ŋyɛ
也可写作月光光
```

解析规则：

- 至少需要前三个字段：`standard_word`、`local_expression`、`ipa`。
- 第四个字段及之后内容合并为 `notes`。

### 文档括号识别模式

一行或一个段落是一条记录：

| 写法 | 对应字段 |
| --- | --- |
| 括号外普通文本 | `standard_word` |
| `[]` | `ipa` |
| `{}` | `notes` |
| `()` 或 `（）` | `local_expression` |

示例：

```text
太阳（日头）[ȵiʔ tou]{常用词}
月亮(月光)[ŋyɛ]{夜晚天体}
```

### Location JSON

导入接口使用 `multipart/form-data`，其中 `location` 字段是 JSON 字符串。

必填：

| 标准字段 | 别名 | 说明 |
| --- | --- | --- |
| `location_name` | `簡稱`、`简称`、`地名`、`name`、`location` | 地点简称。 |
| `coordinates` | `經緯度`、`经纬度`、`lnglat`、`latlng` | 经纬度字符串。 |

可选：

| 标准字段 | 别名 |
| --- | --- |
| `province` | `省` |
| `city` | `市` |
| `county` | `縣`、`县`、`區縣`、`区县` |
| `town` | `鎮`、`镇`、`鄉鎮`、`乡镇` |
| `administrative_village` | `行政村` |
| `natural_village` | `自然村` |
| `yindian_region` | `音典分區`、`音典分区` |
| `atlas_region` | `地圖集二分區`、`地图集二分区`、`地圖集分區`、`地图集分区`、`分區`、`分区` |

示例：

```json
{
  "location_name": "息烽",
  "coordinates": "106.7401,27.0902",
  "province": "贵州",
  "city": "贵阳",
  "county": "息烽",
  "town": "",
  "administrative_village": "",
  "natural_village": "",
  "yindian_region": "",
  "atlas_region": ""
}
```

同义字段示例：

```json
{
  "简称": "息烽",
  "经纬度": "106.7401,27.0902",
  "省": "贵州",
  "市": "贵阳",
  "县": "息烽"
}
```

### `POST /api/vocabulary/imports/preview`

用途：上传前预览。解析文件、校验地点、检查将会删除多少同地点旧 entries，但不写入数据库。

权限：需要登录，且有效 vocabulary 权限为 `edit`、`manage` 或项目 admin。

请求类型：`multipart/form-data`。

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | file | 是 | 无 | 词表文件。 |
| `location` | string | 是 | 无 | JSON 字符串，见 Location JSON。 |
| `parser_mode` | string | 否 | `auto` | `auto`、`table`、`doc_whitespace`、`doc_bracket`。 |
| `overwrite` | boolean | 否 | `false` | 为 true 时允许替换当前用户同 `location_name` 的旧 entries。 |

curl 示例：

```bash
curl -X POST "http://localhost:8000/api/vocabulary/imports/preview" \
  -H "Authorization: Bearer <JWT>" \
  -F "file=@tests/息烽.xlsx" \
  -F 'location={"location_name":"息烽","coordinates":"106.7401,27.0902","province":"贵州","city":"贵阳","county":"息烽"}' \
  -F "parser_mode=auto"
```

响应体：

```json
{
  "success": true,
  "location_name": "息烽",
  "permission_level": "edit",
  "parsed_count": 100,
  "would_delete_existing_count": 23,
  "skipped_count": 0,
  "errors": [],
  "parser_mode": "table"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `success` | boolean | 解析成功且至少有一条有效记录时为 true。 |
| `location_name` | string | 归一化后的地点简称。 |
| `permission_level` | string | 当前用户有效权限。admin 返回 `manage`。 |
| `parsed_count` | number | 解析出的有效行数。有解析错误时当前实现返回 0。 |
| `would_delete_existing_count` | number | 正式导入时会删除的当前用户同 `location_name` 旧 entries 数。 |
| `skipped_count` | number | 空行/空记录跳过数。 |
| `errors` | string[] | 解析或校验错误。 |
| `parser_mode` | string | 实际使用的解析模式。 |

写入行为：

- 不写 `vocabulary_locations`。
- 不删除或插入 `vocabulary_entries`。
- 不写 `vocabulary_logs`。

前端建议：

- 用户选择文件和地点后先调用 preview。
- 展示 `parsed_count`、`would_delete_existing_count`、`skipped_count`、`errors`。
- `would_delete_existing_count > 0` 时明确提示用户：正式导入会替换当前用户这个地点简称下的旧词条。
- 只有用户确认后再调用正式导入。

### `POST /api/vocabulary/imports`

用途：正式导入词表。

权限：需要登录，且有效 vocabulary 权限为 `edit`、`manage` 或项目 admin。

请求类型：`multipart/form-data`。

请求体同 preview：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | file | 是 | 无 | 词表文件。 |
| `location` | string | 是 | 无 | JSON 字符串，见 Location JSON。 |
| `parser_mode` | string | 否 | `auto` | `auto`、`table`、`doc_whitespace`、`doc_bracket`。 |

响应体：

```json
{
  "success": true,
  "location_id": 1,
  "location_name": "息烽",
  "permission_level": "edit",
  "imported_count": 100,
  "deleted_existing_count": 23,
  "skipped_count": 0,
  "errors": [],
  "parser_mode": "table"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `success` | boolean | 成功导入时为 true。 |
| `location_id` | number | `vocabulary_locations.id`，仅在导入响应中返回。其他 location API 当前不暴露 id。 |
| `location_name` | string | 地点简称。 |
| `permission_level` | string | 当前用户有效权限。 |
| `imported_count` | number | 新插入 entries 数。 |
| `deleted_existing_count` | number | 导入前删除的旧 entries 数。 |
| `skipped_count` | number | 跳过的空行/空记录数。 |
| `errors` | string[] | 成功时为空数组。 |
| `parser_mode` | string | 实际使用的解析模式。 |

正式导入事务逻辑：

1. 校验权限。
2. 归一化 location JSON。
3. 解析文件。
4. 插入或更新 `vocabulary_locations` 的 `(user_id, location_name)` 行。
5. 删除当前用户同 `location_name` 的旧 `vocabulary_entries`。
6. 插入新 entries。
7. 写一条 `vocabulary_logs`，`source = "upload"`，`action = "import"`，`table_name = "vocabulary_entries"`。
8. 提交事务。

重要边界：

- 上传替换范围固定为当前用户自己的 `(user_id, location_name)`。
- 即使用户是 `manage` 或项目 admin，上传接口也不会替换其他用户同名地点的数据。
- `overwrite=false` 且当前用户同地点已有 entries 时返回 `409`；其他用户同名地点不会阻止本用户首次上传。
- 如果解析或插入失败，会回滚事务，避免先删后失败造成半导入。

## 4. 地点元数据接口

地点元数据通过专用接口管理，不通过 `/api/vocabulary/sql/*` 暴露。

### `GET /api/vocabulary/locations`

用途：读取 vocabulary 地点元数据。

权限：需要登录，且有效 vocabulary 权限为 `edit`、`manage` 或项目 admin。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 限制 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | number | null | 可选 | `manage`/admin 可用来过滤某个用户；`edit` 只能传自己的 user_id 或不传。 |
| `location_name` | string | null | 可选 | 精确匹配地点简称。 |
| `page` | number | `1` | `>= 1` | 页码。 |
| `page_size` | number | `50` | `1..200` | 每页条数。 |

请求示例：

```text
GET /api/vocabulary/locations?page=1&page_size=50
GET /api/vocabulary/locations?user_id=7&location_name=息烽
```

响应体：

```json
{
  "locations": [
    {
      "user_id": 7,
      "location_name": "息烽",
      "coordinates": "106.7401,27.0902",
      "province": "贵州",
      "city": "贵阳",
      "county": "息烽",
      "town": "",
      "administrative_village": "",
      "natural_village": "",
      "yindian_region": "",
      "atlas_region": "",
      "location_label": "贵州 / 贵阳 / 息烽"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

权限细节：

- `edit` 用户永远只返回自己的 locations。
- `edit` 用户传入其他 `user_id` 会返回 `403`。
- `manage`/admin 不传 `user_id` 时返回全部用户的 locations。

### `PATCH /api/vocabulary/locations/{location_name}`

用途：编辑已有地点元数据。不能改地点简称。

权限：需要登录，且有效 vocabulary 权限为 `edit`、`manage` 或项目 admin。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `location_name` | string | 要编辑的地点简称。 |

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `user_id` | number | null | `manage`/admin 用于指定目标用户。`edit` 只能传自己的 user_id 或不传。 |

请求体：`application/json`。

可更新字段：

```json
{
  "coordinates": "106.7401,27.0902",
  "province": "贵州",
  "city": "贵阳",
  "county": "息烽",
  "town": "",
  "administrative_village": "",
  "natural_village": "",
  "yindian_region": "",
  "atlas_region": ""
}
```

请求体规则：

- 至少提供一个字段。
- 不允许额外字段。
- 不允许传 `location_name`。
- 不允许传 `id`。
- `coordinates` 如果提供，不能为空字符串。
- 其他字段可以更新为空字符串。

响应体：

```json
{
  "user_id": 7,
  "location_name": "息烽",
  "coordinates": "106.7401,27.0902",
  "province": "贵州",
  "city": "贵阳",
  "county": "息烽",
  "town": "",
  "administrative_village": "",
  "natural_village": "",
  "yindian_region": "",
  "atlas_region": "",
  "location_label": "贵州 / 贵阳 / 息烽"
}
```

权限和歧义处理：

- `edit` 用户只能编辑 `(current_user.id, location_name)`。
- `edit` 用户传其他 `user_id` 返回 `403`。
- `manage`/admin 如果不传 `user_id`，而同一个 `location_name` 属于多个用户，返回 `400`，要求前端带 `?user_id=...`。
- 成功更新会写一条 log，`source = "location_editor"`，`action = "update_location"`，`table_name = "vocabulary_locations"`。

## 5. 日志接口

### `GET /api/vocabulary/logs`

用途：读取 vocabulary 操作日志。

权限：需要登录，且有效 vocabulary 权限为 `manage` 或项目 admin。

权限变更日志（`action = "set_permission"`）只对项目 admin 可见；普通 vocabulary `manage` 用户读取 logs 时会自动隐藏这类日志。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `user_id` | number | null | 按操作者过滤。 |
| `permission_level` | string | null | 按操作时权限过滤。 |
| `source` | string | null | 按来源过滤。 |
| `action` | string | null | 按动作过滤。 |
| `table_name` | string | null | 按表名过滤。 |
| `status` | string | null | 按状态过滤。当前成功日志为 `success`。 |
| `page` | number | `1` | 页码，`>= 1`。 |
| `page_size` | number | `50` | 每页条数，`1..200`。 |

请求示例：

```text
GET /api/vocabulary/logs?source=batch_replace&table_name=vocabulary_entries&page=1&page_size=20
```

响应体：

```json
{
  "logs": [
    {
      "id": 10,
      "operation_id": "c85d41ff-514a-486b-934c-4ad44108c0a8",
      "user_id": 7,
      "permission_level": "edit",
      "source": "upload",
      "action": "import",
      "table_name": "vocabulary_entries",
      "target_scope": "user_id = 7; location_name = 息烽",
      "affected_rows": 100,
      "status": "success",
      "payload_json": "{\"filename\":\"息烽.xlsx\",\"location_name\":\"息烽\",\"deleted_existing_count\":23,\"imported_count\":100,\"parser_mode\":\"table\"}",
      "created_at": "2026-07-26 12:34:56"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

日志写入范围：

- 正式导入写 log。
- location PATCH 写 log。
- admin 设置权限写 log。
- SQL mutate、batch mutate、batch replace execute 写 log。
- preview 不写 log。
- 大多数异常失败路径当前不会写失败 log；已进入 SQL 编辑但影响 0 行的操作会写成功状态且 `affected_rows = 0`。

## 6. Admin 权限管理接口

这一组接口用于写 `vocabulary_permissions`。它们需要项目 admin 权限，不是 vocabulary `manage` 权限。

### `GET /api/vocabulary/admin/permissions`

用途：分页列出 vocabulary 权限表。

权限：项目 admin。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 限制 |
| --- | --- | --- | --- |
| `page` | number | `1` | `>= 1` |
| `page_size` | number | `50` | `1..200` |

响应体：

```json
{
  "permissions": [
    {
      "user_id": 7,
      "permission_level": "edit"
    },
    {
      "user_id": 9,
      "permission_level": "manage"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 50
}
```

### `GET /api/vocabulary/admin/permissions/{user_id}`

用途：查询某个用户的 vocabulary 权限。

权限：项目 admin。

请求体：无。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | number | 目标用户 id。 |

响应体，有权限行：

```json
{
  "user_id": 7,
  "permission_level": "edit"
}
```

响应体，无权限行：

```json
{
  "user_id": 7,
  "permission_level": null
}
```

### `PUT /api/vocabulary/admin/permissions/{user_id}`

用途：新增、更新或撤销某个用户的 vocabulary 权限。

权限：项目 admin。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | number | 目标用户 id。 |

请求体：

```json
{
  "permission_level": "edit"
}
```

字段说明：

| 字段 | 类型 | 可选值 |
| --- | --- | --- |
| `permission_level` | string | `edit`、`manage` 或 `none` |

响应体：

```json
{
  "user_id": 7,
  "permission_level": "edit"
}
```

写入行为：

- 如果用户没有权限行且设置 `edit/manage`，则插入。
- 如果用户已有权限行且设置 `edit/manage`，则更新。
- 如果设置 `none`，则删除该用户的权限行；响应里的 `permission_level` 为 `null`。
- 写一条 log：`source = "admin"`、`action = "set_permission"`、`table_name = "vocabulary_permissions"`。

## 7. Vocabulary SQL API

这组接口用于表格模式编辑。它是从通用 SQL 编辑逻辑抽出来的 vocabulary 专用版本，但边界更窄。

统一规则：

- 前缀固定为 `/api/vocabulary/sql`。
- 不需要也不接受 `db_key`。
- 固定访问 `data/vocabulary.db`。
- 只允许访问 `vocabulary_entries`。
- `vocabulary_locations` 不开放给 SQL API，请用 `/api/vocabulary/locations`。
- `vocabulary_logs` 不开放给 SQL API，请用 `/api/vocabulary/logs`。
- `vocabulary_permissions` 不开放给 SQL API，请用 `/api/vocabulary/admin/permissions*`。
- 所有 SQL API 都需要登录，且有效 vocabulary 权限为 `edit`、`manage` 或项目 admin。
- `edit` 用户所有 query/update/batch update/replace 都自动附加 `user_id = current_user.id`。
- `edit` 用户可以通过 SQL API 单条删除自己的 entry，但不能执行 `batch_delete`。
- `manage` 和 admin 可以 query/update/delete/batch/replace 全部 `vocabulary_entries`。
- create 和 batch_create 会忽略前端提交的 `id`，并强制 `user_id = current_user.id`。这对 `manage` 和 admin 也一样。
- `id`、`user_id` 和 `location_name` 不允许被 update 或 replace。
- 所有写操作成功路径都会写一条操作级 log。

### 可编辑字段

`vocabulary_entries` 当前列：

```text
id
user_id
location_name
standard_word
local_expression
ipa
notes
informations
source_filename
```

create 可由前端提交的字段：

```text
location_name
standard_word
local_expression
ipa
notes
informations
source_filename
```

update、batch_update、batch_replace 可修改的字段：

```text
standard_word
local_expression
ipa
notes
informations
source_filename
```

不可修改字段：

```text
id
user_id
location_name
```

### 过滤规则

多个 SQL API 使用相同过滤格式：

```json
{
  "filters": {
    "location_name": ["息烽", "罗田"],
    "notes": [null]
  }
}
```

含义：

- 同一列多个值是 OR：`location_name IN (...)`。
- 不同列之间是 AND。
- 某列值包含 `null` 时，匹配 `NULL` 或空字符串。
- `search_text` 会对 `search_columns` 做 LIKE 搜索。

### `POST /api/vocabulary/sql/query`

用途：表格分页查询 `vocabulary_entries`。

权限：`edit`、`manage`、admin。

请求体：

```json
{
  "table_name": "vocabulary_entries",
  "page": 1,
  "page_size": 20,
  "sort_by": "id",
  "sort_desc": false,
  "filters": {
    "location_name": ["息烽"]
  },
  "search_text": "日头",
  "search_columns": ["standard_word", "local_expression", "ipa", "notes"]
}
```

字段说明：

| 字段 | 类型 | 默认值 | 限制 |
| --- | --- | --- | --- |
| `table_name` | string | `vocabulary_entries` | 只能是 `vocabulary_entries`。 |
| `page` | number | `1` | `>= 1`。 |
| `page_size` | number | `20` | 当前 validator 最大 `500`。 |
| `sort_by` | string or null | null | 必须是有效列名。 |
| `sort_desc` | boolean | false | 是否降序。 |
| `filters` | object | `{}` | key 必须是有效列名。 |
| `search_text` | string or null | null | LIKE 搜索文本。 |
| `search_columns` | string[] | `[]` | 每个值必须是有效列名。 |

响应体：

```json
{
  "data": [
    {
      "rowid": 1,
      "id": 1,
      "user_id": 7,
      "location_name": "息烽",
      "standard_word": "太阳",
      "local_expression": "日头",
      "ipa": "ȵiʔ tou",
      "notes": "示例注释",
      "informations": "",
      "source_filename": "息烽.xlsx"
    }
  ],
  "total": 1,
  "page": 1
}
```

注意：

- 响应包含 `rowid` 和表内所有列。
- 响应当前不返回 `page_size`。
- `edit` 用户只能查到自己的 entries。

### `GET /api/vocabulary/sql/query/columns`

用途：读取表字段信息。

权限：`edit`、`manage`、admin。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `table_name` | string | `vocabulary_entries` | 只能是 `vocabulary_entries`。 |

响应体：

```json
{
  "table": "vocabulary_entries",
  "columns": [
    {
      "name": "id",
      "type": "INTEGER",
      "notnull": false,
      "pk": true,
      "default_value": null
    },
    {
      "name": "standard_word",
      "type": "VARCHAR(500)",
      "notnull": true,
      "pk": false,
      "default_value": null
    }
  ]
}
```

前端建议：

- 表格编辑器初始化时调用。
- 根据 `name` 渲染列，根据 `pk` 判断主键列，根据 `notnull` 辅助校验。
- SQLite 的 integer primary key 在 `PRAGMA table_info` 里可能显示 `notnull = false`，前端判断主键时应优先看 `pk`。

### `GET /api/vocabulary/sql/query/count`

用途：读取当前权限范围内的行数，可带一个简单等值过滤。

权限：`edit`、`manage`、admin。

请求体：无。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `table_name` | string | `vocabulary_entries` | 只能是 `vocabulary_entries`。 |
| `filter_column` | string | null | 可选，有效列名。 |
| `filter_value` | string | null | 可选，过滤值。 |

请求示例：

```text
GET /api/vocabulary/sql/query/count?table_name=vocabulary_entries&filter_column=location_name&filter_value=息烽
```

响应体：

```json
{
  "count": 100
}
```

### `GET /api/vocabulary/sql/distinct/{table_name}/{column}`

用途：读取某列去重值，常用于筛选器。

权限：`edit`、`manage`、admin。

请求体：无。

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `table_name` | string | 只能是 `vocabulary_entries`。 |
| `column` | string | 有效列名。 |

请求示例：

```text
GET /api/vocabulary/sql/distinct/vocabulary_entries/location_name
```

响应体：

```json
{
  "values": ["息烽", "罗田胜利"]
}
```

说明：

- 最多返回 1000 个去重值。
- 当前实现过滤掉 `NULL`。
- `edit` 用户只能看到自己数据范围内的去重值。

### `POST /api/vocabulary/sql/distinct-query`

用途：在当前筛选上下文下读取某列去重值，适合级联筛选器。

权限：`edit`、`manage`、admin。

请求体：

```json
{
  "table_name": "vocabulary_entries",
  "target_column": "location_name",
  "current_filters": {
    "standard_word": ["太阳"]
  },
  "search_text": "日",
  "search_columns": ["standard_word", "local_expression"]
}
```

字段说明：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `table_name` | string | `vocabulary_entries` | 只能是 `vocabulary_entries`。 |
| `target_column` | string | 无 | 要取 distinct 的列。 |
| `current_filters` | object | `{}` | 当前已有过滤。目标列自身会被排除。 |
| `search_text` | string | `""` | 搜索文本。 |
| `search_columns` | string[] | `[]` | LIKE 搜索列。 |

响应体：

```json
{
  "values": ["息烽"]
}
```

### `POST /api/vocabulary/sql/mutate`

用途：单条 create/update/delete。

权限：`edit`、`manage`、admin。

请求体，create：

```json
{
  "table_name": "vocabulary_entries",
  "action": "create",
  "pk_column": "id",
  "pk_value": null,
  "data": {
    "location_name": "息烽",
    "standard_word": "太阳",
    "local_expression": "日头",
    "ipa": "ȵiʔ tou",
    "notes": "示例注释",
    "informations": "",
    "source_filename": "manual"
  }
}
```

create 规则：

- `id` 会被忽略。
- `user_id` 会被强制写成当前用户 id。
- `standard_word`、`local_expression`、`ipa`、`location_name` 依数据库约束应提供非空值。
- 当前不会自动创建 `vocabulary_locations`，所以新建 entries 前最好已有对应 location。

请求体，update：

```json
{
  "table_name": "vocabulary_entries",
  "action": "update",
  "pk_column": "id",
  "pk_value": 1,
  "data": {
    "ipa": "ȵiʔ tʰou",
    "notes": "修订音标"
  }
}
```

update 规则：

- `data` 不能为空。
- `id`、`user_id`、`location_name` 不允许出现在 `data`。
- `edit` 用户更新别人数据时，服务端 WHERE 会带上当前用户 id，因此 `affected_rows = 0`。

请求体，delete：

```json
{
  "table_name": "vocabulary_entries",
  "action": "delete",
  "pk_column": "id",
  "pk_value": 1,
  "data": {}
}
```

delete 规则：

- `edit` 用户只能删除自己的目标 id；删除别人数据时服务端 WHERE 会带上当前用户 id，因此 `affected_rows = 0`。
- `manage`/admin 可以删除任意目标 id。
- 当前没有“按地点清空自己全部 entries”的专用接口。

响应体：

```json
{
  "status": "success",
  "action": "update",
  "affected_rows": 1
}
```

写入日志：

- `source = "sql_editor"`
- `action = create/update/delete`
- `table_name = "vocabulary_entries"`

### `POST /api/vocabulary/sql/batch-mutate`

用途：批量 create/update/delete。

权限：`edit`、`manage`、admin。

请求体，batch_create：

```json
{
  "table_name": "vocabulary_entries",
  "action": "batch_create",
  "pk_column": "id",
  "create_data": [
    {
      "location_name": "息烽",
      "standard_word": "太阳",
      "local_expression": "日头",
      "ipa": "ȵiʔ tou",
      "notes": "",
      "informations": "",
      "source_filename": "manual"
    }
  ],
  "update_data": [],
  "delete_ids": []
}
```

batch_create 规则：

- 每条记录都会强制写入当前用户 id。
- `id` 会被忽略。
- `user_id` 会被覆盖。

请求体，batch_update：

```json
{
  "table_name": "vocabulary_entries",
  "action": "batch_update",
  "pk_column": "id",
  "create_data": [],
  "update_data": [
    {
      "id": 1,
      "ipa": "ȵiʔ tʰou",
      "notes": "批量修订"
    }
  ],
  "delete_ids": []
}
```

batch_update 规则：

- 每条记录必须包含 `pk_column`，默认 `id`。
- 除主键外至少要有一个更新字段。
- 不允许修改 `id`、`user_id`、`location_name`。
- `edit` 用户只能更新自己的记录；无权限或未找到会计入错误。

请求体，batch_delete：

```json
{
  "table_name": "vocabulary_entries",
  "action": "batch_delete",
  "pk_column": "id",
  "create_data": [],
  "update_data": [],
  "delete_ids": [1, 2, 3]
}
```

batch_delete 规则：

- `edit` 用户不能通过 SQL API 批量删除 entries，返回 `403`。
- `manage`/admin 可以删除任意记录。
- 未找到或无权限的 id 会计入错误数量。

响应体：

```json
{
  "status": "completed",
  "action": "batch_update",
  "success_count": 1,
  "error_count": 0,
  "total": 1,
  "errors": null
}
```

有错误时：

```json
{
  "status": "completed",
  "action": "batch_update",
  "success_count": 1,
  "error_count": 1,
  "total": 2,
  "errors": ["第2条记录未找到或无权限 (主键=9)"]
}
```

写入日志：

- `source = "batch_mutate"`
- `action = batch_create/batch_update/batch_delete`
- `table_name = "vocabulary_entries"`

### `POST /api/vocabulary/sql/batch-replace-preview`

用途：批量替换前预览命中数量。

权限：`edit`、`manage`、admin。

请求体：

```json
{
  "table_name": "vocabulary_entries",
  "columns": ["ipa", "notes"],
  "find_text": "旧文本",
  "match_mode": "contains",
  "is_empty_search": false,
  "filters": {
    "location_name": ["息烽"]
  },
  "search_text": "",
  "search_columns": []
}
```

字段说明：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `table_name` | string | `vocabulary_entries` | 只能是 `vocabulary_entries`。 |
| `columns` | string[] | 无 | 要替换的列，不能包含 `id`、`user_id` 或 `location_name`。 |
| `find_text` | string | `""` | 查找文本。 |
| `match_mode` | string | `contains` | `contains` 或 `exact`。 |
| `is_empty_search` | boolean | false | true 时匹配目标列为空或 NULL。 |
| `filters` | object | `{}` | 额外过滤。 |
| `search_text` | string | `""` | 额外全文搜索文本。 |
| `search_columns` | string[] | `[]` | 额外全文搜索列。 |

响应体：

```json
{
  "status": "success",
  "total_matches": 12
}
```

重要规则：

- preview 和 execute 使用同一套 WHERE 构造逻辑。
- `edit` 用户 preview 的数量只包含自己的数据。
- `manage`/admin preview 的数量包含全表匹配数据。

### `POST /api/vocabulary/sql/batch-replace-execute`

用途：执行批量替换。

权限：`edit`、`manage`、admin。

请求体：

```json
{
  "table_name": "vocabulary_entries",
  "columns": ["ipa"],
  "find_text": "旧文本",
  "replace_text": "新文本",
  "match_mode": "contains",
  "is_empty_search": false,
  "filters": {
    "location_name": ["息烽"]
  },
  "search_text": "",
  "search_columns": []
}
```

执行规则：

- `match_mode = "contains"` 且 `is_empty_search = false` 时，使用 SQLite `REPLACE(column, find_text, replace_text)`。
- `match_mode = "exact"` 时，将匹配行的目标列直接设置为 `replace_text`。
- `is_empty_search = true` 时，匹配目标列为空或 NULL 的行，并直接设置为 `replace_text`。
- 不允许替换 `id`、`user_id` 或 `location_name`。

响应体：

```json
{
  "status": "success",
  "affected_rows": 12
}
```

写入日志：

- `source = "batch_replace"`
- `action = "replace"`
- `table_name = "vocabulary_entries"`

## 前端推荐调用流程

### 公开搜索页

1. 进入页面时调用 `GET /api/vocabulary/search/location-options` 初始化地点筛选器。
2. 用户输入关键词后调用 `GET /api/vocabulary/search/entries`。
3. 如果页面有地图，同时调用 `GET /api/vocabulary/search/map-points`。
4. 如果需要搜索地点本身，使用 `locations` 参数，或显式传 `search_fields=location`。

### 上传页面

1. 登录后调用 `GET /api/vocabulary/me`。
2. `can_upload = false` 时隐藏或禁用上传入口。
3. 用户选择文件、填写地点 JSON、选择 parser mode。
4. 调用 `POST /api/vocabulary/imports/preview`。
5. 展示解析模式、解析行数、将删除的旧行数、错误列表。
6. 用户确认后调用 `POST /api/vocabulary/imports`。
7. 导入成功后刷新搜索列表、locations 列表或 SQL 表格。

### 地点编辑页面

1. 调用 `GET /api/vocabulary/me` 判断权限。
2. `edit` 用户调用 `GET /api/vocabulary/locations`，不传 `user_id`。
3. `manage`/admin 可以调用 `GET /api/vocabulary/locations?user_id=...` 或不传查看全部。
4. 编辑时调用 `PATCH /api/vocabulary/locations/{location_name}`。
5. 如果 manage/admin 编辑同名地点，建议始终带 `?user_id=...`，避免同名歧义。

### 表格编辑页面

1. 调用 `GET /api/vocabulary/me` 判断权限。
2. 调用 `GET /api/vocabulary/sql/query/columns` 获取列信息。
3. 调用 `POST /api/vocabulary/sql/query` 分页加载数据。
4. 过滤器使用 `GET /api/vocabulary/sql/distinct/vocabulary_entries/{column}` 或 `POST /api/vocabulary/sql/distinct-query`。
5. 单条编辑调用 `POST /api/vocabulary/sql/mutate`。
6. 批量编辑调用 `POST /api/vocabulary/sql/batch-mutate`；edit 用户可以展示单条删除入口，但不要展示批量删除/清空入口。
7. 批量替换必须先调用 `batch-replace-preview`，用户确认命中数后再调用 `batch-replace-execute`。

### 日志页面

1. 调用 `GET /api/vocabulary/me`。
2. `can_view_logs = true` 时显示日志入口。
3. 调用 `GET /api/vocabulary/logs`，使用 `source`、`action`、`table_name`、`user_id` 等参数过滤。

### 权限管理页面

1. 只给项目 admin 显示入口。
2. 调用 `GET /api/vocabulary/admin/permissions` 展示列表。
3. 调用 `GET /api/vocabulary/admin/permissions/{user_id}` 查看单个用户。
4. 调用 `PUT /api/vocabulary/admin/permissions/{user_id}` 设置 `edit`、`manage` 或 `none`。

## 最初需求完成度

### 已完成

| 原始需求 | 当前状态 |
| --- | --- |
| 数据库名 `vocabulary.db` | 已完成，路径为 `data/vocabulary.db`。 |
| 真实数据表包含释义/当地讲法/IPA/注释、地名、informations | 已完成。内部字段为 `standard_word`、`local_expression`、`ipa`、`notes`、`location_name`、`informations`，另有 `user_id` 和 `source_filename`。 |
| 地点信息表包含地名、经纬度、行政区划、多种分区 | 已完成。包含 `location_name`、`coordinates`、省市县镇、行政村、自然村、音典分区、地图集分区。 |
| 地点信息自动填入用户 id | 已完成。 |
| 权限表只需要 edit/manage | 已完成。 |
| admin 是最高级，不应被 vocabulary 权限拦截 | 已完成。admin 有效权限为 `manage`。 |
| 上传 API 统一前缀 `/api/vocabulary` | 已完成。 |
| 上传时前端传 location JSON | 已完成。 |
| 上传时写 locations，同时 entries 写地点简称 | 已完成。 |
| 同简称已有数据时，先删除对应 entries 再写入新数据 | 已完成，范围是当前用户自己的 `(user_id, location_name)`。 |
| 表格格式 `.xlsx/.xls/.tsv/.csv` | 已实现。 |
| 表格列名 mapping 要宽松 | 已实现多组中英文别名。 |
| doc/docx 空白或换行分隔格式 | 已实现。 |
| doc/docx 括号识别格式 | 已实现。 |
| 普通用户不能编辑，edit 只能编辑自己的数据，manage 管理 entries 全表 | 已实现。 |
| `/api/vocabulary/sql/*` 不需要 `db_key` | 已实现，schema forbid extra。 |
| `/api/vocabulary/sql/*` 只能访问 `vocabulary_entries` | 已实现。locations/logs/permissions 都不能通过 SQL API 访问。 |
| 操作日志 `vocabulary_logs` | 已实现，操作级日志。 |
| manage/admin 可以查看 logs | 已实现，通过 `/api/vocabulary/logs`。 |
| admin 接口写 `vocabulary_permissions` | 已实现 GET list、GET one、PUT upsert。 |
| admin 接口撤销 vocabulary 权限 | 已实现，通过 PUT `permission_level = "none"`。 |
| 删除 username，只存 userid | 已完成。 |
| 删除 `raw_location_json` | 已完成，migration 会移除旧列。 |
| 删除旧路径兼容 | 已完成。 |
| `GET /api/vocabulary/me` 返回能力字段 | 已完成。 |
| 公开搜索展示 `/api/vocabulary/search/*` | 已完成。 |

### 部分完成或需要注意

| 项目 | 当前状态 | 说明 |
| --- | --- | --- |
| `.doc` 真实旧 Word 文件 | 部分完成 | 代码支持 `antiword`、`textutil` 或纯文本 fallback。真正二进制 `.doc` 是否稳定取决于服务器工具。 |
| `.xls` 和 `.tsv` 真实样本 | 代码已支持 | 当前测试主要覆盖 `.xlsx`、`.csv`、真实 `.docx` 和 `.doc` 文本 fallback；`.xls/.tsv` 走同类 parser，但还可以补真实样本测试。 |
| 地点经纬度校验 | 部分完成 | 现在只要求非空。地图接口解析失败会省略点并计数，没有在写入时强校验经纬度格式。 |
| 查询 `query.db` 自动补地点信息 | 未采用 | 当前按后来确认的方案：只接收 API 的 location JSON，不自动查 `query.db`。 |
| location id | 内部存在，API 基本不暴露 | locations 表有自增 `id` 用于内部主键。普通 location 读取/编辑接口只用 `location_name + user_id` 定位。 |
| 失败日志 | 部分完成 | 成功写操作都会记录。解析失败、权限失败、参数失败等大多数失败路径当前不写日志。 |
| 删除能力 | 已按当前策略收紧 | edit 用户可以按 id 删除自己的单条 entry，不能批量删除或按地点清空；manage/admin 可以按 id 单条删除和批量删除。 |
| public search 多用户同名地点歧义 | 需要后续优化 | 搜索展示不返回 `user_id`，location options 对 `location_name` 去重。多用户上传同名地点时，前端无法区分来源。 |
| 专门的前台词表详情 API | 未实现 | 当前只有列表、地图点、地点选项，没有 entry detail 页面接口。 |
| 更高级查询能力 | 未实现 | 没有模糊排序、高亮、拼音/IPA 正规化、全文索引等。 |
| tree 逻辑 | 未实现也未计划在本组开放 | 用户已说明 tree 除外，当前 vocabulary SQL 没有 tree。 |

## 建议下一步

优先级较高：

1. 加强 `coordinates` 写入校验，明确要求 `longitude,latitude`。
2. 如果公开搜索需要区分数据来源，响应中增加 `user_id` 或稳定的 location identity。
3. 补真实 `.xls`、`.tsv`、二进制 `.doc` 样本测试。

中期优化：

1. 给公开搜索加更适合前端的排序、高亮和详情接口。
2. 给 logs 增加失败操作记录策略。
3. 对 entries 的常用搜索字段增加更合适的索引或全文搜索方案。
4. 增加 location 创建接口，或明确只能通过导入创建 location。
5. 增加批量导出接口，便于前端下载当前筛选结果。
