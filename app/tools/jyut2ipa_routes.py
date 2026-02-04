# app/tools/jyut2ipa_routes.py
"""
Jyut2IPA工具的API路由：粤语拼音转IPA
"""
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from pathlib import Path
import asyncio
import sys
import os
import threading

from starlette.responses import StreamingResponse

from common.constants import replace_data

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from .task_manager import task_manager, TaskStatus
from .file_manager import file_manager
from .jyut2ipa_core import process_yutping, init_replace_df

# 初始化替换规则DataFrame
init_replace_df(replace_data)

router = APIRouter()


# ==================== Pydantic模型定义 ====================

class ProcessRequest(BaseModel):
    """处理请求"""
    task_id: str
    custom_rules: Optional[list[dict]] = None  # 新增：自定义规则数组


class ProcessResponse(BaseModel):
    """处理响应"""
    task_id: str
    status: str
    progress: float
    message: str


class ProcessResult(BaseModel):
    """处理结果"""
    task_id: str
    total_rows: int
    processed_rows: int
    message: str


# ==================== 辅助函数 ====================

def find_yutping_column(df: pd.DataFrame) -> Optional[str]:
    """查找粤拼列"""
    # 使用col_map查找，如果没有就直接匹配"粤拼"或"粵拼"
    for col in df.columns:
        col_str = str(col)
        if "粤拼" in col_str or "粵拼" in col_str or "jyutping" in col_str.lower():
            return col
    return None


def cleanup_task_resources(task_id: str, tool_name: str):
    """
    清理任务的所有资源（文件 + 任务记录）

    Args:
        task_id: 任务ID
        tool_name: 工具名称
    """
    try:
        # 清理文件
        file_manager.delete_task_files(task_id, tool_name)
        print(f"[CLEANUP] 已删除任务 {task_id} 的文件")

        # 清理任务记录
        task_manager.delete_task(task_id)
        print(f"[CLEANUP] 已删除任务 {task_id} 的记录")
    except Exception as e:
        print(f"[CLEANUP] 清理任务 {task_id} 时出错: {str(e)}")


async def process_file_async(task_id: str, file_path: Path, custom_rules: Optional[list[dict]] = None):
    """
    异步处理文件（后台任务）

    Args:
        task_id: 任务ID
        file_path: 文件路径
        custom_rules: 自定义规则，格式 [{"to_replace":"aa", "replacement":"a", "category":"wf", "enabled":true}, ...]
    """
    try:
        # 更新状态为处理中
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=0.0,
            message="正在读取文件..."
        )

        # 读取Excel文件
        df = pd.read_excel(file_path, dtype=str, keep_default_na=False)
        total_rows = len(df)

        # 查找粤拼列
        yutping_col = find_yutping_column(df)

        if not yutping_col:
            raise ValueError("未找到'粤拼'或'粵拼'列")

        # 更新进度
        task_manager.update_task(
            task_id,
            progress=10.0,
            message=f"找到粤拼列'{yutping_col}'，共{total_rows}行，开始处理..."
        )

        # 转换custom_rules为replace_data格式
        custom_replace_data = None
        if custom_rules and len(custom_rules) > 0:
            # 过滤启用的规则并转换格式
            enabled_rules = [
                [rule["to_replace"], rule["replacement"], rule["category"]]
                for rule in custom_rules
                if rule.get("enabled", True)  # 只使用启用的规则
            ]
            # 只有当有启用的规则时才使用自定义规则
            if len(enabled_rules) > 0:
                custom_replace_data = enabled_rules
                print(f"[INFO] 使用自定义规则，共{len(custom_replace_data)}条")
            else:
                print(f"[INFO] 自定义规则已全部禁用，使用默认规则")
        else:
            print(f"[INFO] 未提供自定义规则，使用默认规则")

        # 新增的列名
        columns = ['声母', '韵母', '音调', '韵腹', '韵尾',
                   '声母IPA', '韵腹IPA', '韵尾IPA', '音调IPA', 'IPA', '注释']

        # 批量处理（每100行更新一次进度）
        batch_size = 100
        processed = 0

        results = []
        for idx, row in df.iterrows():
            try:
                yutping_value = row[yutping_col]

                # 传递自定义规则
                result = process_yutping(yutping_value, custom_replace_data)

                # 验证返回结果
                if not isinstance(result, pd.Series):
                    raise TypeError(f"行{idx}: process_yutping返回类型错误: {type(result)}")
                if len(result) != 11:
                    raise ValueError(f"行{idx}: 返回长度错误: {len(result)}")

                # 【修改點 1】只提取 values，避免 Series 索引干擾
                if isinstance(result, pd.Series):
                    results.append(result.values)
                else:
                    results.append(result)

            except Exception as e:
                # 单行失败不影响整体，插入空值
                print(f"[ERROR] 行{idx}处理失败: {str(e)}")
                results.append(pd.Series([""] * 11))

            processed += 1
            if processed % batch_size == 0:
                progress = 10.0 + (processed / total_rows) * 80.0
                task_manager.update_task(
                    task_id,
                    progress=progress,
                    message=f"正在处理第 {processed}/{total_rows} 行"
                )
                # 让出控制权，避免阻塞
                await asyncio.sleep(0)

        # 【关键修复】确保索引对齐
        if len(results) == 0:
            raise ValueError("处理结果为空，没有生成任何转换结果")

        result_df = pd.DataFrame(results, columns=columns)

        # 【关键修复】确保空字符串不被转换为NaN
        result_df = result_df.fillna('')  # 将所有NaN替换为空字符串
        result_df = result_df.astype(str)  # 确保所有列都是字符串类型
        result_df = result_df.replace('nan', '')  # 将字符串'nan'替换为空字符串

        # 验证长度一致
        if len(result_df) != len(df):
            raise ValueError(f"结果行数不匹配: result_df={len(result_df)}, df={len(df)}")

        # 验证结果不为空
        non_empty_count = result_df['IPA'].astype(str).str.strip().ne('').sum()
        print(f"[INFO] 转换结果统计: 总行数={len(result_df)}, 非空IPA行数={non_empty_count}")

        # 【诊断日志】检查前几行的实际内容
        if len(result_df) > 0:
            print(f"[DEBUG] result_df前3行内容:")
            for i in range(min(3, len(result_df))):
                print(f"  行{i}: 声母='{result_df.iloc[i]['声母']}', IPA='{result_df.iloc[i]['IPA']}'")

        # 確保 result_df 索引是乾淨的 0 到 N
        result_df.index = range(len(result_df))
        # 確保原始 df 索引也是乾淨的 0 到 N
        df.index = range(len(df))

        # 使用concat而非逐列赋值（更可靠）
        df = pd.concat([df, result_df], axis=1)

        # 【关键修复】确保合并后的DataFrame中空字符串不被转换为NaN
        for col in columns:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).replace('nan', '')

        # 【诊断日志】验证赋值成功
        # print(f"[INFO] DataFrame列数: {len(df.columns)}, 前3列: {df.columns[:3].tolist()}")
        # 使用非空字符串计数而不是notna()，因为空字符串不是NaN
        non_empty_声母 = df['声母'].astype(str).str.strip().ne('').sum()
        non_empty_IPA = df['IPA'].astype(str).str.strip().ne('').sum()
        print(f"[INFO] 新增列验证: 声母(非空)={non_empty_声母}/{len(df)}行, IPA(非空)={non_empty_IPA}/{len(df)}行")

        # 【诊断日志】检查前几行的实际内容
        if len(df) > 0:
            print(f"[DEBUG] 合并后df前3行的声母和IPA列:")
            for i in range(min(3, len(df))):
                print(f"  行{i}: 声母='{df.iloc[i]['声母']}', IPA='{df.iloc[i]['IPA']}'")

        # 保存结果文件
        output_path = file_path.parent / f"result_{file_path.name}"

        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"[INFO] 准备保存: {len(df)}行 x {len(df.columns)}列")
        print(f"[INFO] 输出路径: {output_path}")

        # 显式指定引擎保存
        df.to_excel(output_path, index=False, na_rep="", engine='openpyxl')

        # 【关键验证】确认文件保存成功
        if not output_path.exists():
            raise FileNotFoundError(f"文件保存失败: {output_path}")

        file_size = output_path.stat().st_size
        print(f"[INFO] 文件保存成功: {file_size} bytes")

        if file_size < 1024:  # 小于1KB很可能有问题
            raise ValueError(f"输出文件过小({file_size} bytes)，可能保存失败")

        # 更新任务为完成
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message=f"处理完成，共处理{total_rows}行",
            data={
                "output_path": str(output_path),
                "total_rows": total_rows,
                "processed_rows": total_rows
            }
        )

        # 【新增】5分钟后自动清理文件
        cleanup_delay = 300  # 5分钟 = 300秒
        cleanup_timer = threading.Timer(
            cleanup_delay,
            cleanup_task_resources,
            args=(task_id, "jyut2ipa")
        )
        cleanup_timer.daemon = True
        cleanup_timer.start()
        print(f"[CLEANUP] 已设置定时清理：任务 {task_id} 将在 {cleanup_delay} 秒后清理")

    except Exception as e:
        # 更新任务状态为失败
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e),
            message=f"处理失败: {str(e)}"
        )

        # 【新增】失败时立即清理文件（保留任务记录供前端查看错误信息）
        try:
            file_manager.delete_task_files(task_id, "jyut2ipa")
            print(f"[CLEANUP] 处理失败，已清理任务 {task_id} 的文件")
        except Exception as cleanup_error:
            print(f"[CLEANUP] 清理失败文件时出错: {str(cleanup_error)}")


# ==================== API端点 ====================

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传Excel文件

    Args:
        file: 上传的Excel文件

    Returns:
        任务ID和文件信息
    """
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件（.xlsx或.xls）")

    # 创建任务
    task_id = task_manager.create_task("jyut2ipa", {
        "filename": file.filename
    })

    try:
        # 保存文件
        file_path = file_manager.save_upload_file(
            task_id, "jyut2ipa", file.file, file.filename
        )

        # 读取文件信息
        df = pd.read_excel(file_path)
        total_rows = len(df)

        # 更新任务信息
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message=f"文件上传成功，共{total_rows}行",
            data={
                "filename": file.filename,
                "total_rows": total_rows,
                "file_path": str(file_path)
            }
        )

        return {
            "task_id": task_id,
            "filename": file.filename,
            "total_rows": total_rows,
            "message": "文件上传成功"
        }

    except Exception as e:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.post("/process", response_model=ProcessResponse)
async def process_file(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    开始处理文件（异步）

    Args:
        request: 处理请求（包含task_id和可选的custom_rules）
        background_tasks: 后台任务

    Returns:
        ProcessResponse: 处理状态
    """
    # 获取任务
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 👇 关键修复：安全获取路径，防止 Path(None) 报错
    file_path_str = task['data'].get("file_path")
    if not file_path_str:
        raise HTTPException(status_code=404, detail="文件路径记录丢失")

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件在服务器上不存在")

    # 启动后台处理任务，传递自定义规则
    background_tasks.add_task(
        process_file_async,
        request.task_id,
        file_path,
        request.custom_rules  # 直接传递前端发来的规则
    )

    return ProcessResponse(
        task_id=request.task_id,
        status="processing",
        progress=0.0,
        message="处理任务已启动"
    )


@router.get("/progress/{task_id}", response_model=ProcessResponse)
async def get_progress(task_id: str):
    """
    获取处理进度

    Args:
        task_id: 任务ID

    Returns:
        ProcessResponse: 处理进度
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return ProcessResponse(
        task_id=task_id,
        status=task['status'],  # 👈 改这里
        progress=task['progress'],  # 👈 改这里
        message=task['message']  # 👈 改这里
    )


@router.get("/download/{task_id}")
async def download_result(task_id: str):
    """下载结果文件 (使用流式传输)"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 👇 修复：字典访问
    if task['status'] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    # 👇 修复：字典访问
    output_path_str = task['data'].get("output_path")
    if not output_path_str:
        raise HTTPException(status_code=404, detail="结果文件记录不存在")

    file_path = Path(output_path_str)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="结果文件已在服务器上被清理")

    # 准备下载文件名 (保留原始文件名逻辑)
    original_filename = task['data'].get('filename', 'result.xlsx')
    filename = f"jyut2ipa_result_{original_filename}"
    encoded_filename = quote(filename)

    # 👇 升级：流式响应
    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"
        }
    )