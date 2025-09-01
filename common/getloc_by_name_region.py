import os
import sqlite3
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import get_db
from app.custom.models import Information
from common.config import QUERY_DB_ADMIN


def query_dialect_abbreviations(
        region_input=None,
        location_sequence=None,
        db_path=QUERY_DB_ADMIN,
        tables="dialects",
        need_storage_flag=True,  # 是否需要存儲標記
        region_mode='yindian',
        debug=False
):
    """
    查詢 dialects 表的簡稱欄位，支持完全匹配和元素模糊匹配。

    參數：
    - region_input: 字串或列表。可為完整分區字串（如 '華北-河北-東北'）或單個元素（如 '河北'）或元素列表
    - location_sequence: 地點字串，如 '河北/歷史音；東北'
    - debug: 是否輸出調試資訊
    - region_mode:地圖集二分區-map；音典分區-yindian

    返回：
    - 簡稱列表（排序去重）
    """

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"資料庫不存在: {db_path}")

    if debug:
        print("=== 查詢開始 ===")
        print(f"region_input: {region_input}")
        print(f"location_sequence: {location_sequence}")

    # 處理 region_input 為列表
    if isinstance(region_input, str):
        region_list = [region_input.strip()]
    elif isinstance(region_input, list):
        region_list = [r.strip() for r in region_input if isinstance(r, str)]
    else:
        region_list = []

    if isinstance(location_sequence, str):
        location_list = [location_sequence.strip()]
    elif isinstance(location_sequence, list):
        location_list = [item.strip() for item in location_sequence if isinstance(item, str)]
    else:
        location_list = []

    combined_elements = list(set(region_list))

    if debug:
        print(f"分區合併後元素: {combined_elements}")

    result = []
    seen = set()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # 根據 region_mode 決定使用哪個分區欄位
        partition_column = "地圖集二分區" if region_mode == "map" else "音典分區"
        if debug:
            print(region_mode)
            print(partition_column)
            print(db_path)
        query = f"""
            SELECT {partition_column}, 簡稱 
            FROM {tables} 
            WHERE 1=1
        """
        if need_storage_flag:
            query += " AND 存儲標記 IS NOT NULL AND 存儲標記 != ''"
        cursor.execute(query)
        all_rows = cursor.fetchall()

        for item in region_list:
            found_exact = False
            for partition_str, abbr in all_rows:
                if item == partition_str:
                    if abbr not in seen:
                        result.append(abbr)
                        seen.add(abbr)
                    found_exact = True
            if not found_exact:
                for partition_str, abbr in all_rows:
                    if item in partition_str.split("-"):
                        if abbr not in seen:
                            result.append(abbr)
                            seen.add(abbr)

    # 最終結果：保留匹配順序，直接拼接原始地點
    final_result = result + location_list

    if debug:
        print(f"=== 最終結果（保留資料庫順序 + 地點）: {final_result} ===")

    return final_result


def query_dialect_abbreviations_orm(
        db: Session,
        user=User,
        region_input=None,
        location_sequence=None,
        need_storage_flag=True,  # 是否需要存儲標記
        debug=False,
):
    """
    查詢 dialects 表的簡稱欄位，支持完全匹配和元素模糊匹配。

    參數：
    - region_input: 字串或列表。可為完整音典分區字串（如 '華北-河北-東北'）或單個元素（如 '河北'）或元素列表
    - location_sequence: 地點字串，如 '河北/歷史音；東北'
    - debug: 是否輸出調試資訊
    - db: 只有當傳入 db 參數時，才會使用 ORM 查詢
    - user: 傳遞用戶信息（如果需要）

    返回：
    - 簡稱列表（排序去重）
    """

    if not db:
        raise ValueError("需要傳入 db 參數以啟用 ORM 查詢")

    if debug:
        print("=== 查詢開始 ===")
        print(f"region_input: {region_input}")
        print(f"location_sequence: {location_sequence}")

    # 處理 region_input 為列表
    if isinstance(region_input, str):
        region_list = [region_input.strip()]
    elif isinstance(region_input, list):
        region_list = [r.strip() for r in region_input if isinstance(r, str)]
    else:
        region_list = []

    if isinstance(location_sequence, str):
        location_list = [location_sequence.strip()]
    elif isinstance(location_sequence, list):
        location_list = [item.strip() for item in location_sequence if isinstance(item, str)]
    else:
        location_list = []

    combined_elements = list(set(region_list))

    if debug:
        print(f"分區合併後元素: {combined_elements}")

    result = []
    seen = set()

    # 使用 ORM 查詢
    query = db.query(Information).filter(Information.存儲標記.isnot(None))  # 存儲標記非空
    if need_storage_flag:
        query = query.filter(Information.存儲標記 != '')

    # 如果有 user 信息，可以根據 user 進行過濾
    if user:
        query = query.filter(Information.user_id == user.id)

    orm_rows = query.all()

    for orm_row in orm_rows:
        partition_str = orm_row.音典分區  # 根據實際屬性名來訪問
        abbr = orm_row.簡稱  # 根據實際屬性名來訪問

        for item in region_list:
            found_exact = False
            if item == partition_str:
                if abbr not in seen:
                    result.append(abbr)
                    seen.add(abbr)
                found_exact = True
            if not found_exact:
                if item in partition_str.split("-"):
                    if abbr not in seen:
                        result.append(abbr)
                        seen.add(abbr)

    # 最終結果：保留匹配順序，直接拼接原始地點
    final_result = result + location_list

    if debug:
        print(f"=== 最終結果（保留資料庫順序 + 地點）: {final_result} ===")

    return final_result


# result = query_dialect_abbreviations(region_input=['客家話'],location_sequence= [],debug=True,region_mode='map')
