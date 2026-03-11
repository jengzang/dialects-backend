# FastAPI 项目架构分析与重组建议

**分析日期：** 2026-03-03
**项目规模：** 8.5GB（含数据库），代码约 3MB

---

## 一、当前架构概览

### 1.1 目录结构

```
fastapi/
├── app/                    # 应用核心（3MB，200+ 文件）
│   ├── main.py            # 应用入口
│   ├── auth/              # 认证授权模块
│   ├── routes/            # API 路由（admin/geo/user）
│   ├── schemas/           # Pydantic 数据模型
│   ├── service/           # 业务逻辑层
│   ├── sql/               # 数据库层
│   ├── logs/              # 日志系统
│   ├── custom/            # 自定义数据模块
│   ├── tools/             # 工具模块（Praat/VillagesML）
│   └── statics/           # 前端静态文件（18MB）
│
├── common/                # 共享配置和工具（30KB）
│   ├── config.py          # 核心配置
│   ├── api_config.py      # API 路由配置
│   ├── constants.py       # 常量定义
│   ├── path.py            # 路径配置
│   └── s2t.py             # 简繁转换
│
├── data/                  # 数据库文件（8GB）
│   ├── auth.db            # 认证数据库
│   ├── logs.db            # 日志数据库
│   ├── dialects_*.db      # 方言数据（5GB）
│   ├── villages.db        # 自然村数据（2.5GB）
│   └── ...
│
├── docs/                  # 文档（40+ 文件）
│   ├── FEATURE_OVERVIEW.md
│   ├── VILLAGESML_API_REFERENCE.md
│   └── ...
│
├── test/                  # 测试脚本（2 个文件）
├── StressTest/            # 压力测试套件
├── logs/                  # 旧日志文件（已迁移）
├── userdata/              # 旧数据备份
│
├── run.py                 # 开发启动脚本
├── gunicorn_config.py     # 生产配置
├── requirements.txt       # 依赖清单
├── CLAUDE.md              # Claude Code 指南
└── README.md              # 项目文档
```

---

## 二、架构优点

### ✅ 2.1 模块化设计优秀

**分层清晰：**
- `routes/` - API 端点定义
- `service/` - 业务逻辑实现
- `schemas/` - 数据验证模型
- `sql/` - 数据库访问层

**职责分离：**
- 认证授权独立模块（`auth/`）
- 日志系统独立模块（`logs/`）
- 工具模块独立封装（`tools/`）

### ✅ 2.2 数据库架构合理

**8 个独立数据库：**
- 用户/管理员数据分离（`dialects_user.db` / `dialects_admin.db`）
- 功能数据库分离（auth/logs/supplements/characters/villages）
- 细粒度权限控制

**连接池管理：**
- 预初始化连接池（5-10 连接/数据库）
- 多进程安全设计

### ✅ 2.3 日志系统完善

**多进程队列架构：**
- 5 个独立队列（API 日志、关键词日志、统计、访问、摘要）
- 批量写入策略（3-50 条记录，5-180s 超时）
- 定时清理任务

### ✅ 2.4 工具模块组织良好

**独立工具：**
- `tools/praat/` - Praat 声学分析（22 个文件）
- `tools/VillagesML/` - 自然村分析（53 个文件，1.3MB）
- `tools/check/` - 检查工具
- `tools/merge/` - 合并工具
- `tools/jyut2ipa/` - 粤语转 IPA

**统一文件管理：**
- `file_manager.py` - 统一文件存储（`{temp}/fastapi_tools/`）
- 自动清理机制（12 小时）

### ✅ 2.5 文档丰富

- 40+ 文档文件
- 覆盖 API 参考、实现指南、迁移文档
- 前端对接文档完善

---

## 三、架构问题

### 🔴 3.1 严重问题（需要立即处理）

#### 问题 1：巨大的临时文件占用空间

```bash
myapp.tar          381MB   # 打包文件，应该删除
statics.tar.gz     7.9MB   # 静态文件压缩包，应该删除
nul                796KB   # Windows 错误文件，应该删除
```

**影响：** 占用 389MB 磁盘空间，污染项目根目录

**解决方案：**
```bash
rm myapp.tar statics.tar.gz nul
echo "*.tar" >> .gitignore
echo "*.tar.gz" >> .gitignore
echo "nul" >> .gitignore
```

#### 问题 2：日志文件散落在根目录

```bash
server.log         3.5KB
uvicorn.log        3.5KB
```

**影响：** 根目录混乱，日志文件应该集中管理

**解决方案：**
```bash
mv server.log uvicorn.log logs/
# 修改日志配置，指定日志输出到 logs/ 目录
```

### 🟡 3.2 中等问题（建议处理）

#### 问题 3：文档组织混乱

**未跟踪的文档：**
```
docs/api_hierarchy_status.md
docs/get_vectors_fix.md
docs/performance_optimization_indexes.md
docs/performance_optimization_summary.md
docs/regional_vectors_api_issues.md
docs/subset_compare_api_update.md
docs/vector_api_complete.md
docs/vector_compare_api.md
docs/admin_custom_regions_implementation.md
```

**不应该在 docs/ 的文件：**
```
docs/temp_api_doc.py        # Python 脚本
```

**临时文件：**
```
email_cluster_fields_question.txt   # 应该删除或移到 docs/
HowToBuild.txt                      # 应该整合到 README
```

**解决方案：**
```bash
# 提交文档
git add docs/*.md
git commit -m "docs: add missing documentation"

# 移动脚本
mkdir -p scripts
mv docs/temp_api_doc.py scripts/

# 清理临时文件
rm email_cluster_fields_question.txt

# 整合构建文档
cat HowToBuild.txt >> docs/BUILD.md
rm HowToBuild.txt
```

#### 问题 4：测试文件位置不当

```
app/test.py        # 应该在 test/ 目录
```

**解决方案：**
```bash
mv app/test.py test/app_test.py
```

#### 问题 5：旧数据未清理

```
userdata/          # 旧数据库备份（420KB）
logs/*.txt         # 旧文本日志（已迁移到 logs.db）
```

**解决方案：**
```bash
# 备份旧数据
mkdir -p backups/old_data
mv userdata backups/old_data/
mv logs/*.txt backups/old_data/

# 或直接删除（如果已确认不需要）
rm -rf userdata
rm logs/*.txt
```

### 🟢 3.3 轻微问题（可选优化）

#### 问题 6：文档命名不一致

- 大写：`FEATURE_OVERVIEW.md`、`VILLAGESML_API_REFERENCE.md`
- 小写：`custom_regions_frontend_guide.md`、`vector_api_complete.md`

**建议：** 统一使用小写 + 下划线命名

#### 问题 7：缺少单元测试

`test/` 目录只有 2 个迁移脚本，缺少：
- 单元测试（pytest）
- 集成测试
- API 测试

**建议：** 添加测试框架
```bash
test/
├── unit/              # 单元测试
│   ├── test_auth.py
│   ├── test_service.py
│   └── ...
├── integration/       # 集成测试
│   ├── test_api.py
│   └── ...
└── conftest.py        # pytest 配置
```

---

## 四、关于 common/ 目录的讨论

### 4.1 当前 common/ 目录内容

```python
common/
├── config.py          # 核心配置（运行模式、密钥、限流等）
├── api_config.py      # API 路由配置（限流、日志、登录要求）
├── constants.py       # 常量定义（音韵学常量、地理常量）
├── path.py            # 路径配置（数据库路径、文件路径）
└── s2t.py             # 简繁转换工具
```

### 4.2 是否应该移到 app/ 内？

#### 方案 A：保持 common/ 独立（推荐）

**优点：**
1. **清晰的依赖关系** - `app/` 依赖 `common/`，而不是循环依赖
2. **配置集中管理** - 所有配置文件在一个地方，易于查找
3. **符合 Python 惯例** - 类似 Django 的 `settings.py`、Flask 的 `config.py`
4. **便于测试** - 测试时可以单独 mock `common/` 模块
5. **便于复用** - 如果有多个应用（如 admin app、api app），可以共享 `common/`

**缺点：**
1. 导入路径稍长：`from common.config import ...`

#### 方案 B：移到 app/common/

**优点：**
1. 所有应用代码在 `app/` 下，结构更紧凑
2. 导入路径统一：`from app.common.config import ...`

**缺点：**
1. **可能导致循环依赖** - `app/main.py` 导入 `app/common/config.py`，而 `app/common/path.py` 可能需要导入 `app/` 的某些模块
2. **配置不够突出** - 配置文件埋在 `app/` 深处，不易发现
3. **不符合 Python 惯例** - 大多数 Python 项目将配置放在顶层或独立目录

### 4.3 推荐方案

**保持 common/ 独立，但重命名为 config/**

```
config/
├── __init__.py
├── app.py             # 应用配置（原 config.py）
├── api.py             # API 配置（原 api_config.py）
├── constants.py       # 常量定义
├── paths.py           # 路径配置（原 path.py）
└── utils.py           # 工具函数（原 s2t.py）
```

**理由：**
1. `config/` 比 `common/` 更明确表达用途
2. 保持独立性，避免循环依赖
3. 文件名更清晰（`app.py` vs `config.py`）

---

## 五、推荐的项目架构

### 5.1 理想的目录结构

```
fastapi/
├── app/                    # 应用核心
│   ├── main.py            # 应用入口
│   ├── auth/              # 认证授权
│   ├── routes/            # API 路由
│   ├── schemas/           # 数据模型
│   ├── service/           # 业务逻辑
│   ├── sql/               # 数据库层
│   ├── logs/              # 日志系统
│   ├── custom/            # 自定义数据
│   ├── tools/             # 工具模块
│   └── statics/           # 静态文件
│
├── config/                # 配置（重命名自 common/）
│   ├── app.py             # 应用配置
│   ├── api.py             # API 配置
│   ├── constants.py       # 常量
│   ├── paths.py           # 路径
│   └── utils.py           # 工具
│
├── data/                  # 数据库文件
├── logs/                  # 日志文件
├── docs/                  # 文档
├── test/                  # 测试
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── conftest.py
│
├── scripts/               # 工具脚本
│   ├── deploy.ps1
│   ├── deploy_statics.sh
│   ├── monitor_gunicorn.sh
│   └── temp_api_doc.py
│
├── backups/               # 备份文件
│   └── old_data/
│
├── .github/               # GitHub 配置
│   └── workflows/         # CI/CD
│
├── run.py                 # 开发启动
├── gunicorn_config.py     # 生产配置
├── requirements.txt       # 依赖
├── CLAUDE.md              # Claude 指南
└── README.md              # 项目文档
```

### 5.2 重组步骤

#### 步骤 1：清理临时文件（立即执行）

```bash
# 删除临时文件
rm myapp.tar statics.tar.gz nul email_cluster_fields_question.txt

# 移动日志文件
mv server.log uvicorn.log logs/

# 更新 .gitignore
echo "*.tar" >> .gitignore
echo "*.tar.gz" >> .gitignore
echo "nul" >> .gitignore
echo "logs/*.log" >> .gitignore
```

#### 步骤 2：整理文档（建议执行）

```bash
# 提交未跟踪的文档
git add docs/*.md
git commit -m "docs: add missing documentation files"

# 创建 scripts 目录
mkdir -p scripts

# 移动脚本文件
mv docs/temp_api_doc.py scripts/
mv deploy.ps1 deploy_statics.* monitor_gunicorn.sh restart_gunicorn.sh scripts/

# 整合构建文档
cat HowToBuild.txt >> docs/BUILD.md
rm HowToBuild.txt
```

#### 步骤 3：清理旧数据（可选）

```bash
# 创建备份目录
mkdir -p backups/old_data

# 移动旧数据
mv userdata backups/old_data/
mv logs/*.txt backups/old_data/

# 更新 .gitignore
echo "backups/" >> .gitignore
```

#### 步骤 4：移动测试文件（建议执行）

```bash
# 移动测试文件
mv app/test.py test/app_test.py

# 创建测试目录结构
mkdir -p test/unit test/integration
touch test/conftest.py
```

#### 步骤 5：重命名 common/ 为 config/（可选）

```bash
# 重命名目录
mv common config

# 重命名文件
cd config
mv config.py app.py
mv api_config.py api.py
mv path.py paths.py
mv s2t.py utils.py
cd ..

# 全局替换导入语句
find app -name "*.py" -exec sed -i 's/from common\./from config./g' {} \;
find app -name "*.py" -exec sed -i 's/import common\./import config./g' {} \;
```

**注意：** 步骤 5 需要大量修改导入语句，建议谨慎执行，或者保持 `common/` 不变。

---

## 六、实施建议

### 6.1 优先级

**P0（立即执行）：**
- 删除临时文件（myapp.tar、statics.tar.gz、nul）
- 移动日志文件到 logs/
- 提交未跟踪的文档

**P1（本周执行）：**
- 创建 scripts/ 目录，移动部署脚本
- 移动 app/test.py 到 test/
- 清理旧数据（userdata/、logs/*.txt）

**P2（下个迭代）：**
- 添加单元测试框架
- 统一文档命名规范
- 考虑重命名 common/ 为 config/

### 6.2 风险评估

**低风险操作：**
- 删除临时文件
- 移动日志文件
- 提交文档

**中风险操作：**
- 移动测试文件（需要更新导入）
- 创建 scripts/ 目录（需要更新部署脚本路径）

**高风险操作：**
- 重命名 common/ 为 config/（需要全局替换导入语句）

### 6.3 回滚方案

所有操作前建议：
```bash
# 创建备份
git stash
git branch backup-before-refactor

# 或创建完整备份
tar -czf fastapi-backup-$(date +%Y%m%d).tar.gz .
```

---

## 七、总结

### 7.1 当前架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 模块化设计 | ⭐⭐⭐⭐⭐ | 分层清晰，职责明确 |
| 数据库架构 | ⭐⭐⭐⭐⭐ | 分离合理，权限完善 |
| 日志系统 | ⭐⭐⭐⭐⭐ | 多进程队列，批量写入 |
| 工具模块 | ⭐⭐⭐⭐⭐ | 独立封装，统一管理 |
| 文档完善度 | ⭐⭐⭐⭐ | 文档丰富，但组织混乱 |
| 代码整洁度 | ⭐⭐⭐ | 有临时文件和旧数据 |
| 测试覆盖率 | ⭐⭐ | 缺少单元测试 |
| **总体评分** | **⭐⭐⭐⭐** | **优秀，但需要清理** |

### 7.2 关于 common/ 目录的结论

**推荐：保持 common/ 独立**

理由：
1. 清晰的依赖关系，避免循环依赖
2. 配置集中管理，易于查找
3. 符合 Python 项目惯例
4. 便于测试和复用

**可选：重命名为 config/**
- 更明确表达用途
- 但需要全局替换导入语句（风险较高）

### 7.3 最终建议

1. **立即执行 P0 任务** - 清理临时文件，提交文档
2. **保持 common/ 不变** - 当前架构已经很好，不需要大改
3. **逐步添加测试** - 提高代码质量和可维护性
4. **统一文档规范** - 制定文档命名和组织规范

**这是一个组织良好的 FastAPI 项目，主要问题是根目录有一些临时文件需要清理，核心架构无需大改。**

---

**文档版本：** v1.0
**最后更新：** 2026-03-03
