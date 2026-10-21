# Vocabulary 分区筛选与返回

用户已确认完整路径协议、词表自身数据源及不同维度 AND 的方案，并授权写方案后直接实施。

## 接口与语义

- `/search/entries`、`/search/standard-words`、`/search/map-points`、`/search/map-items` 增加重复 query 参数 `regions`，以及 `region_mode=yindian|map`（默认 yindian）。
- 地点选项 `/search/location-options` 增加同样分区参数及 province/city。多个分区 OR，分区与现有地点/行政区/词条条件 AND。不改变旧 locations 的模糊搜索语义。
- 每条路径匹配本身及 `路径-` 开头的全部后代；不限制层级数，不按末级名称跨分支匹配，不做隐式繁简转换。使用参数化 `= / substr` 保留大小写及 `% _ \\` 字面值。
- 每次最多 50 条原始路径，每条最多 200 字符；空路径、空段、段首尾空白拒绝（400）；无效模式拒绝（400）。先限制输入数量再去重、去除被祖先覆盖的路径。无匹配返回空，不能退回全量；不传路径不筛分区。
- 分区取自 vocabulary_locations 的 yindian_region / atlas_region，仅通过 `(user_id, location_name)` 关联词条。不借公共库简称推断分区。
- entries 新增 yindian_region / atlas_region，默认空字符串。
- location-options 保留旧的每简称一个选项，以最早地点记录作为稳定代表；在过滤后选代表。新增两套标量分区（仅全部匹配记录一致时返回，否则空）和 `yindian_regions` / `atlas_regions`（不同非空值排序数组），避免同名地点静默丢失分区。旧地点标签/行政区仍来自代表记录，不将它当精确身份。
- 新增 `/search/partition-options?region_mode=...&parent=...`，从词表地点 DISTINCT 非空合法路径补全任意深度祖先；返回 schema_version=2、region_mode、revision、max_depth、parent、nodes，每节点 label/path/depth/children。无 parent 返回全树，有 parent 返回直接子节点及其子树；格式错误 400，不存在 404。排序复用现有 ROOT_ORDER，其他节点按原文排序。不套用公共库排除根规则，词表实际合法路径均可选；不额外扫描词条来排除空地点。

## 查询、缓存和失败行为

统一在 query.py 的筛选构造器加入分区谓词。树和分区规范化放在独立 vocabulary/partitions.py，保持公共库接口行为。

实测后采用地点子查询：先在地点表判断精确/前缀条件，再以 `(e.user_id,e.location_name) IN (SELECT p.user_id,p.location_name ...)` 筛词条，避免按每条词条重复判断 50 条路径。有分区条件时，standard-words 使用现有 user_location 索引后分组；无分区条件保留原 covering index 计划。map-points 有分区条件时先聚合窄的地点身份、count、min(id)，再查宽的地点元数据；其他依赖地点的条件仍在内层正确 JOIN。entries 分区查询先计数，空结果提前返回，避免按 id 搜索不存在的首屏。未新增持久索引；子查询和 GROUP BY 的 SQLite 临时结构需要计入内存/临时 I/O 成本。

所有 search 结果依赖地点版本（包括无筛选的地点标签、分区返回），SQL 查询继续只依赖 entries 版本。cache key、Lua 写入校验、旧版本清理同时更新；搜索 scope 使用 search-v2，防止部署后读取旧响应，并清理原 scope 搜索键，SQL 键保留。默认七项预热不增加；分区树和筛选组合使用已有按需 LRU：默认最多 128 个键、每响应 128 KiB、TTL 1 小时。多选顺序/重复项、无分区时无意义模式规范化到同一键。

不增加线程池、进程、服务或后台任务，沿用同步查询在线程中执行、相同缓存键合并计算与现有串行预热。新增树内存 O(不同路径段总数)，查询保留现有分页/聚合返回边界；map-items 等已有无分页输出不承诺固定内存。50 条路径限制 SQL 条件增长，父子合并减少冗余。不额外自动重试数据库查询；复用现有 Redis 熔断回源、计算等待超时和预热退避。不同冷键及 Redis 故障时的全局并发仍受现有服务配置限制，本次不宣称新增全局并发上限。

## 验证与性能验收

隔离 SQLite 测试覆盖四接口、每级祖先/直属/后代、分支边界、大小写和通配字面值、重复父子、多条件 AND、空/不存在/非法路径、同名不同用户、缺坐标、分区选项和树。真实隔离 Redis 命名空间验证规范化、更新后所有搜索失效、SQL count 保留、写入竞态拒绝旧版本及清理当前版本安全。

性能使用只读源库的 SQLite backup 快照，不修改真实数据；基线 commit 为 9c4b76a。记录同一快照条数、Python/SQLite/机器信息、预热次数/样本数。基线与改后交替测试相同无筛选/行政区/地点场景，新增音典根/中间/叶子、地图集、未命中与 50 路径场景。分别测数据库服务函数 wall/CPU、独立 tracemalloc 峰值、SQL 查询计划；真实 Redis 测命中延迟及响应大小，区分命中与超过缓存准入上限。基准不含公网/代理和生产负载，不将开发机延迟外推到 2 核 2GB 服务器。根据实测决定查询形态/索引，记录未筛选回归和过滤开销，结果写入性能报告。

## 范围

不扩展 `/sql/query`、管理端 `/locations` 筛选，不改 ZhongGu，不实现个人分区或额外点并集，不在真实用户库做迁移实验。
