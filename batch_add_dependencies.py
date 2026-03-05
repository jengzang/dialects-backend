#!/usr/bin/env python3
"""批量為路由添加依賴注入 - 簡化版"""
import re
from pathlib import Path

# 需要添加 get_current_admin_user 的文件
ADMIN_FILES = [
    "app/routes/admin/cache_manager.py",
    "app/routes/admin/custom.py",
    "app/routes/admin/custom_edit.py",
    "app/routes/admin/custom_regions.py",
    "app/routes/admin/custom_regions_edit.py",
    "app/routes/admin/get_ip.py",
    "app/routes/admin/leaderboard.py",
    "app/routes/admin/login_logs.py",
    "app/routes/admin/users.py",
    "app/routes/admin/user_stats.py",
]

# 需要添加 ApiLimiter 的文件
APILIMITER_FILES = [
    # 日誌統計
    "app/logs/logs_stats.py",
    "app/routes/logs/stats.py",
    "app/routes/logs/hourly_daily.py",
    # 工具
    "app/tools/check/check_routes.py",
    "app/tools/jyut2ipa/jyut2ipa_routes.py",
    "app/tools/merge/merge_routes.py",
    # VillagesML
    "app/tools/VillagesML/admin/run_ids.py",
    "app/tools/VillagesML/character/embeddings.py",
    "app/tools/VillagesML/character/frequency.py",
    "app/tools/VillagesML/character/significance.py",
    "app/tools/VillagesML/character/tendency.py",
    "app/tools/VillagesML/clustering/assignments.py",
    "app/tools/VillagesML/compute/clustering.py",
    "app/tools/VillagesML/metadata/stats.py",
    "app/tools/VillagesML/ngrams/frequency.py",
    "app/tools/VillagesML/regional/aggregates_deprecated.py",
    "app/tools/VillagesML/regional/aggregates_realtime.py",
    "app/tools/VillagesML/regional/batch_operations_code.py",
    "app/tools/VillagesML/regional/similarity.py",
    "app/tools/VillagesML/semantic/category.py",
    "app/tools/VillagesML/semantic/composition.py",
    "app/tools/VillagesML/semantic/labels.py",
    "app/tools/VillagesML/semantic/subcategories.py",
    "app/tools/VillagesML/spatial/hotspots.py",
    "app/tools/VillagesML/spatial/integration.py",
    "app/tools/VillagesML/village/data.py",
    "app/tools/VillagesML/village/search.py",
]


def ensure_imports(content: str, imports: list) -> str:
    """確保必要的導入存在"""
    lines = content.split('\n')

    # 找到最後一個 import 的位置
    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('from ') or stripped.startswith('import '):
            last_import_idx = i

    # 檢查並添加缺失的導入
    for imp in imports:
        if imp not in content:
            if last_import_idx >= 0:
                lines.insert(last_import_idx + 1, imp)
                last_import_idx += 1
            else:
                # 在文件開頭添加
                lines.insert(0, imp)

    return '\n'.join(lines)


def add_dependency_to_function(func_def: str, dependency: str) -> str:
    """在函數定義中添加依賴參數"""
    # 如果已經有這個依賴，跳過
    if dependency in func_def:
        return func_def

    # 找到函數參數的結束位置
    # 處理單行和多行函數定義
    if '):\n' in func_def or '):' in func_def:
        # 找到最後一個 ) 之前的位置
        close_paren_idx = func_def.rfind(')')
        before_paren = func_def[:close_paren_idx]
        after_paren = func_def[close_paren_idx:]

        # 檢查是否有參數
        open_paren_idx = before_paren.find('(')
        params_section = before_paren[open_paren_idx+1:].strip()

        if params_section:
            # 有參數，添加逗號和新參數
            # 檢查最後一行的縮進
            lines = before_paren.split('\n')
            if len(lines) > 1:
                # 多行函數定義
                last_line = lines[-1]
                indent = len(last_line) - len(last_line.lstrip())
                if not before_paren.rstrip().endswith(','):
                    before_paren = before_paren.rstrip() + ','
                new_func_def = before_paren + '\n' + ' ' * indent + dependency + after_paren
            else:
                # 單行函數定義
                new_func_def = before_paren + ', ' + dependency + after_paren
        else:
            # 沒有參數，直接添加
            new_func_def = before_paren + dependency + after_paren

        return new_func_def

    return func_def


def process_file(file_path: str, dependency_type: str) -> tuple:
    """處理單個文件

    Returns:
        (success: bool, modified_count: int, message: str)
    """
    path = Path(file_path)
    if not path.exists():
        return False, 0, f"文件不存在"

    try:
        content = path.read_text(encoding='utf-8')
        original_content = content

        # 添加必要的導入
        if dependency_type == "admin":
            imports = [
                "from app.auth.dependencies import get_current_admin_user",
                "from app.auth.models import User",
            ]
            if "from fastapi import" in content and "Depends" not in content:
                content = content.replace("from fastapi import", "from fastapi import Depends,", 1)
            dependency_param = "user: User = Depends(get_current_admin_user)"
        else:  # apilimiter
            imports = [
                "from app.logs.service.api_limiter import ApiLimiter",
                "from app.auth.models import User",
            ]
            if "from typing import" in content and "Optional" not in content:
                content = content.replace("from typing import", "from typing import Optional,", 1)
            if "from fastapi import" in content and "Depends" not in content:
                content = content.replace("from fastapi import", "from fastapi import Depends,", 1)
            dependency_param = "user: Optional[User] = Depends(ApiLimiter)"

        content = ensure_imports(content, imports)

        # 查找所有路由函數並添加依賴
        lines = content.split('\n')
        modified_count = 0
        i = 0

        while i < len(lines):
            line = lines[i]

            # 查找路由裝飾器
            if re.match(r'@router\.(get|post|put|delete|patch|options|head)\(', line.strip()):
                # 收集完整的函數定義（可能跨多行）
                func_start = i + 1
                while func_start < len(lines) and not lines[func_start].strip().startswith('def '):
                    func_start += 1

                if func_start < len(lines):
                    # 找到函數定義的結束（找到 ): ）
                    func_end = func_start
                    paren_count = 0
                    found_open = False

                    for j in range(func_start, min(func_start + 30, len(lines))):
                        for char in lines[j]:
                            if char == '(':
                                paren_count += 1
                                found_open = True
                            elif char == ')':
                                paren_count -= 1
                                if found_open and paren_count == 0:
                                    func_end = j
                                    break
                        if found_open and paren_count == 0:
                            break

                    # 提取函數定義
                    func_lines = lines[func_start:func_end + 1]
                    func_def = '\n'.join(func_lines)

                    # 檢查是否已經有依賴
                    if dependency_type == "admin":
                        has_dependency = 'Depends(get_current_admin_user)' in func_def
                    else:
                        has_dependency = 'Depends(ApiLimiter)' in func_def or 'Depends(api_limiter' in func_def

                    if not has_dependency:
                        # 添加依賴
                        new_func_def = add_dependency_to_function(func_def, dependency_param)
                        if new_func_def != func_def:
                            # 替換函數定義
                            new_func_lines = new_func_def.split('\n')
                            lines[func_start:func_end + 1] = new_func_lines
                            modified_count += 1
                            i = func_start + len(new_func_lines)
                            continue

                    i = func_end + 1
                else:
                    i += 1
            else:
                i += 1

        content = '\n'.join(lines)

        if content != original_content:
            path.write_text(content, encoding='utf-8')
            return True, modified_count, f"修改了 {modified_count} 個路由"
        else:
            return True, 0, "無需修改"

    except Exception as e:
        return False, 0, f"錯誤: {str(e)}"


def main():
    print("=" * 80)
    print("開始批量添加依賴注入")
    print("=" * 80)

    print("\n📋 處理管理員路由（添加 get_current_admin_user）...")
    admin_success = 0
    admin_modified = 0

    for file_path in ADMIN_FILES:
        success, count, msg = process_file(file_path, "admin")
        status = "✅" if success else "❌"
        print(f"{status} {file_path}: {msg}")
        if success:
            admin_success += 1
            admin_modified += count

    print(f"\n📋 處理其他路由（添加 ApiLimiter）...")
    api_success = 0
    api_modified = 0

    for file_path in APILIMITER_FILES:
        success, count, msg = process_file(file_path, "apilimiter")
        status = "✅" if success else "❌"
        print(f"{status} {file_path}: {msg}")
        if success:
            api_success += 1
            api_modified += count

    print("\n" + "=" * 80)
    print(f"完成！")
    print(f"- 管理員路由: {admin_success}/{len(ADMIN_FILES)} 個文件處理成功，修改了 {admin_modified} 個路由")
    print(f"- 其他路由: {api_success}/{len(APILIMITER_FILES)} 個文件處理成功，修改了 {api_modified} 個路由")
    print("=" * 80)


if __name__ == "__main__":
    main()
