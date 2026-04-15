# app/tools/merge_routes.py
"""
Merge工具的API路由：Excel表格合并工具
"""
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from pathlib import Path
import sys
import os

from starlette.responses import StreamingResponse

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.tools.task_manager import task_manager, TaskStatus
from app.tools.file_manager import file_manager
from app.tools.config import (
    CLEANUP_POLICY_MERGE_RESULT,
    TASK_CLEANUP_30M_SECONDS,
)
from .merge_core import (
    load_reference_file,
    merge_excel_files,
    create_new_workbook,
    get_file_name
)

router = APIRouter()


# ==================== Pydantic模型定义 ====================

class UploadReferenceResponse(BaseModel):
    """上传参考表响应"""
    task_id: str
    filename: str
    char_count: int
    message: str


class UploadFilesResponse(BaseModel):
    """上传待合并文件响应"""
    task_id: str
    file_count: int
    files: List[str]
    message: str


class MergeRequest(BaseModel):
    """合并请求"""
    task_id: str


class MergeResponse(BaseModel):
    """合并响应"""
    task_id: str
    status: str
    progress: float
    message: str


class MergeResult(BaseModel):
    """合并结果"""
    task_id: str
    merged_columns: int
    total_chars: int
    message: str


def _touch_merge_cleanup(task_id: str, reason: str) -> None:
    task_manager.update_task_cleanup(
        task_id,
        policy_key=CLEANUP_POLICY_MERGE_RESULT,
        armed=True,
        terminal=True,
        ttl_seconds=TASK_CLEANUP_30M_SECONDS,
        reason=reason,
    )


async def merge_files_async(task_id: str, reference_path: Path, file_paths: List[Path]):
    """
    异步合并文件（后台任务）- 使用原有的merge_excel_files逻辑

    Args:
        task_id: 任务ID
        reference_path: 参考表路径
        file_paths: 待合并文件路径列表
    """
    try:
        # 更新状态
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=10.0,
            message="正在加载参考表..."
        )

        # 使用原有的load_reference_file函数
        reference_chars = load_reference_file(str(reference_path))
        char_count = len(reference_chars)

        task_manager.update_task(
            task_id,
            progress=20.0,
            message=f"参考表加载完成，共{char_count}个字，开始合并文件..."
        )

        # 获取文件名称作为列标题
        file_names = [get_file_name(str(fp)) for fp in file_paths]
        total_files = len(file_paths)

        task_manager.update_task(
            task_id,
            progress=30.0,
            message=f"正在合并{total_files}个文件..."
        )

        # 使用原有的merge_excel_files函数
        merged_data, comments_data = merge_excel_files(
            reference_chars,
            [str(fp) for fp in file_paths]
        )

        task_manager.update_task(
            task_id,
            progress=80.0,
            message="合并完成，正在生成结果文件..."
        )

        # 使用原有的create_new_workbook函数
        new_wb = create_new_workbook(
            reference_chars,
            merged_data,
            comments_data,
            file_names
        )

        # 保存结果
        output_path = reference_path.parent / "merge.xlsx"
        new_wb.save(str(output_path))

        task_manager.update_task(
            task_id,
            progress=95.0,
            message="正在保存合并结果..."
        )

        # 统计合并的列数
        merged_columns = len(file_names)

        # 更新任务为完成
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message=f"合并完成，共合并{merged_columns}列",
            data={
                "output_path": str(output_path),
                "merged_columns": merged_columns,
                "total_chars": char_count
            }
        )
        _touch_merge_cleanup(task_id, "merge_completed")

    except Exception as e:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e),
            message=f"合并失败: {str(e)}"
        )
        _touch_merge_cleanup(task_id, "merge_failed")


# ==================== API端点 ====================

@router.post("/upload_reference", response_model=UploadReferenceResponse)
async def upload_reference(file: UploadFile = File(...)):
    """
    上传参考表（使用原有的load_reference_file函数）

    Args:
        file: 参考表文件

    Returns:
        UploadReferenceResponse: 参考表信息
    """
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls', '.xlsm')):
        raise HTTPException(status_code=400, detail="只支持Excel文件（.xlsx、.xls或.xlsm）")

    # 创建任务
    task_id = task_manager.create_task("merge", {
        "reference_filename": file.filename
    })

    try:
        # 保存文件
        file_path = file_manager.save_upload_file(
            task_id, "merge", file.file, f"reference_{file.filename}"
        )

        # 使用原有的load_reference_file函数加载参考表
        reference_chars = load_reference_file(str(file_path))
        char_count = len(reference_chars)

        # 更新任务信息
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=50.0,
            message=f"参考表上传成功，共{char_count}个字",
            data={
                "reference_filename": file.filename,
                "reference_path": str(file_path),
                "char_count": char_count,
                "reference_chars": reference_chars  # 保存参考字表
            }
        )
        _touch_merge_cleanup(task_id, "reference_uploaded")

        return UploadReferenceResponse(
            task_id=task_id,
            filename=file.filename,
            char_count=char_count,
            message="参考表上传成功"
        )

    except HTTPException as e:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e.detail)
        )
        _touch_merge_cleanup(task_id, "reference_upload_failed")
        raise
    except Exception as e:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e)
        )
        _touch_merge_cleanup(task_id, "reference_upload_failed")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.post("/upload_files", response_model=UploadFilesResponse)
async def upload_merge_files(task_id: str = Form(...), files: List[UploadFile] = File(...)):
    """
    上传待合并文件（可多选）

    Args:
        task_id: 任务ID
        files: 待合并文件列表

    Returns:
        UploadFilesResponse: 文件列表信息
    """
    # 获取任务
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        file_paths = []
        filenames = []

        for file in files:
            # 验证文件类型
            if not file.filename.endswith(('.xlsx', '.xls', '.xlsm')):
                continue

            # 保存文件
            file_path = file_manager.save_upload_file(
                task_id, "merge", file.file, file.filename
            )
            file_paths.append(str(file_path))
            filenames.append(file.filename)

        # 更新任务信息
        task_manager.update_task(
            task_id,
            progress=75.0,
            message=f"上传{len(filenames)}个待合并文件",
            data={
                **task['data'],
                "merge_files": file_paths,
                "merge_filenames": filenames
            }
        )
        _touch_merge_cleanup(task_id, "merge_inputs_uploaded")

        return UploadFilesResponse(
            task_id=task_id,
            file_count=len(filenames),
            files=filenames,
            message=f"成功上传{len(filenames)}个文件"
        )

    except HTTPException:
        raise
    except Exception as e:
        _touch_merge_cleanup(task_id, "merge_inputs_upload_failed")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/execute", response_model=MergeResponse)
async def execute_merge(request: MergeRequest, background_tasks: BackgroundTasks):
    """
    开始合并（异步）- 使用原有的merge逻辑

    Args:
        request: 合并请求
        background_tasks: 后台任务

    Returns:
        MergeResponse: 合并状态
    """
    # 获取任务
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取参考表路径
    reference_path_raw = task['data'].get("reference_path")
    reference_path = Path(reference_path_raw) if reference_path_raw else None
    if not reference_path or not reference_path.exists():
        raise HTTPException(status_code=404, detail="参考表不存在")

    # 获取待合并文件路径
    merge_file_paths = task['data'].get("merge_files", [])
    if not merge_file_paths:
        raise HTTPException(status_code=400, detail="没有待合并文件")

    file_paths: List[Path] = []
    for p in merge_file_paths:
        if not p:
            continue
        path_obj = Path(p)
        if path_obj.exists():
            file_paths.append(path_obj)

    if not file_paths:
        raise HTTPException(status_code=400, detail="没有有效的待合并文件")

    # 启动后台合并任务
    background_tasks.add_task(
        merge_files_async,
        request.task_id,
        reference_path,
        file_paths
    )

    return MergeResponse(
        task_id=request.task_id,
        status="processing",
        progress=0.0,
        message="合并任务已启动"
    )


@router.get("/progress/{task_id}", response_model=MergeResponse)
async def get_merge_progress(task_id: str):
    """
    获取合并进度

    Args:
        task_id: 任务ID

    Returns:
        MergeResponse: 合并进度
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return MergeResponse(
        task_id=task_id,
        status=task['status'],  # 👈 关键修改
        progress=task['progress'],  # 👈 关键修改
        message=task['message']  # 👈 关键修改
    )


@router.get("/download/{task_id}")
async def download_merge_result(task_id: str):
    """下载结果 (使用流式传输)"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 1. 字典访问修复
    if task['status'] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    # 2. 字典访问修复
    output_path_str = task['data'].get("output_path")
    if not output_path_str:
        raise HTTPException(status_code=404, detail="结果文件记录不存在")

    file_path = Path(output_path_str).resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="服务器上的结果文件已丢失")

    # 3. 准备文件名
    filename = "合并结果.xlsx"
    encoded_filename = quote(filename)

    # 4. 使用流式响应 (最稳健的方式)
    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    _touch_merge_cleanup(task_id, "result_downloaded")

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"
        }
    )
