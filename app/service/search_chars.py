import numpy as np
from fastapi import HTTPException

from common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH

from common.s2t import s2t_pro
from app.service.getloc_by_name_region import query_dialect_abbreviations
# [NEW] 导入连接池
from app.sql.db_pool import get_db_pool


def search_characters(chars, locations=None, regions=None, db_path=DIALECTS_DB_USER, region_mode='yindian', query_db_path=QUERY_DB_USER):
    """
    Args:
        db_path: 方言数据库路径（用于查询实际读音数据）
        query_db_path: 查询数据库路径（用于查询地点信息）
    """
    all_locations = query_dialect_abbreviations(regions, locations, db_path=query_db_path, region_mode=region_mode)
    if not all_locations:
        raise HTTPException(status_code=400, detail="🛑 請輸入正確的地點！\n建議點擊地點輸入框下方的提示地點！")

    if isinstance(chars, str):
        chars = list(chars)
    elif isinstance(chars, (list, np.ndarray)):
        chars = [char for sublist in chars for char in
                 (sublist if isinstance(sublist, (list, np.ndarray)) else [sublist])]

    clean_str, _ = s2t_pro(chars, level=2)

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
            characters_query = f"""
                SELECT 漢字, 攝, 呼, 等, 韻, 調, 組, 母, 部位, 方式, 多地位標記
                FROM characters
                WHERE 漢字 IN ({char_placeholders})
            """
            characters_cursor.execute(characters_query, clean_str)
            characters_results = characters_cursor.fetchall()

            # 按字符组织结果
            char2rows = {}
            for row in characters_results:
                char = row['漢字']
                if char not in char2rows:
                    char2rows[char] = []
                char2rows[char].append(row)

            # 处理每个字符的地位信息
            for char in clean_str:
                rows = char2rows.get(char, [])
                positions = []
                is_multi = any(row['多地位標記'] == 1 for row in rows)
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
                # 对于大量数据，需要分批处理
                MAX_PARAMS = 900  # 留一些余量
                char_loc_pairs = [(c, loc) for c in clean_str for loc in all_locations]

                # 分批查询
                for i in range(0, len(char_loc_pairs), MAX_PARAMS // 2):
                    batch = char_loc_pairs[i:i + MAX_PARAMS // 2]
                    pair_placeholders = ','.join(['(?,?)'] * len(batch))
                    flat_params = [val for pair in batch for val in pair]

                    dialect_query = f"""
                        SELECT 漢字, 簡稱, 音節, 多音字, 註釋
                        FROM dialects
                        WHERE (漢字, 簡稱) IN ({pair_placeholders})
                    """
                    dialect_cursor.execute(dialect_query, flat_params)
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

            # [OK] 构建最终结果（在内存中组装，不再查询数据库）
            for char in clean_str:
                for location in all_locations:
                    # 获取该字符在该地点的方言数据
                    dialect_results = char2loc2data.get(char, {}).get(location, [])

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
                        for rr in char2all_syllables.get(char, []):
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
                        'char': char,
                        '音节': syllables,
                        'location': location,
                        'positions': char2positions.get(char, []),
                        'notes': notes
                    })

        finally:
            pass  # 连接池会自动管理连接

    return result



