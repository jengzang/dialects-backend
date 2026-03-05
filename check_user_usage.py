#!/usr/bin/env python3
"""檢查路由函數中使用 user 但沒有參數的情況"""
import re
from pathlib import Path

def check_file(file_path: Path) -> list:
    """檢查單個文件"""
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        issues = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # 查找路由裝飾器
            if re.match(r'@router\.(get|post|put|delete|patch)', line):
                # 找到函數定義
                func_start = i + 1
                while func_start < len(lines) and not lines[func_start].strip().startswith('def '):
                    func_start += 1

                if func_start < len(lines):
                    # 收集函數定義（可能多行）
                    func_def_lines = [lines[func_start]]
                    j = func_start + 1
                    while j < len(lines) and not lines[j].strip().startswith('):'):
                        func_def_lines.append(lines[j])
                        j += 1
                    if j < len(lines):
                        func_def_lines.append(lines[j])

                    func_def = '\n'.join(func_def_lines)

                    # 檢查函數定義中是否有 user 參數
                    has_user_param = 'user:' in func_def or 'user =' in func_def or 'current_user' in func_def

                    # 查找函數體（接下來的 50 行）
                    func_body_end = min(j + 50, len(lines))
                    func_body = '\n'.join(lines[j:func_body_end])

                    # 檢查函數體中是否使用 user
                    uses_user = (
                        'user.' in func_body or
                        'user[' in func_body or
                        'if user' in func_body or
                        'user.id' in func_body or
                        'user.role' in func_body or
                        'user.username' in func_body or
                        'current_user.' in func_body or
                        'current_user.id' in func_body
                    )

                    if uses_user and not has_user_param:
                        # 提取函數名
                        func_name_match = re.search(r'def\s+(\w+)', func_def)
                        func_name = func_name_match.group(1) if func_name_match else 'unknown'

                        issues.append({
                            'file': str(file_path),
                            'line': func_start + 1,
                            'function': func_name,
                            'route': line.strip()
                        })

                    i = func_body_end
                else:
                    i += 1
            else:
                i += 1

        return issues
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return []

def main():
    print("=" * 80)
    print("檢查路由函數中使用 user 但沒有參數的情況")
    print("=" * 80)

    directories = [
        Path("app/routes"),
        Path("app/sql"),
        Path("app/tools"),
    ]

    all_issues = []

    for directory in directories:
        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            issues = check_file(py_file)
            all_issues.extend(issues)

    if all_issues:
        print(f"\n發現 {len(all_issues)} 個潛在問題：\n")
        for issue in all_issues:
            print(f"文件: {issue['file']}")
            print(f"行號: {issue['line']}")
            print(f"函數: {issue['function']}")
            print(f"路由: {issue['route']}")
            print("-" * 80)
    else:
        print("\n✓ 沒有發現問題")

    print("\n" + "=" * 80)
    print(f"總計: {len(all_issues)} 個問題")
    print("=" * 80)

if __name__ == "__main__":
    main()
