# Vocabulary 前后端对齐审计与前端优化指南

本文档用于说明当前 `vocabulary` 功能的真实需求、后端已经实现的能力、前端当前实现与后端契约之间的差异，以及前端后续应该如何分阶段优化。

结论先行：

- 后端数据库真实字段不是 `written` 或中文列名。`vocabulary_entries` 的核心字段是 `standard_word`、`local_expression`、`ipa`、`notes`。
- `written`、`当地讲法`、`释义` 等只属于上传文件表头的容忍别名，不是后端数据库字段，也不是 `/api/vocabulary/sql/*` 表格接口字段。
- 前端已经接入了新的公开搜索、导入、locations、logs 和 vocabulary SQL adapter，但仍缺少 `/api/vocabulary/me` 权限上下文、admin permissions wrapper、权限驱动 UI，以及 UniversalTable 的 vocabulary 权限适配。
- `/api/vocabulary/sql/*` 只能访问 `vocabulary_entries`，不应该也不能开放 `vocabulary_locations`、`vocabulary_logs`、`vocabulary_permissions`。
- 普通公开展示应使用 `/api/vocabulary/search/*`。表格模式应使用 `/api/vocabulary/sql/*`，并且只给有 vocabulary 权限的登录用户使用。

## 1. 我理解的真实需求

### 1.1 产品目标

你真正要做的是一个“语保词表”功能。它不是原有 SQL 管理工具的简单复用，也不是语保 YuBao 旧数据展示的替代页，而是一个新的、可逐步扩展的词表数据系统。

第一阶段重点是数据进入系统和基础管理：

1. 用户可以上传一个地点的一份词表文件。
2. 上传时前端同时提交地点 JSON，后端把地点信息写入 `vocabulary_locations`。
3. 后端把词表核心四列写入 `vocabulary_entries`，并自动记录上传用户 `user_id`。
4. 同一用户上传同一个 `location_name` 时，语义是“整批替换”：先删除该用户该地点旧 entries，再插入新 entries。
5. 只有有权限的用户可以上传和编辑。
6. `edit` 用户只能管理自己的数据。
7. `manage` 用户可以管理整张 entries 表和所有地点信息。
8. 项目原有 `admin` 是最高权限，即使没有 vocabulary permission 行，也必须被视为 vocabulary `manage`。
9. 所有编辑操作都写操作级日志，只有 manage/admin 可以查看日志。
10. 权限表由项目 admin 通过后台管理接口维护。

### 1.2 权限目标

Vocabulary 自己只有两级权限：

| 权限 | 能力 |
| --- | --- |
| `edit` | 可以上传词表；可以读取、编辑自己的 `vocabulary_entries`；可以读取、编辑自己的 `vocabulary_locations`。 |
| `manage` | 可以上传词表；可以管理所有 `vocabulary_entries`；可以读取、编辑所有 `vocabulary_locations`；可以查看 logs。 |

项目 `admin` 不受 vocabulary permission 行限制，后端直接当作 `manage`。

需要特别区分：

- 项目登录用户不等于 vocabulary 有权限用户。
- 项目 `admin` 高于 vocabulary `manage`。
- `/api/vocabulary/admin/permissions*` 只能项目 admin 使用，不是 vocabulary `manage` 使用。
- `/api/vocabulary/search/*` 是公开展示接口，不涉及编辑权限。
- `/api/vocabulary/sql/*` 是表格编辑接口，需要登录且有 vocabulary 权限。

### 1.3 前端信息架构目标

当前前端分成 `view`、`import`、`manage` 三块是合理的，但每块职责需要更清晰：

| 页面 | 应该负责什么 | 不应该负责什么 |
| --- | --- | --- |
| `view` | 公开搜索展示：卡片、地图、公开地点筛选。对有权限用户可额外进入表格模式。 | 不负责上传，不负责地点元数据编辑，不负责日志，不负责权限管理。 |
| `import` | 有权限用户上传词表，先后端 preview，再用户确认，再正式 import。 | 不负责自行决定最终解析结果，不应该绕过后端 preview。 |
| `manage` | `edit` 用户管理自己的地点信息；`manage/admin` 管理所有地点信息并查看 logs。 | 不通过 SQL API 管理 locations/logs，不开放 permissions 管理。 |
| dedicated admin UI | 项目 admin 管理 `vocabulary_permissions`。 | 不放在普通 vocabulary manage 页面里，避免混淆 vocabulary manage 和项目 admin。 |

## 2. 后端当前真实实现

### 2.1 数据库与表

后端使用独立数据库：

```text
data/vocabulary.db
```

当前表：

```text
vocabulary_entries
vocabulary_locations
vocabulary_permissions
vocabulary_logs
```

#### `vocabulary_entries` 真实字段

这是前端最容易弄错的地方。真实字段如下：

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

业务含义和字段对应：

| 业务含义 | 后端真实字段 | 是否核心字段 |
| --- | --- | --- |
| 释义、书面词条、书面提示词 | `standard_word` | 是 |
| 当地讲法、方言对应文字 | `local_expression` | 是 |
| IPA | `ipa` | 是 |
| 注释、备注 | `notes` | 是 |
| 地点简称 | `location_name` | 是，上传时来自地点 JSON |
| 上传用户 | `user_id` | 是，由 JWT 当前用户自动填入 |
| 预留信息 | `informations` | 预留 |
| 来源文件名 | `source_filename` | 辅助 |

`written` 不是数据库字段。`当地讲法` 也不是数据库字段。它们只可能作为导入表格的表头别名。

#### `vocabulary_locations` 真实字段

```text
id
user_id
location_name
coordinates
province
city
county
town
administrative_village
natural_village
yindian_region
atlas_region
```

注意：

- `id` 存在于数据库，但当前 location 列表响应不暴露 `id`。
- 前端编辑 location 时用路径参数 `location_name` 定位。
- `location_name` 不允许通过 PATCH 修改。
- 当 manage/admin 遇到多个用户有同名 `location_name` 时，PATCH 必须带 `user_id` 来消歧。
- `raw_location_json` 已经不应该存在，也不应该被前端依赖。

#### `vocabulary_permissions`

```text
id
user_id
permission_level
```

`permission_level` 只能是：

```text
edit
manage
```

#### `vocabulary_logs`

日志是操作级日志，不是逐行日志。一轮上传、一轮批量编辑、一轮批量替换，通常写一条 log。

核心字段：

```text
id
operation_id
user_id
permission_level
source
action
table_name
target_scope
affected_rows
status
payload_json
created_at
```

前端展示日志时应把它理解为“审计记录”，不是回滚系统。虽然部分 payload 里有 `rollback_supported`，当前后端没有实现 rollback API。

### 2.2 后端 API 分组

#### 当前用户 vocabulary 上下文

```http
GET /api/vocabulary/me
```

需要登录。返回：

```json
{
  "user_id": 7,
  "permission_level": "edit",
  "can_upload": true,
  "can_manage_entries": false,
  "can_view_logs": false
}
```

项目 admin 返回：

```json
{
  "user_id": 1,
  "permission_level": "manage",
  "can_upload": true,
  "can_manage_entries": true,
  "can_view_logs": true
}
```

登录但没有 vocabulary 权限的普通用户返回：

```json
{
  "user_id": 12,
  "permission_level": null,
  "can_upload": false,
  "can_manage_entries": false,
  "can_view_logs": false
}
```

前端应该把这个接口作为 vocabulary 权限 UI 的唯一来源。

#### 公开搜索展示

这组三个接口公开可读：

```http
GET /api/vocabulary/search/entries
GET /api/vocabulary/search/map-points
GET /api/vocabulary/search/location-options
```

它们用于普通前台展示，不用于编辑。

`search_fields` 使用语义字段，不使用数据库字段：

| search field | 实际搜索后端列 |
| --- | --- |
| `definition` | `standard_word` |
| `headword` | `local_expression` |
| `pronunciation` | `ipa` |
| `detail` | `notes`, `informations` |
| `location` | `location_name` 和地点元数据 |
| `all` | 当前等同默认内容字段，不包含 `location` |

#### 导入

```http
POST /api/vocabulary/imports/preview
POST /api/vocabulary/imports
```

请求类型是 `multipart/form-data`：

| form 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file` | file | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.docx`, `.doc` |
| `location` | string | JSON 字符串 |
| `parser_mode` | string | `auto`, `table`, `doc_whitespace`, `doc_bracket` |

`location` JSON 至少需要：

```json
{
  "location_name": "息烽",
  "coordinates": "106.7400,27.0900"
}
```

正式导入语义：

1. 校验当前用户是否有 `edit`、`manage` 或项目 admin 权限。
2. 解析 location JSON。
3. 解析文件。
4. upsert `vocabulary_locations` 的 `(user_id, location_name)`。
5. 删除当前用户同一 `location_name` 的旧 entries。
6. 插入新 entries。
7. 写一条 `vocabulary_logs`。

preview 不写 locations、不删 entries、不插 entries、不写 logs。

#### 地点元数据

```http
GET /api/vocabulary/locations
PATCH /api/vocabulary/locations/{location_name}
```

需要登录并有 vocabulary 权限。

`edit` 用户：

- GET 只能看到自己的 locations。
- PATCH 只能改自己的 locations。
- 如果传了 `user_id` 且不是自己，后端返回 403。

`manage/admin` 用户：

- GET 可以看所有 locations。
- 可以用 `user_id` 和 `location_name` 筛选。
- PATCH 同名地点属于多个用户时必须传 `user_id`。

PATCH 请求体允许字段：

```json
{
  "coordinates": "106.7400,27.0900",
  "province": "贵州省",
  "city": "贵阳市",
  "county": "息烽县",
  "town": "",
  "administrative_village": "",
  "natural_village": "",
  "yindian_region": "",
  "atlas_region": ""
}
```

不允许传 `location_name`。

#### 日志

```http
GET /api/vocabulary/logs
```

只有 `manage/admin` 可用。

支持查询参数：

```text
user_id
permission_level
source
action
table_name
status
page
page_size
```

#### Admin permissions

```http
GET /api/vocabulary/admin/permissions
GET /api/vocabulary/admin/permissions/{user_id}
PUT /api/vocabulary/admin/permissions/{user_id}
```

仅项目 admin 可用。不是 vocabulary `manage` 权限。

PUT 请求体：

```json
{
  "permission_level": "edit"
}
```

或：

```json
{
  "permission_level": "manage"
}
```

#### 表格 SQL API

```http
/api/vocabulary/sql/*
```

核心边界：

- 不需要 `db_key`。
- 固定访问 `data/vocabulary.db`。
- 只允许访问 `vocabulary_entries`。
- 不开放 `vocabulary_locations`。
- 不开放 `vocabulary_logs`。
- 不开放 `vocabulary_permissions`。
- 所有接口都需要登录且有 vocabulary 权限。
- `edit` 用户后端自动加 `user_id = current_user.id` 作用域。
- `manage/admin` 可以作用于所有 entries。

前端表格模式必须用真实列名：

```text
standard_word
local_expression
ipa
notes
informations
location_name
source_filename
id
user_id
```

写入时后端禁止改：

```text
id
user_id
location_name
```

当前后端已经禁止通过 SQL API 修改 `location_name`。`source_filename` 仍可被修改，但它主要是来源信息，前端建议只读或弱化显示。

## 3. 前端当前实现概览

本节基于当前前端源码的只读分析。

### 3.1 相关文件

前端 API wrapper：

```text
project/src/api/main/vocabulary.js
project/src/api/index.js
```

页面：

```text
project/src/main/views/explore/word/VocabularyPage.vue
project/src/main/views/explore/word/vocabulary/VocabularyViewPage.vue
project/src/main/views/explore/word/vocabulary/VocabularyImportPage.vue
project/src/main/views/explore/word/vocabulary/VocabularyManagePage.vue
```

表格组件：

```text
project/src/main/components/TableAndTree/UniversalTable.vue
```

路由：

```text
project/src/main/router/exploreRoutes.js
```

测试：

```text
project/tests/vocabularyApi.test.js
project/tests/vocabularyPageShell.test.js
```

### 3.2 前端已经对齐的部分

当前前端已经做对了不少关键点：

1. 公开搜索路径已经使用新路径：

```text
/api/vocabulary/search/entries
/api/vocabulary/search/map-points
/api/vocabulary/search/location-options
```

2. 导入路径已经使用新路径：

```text
/api/vocabulary/imports/preview
/api/vocabulary/imports
```

3. locations 和 logs 已有 wrapper：

```text
getVocabularyLocations
updateVocabularyLocation
getVocabularyLogs
```

4. 表格模式已经使用 `api-adapter="vocabulary"`，并走 `/api/vocabulary/sql/*`。

5. `vocabularySqlApi` 已经会剥离 `db_key`，并强制 `table_name = vocabulary_entries`。

6. View 页面已经分出 card/map/table：

- card 用 `getVocabularyItems`。
- map 用 `getVocabularyMapPoints`。
- table 用 `UniversalTable` + vocabulary adapter。

7. View 页面表格列已经使用真实后端字段：

```text
standard_word
local_expression
ipa
notes
location_name
informations
source_filename
```

8. Import 页面已经提交 location JSON、file、parser_mode。

9. Manage 页面已经使用专用 locations 接口，而不是 SQL API 管理 locations。

10. Manage 页面已经可以读取 logs，并按 `payload_json` 做基础摘要。

11. 前端测试已经覆盖了一部分路径契约，尤其是“不再使用旧 compatibility paths”和“vocabulary SQL adapter 不带 db_key”。

这些方向都应该保留，不需要推倒重来。

## 4. 当前前后端差异与风险

### 4.1 缺少 `/api/vocabulary/me` wrapper 和调用

后端已经实现：

```http
GET /api/vocabulary/me
```

但前端当前没有：

```js
getVocabularyMe()
```

也没有在 `VocabularyPage.vue`、`VocabularyImportPage.vue`、`VocabularyManagePage.vue` 或 `VocabularyViewPage.vue` 中调用它。

直接后果：

- 前端不知道当前用户是否可以上传。
- 前端不知道当前用户是 `edit` 还是 `manage`。
- 前端不知道是否可以查看 logs。
- `import`、`manage`、`table` 入口无法按权限正确显示或禁用。
- 没权限用户会点击后由后端返回 401/403，体验比较硬。
- `edit` 用户、`manage` 非 admin 用户和项目 admin 的 UI 差异无法体现。

建议：

在 `project/src/api/main/vocabulary.js` 增加：

```js
export async function getVocabularyMe() {
  return api('/api/vocabulary/me')
}
```

并从 `project/src/api/index.js` 导出。

建议前端内部统一为：

```js
{
  user_id,
  permission_level,
  can_upload,
  can_manage_entries,
  can_view_logs
}
```

不要自己推断 vocabulary 权限，不要只看 `userStore.role`，因为 vocabulary 权限和项目角色是两套概念。

### 4.2 页面 tab 没有按 vocabulary 权限分层

当前 `VocabularyPage.vue` 固定展示：

```text
view
import
manage
```

问题：

- 未登录用户也会看到 import/manage 入口。
- 登录但没有 vocabulary 权限的普通用户也会看到 import/manage。
- `edit` 用户可以管理自己的 locations，但不能看 logs；manage 页面当前混合了 locations 和 logs。
- `manage/admin` 才应该看到 logs。

建议：

`VocabularyPage.vue` 进入时加载 `/api/vocabulary/me`，或者使用一个 vocabulary permission composable。

tab 展示建议：

| 用户状态 | view | import | manage |
| --- | --- | --- | --- |
| 未登录 | 显示 | 隐藏或显示登录提示 | 隐藏或显示登录提示 |
| 登录无 vocabulary 权限 | 显示 | 隐藏或禁用 | 隐藏或禁用 |
| `edit` | 显示 | 显示 | 显示，但只管理自己的 locations，不显示 logs |
| `manage/admin` | 显示 | 显示 | 显示 locations + logs |

如果为了让用户知道“需要权限才能上传”，也可以显示 disabled tab，但点击后提示需要联系管理员开通 vocabulary 权限。

### 4.3 UniversalTable 仍然只认项目 admin，阻塞 vocabulary edit/manage

当前 `UniversalTable.vue` 多处使用：

```js
userStore.role === 'admin'
```

以及：

```js
const checkAdminPermission = () => {
  if (userStore.role !== 'admin') {
    showWarning(...)
    return false
  }
  return true
}
```

这和后端 vocabulary 权限模型不一致。

后端允许：

- `edit` 用户编辑自己的 `vocabulary_entries`。
- `manage` 用户编辑所有 `vocabulary_entries`。
- 项目 admin 编辑所有 `vocabulary_entries`。

但当前前端：

- 项目 admin 才能看到编辑按钮。
- vocabulary `edit` 用户即使后端允许，也无法通过 UI 编辑。
- vocabulary `manage` 用户如果不是项目 admin，也无法通过 UI 编辑。

建议最小改法：

给 `UniversalTable` 增加一个明确 prop，例如：

```vue
<UniversalTable
  api-adapter="vocabulary"
  :can-edit="vocabularyMe.can_upload"
/>
```

或更准确：

```vue
<UniversalTable
  api-adapter="vocabulary"
  :can-edit="Boolean(vocabularyMe.permission_level)"
/>
```

然后把模板里的：

```vue
v-if="userStore.role === 'admin'"
```

改成一个 computed：

```js
const canUseTableActions = computed(() => {
  if (props.apiAdapter === 'vocabulary') {
    return props.canEdit === true
  }
  return userStore.role === 'admin'
})
```

非 vocabulary 的旧 SQL/admin 表格行为保持原样。

注意：

- 前端只负责显示能力，不负责安全。
- 真正的 row-level 限制仍由后端 `/api/vocabulary/sql/*` 执行。
- `edit` 用户即使前端传了别人的 id，后端也会因为 `user_id = current_user.id` 作用域更新不到。

### 4.4 表格模式是否应该公开，需要重新定边界

`view` 页面现在有三种模式：

```text
table
card
map
```

但后端的公开展示接口只有 card/map 这类搜索接口。`table` 当前走 `/api/vocabulary/sql/*`，它需要登录和 vocabulary 权限。

因此第一版建议：

- 未登录和无权限用户：只显示 card/map。
- 有 `edit/manage/admin` 权限用户：显示 table。
- table 文案应偏“表格管理/编辑”，不要让公开用户以为它是普通展示模式。

如果未来需要公开表格展示，建议新增公开 search table 接口，或让 card/list 支持表格布局，但不要把 `/api/vocabulary/sql/*` 做成公开读接口。

### 4.5 Import 页面本地预览 schema 与后端真实字段不一致

当前 `VocabularyImportPage.vue` 的本地预览 schema key 是：

```text
definition
headword
pronunciation
detail
```

aliases 包括：

```text
释义, definition, gloss
词条, 方言词, headword, word
发音, pronunciation, ipa
详情, detail, description
```

后端真实 parser 目标字段是：

```text
standard_word
local_expression
ipa
notes
```

后端表头 aliases 是：

| 后端目标字段 | 支持表头 |
| --- | --- |
| `standard_word` | `standard_word`, `written`, `释义`, `釋義`, `书面`, `書面`, `书面词条`, `書面詞條`, `词条`, `詞條`, `meaning` |
| `local_expression` | `local_expression`, `vocabulary`, `当地讲法`, `當地講法`, `方言词`, `方言詞`, `方言讲法`, `方言講法`, `local` |
| `ipa` | `ipa`, `IPA`, `音标`, `音標`, `国际音标`, `國際音標` |
| `notes` | `notes`, `note`, `注释`, `註釋`, `备注`, `備註`, `说明`, `說明` |

风险：

- 后端能导入的文件，前端本地预览可能显示映射不完整。
- 前端本地预览显示的字段名和后端实际字段名不一致，容易继续误导为 `definition/headword` 是后端字段。
- `written`、`vocabulary`、`local_expression`、`standard_word`、`notes` 这几个关键别名当前本地预览支持不完整。

建议：

第一版最小优化：

- 本地预览 schema key 改为后端真实字段：

```text
standard_word
local_expression
ipa
notes
```

- label 仍然可以显示中文：

```text
释义
当地讲法
IPA
注释
```

- aliases 完全对齐后端 `_COLUMN_ALIASES`。

如果不想改 UI 内部 schema，也至少要让本地预览 aliases 覆盖后端所有别名，并在提交给后端时不要做字段重写。当前正式上传是传原文件给后端，所以后端最终解析不依赖本地预览 mapping；但用户看到的预览必须避免误判。

### 4.6 Import 页面没有把后端 preview 作为真正的确认步骤展示

当前流程大致是：

1. 用户选择文件。
2. 表格文件做前端本地 preview。
3. 用户点击提交。
4. 前端调用后端 preview。
5. 如果 preview success，马上调用正式 import。

这少了一个关键确认点。

后端 preview 返回：

```json
{
  "success": true,
  "location_name": "息烽",
  "permission_level": "edit",
  "parsed_count": 120,
  "would_delete_existing_count": 120,
  "skipped_count": 0,
  "errors": [],
  "parser_mode": "table"
}
```

这个响应里最重要的是：

```text
would_delete_existing_count
```

因为正式导入会替换同一用户同一 `location_name` 下整批 entries。

建议流程：

1. 用户选择文件，填写 location。
2. 点击“预览导入”。
3. 前端调用 `/api/vocabulary/imports/preview`。
4. 展示后端 preview：

```text
地点：息烽
解析模式：table
将导入：120 条
将跳过空行：0 条
将替换旧数据：120 条
```

5. 如果 `would_delete_existing_count > 0`，明确提示“正式导入会先删除当前用户该地点的旧词条，再写入新词条”。
6. 用户二次确认后，才调用 `/api/vocabulary/imports`。

这样能减少误操作，尤其是同一简称重复上传的场景。

### 4.7 Import 页面对 doc/docx 的体验还比较薄

后端支持三类导入：

1. 表格：`.xlsx`, `.xls`, `.csv`, `.tsv`
2. doc/docx 空白分隔：`doc_whitespace`
3. doc/docx 括号识别：`doc_bracket`

前端当前允许选择 doc/docx，也允许选择 parser mode，但 doc/docx 没有前端本地 preview。

这可以接受，因为 doc/docx 应以后端 preview 为准。

建议：

- 对 doc/docx 文件，前端可以跳过本地表格映射预览。
- 但必须展示后端 preview 结果。
- parser mode 选项文案要清楚：

```text
自动识别
表格四列
文档空白分隔
文档括号识别
```

括号识别规则建议在上传页附近简短说明或通过帮助弹窗展示：

```text
括号外文本 -> standard_word
[] -> ipa
{} -> notes
() 或 （） -> local_expression
```

不要把这段说明写成“数据库字段是括号外文本”，它只是 parser 规则。

### 4.8 Manage 页面把 locations 和 logs 放在一起，但没有权限分流

后端权限：

- `edit` 可以 GET/PATCH 自己的 locations。
- `edit` 不可以 GET logs。
- `manage/admin` 可以 GET/PATCH 所有 locations，也可以 GET logs。

当前 Manage 页面 onMounted 同时调用：

```js
loadVocabularyLocations()
loadVocabularyLogs()
```

问题：

- `edit` 用户进入 manage 页面，locations 可以成功，但 logs 会 403。
- 用户会看到一个错误模块，像是功能坏了。

建议：

基于 `/api/vocabulary/me`：

```js
if (me.permission_level) {
  loadVocabularyLocations()
}

if (me.can_view_logs) {
  loadVocabularyLogs()
}
```

UI：

- `edit`：只显示“地点信息管理”。
- `manage/admin`：显示“地点信息管理”和“操作日志”。
- 无权限：提示无 vocabulary 管理权限，或隐藏整个 manage 入口。

### 4.9 Manage 页面 locations 只加载第一页 200 条

当前：

```js
getVocabularyLocations({ page: 1, page_size: 200 })
```

第一版可用，但会有扩展问题：

- manage/admin 用户 locations 多了以后只能看到前 200 条。
- 没有分页。
- 没有按 `user_id`、`location_name` 搜索。

建议分阶段：

第一阶段：

- 保留 200 条，但显示 total。
- 如果 `total > 200`，显示“还有更多地点，请使用筛选或分页”。

第二阶段：

- 增加分页。
- 增加 `location_name` 搜索。
- manage/admin 增加 `user_id` 搜索或筛选。

### 4.10 Logs 页面没有权限过滤 UI 和分页

当前 logs wrapper 支持查询参数，但页面只拉：

```js
getVocabularyLogs({ page: 1, page_size: 50 })
```

建议：

第一阶段：

- 只在 `can_view_logs` 时展示 logs。
- 显示 total。
- 保留刷新按钮。

第二阶段：

- 增加筛选：

```text
user_id
source
action
table_name
status
permission_level
```

- 增加分页。
- 对 `payload_json` 做折叠详情。

注意：

- 当前没有 rollback API，前端不应该出现“执行回滚”按钮。
- `rollback_supported` 可以展示为“日志包含恢复参考”或“可参考日志人工恢复”，不要让用户以为一键回滚已实现。

### 4.11 Admin permissions 接口还没有前端 wrapper

后端已经实现项目 admin 专用权限管理：

```http
GET /api/vocabulary/admin/permissions
GET /api/vocabulary/admin/permissions/{user_id}
PUT /api/vocabulary/admin/permissions/{user_id}
```

当前前端没有 wrapper。

你已经明确说这组接口会放在专门后台管理里。因此普通 vocabulary 页面不需要加权限管理 UI，但前端 admin 模块需要接入。

建议在 `project/src/api/main/vocabulary.js` 或后台管理专用 api 文件中增加：

```js
export async function getVocabularyPermissions(params = {}) {
  return api(`/api/vocabulary/admin/permissions${appendQueryParams(params)}`)
}

export async function getVocabularyPermission(userId) {
  return api(`/api/vocabulary/admin/permissions/${encodeURIComponent(userId)}`)
}

export async function setVocabularyPermission(userId, permissionLevel) {
  return api(`/api/vocabulary/admin/permissions/${encodeURIComponent(userId)}`, {
    method: 'PUT',
    body: { permission_level: permissionLevel },
  })
}
```

后台页面使用方式：

1. 打开权限管理页：

```http
GET /api/vocabulary/admin/permissions?page=1&page_size=50
```

用于展示现有权限列表。

2. 用户搜索或输入 user id：

```http
GET /api/vocabulary/admin/permissions/{user_id}
```

如果返回：

```json
{
  "user_id": 12,
  "permission_level": null
}
```

说明这个用户当前没有 vocabulary 权限。

3. 选择权限并保存：

```http
PUT /api/vocabulary/admin/permissions/{user_id}
Content-Type: application/json

{
  "permission_level": "edit"
}
```

或：

```json
{
  "permission_level": "manage"
}
```

保存成功后刷新列表或局部更新。

重要：

- 这组接口只允许项目 admin。
- vocabulary `manage` 用户如果不是项目 admin，不应看到后台权限管理入口。

### 4.12 UniversalTable 批量替换 payload 与后端 schema 仍有不一致

后端 `BatchReplacePreviewParams` 和 `BatchReplaceExecuteParams` 使用 `extra="forbid"`。

允许字段：

```text
table_name
columns
find_text
match_mode
is_empty_search
filters
search_text
search_columns
replace_text    // execute only
```

当前 `UniversalTable.vue` 在全表 execute payload 里带了：

```js
pk_column: primaryKeyField.value
```

这会导致后端 422，因为 batch replace execute 不接受 `pk_column`。

建议：

- 对 `batchReplacePreview` 和 `batchReplaceExecute`，前端不要传 `pk_column`。
- 或者在 `vocabularySqlApi.batchReplacePreview/Execute` adapter 内移除 `pk_column`。

更推荐 adapter 兜底移除，因为 UniversalTable 是复用组件，旧通用 SQL API 可能仍需要原有行为。

示例：

```js
function stripVocabularyBatchReplaceParams(params = {}) {
  const { db_key: _dbKey, pk_column: _pkColumn, ...rest } = params
  assertVocabularyEntriesTable(rest)
  return {
    ...rest,
    table_name: VOCABULARY_ENTRIES_TABLE,
  }
}
```

同时，当前全表 batch replace preview/execute 传了：

```js
search_text: searchText.value
```

但没有传：

```js
search_columns: props.columns.map(c => c.key)
```

后端只有在 `search_text` 和 `search_columns` 同时存在时，才会把搜索条件加进 where。

风险：

- 用户以为“在当前搜索结果中全表替换”。
- 实际后端可能只尊重 filters 和替换条件，不尊重全局搜索框。

建议：

在 `previewAllPagesReplace` 和 `executeAllPagesReplace` payload 中补：

```js
const searchCols = props.columns.map(c => c.key)

search_columns: searchCols
```

### 4.13 前端测试没有覆盖 `/me`、admin permissions 和 batch replace schema

当前测试已经覆盖：

- 新 search/import 路径。
- 不使用旧路径。
- SQL adapter 不带 `db_key`。
- SQL adapter 限定 `vocabulary_entries`。
- locations/logs wrapper 基础路径。

建议增加测试：

1. `getVocabularyMe()` 调用 `/api/vocabulary/me`。
2. admin permissions 三个 wrapper 路径和 body。
3. `vocabularySqlApi.batchReplaceExecute` 对 vocabulary adapter 移除 `pk_column`。
4. batch replace preview/execute payload 包含 `search_columns`。
5. `VocabularyPage.vue` 或 composable 调用 `/me` 并用返回值控制 tabs。
6. `UniversalTable` 在 `api-adapter="vocabulary"` 时不再只依赖 `userStore.role === 'admin'`。
7. `VocabularyManagePage` 在 `can_view_logs=false` 时不调用 logs。
8. import 页展示后端 preview 的 `would_delete_existing_count`。

### 4.14 旧字段名和新字段名仍需要在前端概念上彻底分清

前端 UI 可以显示中文：

```text
释义
当地讲法
IPA
注释
```

但代码中的 API 字段应该坚持：

```text
standard_word
local_expression
ipa
notes
```

建议前端内部采用两层命名：

1. API/表格层：使用后端真实字段。
2. UI 展示层：可映射成 `definition/headword/pronunciation/detail` 这类更适合展示的字段。

例如：

```js
function normalizeVocabularyEntry(item) {
  return {
    id: item.id,
    definition: item.standard_word || '',
    headword: item.local_expression || '',
    pronunciation: item.ipa || '',
    detail: [item.notes, item.informations].filter(Boolean).join(' · '),
    locationName: item.location_name || '',
    location: item.location_label || item.location_name || '',
  }
}
```

这类 UI 映射是可以的，但不要把 `definition/headword` 再发回 `/api/vocabulary/sql/*`。

## 5. 前端推荐分阶段优化路线

### 阶段 A：权限上下文先接好

目标：让前端知道当前用户能做什么。

建议改动：

1. 增加 `getVocabularyMe()` wrapper。
2. 从 `api/index.js` 导出。
3. 在 vocabulary 页面入口或 composable 中加载。
4. 处理三种状态：

```text
loading
loaded
error or unauthenticated
```

5. 根据 `/me` 结果控制 tabs、按钮和子页面加载。

推荐新增 composable：

```text
project/src/composables/vocabulary/useVocabularyPermission.js
```

也可以先不抽 composable，直接放在 `VocabularyPage.vue`，等功能稳定后再抽。

最小状态结构：

```js
const vocabularyMe = ref(null)
const isLoadingVocabularyMe = ref(false)
const vocabularyMeError = ref('')

const canUploadVocabulary = computed(() => vocabularyMe.value?.can_upload === true)
const canViewVocabularyLogs = computed(() => vocabularyMe.value?.can_view_logs === true)
const hasVocabularyEditAccess = computed(() => Boolean(vocabularyMe.value?.permission_level))
```

### 阶段 B：修正 UniversalTable 的 vocabulary 权限

目标：让 `edit` 和 `manage` 非项目 admin 用户也能使用表格编辑能力。

建议：

1. 给 `UniversalTable` 增加 `canEdit` 或 `canUseActions` prop。
2. 对 vocabulary adapter 使用这个 prop。
3. 对普通 SQL/admin 表格继续使用 `userStore.role === 'admin'`。
4. 模板里统一改成 computed，不要到处判断 role。

示例：

```js
const canUseTableActions = computed(() => {
  if (props.apiAdapter === 'vocabulary') {
    return props.canEdit === true
  }
  return userStore.role === 'admin'
})
```

然后替换：

```vue
v-if="userStore.role === 'admin'"
```

为：

```vue
v-if="canUseTableActions"
```

并把：

```js
checkAdminPermission()
```

扩展为：

```js
checkTableActionPermission()
```

对 vocabulary 显示 vocabulary 权限提示，对旧表格仍显示 admin 提示。

### 阶段 C：修正 import preview 流程

目标：让“同简称替换旧数据”变成用户明确确认过的操作。

建议交互：

1. 文件选择后，前端可以做本地表格预览。
2. 用户点击“后端预览”或“下一步”。
3. 调 `/api/vocabulary/imports/preview`。
4. 展示：

```text
location_name
parser_mode
parsed_count
skipped_count
would_delete_existing_count
errors
```

5. `would_delete_existing_count > 0` 时展示强提示。
6. 用户确认后才调用 `/api/vocabulary/imports`。

按钮建议：

```text
选择文件
预览导入
确认导入
```

不要在同一个 click 里 preview 成功后马上 import。

### 阶段 D：修正 import 本地 schema 和别名

目标：让前端本地预览和后端 parser 对齐。

建议 schema：

```js
[
  {
    key: 'standard_word',
    label: '释义',
    required: true,
    aliases: ['standard_word', 'written', '释义', '釋義', '书面', '書面', '书面词条', '書面詞條', '词条', '詞條', 'meaning']
  },
  {
    key: 'local_expression',
    label: '当地讲法',
    required: true,
    aliases: ['local_expression', 'vocabulary', '当地讲法', '當地講法', '方言词', '方言詞', '方言讲法', '方言講法', 'local']
  },
  {
    key: 'ipa',
    label: 'IPA',
    required: true,
    aliases: ['ipa', 'IPA', '音标', '音標', '国际音标', '國際音標']
  },
  {
    key: 'notes',
    label: '注释',
    required: false,
    aliases: ['notes', 'note', '注释', '註釋', '备注', '備註', '说明', '說明']
  }
]
```

### 阶段 E：修正 batch replace payload

目标：避免 `/api/vocabulary/sql/batch-replace-execute` 422，并确保搜索范围正确。

建议：

1. vocabulary adapter 对 batch replace 移除 `pk_column`。
2. UniversalTable 全表 preview/execute 补 `search_columns`。
3. 增加测试覆盖。

### 阶段 F：Manage 页面按权限拆展示

目标：`edit` 用户看到自己的地点管理，`manage/admin` 看到地点管理和 logs。

建议：

```js
onMounted(async () => {
  await loadVocabularyMe()
  if (hasVocabularyEditAccess.value) {
    await loadVocabularyLocations()
  }
  if (canViewVocabularyLogs.value) {
    await loadVocabularyLogs()
  }
})
```

UI 分流：

| 权限 | Manage 页面 |
| --- | --- |
| 无权限 | 不进入，或显示无权限提示 |
| `edit` | 只显示自己的 locations 编辑 |
| `manage/admin` | 显示所有 locations 编辑和 logs |

### 阶段 G：接入后台 admin permissions

目标：项目 admin 能在后台管理里维护 vocabulary 权限。

建议 API wrapper：

```js
getVocabularyPermissions(params)
getVocabularyPermission(userId)
setVocabularyPermission(userId, permissionLevel)
```

后台页面流程：

1. 页面加载调用 `GET /api/vocabulary/admin/permissions`。
2. 输入 user id 时调用 `GET /api/vocabulary/admin/permissions/{user_id}`。
3. 选择 `edit` 或 `manage` 后调用 `PUT /api/vocabulary/admin/permissions/{user_id}`。

UI 注意：

- 只给项目 admin 显示。
- 不要给 vocabulary manage 用户显示。
- 如果后端返回 403，提示“需要管理员权限”。

### 阶段 H：完善列表、地图、日志体验

可以后续逐渐优化：

1. card 列表加入分页状态和 total 展示。
2. map detail modal 如果某地点超过 50 条，支持分页或加载更多。
3. location-options 支持更多筛选或服务端搜索。
4. logs 支持筛选、分页、payload 展开。
5. locations 支持分页、按 user_id/location_name 筛选。
6. table 模式中把 `id`、`user_id`、`location_name`、`source_filename` 设为只读或弱化显示。

## 6. 前端页面具体使用建议

### 6.1 `VocabularyPage.vue`

职责：

- 页面级 tab shell。
- 加载 vocabulary permission context。
- 控制 view/import/manage 的可见性。

建议：

- 保留当前 router-view 结构。
- 增加 `/me` 加载。
- provide 给子页面，或通过 props/composable 共享。

推荐规则：

```text
view 永远可见
import 仅 can_upload
manage 仅 permission_level != null
```

如果无权限但用户直接访问 `/explore/vocabulary/import`：

- 可以 redirect 到 `/explore/vocabulary/view`。
- 或显示“需要词表权限”的轻量提示。

### 6.2 `VocabularyViewPage.vue`

职责：

- 公开搜索展示。
- 有权限时提供表格模式。

建议：

- card/map 继续使用 `/api/vocabulary/search/*`。
- table 继续使用 `/api/vocabulary/sql/*`。
- table mode 只在用户有 vocabulary 权限时显示。
- table mode 进入时如果 `/me` 未加载，先加载或显示 loading。

搜索字段：

- 现在的 `definition/headword/pronunciation/detail` 是对的，因为这是 search API 的语义字段。
- 不要把这些字段用于 SQL 表格。

表格字段：

- 继续使用 `standard_word/local_expression/ipa/notes`。

### 6.3 `VocabularyImportPage.vue`

职责：

- 有权限用户上传。
- 严格以后端 preview 为准。

建议：

- 无 `can_upload` 时禁用或隐藏上传表单。
- 本地 preview 只作为辅助。
- 后端 preview 必须单独展示。
- 二次确认后再 import。
- 别名 schema 对齐后端。

错误处理：

| 状态 | 前端提示 |
| --- | --- |
| 401 | 请先登录 |
| 403 | 没有词表上传权限 |
| 400 | 显示后端 detail，例如缺少字段或解析失败 |
| 503 | 词表数据库正在写入，请稍后重试，可自动重试一次 |

### 6.4 `VocabularyManagePage.vue`

职责：

- `edit` 用户管理自己的 locations。
- `manage/admin` 管理全部 locations，并查看 logs。

建议：

- 进入页面先拿 `/me`。
- `permission_level == null` 不加载任何管理数据。
- `can_view_logs == false` 不调用 logs。
- locations 保存时保留当前 `user_id` 参数逻辑，因为 manage/admin 修改同名地点时需要 user_id 消歧。
- location_name 不要放到编辑字段里，当前做法是对的。

### 6.5 Dedicated Admin UI

职责：

- 项目 admin 管 vocabulary permissions。

建议：

- 这部分不要混进普通 `VocabularyManagePage.vue`。
- 放在已有后台管理入口。
- 使用 `GET/GET/PUT /api/vocabulary/admin/permissions*`。

## 7. 建议前端测试清单

### 7.1 API wrapper 测试

建议覆盖：

```text
getVocabularyMe -> /api/vocabulary/me
getVocabularyPermissions -> /api/vocabulary/admin/permissions?page=...
getVocabularyPermission -> /api/vocabulary/admin/permissions/{user_id}
setVocabularyPermission -> PUT body { permission_level }
batchReplaceExecute strips pk_column for vocabulary adapter
batchReplacePreview/Execute can carry search_columns
```

### 7.2 页面 shell 测试

建议覆盖：

```text
VocabularyPage loads /me
no permission: import/manage tab hidden or disabled
edit: import/manage visible, logs hidden
manage: import/manage visible, logs visible
```

### 7.3 Import 页面测试

建议覆盖：

```text
schema aliases include standard_word/written/vocabulary/local_expression/notes
click preview calls imports/preview only
preview success with would_delete_existing_count > 0 shows replacement warning
confirm import calls imports
preview failure does not call imports
docx file bypasses local table mapping but still calls backend preview
```

### 7.4 Manage 页面测试

建议覆盖：

```text
edit user loads locations but not logs
manage user loads locations and logs
location patch does not include location_name in body
manage saving duplicated location sends user_id
```

### 7.5 UniversalTable 测试

建议覆盖：

```text
normal SQL adapter still requires project admin for actions
vocabulary adapter uses canEdit prop for actions
vocabulary edit user can see edit buttons when canEdit=true
vocabulary adapter does not send db_key
vocabulary adapter never allows table_name other than vocabulary_entries
```

## 8. 后端边界现状

这份文档主要指导前端。下面这些边界已经由后端强制，前端仍应同步隐藏或弱化相关入口，避免用户点到无效操作。

### 8.1 edit 用户只能通过 SQL API 删除自己的单条 entry

后端 `/api/vocabulary/sql/mutate` 已允许 `edit` 用户执行单条 `delete`，但仍会自动加 `user_id = current_user.id` 作用域。`/batch-mutate` 的 `batch_delete` 仍对 `edit` 用户禁止。

当前语义：

- `edit` 用户可以上传、创建自己的 entries、更新自己的 entries、批量更新自己的 entries、批量替换自己的 entries。
- `edit` 用户可以删除自己的单条 entry。
- `edit` 用户删除别人的 entry 时不会命中数据，返回 `affected_rows = 0` 并记录日志。
- `edit` 用户批量删除 entries 会返回 `403`。
- `manage`/admin 可以删除任意 entries。
- 后端没有提供“按地点简称清空自己整批数据”的专用接口。

前端要求：

- edit 用户可以展示单行删除入口，但需要二次确认。
- edit 用户不要展示批量删除、清空选中、按地点清空等入口。
- manage/admin 可以展示删除入口，但仍建议二次确认。

### 8.2 entries 的 `location_name` 不允许表格编辑

后端已经禁止通过 SQL API update/batch_update/batch_replace 修改：

```text
id
user_id
location_name
```

`location_name` 仍允许在 create/batch_create 时填写，因为新建 entries 必须归属一个地点简称。

前端要求：

- 表格已有行的 `location_name` 显示为只读。
- 批量替换列选择器不要包含 `location_name`。
- 新建行时可以填写 `location_name`，但最好引导用户从已有 locations 中选择。

### 8.3 `source_filename` 是否允许编辑

当前后端允许修改 `source_filename`。这是来源信息，通常不需要用户编辑。

建议第一版前端只显示，不开放编辑。

## 9. 最小可交付前端改动顺序

如果要尽快把前端接稳，我建议按以下顺序做：

1. 增加 `/api/vocabulary/me` wrapper 和测试。
2. 在 vocabulary 页面加载 `/me`，按权限控制 tabs。
3. Manage 页面按 `can_view_logs` 决定是否加载 logs。
4. UniversalTable 增加 vocabulary 专用 `canEdit` 适配，让 `edit/manage` 非 admin 可编辑。
5. 修 batch replace 的 `pk_column` 和 `search_columns`。
6. Import 页面改成后端 preview -> 用户确认 -> import。
7. Import 本地 schema aliases 对齐后端。
8. Dedicated admin UI 接入 permissions 三个接口。
9. 增加 locations/logs 分页筛选。
10. 再考虑 entries 表格只读列、地图 detail 加载更多等体验优化。

其中 1-6 是第一优先级，因为它们影响权限正确性和真实数据写入安全。

## 10. 一句话给前端的实现原则

前端可以有自己的展示字段，但只要和后端交互，就必须遵守下面这条边界：

```text
公开展示用 /api/vocabulary/search/* 的语义参数；
上传文件表头可以是别名；
表格编辑和数据库字段永远使用 standard_word/local_expression/ipa/notes 等真实字段；
权限 UI 永远以 /api/vocabulary/me 为准；
admin permissions 永远只放后台项目 admin 页面。
```
