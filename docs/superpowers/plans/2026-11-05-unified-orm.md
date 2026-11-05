# ORM 创建、策略与释放统一管理

使用 brainstorming 明确边界，按 writing-plans / test-driven-development 实施。用户已要求统一管理，本次在已有隔离 worktree 的 codex/unify-orm 分支顺序执行，不连接服务器。

**目标：** 集中四个运行时 SQLite ORM 的引擎、连接策略、Session 工厂与停机释放，同时保留现有导入、模型、迁移、权限和事务行为。本次不缩池、不改页缓存、不新增线程/进程/后台服务。

| profile | 连接等待 | 外键 | 页缓存 | 文件池容量/溢出 |
| --- | --- | --- | --- | --- |
| auth | 5s | ON | 保持 SQLite 默认 | 5 / 10 |
| supplements | 5s（原 sqlite 默认） | ON | 保持 SQLite 默认 | 5 / 10 |
| logs | 5s（原 sqlite 默认） | 不覆盖默认 | 64000 KiB（62.5 MiB） | 5 / 10 |
| vocabulary | 10s | ON | 保持 SQLite 默认 | 5 / 10 |

以上均沿用现状；池按需建连接，不预建 15 条。上限指每个数据库、每个 worker，不能作为整机连接或 RSS 上限。WAL、失败回退 DELETE、synchronous=NORMAL、pre_ping 也保持原语义。内存数据库保留 SQLAlchemy 原池策略。

## 文件和步骤

- [x] 新建 tests/test_orm_manager.py，先验证未实现时失败：惰性连接、四个 profile 的 PRAGMA、池容量、Session 绑定/显式提交/异常回滚、内存库兼容、无强引用累计、无 SQL 的池状态和统一 dispose。
- [x] 新建 app/common/sqlite_orm.py，集中不可变 policy、create_engine_and_session(profile, url)、make_session_factory(bind)、只读连接状态诊断和 dispose_all_orm_engines()。资源登记用弱引用，不永久保留临时引擎；同一 worker 的四个应用入口仍分别持有自己的 engine。
- [x] 修改 app/service/auth/database/connection.py、app/service/logging/core/database.py、app/service/user/core/database.py、app/service/vocabulary/database.py，只替换引擎/钩子/Session 创建部分，保留 engine、SessionLocal、get_db、常量及 vocabulary 测试工厂入口。建表和迁移留在原模块，不搬进通用工厂。
- [x] 修改 app/service/vocabulary/deferred_count.py，统一已有 bind 的临时 Session 工厂创建，不新增 engine/pool，不改变 expire_on_commit/autoflush/事务边界。
- [x] 在 app/lifecycle/startup.py 的 shutdown finally 中释放 ORM 池，之后仍释放 raw 池；即使 Redis 关闭失败也要清理。
- [x] 运行新单元测试及 auth usage、user suggestions、vocabulary routes/service/deferred、admin 统计、fixed cache 相关回归；逐项记录原有失败、真实 Redis 缺失导致的跳过，不扩大业务修复范围。
- [x] 全局检索 app 的 create_engine/sessionmaker，确认运行时创建仅集中于新模块。脚本/测试的独立实验 engine 不接入运行时注册表。
- [x] 将 scripts/benchmark_sqlite_connection_lifecycle.py 的只读本地比较和实测边界写入验证报告；记录此管理重构本身没有改变缓存/连接数，不能承诺内存或吞吐收益。检查 diff、复核、提交，并在保留用户未提交文件的前提下合入本地 dev。

验证命令使用原项目现有 .venv/bin/python，不安装依赖。实现不添加写入重试，失败沿用现有异常和关闭语义；无请求数据常驻缓存，注册表大小由实际仍存活的 engine 引用决定。

实现与验证结果见 docs/unified-orm-validation-2026-11-05.md；独立代码复核未发现可确认回归，新 manager 测试 16 项通过。
