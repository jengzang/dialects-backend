"""
子集筛选 API
Subset filter endpoint — single-request village filtering with semantic,
structural, and spatial dimensions for subset analysis.
"""
from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query
from ..schema_runtime import qcolumn, qtable
from ..models import SubsetFilterRequest, SubsetFilterResponse, SubsetVillageItem

router = APIRouter(prefix="/subset")

_SEMANTIC_CATEGORIES = {
    "agriculture", "clan", "direction", "infrastructure",
    "mountain", "settlement", "symbolic", "vegetation", "water",
}

_STRUCTURE_PATTERN_COLS = {
    "modifier_head": ("has_modifier = 1", "has_head = 1"),
    "modifier_only": ("has_modifier = 1", "has_head = 0"),
    "head_only":    ("has_modifier = 0", "has_head = 1"),
    "settlement":   ("has_settlement = 1",),
}


def _qcol(dbpath, table, column):
    return qcolumn(dbpath, table, column)


def _qtbl(dbpath, table):
    return qtable(dbpath, table)


@router.post("/filter", response_model=SubsetFilterResponse)
def filter_villages(
    req: SubsetFilterRequest,
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """筛选村庄，一次返回全部匹配结果。所有条件 AND 关系，同组内 OR。"""
    v_tbl = _qtbl(dbpath, "villages")
    vf_tbl = _qtbl(dbpath, "village_features")
    vss_tbl = _qtbl(dbpath, "village_semantic_structure")

    V = lambda c: f"v.{_qcol(dbpath, 'villages', c)}"
    VF = lambda c: f"vf.{_qcol(dbpath, 'village_features', c)}"
    VSS = lambda c: f"vss.{_qcol(dbpath, 'village_semantic_structure', c)}"

    conditions: list[str] = [f"{V('name')} IS NOT NULL AND {V('name')} != ''"]
    params: list = []

    # ---- 区域 ----
    if req.city is not None:
        conditions.append(f"{V('city')} = ?")
        params.append(req.city)
    if req.county is not None:
        conditions.append(f"{V('county')} = ?")
        params.append(req.county)
    if req.township is not None:
        conditions.append(f"{V('township')} = ?")
        params.append(req.township)

    # ---- 名称 ----
    if req.keyword and req.keyword.strip():
        kw = req.keyword.strip()
        mode = req.name_match_mode
        if mode not in ("contains", "startsWith", "endsWith", "equals"):
            raise HTTPException(status_code=400, detail=f"Invalid name_match_mode: {mode}")
        if mode == "equals":
            conditions.append(f"{V('name')} = ?")
            params.append(kw)
        elif mode == "startsWith":
            conditions.append(f"{V('name')} LIKE ?")
            params.append(f"{kw}%")
        elif mode == "endsWith":
            conditions.append(f"{V('name')} LIKE ?")
            params.append(f"%{kw}")
        else:  # contains
            conditions.append(f"{V('name')} LIKE ?")
            params.append(f"%{kw}%")

    length_expr = f"LENGTH({V('name')})"
    if req.length is not None:
        conditions.append(f"{length_expr} = ?")
        params.append(req.length)
    else:
        if req.min_length is not None:
            conditions.append(f"{length_expr} >= ?")
            params.append(req.min_length)
        if req.max_length is not None:
            conditions.append(f"{length_expr} <= ?")
            params.append(req.max_length)

    # ---- 语义 ----
    if req.semantic_categories:
        unknown = set(req.semantic_categories) - _SEMANTIC_CATEGORIES
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown semantic categories: {', '.join(sorted(unknown))}")
        sem_conds = [f"{VF(f'sem_{cat}')} = 1" for cat in req.semantic_categories]
        sep = " OR " if req.semantic_match == "any" else " AND "
        conditions.append(f"({sep.join(sem_conds)})")

    # ---- 结构 ----
    if req.suffix is not None:
        conditions.append(f"{VF('suffix_1')} = ?")
        params.append(req.suffix)

    if req.prefix is not None:
        conditions.append(f"{VF('prefix_1')} = ?")
        params.append(req.prefix)

    if req.char_at_position is not None and req.char_at_value is not None:
        conditions.append(f"SUBSTR({V('name')}, ?, 1) = ?")
        params.append(req.char_at_position)
        params.append(req.char_at_value)

    if req.structure_patterns:
        pattern_conds = []
        for p in req.structure_patterns:
            if p not in _STRUCTURE_PATTERN_COLS:
                raise HTTPException(status_code=400, detail=f"Unknown structure pattern: {p}")
            clauses = []
            for clause in _STRUCTURE_PATTERN_COLS[p]:
                col, op, val = clause.split()
                clauses.append(f"{VSS(col)} {op} {val}")
            pattern_conds.append(f"({' AND '.join(clauses)})")
        conditions.append(f"({' OR '.join(pattern_conds)})")

    # ---- 空间 ----
    if req.lon_min is not None:
        conditions.append(f"{V('longitude')} >= ?")
        params.append(req.lon_min)
    if req.lon_max is not None:
        conditions.append(f"{V('longitude')} <= ?")
        params.append(req.lon_max)
    if req.lat_min is not None:
        conditions.append(f"{V('latitude')} >= ?")
        params.append(req.lat_min)
    if req.lat_max is not None:
        conditions.append(f"{V('latitude')} <= ?")
        params.append(req.lat_max)

    # ---- JOIN ----
    need_features = bool(
        req.semantic_categories or req.suffix is not None or req.prefix is not None
    )
    need_structure = bool(req.structure_patterns)

    joins = ""
    if need_features:
        joins += f" LEFT JOIN {vf_tbl} AS vf ON {V('village_id')} = {VF('village_id')}"
    if need_structure:
        joins += f" LEFT JOIN {vss_tbl} AS vss ON {V('village_id')} = {VSS('village_id')}"

    where_clause = " AND ".join(conditions)

    # ---- 查询 ----
    from_clause = f"{v_tbl} AS v{joins}"

    count_sql = f"SELECT COUNT(*) as total FROM {from_clause} WHERE {where_clause}"
    total = execute_query(db, count_sql, tuple(params))[0]["total"]

    data_sql = f"""
        SELECT
            v.ROWID as id,
            {V('name')} as name,
            {V('city')} as city,
            {V('county')} as county,
            {length_expr} as name_length
        FROM {from_clause}
        WHERE {where_clause}
        LIMIT ?
    """
    rows = execute_query(db, data_sql, tuple(params + [req.max_results]))

    villages = [SubsetVillageItem(**r) for r in rows]
    return SubsetFilterResponse(villages=villages, total=total)
