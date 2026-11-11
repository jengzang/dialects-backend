# 用户自定义数据安全保存：前端实施计划

> 执行方式：采用 executing-plans 按任务执行，先验证失败行为，再实现和验证；本文件仅为计划。后端接口、错误结构、限额和发布依赖以同目录 `2026-11-09-user-custom-data-backend.md` 为共同约定。

**Goal:** 用户页和地图使用稳定 ID，整批校验、单请求保存、保留失败草稿，并区分已失败与结果未知。

**Architecture:** 复用 Vue 3 页面、现有 API 客户端和 Vitest；抽取小型纯函数处理批次校验与地图差异，提取保存状态以便测试。每个表单同一时刻最多一个写请求，不为每行派发请求。

**Tech Stack:** Vue 3、JavaScript、vue-i18n、Vitest/jsdom、Vite。

**状态：** 2026-11-09 用户已批准实施，核心 A/B/C 已实现；验证结果与未执行的环境验收见 `../../user-custom-safety-verification-2026-11-09.md`。前端项目根目录为 `/Users/jengzang/CodeProject/dialects/dialects-vue-frontend/project`，下面文件均相对此目录。

## 1. 用户可见规则

1. 修改始终保留原记录身份和创建时间，不再删除后重建。
2. 任意已有行不完整，整批阻止提交，定位具体行和字段；仅可忽略完全未填写的新占位行。
3. 每次最多 50 个变更，不能偷偷拆成若干次请求后称整批原子保存。
4. 提交中禁止重复保存；用户不能修改已发送的请求快照。
5. 校验失败、服务端冲突或读取失败均保留草稿。只有确认保存成功后才能关闭编辑器或清空选择。
6. 网络超时/断开属于“结果未知”，不能直接显示“数据库未修改”，不能用新请求键重发新增。
7. 创建时间按设备本地时区展示；迁移到 ID 不改变既有显示策略。

## 2. 文件清单

| 文件 | 改动 |
| --- | --- |
| `src/api/main/user/custom-data.js` | 增加 batchUpdateCustomData、batchDeleteCustomDataById、saveCustomData；保留结构化错误 |
| `src/api/main/user/index.js`、`src/api/index.js` | 导出新 API，旧导出暂保留兼容 |
| 新建 `src/utils/user/customDataMutations.js` | 字段校验、50 条限额、ID 去重、地图差异和请求快照 |
| 新建 `src/main/composables/useCustomDataSave.js` | 保存锁、不可变请求、幂等键及结果未知状态 |
| `src/main/components/user/UserDataPage.vue` | 选择/键/编辑按 ID；原子更新；行错误和提交锁 |
| `src/main/components/map/custom/point/PointDetailForm.vue` | 服务端 ID 与临时行键分离，单请求 save，基础字段变化识别 |
| `src/main/components/map/custom/feature/FeatureDetailTable.vue` | 按 ID 删除，阶段 C 携带 version |
| `src/main/components/map/custom/feature/FeatureRecordEditorModal.vue` | 更新按 ID；阶段 B 创建走幂等 save |
| `src/i18n/locales/zh-CN/user.json`、`zh-Hant/user.json`、`en/user.json` | 行校验、数量、保存状态、冲突文案 |
| `src/i18n/locales/zh-CN/customEntry.json`、`zh-Hant/customEntry.json`、`en/customEntry.json` | 地图整批失败、结果未知、刷新失败、幂等窗口文案 |

不改动现有 httpClient 全局行为，优先在用户数据包装层保留错误和控制提示；若确需全局改动，另加既有认证/限流回归测试。

## 3. 阶段 A：用户页 ID 与原子更新

### F1. API 包装与可测试的校验

- [ ] 新建 `tests/customDataApi.test.js`，mock 现有 api，验证路径、请求体、ID 类型及错误原样传播。
- [ ] 新包装返回原响应；catch 中不再 `throw new Error(error.message)` 丢掉 status/detail/code。避免 API 包装和组件各弹一次错误；组件负责本流程提示。
- [ ] 新建 `tests/customDataMutations.test.js`，覆盖 1/50/51 条、重复 ID、空白字段、不完整已有行、完全空的新行、仅填写说明的新行、坐标与字段长度。
- [ ] 纯函数校验与后端字段规则一致，返回 `{ row_index, field, messageKey }` 数组，不用 filter 静默丢弃无效已有行。
- [ ] API 请求示例统一使用用户专用字段，不再要求前端提交 username/user_id；不发送创建时间作为身份。

API 函数约定：

```js
batchUpdateCustomData(items) // PUT /user/custom/batch-update，body: { items }
batchDeleteCustomDataById(ids) // DELETE /user/custom/batch-delete-by-id，body: { ids }
saveCustomData(snapshot) // POST /user/custom/save，阶段 B 接入
```

### F2. UserDataPage 全面迁移

- [ ] `selectedRecords` 改存数字 ID；列表 `:key`、选中判定、全选、批量编辑映射都使用 record.id。
- [ ] 批量编辑草稿保留 id；单条编辑复用 items 长度为 1 的 batchUpdateCustomData。仅构造允许编辑的字段，不把整条服务端对象直接当请求体。
- [ ] 删除 `submitBatchEdit` 的 batchDeleteCustomData → batchCreateCustomData 链路，替换成一次 batchUpdateCustomData。
- [ ] 对全部草稿校验而非 validBatchEditRows 筛选；首个错误滚动定位，确认框显示实际提交条数。
- [ ] 提交锁在任何 await（包括异步确认框）前获取，finally 释放；按钮 disabled 与函数入口检查双重保护。
- [ ] 保存期间锁定当前表单编辑和关闭，或阻止关闭并解释正在保存；请求快照与实时输入分离。
- [ ] 批量删除改用 ID API；严格失败时保留选择，成功后按服务端 deleted_ids 清理。
- [ ] 读取刷新后移除选择集合中已不存在的 ID，避免留下失效选择；读取失败不把草稿清空。
- [ ] 提交成功与随后 fetchData 失败分开提示；不能把刷新失败标成更新失败。

### F3. 阶段 A 行为测试与验收

- [ ] 新建 `tests/userDataMutations.test.js`，使用 Vue 自带 createApp 在 jsdom 挂载并 mock 路由、store、通知、API；无需为本任务新增组件测试依赖。确需复用逻辑时提取 composable，而非仅用源代码字符串断言。
- [ ] 验证 3 行中 1 行无效时没有任何写请求；合法编辑只有一次 batch-update，无删除和创建调用。
- [ ] 两条 created_at 相同但 ID 不同的行可独立选中、修改和删除。
- [ ] 双击保存/确认只触发一次写请求；422 后原输入仍在；404 后提示服务端状态变化。
- [ ] 前端限额挡住 51 条，全部三种语言显示对应提示；保存成功刷新失败不重复提交。
- [ ] 后端 A 阶段已上线才发布本阶段；新接口不存在时显示不可保存并保留草稿，不能回退到先删后建。

## 4. 阶段 B：地图和所有新增入口单请求保存

### F4. 地图稳定身份与差异

- [ ] 已有行使用 `recordId` 存服务端 id，另用 `clientRowId` 作 Vue 行键；新行只有 clientRowId，不把 `row-1` 字符串误传为记录 ID。
- [ ] 删除集合存 `{ id }`，移除未保存新行不产生服务端删除；恢复行时同步取消待删项，防止同一 ID 同时进入更新和删除。
- [ ] 加载时保留每行原始完整字段与地点、分区、坐标快照。rowChanged 必须识别地点或分区单独变化，不能只比较坐标和特征字段。
- [ ] 完全空白的新行可忽略；任何部分填写的新行或被清空必填值的已有行均报错，禁止静默跳过。
- [ ] 将差异构建为 creates、updates、deletes，一次 save；移除逐行编辑请求与 Promise.allSettled。
- [ ] 基础地点字段变化需要更新的已有行计入 50 个变更上限；超限不自动截断地点记录，也不偷偷拆请求。
- [ ] 成功后按 client_row_id → id 映射同步新增行身份，再更新列表和自定义数据存在状态；失败不清空删除集合及未保存草稿。
- [ ] 自动匹配地点和详情读取加入请求序号校验，只有当前地点的最新响应可覆盖表单；保存开始后不能让晚到读取替换请求快照。

### F5. 幂等保存状态

- [ ] useCustomDataSave 暴露 `idle/saving/succeeded/failed/unknown` 状态；每次新的保存意图生成一次 UUID，深复制请求体。
- [ ] 锁在首个 await 前设置，未知结果时重试使用同一 UUID 和同一请求体；不能把修改过的草稿与旧 UUID 一起发送。
- [ ] unknown 状态允许“重试确认此次保存”和“重新读取并核对”；重新读取保留原草稿作为对照，不把未知提交的新增行直接当作新草稿再次提交。
- [ ] 幂等键与请求快照至少在当前页面生命周期保留，路由离开前提示未确认结果。页面刷新导致键丢失时先重新读取并核对，不声称能自动恢复跨刷新重试。
- [ ] 后端回执有效期 24 小时；超期后禁止自动重发未知新增，要求重新读取核对。UI 不向用户暴露哈希或内部表名。
- [ ] 已确认成功后的列表刷新失败只提供重试读取，不提供重做写入。
- [ ] 用户页批量新增和特征编辑弹窗新增也迁移 save，使用相同状态规则，避免地图修复而其他入口仍重复新增。

### F6. 地图其他入口与测试

- [ ] FeatureDetailTable 单条删除调用严格 ID 删除；FeatureRecordEditorModal 已有记录编辑按 ID 更新。
- [ ] 新建 `tests/pointDetailMutations.test.js`，覆盖仅地点变化、仅分区变化、部分空行、删除全部旧行、移除新行、50/51 个变更、请求失败保留草稿。
- [ ] 新建 `tests/customDataSaveState.test.js`，覆盖双击、超时同键重试、重试内容保持不变、同键不同内容冲突、成功后刷新失败、晚到读取不覆盖当前表单。
- [ ] 集成模拟第一次响应丢失、第二次返回同回执，确认前端没有额外新增意图。
- [ ] 地图全成功后仅触发一次 saved，失败不触发；前端不继续展示“部分成功”作为新保存接口的正常结果。

## 5. 阶段 C：冲突与时间字段

### F7. 版本冲突

- [ ] 所有已有记录草稿保留 version，更新和删除携带预期版本；仅在全部后端写入者已支持版本后启用。
- [ ] 新删除请求变为 `{ items: [{ id, version }] }`；后端兼容已有阶段 A 的 ids 形式，但新网页只发送带版本形式。save.deletes 同样使用 `{ id, version }`。
- [ ] 409 version_conflict 提供当前服务端记录与本地草稿的字段对照。用户选择重新加载或手动合并；合并后基于最新版本发起新的保存意图，不自动覆盖。
- [ ] 不存在的目标与越权统一显示“记录已不可用”；不得通过提示透露其他用户记录归属。
- [ ] 版本改变后的新提交使用新 UUID；原未知请求的重放继续使用原 UUID 并由后端优先命中回执。
- [ ] 新建 `tests/customDataConflict.test.js`，验证冲突后保留草稿、删除冲突不清除选择、合并后携带新版本。

### F8. 时间展示

- [ ] 新建 `tests/customDataTime.test.js`，覆盖 Z、正负偏移、旧 naive、微秒、空值和无效输入；无效时间显示 `-`，不抛出 RangeError 破坏页面。
- [ ] 格式化优先 created_at_utc，兼容原 created_at；无时区旧值按接口约定补 UTC，避免给已有偏移再补 Z。
- [ ] 使用 Intl 按设备本地时区显示，测试显式控制时区以避免开发机差异。
- [ ] 检索页面与地图写请求，确认 created_at 仅用于展示，不再参与新协议的选择、编辑、删除和行差异身份判断。

## 6. 验证与发布

从前端项目根目录执行：

```bash
npm run test -- tests/customDataApi.test.js tests/customDataMutations.test.js tests/userDataMutations.test.js
npm run test -- tests/pointDetailMutations.test.js tests/customDataSaveState.test.js tests/customDataConflict.test.js tests/customDataTime.test.js
npm run test -- tests/customRegionTransport.test.js
npx vite build
```

每阶段只运行当时已创建的测试文件。预期：关键用例实现前失败、实现后通过，Vite 构建成功。直接调用 Vite 是为了避免计划验证时 `npm run build` 的 sitemap 生成步骤覆盖工作区已有的 sitemap 修改。若实际发布必须运行完整 build，先保存并核对既有差异，不擅自覆盖。

- [ ] 对上述改动 JS/Vue 文件运行现有 ESLint；全库已有失败单独记录，不能把新增错误归因于历史问题。
- [ ] 在隔离测试后端联调：创建 → 编辑 → 删除；多行无效；同时间不同 ID；缺失记录；额度到顶；网络断开；重复点击；并发冲突。
- [ ] 浏览器 Network 验证每个保存动作最多一个写请求；写请求不随行数增长成 50 条。
- [ ] 检查中文简体、繁体、英文及移动端按钮状态、行错误定位和长字段反馈，不改变已有布局风格。
- [ ] 前后端按 A → B → C 同步推进，每阶段先后端后网页；移动端或旧网页仍走旧协议的使用情况另行记录。
- [ ] 回退时保留安全编辑流程；服务不可用可暂时禁用写入，不回退到删除后创建。只回退前端不能移除后端仍在服务旧新版网页的新增接口。

## 7. 前端完成标准

- [ ] 用户页和地图所有新写操作以 ID 定位，选择不依赖时间字符串。
- [ ] 不完整的已有行不会被过滤掉后显示整批成功。
- [ ] 失败草稿保留，提交中不能重复发起，结果未知可安全核对。
- [ ] 地图保存和所有新网页新增入口使用幂等 save；无逐行并发写请求。
- [ ] 修改地点、分区、坐标均能正确识别并提交。
- [ ] 版本冲突不会自动覆盖，保存成功后的读取失败不会触发重复写入。
- [ ] 相关行为测试、构建与隔离联调通过，验证结果写入执行记录。
