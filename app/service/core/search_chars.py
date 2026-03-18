import numpy as np
from fastapi import HTTPException

from app.common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH

from app.common.s2t import s2t_pro
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
# [NEW] 导入连接池
from app.sql.db_pool import get_db_pool


def search_characters(chars, locations=None, regions=None, db_path=DIALECTS_DB_USER, region_mode='yindian', query_db_path=QUERY_DB_USER, table="characters"):
    """
    Args:
        db_path: 方言数据库路径（用于查询实际读音数据）
        query_db_path: 查询数据库路径（用于查询地点信息）
        table: 字符数据库表名（默认 "characters"）
    """
    # 驗證表名
    from app.common.constants import validate_table_name, get_table_schema
    if not validate_table_name(table):
        raise HTTPException(status_code=400, detail=f"無效的表名：{table}")

    schema = get_table_schema(table)

    all_locations = query_dialect_abbreviations(regions, locations, db_path=query_db_path, region_mode=region_mode)
    if not all_locations:
        raise HTTPException(status_code=400, detail="🛑 請輸入正確的地點！\n建議點擊地點輸入框下方的提示地點！")

    if isinstance(chars, str):
        chars = list(chars)
    elif isinstance(chars, (list, np.ndarray)):
        chars = [char for sublist in chars for char in
                 (sublist if isinstance(sublist, (list, np.ndarray)) else [sublist])]

    # 使用 keep_all_layers=True 保留各层转换结果
    clean_str, mapping = s2t_pro(chars, level=2, keep_all_layers=True)

    # 构建每个原字的候选列表（原字 + 转换结果）
    char2candidates = {}
    for 原字, 候選 in mapping:
        candidates = [原字] + [c for c in 候選 if c != 原字]
        char2candidates[原字] = candidates

    # 收集所有候选字用于批量查询
    all_candidate_chars = []
    for 原字 in chars:
        all_candidate_chars.extend(char2candidates.get(原字, [原字]))
    clean_str = ''.join(dict.fromkeys(all_candidate_chars))  # 去重

    result = []

    # [NEW] 使用连接池
    dialect_pool = get_db_pool(db_path)
    characters_pool = get_db_pool(CHARACTERS_DB_PATH)

    # [OK] 优化：批量查询字符地位信息（消除N次查询）
    char2positions = {}
    char2is_multi = {}

    with characters_pool.get_connection() as characters_conn:
        characters_cursor = characters_conn.cursor()

        if clean_str:
            # 批量查询所有字符的基本信息
            char_placeholders = ','.join('?' * len(clean_str))

            # 根據表結構構建查詢列
            char_col = schema["char_column"]
            # 只查詢表中實際存在的列
            select_cols = [char_col]
            for col in ['攝', '呼', '等', '韻', '調', '組', '母', '部位', '方式']:
                if col in schema["hierarchy"]:
                    select_cols.append(col)

            # 如果表支持多地位標記，也查詢該列
            if schema.get("has_multi_status", False):
                multi_status_col = schema.get("multi_status_column", "多地位標記")
                select_cols.append(multi_status_col)

            characters_query = f"""
                SELECT {', '.join(select_cols)}
                FROM {table}
                WHERE {char_col} IN ({char_placeholders})
            """
            characters_cursor.execute(characters_query, clean_str)
            characters_results = characters_cursor.fetchall()

            # 按字符组织结果
            char2rows = {}
            for row in characters_results:
                char = row[char_col]
                if char not in char2rows:
                    char2rows[char] = []
                char2rows[char].append(row)

            # 处理每个字符的地位信息
            for char in clean_str:
                rows = char2rows.get(char, [])
                positions = []
                # 只有支持多地位的表才檢查多地位標記
                is_multi = False
                if schema.get("has_multi_status", False):
                    multi_status_col = schema.get("multi_status_column", "多地位標記")
                    is_multi = any(row.get(multi_status_col) == 1 for row in rows)
                char2is_multi[char] = is_multi

                for row in rows:
                    parts = f"{row['攝']}{row['呼']}{row['等']}{row['韻']}{row['調']}"
                    meta = f"{row['組']}·{row['母']}•{row['部位']}·{row['方式']}音"
                    positions.append(f"{parts},{meta}")

                char2positions[char] = positions

    # [OK] 优化：批量查询方言数据（消除N×M次查询）
    char2loc2data = {}  # {char: {location: [rows]}}

    with dialect_pool.get_connection() as dialect_conn:
        dialect_cursor = dialect_conn.cursor()

        try:
            if clean_str and all_locations:
                # SQLite参数限制：默认999个参数
                MAX_PARAMS = 900  # 留一些余量
                unique_chars = list(dict.fromkeys(clean_str))
                unique_locations = list(dict.fromkeys(all_locations))

                # 分批查询（避免构造字符×地点笛卡尔积参数）
                max_loc_batch = max(1, MAX_PARAMS // 2)
                for loc_start in range(0, len(unique_locations), max_loc_batch):
                    loc_batch = unique_locations[loc_start:loc_start + max_loc_batch]
                    max_char_batch = max(1, MAX_PARAMS - len(loc_batch))

                    for char_start in range(0, len(unique_chars), max_char_batch):
                        char_batch = unique_chars[char_start:char_start + max_char_batch]
                        char_placeholders = ','.join('?' * len(char_batch))
                        loc_placeholders = ','.join('?' * len(loc_batch))

                        dialect_query = f"""
                            SELECT 漢字, 簡稱, 音節, 多音字, 註釋
                            FROM dialects
                            WHERE 漢字 IN ({char_placeholders})
                            AND 簡稱 IN ({loc_placeholders})
                        """
                        dialect_cursor.execute(dialect_query, char_batch + loc_batch)
                        batch_results = dialect_cursor.fetchall()

                        # 组织结果到嵌套字典
                        for row in batch_results:
                            char = row['漢字']
                            loc = row['簡稱']
                            if char not in char2loc2data:
                                char2loc2data[char] = {}
                            if loc not in char2loc2data[char]:
                                char2loc2data[char][loc] = []
                            char2loc2data[char][loc].append(row)

            # [OK] 批量查询多音字的全部音节（用于补充）
            char2all_syllables = {}
            polyphonic_chars = [c for c in clean_str if char2is_multi.get(c, False)]

            if polyphonic_chars:
                poly_placeholders = ','.join('?' * len(polyphonic_chars))
                all_syllables_query = f"""
                    SELECT 漢字, 音節, 註釋
                    FROM dialects
                    WHERE 漢字 IN ({poly_placeholders})
                """
                dialect_cursor.execute(all_syllables_query, polyphonic_chars)
                for row in dialect_cursor.fetchall():
                    char = row['漢字']
                    if char not in char2all_syllables:
                        char2all_syllables[char] = []
                    char2all_syllables[char].append(row)

            # [OK] 构建最终结果（按原字分组，过滤空数据候选字）
            for 原字 in chars:
                candidates = char2candidates.get(原字, [原字])

                # 第一步：检查每个候选字是否在所有地点都为空
                candidate_has_data = {}
                for candidate in candidates:
                    has_data = False
                    for location in all_locations:
                        dialect_results = char2loc2data.get(candidate, {}).get(location, [])
                        if dialect_results:  # 如果有任何数据
                            has_data = True
                            break
                    candidate_has_data[candidate] = has_data

                # 第二步：过滤候选字（至少保留一个）
                valid_candidates = [c for c in candidates if candidate_has_data.get(c, False)]
                if not valid_candidates:
                    # 如果所有候选都为空，保留第一个
                    valid_candidates = [candidates[0]]

                # 第三步：为每个有效候选字构建结果
                for candidate in valid_candidates:
                    for location in all_locations:
                        # 获取该候选字在该地点的方言数据
                        dialect_results = char2loc2data.get(candidate, {}).get(location, [])

                        syllable2notes = {}
                        is_polyphonic = False

                        for r in dialect_results:
                            syl = r['音節']
                            note = (r['註釋'] or '').strip()
                            if r['多音字'] == 1:
                                is_polyphonic = True
                            if syl not in syllable2notes:
                                syllable2notes[syl] = set()
                            if note:
                                syllable2notes[syl].add(note)

                        # 如果是多音字但只有一个或零个音节，补充全部音节
                        if is_polyphonic and len(syllable2notes) <= 1:
                            for rr in char2all_syllables.get(candidate, []):
                                syl = rr['音節']
                                note = (rr['註釋'] or '').strip()
                                if syl not in syllable2notes:
                                    syllable2notes[syl] = set()
                                if note:
                                    syllable2notes[syl].add(note)

                        syllables = list(syllable2notes.keys())
                        notes = ['; '.join(sorted(syllable2notes[syl])) if syllable2notes[syl] else '_'
                                 for syl in syllables]

                        result.append({
                            'char': candidate,  # 返回候选字（不是原字）
                            '音节': syllables,
                            'location': location,
                            'positions': char2positions.get(candidate, []),
                            'notes': notes
                        })

        finally:
            pass  # 连接池会自动管理连接

    return result


