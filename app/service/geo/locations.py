from __future__ import annotations

from typing import Any

from app.sql.db_pool import get_db_pool


DETAIL_COLUMNS = [
    "簡稱",
    "語言",
    "地圖集二分區",
    "音典分區",
    "字表來源（母本）",
    "經緯度",
    "省",
    "市",
    "縣",
    "鎮",
    "行政村",
    "自然村",
    "T1陰平",
    "T2陽平",
    "T3陰上",
    "T4陽上",
    "T5陰去",
    "T6陽去",
    "T7陰入",
    "T8陽入",
    "T9其他調",
    "T10輕聲",
]

PARTITION_COLUMNS = [
    "簡稱",
    "語言",
    "存儲標記",
    "地圖集二分區",
    "音典分區",
    "省",
    "市",
    "縣",
    "鎮",
    "行政村",
    "自然村",
]


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def get_location_detail_rows(name: str, query_db: str) -> list[dict[str, Any]]:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        return []

    pool = get_db_pool(query_db)
    select_clause = ", ".join(_quote_identifier(column) for column in DETAIL_COLUMNS)
    sql = (
        f"SELECT {select_clause} "
        f'FROM {_quote_identifier("dialects")} '
        f'WHERE {_quote_identifier("簡稱")} = ? '
        "LIMIT 1"
    )

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (cleaned_name,))
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_location_partition_rows(query_db: str) -> list[dict[str, Any]]:
    pool = get_db_pool(query_db)
    select_clause = ", ".join(_quote_identifier(column) for column in PARTITION_COLUMNS)
    sql = (
        f"SELECT {select_clause} "
        f'FROM {_quote_identifier("dialects")} '
        f'WHERE TRIM(COALESCE({_quote_identifier("簡稱")}, "")) <> ""'
    )

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]
