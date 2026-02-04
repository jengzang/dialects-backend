# app/tools/check_routes.py
"""
Check工具的API路由：方言音位数据检查编辑器
"""
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
import pandas as pd
from pathlib import Path
import sys
import os
import re

from starlette.responses import StreamingResponse

from common.constants import col_map

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from .task_manager import task_manager, TaskStatus
from .file_manager import file_manager
from .check_core import 處理自定義編輯指令, 檢查資料格式, 整理並顯示調值
from .format_convert import (
    process_音典,
    process_跳跳老鼠,
    process_縣志_excel,
    process_縣志_word,
    convert_to_tsv_if_needed, extract_onset_rime_from_ipa, extract_all_from_files
)

router = APIRouter()


# ==================== Pydantic模型定义 ====================

class UploadResponse(BaseModel):
    """文件上传响应"""
    task_id: str
    filename: str
    total_rows: int
    message: str


class ErrorItem(BaseModel):
    """错误项"""
    row: int
    error_type: str  # nonSingleChar, invalidIpa, missingTone
    field: str  # char, ipa
    value: str
    message: str


class AnalysisResult(BaseModel):
    """分析结果"""
    task_id: str
    total_rows: int
    error_count: int
    errors: List[ErrorItem]
    error_stats: Dict[str, int]


class CommandRequest(BaseModel):
    task_id: str
    commands: Union[str, List[str]]  # 支援單一字串或字串列表
    overwrite: Optional[bool] = True  # 是否覆蓋原檔，預設 False (產生 modified_ 檔案)


class CommandResponse(BaseModel):
    """命令执行响应"""
    success: bool
    affected_rows: int
    message: str
    logs: List[str]


class SaveChangesRequest(BaseModel):
    """保存更改请求"""
    task_id: str
    modified_rows: List[Dict[str, Any]]


class GetDataRequest(BaseModel):
    """获取数据请求"""
    task_id: str
    include_all: bool = False  # 是否包含所有行（包括正常行）


class RowData(BaseModel):
    """行数据"""
    row: int
    char: str
    ipa: str
    tone: str = ""
    note: str = ""


class UpdateRowRequest(BaseModel):
    """更新行请求"""
    task_id: str
    row: int
    data: Dict[str, str]


class QuickFixRequest(BaseModel):
    """快速修复请求"""
    task_id: str
    row: int
    error_type: str


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    task_id: str
    rows: List[int]  # 要删除的行号列表


# ==================== 辅助函数 ====================

def find_standard_column(df: pd.DataFrame, standard_name: str) -> Optional[str]:
    """
    根据col_map查找标准列名

    Args:
        df: DataFrame
        standard_name: 标准列名（'漢字', '音標', '解釋'）

    Returns:
        实际的列名，如果找不到返回None
    """
    possible_names = col_map.get(standard_name, [])
    for col in df.columns:
        if col in possible_names:
            return col
    return None


def analyze_excel_file(file_path: Path) -> tuple[pd.DataFrame, List[ErrorItem], Dict[str, int], str, str]:
    """
    分析Excel文件，检查错误（使用原有的檢查資料格式函数）

    Returns:
        (数据框, 错误列表, 错误统计, 汉字列名, 音标列名)
    """
    # 读取Excel文件
    df = pd.read_excel(file_path, dtype=str)

    # 查找关键列
    col_hanzi = find_standard_column(df, '漢字')
    col_ipa = find_standard_column(df, '音標')
    col_note = find_standard_column(df, '解釋')

    if not col_hanzi:
        raise ValueError("未找到汉字列（需包含'漢字'、'單字'或'单字'）")

    if not col_ipa:
        raise ValueError("未找到音标列（需包含'IPA'、'音標'等）")

    # 调用原有的检查函数（捕获输出）
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        檢查資料格式(df, col_hanzi, col_ipa, display=False, col_note=col_note)

    check_output = f.getvalue()

    # 解析检查输出，提取错误信息
    errors = []
    error_stats = {
        "nonSingleChar": 0,
        "invalidIpa": 0,
        "missingTone": 0
    }

    # 解析输出
    lines = check_output.split('\n')
    current_error_type = None

    for line in lines:
        if '非單字漢字' in line:
            current_error_type = 'nonSingleChar'
            # 提取数量
            match = re.search(r'發現 (\d+) 項', line)
            if match:
                error_stats["nonSingleChar"] = int(match.group(1))
        elif '異常音標' in line:
            current_error_type = 'invalidIpa'
            match = re.search(r'發現 (\d+) 項', line)
            if match:
                error_stats["invalidIpa"] = int(match.group(1))
        elif '缺聲調' in line:
            current_error_type = 'missingTone'
            match = re.search(r'發現 (\d+) 項', line)
            if match:
                error_stats["missingTone"] = int(match.group(1))
        elif current_error_type and '(' in line:
            # 解析错误项，格式如 (123, '帥哥')
            items = re.findall(r"\((\d+), '([^']+)'(?:, '([^']*)')?\)", line)
            for item in items:
                row_num = int(item[0]) + 2  # DataFrame索引转Excel行号
                value = item[1]
                error_field = 'char' if current_error_type == 'nonSingleChar' else 'ipa'

                errors.append(ErrorItem(
                    row=row_num,
                    error_type=current_error_type,
                    field=error_field,
                    value=value,
                    message=get_error_message(current_error_type)
                ))

    return df, errors, error_stats, col_hanzi, col_ipa


def get_error_message(error_type: str) -> str:
    """获取错误消息"""
    messages = {
        "nonSingleChar": "应为单字汉字",
        "invalidIpa": "音标格式异常",
        "missingTone": "缺少声调"
    }
    return messages.get(error_type, "未知错误")


# ==================== API端点 ====================

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
        file: UploadFile = File(...),
        format_type: Optional[str] = Form(None),  # 修改這裡：使用 Form(None)
        level: int = Form(0),
):
    """
    上传文件并创建任务

    支持格式：
    - Excel (.xlsx, .xls) - 标准音典格式或特殊格式
    - Word (.doc, .docx) - 县志格式
    - TSV (.tsv) - 制表符分隔文件
    """
    # 验证文件类型
    ext = Path(file.filename).suffix.lower()
    allowed_exts = {'.xlsx', '.xls', '.doc', '.docx', '.tsv'}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式。支持：{', '.join(allowed_exts)}"
        )

    # 创建任务
    task_id = task_manager.create_task("check", {
        "filename": file.filename,
        "original_format": ext,
        "format_type": format_type
    })

    try:
        # 保存文件
        file_path = file_manager.save_upload_file(
            task_id, "check", file.file, file.filename
        )

        converted_path = None
        needs_conversion = False

        # Word格式：转换为标准格式
        if ext in {'.doc', '.docx'}:
            print(f"[FORMAT] 检测到Word文件，使用县志格式处理")
            task_dir = file_manager.get_task_dir(task_id, "check")
            output_tsv = task_dir / f"{Path(file.filename).stem}.tsv"

            process_縣志_word(str(file_path), level, output_path=str(output_tsv))

            # TSV转换为XLSX
            if output_tsv.exists():
                df = pd.read_csv(output_tsv, sep="\t", dtype=str)
                converted_path = task_dir / f"{Path(file.filename).stem}.xlsx"
                df.to_excel(converted_path, index=False)
                file_path = converted_path
                needs_conversion = True
                print(f"[FORMAT] Word文件已转换为Excel: {converted_path}")

        # TSV格式：转换为XLSX
        elif ext == '.tsv':
            print(f"[FORMAT] 检测到TSV文件，转换为Excel")
            df = pd.read_csv(file_path, sep="\t", dtype=str)
            task_dir = file_manager.get_task_dir(task_id, "check")
            converted_path = task_dir / f"{Path(file.filename).stem}.xlsx"
            df.to_excel(converted_path, index=False)
            file_path = converted_path
            needs_conversion = True

        # Excel格式：检查是否为标准格式
        elif ext in {'.xlsx', '.xls'}:
            df = pd.read_excel(file_path, dtype=str)
            df_cols = df.columns.tolist()

            # 检查是否有标准列名
            mapped_cols = {}
            for std_col, variants in col_map.items():
                for v in variants:
                    if v in df_cols:
                        mapped_cols[std_col] = v
                        break

            # 如果缺少必需列，尝试格式转换
            required_cols = {"漢字", "音標"}
            if not (required_cols <= set(mapped_cols.keys())):

                task_dir = file_manager.get_task_dir(task_id, "check")
                output_tsv = task_dir / f"{Path(file.filename).stem}.tsv"
                print("format_type", format_type)
                # 根据format_type选择处理方式
                if format_type == '跳跳老鼠':
                    print(f"[FORMAT] 使用跳跳老鼠格式处理")
                    process_跳跳老鼠(str(file_path), level, output_path=str(output_tsv))
                elif format_type == '縣志':
                    print(f"[FORMAT] 使用县志格式处理")
                    process_縣志_excel(str(file_path), level, output_path=str(output_tsv))
                else:
                    # 默认使用音典格式
                    print(f"[FORMAT] 使用音典格式处理")
                    process_音典(str(file_path), level, output_path=str(output_tsv))

                # TSV转换为XLSX
                if output_tsv.exists():
                    df = pd.read_csv(output_tsv, sep="\t", dtype=str)
                    converted_path = task_dir / f"{Path(file.filename).stem}.xlsx"
                    df.to_excel(converted_path, index=False)
                    file_path = converted_path
                    needs_conversion = True
                    print(f"[FORMAT] 特殊格式已转换为标准Excel: {converted_path}")

        # 读取最终文件
        df = pd.read_excel(file_path, dtype=str)

        print(f"[INFO] 开始提取声母、韵母、声调...")
        df_extracted = extract_all_from_files(str(file_path), preserve_empty_rows=True)

        # 【新增】验证行数一致
        if len(df_extracted) != len(df):
            print(f"[WARNING] 提取结果行数不一致: 原始{len(df)}行, 提取{len(df_extracted)}行")
            # 截断或补齐
            if len(df_extracted) < len(df):
                # 补齐空行
                missing_rows = len(df) - len(df_extracted)
                empty_rows = pd.DataFrame([{"声母": "", "韵母": "", "声调": ""}] * missing_rows)
                df_extracted = pd.concat([df_extracted, empty_rows], ignore_index=True)
            else:
                # 截断多余行
                df_extracted = df_extracted.iloc[:len(df)]

        # 【新增】合并声母、韵母、声调列（覆盖已有列）
        df['声母'] = df_extracted['声母'].fillna("")
        df['韵母'] = df_extracted['韵母'].fillna("")
        df['声调'] = df_extracted['声调'].fillna("")

        # 【新增】保存回文件
        df.to_excel(file_path, index=False)
        print(f"[INFO] 声韵数据已提取并保存")

        # 1. 确定最终的文件名
        final_filename = file.filename
        if needs_conversion:
            # 如果发生了转换，把文件名后缀改成 .xlsx
            # 例如: "县志.docx" -> "县志.xlsx"
            final_filename = f"{Path(file.filename).stem}.xlsx"

        total_rows = len(df)

        # 2. 更新任务信息
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message=f"文件上传成功，共{total_rows}行" + (" (已转换格式)" if needs_conversion else ""),
            data={
                "filename": final_filename,  # <--- 改这里！存 .xlsx
                "original_filename": file.filename,  # <--- 新增！保留原始名字备查
                "total_rows": total_rows,
                "file_path": str(file_path),
                "converted": needs_conversion
            }
        )

        return UploadResponse(
            task_id=task_id,
            filename=final_filename,
            total_rows=total_rows,
            message="文件上传成功" + (" (已自动转换格式)" if needs_conversion else "")
        )

    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] 文件处理失败: {error_detail}")

        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_file(task_id: str):
    """
    分析文件并返回错误列表（使用原有的檢查資料格式函数）
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        task_manager.update_task(task_id, status=TaskStatus.PROCESSING, message="正在分析文件...")

        df, errors, error_stats, col_hanzi, col_ipa = analyze_excel_file(file_path)

        # 更新任务信息
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message=f"分析完成，发现{len(errors)}个错误",
            data={
                **task['data'],
                "errors": [error.dict() for error in errors],
                "error_stats": error_stats,
                "col_hanzi": col_hanzi,
                "col_ipa": col_ipa
            }
        )

        return AnalysisResult(
            task_id=task_id,
            total_rows=len(df),
            error_count=len(errors),
            errors=errors,
            error_stats=error_stats
        )

    except Exception as e:
        task_manager.update_task(task_id, status=TaskStatus.FAILED, error=str(e))
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/execute", response_model=CommandResponse)
async def execute_commands(request: CommandRequest):
    """
    統一執行指令 API
    支持單個指令 (str) 或多個指令 (List[str])
    """
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        # 1. 統一指令格式為 List[str]
        commands = [request.commands] if isinstance(request.commands, str) else request.commands
        command_str = "; ".join(commands)

        # 2. 讀取 Excel
        df = pd.read_excel(file_path, dtype=str)

        # 3. 獲取列名
        col_hanzi = task['data'].get("col_hanzi") or find_standard_column(df, '漢字')
        col_ipa = task['data'].get("col_ipa") or find_standard_column(df, '音標')

        # 4. 執行指令
        results, errors = 處理自定義編輯指令(df, col_hanzi, col_ipa, command_str)
        for idx, row in df.iterrows():
            ipa = str(row.get(col_ipa, "")).strip()
            if ipa:
                onset, rime, tone = extract_onset_rime_from_ipa(ipa)
                df.at[idx, '声母'] = onset
                df.at[idx, '韵母'] = rime
                df.at[idx, '声调'] = tone
        # 5. 決定儲存路徑 (根據 overwrite 參數)
        if request.overwrite:
            save_path = file_path
        else:
            save_path = file_path.parent / f"modified_{file_path.name}"

        df.to_excel(save_path, index=False)

        # 6. 更新任務資訊（確保更新時間戳，防止任務被清理）
        if not request.overwrite:
            task_manager.update_task(
                request.task_id,
                message=f"已執行指令，成功 {len(results)} 條，失敗 {len(errors)} 條",
                data={**task['data'], "modified_file_path": str(save_path)}
            )
        else:
            # 即使覆蓋原文件，也要更新任務時間戳
            task_manager.update_task(
                request.task_id,
                message=f"已執行指令，成功 {len(results)} 條，失敗 {len(errors)} 條"
            )

        return CommandResponse(
            success=len(errors) == 0,
            affected_rows=len(results),
            message=f"執行完成，成功 {len(results)} 條，失敗 {len(errors)} 條",
            logs=results + errors
        )

    except Exception as e:
        # 這裡統一回傳 CommandResponse 格式，保持前端處理邏輯一致
        return CommandResponse(
            success=False,
            affected_rows=0,
            message=f"執行失敗: {str(e)}",
            logs=[str(e)]
        )


@router.post("/save")
async def save_changes(request: SaveChangesRequest):
    """
    保存批量修改
    """
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        # 读取Excel
        df = pd.read_excel(file_path, dtype=str)
        col_ipa = task['data'].get("col_ipa") or find_standard_column(df, '音標')

        modified_ipa_rows = []  # 记录修改了IPA的行
        for modified_row in request.modified_rows:
            row_num = modified_row["row"]
            data = modified_row["data"]
            df_index = row_num - 2

            if 0 <= df_index < len(df):
                for key, value in data.items():
                    if key in df.columns:
                        df.at[df_index, key] = value
                        # 【新增】记录IPA修改
                        if key == col_ipa:
                            modified_ipa_rows.append(df_index)

        for idx in modified_ipa_rows:
            ipa = str(df.at[idx, col_ipa]).strip()
            if ipa:
                onset, rime, tone = extract_onset_rime_from_ipa(ipa)
                df.at[idx, '声母'] = onset
                df.at[idx, '韵母'] = rime
                df.at[idx, '声调'] = tone

        # 保存修改后的文件
        output_path = file_path.parent / f"modified_{file_path.name}"
        df.to_excel(output_path, index=False)

        # 更新任务信息（确保更新时间戳，防止任务被清理）
        task_manager.update_task(
            request.task_id,
            message=f"已保存{len(request.modified_rows)}处修改",
            data={
                **task['data'],
                "modified_file_path": str(output_path)
            }
        )

        return {
            "success": True,
            "message": f"成功保存{len(request.modified_rows)}处修改"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/download/{task_id}")
async def download_file(task_id: str):
    """
    下载结果文件
    """
    task = task_manager.get_task(task_id)
    if not task:
        # 尝试从文件路径恢复任务信息（如果文件还存在）
        # 检查可能的文件路径
        from .file_manager import file_manager
        task_dir = file_manager.get_task_dir(task_id, "check")
        possible_files = []
        if task_dir.exists():
            possible_files = list(task_dir.glob("*.xlsx"))
            possible_files.extend(list(task_dir.glob("modified_*.xlsx")))
        
        if possible_files:
            # 找到文件，尝试恢复任务
            file_path = possible_files[0]
            # 重新创建任务记录
            recovered_task_id = task_manager.create_task("check", {
                "filename": file_path.name,
                "file_path": str(file_path),
                "recovered": True
            })
            # 如果恢复的任务ID不同，说明原任务已彻底丢失
            if recovered_task_id != task_id:
                raise HTTPException(
                    status_code=404, 
                    detail="任务不存在。任务可能已过期（超过1小时未使用），请重新上传文件。"
                )
            task = task_manager.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404, 
                detail="任务不存在。任务可能已过期（超过1小时未使用），请重新上传文件。"
            )

    modified_path = task['data'].get("modified_file_path")
    if modified_path and Path(modified_path).exists():
        file_path = Path(modified_path)
    else:
        file_path = Path(task['data'].get("file_path"))

    file_path = file_path.resolve()

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 2. 准备下载文件名
    # 强制以 .xlsx 结尾
    filename_stem = Path(task['data'].get("filename", file_path.name)).stem
    download_filename = f"{filename_stem}.xlsx"
    encoded_filename = quote(download_filename)

    # 3. 定义文件读取生成器
    # 这是一个生成器函数，它会一点一点读取硬盘文件，防止大文件撑爆内存
    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    # 4. 返回流式响应
    # 这就是你想要的"明确返回 xlsx"
    # 我们发送的是"流"，不是"文件路径"，所以原本的文件名后缀完全失效，只有 Header 里的才是真理
    return StreamingResponse(
        iterfile(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"
        }
    )


@router.post("/get_data")
async def get_data(request: GetDataRequest):
    """
    获取表格数据（可选择只获取错误行或所有行）
    """
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        df = pd.read_excel(file_path, dtype=str)
        df = df.fillna("")

        # 获取列名
        col_hanzi = task['data'].get("col_hanzi") or find_standard_column(df, '漢字')
        col_ipa = task['data'].get("col_ipa") or find_standard_column(df, '音標')
        col_note = find_standard_column(df, '解釋')

        # 构建数据列表
        data_rows = []
        for idx, row in df.iterrows():
            row_data = {
                "row": idx + 2,  # Excel行号（从2开始）
                "char": str(row.get(col_hanzi, "")).strip(),
                "ipa": str(row.get(col_ipa, "")).strip(),
                "onset": str(row.get('声母', "")).strip(),  # 新增
                "rime": str(row.get('韵母', "")).strip(),  # 新增
                "tone": str(row.get('声调', "")).strip(),
                "note": str(row.get(col_note, "")).strip() if col_note else ""
            }

            data_rows.append(row_data)

        # 如果只需要错误行，进行筛选
        if not request.include_all:
            errors = task['data'].get("errors", [])
            error_rows = {e["row"] for e in errors}
            data_rows = [r for r in data_rows if r["row"] in error_rows]

        return {
            "success": True,
            "data": data_rows,
            "total": len(data_rows)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.post("/get_tone_stats")
async def get_tone_stats(request: GetDataRequest):
    """
    获取调值统计信息
    """
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        df = pd.read_excel(file_path, dtype=str)

        # 获取列名
        col_hanzi = task['data'].get("col_hanzi") or find_standard_column(df, '漢字')
        col_ipa = task['data'].get("col_ipa") or find_standard_column(df, '音標')

        # 调用核心函数获取调值统计
        tone_stats = 整理並顯示調值(df, col_hanzi, col_ipa)

        return {
            "success": True,
            "tone_stats": tone_stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取调值统计失败: {str(e)}")


@router.post("/update_row")
async def update_row(request: UpdateRowRequest):
    """
    更新单行数据
    """
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        df = pd.read_excel(file_path, dtype=str)
        df_index = request.row - 2  # Excel行号转DataFrame索引

        if df_index < 0 or df_index >= len(df):
            raise HTTPException(status_code=400, detail="行号超出范围")

        # 获取列名
        col_hanzi = task['data'].get("col_hanzi") or find_standard_column(df, '漢字')
        col_ipa = task['data'].get("col_ipa") or find_standard_column(df, '音標')
        col_note = find_standard_column(df, '解釋')

        # 更新数据
        col_map_update = {
            "char": col_hanzi,
            "ipa": col_ipa,
            "note": col_note
        }

        for key, value in request.data.items():
            col_name = col_map_update.get(key)
            if col_name and col_name in df.columns:
                df.at[df_index, col_name] = value
                # 【新增】如果修改了IPA，重新提取声韵
                if key == "ipa":
                    onset, rime, tone = extract_onset_rime_from_ipa(value)
                    df.at[df_index, '声母'] = onset
                    df.at[df_index, '韵母'] = rime
                    df.at[df_index, '声调'] = tone

        # 保存到原文件（立即生效）
        df.to_excel(file_path, index=False)

        # 更新任务信息（确保更新时间戳，防止任务被清理）
        task_manager.update_task(
            request.task_id,
            message=f"已更新第 {request.row} 行"
        )

        return {
            "success": True,
            "message": f"已更新第 {request.row} 行"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post("/batch_delete")
async def batch_delete(request: BatchDeleteRequest):
    """
    批量删除行

    Args:
        request: 包含task_id和要删除的行号列表

    Returns:
        删除结果
    """
    task = task_manager.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    file_path = Path(task['data'].get("file_path"))
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        df = pd.read_excel(file_path, dtype=str)

        # 转换Excel行号为DataFrame索引（Excel行号从2开始）
        df_indices = [row - 2 for row in request.rows if 0 <= row - 2 < len(df)]

        if not df_indices:
            raise HTTPException(status_code=400, detail="没有有效的行号")

        # 删除行
        df = df.drop(df_indices)

        # 重置索引
        df = df.reset_index(drop=True)

        # 保存修改后的文件
        df.to_excel(file_path, index=False)

        return {
            "success": True,
            "deleted_count": len(df_indices),
            "message": f"成功删除 {len(df_indices)} 行"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")
