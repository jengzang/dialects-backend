"""
测试新增的 Analytics API
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

# 需要先登录获取 token
def login():
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",  # 替换为实际的管理员账号
        "password": "your_password"  # 替换为实际密码
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"登录失败: {response.status_code}")
        print(response.text)
        return None

def test_online_users(token):
    """测试实时在线用户 API"""
    print("\n=== 测试 GET /admin/user-sessions/online-users ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/admin/user-sessions/online-users",
        headers=headers,
        params={"threshold_minutes": 5}
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"在线用户数: {data['online_count']}")
        print(f"用户列表: {json.dumps(data['users'][:3], indent=2, ensure_ascii=False)}")  # 只显示前3个
    else:
        print(f"错误: {response.text}")

def test_analytics(token):
    """测试聚合统计 API"""
    print("\n=== 测试 GET /admin/user-sessions/analytics ===")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/admin/user-sessions/analytics",
        headers=headers,
        params={"days": 30}
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()

        print("\n--- 登录热力图 ---")
        print(f"按小时: {data['login_heatmap']['by_hour'][:5]}... (前5小时)")
        print(f"按星期: {data['login_heatmap']['by_weekday']}")

        print("\n--- 用户活跃度 ---")
        print(f"MAU: {data['user_activity']['mau']}")
        print(f"DAU 数据点数: {len(data['user_activity']['dau'])}")
        if data['user_activity']['dau']:
            print(f"最近一天: {data['user_activity']['dau'][-1]}")

        print("\n--- 设备分布 ---")
        print(json.dumps(data['device_distribution'], indent=2))

        print("\n--- 地理分布 (Top 5) ---")
        print(json.dumps(data['geo_distribution'][:5], indent=2, ensure_ascii=False))

        print("\n--- 会话时长分布 ---")
        print(json.dumps(data['session_duration_distribution'], indent=2))
    else:
        print(f"错误: {response.text}")

if __name__ == "__main__":
    print("请先确保服务器正在运行，并修改 login() 函数中的用户名和密码")
    print("然后取消下面的注释运行测试\n")

    # token = login()
    # if token:
    #     test_online_users(token)
    #     test_analytics(token)

    print("\n提示：如果你已经有 token，可以直接设置：")
    print("token = 'your_token_here'")
    print("test_online_users(token)")
    print("test_analytics(token)")
