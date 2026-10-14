# 自定义分区改造方案：后端

日期：2026-10-14。状态：需求细节已逐项确认，书面方案待审阅；当前仅设计，不实现。

配套方案：[前端](../../../../dialects-vue-frontend/docs/superpowers/specs/2026-10-14-custom-partitions-design.md)、[预处理](../../../../dialects-build/docs/superpowers/specs/2026-10-14-location-identity-design.md)。本文为新个人分区 API 与 supplements 数据结构的契约依据。

## 1. 当前实现与改造边界

`app/service/user/core/models.py` 的 UserRegion 在 supplements 库保存组名、用户、地点简称 JSON、描述和时间，唯一约束是 `(user_id, region_name)`。`app/service/user/submission/region.py` 及 `app/routes/user/custom_regions.py` 按名称增改删，未建立地点身份或层级约束；列表已返回全部地点。

直接扩大 JSON 字段或增加四个分区列无法覆盖八级、节点移动、同名子区、多归属与主归属。方案新增关系模型，保留旧数据用于预览与归档，不维护两套同时可编辑功能。

`app/routes/user/custom_data.py` 当前以 `簡稱 + 音典分區` 聚合 Information 行，以 `簡稱||音典分區` 生成 point_key；这不是永久点 ID。独立个人地点必须补充实体身份，公共资料补充必须明确引用公共地点。

当前 geo 服务、get_locs 和坐标服务以简称为主。新功能需在服务边界支持 location ref，再按实际来源适配现有查询，不能把公共点与同名个人点都转换成同一个简称。

2026-10-14 当前代码已有默认路径相关修改：`app/service/geo/partitions.py`、`app/routes/geo/get_partitions.py`、`app/service/geo/getloc_by_name_region.py` 和 `tests/test_partition_paths.py`。现有 `/api/partitions/resolve` 解析默认路径名称 / 完整路径，`scope=default_and_user` 指已有用户音典数据路径，并非新的个人节点。新方案不撤回这些修改，也不赋予原 scope 新含义。

本地配置 `app/common/path.py` 中 QUERY_DB_ADMIN / QUERY_DB_USER 当前都指向 `data/query_user.db`，DIALECTS 两套常量也指向 user 库。沿用配置；读实际身份元数据确定源，不以权限角色猜源，不顺带改部署配置。

## 2. 共享规则与解析定义

个人树属于用户，map / yindian 共用。每个地点可有多个成员关系，有成员时恰有一个主归属；首次加入自动主，后续新增保留原主。删除主归属仍有成员时必须显式选接替者，无成员则恢复默认。恢复默认清空该地点全部成员，保留节点。

节点父子结构最多 8 级，根为第一级；地点可直属父区，父选择包含直属及全部后代，按身份去重。选点包含全部个人成员，dot 着色只使用主归属。选中层级超过主路径深度时使用最深实际节点。

默认回退采用读取时计算：个人成员非空则使用个人结果；否则读取当前 `region_mode` 默认；无默认则为未分类。没有为全部点预建个人行，不存在个人“未修改默认快照”。官方新增点与默认改动自动进入未修改地点结果，个人节点不被官方更新改写。

保留原官方选择与官方绘图。新入口明确选择有效个人结果；个人视图中的继承默认节点只包含没有个人成员的地点。有效结果覆盖全部权限可见公共点与用户独立新增点，资料缺音韵或坐标不影响管理资格，查询 / 绘图分别判断能力。

## 3. 永久地点引用

统一引用格式：

| 类型 | `location_ref` | 身份权威 |
| --- | --- | --- |
| 公共资料 | `public:<dataset_id>:<location_id>` | 实际 query 库的身份表 |
| 独立个人点 | `private:<point_id>` | supplements 个人地点实体 |
| 公共资料补充 | 原公共引用 | Information 的公共身份绑定 |

所有 ID 为 UUID，dataset ID 持久且每个构建源独立，dataset version 随发布数据变化递增。user / admin 同名点不自动获得同一身份；跨源关联若未来需要，必须单独设计可验证映射。当前源不可用成员保留，不能自动套到另一源同名点。map / yindian 共用是相同地点引用的共享，不是两个数据库身份的强制统一。

公共引用无法跨 SQLite 建真实外键，服务端校验 query 元数据、当前有效身份、权限和发布版本；保存成员时不修改 query 表。个人引用校验 point owner，不能只信前端 ID。查询当前简称通过公共 ID 映射，历史简称仅用于迁移候选，不直接替代权限校验。

无数据源身份元数据时 capability 不开启新体系，保持旧接口；缺表不能临时由后端随机生成公共 ID。实际数据库发布需携带身份表及历史，不能只更新 dialects 表。

## 4. supplements 数据模型

以下为拟新增表及约束，不直接运行在当前库。用户 ID 来自 auth 库，不能声明不可执行的跨库 FK。

| 表 | 关键字段与约束 |
| --- | --- |
| `personal_partition_state` | user_id PK、revision、activation_state（legacy / active）、activated_at、migration_snapshot_id |
| `personal_partition_node` | `(user_id, node_id)` PK、parent_id 可空、label、description、sort_order、created_at、updated_at；父引用 `(user_id,parent_id)` 本表复合 FK |
| `personal_partition_membership` | `(user_id, location_ref, node_id)` PK、is_primary 0/1、created_at；复合 FK 至自己的节点 |
| `personal_partition_migration_snapshot` | snapshot_id、user_id、legacy_digest、dataset_id、dataset_version、原组及原成员 JSON、处理记录、时间 |
| `personal_partition_pending_member` | user_id、snapshot_id、旧组 / 原成员 / 原因 / 候选 / 用户处理记录；保留用户明确暂存的迁移未决材料 |
| `user_location` | point_id PK、user_id、display_name、默认 yindian 路径、可选坐标、deleted_at、created_at、updated_at |
| `information_location_binding` | information_id PK、本地 Information FK、location_ref；每条旧 / 新音韵记录至多绑定一个地点身份 |

节点名称作为显示属性，不作为 CRUD 主键。节点 UUID 由客户端草稿生成，后端校验格式、所有权和碰撞；已有节点不能通过跨用户 ID 被引用或替换。根及同一父节点下 label 唯一，不同父下同名允许。SQLite 对 NULL 的 UNIQUE 行为需显式处理：使用 `COALESCE(parent_id, '')` 表达式唯一索引，ID 禁止空串。标签 trim 后非空，保留内部文字、大小写、繁简与横杠；不把 labels 串接后再拆成层级。

成员表的关键索引：`(user_id,node_id)` 用于反向选点；按 `(user_id,location_ref)` 查询；部分唯一索引 `UNIQUE(user_id,location_ref) WHERE is_primary=1` 保证最多一个主。CHECK 约束限制 is_primary。服务端保证有成员时至少一个主；SQLite 部分索引不能单独保证“至少一个”。切换主时先清原主再设新主，在同一事务中完成。

节点 parent FK 不使用自动级联删除；成员 FK 也不靠级联绕过用户处理。先验证删除后的最终图和成员，再按依赖顺序写入。开启并验证 SQLite foreign_keys。建模迁移使用当前 `app/service/user/core/database.py` 与启动迁移机制，不在请求中隐式建表。

直属父区与其子区同时成为同一点的两个成员允许；同节点重复成员禁止。父选择去重，主归属为用户明确选中的那个节点，不自动提升为最深成员。

个人实体改名 / 修改默认路径不改变 point ID。删除实体保留墓碑及已有引用，归属不静默转给同名公共点；待用户解除 / 迁移后，清理策略再单独实施。公共退休身份同样保留成员，读取时分类为 unavailable，不参与可查询 / 可绘图结果。

## 5. 公共补充与个人新增的写入适配

新提交明确传 `location_ref`，或传“新增独立点”请求创建 user_location；同名不阻止独立新增。给公共点补充时沿用公共 ref，只写自己的 Information 及绑定，不改变公共资料身份或别人记录。

保留现有 Information 中简称、路径等字符串字段以兼容原业务，身份绑定成为新链路选择依据；字符串变更不重新生成 point ID。公共资料当前名可能变化，读取按映射呈现，不强制批量改写用户原提交文本。

迁移旧 Information 时按用户和旧聚合完整证据生成预览：明确属于同一旧个人点的多特征记录绑定同一个 point ID；与公共点同名 / 同路径但身份意图不明确的，让用户选择公共补充或独立新增。不能通过 `min(經緯度)` 掩盖一组记录的冲突，同一组坐标 / 来源冲突也要出现在预览。

实现时全局检索 Information 所有新增、编辑、删除、管理、批量导入路径，包括 `app/service/user/submission/submit.py`、`delete.py`、`app/routes/user/form_submit.py`、`custom_data.py`，以及本次搜索确认的 `app/service/admin/submissions/management.py`、`app/routes/admin/submissions/data.py`。旧客户端缺 ref 的写入只能在唯一已绑定目标时适配；有多个候选明确拒绝并要求升级，不能按简称覆盖多个个人点。

## 6. 新 API 契约（contract_version = 1）

新路由独立命名 `/api/personal_partitions`，旧 `/api/custom_regions` 与默认 `/api/partitions/*` 保持原含义。包括 context 在内的新个人功能都需要登录，未登录返回 401，不以空树伪装成功。

### 6.1 上下文、快照与地点列表

GET `/api/personal_partitions/context`：

```json
{
  "contract_version": 1,
  "enabled": true,
  "dataset_id": "UUID",
  "dataset_version": 12,
  "revision": 6,
  "max_depth": 8,
  "activation_state": "active",
  "color_algorithm_version": 1,
  "palette_version": "divide-v1"
}
```

GET `/api/personal_partitions` 返回上下文字段及 `nodes`、`memberships`；member 含 location_ref / node_id / is_primary。树数据按用户隔离，成员状态至少区分 available、unavailable、different_dataset；不可见资料不得泄露元数据。默认路径不当作个人节点落库。

GET `/api/personal_partitions/locations` 参数：`region_mode`、`dataset_id`、`dataset_version`、`expected_revision`、`view`（default / inherited_default / personal / private / unclassified / other_default）、`path_segments` 或 `node_id`、`search`、`cursor`。JSON path_segments 通过结构化参数编码，不使用新标签的横杠拼接。

每行返回 location_ref、display_name、origin、default_path 数组、个人全部路径及主标记、effective_path、查询可用性、坐标可用性。列表 cursor 绑定数据源版本与 revision，变更后返回 409，避免翻页混合版本。default 视图按官方范围导航，行内仍显示个人结果；personal 视图按个人成员；inherited_default 视图按未修改地点的默认归属；other_default 提供原树展示策略排除的默认根类。unclassified 管理视图包括当前默认缺失的地点，即使已有个人成员也能从此导航到它；resolve 的 unclassified 则指有效个人结果仍未分类的未修改地点，两者不是同一筛选用途。

所有可见公共点必须可被管理：默认根展示策略排除的资料通过“其他默认分类”分支 / 搜索提供；空或异常路径归入未分类并附原因，不因存儲標記不为 1 被过滤。独立个人点只读取当前用户实体。

### 6.2 页面草稿一次提交

POST `/api/personal_partitions/commit` 接受最终状态 delta，避免操作日志重放：

```json
{
  "contract_version": 1,
  "dataset_id": "UUID",
  "dataset_version": 12,
  "base_revision": 6,
  "upsert_nodes": [
    {"node_id": "UUID", "parent_id": null, "label": "我的A区", "description": "", "sort_order": 0}
  ],
  "delete_node_ids": [],
  "set_locations": [
    {"location_ref": "public:<dataset_id>:<location_id>", "node_ids": ["UUID"], "primary_node_id": "UUID"}
  ]
}
```

set_locations 是该地点最终完整个人成员集，空 node_ids + null primary 表示恢复默认；没有列出的地点不变。节点未列出则不变。删除非空节点必须同时给出子区的新 parent / 删除列表及受影响地点最终成员，不允许隐式解除或级联。

事务流程：

1. 固定当前用户与实际 dataset 上下文，验证版本、activation state 和请求身份。
2. 读取 base revision，构建合并后的最终节点图与受影响地点成员。没有变更不递增 revision。
3. 检查 ownership、同父重名、孤儿、环、全图深度不超过 8、节点移动的后代深度、被删除节点不再被引用。
4. 检查每个新 / 修改地点身份可见且当前可管理；全部成员属于自己且存在；有成员恰有一个主。首个新增成员可仅在单成员且明确无旧成员时自动主，重叠最终状态必须带 primary。
5. 事务内用 `UPDATE ... WHERE revision = base_revision` 抢占用户 revision，受影响行非 1 返回 409；防止校验后另一页提交。按 FK 和唯一索引安全顺序写图与成员，任何失败回滚整批。
6. 提交后返回新 revision 与更新快照。响应失败但事务成功时客户端通过读取 revision 和目标状态确认，delta 再传不会重复创建节点。

默认 / query 库不与 supplements 共享事务：提交前后复核当前发布代数，数据源发布协调保证一次请求绑定同一代。不能声称跨库写原子性。当前写入只改 supplements，部署切换中的上下文不一致直接拒绝重试。

错误：401 未登录；403 无权；409 revision / 数据源版本 / 迁移预览已变化；422 校验失败，以 `{code, node_id?, location_ref?, field?, message}` 定位；服务异常 500 不当作部分成功。对当前不可见点不返回可枚举的私人详细信息。

已有 unavailable / 不同源成员可以原样保留，或由用户明确解除；不能新增到失效身份。节点删除若涉及不能显示详情的旧成员仍需告知隐藏受影响数量，并拒绝未经明确处理的删除，不能泄露元数据或静默丢弃引用。

### 6.3 服务端选点解析

POST `/api/personal_partitions/resolve` 参数共用 `dataset_id` / `dataset_version` / `expected_revision` / `region_mode`，并传：

- `selectors`：`{kind:"personal", node_id}` 或 `{kind:"inherited_default", path_segments:[...]}`，未分类使用 `{kind:"unclassified"}`；禁止用标签充当 node ID。
- `location_refs`：显式地点集合，与 selectors 做身份并集。
- `purpose`：query 或 manage；query 再传实际 `query_context` 以应用已有权限和功能限额。

个人节点包含直属和后代全部归属；继承默认节点仅包含无个人成员的当前默认点；unclassified 指无个人成员且当前无默认路径。返回引用、当前显示名、来源、不可用原因、匹配 / 可用总数和版本，不静默截断。

个人树不沿用旧单集合 1000 成员上限；查询仍沿用角色 / 上下文上限。大范围使用 POST 服务端展开，超出实际查询上限明确拒绝，不能只传前 1000 个然后显示“全部”。旧字符串查询保持行为；新增 location_refs 时沿相同业务权限过滤，公共 ID 解析到当前简称，个人 ID 查询其绑定记录。

前端已找到六处消费端：查字 / 中古等 QueryPage、ComparePage、聚类 ClusterInputPanel、音韵计数 Countphos、词表 VocabularyTopControls、DivideTab。实施时须追踪各自实际后端请求与地点名键结果结构，公共 ID 均解析到本代资料；个人点按功能原有能力返回数据或不可用原因。不能只改 `/get_locs/` 后宣称全部支持，更不能让私有同名点借公共点数据通过可用性检查。

### 6.4 个人 dot 绘图

POST `/api/personal_partitions/plot` 参数共用版本与 region_mode，`level` 1 至 8，`scope` 为 selected 或 all_visible，selected 使用与 resolve 同型的 selectors / location_refs；`iscustom` 沿用已有补充数据含义。

有效主路径按个人主节点祖先或当前默认路径计算。选中层级为 `min(level, 实际深度)`；无默认分组为未分类。返回 `points`，每点有 location_ref、display_name、coordinates、primary_path（结构化节点 / 默认段）、group_key、group_label、color_index；并返 matched_count、plotted_count、skipped 按原因汇总及版本。

颜色键定义：个人节点 `personal:<user_id>:<node_id>`；默认 `default:<dataset_id>:<region_mode>:<规范JSON祖先段数组>`；未分类 `unclassified:<dataset_id>:<region_mode>`。规范 JSON 为 UTF-8 原段数组、保留非 ASCII 字符、无多余空格，不繁简转换。采用 SHA-256 的 UTF-8 key，取前 8 字节无符号大端整数 `% palette_length`；算法版本 1，`divide-v1` 精确沿用前端 `CATEGORY_PALETTE` 的 20 色与顺序，前端消费 color_index。节点改名和选点子集不改颜色；不同父下同名不合组；有限色板允许碰色。palette version 变更需显式发布，不因请求遍历顺序分配颜色。

全部可见点沿原 all-data 绘图能力，不能套用一般音韵查询 1000 点上限；响应按现有大范围接口方式处理。坐标缺失 / 无效跳过并汇总，不能把点管理资格等同于可绘图；同名独立个人点保持各自点记录。通过 B 非主归属选出的点仍按 A 主归属画。

## 7. 旧分区与旧个人资料迁移

启动 schema migration 只建表，不自动启用用户内容。未激活用户继续读写旧 UserRegion，进入新页面时可申请预览。旧表保留原 JSON 和名称，任何归属不能在解析过程中直接被丢弃。

POST `/api/personal_partitions/migration/preview` 固定当前 dataset version、用户 revision、旧表与相关个人资料摘要，返回 snapshot_id 和完整原数据及建议：

- 每组原名作为一级节点，`A-B` 原样保留，不拆层级；名称冲突显示处理选项。
- 当前公共身份、可靠历史简称及个人绑定共同产生候选。旧名字与现在名字 / 多历史身份冲突时不能优先猜某一者；缺乏来源时间证据标为待确认。
- 同一点只有一个明确归属可建议主；重叠必须选主。
- 不可识别、退休、同名资料、坐标 / 来源冲突显示原因；用户可以选明确目标或明确暂存为 pending，不能自动删除。暂存项不进入新可选 / 可画结果，原始材料完整保留。
- 公共补充 / 独立个人点身份先确认，再把相关 Information 绑定和分区成员关联到相同引用。

POST `.../migration/activate` 传 snapshot_id、base_revision、dataset 版本及逐项处理结果；每个原成员必须有 resolved 或用户明确 pending 的处理，所有已迁入重叠必须指定主。未查看 / 未处理项拒绝启用。原组成员数等于已迁入原成员记录数加明确 pending 数，重复成员映射可去重但原行保留。

激活事务同时保存必要个人点 / 绑定、个人节点 / 成员、处理记录、状态及 revision。预览过期返回 409；与旧 API 写入共同采用用户状态锁，避免预览期间新旧竞态。激活后旧 POST / DELETE `/api/custom_regions` 返回明确 409 升级要求；旧 GET 明示 activation state / 升级提示，不能提供可编辑的失真树扁平投影。

pending 后续在同一迁移处理入口确认目标，再作为一次正式修改接入新体系，不新增第二套集合功能。默认库 / 权限变化使已迁入身份失效时保持成员并提示，不再次自动按名字匹配。

回滚区分 schema 回滚与内容回滚：备份 supplements、query 身份及发布版本。旧分组 JSON 无法无损表示主归属和树；已启用账号不能回到允许旧 API 写入的服务版本。最小回滚保持新数据与接口，关闭新 UI 写入口并提示；需要真正恢复旧内容必须依据完整备份且评估新写入损失。

## 8. 地点改名调研依据

MCPDict 在审阅的提交 `79c7388c9f98968141518ca44947d3b986d758cc` 中，将方案成员保存为完整 `語言` 字符串，而不是地点简称 UUID；绘图 / 选择时由当前完整語言查短简称。仅简称改变、完整語言不变时能继续匹配；`sanitizeCustomLanguages` 会过滤当前 DB.getLanguages 不包含的名称，完整語言更名仍可能失效。其分区名称的全角横杠前缀模拟层级也不适合直接作为新八级节点数据库。

参考：[Pref.java 的成员清理](https://github.com/osfans/MCPDict/blob/79c7388c9f98968141518ca44947d3b986d758cc/app/src/main/java/com/osfans/mcpdict/Util/Pref.java#L548)、[DB.java](https://github.com/osfans/MCPDict/blob/79c7388c9f98968141518ca44947d3b986d758cc/app/src/main/java/com/osfans/mcpdict/DB.java)。本项目采用预处理永久身份 + 可靠别名历史，不宣称借用完整語言即可解决所有更名。

本地旧 UserRegion 样本只有 2 组、1 位用户、5 条成员记录，无重叠；5 个简称均非当前公共簡稱直接命中。这只说明样本需要解析，不能证明生产规模，也不能证明它们全是更名。

## 9. 代码落点与实施阶段

| 现有文件 | 拟实施职责 |
| --- | --- |
| `app/service/user/core/models.py`、`database.py` | 新实体与版本化 schema migration |
| `app/lifecycle/startup.py` | 沿现有启动迁移入口建结构，不激活用户内容 |
| `app/service/user/submission/region.py` | 旧接口状态保护及迁移接入；新服务留在现有 user/service 组织中，实际新文件须在实施计划明确 |
| `app/routes/user/custom_regions.py`、`app/schemas/user/submissions.py` | 新个人路由 / schema 注册、旧能力协商 |
| `app/routes/user/custom_data.py`、`form_submit.py` | 点身份读写与聚合改造 |
| `app/service/user/submission/submit.py`、`delete.py` | 所有权明确的实体绑定与删除 |
| `app/service/geo/locations.py`、`app/routes/geo/locations.py` | 公共 ID、默认结构路径、可用性读取 |
| `app/service/geo/locs_regions.py`、`app/routes/geo/get_coordinates.py`、`app/schemas/core/coordinates.py` | 引用型选点 / 坐标适配、个人 dot 输出 |
| `app/sql/db_selector.py`、`app/common/path.py` | 核查实际源，不改变现有库选择策略 |
| `app/service/geo/partitions.py`、`app/common/partition_policy.py` | 复用当前默认路径规则，个人模型不覆盖原接口语义 |

依赖顺序：预处理先提供公共身份；后端可先用临时测试库做 schema / 约束开发，但生产 capability 必须等身份元数据可用；随后前端分阶段接入。

每步实施、真实 CR、验证、只提交该步文件：

1. 数据源身份读取及公共 / 个人引用适配，隔离测试覆盖权限与同名。
2. 新 schema 与个人资料身份，全局枚举 Information 写入口；迁移只建表。
3. 节点 / 成员快照、最终 delta 原子保存、revision 并发校验。
4. 完整可见地点列表、服务端选点及查询消费者适配。
5. 迁移预览 / 激活 / pending / 旧 API 状态保护。
6. dot 输出、稳定颜色、缺坐标诊断与前端联调。

## 10. 必须验证的业务不变量

- 深度 8 可用，第 9 级 / 环 / 跨用户 parent / 同父同名拒绝；不同父同名独立。移动父节点按整个后代图校验。
- 父直属点与子孙成员合并无重复；多归属一主，首次自动主、追加不换主、去主未指定接替拒绝；恢复默认清空所有成员。
- map / yindian 共享个人结果，未修改分别回退；官方更新不修改个人路径；空默认可管理且未分类。
- 存儲標記文本 / 数值和缺音韵不影响管理；查询按功能可用性过滤且超限不截断；无坐标只影响绘图。
- 公共补充沿公有身份，独立私有同名点隔离；改名不改引用；他人点、其他源或无权限资料不得泄露或误用。
- 并发两次保存仅一个成功；任何节点 / 成员写失败整批回滚；已有 unavailable 引用保留而新增被拒绝。
- 预览版本变化 / 旧接口竞态拒绝激活；原成员逐条保留；横杠组名不拆；重叠选主；pending 明确确认；旧客户端不假成功。
- 个人绘图第 4 至 8 级、浅路径回退、同名子区、选点子集和排序变化颜色一致；默认绘图、`iscustom` 原含义保持。

使用隔离 supplements/query/auth 临时测试库验证迁移与事务，禁止在真实用户库做实验。现有默认路径测试与用户数据测试作为兼容回归；实现时再确定并运行精准 pytest 目标，本次文档阶段不运行与改动无关的应用测试。
