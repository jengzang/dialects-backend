"""测试有调类合并的地点"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.service.search_tones import search_tones
import json

# 测试一个可能有调类合并的地点
locations_to_test = ['梅縣', '潮州', '汕頭']

for loc in locations_to_test:
    try:
        result = search_tones(locations=[loc], get_raw=True)
        print(f'\n=== {loc} ===')

        # 检查是否有调类合并
        has_merge = False
        for i in range(1, 11):
            t_key = f"T{i}"
            t_data = result[0].get(t_key, {})
            value = t_data.get('value', [])
            match = t_data.get('match', [])

            # 如果 value 为空但 match 不为空，说明有合并
            if not value and match:
                has_merge = True
                print(f"{t_key}: value={value}, match={match} <- 合并到其他调类")
            elif value:
                print(f"{t_key}: value={value}, match={match}")

        if has_merge:
            print(f"\n✓ {loc} 有调类合并！")
            break
    except:
        continue
