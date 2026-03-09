#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单的编码修复脚本 - 直接替换乱码为正确的中文"""

import sys
from pathlib import Path

# 编码映射 - 从乱码到正确的中文
FIXES = [
    ("鏀圭敤璺ㄨ繘绋嬮槦鍒?", "使用线程队列（每个worker进程独立）"),
    ("鍙紩鍏ラ€欏€嬬暟甯搁锛屼笉寮曞叆 Queue 椤?", "只引入异常类，不引入 Queue 类"),
    ("璺緞瑙勮寖鍖栧嚱鏁?", "路径规范化函数"),
    ("瑙勮寖鍖?API 璺緞锛屽皢璺緞鍙傛暟鏇挎崲涓哄崰浣嶇", "规范化 API 路径，将路径参数替换为占位符"),
    ("鏍规嵁瀹屾暣璺緞鍓嶇紑绮剧'鍖归厤锛岄伩鍏嶈鍒?", "根据完整路径前缀精确匹配，避免误判"),
    ("绀轰緥锛?", "示例："),
    ("鍘熷 API 璺緞", "原始 API 路径"),
    ("瑙勮寖鍖栧悗鐨勮矾寰?", "规范化后的路径"),
    ("绮剧'鐨勮矾寰勬ā鏉挎槧灏勶紙鏍规嵁瀹為檯璺敱瀹氫箟锛?", "精确的路径模板映射（根据实际路由定义）"),
    ("鏍煎紡锛?鍓嶇紑, 鍙傛暟鍚?", "格式：(前缀, 参数名)"),
    ("娉ㄦ剰锛氳繖涓鏀惧湪鏈€鍚庯紝閬垮厤璇尮閰?", "注意：这个要放在最后，避免误匹配"),
    ("鐗规畩锛氫袱涓弬鏁?", "特殊：两个参数"),
    ("鐗规畩锛氫笁涓弬鏁?", "特殊：三个参数"),
    ("鎸夊墠缂€闀垮害闄嶅簭鎺掑簭锛岀'淇濇洿鍏蜂綋鐨勮矾寰勫厛鍖归厤", "按前缀长度降序排序，确保更具体的路径先匹配"),
    ("鎻愬彇鍓嶇紑鍚庣殑閮ㄥ垎", "提取前缀后的部分"),
    ("濡傛灉鍚庨潰杩樻湁璺緞锛堝 /activity, /revoke锛夛紝淇濈暀", "如果后面还有路径（如 /activity, /revoke），保留"),
    ("鍙浛鎹㈢涓€娈?", "只替换第一段"),
    ("鏁翠釜鍚庣紑閮芥槸鍙傛暟", "整个后缀都是参数"),
    ("娌℃湁鍖归厤鍒帮紝杩斿洖鍘熻矾寰?", "没有匹配到，返回原路径"),
    ("闃熷垪锛堣法杩涚▼锛?", "队列（进程内，每个worker独立）"),
    ("涓嶅啀浣跨敤 txt鏂囦欢闃熷垪", "不再使用 txt文件队列"),
    ("闄愬埗 2000 鏉?", "限制 2000 条"),
    ("闄愬埗 5000 鏉?", "限制 5000 条"),
    ("闄愬埗 1000 鏉?", "限制 1000 条"),
    ("闄愬埗 500 鏉?", "限制 500 条"),
    ("鍏抽敭璇嶆棩蹇楋紙鍐欏叆logs.db锛?", "关键词日志（写入logs.db）"),
    ("璁板綍 API 鍙傛暟瀛楁鍜屽€?", "记录 API 参数字段和值"),
    ("鍏抽敭璇嶆棩蹇楀啓鍏ョ嚎绋嬶紙logs.db锛?", "关键词日志写入线程（logs.db）"),
    ("姣?50 鏉℃壒閲忓啓鍏ヤ竴娆?", "每 50 条批量写入一次"),
    ("绛夊緟闃熷垪涓殑鏁版嵁锛岃秴鏃?绉?", "等待队列中的数据，超时1秒"),
    ("鏀圭敤 multiprocessing.Queue 浠ユ敮鎸佷富杩涚▼涓殑鍚庡彴绾跨▼", "改用 multiprocessing.Queue 以支持主进程中的后台线程"),
    ("璁板綍", "记录"),
    ("鏁版嵁", "数据"),
    ("璇锋眰", "请求"),
    ("鍝嶅簲", "响应"),
    ("涓棿浠?", "中间件"),
    ("鐢ㄦ埛", "用户"),
    ("璁よ瘉", "认证"),
    ("鏉冮檺", "权限"),
    ("鏃ュ織", "日志"),
    ("缁熻", "统计"),
    ("闃熷垪", "队列"),
    ("绾跨▼", "线程"),
    ("杩涚▼", "进程"),
    ("鏁版嵁搴?", "数据库"),
    ("杩炴帴", "连接"),
    ("鏌ヨ", "查询"),
    ("鎻掑叆", "插入"),
    ("鏇存柊", "更新"),
    ("鍒犻櫎", "删除"),
    ("閿欒", "错误"),
    ("璀﹀憡", "警告"),
    ("淇℃伅", "信息"),
    ("璋冭瘯", "调试"),
]

def fix_file(filepath):
    """修复单个文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content
        for wrong, correct in FIXES:
            content = content.replace(wrong, correct)

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        sys.stderr.write(f"Error fixing {filepath}: {e}\n")
        return False

def main():
    base = Path(__file__).parent.parent
    files = [
        base / "app/logging/middleware/traffic_logging.py",
        base / "app/logging/middleware/params_logging.py",
        base / "gunicorn_config.py",
    ]

    fixed = 0
    for f in files:
        if f.exists():
            if fix_file(f):
                sys.stdout.write(f"Fixed: {f.name}\n")
                fixed += 1
            else:
                sys.stdout.write(f"No changes: {f.name}\n")
        else:
            sys.stderr.write(f"Not found: {f}\n")

    sys.stdout.write(f"\nTotal fixed: {fixed} files\n")

if __name__ == "__main__":
    main()
