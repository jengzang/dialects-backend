"""Spatial hotspot and cluster APIs."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import execute_query, execute_single, get_db, get_dbpath
from ..run_id_manager import get_run_id_manager
from ..schema_runtime import qcolumn, qtable, run_id_analysis_type
from ..schema_keys import C, T

router = APIRouter(prefix="/spatial")


@router.get("/hotspots")
def get_spatial_hotspots(
    run_id: Optional[str] = Query(None, description="Spatial analysis run id"),
    min_density: Optional[float] = Query(None, description="Minimum density score"),
    min_village_count: Optional[int] = Query(None, ge=1, description="Minimum village count"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get spatial density hotspots."""
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.SPATIAL_HOTSPOTS)
        )

    table = qtable(dbpath, T.SPATIAL_HOTSPOTS)
    run_id_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.RUN_ID)
    hotspot_id_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.HOTSPOT_ID)
    center_lon_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.CENTER_LON)
    center_lat_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.CENTER_LAT)
    density_score_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.DENSITY_SCORE)
    village_count_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.VILLAGE_COUNT)
    radius_km_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.RADIUS_KM)

    query = f"""
        SELECT
            {hotspot_id_col} as hotspot_id,
            {center_lon_col} as center_lon,
            {center_lat_col} as center_lat,
            {density_score_col} as density_score,
            {village_count_col} as village_count,
            {radius_km_col} as radius_km
        FROM {table}
        WHERE {run_id_col} = ?
    """
    params = [run_id]

    if min_density is not None:
        query += f" AND {density_score_col} >= ?"
        params.append(min_density)

    if min_village_count is not None:
        query += f" AND {village_count_col} >= ?"
        params.append(min_village_count)

    query += f" ORDER BY {density_score_col} DESC"
    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail=f"No spatial hotspots found for run_id: {run_id}")

    return results


@router.get("/hotspots/{hotspot_id}")
def get_hotspot_detail(
    hotspot_id: int,
    run_id: Optional[str] = Query(None, description="Spatial analysis run id"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get one hotspot detail."""
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.SPATIAL_HOTSPOTS)
        )

    table = qtable(dbpath, T.SPATIAL_HOTSPOTS)
    run_id_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.RUN_ID)
    hotspot_id_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.HOTSPOT_ID)
    center_lon_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.CENTER_LON)
    center_lat_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.CENTER_LAT)
    density_score_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.DENSITY_SCORE)
    village_count_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.VILLAGE_COUNT)
    radius_km_col = qcolumn(dbpath, T.SPATIAL_HOTSPOTS, C.SPATIAL_HOTSPOTS.RADIUS_KM)

    query = f"""
        SELECT
            {hotspot_id_col} as hotspot_id,
            {center_lon_col} as center_lon,
            {center_lat_col} as center_lat,
            {density_score_col} as density_score,
            {village_count_col} as village_count,
            {radius_km_col} as radius_km
        FROM {table}
        WHERE {run_id_col} = ? AND {hotspot_id_col} = ?
    """

    result = execute_single(db, query, (run_id, hotspot_id))
    if not result:
        raise HTTPException(status_code=404, detail=f"Hotspot {hotspot_id} not found")

    return result


@router.get("/clusters")
def get_spatial_clusters(
    run_id: Optional[str] = Query(None, description="Spatial clustering run id"),
    cluster_id: Optional[int] = Query(None, description="Cluster id filter"),
    min_size: Optional[int] = Query(None, ge=1, description="Minimum cluster size"),
    limit: int = Query(100, ge=0, description="Max records, 0 for all"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get DBSCAN cluster summaries."""
    try:
        resolved_run_id = run_id

        if resolved_run_id is None:
            try:
                resolved_run_id = get_run_id_manager(dbpath).get_active_run_id(
                    run_id_analysis_type(dbpath, T.SPATIAL_CLUSTERS)
                )
            except ValueError:
                resolved_run_id = None

            if not resolved_run_id:
                table = qtable(dbpath, T.SPATIAL_CLUSTERS)
                run_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID)
                fallback_query = f"""
                    SELECT {run_id_col} as run_id FROM {table}
                    ORDER BY {run_id_col} DESC
                    LIMIT 1
                """
                result = execute_single(db, fallback_query, ())
                if result:
                    resolved_run_id = result["run_id"]

        if not resolved_run_id:
            raise HTTPException(status_code=404, detail="No spatial clusters data found in database")

        table = qtable(dbpath, T.SPATIAL_CLUSTERS)
        run_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID)
        cluster_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_ID)
        cluster_size_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_SIZE)
        centroid_lon_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CENTROID_LON)
        centroid_lat_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CENTROID_LAT)
        avg_distance_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.AVG_DISTANCE_KM)
        dominant_city_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.DOMINANT_CITY)
        dominant_county_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.DOMINANT_COUNTY)

        query = f"""
            SELECT
                {cluster_id_col} as cluster_id,
                {cluster_size_col} as cluster_size,
                {centroid_lon_col} as centroid_lon,
                {centroid_lat_col} as centroid_lat,
                {avg_distance_col} as avg_distance_km,
                {dominant_city_col} as dominant_city,
                {dominant_county_col} as dominant_county
            FROM {table}
            WHERE {run_id_col} = ?
        """
        params = [resolved_run_id]

        if cluster_id is not None:
            query += f" AND {cluster_id_col} = ?"
            params.append(cluster_id)

        if min_size is not None:
            query += f"""
                AND {cluster_id_col} IN (
                    SELECT {cluster_id_col}
                    FROM {table}
                    WHERE {run_id_col} = ?
                    GROUP BY {cluster_id_col}
                    HAVING COUNT(*) >= ?
                )
            """
            params.extend([resolved_run_id, min_size])

        query += f" ORDER BY {cluster_id_col}"

        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        results = execute_query(db, query, tuple(params))
        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No spatial clusters found for run_id: {resolved_run_id}",
            )

        return results
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(status_code=404, detail="Spatial clusters data table is not available")
        raise HTTPException(status_code=500, detail=f"Spatial cluster query failed: {str(e)}")


@router.get("/clusters/summary")
def get_cluster_summary(
    run_id: Optional[str] = Query(None, description="Spatial clustering run id"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get cluster summary statistics."""
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.SPATIAL_CLUSTERS)
        )

    table = qtable(dbpath, T.SPATIAL_CLUSTERS)
    run_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID)
    cluster_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_ID)
    cluster_size_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_SIZE)
    avg_distance_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.AVG_DISTANCE_KM)
    centroid_lon_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CENTROID_LON)
    centroid_lat_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CENTROID_LAT)

    query = f"""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT {cluster_id_col}) as unique_clusters,
            AVG({cluster_size_col}) as avg_cluster_size,
            MIN({cluster_size_col}) as min_cluster_size,
            MAX({cluster_size_col}) as max_cluster_size,
            SUM({cluster_size_col}) as total_villages,
            SUM(CASE WHEN {cluster_id_col} = -1 THEN 1 ELSE 0 END) as noise_count,
            AVG({avg_distance_col}) as avg_distance,
            MIN({centroid_lon_col}) as min_lon,
            MAX({centroid_lon_col}) as max_lon,
            MIN({centroid_lat_col}) as min_lat,
            MAX({centroid_lat_col}) as max_lat
        FROM {table}
        WHERE {run_id_col} = ?
    """

    result = execute_single(db, query, (run_id,))
    if not result:
        raise HTTPException(status_code=404, detail=f"No cluster summary found for run_id: {run_id}")

    valid_clusters = result["unique_clusters"]
    if result["noise_count"] > 0:
        valid_clusters -= 1

    return {
        "run_id": run_id,
        "total_records": result["total_records"],
        "total_clusters": valid_clusters,
        "noise_points": result["noise_count"],
        "total_villages": result["total_villages"],
        "cluster_size": {
            "avg": result["avg_cluster_size"],
            "min": result["min_cluster_size"],
            "max": result["max_cluster_size"],
        },
        "spatial_extent": {
            "avg_distance_km": result["avg_distance"],
            "lon_range": [result["min_lon"], result["max_lon"]],
            "lat_range": [result["min_lat"], result["max_lat"]],
        },
    }


@router.get("/clusters/available-runs")
def get_available_cluster_runs(
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get available cluster run ids."""
    table = qtable(dbpath, T.SPATIAL_CLUSTERS)
    run_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID)
    cluster_id_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_ID)
    cluster_size_col = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_SIZE)

    query = f"""
        SELECT
            {run_id_col} as run_id,
            COUNT(*) as total_records,
            COUNT(DISTINCT {cluster_id_col}) as unique_clusters,
            MIN({cluster_id_col}) as min_cluster_id,
            MAX({cluster_id_col}) as max_cluster_id,
            AVG({cluster_size_col}) as avg_cluster_size,
            MAX({cluster_size_col}) as max_cluster_size,
            SUM(CASE WHEN {cluster_id_col} = -1 THEN 1 ELSE 0 END) as noise_count
        FROM {table}
        GROUP BY {run_id_col}
        ORDER BY {run_id_col}
    """

    results = execute_query(db, query, ())
    if not results:
        raise HTTPException(status_code=404, detail="No clustering runs found")

    active_run_id = get_run_id_manager(dbpath).get_active_run_id(
        run_id_analysis_type(dbpath, T.SPATIAL_CLUSTERS)
    )
    for result in results:
        result["is_active"] = result["run_id"] == active_run_id

    return {
        "active_run_id": active_run_id,
        "available_runs": results,
    }
