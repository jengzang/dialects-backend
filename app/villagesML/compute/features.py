"""
特征提取API (Feature Extraction API)

提供村庄特征提取和区域聚合接口：
- POST /api/compute/features/extract - 批量特征提取
- POST /api/compute/features/aggregate - 区域特征聚合
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from .validators import FeatureExtractionParams, FeatureAggregationParams
from .cache import compute_cache
from .engine import FeatureEngine
from .timeout import timeout, TimeoutException
from ..config import get_db_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute/features")


def get_feature_engine():
    """获取特征引擎实例"""
    db_path = get_db_path()
    return FeatureEngine(db_path)


@router.post("/extract")
async def extract_features(
    params: FeatureExtractionParams,
    engine: FeatureEngine = Depends(get_feature_engine)
) -> Dict[str, Any]:
    """
    批量提取村庄特征（需要登录）

    Args:
        params: 提取参数
    Returns:
        特征提取结果

    Raises:
        HTTPException: 如果提取失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("feature_extract", params.dict())
        if cached_result:
            logger.info("Returning cached extraction result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Extracting features for {len(params.villages)} villages")

        # 执行提取（带超时控制）
        with timeout(3):  # 3秒超时
            result = engine.extract_features(params.dict())

        # 缓存结果
        compute_cache.set("feature_extract", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Feature extraction timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except Exception as e:
        logger.error(f"Feature extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/aggregate")
async def aggregate_features(
    params: FeatureAggregationParams,
    engine: FeatureEngine = Depends(get_feature_engine)
) -> Dict[str, Any]:
    """
    聚合区域特征（需要登录）

    Args:
        params: 聚合参数
    Returns:
        特征聚合结果

    Raises:
        HTTPException: 如果聚合失败或超时
    """
    try:
        # 检查缓存
        cached_result = compute_cache.get("feature_aggregate", params.dict())
        if cached_result:
            logger.info("Returning cached aggregation result")
            cached_result['from_cache'] = True
            return cached_result

        logger.info(f"Aggregating features for {len(params.region_names)} regions")

        # 执行聚合（带超时控制）
        with timeout(5):  # 5秒超时
            result = engine.aggregate_features(params.dict())

        # 缓存结果
        compute_cache.set("feature_aggregate", params.dict(), result)

        result['from_cache'] = False
        return result

    except TimeoutException as e:
        logger.error(f"Feature aggregation timeout: {str(e)}")
        raise HTTPException(status_code=408, detail=str(e))

    except Exception as e:
        logger.error(f"Feature aggregation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")


