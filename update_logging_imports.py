#!/usr/bin/env python3
"""批量更新導入路徑：logs → logging"""
import re
from pathlib import Path

# 需要更新的路徑映射
PATH_MAPPINGS = {
    'from app.logs.database import': 'from app.logging.core.database import',
    'from app.logs.models import': 'from app.logging.core.models import',
    'from app.logs.service.api_logger import': 'from app.logging.middleware.traffic_logging import',
    'from app.logs.service.api_limit_keyword import': 'from app.logging.middleware.params_logging import',
    'from app.logs.service.api_limiter import': 'from app.logging.dependencies.limiter import',
    'from app.logs.service.route_matcher import': 'from app.logging.utils.route_matcher import',
    'from app.logs.scheduler import': 'from app.logging.tasks.scheduler import',
    'from app.logs import': 'from app.logging import',
    'import app.logs.': 'import app.logging.',
    'app.logs.': 'app.logging.',
}

def update_file(file_path: Path) -> tuple:
    """更新單個文件的導入路徑"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        # 應用所有路徑映射
        for old_path, new_path in PATH_MAPPINGS.items():
            content = content.replace(old_path, new_path)

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, "已更新"
        else:
            return True, "無需更新"
    except Exception as e:
        return False, f"錯誤: {e}"

def main():
    print("=" * 80)
    print("開始更新導入路徑")
    print("=" * 80)

    # 需要掃描的目錄
    directories = [
        Path("app"),
    ]

    updated_count = 0
    total_count = 0

    for directory in directories:
        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            total_count += 1
            success, msg = update_file(py_file)

            if success and msg == "已更新":
                print(f"[OK] {py_file}: {msg}")
                updated_count += 1

    print("\n" + "=" * 80)
    print(f"完成！")
    print(f"- 掃描文件: {total_count} 個")
    print(f"- 更新文件: {updated_count} 個")
    print("=" * 80)

if __name__ == "__main__":
    main()
