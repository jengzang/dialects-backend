"""
Test script for admin leaderboard API endpoints.

Tests all ranking types and edge cases.
"""

import requests
import json
from typing import Optional

# Configuration
BASE_URL = "http://localhost:5000"
ADMIN_USERNAME = "admin"  # Replace with your admin username
ADMIN_PASSWORD = "admin"  # Replace with your admin password


def get_admin_token() -> Optional[str]:
    """Login and get admin access token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None


def test_user_global_ranking(token: str):
    """Test 1: User global ranking by count"""
    print("\n" + "="*60)
    print("Test 1: User Global Ranking - By Count")
    print("="*60)

    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_global",
            "metric": "count",
            "page": 1,
            "page_size": 10
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total users: {data['total_count']}")
        print(f"✅ Total pages: {data['total_pages']}")
        print(f"✅ Rankings count: {len(data['rankings'])}")
        if data['rankings']:
            print("\nTop 3 users:")
            for item in data['rankings'][:3]:
                print(f"  Rank {item['rank']}: {item['username']} - {item['value']} calls ({item['percentage']}%)")
    else:
        print(f"❌ Failed: {response.text}")


def test_user_global_ranking_all_metrics(token: str):
    """Test 2: User global ranking - all metrics"""
    print("\n" + "="*60)
    print("Test 2: User Global Ranking - All Metrics")
    print("="*60)

    metrics = ["count", "duration", "upload", "download"]
    for metric in metrics:
        response = requests.get(
            f"{BASE_URL}/admin/leaderboard/rankings",
            params={
                "ranking_type": "user_global",
                "metric": metric,
                "page": 1,
                "page_size": 5
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ {metric}: {data['total_count']} users, {len(data['rankings'])} in page")
        else:
            print(f"❌ {metric} failed: {response.text}")


def test_available_apis(token: str):
    """Test 3: Get available APIs"""
    print("\n" + "="*60)
    print("Test 3: Get Available APIs")
    print("="*60)

    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/available-apis",
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total APIs: {len(data['apis'])}")
        print("\nFirst 10 APIs:")
        for api in data['apis'][:10]:
            print(f"  - {api}")
        return data['apis']
    else:
        print(f"❌ Failed: {response.text}")
        return []


def test_user_by_api_ranking(token: str, api_path: str):
    """Test 4: User ranking by specific API"""
    print("\n" + "="*60)
    print(f"Test 4: User Ranking by API - {api_path}")
    print("="*60)

    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_by_api",
            "metric": "count",
            "api_path": api_path,
            "page": 1,
            "page_size": 10
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total users: {data['total_count']}")
        print(f"✅ Rankings count: {len(data['rankings'])}")
        if data['rankings']:
            print("\nTop 3 users:")
            for item in data['rankings'][:3]:
                print(f"  Rank {item['rank']}: {item['username']} - {item['value']} calls")
    else:
        print(f"❌ Failed: {response.text}")


def test_api_ranking(token: str):
    """Test 5: API endpoint ranking"""
    print("\n" + "="*60)
    print("Test 5: API Endpoint Ranking - By Count")
    print("="*60)

    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "api",
            "metric": "count",
            "page": 1,
            "page_size": 10
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total APIs: {data['total_count']}")
        print(f"✅ Rankings count: {len(data['rankings'])}")
        if data['rankings']:
            print("\nTop 5 APIs:")
            for item in data['rankings'][:5]:
                print(f"  Rank {item['rank']}: {item['path']}")
                print(f"    Calls: {item['value']}, Users: {item['unique_users']}, Percentage: {item['percentage']}%")
    else:
        print(f"❌ Failed: {response.text}")


def test_online_time_ranking(token: str):
    """Test 6: Online time ranking"""
    print("\n" + "="*60)
    print("Test 6: Online Time Ranking")
    print("="*60)

    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "online_time",
            "page": 1,
            "page_size": 10
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Total users: {data['total_count']}")
        print(f"✅ Rankings count: {len(data['rankings'])}")
        if data['rankings']:
            print("\nTop 3 users:")
            for item in data['rankings'][:3]:
                hours = item['value'] / 3600
                print(f"  Rank {item['rank']}: {item['username']} - {hours:.2f} hours ({item['percentage']}%)")
    else:
        print(f"❌ Failed: {response.text}")


def test_pagination(token: str):
    """Test 7: Pagination"""
    print("\n" + "="*60)
    print("Test 7: Pagination")
    print("="*60)

    # Get page 1
    response1 = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_global",
            "metric": "count",
            "page": 1,
            "page_size": 5
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Get page 2
    response2 = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_global",
            "metric": "count",
            "page": 2,
            "page_size": 5
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    if response1.status_code == 200 and response2.status_code == 200:
        data1 = response1.json()
        data2 = response2.json()

        print(f"✅ Page 1: {len(data1['rankings'])} items")
        print(f"✅ Page 2: {len(data2['rankings'])} items")

        # Check if items are different
        if data1['rankings'] and data2['rankings']:
            user1 = data1['rankings'][0]['username']
            user2 = data2['rankings'][0]['username']
            if user1 != user2:
                print(f"✅ Pagination working: Page 1 top user ({user1}) != Page 2 top user ({user2})")
            else:
                print(f"⚠️  Warning: Same user on both pages")
    else:
        print(f"❌ Failed")


def test_error_cases(token: str):
    """Test 8: Error handling"""
    print("\n" + "="*60)
    print("Test 8: Error Handling")
    print("="*60)

    # Test 1: online_time with metric (should fail)
    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "online_time",
            "metric": "count",  # Should not be provided
            "page": 1
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 400:
        print("✅ Correctly rejected online_time with metric")
    else:
        print(f"❌ Should reject online_time with metric: {response.status_code}")

    # Test 2: user_by_api without api_path (should fail)
    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_by_api",
            "metric": "count",
            "page": 1
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 400:
        print("✅ Correctly rejected user_by_api without api_path")
    else:
        print(f"❌ Should reject user_by_api without api_path: {response.status_code}")

    # Test 3: user_global without metric (should fail)
    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_global",
            "page": 1
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 400:
        print("✅ Correctly rejected user_global without metric")
    else:
        print(f"❌ Should reject user_global without metric: {response.status_code}")


def test_permission(token: str):
    """Test 9: Permission check (non-admin should fail)"""
    print("\n" + "="*60)
    print("Test 9: Permission Check")
    print("="*60)

    # Try without token
    response = requests.get(
        f"{BASE_URL}/admin/leaderboard/rankings",
        params={
            "ranking_type": "user_global",
            "metric": "count",
            "page": 1
        }
    )

    if response.status_code in [401, 403]:
        print(f"✅ Correctly rejected request without token: {response.status_code}")
    else:
        print(f"❌ Should reject request without token: {response.status_code}")


def main():
    """Run all tests"""
    print("="*60)
    print("Admin Leaderboard API Test Suite")
    print("="*60)

    # Get admin token
    token = get_admin_token()
    if not token:
        print("\n❌ Cannot proceed without admin token")
        return

    print(f"✅ Admin token obtained")

    # Run tests
    test_user_global_ranking(token)
    test_user_global_ranking_all_metrics(token)
    apis = test_available_apis(token)

    # Test user by API ranking with first available API
    if apis:
        test_user_by_api_ranking(token, apis[0])

    test_api_ranking(token)
    test_online_time_ranking(token)
    test_pagination(token)
    test_error_cases(token)
    test_permission(token)

    print("\n" + "="*60)
    print("Test Suite Complete")
    print("="*60)


if __name__ == "__main__":
    main()
