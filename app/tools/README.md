# 工具模块开发指南

本文档介绍如何在 `app/tools` 目录下新增工具，以及如何使用 `task_manager` 和 `file_manager` 管理任务和文件。

## 目录结构

```
app/tools/
├── __init__.py              # 工具路由注册入口
├── task_manager.py          # 任务生命周期管理
├── file_manager.py          # 文件存储管理
├── check/                   # Check 工具
│   ├── check_routes.py
│   └── check_core.py
├── jyut2ipa/               # Jyut2IPA 工具
│   ├── jyut2ipa_routes.py
│   └── jyut2ipa_core.py
├── merge/                  # Merge 工具
│   ├── merge_routes.py
│   └── merge_core.py
└── praat/                  # Praat 工具
    ├── routes.py
    └── core/
```

---

## 一、TaskManager 使用指南

### 什么时候需要使用 TaskManager？

当你的工具需要处理**异步任务**或**长时间运行的操作**时，应该使用 TaskManager：

- ✅ 文件上传和处理（需要跟踪进度）
- ✅ 数据分析任务（可能需要几秒到几分钟）
- ✅ 批量处理操作
- ✅ 需要返回任务 ID 供前端轮询状态的场景
- ❌ 简单的同步 API（如查询配置、获取列表等）

### TaskManager 核心方法

#### 1. 创建任务

```python
from app.tools.task_manager import task_manager, TaskStatus

# 创建任务，返回 task_id
task_id = task_manager.create_task(
    tool_name="your_tool",  # 工具名称，如 "check", "praat"
    initial_data={          # 可选：初始化任务数据
        "filename": "example.txt",
        "options": {"mode": "advanced"}
    }
)
```

**参数说明：**
- `tool_name`: 工具名称，用于文件存储路径和任务识别
- `initial_data`: 可选的初始数据字典，存储任务相关信息

**返回值：**
- `task_id`: 格式为 `{tool_name}_{uuid}`，如 `praat_123e4567-e89b-12d3-a456-426614174000`

#### 2. 获取任务信息

```python
# 获取任务详情
task = task_manager.get_task(task_id)

if task:
    print(f"状态: {task['status']}")
    print(f"进度: {task['progress']}%")
    print(f"数据: {task['data']}")
```

**返回值：** 字典格式的任务信息，包含以下字段：
- `task_id`: 任务 ID
- `tool_name`: 工具名称
- `status`: 任务状态（pending, processing, completed, failed）
- `progress`: 进度（0-100）
- `message`: 状态消息
- `data`: 任务数据字典
- `error`: 错误信息（如果失败）
- `created_at`: 创建时间戳
- `updated_at`: 更新时间戳

#### 3. 更新任务状态

```python
# 更新任务状态和进度
task_manager.update_task(
    task_id,
    status=TaskStatus.PROCESSING,
    progress=50.0,
    message="正在处理文件..."
)

# 更新任务数据（会合并到现有 data 中）
task_manager.update_task(
    task_id,
    data={
        "result_file": "output.csv",
        "rows_processed": 1000
    }
)

# 标记任务完成
task_manager.update_task(
    task_id,
    status=TaskStatus.COMPLETED,
    progress=100.0,
    message="处理完成"
)

# 标记任务失败
task_manager.update_task(
    task_id,
    status=TaskStatus.FAILED,
    error="文件格式不正确"
)
```

#### 4. 删除任务

```python
# 删除任务及其所有文件
task_manager.delete_task(task_id)
```

---

## 二、FileManager 使用指南

### 什么时候需要使用 FileManager？

当你的工具需要**存储和管理文件**时，应该使用 FileManager：

- ✅ 保存用户上传的文件
- ✅ 存储处理结果文件
- ✅ 管理临时文件
- ✅ 需要为每个任务创建独立的文件目录

### FileManager 核心方法

#### 1. 获取任务目录

```python
from app.tools.file_manager import file_manager

# 获取任务专属目录（自动创建）
task_dir = file_manager.get_task_dir(task_id, "your_tool")
# 返回: Path 对象，如 /tmp/fastapi_tools/your_tool/task_id/
```

**目录结构：**
```
base_dir/
└── your_tool/
    └── task_id/
        ├── task_info.json      # TaskManager 自动创建
        ├── uploaded_file.xlsx  # 你保存的文件
        └── result.csv          # 处理结果
```

#### 2. 保存上传文件

```python
from fastapi import UploadFile

# 方法 1: 使用 FileManager 保存
file_path = file_manager.save_upload_file(
    task_id=task_id,
    tool_name="your_tool",
    file=file.file,  # UploadFile.file (BinaryIO)
    filename="original.xlsx"
)

# 方法 2: 手动保存到任务目录
task_dir = file_manager.get_task_dir(task_id, "your_tool")
file_path = task_dir / file.filename
with open(file_path, "wb") as f:
    shutil.copyfileobj(file.file, f)
```

#### 3. 获取文件路径

```python
# 获取文件路径（如果存在）
file_path = file_manager.get_file_path(
    task_id=task_id,
    tool_name="your_tool",
    filename="result.csv"
)

if file_path:
    # 返回文件
    return FileResponse(file_path)
```

#### 4. 列出任务文件

```python
# 列出任务目录下的所有文件
files = file_manager.list_task_files(task_id, "your_tool")
# 返回: ['task_info.json', 'uploaded.xlsx', 'result.csv']
```

#### 5. 删除任务文件

```python
# 删除任务的所有文件（包括目录）
file_manager.delete_task_files(task_id, "your_tool")
```

---

## 三、新增工具完整步骤

### 步骤 1: 创建工具目录

```bash
mkdir app/tools/your_tool
touch app/tools/your_tool/__init__.py
touch app/tools/your_tool/routes.py
touch app/tools/your_tool/core.py
```

### 步骤 2: 编写路由文件 (routes.py)

```python
# app/tools/your_tool/routes.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional

from app.tools.task_manager import task_manager, TaskStatus
from app.tools.file_manager import file_manager
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

# 注意：不要在这里设置 prefix 和 tags
router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: Optional[User] = Depends(ApiLimiter)
):
    """上传文件并创建任务"""

    # 1. 创建任务
    task_id = task_manager.create_task("your_tool", {
        "filename": file.filename
    })

    # 2. 保存文件
    task_dir = file_manager.get_task_dir(task_id, "your_tool")
    file_path = task_dir / file.filename

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 3. 更新任务状态
    task_manager.update_task(
        task_id,
        status=TaskStatus.COMPLETED,
        data={"file_path": str(file_path)}
    )

    return {"task_id": task_id, "filename": file.filename}


@router.post("/process")
async def process_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    user: Optional[User] = Depends(ApiLimiter)
):
    """处理任务（后台执行）"""

    # 验证任务存在
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 添加后台任务
    background_tasks.add_task(process_in_background, task_id)

    return {"message": "任务已提交", "task_id": task_id}


@router.get("/status/{task_id}")
async def get_status(
    task_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """获取任务状态"""
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"]
    }


@router.get("/result/{task_id}")
async def get_result(
    task_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """下载结果文件"""
    task = task_manager.get_task(task_id)

    if not task or task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务未完成")

    # 获取结果文件
    result_path = file_manager.get_file_path(
        task_id, "your_tool", "result.csv"
    )

    if not result_path:
        raise HTTPException(status_code=404, detail="结果文件不存在")

    return FileResponse(result_path, filename="result.csv")


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user: Optional[User] = Depends(ApiLimiter)
):
    """删除任务"""
    task_manager.delete_task(task_id)
    return {"message": "任务已删除"}


# 后台处理函数
def process_in_background(task_id: str):
    """后台处理任务"""
    try:
        # 更新状态为处理中
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=0.0,
            message="开始处理..."
        )

        # 获取任务信息
        task = task_manager.get_task(task_id)
        task_dir = file_manager.get_task_dir(task_id, "your_tool")

        # 执行处理逻辑
        # ... 你的处理代码 ...

        # 更新进度
        task_manager.update_task(task_id, progress=50.0)

        # 保存结果
        result_path = task_dir / "result.csv"
        # ... 保存结果文件 ...

        # 标记完成
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="处理完成",
            data={"result_path": str(result_path)}
        )

    except Exception as e:
        # 标记失败
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e)
        )
```

### 步骤 3: 注册路由到主应用

编辑 `app/tools/__init__.py`：

```python
def setup_tools_routes(app: FastAPI):
    """
    注册所有工具路由
    """
    from app.tools.check.check_routes import router as check_router
    from app.tools.jyut2ipa.jyut2ipa_routes import router as jyut2ipa_router
    from app.tools.merge.merge_routes import router as merge_router
    from app.tools.praat.routes import router as praat_router
    from app.tools.your_tool.routes import router as your_tool_router  # 新增

    app.include_router(check_router, prefix="/api/tools/check", tags=["工具-Check"])
    app.include_router(jyut2ipa_router, prefix="/api/tools/jyut2ipa", tags=["工具-Jyut2IPA"])
    app.include_router(merge_router, prefix="/api/tools/merge", tags=["工具-Merge"])
    app.include_router(praat_router, prefix="/api/tools/praat", tags=["工具-Praat"])
    app.include_router(your_tool_router, prefix="/api/tools/your_tool", tags=["工具-YourTool"])  # 新增
```

### 步骤 4: 测试 API

启动服务后，访问 `http://localhost:8000/docs` 查看自动生成的 API 文档。

---

## 四、最佳实践

### 1. 任务状态管理

```python
# ✅ 好的做法：及时更新状态
task_manager.update_task(task_id, status=TaskStatus.PROCESSING)
# ... 处理逻辑 ...
task_manager.update_task(task_id, status=TaskStatus.COMPLETED)

# ❌ 不好的做法：忘记更新状态
# 任务会一直停留在 PENDING 状态
```

### 2. 错误处理

```python
# ✅ 好的做法：捕获异常并更新任务状态
try:
    # 处理逻辑
    result = process_data()
    task_manager.update_task(task_id, status=TaskStatus.COMPLETED)
except Exception as e:
    task_manager.update_task(
        task_id,
        status=TaskStatus.FAILED,
        error=str(e)
    )
    raise  # 可选：重新抛出异常
```

### 3. 文件清理

```python
# ✅ 好的做法：处理完成后提供删除接口
@router.delete("/{task_id}")
async def delete_task(task_id: str):
    task_manager.delete_task(task_id)  # 会自动删除所有文件
    return {"message": "已删除"}

# 或者设置定时清理（在 main.py 中）
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    lambda: file_manager.cleanup_old_files(max_age_hours=24),
    'interval',
    hours=1
)
scheduler.start()
```

### 4. 进度更新

```python
# ✅ 好的做法：在长时间操作中更新进度
total_items = len(items)
for i, item in enumerate(items):
    process_item(item)
    progress = (i + 1) / total_items * 100
    task_manager.update_task(task_id, progress=progress)
```

---

## 五、常见问题

### Q1: TaskManager 和 FileManager 的关系？

- **TaskManager** 管理任务的**元数据**（状态、进度、错误信息等）
- **FileManager** 管理任务的**文件存储**（上传文件、结果文件等）
- 它们通过 `task_id` 和 `tool_name` 关联

### Q2: 什么时候使用后台任务？

当操作需要超过 2-3 秒时，建议使用 `BackgroundTasks` 或 Celery：

```python
# 短时间操作（< 2秒）：直接处理
@router.post("/quick")
async def quick_operation():
    result = do_something_fast()
    return result

# 长时间操作（> 2秒）：后台处理
@router.post("/slow")
async def slow_operation(background_tasks: BackgroundTasks):
    task_id = task_manager.create_task("tool", {})
    background_tasks.add_task(process_slowly, task_id)
    return {"task_id": task_id}
```

### Q3: 如何处理大文件上传？

```python
# 使用流式保存，避免内存溢出
@router.post("/upload")
async def upload_large_file(file: UploadFile = File(...)):
    task_id = task_manager.create_task("tool", {})
    task_dir = file_manager.get_task_dir(task_id, "tool")
    file_path = task_dir / file.filename

    # 流式写入
    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)

    return {"task_id": task_id}
```

### Q4: 如何实现任务队列？

对于复杂的任务调度，建议使用 Celery：

```python
# celery_tasks.py
from celery import Celery

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task
def process_task(task_id: str):
    # 处理逻辑
    pass

# routes.py
@router.post("/process")
async def submit_task(task_id: str):
    process_task.delay(task_id)  # 提交到 Celery
    return {"message": "任务已提交"}
```

---

## 六、参考示例

完整的工具实现示例，请参考：

- **简单工具**: `app/tools/check/` - 文件上传和处理
- **复杂工具**: `app/tools/praat/` - 多阶段任务、后台处理、结果下载

---

## 七、总结

### 核心要点

1. **TaskManager**: 管理任务生命周期（创建 → 处理 → 完成/失败）
2. **FileManager**: 管理文件存储（上传 → 处理 → 下载 → 清理）
3. **路由注册**: 在 `__init__.py` 中统一注册，不在 routes.py 中设置 prefix/tags
4. **错误处理**: 始终捕获异常并更新任务状态
5. **后台任务**: 长时间操作使用 BackgroundTasks 或 Celery

### 开发检查清单

- [ ] 创建工具目录和文件
- [ ] 实现 routes.py（不设置 prefix/tags）
- [ ] 在 `__init__.py` 中注册路由
- [ ] 使用 TaskManager 管理任务状态
- [ ] 使用 FileManager 管理文件存储
- [ ] 实现错误处理和状态更新
- [ ] 提供任务删除接口
- [ ] 测试 API 功能
- [ ] 编写 API 文档注释

---

**祝开发顺利！** 🚀
