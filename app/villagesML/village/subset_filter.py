"""
子集筛选 API
Subset filter endpoint — single-request village filtering for subset analysis
"""
from fastapi import APIRouter, Depends
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query
from ..schema_runtime import qcolumn, qtable
from ..models import SubsetFilterRequest, SubsetFilterResponse, SubsetVillageItem

router = APIRouter(prefix="/subset")


@router.post("/filter", response_model=SubsetFilterResponse)
def filter_villages(
    req: SubsetFilterRequest,
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """筛选村庄，一次返回全部匹配结果（无分页）。"""
    villages_table = qtable(dbpath, "villages")
    name_col = qcolumn(dbpath, "villages", "name")
    city_col = qcolumn(dbpath, "villages", "city")
    county_col = qcolumn(dbpath, "villages", "county")
    township_col = qcolumn(dbpath, "villages", "township")

    conditions = [f"{name_col} IS NOT NULL AND {name_col} != ''"]
    params = []

    if req.keyword and req.keyword.strip():
        conditions.append(f"{name_col} LIKE ?")
        params.append(f"%{req.keyword.strip()}%")

    if req.city is not None:
        conditions.append(f"{city_col} = ?")
        params.append(req.city)

    if req.county is not None:
        conditions.append(f"{county_col} = ?")
        params.append(req.county)

    if req.township is not None:
        conditions.append(f"{township_col} = ?")
        params.append(req.township)

    length_expr = f"LENGTH({name_col})"
    if req.min_length is not None:
        conditions.append(f"{length_expr} >= ?")
        params.append(req.min_length)
    if req.max_length is not None:
        conditions.append(f"{length_expr} <= ?")
        params.append(req.max_length)

    where_clause = " AND ".join(conditions)

    count_sql = f"SELECT COUNT(*) as total FROM {villages_table} WHERE {where_clause}"
    total = execute_query(db, count_sql, tuple(params))[0]["total"]

    data_sql = f"""
        SELECT
            ROWID as id,
            {name_col} as name,
            {city_col} as city,
            {county_col} as county,
            {length_expr} as name_length
        FROM {villages_table}
        WHERE {where_clause}
        LIMIT ?
    """
    rows = execute_query(db, data_sql, tuple(params + [req.max_results]))

    villages = [SubsetVillageItem(**r) for r in rows]
    return SubsetFilterResponse(villages=villages, total=total)
