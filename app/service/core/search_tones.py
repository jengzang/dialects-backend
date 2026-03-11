import re

from fastapi import HTTPException

from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.common.path import QUERY_DB_ADMIN
# [NEW] 导入连接池
from app.sql.db_pool import get_db_pool


def search_tones(locations=None, regions=None, get_raw: bool = False, db_path=QUERY_DB_ADMIN, region_mode='yindian'):
    """
    查询声调信息

    性能优化：使用cursor代替pandas读取（5-10倍性能提升）
    """
    # 假设 query_dialect_abbreviations 函数返回一个地点简称的列表
    all_locations = query_dialect_abbreviations(regions, locations, db_path=db_path,region_mode=region_mode)
    if not all_locations:
        raise HTTPException(status_code=400, detail="🛑 請輸入正確的地點！\n建議點擊地點輸入框下方的提示地點！")

    # 【性能优化】使用cursor代替pandas
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(all_locations))
        query = f"""
        SELECT 簡稱, T1陰平, T2陽平, T3陰上, T4陽上, T5陰去, T6陽去, T7陰入, T8陽入, T9其他調, T10輕聲
        FROM dialects
        WHERE 簡稱 IN ({placeholders})
        """
        cursor.execute(query, all_locations)
        rows = cursor.fetchall()

    # 构建数据字典 {簡稱: [T1, T2, ..., T10]}
    data_dict = {}
    for row in rows:
        loc = row[0]
        tone_data = list(row[1:])  # T1-T10
        data_dict[loc] = tone_data

    # 按照all_locations的顺序处理
    ordered_data = []
    for loc in all_locations:
        if loc in data_dict:
            ordered_data.append((loc, data_dict[loc]))

    # 处理每一列的单元格
    def process_cell(value, num):
        if value is None or value == '':
            return ""
        if isinstance(value, str):
            # 1. 先拆分
            raw_elements = re.split(r'[，,|;]', value)

            # 2. 預先清洗：去除空字符串，這樣 len() 才是準確的有效元素個數
            elements = [e.strip() for e in raw_elements if e.strip()]

            processed_elements = []
            # 3. 判斷是否需要字母：只有當元素大於 1 個時才啟用
            need_letter = len(elements) > 1

            for i, element in enumerate(elements):
                # 4. 如果需要字母則生成 'a', 'b'...，否則為空字符串
                letter = chr(97 + i) if need_letter else ""

                # 只有當元素沒有 [ 和 ] 時才加上 [num + letter]
                if '[' not in element and ']' not in element:
                    processed_elements.append(f"[{num}{letter}]{element}")
                else:
                    processed_elements.append(element)

            return ','.join(processed_elements)
        return value

    match_table = {
        'T1': ['陰平', '平聲', '阴平', '平声'],
        'T2': ['陽平', '阳平'],
        'T3': ['陰上', '上聲', '阴上', '上声'],
        'T4': ['陽上', '阳上'],
        'T5': ['陰去', '去聲', '阴去', '去声'],
        'T6': ['陽去', '阳去'],
        'T7': ['陰入', '阴入'],
        'T8': ['陽入', '阳入']
    }

    result = []
    new_result = []

    # 遍历所有数据行
    for loc, tone_values in ordered_data:
        # 处理每一列
        total_data = [process_cell(val, i+1) for i, val in enumerate(tone_values)]

        # 创建一个字典，保留簡稱和總數據
        row_data = {
            "簡稱": loc,
            "總數據": total_data
        }

        # 生成新的 tones 字段
        new_row = {
            "簡稱": loc,
            "總數據": total_data,
            "tones": []
        }

        # Part 1: 循环处理 T1 到 T8
        for i in range(1, 9):  # 范围是 1 到 8（包含 8）
            matched = total_data[i - 1]  # 索引从 0 开始，因此使用 i - 1

            # 去除方括号和其中的内容
            raw_value = re.sub(r'\[.*?\]', '', matched)  # 删除方括号和其中的内容

            if raw_value:
                # 按逗号分割
                raw_parts = re.split(r'[，,]', raw_value)
                value_list = []
                name_list = []

                for part in raw_parts:
                    # 提取数字部分 (value)
                    value = ''.join(re.findall(r'\d+', part))
                    # 提取汉字部分 (name)
                    name = ''.join(re.findall(r'[^\d,]+', part))

                    # 如果 name 中包含 "入"，则给 value 添加前缀
                    if "入" in name:
                        value = f'`{value}'  # 给 value 添加前缀

                    value_list.append(value)
                    name_list.append(name)

                # 匹配名称
                match_list = []
                for name in name_list:
                    matched_t = set()  # 使用 set 来去重

                    # 提取所有连续的词（窗口大小 2-4）
                    continuous_words = set()
                    for window_size in range(2, min(len(name) + 1, 5)):  # 窗口 2-4
                        for j in range(len(name) - window_size + 1):
                            continuous_words.add(name[j:j + window_size])

                    # 用连续词精确匹配 match_table
                    for t, names in match_table.items():
                        if any(matching_name in continuous_words for matching_name in names):
                            matched_t.add(t)

                    match_list.extend(list(matched_t))  # 将 set 转回 list，直接扩展到 match_list

                    # 备用规则：检查连续的 2 字词
                    if 'T1' not in match_list:
                        for j in range(len(name) - 1):
                            word = name[j:j+2]
                            if word.endswith('平') and not word.startswith('陽') and not word.startswith('阳'):
                                match_list.append('T1')
                                break
                    if 'T3' not in match_list:
                        for j in range(len(name) - 1):
                            word = name[j:j+2]
                            if word.endswith('上') and not word.startswith('陽') and not word.startswith('阳'):
                                match_list.append('T3')
                                break
                    if 'T5' not in match_list:
                        for j in range(len(name) - 1):
                            word = name[j:j+2]
                            if word.endswith('去') and not word.startswith('陽') and not word.startswith('阳'):
                                match_list.append('T5')
                                break
                    if 'T7' not in match_list:
                        for j in range(len(name) - 1):
                            word = name[j:j+2]
                            if word.endswith('入') and not word.startswith('陽') and not word.startswith('阳'):
                                match_list.append('T7')
                                break

                # 去重 match_list
                match_list = list(set(match_list))
                bracket_nums = re.findall(r'\[(\d+)\]', matched)

                # 将结果保存到 row_data 字典中
                row_data[f"T{i}"] = {
                    'raw': raw_value,
                    'value': value_list,
                    'name': name_list,
                    'match': match_list,
                    'num': bracket_nums
                }

                # 更新 tones 列表
                new_row['tones'].append(
                    {f"T{i}": ','.join(value_list) if value_list else ','.join(match_list) if match_list else '無'})
            else:
                # 如果没有匹配值，初始化为空
                row_data[f"T{i}"] = {
                    'raw': '',
                    'value': [],
                    'name': [],
                    'match': [],
                    'num': []
                }

                new_row['tones'].append({f"T{i}": '無'})  # 初步处理为无匹配

        # Part 2: 循环处理 T9 到 T10
        for i in range(9, 11):  # 范围是 9 到 10（包含 10）
            matched = total_data[i - 1]  # 索引从 0 开始，因此使用 i - 1

            # 去除方括号和其中的内容
            raw_value = re.sub(r'\[.*?\]', '', matched)  # 删除方括号和其中的内容

            if raw_value:
                # 按逗号分割
                raw_parts = re.split(r'[，,]', raw_value)
                value_list = []
                name_list = []

                for part in raw_parts:
                    # 提取数字部分 (value)
                    value = ''.join(re.findall(r'\d+', part))
                    # 提取汉字部分 (name)
                    name = ''.join(re.findall(r'[^\d,]+', part))

                    # 如果 name 中包含 "入"，则给 value 添加前缀
                    if "入" in name:
                        value = f'`{value}'  # 给 value 添加前缀

                    value_list.append(value)
                    name_list.append(name)

                # 匹配名称
                match_list = []
                for name in name_list:
                    matched_t = set()  # 使用 set 来去重

                    # 提取所有连续的词（窗口大小 2-4）
                    continuous_words = set()
                    for window_size in range(2, min(len(name) + 1, 5)):  # 窗口 2-4
                        for j in range(len(name) - window_size + 1):
                            continuous_words.add(name[j:j + window_size])

                    # 用连续词精确匹配 match_table
                    for t, names in match_table.items():
                        if any(matching_name in continuous_words for matching_name in names):
                            matched_t.add(t)

                    match_list.extend(list(matched_t))  # 将 set 转回 list，直接扩展到 match_list

                # 去重 match_list
                match_list = list(set(match_list))
                bracket_nums = re.findall(r'\[(\d+)\]', matched)

                # 将结果保存到 row_data 字典中
                row_data[f"T{i}"] = {
                    'raw': raw_value,
                    'value': value_list,
                    'name': name_list,
                    'match': match_list,
                    'num': bracket_nums
                }

                # 更新 tones 列表
                new_row['tones'].append(
                    {f"T{i}": ','.join(value_list) if value_list else ','.join(match_list) if match_list else '無'})
            else:
                # 如果没有匹配值，初始化为空
                row_data[f"T{i}"] = {
                    'raw': '',
                    'value': [],
                    'name': [],
                    'match': [],
                    'num': []
                }

                new_row['tones'].append({f"T{i}": '無'})  # 初步处理为无匹配

        # 在这里遍历结束之后再处理没有匹配的 T
        for i in range(1, 11):  # 再次遍历每个 T
            t_data = row_data[f"T{i}"]

            if not t_data['value']:  # 如果 T[i] 的 value 为空
                match_found = []
                for j in range(1, 11):  # 遍历同一簡稱中的其他 T（T1 到 T10）
                    if j != i:  # 避免比较自己
                        t_j_data = row_data[f"T{j}"]
                        if f"T{i}" in t_j_data.get('match', []):  # 检查 T[i] 是否在 T[j] 的 match 中
                            match_found.append(f"T{j}")  # 如果匹配，则加入匹配列表

                # 打印调试输出：当前 T[i] 在其它 T 的 match 中找到了什么
                # print(f"Searching for matches for T{i}: Found {match_found}")

                if match_found:
                    row_data[f"T{i}"]['match'] = ','.join(match_found)  # 填充匹配的 T
                    new_row['tones'][i - 1] = {f"T{i}": ','.join(match_found)}  # 更新 tones
                else:
                    row_data[f"T{i}"]['match'] = '無'  # 如果没有匹配项，填充无
                    new_row['tones'][i - 1] = {f"T{i}": '無'}  # 更新 tones 为无

        # 添加到 result 和 new_result 中
        if get_raw:
            result.append(row_data)
        else:
            new_result.append(new_row)

    return result if get_raw else new_result
