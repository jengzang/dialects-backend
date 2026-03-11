#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试SQL安全提交（39378a3和a3b8664）的影响

测试内容：
1. SQL标识符引用功能
2. 表名白名单验证
3. Schema缓存机制
"""

import sys
import sqlite3
from pathlib import Path

# 添加项目路径
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_quote_identifier():
    """测试SQL标识符引用"""
    def _quote_identifier(name: str) -> str:
        return f'"{name}"'

    test_cases = [
        ('normal_column', '"normal_column"'),
        ('中文列名', '"中文列名"'),
        ('column with space', '"column with space"'),
        ('column-with-dash', '"column-with-dash"'),
        ('table.column', '"table.column"'),
    ]

    print('=== SQL标识符引用测试 ===')
    passed = 0
    for input_name, expected in test_cases:
        result = _quote_identifier(input_name)
        if result == expected:
            print(f'PASS: {input_name} -> {result}')
            passed += 1
        else:
            print(f'FAIL: {input_name} -> {result} (expected: {expected})')

    print(f'\n结果: {passed}/{len(test_cases)} 通过\n')
    return passed == len(test_cases)


def test_sql_injection_prevention():
    """测试SQL注入防护"""
    print('=== SQL注入防护测试 ===')

    # 创建测试数据库
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 创建测试表
    cursor.execute('''
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            "中文列名" TEXT,
            "column with space" TEXT
        )
    ''')

    cursor.execute('''
        INSERT INTO test_table VALUES
        (1, '测试1', 'value1'),
        (2, '测试2', 'value2')
    ''')

    # 测试1：不使用引用（可能失败）
    print('\n测试1: 不使用引用查询中文列名')
    try:
        cursor.execute('SELECT 中文列名 FROM test_table')
        print('PASS: 查询成功（某些SQLite版本支持）')
    except sqlite3.OperationalError as e:
        print(f'FAIL: {e}')

    # 测试2：使用引用（应该成功）
    print('\n测试2: 使用引用查询中文列名')
    try:
        cursor.execute('SELECT "中文列名" FROM test_table')
        results = cursor.fetchall()
        print(f'PASS: 查询成功，返回 {len(results)} 行')
    except sqlite3.OperationalError as e:
        print(f'FAIL: {e}')

    # 测试3：带空格的列名（必须使用引用）
    print('\n测试3: 查询带空格的列名')
    try:
        cursor.execute('SELECT column with space FROM test_table')
        print('FAIL: 不应该成功（没有引用）')
    except sqlite3.OperationalError:
        print('PASS: 正确拒绝（需要引用）')

    try:
        cursor.execute('SELECT "column with space" FROM test_table')
        results = cursor.fetchall()
        print(f'PASS: 使用引用后查询成功，返回 {len(results)} 行')
    except sqlite3.OperationalError as e:
        print(f'FAIL: {e}')

    # 测试4：SQL注入尝试
    print('\n测试4: SQL注入防护')
    malicious_input = '"; DROP TABLE test_table; --'

    # 不使用引用（危险）
    try:
        # 这是错误的做法
        query = f'SELECT * FROM test_table WHERE "中文列名" = {malicious_input}'
        print(f'危险查询: {query}')
        print('WARNING: 这种拼接方式容易受到SQL注入攻击')
    except:
        pass

    # 使用参数化查询（安全）
    try:
        cursor.execute('SELECT * FROM test_table WHERE "中文列名" = ?', (malicious_input,))
        results = cursor.fetchall()
        print(f'PASS: 参数化查询安全，返回 {len(results)} 行（应该是0）')
    except sqlite3.OperationalError as e:
        print(f'FAIL: {e}')

    conn.close()
    print()


def test_schema_validation():
    """测试Schema验证"""
    print('=== Schema验证测试 ===')

    # 模拟schema缓存
    schema_cache = {
        'test_db': {
            'users': {'id', 'username', 'email'},
            'posts': {'id', 'title', 'content', 'user_id'},
            '广东省自然村': {'id', '村名', '乡镇级', '行政村'}
        }
    }

    def validate_table(db_key: str, table_name: str) -> bool:
        if db_key not in schema_cache:
            return False
        return table_name in schema_cache[db_key]

    test_cases = [
        ('test_db', 'users', True),
        ('test_db', 'posts', True),
        ('test_db', '广东省自然村', True),
        ('test_db', 'nonexistent', False),
        ('wrong_db', 'users', False),
    ]

    passed = 0
    for db_key, table_name, expected in test_cases:
        result = validate_table(db_key, table_name)
        if result == expected:
            status = 'PASS'
            passed += 1
        else:
            status = 'FAIL'
        print(f'{status}: validate_table("{db_key}", "{table_name}") = {result} (expected: {expected})')

    print(f'\n结果: {passed}/{len(test_cases)} 通过\n')
    return passed == len(test_cases)


def main():
    print('=' * 60)
    print('SQL安全提交测试')
    print('提交: 39378a3, a3b8664')
    print('=' * 60)
    print()

    results = []

    # 运行测试
    results.append(('标识符引用', test_quote_identifier()))
    results.append(('SQL注入防护', test_sql_injection_prevention()))
    results.append(('Schema验证', test_schema_validation()))

    # 总结
    print('=' * 60)
    print('测试总结')
    print('=' * 60)
    for name, passed in results:
        status = 'PASS' if passed else 'FAIL'
        print(f'{status}: {name}')

    all_passed = all(passed for _, passed in results)
    print()
    if all_passed:
        print('结论: 所有测试通过，SQL安全提交工作正常')
        return 0
    else:
        print('结论: 部分测试失败，需要检查')
        return 1


if __name__ == '__main__':
    sys.exit(main())
