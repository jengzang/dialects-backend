# -*- coding: utf-8 -*-
"""修复中文编码的脚本"""
import sys

def main():
    file_path = 'app/logging/middleware/traffic_logging.py'

    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 逐行替换
    fixed_lines = []
    for line in lines:
        # 第7行
        if 'import queue  # [FIX]' in line and '鏀圭敤' in line:
            line = 'import queue  # [FIX] 使用线程队列（每个worker进程独立）\n'
        # 第20行
        elif 'from queue import Empty, Full' in line and '鍙紩鍏?' in line:
            line = 'from queue import Empty, Full  # 只引入异常类，不引入 Queue 类\n'
        # 第29行
        elif line.strip() == '# === 璺緞瑙勮寖鍖栧嚱鏁?===':
            line = '# === 路径规范化函数 ===\n'
        # 第32行 - docstring
        elif '瑙勮寖鍖?API 璺緞' in line:
            line = '    规范化 API 路径，将路径参数替换为占位符\n'
        elif '鏍规嵁瀹屾暣璺緞' in line:
            line = '    根据完整路径前缀精确匹配，避免误判\n'
        elif line.strip() == '绀轰緥锛?':
            line = '    示例：\n'
        elif 'path: 鍘熷' in line:
            line = '        path: 原始 API 路径\n'
        elif '瑙勮寖鍖栧悗鐨勮矾寰?' in line:
            line = '        规范化后的路径\n'
        elif '绮剧'鐨勮矾寰勬ā鏉?' in line:
            line = '    # 精确的路径模板映射（根据实际路由定义）\n'
        elif '鏍煎紡锛?鍓嶇紑' in line:
            line = '    # 格式：(前缀, 参数名)\n'
        elif '娉ㄦ剰锛氳繖涓' in line:
            line = line.replace('娉ㄦ剰锛氳繖涓鏀惧湪鏈€鍚庯紝閬垮厤璇尮閰?', '注意：这个要放在最后，避免误匹配')
        elif '鐗规畩锛氫袱涓弬鏁?' in line:
            line = line.replace('鐗规畩锛氫袱涓弬鏁?', '特殊：两个参数')
        elif '鐗规畩锛氫笁涓弬鏁?' in line:
            line = line.replace('鐗规畩锛氫笁涓弬鏁?', '特殊：三个参数')
        elif '鎸夊墠缂€闀垮害' in line:
            line = '    # 按前缀长度降序排序，确保更具体的路径先匹配\n'
        elif '鎻愬彇鍓嶇紑鍚庣殑閮ㄥ垎' in line:
            line = '            # 提取前缀后的部分\n'
        elif '濡傛灉鍚庨潰杩樻湁璺緞' in line:
            line = '            # 如果后面还有路径（如 /activity, /revoke），保留\n'
        elif '鍙浛鎹㈢涓€娈?' in line:
            line = '                # 只替换第一段\n'
        elif '鏁翠釜鍚庣紑閮芥槸鍙傛暟' in line:
            line = '                # 整个后缀都是参数\n'
        elif '娌℃湁鍖归厤鍒帮紝杩斿洖鍘熻矾寰?' in line:
            line = '    # 没有匹配到，返回原路径\n'
        elif '# === 闃熷垪锛堣法杩涚▼锛?===' in line:
            line = '# === 队列（进程内，每个worker独立） ===\n'
        elif '# [FIX] 鏀圭敤 multiprocessing.Queue' in line:
            line = '# [FIX] 改用 multiprocessing.Queue 以支持主进程中的后台线程\n'
        elif '# keyword_queue = queue.Queue()  # [X] 涓嶅啀浣跨敤' in line:
            line = '# keyword_queue = queue.Queue()  # [X] 不再使用 txt文件队列\n'
        elif 'log_queue = queue.Queue(maxsize=2000)' in line and '闄愬埗' in line:
            line = 'log_queue = queue.Queue(maxsize=2000)  # [OK] ApiUsageLog 队列（auth.db） - 限制 2000 条\n'
        elif 'keyword_log_queue = queue.Queue(maxsize=5000)' in line and '闄愬埗' in line:
            line = 'keyword_log_queue = queue.Queue(maxsize=5000)  # [OK] ApiKeywordLog 队列（logs.db） - 限制 5000 条\n'
        elif 'statistics_queue = queue.Queue(maxsize=1000)' in line and '闄愬埗' in line:
            line = 'statistics_queue = queue.Queue(maxsize=1000)  # [OK] ApiStatistics 队列（logs.db） - 限制 1000 条\n'
        elif 'html_visit_queue = queue.Queue(maxsize=500)' in line and '闄愬埗' in line:
            line = 'html_visit_queue = queue.Queue(maxsize=500)  # [OK] HTML 页面访问统计队列（logs.db） - 限制 500 条\n'
        elif 'summary_queue = queue.Queue(maxsize=1000)' in line and '闄愬埗' in line:
            line = 'summary_queue = queue.Queue(maxsize=1000)  # [NEW] ApiUsageSummary 队列（auth.db） - 限制 1000 条\n'
        elif '# === 鍏抽敭璇嶆棩蹇楋紙鍐欏叆logs.db锛?===' in line:
            line = '# === 关键词日志（写入logs.db） ===\n'
        elif '璁板綍 API 鍙傛暟瀛楁鍜屽€?' in line:
            line = '    """记录 API 参数字段和值"""\n'
        elif '# ===鍏抽敭璇嶆棩蹇楀啓鍏ョ嚎绋嬶紙logs.db锛?==' in line:
            line = '# ===关键词日志写入线程（logs.db）===\n'
        elif '姣?50 鏉℃壒閲忓啓鍏ヤ竴娆?' in line:
            line = '    batch_size = 50  # 每 50 条批量写入一次\n'
        elif '绛夊緟闃熷垪涓殑鏁版嵁锛岃秴鏃?绉?' in line:
            line = '            # 等待队列中的数据，超时1秒\n'

        fixed_lines.append(line)

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

    print(f'Fixed {file_path}')

if __name__ == '__main__':
    main()
