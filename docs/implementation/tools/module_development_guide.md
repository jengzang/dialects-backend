# Tools 模块开发与接入指南

本文档面向后续协作者、维护者与联调开发者，专门说明以下几件事：

1. 如何在 `app/tools/` 目录下新增一个新的工具模块。
2. 当前仓库中工具模块应当如何统一挂载。
3. [`app/tools/file_manager.py`](../../../app/tools/file_manager.py) 的类、方法、配置和注意事项。
4. [`app/tools/task_manager.py`](../../../app/tools/task_manager.py) 的类、方法、配置和注意事项。
5. 路由配置应当改哪些位置、哪些地方不能再写第二套特例逻辑。

本文档不是一个只给“最小 demo”的速记，而是按当前仓库的真实做法，把新增工具模块时需要知道的约束、推荐模式、常见误区和函数级别的调用方式一次讲清楚。

---

## 1. 先理解当前 `app/tools/` 的职责

`app/tools/` 当前承担的是“工具类 API 模块”的统一组织职责。

从仓库结构上看，它主要包括两部分：

1. 工具模块目录
   - `check/`
   - `jyut2ipa/`
   - `merge/`
   - `praat/`

2. 工具模块共用基础设施
   - [`app/tools/file_manager.py`](../../../app/tools/file_manager.py)
   - [`app/tools/task_manager.py`](../../../app/tools/task_manager.py)
   - [`app/tools/__init__.py`](../../../app/tools/__init__.py)

可以把它理解为：

- 每个工具模块目录负责自己的业务逻辑、局部 schema、后台任务和路由。
- `file_manager` 负责所有工具模块共享的文件存储目录、任务目录、文件保存与清理。
- `task_manager` 负责所有工具模块共享的任务 ID、任务状态、进度、持久化和任务读取。
- `app/tools/__init__.py` 负责把所有工具模块统一挂到主应用上。

---

## 2. 当前唯一正确的挂载方式

### 2.1 统一规则

当前仓库中，所有工具模块都必须通过：

- [`app/tools/__init__.py`](../../../app/tools/__init__.py)

统一注册到主应用。

也就是说：

- 工具模块内部只写 `router = APIRouter()`
- 不在工具模块内部写 `prefix="/api/tools/..."`
- 不在工具模块内部写全局级 `dependencies=[Depends(ApiLimiter)]`
- 统一在 `app/tools/__init__.py` 中 `app.include_router(...)`

### 2.2 当前统一注册位置

真正负责工具模块挂载的入口是：

- [`app/tools/__init__.py`](../../../app/tools/__init__.py)

当前模式示意如下：

```python
from app.tools.check.check_routes import router as check_router
from app.tools.jyut2ipa.jyut2ipa_routes import router as jyut2ipa_router
from app.tools.merge.merge_routes import router as merge_router
from app.tools.praat.routes import router as praat_router
from app.service.logging.dependencies.limiter import ApiLimiter

app.include_router(
    check_router,
    prefix="/api/tools/check",
    tags=["工具-Check"],
    dependencies=[Depends(ApiLimiter)],
)
```

`jyut2ipa`、`merge`、`praat` 也都应采用相同模式。

### 2.3 不应该再出现的旧写法

不要再写下面这种模式：

```python
router = APIRouter(
    prefix="/api/tools/praat",
    dependencies=[Depends(ApiLimiter)],
)
```

然后在全局路由里再单独：

```python
app.include_router(praat_router)
```

这种“模块自带 prefix，再由外层特判挂载”的方式已经不应继续使用。原因很简单：

- 会让 `tools` 模块出现两套接入规则。
- 新协作者容易照抄出更多特例。
- `prefix`、`tags`、`ApiLimiter` 的职责边界会变得不清晰。
- 以后如果统一调整 `/api/tools/*` 的挂载规则，维护成本会升高。

### 2.4 `app/routes/__init__.py` 应承担什么职责

全局主路由文件是：

- [`app/routes/__init__.py`](../../../app/routes/__init__.py)

它对工具模块的职责只有一件事：

- 调用 `setup_tools_routes(app)`

它不应该再单独 include 某一个工具模块的 router。

---

## 3. 新增工具模块时应改哪些文件

如果你要新增一个工具模块，例如 `excel_cleaner`，通常要改这些位置：

1. 新建工具目录
   - `app/tools/excel_cleaner/`

2. 新建路由文件
   - `app/tools/excel_cleaner/excel_cleaner_routes.py`

3. 新建业务逻辑文件
   - `app/tools/excel_cleaner/excel_cleaner_core.py`

4. 如有需要，再新增：
   - `schemas/`
   - `utils/`
   - `config.py`
   - `README.md`

5. 在统一挂载入口注册
   - 修改 [`app/tools/__init__.py`](../../../app/tools/__init__.py)

6. 如果需要给协作者或前端补文档，再修改：
   - 根目录 [`README.md`](../../../README.md)
   - [`docs/README.md`](../../README.md)
   - 对应模块文档

通常不需要改：

- `app/routes/__init__.py`

除非你在 `setup_tools_routes(app)` 的调用本身上做了架构级调整。但普通新增工具模块不该改这里。

---

## 4. 推荐目录结构

### 4.1 简单工具模块

适用于：

- 接口数量不多
- 没有特别复杂的配置
- 处理链路清晰

推荐结构：

```text
app/tools/<tool_name>/
├── __init__.py
├── <tool_name>_routes.py
└── <tool_name>_core.py
```

示例：

```text
app/tools/excel_cleaner/
├── __init__.py
├── excel_cleaner_routes.py
└── excel_cleaner_core.py
```

### 4.2 中等复杂度工具模块

适用于：

- 有请求/响应模型
- 有多个处理阶段
- 有校验逻辑或输出格式逻辑

推荐结构：

```text
app/tools/<tool_name>/
├── __init__.py
├── routes.py
├── core.py
├── schemas.py
└── utils.py
```

### 4.3 复杂工具模块

适用于：

- 模块本身像一个子系统
- 有多类 schema、validator、executor、processor
- 有后台作业和多个结果视图

推荐结构：

```text
app/tools/<tool_name>/
├── __init__.py
├── routes.py
├── config.py
├── schemas/
│   ├── __init__.py
│   ├── request.py
│   └── response.py
├── core/
│   ├── __init__.py
│   ├── processor.py
│   └── executor.py
└── utils/
    ├── __init__.py
    └── validators.py
```

`praat` 当前在“目录复杂度”上更接近这一类，但它在“路由挂载方式”上仍然必须与其他工具模块统一。

---

## 5. 推荐的工具模块生命周期

绝大多数工具模块都可以按照下面的生命周期设计：

1. 上传输入文件或接收输入参数
2. 创建任务
3. 保存输入文件
4. 启动后台处理
5. 更新任务进度
6. 提供轮询接口
7. 提供结果下载或结果读取接口
8. 提供清理接口或延迟清理逻辑

典型 API 族一般包括：

- `POST /upload`
- `POST /process` 或 `POST /execute`
- `GET /progress/{task_id}`
- `GET /download/{task_id}`
- `DELETE /progress/{task_id}` 或 `DELETE /task/{task_id}`

如果工具模块是同步工具，也可以简化为：

- `POST /run`
- 立即返回结果

但只要出现下面任一情况，就建议引入 `TaskManager`：

- 处理时间可能超过 1 秒
- 需要后台执行
- 需要进度查询
- 需要后续下载文件
- 需要失败后保留任务状态

---

## 6. `FileManager` 详解

文件位置：

- [`app/tools/file_manager.py`](../../../app/tools/file_manager.py)

### 6.1 这个类负责什么

`FileManager` 负责所有工具模块共享的文件存储逻辑：

- 决定基础存储目录
- 决定每个工具的目录
- 决定每个任务的目录
- 保存上传文件
- 查找文件
- 列出任务目录文件
- 删除任务文件
- 清理过期任务目录

它不是业务逻辑类，而是工具基础设施。

### 6.2 类与全局实例

类：

- `FileManager`

全局实例：

- `file_manager = FileManager()`

普通工具模块不需要自己再 new 一个新的 `FileManager`。应直接复用全局实例 `file_manager`。

### 6.3 `FileManager.__init__(base_dir: Optional[str] = None)`

作用：

- 初始化工具文件存储根目录。

优先级：

1. 显式传入的 `base_dir`
2. 环境变量 `FILE_STORAGE_PATH`
3. 系统临时目录下的 `fastapi_tools`

默认目录示意：

```text
<temp>/fastapi_tools/
```

调用方式：

```python
manager = FileManager()
manager = FileManager(base_dir="D:/tool-storage")
```

实际项目里通常不需要自己调用这个构造函数，而是直接使用全局 `file_manager`。

注意事项：

- 初始化时会自动创建基础目录。
- 如果你在部署环境中希望文件不落在系统临时目录，应该设置 `FILE_STORAGE_PATH`。
- 这个目录下会按 `tool_name / task_id` 继续分层。

### 6.4 `_normalize_task_id(task_id: str) -> str`

作用：

- 校验并规范 `task_id`。

当前规则：

- 只能匹配正则 `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`

也就是说：

- 第一个字符必须是字母或数字
- 后续可包含字母、数字、下划线、连字符
- 总长度最多 128

典型合法值：

- `merge_abc123`
- `praat_8dbe1c8e`

典型不合法值：

- `../evil`
- `/tmp/abc`
- `中文任务`

使用建议：

- 一般不需要业务代码直接调用。
- 它由 `get_task_dir()`、`save_upload_file()` 等内部方法统一调用。

### 6.5 `_normalize_filename(filename: str) -> str`

作用：

- 规范上传文件名，防止路径穿越和异常文件名。

当前处理方式：

- 使用 `Path(filename).name`
- 拒绝空字符串、`.`、`..`

作用举例：

- `../../secret.txt` 会被裁成 `secret.txt`
- `a/b/c.xlsx` 会被裁成 `c.xlsx`

使用建议：

- 一般不需要手动调用。
- 应通过 `save_upload_file()` 间接使用。

### 6.6 `get_tool_dir(tool_name: str) -> Path`

作用：

- 获取某个工具模块的根目录。

示例：

```python
tool_dir = file_manager.get_tool_dir("jyut2ipa")
```

返回值示意：

```text
<base_dir>/jyut2ipa
```

特点：

- 如果目录不存在，会自动创建。

适用场景：

- 你需要在工具级别放置共享缓存文件
- 你需要枚举某个工具模块下的所有任务目录

### 6.7 `get_task_dir(task_id: str, tool_name: str) -> Path`

作用：

- 获取某个任务的目录。

示例：

```python
task_dir = file_manager.get_task_dir(task_id, "merge")
```

返回值示意：

```text
<base_dir>/merge/<task_id>/
```

特点：

- 会校验 `task_id`
- 若目录不存在则自动创建

适用场景：

- 保存上传文件
- 保存中间结果
- 保存最终结果
- 保存任务状态 JSON 以外的其他文件

注意事项：

- `tool_name` 必须与创建任务时使用的工具名保持一致。
- 不要把别的工具的 `task_id` 和当前工具的 `tool_name` 混用。

### 6.8 `save_upload_file(task_id, tool_name, file, filename) -> Path`

作用：

- 将上传文件保存到任务目录中。

典型调用：

```python
task_id = task_manager.create_task("excel_cleaner", {"filename": upload.filename})
saved_path = file_manager.save_upload_file(
    task_id,
    "excel_cleaner",
    upload.file,
    upload.filename,
)
```

内部做了什么：

- 校验 `task_id`
- 规范化 `filename`
- 获取任务目录
- 把文件流 seek 到起始位置
- 复制到目标文件

返回值：

- 保存后的完整 `Path`

注意事项：

- 这个方法假设 `file` 是一个文件对象或文件流。
- 调用前应先创建任务，这样任务目录才能与任务状态对应。
- 如果业务上需要对原始文件名和保存名做区别，可以自己传入一个新的 `filename`。

### 6.9 `get_file_path(task_id, tool_name, filename) -> Optional[Path]`

作用：

- 按文件名读取某个任务目录中的目标文件路径。

示例：

```python
result_path = file_manager.get_file_path(task_id, "merge", "result.xlsx")
if result_path is None:
    raise HTTPException(status_code=404, detail="文件不存在")
```

适合场景：

- 下载接口
- 结果文件存在性校验

注意事项：

- 返回 `None` 表示文件不存在，不会抛异常。
- 仍然会对文件名做基本规范化。

### 6.10 `delete_task_files(task_id, tool_name)`

作用：

- 删除某个任务目录下的所有文件和整个目录。

示例：

```python
file_manager.delete_task_files(task_id, "praat")
```

适用场景：

- 用户手动删除任务
- 后台任务失败后清理脏文件
- 下载完成后延迟清理

注意事项：

- 这是目录级删除，不是单文件删除。
- 如果你需要保留任务状态但删除文件，这个方法会连同 `task_info.json` 所在目录一起删掉；通常应通过 `task_manager.delete_task()` 统一删除，而不是自己只删文件。

### 6.11 `list_task_files(task_id, tool_name) -> list[str]`

作用：

- 列出某个任务目录中的文件名列表。

示例：

```python
files = file_manager.list_task_files(task_id, "merge")
```

适用场景：

- 调试
- 管理接口
- 检查某些中间产物是否已经生成

### 6.12 `cleanup_old_files(max_age_hours: int = 24) -> int`

作用：

- 清理所有工具目录下超过指定年龄的任务目录。

示例：

```python
deleted_count = file_manager.cleanup_old_files(max_age_hours=24)
```

返回值：

- 删除的任务目录数量

适用场景：

- 周期性清理
- 后台维护任务

注意事项：

- 它按目录的修改时间判断是否过期。
- 它是跨所有工具目录统一清理，不是只清理某一个工具。
- 如果你自己的工具模块有“需要长期保留文件”的需求，不要直接依赖默认清理策略。

---

## 7. `TaskManager` 详解

文件位置：

- [`app/tools/task_manager.py`](../../../app/tools/task_manager.py)

### 7.1 这个类负责什么

`TaskManager` 负责所有工具模块共享的任务状态管理：

- 生成任务 ID
- 保存任务状态
- 保存任务元数据
- 读取任务
- 更新任务
- 删除任务
- 列出任务
- 清理旧任务

### 7.2 相关类型

#### `TaskStatus`

当前是 `Enum`，包括：

- `pending`
- `processing`
- `completed`
- `failed`

建议新增工具模块时优先沿用这四个状态，不要自己再发明另一套状态名，除非模块确实有明确需要。

#### `Task`

文件里保留了 `Task` dataclass，但当前实际对外最常见的使用方式是读取/返回 `dict` 结构，而不是 dataclass 实例。

所以在业务代码里，你通常会看到：

```python
task = task_manager.get_task(task_id)
task["status"]
task["data"]
```

而不是：

```python
task.status
task.data
```

### 7.3 全局实例

全局实例：

- `task_manager = TaskManager()`

普通工具模块不需要自己额外 new 一个 `TaskManager`。应直接复用这个全局实例。

### 7.4 单例行为与缓存

`TaskManager` 通过 `__new__` 和内部锁维持全局单例行为，并维护 `_task_cache`。

这意味着：

- 同一进程内的工具模块共享一套任务缓存。
- 任务信息既会落磁盘，也会存在进程内缓存中。

### 7.5 `_get_task_json_path(task_id, tool_name) -> Path`

作用：

- 获取任务状态文件 `task_info.json` 的完整路径。

返回路径示意：

```text
<base_dir>/<tool_name>/<task_id>/task_info.json
```

一般不需要业务代码直接调用。

### 7.6 `_parse_id(task_id) -> tuple[str, str]`

作用：

- 从 `task_id` 解析出 `tool_name` 和原始任务 ID。

当前规则：

- 若 `task_id` 中含 `_`，会按第一次 `_` 切分
- 左侧视为 `tool_name`
- 否则兼容老任务，默认归到 `"check"`

例如：

- `praat_abc123` -> `("praat", "abc123")`
- `merge_xxxxx` -> `("merge", "xxxxx")`

注意事项：

- 这也是为什么推荐 `task_id` 保持 `<tool_name>_<uuid>` 风格。
- 如果你偏离这个风格，会让解析和兼容成本变高。

### 7.7 `_save_json(path, data)`

作用：

- 把任务信息写入 JSON 文件。

一般不需要业务代码直接调用。

### 7.8 `_load_json(path) -> Optional[Dict]`

作用：

- 从 JSON 文件加载任务信息。

一般不需要业务代码直接调用。

### 7.9 `create_task(tool_name, initial_data=None) -> str`

作用：

- 创建一个新的任务。

典型调用：

```python
task_id = task_manager.create_task(
    "jyut2ipa",
    {"filename": upload.filename}
)
```

当前行为：

- 生成 `<tool_name>_<uuid>` 风格的 `task_id`
- 写入 `task_info.json`
- 把任务信息放入缓存

返回值：

- 新任务的 `task_id`

这是绝大多数工具模块的第一步。

建议：

- 上传类工具模块在接到文件时就立刻创建任务。
- `initial_data` 只放最初始、最必要的信息，例如上传文件名、原始参数摘要等。

### 7.10 `get_task(task_id) -> Optional[Dict[str, Any]]`

作用：

- 读取任务信息。

读取顺序：

1. 先查缓存
2. 再查磁盘 `task_info.json`

典型调用：

```python
task = task_manager.get_task(task_id)
if not task:
    raise HTTPException(status_code=404, detail="任务不存在")
```

适用场景：

- 进度查询接口
- 下载接口
- 删除接口
- 后台任务执行前检查任务是否存在

### 7.11 `update_task(task_id, **kwargs)`

作用：

- 更新任务状态和任务数据。

典型调用：

```python
task_manager.update_task(
    task_id,
    status=TaskStatus.PROCESSING,
    progress=20.0,
    message="正在解析文件",
)
```

也可以更新 `data`：

```python
task_manager.update_task(
    task_id,
    data={"output_path": str(output_path)}
)
```

重要行为：

- 如果 `kwargs` 里有 `data`，会和现有 `task_info["data"]` 做 merge，而不是整个覆盖。

这意味着：

- 可以分阶段往 `data` 中补字段。
- 但也要注意字段名冲突，避免把旧值意外覆盖。

推荐字段：

- `status`
- `progress`
- `message`
- `error`
- `data`

### 7.12 `delete_task(task_id)`

作用：

- 删除任务缓存和任务目录。

典型调用：

```python
task_manager.delete_task(task_id)
```

内部会：

- 从缓存删除
- 通过 `file_manager.delete_task_files()` 删除任务目录

这是删除任务时的推荐入口。不要自己手动删 JSON 再删目录。

### 7.13 `cleanup_old_tasks(max_age_seconds=3600)`

作用：

- 清理旧任务。

当前实现：

- 实际上是换算成小时后委托给 `file_manager.cleanup_old_files()`

也就是说，它最终仍然是目录级清理。

适用场景：

- 周期性维护任务

### 7.14 `get_all_tasks(tool_name=None) -> Dict[str, Dict[str, Any]]`

作用：

- 遍历并读取所有任务。

示例：

```python
all_tasks = task_manager.get_all_tasks()
merge_tasks = task_manager.get_all_tasks("merge")
```

适合场景：

- 管理接口
- 调试
- 本地排查某个工具是否残留大量历史任务

注意事项：

- 这是全量扫描，不应在普通高频业务接口里乱用。

---

## 8. 一个推荐的最小工具模块模板

下面给出一个推荐的最小模板，用于新增诸如 `excel_cleaner` 一类的文件工具。

### 8.1 路由文件模板

```python
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.tools.file_manager import file_manager
from app.tools.task_manager import task_manager, TaskStatus

router = APIRouter()


class ProcessRequest(BaseModel):
    task_id: str


async def run_async(task_id: str, file_path: Path):
    try:
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=10.0,
            message="正在处理文件",
        )

        output_path = file_path.parent / "result.txt"
        output_path.write_text("done", encoding="utf-8")

        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="处理完成",
            data={"output_path": str(output_path)},
        )
    except Exception as e:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message=f"处理失败: {e}",
            error=str(e),
        )


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    task_id = task_manager.create_task("excel_cleaner", {"filename": file.filename})
    file_path = file_manager.save_upload_file(
        task_id,
        "excel_cleaner",
        file.file,
        file.filename,
    )

    task_manager.update_task(
        task_id,
        status=TaskStatus.COMPLETED,
        progress=100.0,
        message="上传完成",
        data={"file_path": str(file_path)},
    )
    return {"task_id": task_id}


@router.post("/process")
async def process_file(request: ProcessRequest, background_tasks: BackgroundTasks):
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task["data"]["file_path"])
    background_tasks.add_task(run_async, request.task_id, file_path)
    return {
        "task_id": request.task_id,
        "status": "processing",
        "progress": 0.0,
        "message": "任务已开始",
    }


@router.get("/progress/{task_id}")
async def get_progress(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task
```

### 8.2 统一挂载

然后在：

- [`app/tools/__init__.py`](../../../app/tools/__init__.py)

中注册：

```python
from app.tools.excel_cleaner.excel_cleaner_routes import router as excel_cleaner_router

app.include_router(
    excel_cleaner_router,
    prefix="/api/tools/excel_cleaner",
    tags=["工具-ExcelCleaner"],
    dependencies=[Depends(ApiLimiter)],
)
```

这样一个最小可用工具模块就接入完成了。

---

## 9. 路由配置位置总结

### 9.1 工具模块自己的路由文件

作用：

- 只声明 endpoint
- 只维护 `router = APIRouter()`
- 不负责全局 prefix

示例位置：

- `app/tools/check/check_routes.py`
- `app/tools/jyut2ipa/jyut2ipa_routes.py`
- `app/tools/merge/merge_routes.py`
- `app/tools/praat/routes.py`

### 9.2 工具模块统一注册入口

作用：

- 给每个工具模块加统一 prefix
- 给每个工具模块加统一 tags
- 给每个工具模块加统一 `ApiLimiter`

位置：

- [`app/tools/__init__.py`](../../../app/tools/__init__.py)

### 9.3 全局总路由入口

作用：

- 调用 `setup_tools_routes(app)`

位置：

- [`app/routes/__init__.py`](../../../app/routes/__init__.py)

注意：

- 普通新增工具模块时，不要把新模块直接 include 到这里。

---

## 10. 配置与环境变量

### 10.1 `FILE_STORAGE_PATH`

这个环境变量决定工具文件的根目录。

如果不配置，默认落在系统临时目录下：

```text
<temp>/fastapi_tools
```

建议：

- 本地调试可以不配
- 部署环境建议显式配置到稳定的持久目录

### 10.2 `tool_name` 的命名规则

建议统一：

- 只使用小写字母、数字、下划线
- 与目录名保持一致
- 与路由前缀保持一致

例如：

- 目录：`app/tools/excel_cleaner/`
- `tool_name`：`excel_cleaner`
- 前缀：`/api/tools/excel_cleaner`
- `task_id`：`excel_cleaner_<uuid>`

不要出现：

- 目录叫 `excel_cleaner`，`tool_name` 却写成 `cleaner`
- 路由前缀又写成 `/api/tools/excel`

这种不一致会给文件路径、任务路径、排查和协作带来持续成本。

### 10.3 清理策略

如果你的工具模块会生成大文件，必须考虑清理。

一般有三种策略：

1. 用户主动删除任务
2. 下载完成后延迟清理
3. 周期性清理旧任务目录

推荐至少保留一种自动清理策略，否则磁盘会持续增长。

---

## 11. 现有几个工具模块分别适合参考什么

### 11.1 `check`

适合参考：

- 相对传统的文件工具模式
- 上传后编辑/分析的工作流

### 11.2 `jyut2ipa`

适合参考：

- 上传 -> 后台处理 -> 进度 -> 下载 的经典链路
- 处理完成后延迟清理任务资源

### 11.3 `merge`

适合参考：

- 多文件上传
- 任务阶段较多
- 最终输出文件下载

### 11.4 `praat`

适合参考：

- 更复杂的目录组织
- `schemas / core / utils` 分层
- 上传与 job 分离
- `job_id` 与 `task_id` 并存

但注意：

- `praat` 只是在模块内部结构上更复杂
- 它不是挂载方式上的特例
- 不要再复制“模块内部自带 prefix，再在主路由单独挂载”的旧模式

---

## 12. 常见误区

### 12.1 `tool_name` 前后不一致

错误示例：

- `create_task("merge")`
- `save_upload_file(..., "merge_tool", ...)`

这会导致文件和任务目录不一致。

### 12.2 把 `task_manager.get_task()` 当 dataclass 用

当前返回的是字典结构，常见正确写法是：

```python
task = task_manager.get_task(task_id)
task["status"]
task["data"]
```

### 12.3 没有统一走 `app/tools/__init__.py`

新增工具模块时，如果你直接跑去改 `app/routes/__init__.py`，一般就是走偏了。

### 12.4 文件保存前没有先创建任务

推荐顺序应当是：

1. `create_task(...)`
2. `save_upload_file(...)`

而不是反过来。

### 12.5 处理失败时没有回写任务状态

如果后台任务异常但你没有调用：

```python
task_manager.update_task(..., status=TaskStatus.FAILED, ...)
```

前端就会看到卡死的任务。

### 12.6 只删文件，不删任务

如果你想删除整个任务，请优先调用：

```python
task_manager.delete_task(task_id)
```

不要自己只删任务目录，留下缓存和状态文件不一致的问题。

### 12.7 盲目照抄 `praat`

`praat` 适合参考的是复杂子系统的内部组织方式，不是所有工具模块都需要一上来就抄成那么重。

---

## 13. 新增工具模块 checklist

新增一个工具模块前，建议逐项核对：

1. 是否确定了唯一一致的 `tool_name`
2. 是否确定了模块目录名
3. 是否确定了路由文件名
4. 是否确定该模块是否需要任务系统
5. 是否确定该模块是否需要文件系统
6. 是否确定了上传、处理、进度、下载、删除的完整链路
7. 是否在失败路径中回写 `FAILED`
8. 是否在 [`app/tools/__init__.py`](../../../app/tools/__init__.py) 中统一注册
9. 是否避免改动 [`app/routes/__init__.py`](../../../app/routes/__init__.py) 做特判
10. 是否考虑了清理策略
11. 是否补了必要文档

---

## 14. 对协作者的直接建议

如果你只是想新增一个普通工具模块，请直接：

1. 参考 `jyut2ipa` 或 `merge`
2. 复用 `file_manager`
3. 复用 `task_manager`
4. 在 `app/tools/__init__.py` 统一挂载

如果你要新增一个复杂工具模块，也仍然建议：

1. 目录可以参考 `praat`
2. 但路由挂载仍然统一走 `app/tools/__init__.py`

一句话总结：

- 复杂度可以不同
- 挂载方式不要分叉

---

## 15. 最终结论

当前仓库下新增工具模块的推荐实践是：

1. 模块内部使用 `APIRouter()`，不要自带全局 prefix
2. 路由统一在 [`app/tools/__init__.py`](../../../app/tools/__init__.py) 注册
3. 文件相关逻辑尽量复用 [`app/tools/file_manager.py`](../../../app/tools/file_manager.py)
4. 任务相关逻辑尽量复用 [`app/tools/task_manager.py`](../../../app/tools/task_manager.py)
5. `praat` 可以作为复杂目录组织示例，但不再作为挂载特例

如果后续有新的协作者加入，这份文档应当作为 `tools` 目录协作的第一入口文档。
