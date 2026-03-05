#!/usr/bin/env python3
"""批量為路由添加依賴注入"""
import re
from pathlib import Path
from typing import List, Tuple

# 需要添加 get_current_admin_user 的文件（管理員路由）
ADMIN_FILES = [
    "app/routes/admin/api_usage.py",
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

# 需要添加 ApiLimiter 的文件（其他路由）
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


def add_import_if_missing(content: str, import_line: str) -> str:
    """如果導入語句不存在，則添加"""
    if import_line in content:
        return content

    # 找到最後一個 import 語句的位置
    import_pattern = r'^(from .+ import .+|import .+)$'
    lines = content.split('\n')
    last_import_idx = -1

    for i, line in enumerate(lines):
        if re.match(import_pattern, line.strip()):
            last_import_idx = i

    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1, import_line)
    else:
        # 如果沒有找到 import，在文件開頭添加
        lines.insert(0, import_line)

    return '\n'.join(lines)


def add_dependency_to_route(content: str, dependency_type: str) -> Tuple[str, int]:
    """為路由函數添加依賴注入

    Returns:
        (modified_content, count_of_modifications)
    """
    lines = content.split('\n')
    modified_count = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # 查找路由裝飾器
        if re.match(r'@router\.(get|post|put|delete|patch|options|head)\(', line):
            # 找到對應的函數定義（可能在下一行或幾行之後）
            func_line_idx = i + 1
            while func_line_idx < len(lines) and not lines[func_line_idx].strip().startswith('def '):
                func_line_idx += 1

            if func_line_idx < len(lines):
                func_line = lines[func_line_idx]

                # 檢查是否已經有依賴注入
                # 檢查接下來的幾行，看是否已經有 Depends
                next_lines = '\n'.join(lines[func_line_idx:min(func_line_idx + 10, len(lines))])

                if dependency_type == "admin":
                    if 'Depends(get_current_admin_user)' in next_lines:
                        i = func_line_idx + 1
                        continue
                    dependency_param = "user: User = Depends(get_current_admin_user)"
                else:  # apilimiter
                    if 'Depends(ApiLimiter)' in next_lines or 'Depends(api_limiter' in next_lines:
                        i = func_line_idx + 1
                        continue
                    dependency_param = "user: Optional[User] = Depends(ApiLimiter)"

                # 解析函數定義
                # 情況1: def func():
                # 情況2: def func(param1, param2):
                # 情況3: def func(\n    param1,\n    param2\n):

                # 找到函數參數的結束位置
                paren_count = 0
                start_paren_found = False
                end_line_idx = func_line_idx

                for j in range(func_line_idx, len(lines)):
                    for char in lines[j]:
                        if char == '(':
                            paren_count += 1
                            start_paren_found = True
                        elif char == ')':
                            paren_count -= 1
                            if start_paren_found and paren_count == 0:
                                end_line_idx = j
                                break
                    if start_paren_found and paren_count == 0:
                        break

                # 檢查函數是否有參數
                func_params_text = '\n'.join(lines[func_line_idx:end_line_idx + 1])

                # 提取函數名和參數部分
                func_match = re.search(r'def\s+(\w+)\s*\((.*?)\)', func_params_text, re.DOTALL)
                if func_match:
                    func_name = func_match.group(1)
                    params = func_match.group(2).strip()

                    # 如果沒有參數，直接添加
                    if not params:
                        new_func_line = func_line.replace('():', f'({dependency_param}):')
                        lines[func_line_idx] = new_func_line
                        modified_count += 1
                    else:
                        # 有參數，需要在最後添加
                        # 找到最後一個參數的位置
                        if end_line_idx == func_line_idx:
                            # 單行函數定義
                            new_func_line = func_line.replace('):', f', {dependency_param}):')
                            lines[func_line_idx] = new_func_line
                            modified_count += 1
                        else:
                            # 多行函數定義，在倒數第二行添加
                            # 找到最後一個參數所在的行
                            last_param_line_idx = end_line_idx - 1
                            while last_param_line_idx > func_line_idx and not lines[last_param_line_idx].strip():
                                last_param_line_idx -= 1

                            # 在最後一個參數後添加逗號和新參數
                            if not lines[last_param_line_idx].rstrip().endswith(','):
                                lines[last_param_line_idx] = lines[last_param_line_idx].rstrip() + ','

                            # 獲取縮進
                            indent = len(lines[last_param_line_idx]) - len(lines[last_param_line_idx].lstrip())
                            lines.insert(last_param_line_idx + 1, ' ' * indent + dependency_param)
                            modified_count += 1

                i = end_line_idx + 1
            else:
                i += 1
        else:
            i += 1

    return '\n'.join(lines), modified_count


def process_file(file_path: str, dependency_type: str) -> bool:
    """處理單個文件"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  文件不存在: {file_path}")
        return False

    try:
        content = path.read_text(encoding='utf-8')
        original_content = content

        # 添加必要的導入
        if dependency_type == "admin":
            content = add_import_if_missing(content, "from app.auth.dependencies import get_current_admin_user")
            content = add_import_if_missing(content, "from app.auth.models import User")
            content = add_import_if_missing(content, "from fastapi import Depends")
        else:  # apilimiter
            content = add_import_if_missing(content, "from app.logs.service.api_limiter import ApiLimiter")
            content = add_import_if_missing(content, "from app.auth.models import User")
            content = add_import_if_missing(content, "from fastapi import Depends")
            content = add_import_if_missing(content, "from typing import Optional")

        # 添加依賴注入
        content, modified_count = add_dependency_to_route(content, dependency_type)

        if content != original_content:
            path.write_text(content, encoding='utf-8')
            print(f"✅ {file_path}: 修改了 {modified_count} 個路由")
            return True
        else:
            print(f"⏭️  {file_path}: 無需修改")
            return False
    except Exception as e:
        print(f"❌ {file_path}: 錯誤 - {e}")
        return False


def main():
    print("=" * 80)
    print("開始批量添加依賴注入")
    print("=" * 80)

    admin_success = 0
    apilimiter_success = 0

    print("\n📋 處理管理員路由（添加 get_current_admin_user）...")
    for file_path in ADMIN_FILES:
        if process_file(file_path, "admin"):
            admin_success += 1

    print(f"\n📋 處理其他路由（添加 ApiLimiter）...")
    for file_path in APILIMITER_FILES:
        if process_file(file_path, "apilimiter"):
            apilimiter_success += 1

    print("\n" + "=" * 80)
    print(f"完成！")
    print(f"- 管理員路由: {admin_success}/{len(ADMIN_FILES)} 個文件已修改")
    print(f"- 其他路由: {apilimiter_success}/{len(APILIMITER_FILES)} 個文件已修改")
    print("=" * 80)


if __name__ == "__main__":
    main()
