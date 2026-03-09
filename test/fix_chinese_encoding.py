#!/usr/bin/env python3
"""
修复中文编码问题的脚本

这个脚本会修复提交 357916a, 6ccaea5, 40afa8c, 8d750e7 中引入的中文编码错误。
"""

import re
from pathlib import Path

# 编码映射表（从错误编码到正确编码）
ENCODING_FIXES = {
    # 常见的错误编码模式
    "鏀圭敤璺ㄨ繘绋嬮槦鍒?": "改用跨进程队列",
    "鍙紩鍏ラ€欏€嬬暟甯搁锛屼笉寮曞叆 Queue 椤?": "只引入這個異常類，不引入 Queue 類",
    "璺緞瑙勮寖鍖栧嚱鏁?": "路径规范化函数",
    "瑙勮寖鍖?API 璺緞锛屽皢璺緞鍙傛暟鏇挎崲涓哄崰浣嶇": "规范化 API 路径，将路径参数替换为占位符",
    "鏍规嵁瀹屾暣璺緞鍓嶇紑绮剧'鍖归厤锛岄伩鍏嶈鍒?": "根据完整路径前缀精确匹配，避免误判",
    "绀轰緥锛?": "示例：",
    "鍘熷 API 璺緞": "原始 API 路径",
    "瑙勮寖鍖栧悗鐨勮矾寰?": "规范化后的路径",
    "绮剧'鐨勮矾寰勬ā鏉挎槧灏勶紙鏍规嵁瀹為檯璺敱瀹氫箟锛?": "精确的路径模板映射（根据实际路由定义）",
    "鏍煎紡锛?鍓嶇紑, 鍙傛暟鍚?": "格式：(前缀, 参数名)",
    "娉ㄦ剰锛氳繖涓鏀惧湪鏈€鍚庯紝閬垮厤璇尮閰?": "注意：这个要放在最后，避免误匹配",
    "鐗规畩锛氫袱涓弬鏁?": "特殊：两个参数",
    "鐗规畩锛氫笁涓弬鏁?": "特殊：三个参数",
    "鎸夊墠缂€闀垮害闄嶅簭鎺掑簭锛岀'淇濇洿鍏蜂綋鐨勮矾寰勫厛鍖归厤": "按前缀长度降序排序，确保更具体的路径先匹配",
    "鎻愬彇鍓嶇紑鍚庣殑閮ㄥ垎": "提取前缀后的部分",
    "濡傛灉鍚庨潰杩樻湁璺緞锛堝 /activity, /revoke锛夛紝淇濈暀": "如果后面还有路径（如 /activity, /revoke），保留",
    "鍙浛鎹㈢涓€娈?": "只替换第一段",
    "鏁翠釜鍚庣紑閮芥槸鍙傛暟": "整个后缀都是参数",
    "娌℃湁鍖归厤鍒帮紝杩斿洖鍘熻矾寰?": "没有匹配到，返回原路径",
    "闃熷垪锛堣法杩涚▼锛?": "队列（跨进程）",
    "涓嶅啀浣跨敤 txt鏂囦欢闃熷垪": "不再使用 txt文件队列",
    "闄愬埗 2000 鏉?": "限制 2000 条",
    "闄愬埗 5000 鏉?": "限制 5000 条",
    "闄愬埗 1000 鏉?": "限制 1000 条",
    "闄愬埗 500 鏉?": "限制 500 条",
    "鍏抽敭璇嶆棩蹇楋紙鍐欏叆logs.db锛?": "关键词日志（写入logs.db）",
    "璁板綍 API 鍙傛暟瀛楁鍜屽€?": "记录 API 参数字段和值",
    "鍏抽敭璇嶆棩蹇楀啓鍏ョ嚎绋嬶紙logs.db锛?": "关键词日志写入线程（logs.db）",
    "姣?50 鏉℃壒閲忓啓鍏ヤ竴娆?": "每 50 条批量写入一次",
    "绛夊緟闃熷垪涓殑鏁版嵁锛岃秴鏃?绉?": "等待队列中的数据，超时1秒",

    # 更多常见的错误编码
    "璁板綍": "记录",
    "鏁版嵁": "数据",
    "璇锋眰": "请求",
    "鍝嶅簲": "响应",
    "涓棿浠?": "中间件",
    "鐢ㄦ埛": "用户",
    "璁よ瘉": "认证",
    "鏉冮檺": "权限",
    "鏃ュ織": "日志",
    "缁熻": "统计",
    "闃熷垪": "队列",
    "绾跨▼": "线程",
    "杩涚▼": "进程",
    "鏁版嵁搴?": "数据库",
    "杩炴帴": "连接",
    "鏌ヨ": "查询",
    "鎻掑叆": "插入",
    "鏇存柊": "更新",
    "鍒犻櫎": "删除",
    "閿欒": "错误",
    "璀﹀憡": "警告",
    "淇℃伅": "信息",
    "璋冭瘯": "调试",
}


def fix_file_encoding(file_path: Path) -> bool:
    """
    修复单个文件的编码问题

    Args:
        file_path: 文件路径

    Returns:
        是否进行了修改
    """
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 应用所有修复
        for wrong, correct in ENCODING_FIXES.items():
            if wrong in content:
                content = content.replace(wrong, correct)
                print(f"  修复: {wrong} -> {correct}")

        # 如果有修改，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"  错误: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("修复中文编码问题")
    print("=" * 60)

    # 需要修复的文件列表
    files_to_fix = [
        "app/logging/middleware/traffic_logging.py",
        "app/logging/middleware/params_logging.py",
        "gunicorn_config.py",
    ]

    base_dir = Path(__file__).parent.parent
    fixed_count = 0

    for file_path_str in files_to_fix:
        file_path = base_dir / file_path_str

        if not file_path.exists():
            print(f"\n⚠️  文件不存在: {file_path}")
            continue

        print(f"\n处理文件: {file_path}")

        if fix_file_encoding(file_path):
            print(f"✅ 已修复: {file_path}")
            fixed_count += 1
        else:
            print(f"➡️  无需修复: {file_path}")

    print("\n" + "=" * 60)
    print(f"修复完成！共修复 {fixed_count} 个文件")
    print("=" * 60)

    if fixed_count > 0:
        print("\n建议：")
        print("1. 检查修复后的文件是否正确")
        print("2. 运行测试确保功能正常")
        print("3. 提交修复：git add . && git commit -m 'fix: 修复中文编码问题'")


if __name__ == "__main__":
    main()
