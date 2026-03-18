"""Spatial hotspot and cluster APIs."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import execute_query, execute_single, get_db
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/spatial")


@router.get("/hotspots")
def get_spatial_hotspots(
    run_id: Optional[str] = Query(None, description="Spatial analysis run id"),
    min_density: Optional[float] = Query(None, description="Minimum density score"),
    min_village_count: Optional[int] = Query(None, ge=1, description="Minimum village count"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Get spatial density hotspots."""
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            hotspot_id,
            center_lon,
            center_lat,
            density_score,
            village_count,
            radius_km
        FROM spatial_hotspots
        WHERE run_id = ?
    """
    params = [run_id]

    if min_density is not None:
        query += " AND density_score >= ?"
        params.append(min_density)

    if min_village_count is not None:
        query += " AND village_count >= ?"
        params.append(min_village_count)

    query += " ORDER BY density_score DESC"
    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail=f"No spatial hotspots found for run_id: {run_id}")

    return results


@router.get("/hotspots/{hotspot_id}")
def get_hotspot_detail(
    hotspot_id: int,
    run_id: Optional[str] = Query(None, description="Spatial analysis run id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Get one hotspot detail."""
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            hotspot_id,
            center_lon,
            center_lat,
            density_score,
            village_count,
            radius_km
        FROM spatial_hotspots
        WHERE run_id = ? AND hotspot_id = ?
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
):
    """Get DBSCAN cluster summaries."""
    try:
        resolved_run_id = run_id

        if resolved_run_id is None:
            try:
                resolved_run_id = run_id_manager.get_active_run_id("spatial_clusters")
            except ValueError:
                resolved_run_id = None

            if not resolved_run_id:
                fallback_query = """
                    SELECT run_id FROM spatial_clusters
                    ORDER BY run_id DESC
                    LIMIT 1
                """
                result = execute_single(db, fallback_query, ())
                if result:
                    resolved_run_id = result["run_id"]

        if not resolved_run_id:
            raise HTTPException(status_code=404, detail="No spatial clusters data found in database")

        query = """
            SELECT
                cluster_id,
                cluster_size,
                centroid_lon,
                centroid_lat,
                avg_distance_km,
                dominant_city,
                dominant_county
            FROM spatial_clusters
            WHERE run_id = ?
        """
        params = [resolved_run_id]

        if cluster_id is not None:
            query += " AND cluster_id = ?"
            params.append(cluster_id)

        if min_size is not None:
            query += """
                AND cluster_id IN (
                    SELECT cluster_id
                    FROM spatial_clusters
                    WHERE run_id = ?
                    GROUP BY cluster_id
                    HAVING COUNT(*) >= ?
                )
            """
            params.extend([resolved_run_id, min_size])

        query += " ORDER BY cluster_id"

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
):
    """Get cluster summary statistics."""
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT cluster_id) as unique_clusters,
            AVG(cluster_size) as avg_cluster_size,
            MIN(cluster_size) as min_cluster_size,
            MAX(cluster_size) as max_cluster_size,
            SUM(cluster_size) as total_villages,
            SUM(CASE WHEN cluster_id = -1 THEN 1 ELSE 0 END) as noise_count,
            AVG(avg_distance_km) as avg_distance,
            MIN(centroid_lon) as min_lon,
            MAX(centroid_lon) as max_lon,
            MIN(centroid_lat) as min_lat,
            MAX(centroid_lat) as max_lat
        FROM spatial_clusters
        WHERE run_id = ?
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
def get_available_cluster_runs(db: sqlite3.Connection = Depends(get_db)):
    """Get available cluster run ids."""
    query = """
        SELECT
            run_id,
            COUNT(*) as total_records,
            COUNT(DISTINCT cluster_id) as unique_clusters,
            MIN(cluster_id) as min_cluster_id,
            MAX(cluster_id) as max_cluster_id,
            AVG(cluster_size) as avg_cluster_size,
            MAX(cluster_size) as max_cluster_size,
            SUM(CASE WHEN cluster_id = -1 THEN 1 ELSE 0 END) as noise_count
        FROM spatial_clusters
        GROUP BY run_id
        ORDER BY run_id
    """

    results = execute_query(db, query, ())
    if not results:
        raise HTTPException(status_code=404, detail="No clustering runs found")

    active_run_id = run_id_manager.get_active_run_id("spatial_hotspots")
    for result in results:
        result["is_active"] = result["run_id"] == active_run_id

    return {
        "active_run_id": active_run_id,
        "available_runs": results,
    }
