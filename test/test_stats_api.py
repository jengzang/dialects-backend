"""
测试 API 统计接口

验证新增的 4 个统计 API 是否正常工作
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_hourly_trend():
    """测试小时级趋势"""
    print("\n=== 测试 /logs/stats/hourly ===")
    response = requests.get(f"{BASE_URL}/logs/stats/hourly?hours=24")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Period: {data['period']}")
        print(f"Data points: {len(data['data'])}")
        print(f"Summary: {json.dumps(data['summary'], indent=2)}")
    else:
        print(f"Error: {response.text}")

def test_daily_trend():
    """测试每日趋势"""
    print("\n=== 测试 /logs/stats/daily ===")
    response = requests.get(f"{BASE_URL}/logs/stats/daily?days=7")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Period: {data['period']}")
        print(f"Data points: {len(data['data'])}")
        print(f"Summary: {json.dumps(data['summary'], indent=2)}")
    else:
        print(f"Error: {response.text}")

def test_api_ranking():
    """测试 API 排行榜"""
    print("\n=== 测试 /logs/stats/ranking ===")
    response = requests.get(f"{BASE_URL}/logs/stats/ranking?limit=5")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Date: {data['date']}")
        print(f"Total calls: {data['total_calls']}")
        print(f"Top {len(data['ranking'])} APIs:")
        for item in data['ranking']:
            print(f"  {item['rank']}. {item['path']}: {item['call_count']} ({item['percentage']}%)")
    else:
        print(f"Error: {response.text}")

def test_api_history():
    """测试 API 历史趋势"""
    print("\n=== 测试 /logs/stats/api-history ===")
    response = requests.get(f"{BASE_URL}/logs/stats/api-history?path=/api/test&days=7")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Path: {data['path']}")
        print(f"Period: {data['period']}")
        print(f"Data points: {len(data['data'])}")
        print(f"Summary: {json.dumps(data['summary'], indent=2)}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    print("开始测试 API 统计接口...")
    print("请确保服务器已启动: uvicorn app.main:app --reload --port 5000")

    try:
        test_hourly_trend()
        test_daily_trend()
        test_api_ranking()
        test_api_history()
        print("\n✅ 所有测试完成!")
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器，请先启动服务器")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
