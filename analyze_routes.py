#!/usr/bin/env python3
"""分析所有路由的权限检查使用情况"""
import os
import re
from pathlib import Path
from collections import defaultdict

routes_dir = Path("app")

# 统计数据
stats = {
    'total': 0,
    'with_apilimiter': [],
    'with_admin_user': [],
    'with_current_user': [],
    'without_depends': [],
}

route_pattern = re.compile(r'@router\.(get|post|put|delete|patch|options|head)\(["\']([^"\']+)')

for py_file in routes_dir.rglob("*.py"):
    if py_file.name == "__init__.py":
        continue

    try:
        content = py_file.read_text(encoding='utf-8')
        lines = content.split('\n')

        for i, line in enumerate(lines):
            match = route_pattern.search(line)
            if match:
                method = match.group(1)
                path = match.group(2)

                # 检查接下来的 15 行
                next_lines = '\n'.join(lines[i:min(i+15, len(lines))])

                route_info = f"{method.upper():6} {path:50} ({py_file.relative_to('app')})"
                stats['total'] += 1

                if 'Depends(ApiLimiter)' in next_lines or 'Depends(api_limiter' in next_lines:
                    stats['with_apilimiter'].append(route_info)
                elif 'Depends(get_current_admin_user)' in next_lines:
                    stats['with_admin_user'].append(route_info)
                elif 'Depends(get_current_user)' in next_lines:
                    stats['with_current_user'].append(route_info)
                else:
                    stats['without_depends'].append(route_info)
    except Exception as e:
        print(f"Error processing {py_file}: {e}")

# 输出统计结果到文件
output_file = "route_analysis_report.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=" * 100 + "\n")
    f.write("路由权限检查统计\n")
    f.write("=" * 100 + "\n\n")
    f.write(f"总路由数: {stats['total']}\n\n")
    f.write(f"1. 使用 ApiLimiter (限流 + 可选登录): {len(stats['with_apilimiter'])} ({len(stats['with_apilimiter'])/stats['total']*100:.1f}%)\n")
    f.write(f"2. 使用 get_current_admin_user (强制管理员): {len(stats['with_admin_user'])} ({len(stats['with_admin_user'])/stats['total']*100:.1f}%)\n")
    f.write(f"3. 使用 get_current_user (强制登录): {len(stats['with_current_user'])} ({len(stats['with_current_user'])/stats['total']*100:.1f}%)\n")
    f.write(f"4. 没有权限检查: {len(stats['without_depends'])} ({len(stats['without_depends'])/stats['total']*100:.1f}%)\n")

    f.write("\n" + "=" * 100 + "\n")
    f.write("使用 get_current_user 的路由（建议改用 ApiLimiter）:\n")
    f.write("=" * 100 + "\n")
    for route in stats['with_current_user']:
        f.write(route + "\n")

    f.write("\n" + "=" * 100 + "\n")
    f.write("没有权限检查的路由（完整列表）:\n")
    f.write("=" * 100 + "\n")
    for route in stats['without_depends']:
        f.write(route + "\n")

print(f"分析完成！报告已保存到: {output_file}")
print(f"\n总路由数: {stats['total']}")
print(f"- 使用 ApiLimiter: {len(stats['with_apilimiter'])} ({len(stats['with_apilimiter'])/stats['total']*100:.1f}%)")
print(f"- 使用 get_current_admin_user: {len(stats['with_admin_user'])} ({len(stats['with_admin_user'])/stats['total']*100:.1f}%)")
print(f"- 使用 get_current_user: {len(stats['with_current_user'])} ({len(stats['with_current_user'])/stats['total']*100:.1f}%)")
print(f"- 没有权限检查: {len(stats['without_depends'])} ({len(stats['without_depends'])/stats['total']*100:.1f}%)")
print(f"\n建议修改的路由数: {len(stats['with_current_user'])} 个（从 get_current_user 改为 ApiLimiter）")

