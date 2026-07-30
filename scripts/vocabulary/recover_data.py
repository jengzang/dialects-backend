"""从 /tmp/vocabulary_restored.db 的 lost_and_found 恢复数据到 data/vocabulary.db"""

import sqlite3


def recover():
    src = sqlite3.connect('/tmp/vocabulary_restored.db')

    # nfield=9: vocabulary_entries (c1=user_id, c2=location_name, c3=standard_word, c4=local_expression, c5=ipa, c6=notes, c7=informations, c8=source_filename)
    rows = src.execute(
        "SELECT DISTINCT c0,c1,c2,c3,c4,c5,c6,c7,c8 FROM lost_and_found WHERE nfield=9 AND c2 IS NOT NULL ORDER BY id"
    ).fetchall()

    # 去重: (user_id, location_name, standard_word)
    seen = set()
    unique = []
    for r in rows:
        key = (r[1], r[2], r[3])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    print(f"去重后: {len(unique)} 行 (原始找回 {len(rows)} 行)")

    # 按 location 统计
    from collections import Counter
    for loc, cnt in Counter(r[2] for r in unique).most_common():
        print(f"  {loc}: {cnt} entries")

    # 写入
    dst = sqlite3.connect("data/vocabulary.db")
    inserted = 0
    for r in unique:
        dst.execute(
            "INSERT INTO vocabulary_entries (user_id, location_name, standard_word, local_expression, ipa, notes, informations, source_filename) VALUES (?,?,?,?,?,?,?,?)",
            (r[1], r[2], r[3], r[4], r[5], r[6] or "", r[7] or "", r[8] or ""),
        )
        inserted += 1

    dst.commit()
    dst.close()
    src.close()
    print(f"\n写入 data/vocabulary.db: {inserted} 行")


if __name__ == "__main__":
    recover()
