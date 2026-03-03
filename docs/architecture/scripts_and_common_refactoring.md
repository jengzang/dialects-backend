# 脚本整理和 common 目录迁移方案

## 一、根目录脚本整理

### 1.1 当前根目录脚本

```
fastapi/
├── run.py                    # 开发启动脚本（保留）
├── serve.py                  # 生产启动脚本（保留）
├── gunicorn_config.py        # Gunicorn 配置（保留）
├── deploy.ps1                # PowerShell 部署脚本
├── deploy_statics.ps1        # 静态文件部署脚本
├── deploy_statics.sh         # 静态文件部署脚本（Shell）
├── monitor_gunicorn.sh       # Gunicorn 监控脚本
└── restart_gunicorn.sh       # Gunicorn 重启脚本
```

### 1.2 脚本分类

#### 核心启动脚本（必须保留在根目录）
- `run.py` - 开发环境启动
- `serve.py` - 生产环境启动
- `gunicorn_config.py` - Gunicorn 配置

**原因：** 这些是应用入口，Docker 和部署脚本直接引用，必须在根目录。

#### 部署和运维脚本（建议移到 scripts/）
- `deploy.ps1`
- `deploy_statics.ps1`
- `deploy_statics.sh`
- `monitor_gunicorn.sh`
- `restart_gunicorn.sh`

**原因：** 这些是运维工具，不是应用核心，可以集中管理。

### 1.3 建议的整理方案

```bash
# 创建 scripts 目录
mkdir -p scripts/deployment

# 移动部署脚本
mv deploy.ps1 scripts/deployment/
mv deploy_statics.ps1 scripts/deployment/
mv deploy_statics.sh scripts/deployment/
mv monitor_gunicorn.sh scripts/deployment/
mv restart_gunicorn.sh scripts/deployment/

# 更新脚本中的路径引用（如果有）
```

整理后的结构：
```
fastapi/
├── run.py                    # 开发启动
├── serve.py                  # 生产启动
├── gunicorn_config.py        # Gunicorn 配置
├── scripts/                  # 工具脚本
│   └── deployment/           # 部署脚本
│       ├── deploy.ps1
│       ├── deploy_statics.ps1
│       ├── deploy_statics.sh
│       ├── monitor_gunicorn.sh
│       └── restart_gunicorn.sh
├── test/                     # 测试脚本
└── docs/                     # 文档
```

---

## 二、common 目录迁移到 app/

### 2.1 影响分析

#### 需要修改的文件统计
- **63 个文件** 导入了 `from common.*`
- **Dockerfile** 第 28 行：`COPY common/ /app/common/`
- **gunicorn_config.py** 无直接导入（通过 app 间接使用）

#### 导入语句变化

```python
# 修改前
from common.config import _RUN_TYPE
from app.common.api_config import API_ROUTE_CONFIG
from app.common.constants import PHONOLOGY_FEATURES
from common.path import QUERY_DB_ADMIN

# 修改后
from app.common.config import _RUN_TYPE
from app.common.api_config import API_ROUTE_CONFIG
from app.common.constants import PHONOLOGY_FEATURES
from app.common.path import QUERY_DB_ADMIN
```

### 2.2 迁移步骤

#### 步骤 1：移动目录
```bash
mv common app/
```

#### 步骤 2：修改 BASE_DIR 路径（重要！）
```python
# app/common/path.py 第 5 行
# 修改前
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 修改后（需要往上两级到项目根目录）
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
```

#### 步骤 3：全局替换导入语句（63 个文件）
```bash
# 方法 1：使用 sed（Linux/Mac/Git Bash）
find app -name "*.py" -type f -exec sed -i 's/from common\./from app.common./g' {} \;
find app -name "*.py" -type f -exec sed -i 's/import common\./import app.common./g' {} \;

# 方法 2：使用 Python 脚本（跨平台）
python scripts/refactor_imports.py
```

#### 步骤 3：修改 Dockerfile
```dockerfile
# 修改前（第 28 行）
COPY common/ /app/common/

# 修改后
COPY app/common/ /app/app/common/
```

#### 步骤 4：测试
```bash
# 语法检查
python -m py_compile app/**/*.py

# 启动测试
python run.py

# 运行测试
pytest test/
```

### 2.3 风险评估

| 风险项 | 风险等级 | 影响范围 | 缓解措施 |
|--------|----------|----------|----------|
| 导入语句遗漏 | 🟡 中 | 63 个文件 | 使用自动化脚本，全局搜索验证 |
| Dockerfile 构建失败 | 🟡 中 | Docker 部署 | 修改后立即测试构建 |
| 循环依赖 | 🟢 低 | app 内部 | common 不依赖 app，无循环依赖风险 |
| 测试脚本失败 | 🟢 低 | test/ 目录 | test/ 中的脚本也需要更新导入 |

### 2.4 回滚方案

```bash
# 如果出现问题，快速回滚
git checkout -- .
git clean -fd

# 或者从备份恢复
mv app/common common
# 恢复所有导入语句
find app -name "*.py" -type f -exec sed -i 's/from app\.common\./from common./g' {} \;
```

---

## 三、迁移脚本

### 3.1 自动化重构脚本

创建 `scripts/refactor_common_to_app.py`：

```python
#!/usr/bin/env python3
"""
将 common/ 目录迁移到 app/common/ 并更新所有导入语句
"""
import os
import re
from pathlib import Path

def update_imports_in_file(file_path):
    """更新单个文件中的导入语句"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 替换 from common. 为 from app.common.
    content = re.sub(r'\bfrom common\.', 'from app.common.', content)

    # 替换 import common. 为 import app.common.
    content = re.sub(r'\bimport common\.', 'import app.common.', content)

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    base_dir = Path(__file__).parent.parent
    app_dir = base_dir / 'app'
    test_dir = base_dir / 'test'

    updated_files = []

    # 更新 app/ 目录
    for py_file in app_dir.rglob('*.py'):
        if update_imports_in_file(py_file):
            updated_files.append(py_file)

    # 更新 test/ 目录
    for py_file in test_dir.rglob('*.py'):
        if update_imports_in_file(py_file):
            updated_files.append(py_file)

    # 更新根目录的 Python 文件
    for py_file in base_dir.glob('*.py'):
        if update_imports_in_file(py_file):
            updated_files.append(py_file)

    print(f"✅ 已更新 {len(updated_files)} 个文件的导入语句")
    for f in updated_files:
        print(f"   - {f.relative_to(base_dir)}")

if __name__ == '__main__':
    main()
```

### 3.2 验证脚本

创建 `scripts/verify_imports.py`：

```python
#!/usr/bin/env python3
"""
验证所有导入语句是否正确
"""
import os
import re
from pathlib import Path

def check_old_imports(file_path):
    """检查是否还有旧的 common 导入"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 from common. 或 import common.
    old_imports = re.findall(r'(from common\.|import common\.)', content)
    return old_imports

def main():
    base_dir = Path(__file__).parent.parent

    files_with_old_imports = []

    # 检查所有 Python 文件
    for py_file in base_dir.rglob('*.py'):
        if '.venv' in str(py_file) or '__pycache__' in str(py_file):
            continue

        old_imports = check_old_imports(py_file)
        if old_imports:
            files_with_old_imports.append((py_file, old_imports))

    if files_with_old_imports:
        print(f"❌ 发现 {len(files_with_old_imports)} 个文件仍使用旧的导入语句：")
        for f, imports in files_with_old_imports:
            print(f"   - {f.relative_to(base_dir)}: {imports}")
        return False
    else:
        print("✅ 所有文件的导入语句已更新")
        return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
```

---

## 四、完整迁移流程

### 4.1 准备阶段

```bash
# 1. 创建备份
git stash
git branch backup-before-common-migration

# 2. 确保工作区干净
git status

# 3. 创建脚本目录
mkdir -p scripts/deployment
mkdir -p scripts/refactoring
```

### 4.2 脚本整理

```bash
# 移动部署脚本
mv deploy.ps1 deploy_statics.ps1 deploy_statics.sh scripts/deployment/
mv monitor_gunicorn.sh restart_gunicorn.sh scripts/deployment/

# 提交
git add scripts/
git commit -m "refactor: move deployment scripts to scripts/deployment/"
```

### 4.3 common 目录迁移

```bash
# 1. 创建重构脚本
# （将上面的 refactor_common_to_app.py 和 verify_imports.py 保存到 scripts/refactoring/）

# 2. 移动 common 目录
mv common app/

# 3. 运行重构脚本
python scripts/refactoring/refactor_common_to_app.py

# 4. 验证导入
python scripts/refactoring/verify_imports.py

# 5. 修改 Dockerfile
sed -i 's|COPY common/ /app/common/|COPY app/common/ /app/app/common/|' Dockerfile

# 6. 语法检查
python -m compileall app/

# 7. 测试启动
python run.py &
sleep 5
curl http://localhost:5000/__ping
kill %1
```

### 4.4 测试和提交

```bash
# 1. 运行测试
pytest test/ -v

# 2. Docker 构建测试
docker build -t myapp:test .

# 3. 提交更改
git add .
git commit -m "refactor: move common/ to app/common/ and update all imports"

# 4. 如果有问题，回滚
git reset --hard backup-before-common-migration
```

---

## 五、推荐方案

### 方案 A：完全迁移（推荐）

**优点：**
- ✅ 所有应用代码在 app/ 下，结构统一
- ✅ 符合"应用内配置"的理念
- ✅ 更容易打包和分发

**缺点：**
- ❌ 需要修改 63 个文件
- ❌ 需要修改 Dockerfile
- ❌ 有一定风险

**适用场景：** 如果你希望项目结构更紧凑，所有应用代码集中管理。

### 方案 B：保持现状（稳妥）

**优点：**
- ✅ 无需修改任何代码
- ✅ 零风险
- ✅ 配置独立，易于查找

**缺点：**
- ❌ 目录结构不够紧凑

**适用场景：** 如果当前架构运行良好，不想冒险。

### 方案 C：仅整理脚本（折中）

**优点：**
- ✅ 清理根目录，保持整洁
- ✅ 风险极低
- ✅ common/ 保持独立

**缺点：**
- ❌ common/ 仍在根目录

**适用场景：** 先整理脚本，观察一段时间后再决定是否迁移 common/。

---

## 六、我的建议

### 立即执行：方案 C（仅整理脚本）

```bash
# 1. 创建 scripts 目录
mkdir -p scripts/deployment

# 2. 移动部署脚本
mv deploy.ps1 deploy_statics.ps1 deploy_statics.sh scripts/deployment/
mv monitor_gunicorn.sh restart_gunicorn.sh scripts/deployment/

# 3. 更新 CLAUDE.md
# （已完成）

# 4. 提交
git add scripts/ CLAUDE.md
git commit -m "refactor: organize deployment scripts into scripts/deployment/"
```

### 可选执行：方案 A（迁移 common）

**建议时机：**
- 在下一个大版本发布前
- 或者在功能开发的空档期
- 确保有充足的测试时间

**执行前提：**
- 完整的单元测试覆盖
- 完整的备份
- 充足的回滚时间

---

## 七、总结

### 脚本整理
- ✅ **立即执行** - 移动部署脚本到 `scripts/deployment/`
- ✅ 风险低，收益明显
- ✅ 保持根目录整洁

### common 迁移
- ⚠️ **谨慎考虑** - 需要修改 63 个文件 + Dockerfile
- ⚠️ 有一定风险，需要充分测试
- ⚠️ 建议在稳定期执行，不要在功能开发期

### 最终建议
1. **现在：** 整理脚本（方案 C）
2. **观察：** 运行一段时间，确保稳定
3. **未来：** 如果确实需要更紧凑的结构，再考虑迁移 common（方案 A）

**当前架构已经很好，common/ 独立有其优势，不必强求迁移。**
