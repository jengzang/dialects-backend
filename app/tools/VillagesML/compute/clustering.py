"""
聚类计算API (Clustering Computation API)

提供参数化的聚类分析接口：
- POST /api/compute/clustering/run - 执行聚类分析
- POST /api/compute/clustering/scan - 参数扫描
- GET /api/compute/clustering/cache-stats - 缓存统计
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import logging

from .validators import ClusteringParams, ClusteringScanParams
from .cache import compute_cache
from .engine import ClusteringEngine
from .timeout import timeout, TimeoutException
from ..config import get_db_path

# 导入身份验证依赖
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/clustering")


def get_clustering_engine():
    """获取聚类引擎实例"""
    db_path = get_db_path()
    return ClusteringEngine(db_path)


@router.post("/run")
async def run_clustering(
    params: ClusteringParams,
    user: Optional[User] = Depends(ApiLimiter),  # 添加身份验证
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    执行聚类分析（需要登录）

    Args:
        params: 聚类参数
        user: 当前用户（由 ApiLimiter 自动验证）

    Returns:
        聚类结果

    Raises:
        HTTPException: 如果未登录、计算失败或超时
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

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

    except Exception as e:
        logger.error(f"Clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.post("/scan")
async def scan_clustering_params(
    params: ClusteringScanParams,
    user: Optional[User] = Depends(ApiLimiter),  # 添加身份验证
    engine: ClusteringEngine = Depends(get_clustering_engine)
) -> Dict[str, Any]:
    """
    扫描聚类参数（多个k值）（需要登录）

    Args:
        params: 扫描参数
        user: 当前用户（由 ApiLimiter 自动验证）

    Returns:
        扫描结果

    Raises:
        HTTPException: 如果未登录、计算失败或超时
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="此功能需要登录")

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

                # 执行聚类
                result = engine.run_clustering(clustering_params)

                # 提取评估指标
                scan_result = {
                    'k': k,
                    params.metric: result['metrics'][params.metric],
                    'execution_time_ms': result['execution_time_ms']
                }
                results.append(scan_result)

        total_time = int((time.time() - total_start_time) * 1000)

        # 找到最佳k值
        best_result = max(results, key=lambda x: x[params.metric])

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


import time
