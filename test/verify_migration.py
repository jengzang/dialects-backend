#!/usr/bin/env python3
"""
验证统一 API 限流和日志系统迁移
测试所有迁移的路由是否正常工作
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_imports():
    """检查所有路由文件的导入是否正确"""
    print("=" * 60)
    print("检查导入语句...")
    print("=" * 60)

    route_files = [
        "app/routes/form_submit.py",
        "app/routes/custom_query.py",
        "app/routes/get_locs.py",
        "app/routes/batch_match.py",
        "app/routes/get_coordinates.py",
        "app/routes/get_partitions.py",
        "app/routes/get_regions.py",
    ]

    errors = []

    for file_path in route_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查是否还有旧的导入
            if "from app.logs.service.api_logger import *" in content:
                errors.append(f"❌ {file_path}: 仍然使用旧的导入 'api_logger'")

            # 检查是否有新的导入
            if "from app.logs.service.api_limiter import ApiLimiter" not in content:
                errors.append(f"❌ {file_path}: 缺少新的导入 'ApiLimiter'")

            # 检查是否还有手动调用
            if "log_all_fields(" in content:
                errors.append(f"❌ {file_path}: 仍然有手动调用 'log_all_fields()'")

            if not errors or not any(file_path in e for e in errors):
                print(f"✅ {file_path}: 导入正确")

        except Exception as e:
            errors.append(f"❌ {file_path}: 读取文件失败 - {str(e)}")

    return errors

def check_config():
    """检查配置文件是否包含所有路由"""
    print("\n" + "=" * 60)
    print("检查配置文件...")
    print("=" * 60)

    try:
        from app.common.api_config import API_ROUTE_CONFIG

        required_routes = [
            "/api/submit_form",
            "/api/delete_form",
            "/api/get_custom",
            "/api/get_custom_feature",
            "/api/get_locs/*",
            "/api/batch_match",
            "/api/get_coordinates",
            "/api/partitions",
            "/api/get_regions",
        ]

        errors = []

        for route in required_routes:
            if route in API_ROUTE_CONFIG:
                config = API_ROUTE_CONFIG[route]
                print(f"✅ {route}: {config}")
            else:
                errors.append(f"❌ {route}: 配置缺失")

        return errors

    except Exception as e:
        return [f"❌ 读取配置失败: {str(e)}"]

def check_middleware():
    """检查中间件是否正确注册"""
    print("\n" + "=" * 60)
    print("检查中间件...")
    print("=" * 60)

    try:
        from app.main import app

        # 检查中间件是否注册
        middleware_names = [m.__class__.__name__ for m in app.user_middleware]

        if "ApiLoggingMiddleware" in str(middleware_names):
            print("✅ ApiLoggingMiddleware 已注册")
            return []
        else:
            return ["❌ ApiLoggingMiddleware 未注册"]

    except Exception as e:
        return [f"⚠️  无法检查中间件: {str(e)}"]

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("统一 API 限流和日志系统 - 迁移验证")
    print("=" * 60 + "\n")

    all_errors = []

    # 检查导入
    errors = check_imports()
    all_errors.extend(errors)

    # 检查配置
    errors = check_config()
    all_errors.extend(errors)

    # 检查中间件
    errors = check_middleware()
    all_errors.extend(errors)

    # 总结
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    if all_errors:
        print(f"\n❌ 发现 {len(all_errors)} 个问题:\n")
        for error in all_errors:
            print(f"  {error}")
        print("\n请修复以上问题后重新运行验证。\n")
        return 1
    else:
        print("\n✅ 所有检查通过！迁移成功！\n")
        print("建议:")
        print("  1. 启动服务器测试实际功能")
        print("  2. 检查日志数据库是否正常记录")
        print("  3. 进行压力测试验证性能")
        print()
        return 0

if __name__ == "__main__":
    sys.exit(main())
