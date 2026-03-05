"""
查找所有路由文件中使用 user 但没有声明参数的函数
"""
import os
import re

def find_function_with_user_usage(filepath):
    """查找文件中使用 user 但没有声明参数的路由函数"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []

    # 查找所有 @router 装饰的函数
    pattern = r'@router\.(get|post|put|delete|patch)\([^)]+\)\s*\n\s*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\):'

    for match in re.finditer(pattern, content, re.MULTILINE):
        method = match.group(1)
        func_name = match.group(2)
        params = match.group(3)
        func_start = match.start()

        # 检查参数中是否有 user
        has_user_param = 'user' in params.split(',')

        # 查找函数体（简单方法：找到下一个 @router 或文件结尾）
        next_decorator = content.find('@router.', func_start + 1)
        if next_decorator == -1:
            func_body = content[func_start:]
        else:
            func_body = content[func_start:next_decorator]

        # 检查函数体中是否使用了 user
        # 匹配 user.xxx 或 user and/or
        uses_user = bool(re.search(r'\buser\s*\.(role|id|username)', func_body) or
                        re.search(r'\buser\s+(and|or)\s+', func_body))

        if uses_user and not has_user_param:
            # 找到函数定义的行号
            line_num = content[:func_start].count('\n') + 1
            issues.append({
                'file': filepath,
                'function': func_name,
                'line': line_num,
                'method': method
            })

    return issues

# 扫描所有路由文件
all_issues = []
for root, dirs, files in os.walk('app/routes'):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            filepath = os.path.join(root, file)
            issues = find_function_with_user_usage(filepath)
            all_issues.extend(issues)

print(f"找到 {len(all_issues)} 个需要修复的函数：\n")
print("=" * 80)

# 按文件分组
from collections import defaultdict
by_file = defaultdict(list)
for issue in all_issues:
    by_file[issue['file']].append(issue)

for filepath, issues in sorted(by_file.items()):
    print(f"\n文件: {filepath}")
    print("-" * 80)
    for issue in issues:
        print(f"  行 {issue['line']}: {issue['function']}() [@router.{issue['method']}]")

print("\n" + "=" * 80)
print(f"总计: {len(all_issues)} 个函数需要添加 user 参数")
