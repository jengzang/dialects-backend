#!/usr/bin/env python3
"""
批量更新 common 导入语句为 app.common
"""
import os
import re
from pathlib import Path

def update_imports_in_file(file_path):
    """更新单个文件中的导入语句"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 替换 from app.common. 为 from app.common.
    content = re.sub(r'\bfrom common\.', 'from app.common.', content)

    # 替换 import app.common. 为 import app.common.
    content = re.sub(r'\bimport common\.', 'import app.common.', content)

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    base_dir = Path(__file__).parent.parent
    app_dir = base_dir / 'app'
    test_dir = base_dir / 'test'

    updated_files = []

    # 更新 app/ 目录
    for py_file in app_dir.rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue
        if update_imports_in_file(py_file):
            updated_files.append(py_file)

    # 更新 test/ 目录
    if test_dir.exists():
        for py_file in test_dir.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            if update_imports_in_file(py_file):
                updated_files.append(py_file)

    # 更新根目录的 Python 文件
    for py_file in base_dir.glob('*.py'):
        if update_imports_in_file(py_file):
            updated_files.append(py_file)

    print(f"Updated {len(updated_files)} files")
    for f in updated_files:
        print(f"   - {f.relative_to(base_dir)}")

if __name__ == '__main__':
    main()
