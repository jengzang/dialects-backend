"""
全面检查所有路由文件中使用 user 但没有声明参数的函数
"""
import os
import re

def check_file_for_user_usage(filepath):
    """检查文件中使用 user 但没有声明参数的路由函数"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return []

    issues = []

    # 查找所有函数定义（包括跨多行的参数）
    # 匹配 @router.xxx 装饰器后的函数定义
    pattern = r'(@router\.(get|post|put|delete|patch)\([^\)]*\))\s*\n\s*(async\s+)?def\s+(\w+)\s*\('

    matches = list(re.finditer(pattern, content, re.MULTILINE))

    for i, match in enumerate(matches):
        decorator = match.group(1)
        method = match.group(2)
        func_name = match.group(4)
        func_start = match.start()

        # 找到函数定义的结束位置（找到 ): 或 ) -> 或 ):）
        # 从函数名后的 ( 开始查找
        paren_start = match.end()

        # 找到匹配的右括号
        paren_count = 1
        params_end = paren_start
        for j in range(paren_start, len(content)):
            if content[j] == '(':
                paren_count += 1
            elif content[j] == ')':
                paren_count -= 1
                if paren_count == 0:
                    params_end = j
                    break

        # 提取参数部分
        params = content[paren_start:params_end]

        # 检查参数中是否有 user
        has_user_param = re.search(r'\buser\s*:', params) is not None

        # 找到函数体（到下一个 @router 或文件结尾）
        if i + 1 < len(matches):
            func_body = content[func_start:matches[i+1].start()]
        else:
            func_body = content[func_start:]

        # 检查函数体中是否使用了 user（排除注释）
        # 移除注释行
        func_body_lines = []
        for line in func_body.split('\n'):
            # 移除 # 后的内容
            if '#' in line:
                line = line[:line.index('#')]
            func_body_lines.append(line)
        func_body_no_comments = '\n'.join(func_body_lines)

        # 检查是否使用了 user
        uses_user = (
            re.search(r'\buser\s*\.(role|id|username|email|is_verified)', func_body_no_comments) or
            re.search(r'\buser\s+(and|or)\s+', func_body_no_comments) or
            re.search(r'\buser\s*,', func_body_no_comments) or  # user 作为参数传递
            re.search(r'\(.*\buser\s*\)', func_body_no_comments) or  # user 在括号中
            re.search(r'=\s*user\b', func_body_no_comments)  # user 被赋值
        )

        if uses_user and not has_user_param:
            # 找到函数定义的行号
            line_num = content[:func_start].count('\n') + 1
            issues.append({
                'file': filepath,
                'function': func_name,
                'line': line_num,
                'method': method,
                'decorator': decorator
            })

    return issues

# 扫描所有路由文件
all_issues = []
route_files = [
    'app/routes/admin/analytics.py',
    'app/routes/admin/users.py',
    'app/routes/admin/user_stats.py',
    'app/routes/admin/custom.py',
    'app/routes/admin/custom_edit.py',
    'app/routes/admin/sessions.py',
    'app/routes/admin/user_sessions.py',
    'app/routes/admin/permissions.py',
    'app/routes/admin/leaderboard.py',
    'app/routes/admin/login_logs.py',
    'app/routes/admin/api_usage.py',
    'app/routes/admin/cache_manager.py',
    'app/routes/admin/get_ip.py',
    'app/routes/admin/custom_regions.py',
    'app/routes/admin/custom_regions_edit.py',
    'app/routes/user/custom.py',
    'app/routes/user/custom_query.py',
    'app/routes/user/custom_regions.py',
    'app/routes/user/form_submit.py',
    'app/routes/auth.py',
    'app/routes/phonology.py',
    'app/routes/compare.py',
    'app/routes/search.py',
    'app/routes/new_pho.py',
    'app/routes/geo/batch_match.py',
    'app/routes/geo/get_locs.py',
    'app/routes/geo/get_coordinates.py',
    'app/routes/geo/get_regions.py',
    'app/routes/geo/get_partitions.py',
    'app/routes/logging/stats.py',
    'app/routes/logging/hourly_daily.py',
]

for filepath in route_files:
    if os.path.exists(filepath):
        issues = check_file_for_user_usage(filepath)
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

# 列出所有受影响的文件
if all_issues:
    print("\n受影响的文件列表：")
    for filepath in sorted(by_file.keys()):
        print(f"  - {filepath} ({len(by_file[filepath])} 个函数)")
