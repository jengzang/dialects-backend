"""
聚类计算API (Clustering Computation API)

提供参数化的聚类分析接口：
- POST /api/compute/clustering/run - 执行聚类分析
- POST /api/compute/clustering/scan - 参数扫描
- GET /api/compute/clustering/cache-stats - 缓存统计
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging
import time

from .validators import ClusteringParams, ClusteringScanParams, CharacterTendencyClusteringParams, SampledVillageClusteringParams, SpatialAwareClusteringParams, HierarchicalClusteringParams
from .cache import compute_cache
from .engine import ClusteringEngine
from .timeout import timeout, TimeoutException
from ..config import get_db_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/clustering")


def get_clustering_engine():
    """获取聚类引擎实例"""
    db_path = get_db_path()
    return ClusteringEngine(db_path)


@router.post("/run")
async def run_clustering(
    params: ClusteringParams,
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    执行聚类分析（需要登录）

    Args:
        params: 聚类参数
    Returns:
        聚类结果

    Raises:
        HTTPException: 如果计算失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("clustering_run", params.dict())
        if cached_result:
            logger.info("Returning cached clustering result")
            cached_result['from_cache'] = True
            return cached_result

        # 执行聚类（带超时控制）
        logger.info(f"Running clustering: {params.algorithm}, k={params.k}, level={params.region_level}")

        with timeout(5):  # 5秒超时
            result = engine.run_clustering(params.dict())

        # 缓存结果
        compute_cache.set("clustering_run", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Clustering timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Clustering validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.post("/scan")
async def scan_clustering_params(
    params: ClusteringScanParams,
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    扫描聚类参数（多个k值）（需要登录）

    Args:
        params: 扫描参数
    Returns:
        扫描结果

    Raises:
        HTTPException: 如果计算失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("clustering_scan", params.dict())
        if cached_result:
            logger.info("Returning cached scan result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Scanning k values: {params.k_range}")

        results = []
        total_start_time = time.time()

        with timeout(15):  # 15秒总超时
            for k in params.k_range:
                # 构建单次聚类参数
                clustering_params = {
                    'algorithm': params.algorithm,
                    'k': k,
                    'region_level': params.region_level,
                    'features': params.features.dict(),
                    'preprocessing': {'standardize': True, 'use_pca': True, 'pca_n_components': 50},
                    'random_state': 42
                }

                # 执行聚类（优先复用单次聚类缓存，减少重复计算）
                cached_run_result = compute_cache.get("clustering_run", clustering_params)
                if cached_run_result:
                    result = cached_run_result
                else:
                    result = engine.run_clustering(clustering_params)
                    compute_cache.set("clustering_run", clustering_params, result)
                metrics = result.get('metrics', {})
                metric_value = metrics.get(params.metric)

                # 提取评估指标
                scan_result = {
                    'k': k,
                    params.metric: metric_value,
                    'execution_time_ms': result.get('execution_time_ms', 0)
                }
                results.append(scan_result)

        total_time = int((time.time() - total_start_time) * 1000)

        # 找到最佳k值
        valid_results = [r for r in results if r.get(params.metric) is not None]
        if not valid_results:
            raise HTTPException(
                status_code=422,
                detail=f"Metric '{params.metric}' unavailable for all scanned k values."
            )

        if params.metric == "davies_bouldin_index":
            best_result = min(valid_results, key=lambda x: x[params.metric])
        else:
            best_result = max(valid_results, key=lambda x: x[params.metric])

        scan_output = {
            'scan_id': f"scan_{int(time.time())}",
            'results': results,
            'best_k': best_result['k'],
            'best_score': best_result[params.metric],
            'total_time_ms': total_time,
            'from_cache': False
        }

        # 缓存结果
        compute_cache.set("clustering_scan", params.dict(), scan_output)

        return scan_output

    except TimeoutException as e:
        logger.error(f"Scan timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Scan validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Scan error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/cache-stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息

    Returns:
        缓存统计
    """
    return compute_cache.get_stats()


@router.delete("/cache")
async def clear_cache() -> Dict[str, str]:
    """
    清除缓存

    Returns:
        操作结果
    """
    compute_cache.clear("clustering")
    return {"status": "success", "message": "Clustering cache cleared"}


@router.post("/character-tendency")
async def run_character_tendency_clustering(
    params: CharacterTendencyClusteringParams,
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    执行字符倾向性聚类（需要登录）

    基于字符使用模式（lift/z_score）对区域进行聚类

    Args:
        params: 字符倾向性聚类参数
    Returns:
        聚类结果

    Raises:
        HTTPException: 如果计算失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("character_tendency", params.dict())
        if cached_result:
            logger.info("Returning cached character tendency clustering result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Running character tendency clustering: {params.algorithm}, level={params.region_level}, metric={params.tendency_metric}")

        with timeout(5):
            result = engine.run_character_tendency_clustering(params.dict())

        # 缓存结果
        compute_cache.set("character_tendency", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Character tendency clustering timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Character tendency validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Character tendency clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Character tendency clustering failed: {str(e)}")


@router.post("/sampled-villages")
async def run_sampled_village_clustering(
    params: SampledVillageClusteringParams,
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    执行采样村庄聚类（需要登录）

    对28.5万村庄进行智能采样后聚类

    Args:
        params: 采样村庄聚类参数
    Returns:
        聚类结果

    Raises:
        HTTPException: 如果计算失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("sampled_villages", params.dict())
        if cached_result:
            logger.info("Returning cached sampled village clustering result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Running sampled village clustering: {params.algorithm}, strategy={params.sampling_strategy}, size={params.sample_size}")

        with timeout(60):
            result = engine.run_sampled_village_clustering(params.dict())

        # 缓存结果
        compute_cache.set("sampled_villages", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Sampled village clustering timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Sampled village validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Sampled village clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sampled village clustering failed: {str(e)}")


@router.post("/spatial-aware")
async def run_spatial_aware_clustering(
    params: SpatialAwareClusteringParams,
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    执行空间感知聚类（需要登录）

    对已有的空间聚类结果进行二次聚类

    Args:
        params: 空间感知聚类参数
    Returns:
        聚类结果

    Raises:
        HTTPException: 如果计算失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("spatial_aware", params.dict())
        if cached_result:
            logger.info("Returning cached spatial-aware clustering result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Running spatial-aware clustering: {params.algorithm}, run_id={params.spatial_run_id}")

        with timeout(5):
            result = engine.run_spatial_aware_clustering(params.dict())

        # 缓存结果
        compute_cache.set("spatial_aware", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Spatial-aware clustering timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Spatial-aware validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Spatial-aware clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Spatial-aware clustering failed: {str(e)}")


@router.post("/hierarchical")
async def run_hierarchical_clustering(
    params: HierarchicalClusteringParams,
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    执行层次聚类（需要登录）

    展示市→县→镇的嵌套聚类结构

    Args:
        params: 层次聚类参数
    Returns:
        层次聚类结果

    Raises:
        HTTPException: 如果计算失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("hierarchical", params.dict())
        if cached_result:
            logger.info("Returning cached hierarchical clustering result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Running hierarchical clustering: {params.algorithm}, k_city={params.k_city}, k_county={params.k_county}, k_township={params.k_township}")

        # 层次聚类可能需要更长时间
        with timeout(8):
            result = engine.run_hierarchical_clustering(params.dict())

        # 缓存结果
        compute_cache.set("hierarchical", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Hierarchical clustering timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except HTTPException:
        raise

    except ValueError as e:
        logger.warning(f"Hierarchical validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Hierarchical clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Hierarchical clustering failed: {str(e)}")
