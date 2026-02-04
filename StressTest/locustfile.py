"""
FastAPI 方言数据库压力测试脚本
使用 Locust 进行压力测试

安装依赖:
    pip install locust

运行方式:
    # Web UI 模式（推荐）
    locust -f locustfile.py --host http://localhost:5000

    # 无头模式（命令行）
    locust -f locustfile.py --host http://localhost:5000 --headless -u 50 -r 5 -t 5m

    # 查看实时统计
    浏览器访问: http://localhost:8089
"""

from locust import HttpUser, task, between, events
import random
import json
import time
from config import (
    TEST_USERS, ADMIN_USER, TEST_CHARACTERS, TEST_LOCATIONS,
    TEST_REGIONS, ENDPOINT_WEIGHTS, WAIT_TIME_MIN, WAIT_TIME_MAX,
    RESPONSE_TIME_THRESHOLD, VERBOSE_LOGGING
)


class DialectAPIUser(HttpUser):
    """模拟普通用户行为"""

    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)

    def on_start(self):
        """用户启动时执行：登录获取 token"""
        # 随机选择一个测试用户
        user = random.choice(TEST_USERS)
        self.username = user["username"]

        response = self.client.post("/auth/login", json={
            "username": user["username"],
            "password": user["password"]
        })

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
            if VERBOSE_LOGGING:
                print(f"✓ 用户 {self.username} 登录成功")
        else:
            self.token = None
            self.headers = {}
            print(f"✗ 用户 {self.username} 登录失败: {response.status_code}")

    @task(ENDPOINT_WEIGHTS["search_chars"])
    def search_characters(self):
        """测试字符搜索端点 - 最常用的功能"""
        char = random.choice(TEST_CHARACTERS)
        params = {
            "char": char,
            "limit": random.choice([10, 20, 50]),
            "offset": 0
        }

        with self.client.get(
            "/api/search_chars/",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/api/search_chars/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(ENDPOINT_WEIGHTS["phonology"])
    def phonology_analysis(self):
        """测试音韵分析端点 - CPU 密集型操作"""
        test_data = {
            "characters": random.sample(TEST_CHARACTERS, k=random.randint(1, 3)),
            "locations": random.sample(TEST_LOCATIONS, k=random.randint(1, 2))
        }

        with self.client.post(
            "/api/phonology",
            json=test_data,
            headers=self.headers,
            catch_response=True,
            name="/api/phonology"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.elapsed.total_seconds() * 1000 > RESPONSE_TIME_THRESHOLD["timeout"]:
                response.failure(f"超时: {response.elapsed.total_seconds():.2f}s")
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(ENDPOINT_WEIGHTS["get_locs"])
    def get_locations(self):
        """测试获取地点列表"""
        params = {
            "region": random.choice(TEST_REGIONS + [None]),
            "limit": random.choice([20, 50, 100])
        }

        with self.client.get(
            "/api/get_locs/",
            params={k: v for k, v in params.items() if v is not None},
            headers=self.headers,
            catch_response=True,
            name="/api/get_locs/"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(ENDPOINT_WEIGHTS["get_coordinates"])
    def get_coordinates(self):
        """测试获取坐标数据"""
        params = {
            "location": random.choice(TEST_LOCATIONS),
            "char": random.choice(TEST_CHARACTERS)
        }

        with self.client.get(
            "/api/get_coordinates",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/api/get_coordinates"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(ENDPOINT_WEIGHTS["get_regions"])
    def get_regions(self):
        """测试获取区域列表"""
        with self.client.get(
            "/api/get_regions",
            headers=self.headers,
            catch_response=True,
            name="/api/get_regions"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(ENDPOINT_WEIGHTS["custom_query"])
    def custom_query(self):
        """测试自定义查询"""
        params = {
            "query_type": random.choice(["location", "character", "region"]),
            "keyword": random.choice(TEST_CHARACTERS + TEST_LOCATIONS)
        }

        with self.client.get(
            "/api/get_custom",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/api/get_custom"
        ) as response:
            if response.status_code in [200, 404]:  # 404 也是正常的（没有数据）
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")


class AnonymousUser(HttpUser):
    """模拟匿名用户（未登录）"""

    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)
    weight = 3  # 匿名用户占比 30%

    @task(50)
    def search_chars_anonymous(self):
        """匿名用户搜索字符"""
        char = random.choice(TEST_CHARACTERS)
        params = {"char": char, "limit": 10}

        with self.client.get(
            "/api/search_chars/",
            params=params,
            catch_response=True,
            name="/api/search_chars/ (anonymous)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(30)
    def get_locs_anonymous(self):
        """匿名用户获取地点"""
        with self.client.get(
            "/api/get_locs/",
            params={"limit": 20},
            catch_response=True,
            name="/api/get_locs/ (anonymous)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(20)
    def view_homepage(self):
        """访问首页"""
        with self.client.get(
            "/",
            catch_response=True,
            name="/ (homepage)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")


class AdminUser(HttpUser):
    """模拟管理员用户 - 测试管理端点"""

    wait_time = between(5, 10)  # 管理员操作间隔更长
    weight = 1  # 管理员占比 10%

    def on_start(self):
        """管理员登录"""
        response = self.client.post("/auth/login", json={
            "username": ADMIN_USER["username"],
            "password": ADMIN_USER["password"]
        })

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
            if VERBOSE_LOGGING:
                print(f"✓ 管理员登录成功")
        else:
            self.token = None
            self.headers = {}
            print(f"✗ 管理员登录失败: {response.status_code}")

    @task(40)
    def view_api_usage(self):
        """查看 API 使用统计"""
        with self.client.get(
            "/admin/api-usage/api-summary",
            headers=self.headers,
            catch_response=True,
            name="/admin/api-usage/api-summary"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(30)
    def view_users(self):
        """查看用户列表"""
        with self.client.get(
            "/admin/users/all",
            headers=self.headers,
            catch_response=True,
            name="/admin/users/all"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(20)
    def view_login_logs(self):
        """查看登录日志"""
        params = {"limit": 50, "offset": 0}
        with self.client.get(
            "/admin/login_logs",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/admin/login_logs"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")

    @task(10)
    def view_user_stats(self):
        """查看用户统计"""
        with self.client.get(
            "/admin/user_stats",
            headers=self.headers,
            catch_response=True,
            name="/admin/user_stats"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"状态码: {response.status_code}")


# ==================== 事件监听器 ====================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时执行"""
    print("\n" + "="*60)
    print("🚀 压力测试开始")
    print("="*60)
    print(f"目标地址: {environment.host}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时执行"""
    print("\n" + "="*60)
    print("✓ 压力测试完成")
    print("="*60)
    print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("详细报告请查看 Web UI: http://localhost:8089")
    print("="*60 + "\n")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """每个请求完成后执行 - 用于自定义监控"""
    if exception:
        print(f"✗ 请求失败: {name} - {exception}")
    elif response_time > RESPONSE_TIME_THRESHOLD["slow"]:
        print(f"⚠ 慢请求: {name} - {response_time:.0f}ms")

