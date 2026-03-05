"""测试 search_tones 的返回格式"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.service.search_tones import search_tones
import json

# 测试 get_raw=False（简化格式）
result_simple = search_tones(locations=['廣州'], get_raw=False)
print('=== get_raw=False 格式（简化） ===')
print(json.dumps(result_simple[0], ensure_ascii=False, indent=2))

print('\n' + '='*80 + '\n')

# 测试 get_raw=True（完整格式）
result_raw = search_tones(locations=['廣州'], get_raw=True)
print('=== get_raw=True 格式（完整，包含 match） ===')
# 只打印前3个调类，避免输出太长
simplified = {
    "簡稱": result_raw[0]["簡稱"],
    "T1": result_raw[0]["T1"],
    "T2": result_raw[0]["T2"],
    "T3": result_raw[0]["T3"],
}
print(json.dumps(simplified, ensure_ascii=False, indent=2))
