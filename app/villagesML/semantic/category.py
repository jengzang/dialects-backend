"""
语义类别API
Semantic Category API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List, Optional
import sqlite3

from ..dependencies import get_db_connection, get_dbpath, execute_query
from ..models import SemanticCategory, SemanticTendency
from ..schema_runtime import qcolumn, qtable

router = APIRouter(prefix="/semantic/category")


def _get_semantic_categories_sync(dbpath: str):
    """同步获取所有语义类别"""
    with get_db_connection(dbpath) as db:
        table = qtable(dbpath, "semantic_vtf_global")
        category_col = qcolumn(dbpath, "semantic_vtf_global", "category")
        vtf_count_col = qcolumn(dbpath, "semantic_vtf_global", "vtf_count")

        query = f"""
            SELECT
                {category_col} as category,
                {category_col} as description,
                {vtf_count_col} as character_count
            FROM {table}
            ORDER BY {category_col}
        """
        results = execute_query(db, query, ())
        if not results:
            raise HTTPException(status_code=404, detail="No semantic categories found")
        return results


@router.get("/list", response_model=List[SemanticCategory])
async def get_semantic_categories(dbpath: str = Depends(get_dbpath)):
    """
    获取所有语义类别
    Get all semantic categories

    Returns:
        List[SemanticCategory]: 语义类别列表
    """
    return await run_in_threadpool(_get_semantic_categories_sync, dbpath)


def _get_global_semantic_vtf_sync(dbpath: str, category: Optional[str], detail: bool = False):
    """同步获取全局语义虚拟词频"""
    with get_db_connection(dbpath) as db:
        if detail:
            table = qtable(dbpath, "semantic_subcategory_vtf_global")
            subcategory_col = qcolumn(dbpath, "semantic_subcategory_vtf_global", "subcategory")
            parent_col = qcolumn(dbpath, "semantic_subcategory_vtf_global", "parent_category")
            char_count_col = qcolumn(dbpath, "semantic_subcategory_vtf_global", "char_count")
            village_count_col = qcolumn(dbpath, "semantic_subcategory_vtf_global", "village_count")
            vtf_col = qcolumn(dbpath, "semantic_subcategory_vtf_global", "vtf")
            pct_col = qcolumn(dbpath, "semantic_subcategory_vtf_global", "percentage")

            query = f"""
                SELECT
                    {subcategory_col} as subcategory,
                    {parent_col} as parent_category,
                    {char_count_col} as char_count,
                    {village_count_col} as village_count,
                    {vtf_col} as vtf,
                    {pct_col} as percentage
                FROM {table}
                WHERE 1=1
            """
            params = []
            filter_col = parent_col
        else:
            table = qtable(dbpath, "semantic_vtf_global")
            category_col = qcolumn(dbpath, "semantic_vtf_global", "category")
            vtf_col = qcolumn(dbpath, "semantic_vtf_global", "vtf")
            village_count_col = qcolumn(dbpath, "semantic_vtf_global", "village_count")
            char_count_col = qcolumn(dbpath, "semantic_vtf_global", "char_count")
            total_villages_col = qcolumn(dbpath, "semantic_vtf_global", "total_villages")

            query = f"""
                SELECT
                    {category_col} as category,
                    {vtf_col} AS vtf,
                    {village_count_col} AS village_count,
                    {char_count_col} AS char_count,
                    {total_villages_col} AS total_villages
                FROM {table}
                WHERE 1=1
            """
            params = []
            filter_col = category_col

        if category is not None:
            query += f" AND {filter_col} = ?"
            params.append(category)

        query += " ORDER BY vtf DESC"
        results = execute_query(db, query, tuple(params))

        if not results:
            raise HTTPException(status_code=404, detail="No VTF data found")
        return results


@router.get("/vtf/global")
async def get_global_semantic_vtf(
    category: Optional[str] = Query(None, description="语义类别过滤（detail=false按大类，detail=true按父类）"),
    detail: bool = Query(False, description="是否使用子类别表（53子类别，v4词典）"),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取全局语义虚拟词频
    Get global semantic VTF (Virtual Term Frequency)

    Args:
        category: 语义类别（可选）
        detail: 是否使用子类别表（53子类别，v4词典），默认False（9大类别）

    Returns:
        List[dict]: 语义VTF列表
    """
    return await run_in_threadpool(_get_global_semantic_vtf_sync, dbpath, category, detail)


def _get_regional_semantic_vtf_sync(dbpath: str, run_id: str, region_level: str, region_name: Optional[str], city: Optional[str], county: Optional[str], township: Optional[str], category: Optional[str], detail: bool = False):
    """同步获取区域语义虚拟词频"""
    with get_db_connection(dbpath) as db:
        if detail:
            table = qtable(dbpath, "semantic_subcategory_vtf_regional")
            region_level_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "region_level")
            region_name_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "region_name")
            city_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "city")
            county_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "county")
            township_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "township")
            subcategory_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "subcategory")
            parent_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "parent_category")
            char_count_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "char_count")
            village_count_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "village_count")
            vtf_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "vtf")
            pct_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "percentage")
            tendency_col = qcolumn(dbpath, "semantic_subcategory_vtf_regional", "tendency")

            query = f"""
                SELECT
                    {region_level_col} as region_level,
                    {region_name_col} as region_name,
                    {city_col} as city,
                    {county_col} as county,
                    {township_col} as township,
                    {subcategory_col} as subcategory,
                    {parent_col} as parent_category,
                    {char_count_col} as char_count,
                    {village_count_col} as village_count,
                    {vtf_col} as vtf,
                    {pct_col} as percentage,
                    {tendency_col} as tendency
                FROM {table}
                WHERE {region_level_col} = ?
            """
            params = [region_level]

            if city is not None:
                query += f" AND {city_col} = ?"
                params.append(city)
            if county is not None:
                query += f" AND {county_col} = ?"
                params.append(county)
            elif city is not None and region_level == 'township':
                query += f" AND ({county_col} IS NULL OR {county_col} = '')"
            if township is not None:
                query += f" AND {township_col} = ?"
                params.append(township)

            if region_name is not None:
                query += f" AND ({city_col} = ? OR {county_col} = ? OR {township_col} = ?)"
                params.extend([region_name, region_name, region_name])

            if category is not None:
                query += f" AND {parent_col} = ?"
                params.append(category)

            query += f" ORDER BY {vtf_col} DESC"
        else:
            table = qtable(dbpath, "semantic_regional_analysis")
            region_level_col = qcolumn(dbpath, "semantic_regional_analysis", "region_level")
            region_name_col = qcolumn(dbpath, "semantic_regional_analysis", "region_name")
            city_col = qcolumn(dbpath, "semantic_regional_analysis", "city")
            county_col = qcolumn(dbpath, "semantic_regional_analysis", "county")
            township_col = qcolumn(dbpath, "semantic_regional_analysis", "township")
            category_col = qcolumn(dbpath, "semantic_regional_analysis", "category")
            frequency_col = qcolumn(dbpath, "semantic_regional_analysis", "frequency")

            query = f"""
                SELECT
                    {region_level_col} as region_level,
                    {region_name_col} as region_name,
                    {city_col} as city,
                    {county_col} as county,
                    {township_col} as township,
                    {category_col} as category,
                    {frequency_col} AS vtf,
                    {frequency_col} AS intensity_index
                FROM {table}
                WHERE {region_level_col} = ?
            """
            params = [region_level]

            if city is not None:
                query += f" AND {city_col} = ?"
                params.append(city)
            if county is not None:
                query += f" AND {county_col} = ?"
                params.append(county)
            elif city is not None and region_level == 'township':
                query += f" AND ({county_col} IS NULL OR {county_col} = '')"
            if township is not None:
                query += f" AND {township_col} = ?"
                params.append(township)

            if region_name is not None:
                query += f" AND ({city_col} = ? OR {county_col} = ? OR {township_col} = ?)"
                params.extend([region_name, region_name, region_name])

            if category is not None:
                query += f" AND {category_col} = ?"
                params.append(category)

            query += f" ORDER BY {region_name_col}, {frequency_col} DESC"

        results = execute_query(db, query, tuple(params))

        if not results:
            raise HTTPException(status_code=404, detail=f"No regional VTF data found")
        return results


@router.get("/vtf/regional")
async def get_regional_semantic_vtf(
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    category: Optional[str] = Query(None, description="语义类别（detail=false按大类，detail=true按父类）"),
    detail: bool = Query(False, description="是否使用子类别表（53子类别，v4词典）"),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域语义虚拟词频
    Get regional semantic VTF

    Args:
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        category: 语义类别（可选）
        detail: 是否使用子类别表（53子类别，v4词典），默认False（9大类别）

    Returns:
        List[dict]: 区域语义VTF列表
    """
    return await run_in_threadpool(_get_regional_semantic_vtf_sync, dbpath, None, region_level, region_name, city, county, township, category, detail)


def _get_semantic_tendency_sync(dbpath: str, run_id: str, region_level: str, region_name: Optional[str], city: Optional[str], county: Optional[str], township: Optional[str], top_n: int):
    """同步获取区域语义倾向性"""
    with get_db_connection(dbpath) as db:
        table = qtable(dbpath, "semantic_regional_analysis")
        region_level_col = qcolumn(dbpath, "semantic_regional_analysis", "region_level")
        region_name_col = qcolumn(dbpath, "semantic_regional_analysis", "region_name")
        city_col = qcolumn(dbpath, "semantic_regional_analysis", "city")
        county_col = qcolumn(dbpath, "semantic_regional_analysis", "county")
        township_col = qcolumn(dbpath, "semantic_regional_analysis", "township")
        category_col = qcolumn(dbpath, "semantic_regional_analysis", "category")
        lift_col = qcolumn(dbpath, "semantic_regional_analysis", "lift")
        z_score_col = qcolumn(dbpath, "semantic_regional_analysis", "z_score")

        query = f"""
            SELECT
                {region_level_col} as region_level,
                {region_name_col} as region_name,
                {city_col} as city,
                {county_col} as county,
                {township_col} as township,
                {category_col} as category,
                {lift_col} as lift,
                {z_score_col} as z_score
            FROM {table}
            WHERE {region_level_col} = ?
        """
        params = [region_level]

        # 优先使用层级参数（精确匹配）
        if city is not None:
            query += f" AND {city_col} = ?"
            params.append(city)
        if county is not None:
            query += f" AND {county_col} = ?"
            params.append(county)
        elif city is not None and region_level == 'township':
            # Handle 东莞市/中山市 (no county level)
            query += f" AND ({county_col} IS NULL OR {county_col} = '')"
        if township is not None:
            query += f" AND {township_col} = ?"
            params.append(township)

        # 向后兼容：region_name（模糊匹配）
        if region_name is not None:
            query += f" AND ({city_col} = ? OR {county_col} = ? OR {township_col} = ?)"
            params.extend([region_name, region_name, region_name])

        query += f" ORDER BY {z_score_col} DESC LIMIT ?"
        params.append(top_n)

        results = execute_query(db, query, tuple(params))

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No semantic tendency data found"
            )
        return results


@router.get("/tendency", response_model=List[SemanticTendency])
async def get_semantic_tendency(
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    top_n: int = Query(9, ge=1, le=20, description="返回前N个类别"),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域语义倾向性
    Get semantic tendency for a region

    Args:
        region_level: 区域级别
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        top_n: 返回前N个类别

    Returns:
        List[SemanticTendency]: 语义倾向性列表
    """
    return await run_in_threadpool(_get_semantic_tendency_sync, dbpath, None, region_level, region_name, city, county, township, top_n)
