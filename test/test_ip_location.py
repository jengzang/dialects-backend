"""
测试 IP 地理位置功能

验证所有管理员接口是否正确返回 IP 地理位置信息
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.admin.analytics.geo import lookup_ip_location


def test_lookup_ip_location():
    """测试 IP 地理位置查询函数"""
    print("=" * 60)
    print("测试 IP 地理位置查询功能")
    print("=" * 60)

    # 测试用例
    test_cases = [
        ("8.8.8.8", "美国 Google DNS"),
        ("114.114.114.114", "中国 DNS"),
        ("1.1.1.1", "美国 Cloudflare DNS"),
        ("223.5.5.5", "中国阿里 DNS"),
        ("0.0.0.0", "无效 IP"),
        (None, "空 IP"),
        ("192.168.1.1", "内网 IP"),
        ("invalid", "非法 IP"),
    ]

    print("\n测试 city 级别查询:")
    print("-" * 60)
    for ip, description in test_cases:
        location = lookup_ip_location(ip, level="city")
        print(f"{description:20s} | IP: {str(ip):15s} | 位置: {location}")

    print("\n测试 country 级别查询:")
    print("-" * 60)
    for ip, description in test_cases:
        location = lookup_ip_location(ip, level="country")
        print(f"{description:20s} | IP: {str(ip):15s} | 位置: {location}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_lookup_ip_location()
