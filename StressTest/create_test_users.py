"""
创建测试用户的辅助脚本
Helper script to create test users

使用方法:
    python create_test_users.py
"""

import requests
import sys
from config import BASE_URL, TEST_USERS, ADMIN_USER


def create_user(username, password, email, is_admin=False):
    """创建单个用户"""
    url = f"{BASE_URL}/auth/register"
    data = {
        "username": username,
        "password": password,
        "email": email
    }

    try:
        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            print(f"✓ 用户 {username} 创建成功")
            return True
        elif response.status_code == 400:
            error = response.json().get("detail", "未知错误")
            if "already exists" in error.lower() or "已存在" in error:
                print(f"⚠ 用户 {username} 已存在")
                return True
            else:
                print(f"✗ 创建用户 {username} 失败: {error}")
                return False
        else:
            print(f"✗ 创建用户 {username} 失败: HTTP {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接到服务器: {BASE_URL}")
        print("  请确认 FastAPI 应用已启动")
        return False
    except Exception as e:
        print(f"✗ 创建用户 {username} 时出错: {e}")
        return False


def main():
    print("="*60)
    print("创建压力测试用户")
    print("="*60)
    print(f"目标服务器: {BASE_URL}")
    print()

    # 检查服务器连接
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print("✓ 服务器连接正常")
    except:
        print("✗ 无法连接到服务器")
        print(f"  请确认 FastAPI 应用已在 {BASE_URL} 启动")
        sys.exit(1)

    print()
    print(f"将创建 {len(TEST_USERS)} 个测试用户...")
    print()

    success_count = 0
    fail_count = 0

    # 创建普通测试用户
    for i, user in enumerate(TEST_USERS, 1):
        username = user["username"]
        password = user["password"]
        email = f"{username}@test.com"

        print(f"[{i}/{len(TEST_USERS)}] 创建用户: {username}")

        if create_user(username, password, email):
            success_count += 1
        else:
            fail_count += 1

    # 创建管理员用户（如果配置了）
    if ADMIN_USER and ADMIN_USER.get("username"):
        print()
        print("创建管理员用户...")
        admin_username = ADMIN_USER["username"]
        admin_password = ADMIN_USER["password"]
        admin_email = f"{admin_username}@admin.com"

        if create_user(admin_username, admin_password, admin_email, is_admin=True):
            success_count += 1
            print("⚠ 注意: 需要手动在数据库中将该用户设置为管理员")
        else:
            fail_count += 1

    # 打印摘要
    print()
    print("="*60)
    print("创建完成")
    print("="*60)
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print()

    if fail_count == 0:
        print("✓ 所有用户创建成功！现在可以运行压力测试了")
        print()
        print("下一步:")
        print("  1. 运行 run_test.bat 开始压力测试")
        print("  2. 或运行 locust -f locustfile.py --host", BASE_URL)
    else:
        print("⚠ 部分用户创建失败，请检查错误信息")

    print()


if __name__ == "__main__":
    main()
