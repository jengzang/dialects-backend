import re
import sqlite3

import pandas as pd
from fastapi import HTTPException

from common.getloc_by_name_region import query_dialect_abbreviations
from common.config import QUERY_DB_ADMIN
# [NEW] 导入连接池
from app.sql.db_pool import get_db_pool


def search_tones(locations=None, regions=None, get_raw: bool = False, db_path=QUERY_DB_ADMIN, region_mode='yindian'):
    # 假设 query_dialect_abbreviations 函数返回一个地点简称的列表
    all_locations = query_dialect_abbreviations(regions, locations, db_path=db_path,region_mode=region_mode)
    if not all_locations:
        raise HTTPException(status_code=400, detail="🛑 請輸入正確的地點！\n建議點擊地點輸入框下方的提示地點！")

    # [NEW] 使用连接池
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        # if all_locations is not None and len(all_locations) > 0:
        placeholders = ','.join(['?'] * len(all_locations))  # 動態生成 SQL IN 子句的佔位符
        query = f"""
        SELECT 簡稱, T1陰平, T2陽平, T3陰上, T4陽上, T5陰去, T6陽去, T7陰入, T8陽入, T9其他調, T10輕聲
        FROM dialects
        WHERE 簡稱 IN ({placeholders})
        """
        df = pd.read_sql(query, conn, params=all_locations)

    df.set_index('簡稱', inplace=True)

    # 如果传入了abbreviation，则根据它过滤数据
    if all_locations is not None:
        df = df.loc[all_locations]

    # 处理每一列的单元格
    def process_cell(value, num):
        # 如果值是 None 或 NaN，返回空字符串
        if value is None or pd.isnull(value):
            return ""
        if isinstance(value, str):  # 确保是字符串
            # 如果没有 []，在开头添加[num]
            if ('[' not in value) or (']' not in value):
                return f"[{num}]{value}"
            else:
                # 如果有 []，按逗号拆分并处理
                elements = re.split(r'[，,|;]', value)
                processed_elements = []
                for element in elements:
                    # 只有当元素没有 [num] 或 [] 时才加上[num]
                    if '[' not in element and ']' not in element:
                        processed_elements.append(f"[{num}]{element}")
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

    # 遍历数据框并进行处理
    for col_num, col_name in enumerate(df.columns, start=1):
        # 处理每一列的每一行
        df[col_name] = df[col_name].apply(lambda x: process_cell(x, col_num))

    result = []
    new_result = []

    # 遍历所有数据行
    for index, row in df.iterrows():
        # 获取总数据
        total_data = [str(x) if x != "" else "" for x in row.tolist()]

        # 创建一个字典，保留簡稱和總數據
        row_data = {
            "簡稱": index,
            "總數據": total_data
        }

        # 生成新的 tones 字段
        new_row = {
            "簡稱": index,
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
                    for t, names in match_table.items():
                        if any(matching_name in name for matching_name in names):  # 部分匹配
                            matched_t.add(t)

                    match_list.extend(list(matched_t))  # 将 set 转回 list，直接扩展到 match_list
                    # 如果 T5 没有被匹配到，则使用备用规则 ['去'] 来匹配 T5
                    if 'T1' not in match_list:
                        if '平' in name and not re.search(r'^(陽|阳)', name):
                            match_list.append('T1')
                    if 'T3' not in match_list:
                        if '上' in name and not re.search(r'^(陽|阳)', name):
                            match_list.append('T3')
                    if 'T5' not in match_list:
                        if '去' in name and not re.search(r'^(陽|阳)', name):
                            match_list.append('T5')
                    if 'T7' not in match_list:
                        if '入' in name and not re.search(r'^(陽|阳)', name):
                            match_list.append('T7')

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
                    for t, names in match_table.items():
                        if any(matching_name in name for matching_name in names):  # 部分匹配
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
            return result
        new_result.append(new_row)

    return new_result
