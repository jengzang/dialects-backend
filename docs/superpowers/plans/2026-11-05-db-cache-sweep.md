# 通用池逐库页缓存测量

用户授权本地测试并给出建议，本轮不改变生产/运行时缓存策略、不连接服务器。使用 systematic-debugging 的证据流程，顺序执行。

- [x] 清点固定启动池、懒加载统计池、可选SQL库、只读GIS/toponyms、matrix ATTACH路径；按真实路径去重。
- [x] 写本地只读benchmark：同一SQL/参数/临时存储/连接数，cache_size为2000/4096/8192/16000KiB；每组独立进程，重复3轮，轮换预算顺序。最多2条并发连接，只跑本地文件；每case累计最多3秒，fetchmany限制Python缓冲，不采集用户明细。
- [x] 工作负载覆盖索引定位、批量读取、聚合/COUNT、同连接重复、混合顺序和2连接并发；notes TEMP表只存在于连接，主数据库mode=ro。matrix ATTACH单独改变被附加库预算，主库保持固定。
- [x] 先跑逐库小样本验证：无SQL错误，非空/结果摘要一致，路径/配置断言，无持久配置写入；再完整运行。
- [x] 收集首次/重复/混合/并发耗时、CPU、RSS及峰值、超时、文件身份。结果跨预算/轮次对比，不把小幅噪声或失败当收益，不拿缓存预算直接当RSS节省。
- [x] 对每库给预算建议和证据等级，说明optional/admin库的真实使用频率未知、写入和ORM池不在只读测试覆盖内；不根据一次读测量调写入路径。
- [x] 保存可复现脚本、聚合原始结果与报告，独立复核测量有效性，提交并合入本地dev，保留其他改动。

数据库：query_user.db、dialects_user.db（包括notes）、characters.db、yubao.db、villages.db、villages_admin.db、logs.db、auth.db、yc_spoken.db、vocabulary.db（通用SQL访问）、toponyms.db、dependency/gis.db。query_admin/dialects_admin当前映射同user路径，磁盘同名旧admin文件不当成另一个运行池。supplements仅ORM，不伪装为通用池测试。自定义路径不能无限枚举，按配置固定路径覆盖。

完成：最终156组/4416样本/46case；成功摘要一致，1次首次toponyms超时保留。独立复核发现并修复ATTACH样本去重与辅助连接显式关闭，并重跑相关组。建议多数库2000KiB、toponyms保守维持4096KiB；8192为可选性能档。报告docs/db-cache-sweep-validation-2026-11-05.md，运行配置未改。
