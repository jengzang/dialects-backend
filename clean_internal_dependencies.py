#!/usr/bin/env python3
"""刪除路由函數內部的依賴注入參數"""
import re
from pathlib import Path

FILES_TO_CLEAN = [
    "app/routes/admin/custom_edit.py",
    "app/routes/admin/users.py",
    "app/routes/compare.py",
    "app/routes/geo/batch_match.py",
    "app/routes/geo/get_coordinates.py",
    "app/routes/geo/get_locs.py",
    "app/routes/geo/get_partitions.py",
    "app/routes/geo/get_regions.py",
    "app/routes/new_pho.py",
    "app/routes/phonology.py",
    "app/routes/search.py",
    "app/routes/user/custom.py",
    "app/routes/user/custom_query.py",
    "app/routes/user/custom_regions.py",
    "app/routes/user/form_submit.py",
    "app/sql/sql_routes.py",
    "app/sql/sql_tree_routes.py",
    "app/tools/VillagesML/admin/run_ids.py",
    "app/tools/VillagesML/compute/clustering.py",
    "app/tools/VillagesML/compute/features.py",
    "app/tools/VillagesML/compute/semantic.py",
    "app/tools/VillagesML/compute/subset.py",
    "app/tools/praat/routes.py",
]


def remove_dependency_params(content: str) -> tuple:
    """刪除依賴注入參數

    Returns:
        (modified_content, count_of_removals)
    """
    original_content = content
    removed_count = 0

    # 模式1: user: Optional[User] = Depends(get_current_user)
    # 模式2: user: User = Depends(get_current_admin_user)
    # 模式3: user: Optional[User] = Depends(ApiLimiter)
    # 模式4: current_user: Optional[User] = Depends(get_current_user)

    patterns = [
        # 單行參數
        r',\s*\n?\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(get_current_user\)',
        r',\s*\n?\s*\w+:\s*User\s*=\s*Depends\(get_current_admin_user\)',
        r',\s*\n?\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(ApiLimiter\)',
        r',\s*\n?\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(api_limiter\)',
        # 多行參數（帶換行和縮進）
        r',\s*\n\s+\w+:\s*Optional\[User\]\s*=\s*Depends\(get_current_user\)',
        r',\s*\n\s+\w+:\s*User\s*=\s*Depends\(get_current_admin_user\)',
        r',\s*\n\s+\w+:\s*Optional\[User\]\s*=\s*Depends\(ApiLimiter\)',
        r',\s*\n\s+\w+:\s*Optional\[User\]\s*=\s*Depends\(api_limiter\)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content)
        if matches:
            removed_count += len(matches)
            content = re.sub(pattern, '', content)

    # 處理函數定義開頭的依賴參數（沒有前面的逗號）
    patterns_first_param = [
        r'\(\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(get_current_user\)\s*,',
        r'\(\s*\w+:\s*User\s*=\s*Depends\(get_current_admin_user\)\s*,',
        r'\(\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(ApiLimiter\)\s*,',
        r'\(\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(api_limiter\)\s*,',
    ]

    for pattern in patterns_first_param:
        matches = re.findall(pattern, content)
        if matches:
            removed_count += len(matches)
            content = re.sub(pattern, '(', content)

    # 處理函數定義中唯一的參數（前後都沒有逗號）
    patterns_only_param = [
        r'\(\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(get_current_user\)\s*\)',
        r'\(\s*\w+:\s*User\s*=\s*Depends\(get_current_admin_user\)\s*\)',
        r'\(\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(ApiLimiter\)\s*\)',
        r'\(\s*\w+:\s*Optional\[User\]\s*=\s*Depends\(api_limiter\)\s*\)',
    ]

    for pattern in patterns_only_param:
        matches = re.findall(pattern, content)
        if matches:
            removed_count += len(matches)
            content = re.sub(pattern, '()', content)

    return content, removed_count


def clean_file(file_path: str) -> tuple:
    """清理單個文件

    Returns:
        (success: bool, removed_count: int, message: str)
    """
    path = Path(file_path)
    if not path.exists():
        return False, 0, "文件不存在"

    try:
        content = path.read_text(encoding='utf-8')
        new_content, removed_count = remove_dependency_params(content)

        if new_content != content:
            path.write_text(new_content, encoding='utf-8')
            return True, removed_count, f"刪除了 {removed_count} 個依賴參數"
        else:
            return True, 0, "無需修改"
    except Exception as e:
        return False, 0, f"錯誤: {str(e)}"


def main():
    print("=" * 80)
    print("開始清理路由函數內部的依賴注入")
    print("=" * 80)

    total_success = 0
    total_removed = 0

    for file_path in FILES_TO_CLEAN:
        success, count, msg = clean_file(file_path)
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {file_path}: {msg}")
        if success:
            total_success += 1
            total_removed += count

    print("\n" + "=" * 80)
    print(f"完成！")
    print(f"- 處理成功: {total_success}/{len(FILES_TO_CLEAN)} 個文件")
    print(f"- 刪除參數: {total_removed} 個")
    print("=" * 80)


if __name__ == "__main__":
    main()
