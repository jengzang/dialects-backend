import numpy as np
from fastapi import HTTPException

from common.config import CHARACTERS_DB_PATH, DIALECTS_DB_USER

import sqlite3

from common.s2t import s2t_pro
from common.getloc_by_name_region import query_dialect_abbreviations


def search_characters(chars, locations=None, regions=None, db_path=DIALECTS_DB_USER, region_mode='yindian'):
    all_locations = query_dialect_abbreviations(regions, locations, region_mode=region_mode)
    if not all_locations:
        raise HTTPException(status_code=400, detail="🛑 請輸入正確的地點！\n建議點擊地點輸入框下方的提示地點！")

    if isinstance(chars, str):
        chars = list(chars)
    elif isinstance(chars, (list, np.ndarray)):
        chars = [char for sublist in chars for char in
                 (sublist if isinstance(sublist, (list, np.ndarray)) else [sublist])]

    clean_str, _ = s2t_pro(chars, level=2)

    result = []

    dialect_conn = sqlite3.connect(db_path)
    dialect_conn.row_factory = sqlite3.Row
    characters_conn = sqlite3.connect(CHARACTERS_DB_PATH)
    characters_conn.row_factory = sqlite3.Row

    # ✅ 优化：共用游标，避免频繁创建
    dialect_cursor = dialect_conn.cursor()
    all_syllables_cursor = dialect_conn.cursor()
    characters_cursor = characters_conn.cursor()
    position_cursor = characters_conn.cursor()

    # ✅ 优化：缓存字符地位信息
    char2positions = {}
    for char in clean_str:
        characters_query = """
            SELECT 攝, 呼, 等, 韻, 調, 組, 母, 部位, 方式, 多地位標記
            FROM characters
            WHERE 漢字 = ?
        """
        characters_cursor.execute(characters_query, [char])
        characters_results = characters_cursor.fetchall()

        positions = []
        is_multi = any(row['多地位標記'] == 1 for row in characters_results)

        if is_multi:
            position_query = """
                SELECT 攝, 呼, 等, 韻, 調, 組, 母, 部位, 方式,
                FROM characters
                WHERE 多地位標記 = 1 AND 漢字 = ?
            """
            position_cursor.execute(position_query, [char])
            for row in position_cursor.fetchall():
                parts = f"{row['攝']}{row['呼']}{row['等']}{row['韻']}{row['調']}"
                meta = f"{row['組']}·{row['母']}•{row['部位']}·{row['方式']}音"
                # if row['釋義']:
                #     meta += f"<br>（{row['釋義']}）"
                positions.append(f"{parts},{meta}")
        else:
            for row in characters_results:
                parts = f"{row['攝']}{row['呼']}{row['等']}{row['韻']}{row['調']}"
                meta = f"{row['組']}·{row['母']}•{row['部位']}·{row['方式']}音"
                # if row['釋義']:
                #     meta += f"<br>（{row['釋義']}）"
                positions.append(f"{parts},{meta}")

        char2positions[char] = positions

    # ✅ 优化：缓存多音字全注释查詢
    char2all_syllables = {}

    try:
        for char in clean_str:
            for location in all_locations:
                dialect_query = """
                    SELECT 音節, 多音字, 註釋, 簡稱
                    FROM dialects
                    WHERE 漢字 = ? AND 簡稱 = ?
                """
                dialect_cursor.execute(dialect_query, [char, location])
                dialect_results = dialect_cursor.fetchall()

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

                if is_polyphonic and len(syllable2notes) <= 1:
                    if char not in char2all_syllables:
                        all_syllables_query = """
                            SELECT 音節, 註釋
                            FROM dialects
                            WHERE 漢字 = ?
                        """
                        all_syllables_cursor.execute(all_syllables_query, [char])
                        char2all_syllables[char] = all_syllables_cursor.fetchall()

                    for rr in char2all_syllables[char]:
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
                    'positions': char2positions[char],  # ✅ 使用缓存
                    'notes': notes
                })

    finally:
        dialect_conn.close()
        characters_conn.close()

    return result



